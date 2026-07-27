from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

import pandas as pd


class PrecisionEngine:
    # SCALE=10000 表示"厘"级精度（1元 = 10000厘），不是"分"(cents)
    SCALE = 10000
    DECIMAL_QUANTIZER = Decimal("0.01")
    MAX_DECIMAL_VAL = Decimal("99999999999999.9999")

    @staticmethod
    def bankers_round(val: Any) -> Decimal:
        if val is None:
            return Decimal("0.00")
        try:
            if pd.isna(val):
                return Decimal("0.00")
        except Exception:
            pass
        if isinstance(val, str) and val.strip() == "":
            return Decimal("0.00")
        return Decimal(str(val)).quantize(PrecisionEngine.DECIMAL_QUANTIZER, rounding=ROUND_HALF_EVEN)

    @staticmethod
    def to_integer_cents(series: pd.Series) -> pd.Series:
        from decimal import Decimal, ROUND_HALF_EVEN
        # 使用 Decimal 精确舍入到分，避免浮点数 banker's rounding 陷阱
        # （如 0.015 在浮点表示中为 0.014999...，round(2) 会错误地舍入为 0.01）
        numeric = pd.to_numeric(series, errors="coerce").fillna(0)
        rounded = numeric.apply(
            lambda v: int(
                Decimal(str(v)).quantize(
                    PrecisionEngine.DECIMAL_QUANTIZER, rounding=ROUND_HALF_EVEN
                )
                * PrecisionEngine.SCALE
            )
        )
        return rounded.astype("int64")

    @staticmethod
    def from_integer_cents(series: pd.Series) -> pd.Series:
        return (pd.to_numeric(series, errors="coerce").fillna(0) / PrecisionEngine.SCALE).round(2)

    @staticmethod
    def to_integer_li(value: Any) -> int:
        if value is None:
            return 0
        decimal_value = Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
        return int(decimal_value * PrecisionEngine.SCALE)

    @staticmethod
    def amounts_match(amount1: Any, amount2: Any, tolerance_li: int = 100) -> bool:
        return abs(PrecisionEngine.to_integer_li(amount1) - PrecisionEngine.to_integer_li(amount2)) <= tolerance_li

    @staticmethod
    def compare_amounts(amount1: Any, amount2: Any) -> int:
        left = PrecisionEngine.to_integer_li(amount1)
        right = PrecisionEngine.to_integer_li(amount2)
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
