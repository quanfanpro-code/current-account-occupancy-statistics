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

    def validate(self) -> None:
        required = {
            "trans_file": self.trans_file,
            "trans_sheet": self.trans_sheet,
            "balance_file": self.balance_file,
            "balance_sheet": self.balance_sheet,
            "col_name": self.col_name,
            "col_debit": self.col_debit,
            "col_credit": self.col_credit,
            "col_date": self.col_date,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"以下配置缺失: {joined}")
        # 校验列映射不能重复（如借方和贷方映射到同一列）
        col_mappings = [
            ("往来单位", self.col_name),
            ("借方发生额", self.col_debit),
            ("贷方发生额", self.col_credit),
            ("记账日期", self.col_date),
        ]
        seen: dict[str, str] = {}
        for label, col_name in col_mappings:
            if col_name in seen:
                raise ValueError(
                    f'列映射冲突: "{label}" 与 "{seen[col_name]}" 都映射到了 "{col_name}"，'
                    "请选择不同的列。"
                )
            seen[col_name] = label

    def build_output_path(self) -> str:
        balance_path = Path(self.balance_file)
        output_dir = Path(self.output_dir)
        return str(output_dir / f"{balance_path.stem}数据已整理{balance_path.suffix}")


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
