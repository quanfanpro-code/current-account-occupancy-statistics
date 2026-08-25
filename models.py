from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import ReportNames


@dataclass(frozen=True)
class ProcessConfig:
    trans_file: str
    trans_sheet: str
    balance_file: str
    balance_sheet: str
    output_dir: str
    col_name: str
    col_debit: str
    col_credit: str
    col_date: str
    # 可选：序时账“科目”列，选了之后只保留往来科目（应收账款等）的记录
    col_account: str = ""

    def validate(self) -> None:
        # 期初余额表可选：不填则所有单位期初余额按 0 处理
        required = {
            "trans_file": self.trans_file,
            "trans_sheet": self.trans_sheet,
            "col_name": self.col_name,
            "col_debit": self.col_debit,
            "col_credit": self.col_credit,
            "col_date": self.col_date,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"以下配置缺失: {joined}")
        if self.balance_file and not self.balance_sheet:
            raise ValueError("已选择期初余额表文件，但未选择 Sheet")
        # 校验列映射不能重复（如借方和贷方映射到同一列）
        col_mappings = [
            ("往来单位", self.col_name),
            ("借方发生额", self.col_debit),
            ("贷方发生额", self.col_credit),
            ("记账日期", self.col_date),
        ]
        if self.col_account:
            col_mappings.append(("科目筛选", self.col_account))
        seen: dict[str, str] = {}
        for label, col_name in col_mappings:
            if col_name in seen:
                raise ValueError(
                    f'列映射冲突: "{label}" 与 "{seen[col_name]}" 都映射到了 "{col_name}"，'
                    "请选择不同的列。"
                )
            seen[col_name] = label

    def build_output_path(self) -> str:
        # 未提供余额表时用序时账文件名生成输出文件名
        source_path = Path(self.balance_file or self.trans_file)
        output_dir = Path(self.output_dir)
        return str(output_dir / f"{source_path.stem}数据已整理{source_path.suffix}")


@dataclass
class ReportBundle:
    balance: pd.DataFrame
    summary: pd.DataFrame
    stats_occupied: pd.DataFrame
    stats_occupying: pd.DataFrame
    detail_occupied: pd.DataFrame
    detail_occupying: pd.DataFrame

    def to_sheet_map(self) -> dict[str, pd.DataFrame]:
        return {
            ReportNames.balance: self.balance,
            ReportNames.summary: self.summary,
            ReportNames.stats_occupied: self.stats_occupied,
            ReportNames.stats_occupying: self.stats_occupying,
            ReportNames.detail_occupied: self.detail_occupied,
            ReportNames.detail_occupying: self.detail_occupying,
        }
