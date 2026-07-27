import pytest

from 往来占用统计.gui import ProgressAdapter
from 往来占用统计.models import ProcessConfig


class FakeProgressbar:
    def __init__(self):
        self.value = None
        self.calls = []

    def set(self, value):
        self.calls.append(("set", value))
        self.value = value

    def __setitem__(self, key, value):
        self.calls.append((key, value))
        if key == "value":
            self.value = value


class FakeLabel:
    def __init__(self):
        self.kwargs = {}

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)


def test_progress_adapter_works_for_ttk_widgets():
    progress = FakeProgressbar()
    label = FakeLabel()
    adapter = ProgressAdapter(progress, label, use_customtkinter=False)

    adapter.set_value(35, "处理中")
    adapter.set_success("完成")

    assert progress.value == 100
    assert label.kwargs["text"] == "完成"


def test_process_config_rejects_duplicate_column_mapping():
    """列映射重复（如借方和贷方都映射到同一列）应抛出错误"""
    config = ProcessConfig(
        trans_file="/tmp/a.xlsx",
        trans_sheet="Sheet1",
        balance_file="/tmp/b.xlsx",
        balance_sheet="Sheet1",
        output_dir="/tmp",
        col_name="单位",
        col_debit="金额",
        col_credit="金额",  # 与借方相同
        col_date="日期",
    )
    with pytest.raises(ValueError, match="列映射冲突"):
        config.validate()


def test_process_config_valid_passes():
    """合法配置应通过校验"""
    config = ProcessConfig(
        trans_file="/tmp/a.xlsx",
        trans_sheet="Sheet1",
        balance_file="/tmp/b.xlsx",
        balance_sheet="Sheet1",
        output_dir="/tmp",
        col_name="单位",
        col_debit="借方",
        col_credit="贷方",
        col_date="日期",
    )
    config.validate()  # 不应抛出异常
