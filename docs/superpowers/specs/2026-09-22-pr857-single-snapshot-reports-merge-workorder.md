# 2026-09-22 #857 体检与当日复盘绑定单快照 合入准备工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#59（main 顶端干净收据）。姊妹：#75（独立 QC）。本单小，半天。

## 背景与动机

- #851 修的是「换池预览跨快照拼接」：DuckDB 自动提交下每条 SELECT 各取一次快照，夜跑写者在两条语句之间提交，一次调用返回「旧名单 + 新价格」且不报错。#851 用 `db.read_snapshot()`（`BEGIN TRANSACTION READ ONLY`）把全部读取绑到同一快照，已合 main（`53bd332c1`）。
- PR **#857**（`fix/report-reads-single-snapshot` @ `086d99962`，base main，代码提交 `e78c9eb5b`，已推）把它当成**一类**扫：`scripts/audit_unsnapshotted_reads.py` AST 列出候选；只修**演示得出错误结论**的两处——`query.health`（体检单称有成分股的板块比维表里存在的还多：`assert 3 <= 2`）与 `collect_daily_review`（日报拼了旧市场 + 新板块：`during != before`）。`completion_audit` 不改（首条读出 `snapshot_id`、其后按它过滤，内部不会打架）。审计器退出码恒 0 是辅助不是门禁（判该不该绑快照要语义，AST 做成闸必然误报或靠白名单）。死代码 `_start_day_confirmation` 全仓零引用只记录不删。
- 读数：5 条新用例先红后绿；保护性变异 3/3 见红（拆 health 红 3、拆日报红 2、两处都拆红 5），还原逐字节相同；干净树收据 `20260922T135535Z-e78c9eb5.json` 54P（`--expect-revision` 可采信）；回归 `-k "review or query or health or generation or report"` 473P/9S。**未跑全仓**；剩余 52 个候选未逐一裁定；审计器看不出助手已被上层快照覆盖（`_sw_l1_double_red_matrix` 仍被列出，实际在 `collect_daily_review` 快照内）；只证同进程第二连接提交，未测多进程 / 夜跑真实并发。
- 开 PR 时 API 超时但 PR 已建成，作者回读确认未重试（POST 非幂等），22:20 核对 Gitea 无重复单。
- **已定的形态决策**：只修能演示错误结论的点，不把 54 个无保护函数全包；审计器不做闸；死代码不在本 PR 删。

## 目标

1. 前向到最新 main（`merge-tree`）；低负载四叶；收据 revision == head。
2. 52 个未裁定候选出一张表（函数、读了几条 SELECT、能否编出错误结论、结论：修 / 不修 / 上层已覆盖），落 `docs/verification/<日期>-unsnapshotted-reads-triage.md`；能编出错误结论的**不在本 PR 修**，登记占位单。
3. 一条多进程阳性对照：用第二个进程（`subprocess` 起 `duckdb` 写者）在两条读取之间提交，未修版本必须复现 `during != before`，修后一致。
4. #75 独立 QC（可与 #851 补验合审）；用户确认后 `merge --record`；合入后 main tip python 叶复跑。

## 非目标（写死认领）

- ❌ 不删 `_start_day_confirmation`（删代码是另一个决定）。
- ❌ 不把审计器做成 pre-commit 闸。
- ❌ 不给 `completion_audit` 加快照。
- ❌ 不修 52 个候选里任何一个（登记占位）。

## 证据路径

| 文件 | 看什么 |
|---|---|
| gitea `fix/report-reads-single-snapshot:docs/handoffs/inflight/fix-report-reads-single-snapshot.md` | 决策、读数、边界 |
| `scripts/audit_unsnapshotted_reads.py`、`tests/test_report_reads_single_snapshot.py` | 审计器与 5 条用例 |
| `market_feature_store/db.py::read_snapshot`（main） | 只读事务与 fail-closed 副作用说明（调用方未提交事务会被置 aborted） |
| `~/.finance-runtime/test-receipts/20260922T135535Z-e78c9eb5.json` | 干净目标收据 |
| `gitea/main:docs/handoffs/2026-09-22-hithink-sector-closeout.md` | #851 的 D1 机制与被否方案 |

## 步骤

1. 开工三连；`gitea_pr.py show 857`；确认无重复 PR。
2. `merge-tree` 探冲突；前向；低负载四叶。
3. 52 候选表；多进程阳性对照落 `docs/verification/…`。
4. 交 #75；确认后合入；main tip python 叶。
5. INDEX #74 行；inflight ≤3K。

## 验收

- [ ] 四叶收据 revision == head。
- [ ] 阳性对照：拆掉 `collect_daily_review` 的快照绑定，多进程用例红；还原绿；指纹一致。
- [ ] 52 候选表每行有结论；能编出错误结论的行数与占位单数一致。
- [ ] 合并记录含授权原话与出处。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- 不写生产库；对照用临时 DuckDB 文件。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 不写明文密钥。
