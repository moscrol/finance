# 2026-09-22 未绑快照读取 A 类 7 处 修复占位工单（#78）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#74（#857 合入）。本单只处理 `docs/verification/2026-09-22-unsnapshotted-reads-triage.md` 裁成 **A** 的 7 行；B / C 不碰。
**编号 #78 基于 2026-09-22 23:5x 对全部本地 / gitea 分支 INDEX 的扫描（最大号 77，在 PR #858 分支上）；接手先重扫，撞号按 INDEX 规则改号留记录。**

## 背景与动机

- #851 / #857 把「多条 SELECT 各取一次快照、拼出从未同时成立的报告」修在了换池预览、`query.health`、`collect_daily_review` 三处，修法是 `db.read_snapshot()`。
- #74 把审计器列出的其余 54 个候选逐条裁定，7 处能编出**静默**错误结论且是对外产物或写进库的值（裁定表第 1–7 行）。按 #857 的形态决策它们不在同一 PR 里修，登记到本单。
- **实测边界**（`tests/test_report_reads_cross_process_boundary.py`）：DuckDB 拒绝跨进程并发打开同一文件；生产写者走 staging + `os.replace`。所以这 7 处在生产上的真实暴露面是「同进程多线程写者」（目前 grep 未发现）与「一次调用多次 connect 跨越换库」（第 4 行 `strong_subtheme_trace` 命中）。优先级因此 ≤ P2。

## 目标（7 条，一条一行，与裁定表 A 类一一对应）

| 条 | 函数 | 修法方向 | 优先级 |
|---|---|---|---|
| 1 | `query.stock_highs` | 三条读包进 `with read_snapshot(con)`；连接由函数自持（`connect(read_only=True)`），无外层事务风险 | P2 |
| 2 | `query.sw_l1_signal_peaks` | 同上；`_table_window_dates` 两次调用在同一快照内 | P2 |
| 3 | `query._interval_stock_rank` | 同上；`rng → metadata_date → 主查询` 三步同快照 | P2 |
| 4 | `query.strong_subtheme_trace` | **不能只包自身三读**：要把连接 / 快照穿透进 `sw_l1_signal_peaks`（加 `con=` 参数或拆出 `_sw_l1_signal_peaks_on(con, …)`），逐日 60 次 connect 收成 1 条连接 1 个快照。这是唯一跨进程也会混的形态 | **P2（首做）** |
| 5 | `query.limit_heat` | 两条读包进 `read_snapshot` | P2 |
| 6 | `models.market_stage.build_feature_frame` | 三条读包进 `read_snapshot`；调用方 `predict_stage` 的 UPDATE 在快照 ROLLBACK 之后发出，先确认 `train` 路径调用点也不在事务内 | P3 |
| 7 | `compute_local_stats.core_leader_candidates` | `_limit_flags` / `gain5` / `highs` 同快照；调用方 `compute_core_leader_local` 与 `scripts/eval_core_leader_authenticity.py` 两个入口都要看是否持事务 | P3 |

每条都要有 #857 同款用例：真第二连接在指定读取之后提交，`during == before` 且 `after != before`；再加一条「调用方已持事务 → `SnapshotUnavailableError`」。

## 非目标（写死认领）

- ❌ 不碰 B 类 12 行与 C 类 35 行（裁定表已给理由；要翻案先改裁定表）。
- ❌ 不把审计器做成门禁；不给它加白名单。
- ❌ 不删 `_start_day_confirmation`。
- ❌ 不改 `completion_audit`。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `docs/verification/2026-09-22-unsnapshotted-reads-triage.md` | 7 行 A 的判据要点与 B / C 的排除理由 |
| `tests/test_report_reads_single_snapshot.py` | 用例形状（`Passthrough` / `ConcurrentCommit`）直接复用 |
| `tests/test_report_reads_cross_process_boundary.py` | 为什么第 4 条是首做：多次 connect 跨换库会混 |
| `market_feature_store/db.py::read_snapshot` | fail-closed 副作用（调用方事务被置 aborted） |
| `scripts/audit_unsnapshotted_reads.py` | 修完复跑，7 行应从候选列表消失 |

## 步骤

1. 开工三连；从最新 `gitea/main` 开 `fix/unsnapshotted-reads-a7`；确认 #857 已在 main（`git merge-base --is-ancestor`）。
2. 第 4 条先做（穿透连接），其余 6 条逐条：先红后绿 + 拆门变异见红（`PYTHONDONTWRITEBYTECODE=1`，实现先提交再拆）。
3. 复跑审计器，贴前后候选数。
4. 低负载四叶；收据 revision == head；开 PR；#75 独立 QC。
5. INDEX #78 行；inflight ≤3K。

## 验收

- [ ] 7 条各有先红后绿用例，且拆掉各自绑定后对应用例红、还原后指纹一致。
- [ ] 审计器未绑候选数从 54 降到 47（`_start_day_confirmation` 与 `completion_audit` 仍在列表里，这是对的）。
- [ ] `strong_subtheme_trace` 一次调用只 connect 一次（用 monkeypatch 计数断言）。
- [ ] 四叶收据 revision == head。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- 不写生产库；用例用临时 DuckDB 文件。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 不写明文密钥。
