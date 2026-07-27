# 全面复核 — 验收审查报告

> 日期：2026-07-28
> 范围：往来占用统计 全项目（13 个源文件 + 5 个既有测试文件）
> 说明：本报告最初在 `C:\Users\27651\Documents\Code\往来占用统计` 完成；同日确认 `D:\BaiduSyncdisk\Code\往来占用统计` 为同一版本（仅 make_excel.py 为 7月20日 增强版：主题校验、fmt_override、A 列格式化、关键词扩充），已将相同修复同步应用到该副本，增强版 make_excel.py 完整保留并仅追加空 sheet 兜底。

## 审查范围与方法

逐文件阅读全部源码与测试；`pytest` 实测复现故障；每个修复点按 RED→GREEN 循环取得失败/通过证据；修复后重新全量验证。

## 发现与修复

| # | 严重度 | 问题 | 修复 | 验证证据 |
|---|--------|------|------|----------|
| 1 | 🔴 致命 | `config.py` 8 个字符串末尾 UTF-8 字节损坏为 `0x3F`，import 即 SyntaxError，程序与全部测试无法加载 | 按原语义整体重写为纯 UTF-8 | RED：collection SyntaxError；GREEN：`tests/test_config.py` 2 项通过，字节级 `decode('utf-8')` 通过，9 个模块 import 冒烟通过 |
| 2 | 🟡 高 | 早于期初日期的交易被 `reindex` 静默丢弃，余额错误无提示 | 语义不变，新增日志警告（含笔数与期初日期） | RED：警告断言失败；GREEN：`test_transactions_before_initial_date_are_dropped_with_warning` 通过，丢弃语义断言同步锁定 |
| 3 | 🟡 中 | GUI 允许选 `.xls` 但 openpyxl 读不了，报错晦涩 | 选择器收窄 `.xlsx/.xlsm`，读取层抛明确中文 `ValueError` | RED：FileNotFoundError；GREEN：`test_read_dataframes_rejects_xls` 通过 |
| 4 | 🟡 中 | 全空结果导出时 `make_excel` 无可见 sheet，`wb.save` 抛 IndexError | 保存前兜底创建空 sheet | RED：IndexError；GREEN：`test_make_excel_all_empty_sheets_still_saves` 通过 |
| 5 | 🟢 低 | README 启动方式与版本号与实际不符 | 启动方式改 `python main.py`，版本统一 v2.0.6，补更新日志 | `test_version_is_current` + grep 全库版本引用一致性检查 |

## 测试质量检查（mutation check）

- 篡改 config 任一常量或写入坏字节 → `test_config.py` 失败 ✓
- 删除警告代码 → 期初前交易测试最后断言失败；改变丢弃语义 → 余额断言失败 ✓
- 删除 `.xls` 校验 → xls 测试失败（错误类型不符） ✓
- 删除空 sheet 兜底 → make_excel 测试失败 ✓
- 无 mock 断言、无 source-grep 式测试；期望值均为手工推导字面量。

## 过度工程检查（ponytail）

本次 diff 全部为最小修复：无新依赖、无新抽象、无投机配置。净增约 30 行生产代码 + 4 个测试文件，每行可追溯至需求条目。Lean already. Ship.

## 已知残余风险（不修，记录）

1. 取消请求仅在进度回调时机生效，大文件读取阶段无法即时取消（既有设计限制）。
2. `save_results` 的写入进度为估算进度，非真实字节进度（显示层面，不影响结果）。
3. 输出文件已存在时直接覆盖，无二次确认（既有行为）。

## 最终验证（本消息内新鲜执行）

- `python -m pytest tests -q` → **19 passed**（14 既有 + 5 新增）
- 9 个模块 import 冒烟 → 全部 OK
- `config.py` 字节级 UTF-8 校验 → 通过
- 版本引用 grep 全库一致 → v2.0.6
- `config.py.bak` 验证完成后已删除
