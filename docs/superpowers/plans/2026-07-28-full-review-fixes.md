# 全面复核修复 Implementation Plan

> **For agentic workers:** Read `subagent-driven-development.md` when the user authorizes subagents; otherwise read `executing-plans.md` and implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 config.py 致命编码损坏，并修复复核发现的 4 处高/中风险问题，统一版本与 README。

**Architecture:** 全部为文件内局部修复，不改变 `preprocess_data → calculate_balances → build_bundle → save_results` 计算路径；新增透明度警告与防御性兜底。

**Tech Stack:** Python 3.14、pandas、openpyxl、pytest。

## Global Constraints

- 项目非 git 仓库，不执行任何 git 写操作；验证完成前保留 `config.py.bak`。
- `config.py` 必须重写为纯 UTF-8，8 个字符串恢复为：`往来占用统计分析系统`、`往来单位`、`往来单位每日余额`、`汇总数据统计`、`资金被占用情况统计`、`占用外单位资金情况统计`、`资金被占用情况明细`、`占用外单位资金明细`。
- 版本统一为 `v2.0.6`，日期 `2026-07-28`。
- 不改 `PrecisionEngine` 舍入语义，既有 15 个测试必须全部保持通过。
- 测试命令统一：`python -m pytest tests -q`（工作目录 `C:/Users/27651/Documents/Code/往来占用统计`）。

---

### Task 1: 重写 config.py 为合法 UTF-8 并恢复 8 个损坏字符串

**Files:**
- Modify: `config.py`（整体重写）
- Test: `tests/test_config.py`（新建）

**Interfaces:**
- Produces: `AppMetadata(name/version/version_date)`、`UiConfig`、`ColumnNames.unit = "往来单位"`、`ColumnNames.amount = "占用金额"`、`ReportNames.*`（7 个 sheet 名）、`EXCEL_MAX_ROWS = 1048575`、`ZERO_THRESHOLD = 1e-9`；`AppMetadata.version = "v2.0.6"`、`version_date = "2026-07-28"`。

- [ ] **Step 1: 备份并写失败测试**

```bash
cp config.py config.py.bak
```

```python
# tests/test_config.py
from 往来占用统计.config import AppMetadata, ColumnNames, ReportNames


def test_config_is_valid_utf8_and_importable():
    from pathlib import Path
    data = (Path(__file__).resolve().parents[1] / "config.py").read_bytes()
    data.decode("utf-8")  # 不抛异常即合法 UTF-8
    assert AppMetadata().name == "往来占用统计分析系统"
    assert ColumnNames.unit == "往来单位"
    assert ReportNames.balance == "往来单位每日余额"
    assert ReportNames.summary == "汇总数据统计"
    assert ReportNames.stats_occupied == "资金被占用情况统计"
    assert ReportNames.stats_occupying == "占用外单位资金情况统计"
    assert ReportNames.detail_occupied == "资金被占用情况明细"
    assert ReportNames.detail_occupying == "占用外单位资金明细"


def test_version_is_current():
    assert AppMetadata().version == "v2.0.6"
    assert AppMetadata().version_date == "2026-07-28"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_config.py -q`
Expected: collection 阶段 SyntaxError

- [ ] **Step 3: 重写 config.py**（内容与现状一致，仅修复字符串与版本号；用 Write 工具输出 UTF-8）

- [ ] **Step 4: 运行确认通过 + 全量回归**

Run: `python -m pytest tests -q`
Expected: 全部通过（既有 15 + 新增 2）

---

### Task 2: 早于期初日期的交易发出警告

**Files:**
- Modify: `pipeline.py` `calculate_balances`（pivot 之后、reindex 之前）
- Test: `tests/test_pipeline.py`（追加）

**Interfaces:**
- Consumes: 现有 `progress_callback(percent, message, phase)` 通道。
- Produces: 语义不变；有期初前交易时 callback 收到含"早于期初日期"的警告消息。

- [ ] **Step 1: 写失败测试**

```python
def test_transactions_before_initial_date_are_dropped_with_warning():
    """早于期初日期的交易被丢弃，但必须发出警告"""
    balance = pd.DataFrame({"日期": ["2025-01-10"], "单位A": [10000]})
    trans = pd.DataFrame({
        "单位名称": ["单位A", "单位A"],
        "借方金额": [500, 300],
        "贷方金额": [0, 0],
        "日期": ["2025-01-05", "2025-01-12"],  # 01-05 早于期初
    })
    messages = []
    pipeline = FinancePipeline()
    config = ProcessConfig("", "", "", "", "", "单位名称", "借方金额", "贷方金额", "日期")
    noop_config = config
    pb, pt = pipeline.preprocess_data(balance, trans, noop_config, lambda *a: None)
    result, _, _ = pipeline.calculate_balances(
        pb, pt, noop_config, lambda p, m, ph=None: messages.append(m)
    )
    # 期初前交易被丢弃：01-10 = 10000, 01-12 = 10300
    assert list(result["单位A"])[0] == 100000000
    assert list(result["单位A"])[-1] == 103000000
    assert any("早于期初日期" in m for m in messages)
```

