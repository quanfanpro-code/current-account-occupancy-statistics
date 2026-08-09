from pathlib import Path

from 往来占用统计.config import AppMetadata, ColumnNames, ReportNames


def test_config_is_valid_utf8_and_importable():
    """config.py 必须是合法 UTF-8，且 8 个中文常量无损坏"""
    data = (Path(__file__).resolve().parents[1] / "config.py").read_bytes()
    data.decode("utf-8")  # 损坏时抛 UnicodeDecodeError
    assert AppMetadata().name == "往来占用统计分析系统"
    assert ColumnNames.unit == "往来单位"
    assert ReportNames.balance == "往来单位每日余额"
    assert ReportNames.summary == "汇总数据统计"
    assert ReportNames.stats_occupied == "资金被占用情况统计"
    assert ReportNames.stats_occupying == "占用外单位资金情况统计"
    assert ReportNames.detail_occupied == "资金被占用情况明细"
    assert ReportNames.detail_occupying == "占用外单位资金明细"


def test_version_is_current():
    """版本号与 README 头部保持一致"""
    assert AppMetadata().version == "v2.0.7"
    assert AppMetadata().version_date == "2026-08-09"
