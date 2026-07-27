import pytest

from 往来占用统计.excel_io import ExcelRepository
from 往来占用统计.models import ProcessConfig


def test_read_dataframes_rejects_xls():
    """openpyxl 不支持旧版 .xls，应给出明确中文错误而非晦涩底层报错"""
    config = ProcessConfig("a.xls", "S", "b.xlsx", "S", "", "n", "d", "c", "dt")
    with pytest.raises(ValueError, match="不支持的文件格式"):
        ExcelRepository().read_dataframes(config)
