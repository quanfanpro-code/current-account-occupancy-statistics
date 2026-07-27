import pandas as pd
import pytest

from 往来占用统计.pipeline import FinancePipeline


def test_single_initial_row_still_expands_all_dates():
    balance = pd.DataFrame({"日期": ["2025-01-01"], "单位A": [10000]})
    trans = pd.DataFrame(
        {
            "单位名称": ["单位A", "单位A"],
            "借方金额": [500, 300],
            "贷方金额": [0, 0],
            "日期": ["2025-01-02", "2025-01-03"],
        }
    )

    result = FinancePipeline().calculate_balances_from_frames(
        balance, trans, "单位名称", "借方金额", "贷方金额", "日期"
    )

    assert len(result) == 3
    assert list(result["单位A"]) == [100000000, 105000000, 108000000]


def test_transaction_on_initial_date_is_not_lost():
    """验证与期初余额同日期的交易不会被静默丢弃"""
    balance = pd.DataFrame({"日期": ["2025-01-01"], "单位A": [10000]})
    trans = pd.DataFrame(
        {
            "单位名称": ["单位A"],
            "借方金额": [200],
            "贷方金额": [0],
            "日期": ["2025-01-01"],
        }
    )

    result = FinancePipeline().calculate_balances_from_frames(
        balance, trans, "单位名称", "借方金额", "贷方金额", "日期"
    )

    assert len(result) == 1
    # 10000元(期初) + 200元(首日交易) = 10200元 → 10200 * 10000 = 102000000
    assert list(result["单位A"]) == [102000000]


def test_no_transactions_returns_initial_balance():
    """无交易时仅返回期初余额"""
    balance = pd.DataFrame({"日期": ["2025-01-01"], "单位A": [5000]})
    trans = pd.DataFrame(
        {"单位名称": [], "借方金额": [], "贷方金额": [], "日期": []}
    )

    result = FinancePipeline().calculate_balances_from_frames(
        balance, trans, "单位名称", "借方金额", "贷方金额", "日期"
    )

    assert len(result) == 1
    assert list(result["单位A"]) == [50000000]


def test_new_supplier_in_trans_creates_column():
    """序时账中的新单位应自动创建对应列"""
    balance = pd.DataFrame({"日期": ["2025-01-01"], "单位A": [10000]})
    trans = pd.DataFrame(
        {
            "单位名称": ["新单位B"],
            "借方金额": [300],
            "贷方金额": [0],
            "日期": ["2025-01-02"],
        }
    )

    result = FinancePipeline().calculate_balances_from_frames(
        balance, trans, "单位名称", "借方金额", "贷方金额", "日期"
    )

    assert "新单位B" in result.columns
    assert len(result) == 2


def test_multi_row_balance_uses_first_row_and_expands():
    """多行余额表：取第一行作为期初余额，展开到最后一行日期"""
    balance = pd.DataFrame({
        "日期": ["2025-01-01", "2025-01-02", "2025-01-03"],
        "单位A": [10000, 12000, 15000],
    })
    trans = pd.DataFrame(
        {"单位名称": [], "借方金额": [], "贷方金额": [], "日期": []}
    )

    result = FinancePipeline().calculate_balances_from_frames(
        balance, trans, "单位名称", "借方金额", "贷方金额", "日期"
    )

    # 展开到余额表最后一行日期（3天），期初余额取第一行 10000
    assert len(result) == 3
    # 无交易，每天余额都是期初余额 10000 * 10000 = 100000000
    assert list(result["单位A"]) == [100000000, 100000000, 100000000]


def test_transactions_before_initial_date_are_dropped_with_warning():
    """早于期初日期的交易被丢弃，但必须发出警告提示"""
    from 往来占用统计.models import ProcessConfig

    balance = pd.DataFrame({"日期": ["2025-01-10"], "单位A": [10000]})
    trans = pd.DataFrame(
        {
            "单位名称": ["单位A", "单位A"],
            "借方金额": [500, 300],
            "贷方金额": [0, 0],
            "日期": ["2025-01-05", "2025-01-12"],  # 01-05 早于期初日期
        }
    )
    messages = []
    pipeline = FinancePipeline()
    config = ProcessConfig("", "", "", "", "", "单位名称", "借方金额", "贷方金额", "日期")
    pb, pt = pipeline.preprocess_data(balance, trans, config, lambda *a: None)
    result, _, _ = pipeline.calculate_balances(
        pb, pt, config, lambda p, m, ph=None: messages.append(m)
    )
    # 期初前交易 500 被丢弃：01-10 余额 = 10000，01-12 余额 = 10300
    assert list(result["单位A"])[0] == 100000000
    assert list(result["单位A"])[-1] == 103000000
    assert any("早于期初日期" in m for m in messages)