注：测试需 `from 往来占用统计.models import ProcessConfig`。

- [ ] **Step 2: 运行确认失败**（无警告消息，最后断言失败）

- [ ] **Step 3: 实现** — 在 `calculate_balances` 的 `if not df_trans_filtered.empty:` 分支 pivot 生成后加入：

```python
early_mask = pivot.index < initial_date
if early_mask.any():
    early_count = int(
        df_trans_filtered[df_trans_filtered[config.col_date] < initial_date].shape[0]
    )
    progress_callback(
        28,
        f"警告：{early_count} 条交易早于期初日期 {initial_date:%Y-%m-%d}，未纳入余额计算",
        "核心计算阶段",
    )
```

- [ ] **Step 4: 运行 `python -m pytest tests -q` 全部通过**

---

### Task 3: .xls 明确拒绝 + GUI 文件选择器收窄

**Files:**
- Modify: `excel_io.py` `read_dataframes`（开头检查后缀）
- Modify: `gui.py` `browse_file` filetypes
- Test: `tests/test_excel_io.py`（新建）

**Interfaces:**
- Produces: `ExcelRepository.read_dataframes` 对非 `.xlsx/.xlsm` 抛 `ValueError("不支持的文件格式: .xls，请另存为 .xlsx 后重试")`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_excel_io.py
import pytest
from 往来占用统计.excel_io import ExcelRepository
from 往来占用统计.models import ProcessConfig


def test_read_dataframes_rejects_xls():
    config = ProcessConfig("a.xls", "S", "b.xls", "S", "", "n", "d", "c", "dt")
    with pytest.raises(ValueError, match="不支持的文件格式"):
        ExcelRepository().read_dataframes(config)
```

- [ ] **Step 2: 运行确认失败**（当前不抛 ValueError，走到 read_excel 报 FileNotFoundError）

- [ ] **Step 3: 实现** — `read_dataframes` 开头：

```python
for path in (config.balance_file, config.trans_file):
    suffix = Path(path).suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise ValueError(f"不支持的文件格式: {suffix or path}，请另存为 .xlsx 后重试")
```

`gui.py` `browse_file` 中 `filetypes=[("Excel files", "*.xlsx *.xlsm")]`。

- [ ] **Step 4: 运行全量测试通过**

---

### Task 4: make_excel 全空 sheet 不再崩溃

**Files:**
- Modify: `make_excel.py` `make_excel`（保存前检查）
- Test: `tests/test_make_excel.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_make_excel.py
import pandas as pd
from openpyxl import load_workbook

from make_excel import make_excel


def test_make_excel_all_empty_sheets_still_saves(tmp_path):
    out = tmp_path / "empty.xlsx"
    make_excel([("空表", pd.DataFrame())], str(out))
    wb = load_workbook(out)
    assert len(wb.sheetnames) >= 1
```

注：`make_excel.py` 在项目根目录，测试通过 conftest 已有的 `sys.path`（项目根的父目录）不够，需在测试内 `sys.path.insert(0, 项目根)`；更稳妥：在 `tests/conftest.py` 追加项目根本身进 `sys.path`。

- [ ] **Step 2: 运行确认失败**（`IndexError: At least one sheet must be visible`）

- [ ] **Step 3: 实现** — `make_excel` 在 `wb.save` 前：

```python
if not wb.sheetnames:
    wb.create_sheet(title="空表")
```

- [ ] **Step 4: 运行全量测试通过**

---

### Task 5: README 更新（启动方式、v2.0.6 更新日志、版本头）

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** 版本头改为 `v2.0.6 / 2026-07-28`；「三步上手」启动方式改为 `python main.py` 或 `python -m 往来占用统计.main`，删除"双击 往来占用统计.py"及"外层启动文件保留"的过时描述；「给维护人员看的补充说明」同步修正结构描述。
- [ ] **Step 2:** 更新日志顶部新增 v2.0.6 条目，记录本次 5 项修复。
- [ ] **Step 3:** 运行 `python -m pytest tests -q` 最终全量验证；版本一致性由 `test_version_is_current` + 人工比对 README 头确认。

---

## Self-Review

- 需求 5 条 → Task 1/2/3/4/5 全覆盖，无缺口。
- 无占位符；测试代码完整可复制。
- 类型一致性：ProcessConfig 位置参数顺序与 models.py 定义一致；`make_excel` 签名 `(data, output_path, sheet_name, theme)` 与测试调用一致。
- git 提交步骤全部移除（非 git 仓库）。
