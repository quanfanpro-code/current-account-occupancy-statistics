from dataclasses import dataclass


@dataclass(frozen=True)
class AppMetadata:
    name: str = "往来占用统计分析系统"
    version: str = "v2.0.7"
    version_date: str = "2026-08-09"


@dataclass(frozen=True)
class UiConfig:
    main_window_size: str = "980x760"
    path_entry_width: int = 320
    combo_width: int = 150
    mapping_combo_width: int = 140
    button_width: int = 120


class ColumnNames:
    unit = "往来单位"
    amount = "占用金额"


class ReportNames:
    balance = "往来单位每日余额"
    summary = "汇总数据统计"
    stats_occupied = "资金被占用情况统计"
    stats_occupying = "占用外单位资金情况统计"
    detail_occupied = "资金被占用情况明细"
    detail_occupying = "占用外单位资金明细"


EXCEL_MAX_ROWS = 1048575
ZERO_THRESHOLD = 1e-9

# 往来科目关键字：序时账“科目”列开头与其中任意一个一致，即视为往来科目参与计算
CURRENT_ACCOUNT_KEYWORDS = (
    "应收账款",
    "预付账款",
    "其他应收款",
    "应付账款",
    "预收账款",
    "其他应付款",
    "合同资产",
    "合同负债",
)

# 科目列自动识别的优先级：有一级科目看一级科目，没有再看科目名称
ACCOUNT_COLUMN_CANDIDATES = ("一级科目", "科目名称", "科目")


def detect_account_column(columns) -> str:
    """在序时账列名中自动寻找科目列，找不到返回空字符串"""
    columns = [str(col) for col in columns]
    for keyword in ACCOUNT_COLUMN_CANDIDATES:
        for col in columns:
            if keyword in col:
                return col
    return ""
