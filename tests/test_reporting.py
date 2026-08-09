import pandas as pd

from 往来占用统计.reporting import ReportBuilder


def test_duplicate_date_and_unit_name_is_handled():
    df = pd.DataFrame({"往来单位": pd.to_datetime(["2025-01-01"]), "单位A": [100000000]})
    report = ReportBuilder().build_bundle(df, ["单位A"], [], lambda *_args: None)
    assert not report.summary.empty


def test_new_supplier_note_is_present():
    detail = pd.DataFrame({"往来单位": ["新增单位"], "占用金额": [100.0]})
    stats = ReportBuilder().calculate_statistics(detail, new_suppliers=["新增单位"])
    assert stats.loc[0, "备注"] == "该单位仅存在于序时账"
