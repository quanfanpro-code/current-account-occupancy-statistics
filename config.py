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
