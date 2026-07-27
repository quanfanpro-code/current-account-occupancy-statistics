from __future__ import annotations

import gc
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from .config import ColumnNames, EXCEL_MAX_ROWS, ReportNames, ZERO_THRESHOLD
from .models import ReportBundle
from .precision import PrecisionEngine


class ReportBuilder:
    def __init__(self, max_workers: int | None = None) -> None:
        cpu_count = max_workers or max(1, multiprocessing.cpu_count())
        self.max_workers = min(2, cpu_count)

    def unpivot_and_filter_data(self, df, id_vars, value_vars, var_name, value_name):
        if df.empty or not value_vars:
            return pd.DataFrame(columns=list(id_vars) + [var_name, value_name])
        # 选取列后去除重复列名（保底，防止上游有遗漏）
        selected = df[list(id_vars) + list(value_vars)].loc[:, ~df[list(id_vars) + list(value_vars)].columns.duplicated()]
        # 用 melt 替代 stack，避免 stack 对重复列/索引敏感的问题
        try:
            melted = selected.melt(
                id_vars=list(id_vars),
                value_vars=[c for c in selected.columns if c not in id_vars],
                var_name=var_name,
                value_name=value_name,
            )
        except (TypeError, ValueError):
            # 极端情况：melt 也失败时回退到 stack + dropna
            subset = selected.set_index(list(id_vars))
            stacked = subset.stack(dropna=True).reset_index()
            melted = stacked
        # 过滤零值与空值
        if value_name in melted.columns:
            melted[value_name] = pd.to_numeric(melted[value_name], errors="coerce")
            melted = melted[melted[value_name].abs() > ZERO_THRESHOLD]
            melted[value_name] = melted[value_name].fillna(0)
        return melted.reset_index(drop=True)

    def calculate_statistics(self, df_detail, unit_col=ColumnNames.unit, amount_col=ColumnNames.amount, new_suppliers=None, all_suppliers=None, total_days=None):
        df_detail = df_detail.copy()
        if unit_col in df_detail.columns:
            df_detail = df_detail[df_detail[unit_col].notna()]
            df_detail = df_detail[df_detail[unit_col].astype(str).str.strip() != ""]
            df_detail = df_detail[~df_detail[unit_col].astype(str).isin(["nan", "None"])]
        if df_detail.empty and not all_suppliers:
            return pd.DataFrame(columns=[unit_col, "占用时间", amount_col, "日均占用额", "备注"])
        if df_detail.empty:
            stats = pd.DataFrame(columns=[unit_col, "占用时间", amount_col, "日均占用额"])
        else:
            stats = df_detail.groupby(unit_col)[amount_col].agg(count="count", sum="sum").reset_index()
            stats.columns = [unit_col, "占用时间", amount_col]
            # 全周期平均：总金额 / 全周期天数；若未传入总天数则回退到占用天数平均
            divisor = total_days if total_days else stats["占用时间"].replace(0, 1)
            stats["日均占用额"] = stats[amount_col] / divisor
        if all_suppliers:
            full = pd.DataFrame({unit_col: all_suppliers})
            stats = full.merge(stats, on=unit_col, how="left")
            stats["占用时间"] = stats["占用时间"].fillna(0).astype("int64")
            stats[amount_col] = stats[amount_col].fillna(0)
            stats["日均占用额"] = stats["日均占用额"].fillna(0)
        stats = stats.assign(_abs=stats["日均占用额"].abs()).sort_values(by=["_abs", amount_col], ascending=[False, False]).drop(columns=["_abs"])
        new_set = set(new_suppliers or [])
        stats["备注"] = stats[unit_col].apply(lambda value: "该单位仅存在于序时账" if value in new_set else "")
        return stats.reset_index(drop=True)

    def optimize_and_limit_data(self, df, value_col, limit=EXCEL_MAX_ROWS):
        if df.empty or value_col not in df.columns:
            return df
        result = df.copy()
        result["_abs"] = pd.to_numeric(result[value_col], errors="coerce").fillna(0).abs()
        if len(result) > limit:
            result = result.nlargest(limit, "_abs")
        else:
            result = result.sort_values("_abs", ascending=False)
        return result.drop(columns=["_abs"]).reset_index(drop=True)

    def build_bundle(self, df_balance, supplier_columns, new_suppliers, progress_callback) -> ReportBundle:
        progress_callback(40, "正在生成报表数据", "报表生成阶段")
        # 保底：去除 DataFrame 中的重复列名
        df_balance = df_balance.loc[:, ~df_balance.columns.duplicated()]
        date_col_name = df_balance.columns[0]
        effective_date_col = date_col_name
        value_vars = [column for column in df_balance.columns if column != date_col_name]
        unit_col_name = ColumnNames.unit
        temp_date_col = None
        if date_col_name == unit_col_name:
            temp_date_col = f"_temp_date_{id(df_balance)}"
            work_df = df_balance.rename(columns={date_col_name: temp_date_col})
            id_vars = [temp_date_col]
        else:
            work_df = df_balance.copy()
            id_vars = [date_col_name]
        unpivoted = self.unpivot_and_filter_data(work_df, id_vars=id_vars, value_vars=value_vars, var_name=unit_col_name, value_name=ColumnNames.amount)
        if temp_date_col and temp_date_col in unpivoted.columns:
            restored_date_name = "日期" if date_col_name == unit_col_name else date_col_name
            effective_date_col = restored_date_name
            unpivoted = unpivoted.rename(columns={temp_date_col: restored_date_name})
        if ColumnNames.amount in unpivoted.columns:
            unpivoted[ColumnNames.amount] = PrecisionEngine.from_integer_cents(unpivoted[ColumnNames.amount])
        unpivoted[ColumnNames.amount] = unpivoted[ColumnNames.amount].fillna(0)
        occupied = unpivoted[unpivoted[ColumnNames.amount] > 0].copy()
        occupying = unpivoted[unpivoted[ColumnNames.amount] < 0].copy()
        # 计算全周期天数：数据中最早日期到最晚日期的总天数
        if effective_date_col in unpivoted.columns and not unpivoted.empty:
            date_series = pd.to_datetime(unpivoted[effective_date_col])
            total_days = max(1, (date_series.max() - date_series.min()).days + 1)
        else:
            total_days = None
        all_suppliers = supplier_columns + new_suppliers
        summary = self.calculate_statistics(unpivoted, new_suppliers=new_suppliers, all_suppliers=all_suppliers, total_days=total_days)
        summary = summary[summary[ColumnNames.amount].fillna(0) != 0].reset_index(drop=True)
        del unpivoted
        gc.collect()

        def build_side(detail_frame: pd.DataFrame):
            stats = self.calculate_statistics(detail_frame, new_suppliers=new_suppliers, total_days=total_days)
            if effective_date_col in detail_frame.columns:
                detail_frame[effective_date_col] = pd.to_datetime(detail_frame[effective_date_col]).dt.strftime("%Y-%m-%d")
            detail = self.optimize_and_limit_data(detail_frame, ColumnNames.amount)
            return stats, detail

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_occupied = executor.submit(build_side, occupied.copy())
            future_occupying = executor.submit(build_side, occupying.copy())
            stats_occupied, detail_occupied = future_occupied.result()
            stats_occupying, detail_occupying = future_occupying.result()

        formatted_balance = df_balance.copy()
        formatted_balance[date_col_name] = pd.to_datetime(formatted_balance[date_col_name]).dt.strftime("%Y-%m-%d")
        for column in supplier_columns + new_suppliers:
            if column in formatted_balance.columns:
                formatted_balance[column] = PrecisionEngine.from_integer_cents(formatted_balance[column])
        progress_callback(48, "报表数据生成完成", "报表生成阶段")
        return ReportBundle(
            balance=formatted_balance,
            summary=summary,
            stats_occupied=stats_occupied,
            stats_occupying=stats_occupying,
            detail_occupied=detail_occupied,
            detail_occupying=detail_occupying,
        )

    def build_from_balance(self, df_balance, new_suppliers):
        noop = lambda *_args, **_kwargs: None
        bundle = self.build_bundle(df_balance, [column for column in df_balance.columns[1:]], new_suppliers, noop)
        return {
            "balance": bundle.balance,
            "summary": bundle.summary,
            "stats_occupied": bundle.stats_occupied,
            "stats_occupying": bundle.stats_occupying,
            "detail_occupied": bundle.detail_occupied,
            "detail_occupying": bundle.detail_occupying,
        }
