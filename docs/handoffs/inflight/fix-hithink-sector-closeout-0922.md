# fix/hithink-sector-closeout-0922

基座 `a2c8d1f90`。隔离树，只做离线修复与验证：**未写生产库、未发布新池、未合并、未部署、
未取真实行情、未 push**。背景 / 被否方案 / 理由见 `docs/handoffs/2026-09-22-hithink-sector-closeout.md`。

## 改了什么（未提交 → 见下方提交）

- **D1 预览跨快照拼接**：`preview_sector_calculation` 原发 3～4 条独立 SELECT，DuckDB 自动提交下
  每条各取一次快照，写者中途提交即产出「旧名单+新价格」报告且**不报错**（实测 amount 600→1200）。
  新增 `db.read_snapshot()`（`BEGIN TRANSACTION READ ONLY`）收进同一快照。
- **D2 同日两版「正式名单」**：读者侧（`published_snapshot()`、`fact_sector_daily` 视图、
  `get_published_snapshot_id()`）按**日**强制唯一，写者 `publish_snapshot()` 却按 **(日, provider)**
  强制（三处 SQL）。fupanhui 已发布的日子再发 hithink → 两个 `published` 表头 → 视图无 LIMIT
  **同时暴露两池**。三处收回按日；换源须显式 `supersede_provider=<当前在位 provider>`，写错即拒；
  旧 provider 的 `dim_sector` 身份同步退役。

## 已验证

- 新增 10 用例先红后绿；**删保护变异 3/3 见红**、还原全绿。变异2 只红「显式换源」正向用例——
  只写拒绝用例，把换源做死也能全绿。
- 全量 `pytest -q -p no:randomly`：**12528 passed / 85 skipped / 2 xfailed**。
- `hithink_stock_preview._read_inputs` 单条 `con.execute`，天然单快照，**无同类缺陷**（已核）。

## 未验证 / 会咬人的坑

- 全部离线合成数据；**未碰**生产库、真实行情、板块全目录、成员 generation。
- 全量跑里 1 failed = `test_rag_worker.py::test_warm_worker_survives_first_timeout_...`，
  与本改动**无 import 依赖**，单跑 3/3 绿 → 全量负载下偶发超时，**非本次引入，别去"修"它**。
- **fail-closed 的拒绝不是无副作用的**：DuckDB Python API 不暴露事务状态，只能试 BEGIN；
  失败会把调用方事务置 aborted、未提交改动丢失。已写进 docstring 与用例，别当成「只是报个错」。
- 换源仍**绕过 95% 名称连续性闸门**（`_adjacent_name_continuity` 按 provider 比前一日）。跨源名称
  本就不同，无可辩护阈值，故只留痕不设闸——刻意的非目标。
- 无 schema 变更；换源留痕靠旧表头转 `superseded`。

## 下一步

1. 请人复核 D2 口径（写者对齐读者），再决定 push / 开 PR。
2. 真实验算前先签：名称来源合同、换手率来源合同、停复牌分母政策；再验名单 generation。
3. 写库须另获授权并分阶段：隔离 staging → 逐表回读 → 日历最后写 → 全质量门 → 原子换库。
