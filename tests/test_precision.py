from decimal import Decimal

import pandas as pd

from 往来占用统计.precision import PrecisionEngine


def test_bankers_round_keeps_finance_rounding():
    assert PrecisionEngine.bankers_round("2.345") == Decimal("2.34")


def test_integer_li_roundtrip():
    value = PrecisionEngine.to_integer_li("123.4567")
    assert value == 1234567


def test_to_integer_cents_handles_boundary_values():
    """验证边界浮点数（如 0.015）不会被错误舍入"""
    series = pd.Series([0.015, 0.025, 0.035, 123.45])
    result = PrecisionEngine.to_integer_cents(series)
    # 0.015 → 0.02元 → 200; 0.025 → 0.02元(银行家舍入) → 200; 0.035 → 0.04元 → 400; 123.45 → 1234500
    assert list(result) == [200, 200, 400, 1234500]


def test_to_from_integer_cents_roundtrip():
    """验证往返精度无损失"""
    original = pd.Series([123.45, -99.99, 0.01, 0.00])
    result = PrecisionEngine.from_integer_cents(
        PrecisionEngine.to_integer_cents(original)
    )
    assert list(result) == [123.45, -99.99, 0.01, 0.0]
