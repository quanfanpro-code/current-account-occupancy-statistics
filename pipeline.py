from __future__ import annotations

import pandas as pd

from .config import CURRENT_ACCOUNT_KEYWORDS, detect_account_column
from .models import ProcessConfig
from .precision import PrecisionEngine


class FinancePipeline:
    def preprocess_data(
        self,
        df_balance: pd.DataFrame | None,
        df_trans: pd.DataFrame,
        config: ProcessConfig,
        progress_callback,
    ) -> tuple[pd.DataFrame | None, pd.DataFrame]:
        progress_callback(10, "开始数据预处理", "数据预处理阶段")

        # 期初余额表可选：未提供时跳过余额表预处理，期初余额一律按 0 处理
        if df_balance is not None:
            date_col_name = self._detect_balance_date_column(df_balance)
            df_balance = df_balance.copy()

            # 去除余额表中的重复列名，只保留首次出现的列
            df_balance = df_balance.loc[:, ~df_balance.columns.duplicated()]

            df_balance[date_col_name] = pd.to_datetime(df_balance[date_col_name], errors="coerce").dt.normalize()
            df_balance = df_balance.dropna(subset=[date_col_name]).sort_values(date_col_name).reset_index(drop=True)
            if df_balance.empty:
                raise ValueError(
                    f"余额表的日期列「{date_col_name}」无法解析为有效日期，"
                    "请确认该列是否为日期格式。"
                )

            balance_columns = [col for col in df_balance.columns if col != date_col_name]
            if balance_columns:
                # 使用 Decimal 精确舍入，与 to_integer_cents 保持一致，
                # 避免浮点数 banker's rounding 陷阱（如 0.015 被 float round(2) 错误舍入为 0.01）
                for col in balance_columns:
                    df_balance[col] = PrecisionEngine.to_integer_cents(df_balance[col])

        df_trans = df_trans.copy()
        df_trans[config.col_name] = df_trans[config.col_name].astype(str).str.strip()
        # 第一重筛选：必须有往来单位明细，单位为空的行直接丢弃
        before = len(df_trans)
        df_trans = df_trans[~df_trans[config.col_name].isin(["", "nan", "None"])]
        dropped_empty = before - len(df_trans)
        if dropped_empty:
            progress_callback(14, f"忽略无往来单位明细的记录 {dropped_empty} 条", "数据预处理阶段")
        # 第二重筛选：自动识别科目列（优先一级科目），只保留八大往来科目。
        # 去掉开头的科目编码（数字、点、空格）后，按前缀与关键字比对，
        # 兼容“1122 应收账款”“应收账款\某公司”等写法
        account_col = config.col_account or detect_account_column(df_trans.columns)
        if account_col:
            name_part = df_trans[account_col].astype(str).str.strip().str.replace(r"^[\d.\s]+", "", regex=True)
            before = len(df_trans)
            df_trans = df_trans[name_part.str.startswith(CURRENT_ACCOUNT_KEYWORDS)]
            progress_callback(
                15,
                f"自动识别科目列「{account_col}」：保留往来科目 {len(df_trans)} 条，忽略非往来科目 {before - len(df_trans)} 条",
                "数据预处理阶段",
            )
        df_trans[config.col_debit] = PrecisionEngine.to_integer_cents(df_trans[config.col_debit])
        df_trans[config.col_credit] = PrecisionEngine.to_integer_cents(df_trans[config.col_credit])
        df_trans[config.col_date] = pd.to_datetime(df_trans[config.col_date], errors="coerce").dt.normalize()
        df_trans = df_trans.dropna(subset=[config.col_date]).reset_index(drop=True)
        progress_callback(20, "数据预处理完成", "数据预处理阶段")
        return df_balance, df_trans

    def calculate_balances(
        self,
        df_balance: pd.DataFrame | None,
        df_trans: pd.DataFrame,
        config: ProcessConfig,
        progress_callback,
    ) -> tuple[pd.DataFrame, list[str], list[str]]:
        progress_callback(25, "正在计算每日余额", "核心计算阶段")
        if df_balance is None:
            # 未提供期初余额表：没有固定供应商列，日期范围完全由序时账决定
            date_col_name = "日期"
            supplier_columns = []
        else:
            date_col_name = self._detect_balance_date_column(df_balance)
            supplier_columns = [col for col in df_balance.columns if col != date_col_name and str(col).strip() and not str(col).startswith("Unnamed")]
            supplier_columns = list(dict.fromkeys(supplier_columns))

        all_trans_suppliers = list(dict.fromkeys(df_trans[config.col_name].tolist()))
        new_suppliers = [item for item in all_trans_suppliers if item not in supplier_columns]
        all_target_columns = supplier_columns + new_suppliers
        # 排除与日期列同名的供应商列，并去除内部重复列，避免 concat 后出现重复列
        all_target_columns = list(dict.fromkeys(c for c in all_target_columns if c != date_col_name))

        df_trans_filtered = df_trans[df_trans[config.col_name].isin(all_target_columns)].copy()
        df_trans_filtered["net_amount"] = df_trans_filtered[config.col_debit] - df_trans_filtered[config.col_credit]

        if df_balance is None:
            # 无余额表：期初余额全为 0，起始日取序时账第一笔日期，截止日取最后一笔日期
            if df_trans_filtered.empty:
                raise ValueError("未提供期初余额表，且序时账中没有有效记录，无法确定计算区间。")
            initial_date = df_trans_filtered[config.col_date].min()
            balance_end_date = df_trans_filtered[config.col_date].max()
            initial_balances = pd.Series(dtype="int64")
        else:
            # 余额表可能有多行，取第一行作为期初余额，结束日期取余额表最后一行或交易最大日期（取较晚者）
            initial_date = df_balance[date_col_name].iloc[0]
            balance_end_date = df_balance[date_col_name].iloc[-1]
            initial_balances = df_balance.iloc[0][supplier_columns].fillna(0).astype("int64") if supplier_columns else pd.Series(dtype="int64")

        if not df_trans_filtered.empty:
            pivot = df_trans_filtered.pivot_table(
                index=config.col_date,
                columns=config.col_name,
                values="net_amount",
                aggfunc="sum",
                fill_value=0,
            )
            # 早于期初日期的交易会在 reindex 时被裁剪：余额语义正确，但必须提示用户
            early_mask = pivot.index < initial_date
            if early_mask.any():
                early_count = int((df_trans_filtered[config.col_date] < initial_date).sum())
                progress_callback(
                    28,
                    f"警告：{early_count} 条交易早于期初日期 {initial_date:%Y-%m-%d}，未纳入余额计算",
                    "核心计算阶段",
                )
            end_date = max(pivot.index.max(), balance_end_date, initial_date)
            all_dates = pd.date_range(start=initial_date, end=end_date, freq="D")
            pivot = pivot.reindex(all_dates, fill_value=0)
        else:
            end_date = max(balance_end_date, initial_date)
            all_dates = pd.date_range(start=initial_date, end=end_date, freq="D")
            pivot = pd.DataFrame(index=all_dates)

        balance_frame = pd.DataFrame({date_col_name: all_dates})
        changes = pd.DataFrame(0, index=balance_frame.index, columns=all_target_columns, dtype="int64")
        common_cols = pivot.columns.intersection(changes.columns)
        if len(common_cols) > 0:
            changes[common_cols] = pivot[common_cols].astype("int64").values
        cumulative = changes.cumsum()
        if supplier_columns:
            aligned = initial_balances.reindex(supplier_columns).fillna(0).astype("int64")
            cumulative[supplier_columns] = cumulative[supplier_columns].values + aligned.values
        result = pd.concat([balance_frame[[date_col_name]], cumulative[all_target_columns]], axis=1)
        # 最终结果再次去除重复列，保证下游无重复列
        result = result.loc[:, ~result.columns.duplicated()]
        # 调试：检查并报告重复列
        if result.columns.duplicated().any():
            dup_cols = result.columns[result.columns.duplicated()].tolist()
            progress_callback(35, f"警告：发现重复列 {dup_cols}，已自动去除", "核心计算阶段")
        progress_callback(35, "每日余额计算完成", "核心计算阶段")
        return result, supplier_columns, new_suppliers

    def calculate_balances_from_frames(
        self,
        df_balance: pd.DataFrame,
        df_trans: pd.DataFrame,
        col_name: str,
        col_debit: str,
        col_credit: str,
        col_date: str,
    ) -> pd.DataFrame:
        config = ProcessConfig(
            trans_file="",
            trans_sheet="",
            balance_file="",
            balance_sheet="",
            output_dir="",
            col_name=col_name,
            col_debit=col_debit,
            col_credit=col_credit,
            col_date=col_date,
        )
        noop = lambda *_args, **_kwargs: None
        preprocessed_balance, preprocessed_trans = self.preprocess_data(df_balance, df_trans, config, noop)
        result, _, _ = self.calculate_balances(preprocessed_balance, preprocessed_trans, config, noop)
        return result

    @staticmethod
    def _detect_balance_date_column(df_balance: pd.DataFrame) -> str:
        if df_balance.empty:
            raise ValueError("余额表不能为空")
        first_column = df_balance.columns[0]
        if "日期" in str(first_column) or "date" in str(first_column).lower():
            return first_column
        for column in df_balance.columns:
            if any(keyword in str(column) for keyword in ["日期", "时间", "Date", "date"]):
                return column
        return first_column
