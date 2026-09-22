# fix/hithink-sector-closeout-0922

提交 `078f7eb41`（基座 `a2c8d1f90`）。隔离树，离线修复与验证：**未写生产库、未发布新池、
未合并、未部署、未取真实行情**。已 push，**PR #851 待复核**（合并须用户确认）。
背景/被否见 `../2026-09-22-hithink-sector-closeout.md`。

## 改了什么

- **D1 预览跨快照拼接**：`preview_sector_calculation` 原发 3～4 条独立 SELECT，DuckDB 自动提交下
  每条各取一次快照，写者中途提交即产出「旧名单+新价格」报告且**不报错**（实测 amount 600→1200）。
  新增 `db.read_snapshot()`（`BEGIN TRANSACTION READ ONLY`）收进同一快照。
- **D2 同日两版「正式名单」**：读者侧（`published_snapshot()`、`fact_sector_daily` 视图、
  `get_published_snapshot_id()`）按**日**强制唯一，写者 `publish_snapshot()` 却按 **(日, provider)**
  强制（三处 SQL）→ fupanhui 已发布的日子再发 hithink 会留两个 `published` 表头，视图无 LIMIT
  **同时暴露两池**。三处收回按日；换源须显式 `supersede_provider=<当前在位 provider>`，写错即拒。

## 已验证

- 新增 10 用例先红后绿；**删保护变异 3/3 见红**、还原全绿。变异2 只红「显式换源」**正向**用例：
  只写拒绝用例，把换源做死也能全绿。
- 干净树收据两份，均可采信、均**是目标收据不是全量**：`…112608Z-f900c1f3`（绑 `f900c1f31`，
  196 passed / 5 文件）；`…114039Z-078f7eb4`（绑 `078f7eb41`，143 passed / 3 文件）。其后仅文档。
- 全量：**12528 passed / 85 skipped / 2 xfailed**，跑于提交前脏树，**无收据**。
- `hithink_stock_preview._read_inputs` 单条 `con.execute`，天然单快照，**无同类缺陷**。

## 坑 / 未验证

- 全部离线合成数据；**未碰**生产库、真实行情、板块全目录、成员 generation。
- 全量跑里 1 failed = `test_rag_worker.py` 超时用例：与本改动**无 import 依赖**，单跑 3/3 绿，
  当时 **load average ≈50**（多棵工作树在跑）→ 负载假红，**非本次引入，别去「修」**；
  重跑全量前先看 `uptime`。
- **fail-closed 的拒绝不是无副作用的**：DuckDB 不暴露事务状态，只能试 BEGIN；失败会把调用方事务
  置 aborted、未提交改动丢失。已写进 docstring 与用例，别当「只是报个错」。
- 换源仍**绕过 95% 名称连续性闸门**（按 provider 比前一日）：跨源名称本就不同，无可辩护阈值，
  故只留痕不设闸——刻意的非目标。
- 无 schema 变更。

## 下一步

1. PR #851 复核 D2 口径（写者对齐读者）；**合并须用户确认**，不自行合。
2. 真实验算前先签：名称来源合同、换手率来源合同、停复牌分母政策；再验名单 generation。
3. 写库须另获授权并分阶段：隔离 staging → 逐表回读 → 日历最后写 → 全质量门 → 原子换库。
