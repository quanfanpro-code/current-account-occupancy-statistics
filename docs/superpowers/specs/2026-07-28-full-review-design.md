# 往来占用统计 — 全面复核修复设计

> 日期：2026-07-28
> 对应需求：docs/requirements/2026-07-28-full-review-requirement.md

## 方案比较

### 问题 1（P0）：config.py 编码损坏

- **方案 A（推荐）：按原语义整体重写 config.py 为纯 UTF-8。** 文件仅 8 个损坏字符串，语义明确（README 与 sheet 名可互证），重写最简单彻底，杜绝残留坏字节。
- 方案 B：逐字节修补 8 处坏字节。等价但易漏，且保留历史混合编码风险。
- 结论：选 A，写完后字节级 `decode('utf-8')` 校验 + import 校验。

### 问题 2（高风险）：早于期初日期的交易被静默丢弃

- **方案 A（推荐）：保留丢弃语义，在 `calculate_balances` 中统计被丢弃笔数，经 `progress_callback` 发出明确警告。** 期初余额本身就是期初日起点，早于该日的交易本就不应叠加，语义不变，只补透明度。
- 方案 B：直接报错拒绝。对真实账套（常含期初前凭证）过于严苛。
- 方案 C：自动把起始日期提前。改变余额语义，风险大。
- 结论：选 A。

### 问题 3（中风险）：.xls 可选但读不了

- **方案 A（推荐）：GUI 文件选择器 `filetypes` 收窄为 `*.xlsx *.xlsm`，读取层 catch 后缀不支持的异常时给出明确中文提示。** 零新依赖。
- 方案 B：引入 xlrd 支持 .xls。新增依赖，收益小（旧格式罕见且用户可另存）。
- 结论：选 A。

### 问题 4（中风险）：全空结果导出必崩

- **方案 A（推荐）：`make_excel.make_excel` 末尾保存前检查，若没有任何 sheet 则创建一个空 sheet 再保存。** 修复点在崩溃发生的模块内，一劳永逸。
- 方案 B：`excel_io.save_results` 兜底改非空 DataFrame。只修一个调用方，其他调用方仍会踩。
- 结论：选 A。

### 问题 5（文档）：启动方式与版本号

- **方案 A（推荐）：README 改为当前真实启动方式（`python main.py` 或 `python -m 往来占用统计.main`），版本统一升 v2.0.6 并补更新日志。** 不重建外层启动文件（其消失已久且非本次缺陷）。
- 方案 B：在父目录重建 `往来占用统计.py` 双击启动器。需写项目目录外文件，超出本次范围。
- 结论：选 A。

## 数据流与错误处理

- 修复不改变任何计算路径：`preprocess_data → calculate_balances → build_bundle → save_results` 保持不变。
- 新增警告路径：`calculate_balances` 在 reindex 前统计 `pivot.index < initial_date` 的行对应交易笔数，经 callback(percent, 警告消息, phase) 透传到 GUI 日志区，不中断流程。
- 读取错误路径：`read_dataframes` 捕获 openpyxl 不支持格式异常，重抛带文件后缀提示的 `ValueError`，由 controller 现有 error 通道展示。

## 测试策略（TDD）

1. `test_config_is_valid_utf8_and_importable`：字节级 UTF-8 校验 + 8 个常量值断言。
2. `test_early_transactions_warn_but_keep_semantics`：期初前交易被丢弃且 callback 收到警告。
3. `test_version_consistency`：`AppMetadata.version` 与 README 头部版本一致。
4. `test_make_excel_all_empty_sheets_still_saves`：全空 DataFrame 列表也能保存出合法 xlsx。
5. 既有 15 个测试全部保持通过，语义不回退。

## 迁移与回滚

- 全部为文件内局部修改，无数据迁移；git 未初始化（项目非 git 仓库），回滚方式为保留修改前副本（仅对 config.py 保留 `.bak` 至验证完成后删除）。
