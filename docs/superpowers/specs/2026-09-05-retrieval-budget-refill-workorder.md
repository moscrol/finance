# 2026-09-05 检索预算闸回填工单（#26）

> 可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
> 来源：工单 #22（`2026-09-04-rag-worker-resident-memory-workorder.md`）**步骤 5** 的兑现单。
> #22 的非目标里写死「不抬 30s 帽、不跑 T120/R20，去处是本单」——本单是那个去处。
> 前置（内存层）已完成，见下；本单**不依赖** #22 继续开工，但**依赖一次用户裁决**（见「阻塞前置」）。

## 背景与动机

`min_window_seconds`（`intelligence/services/research_tool_registry.py:1254`：kb_search 20.0 /
evidence_search 30.0）与 `intelligence/services/episode_tools.py:910` 的 `timeout=min(timeout, 30.0)`
是 2026-08 在**冷 worker**条件下钉的：那时生产 kb_search 66% 以 `tool_timeout` 收场，单次换入要付 20–60s。
这两个数字现在同时决定两件事——工具**可见性**（`intelligence/runtime/episode_tool_batch.py:300-320`：
`floor > would_grant` 就把工具从菜单里摘掉，模型根本点不到）与**超时**——所以钉高了会静默减少检索机会，
钉低了会把窗口烧在必超时的调用上。

阻塞它们的内存层已经治完（工单 #22 步骤 2/3/4，PR #577 + 瘦身三刀 KB #141/#142/#143 + 金融 #587）。
2026-09-05 生产实测（8792 重启后，快照 `f4c03b9a`，交接 `docs/handoffs/inflight/perf-rag-worker-slimming.md`）：

| 条件 | kb_search 端到端 | 出处 |
|---|---|---|
| 热态（N=8） | p50 838 ms / p95 1140 ms / 0 超时 | `~/.finance-runtime/rag-mem-probe-20260905/kb-cases/q1–q7.json` |
| 空闲 35 分钟后首查 | 5,341.6 ms | 同上 `q7.json` |
| 空闲 7.2 小时后首查 | 8,128.1 ms（未超时） | 同上 `q8.json`（09-05 09:46） |
| 空闲 4 小时曲线 | 足迹恒 2.5 GB、RSS 11–13 MB、0 abandoned / 0 killed | 同目录 `samples.csv`（237 样本） |

即**最坏观测值 8.1 s，离 30s 帽还有 3.7 倍余量**；20s 的 kb_search 地板现在几乎必然过度保守
（授窗 < 20s 的轮次直接看不到 kb_search）。但上表全部量自 swap 89–92% 的脏机器，是**上界不是申报值**——
本单第一步就是拿干净条件的读数，然后才动数字。

## 阻塞前置（开工前先确认，别跑到一半发现过线标准恒 false）

#22 步骤 5 指定的过线标准是 `rag_hits > 0`（`finance-base-ab/shape_lib/budget_matrix_compare.py` 按载荷判）。
**当前生产 `hit_count` 恒为 0**：整库 verdict=stale × `require_fresh=True`，检索本身有 24 条命中、全被
新鲜度层丢掉（09-05 八次真实调用无一例外）。所以在新鲜度线未裁决前，`rag_hits > 0` 是一个**永远不成立**的门，
矩阵会全臂判负而与预算无关。二选一，**由用户拍**：

- **(a)** 合 KB 仓 `fix/rag-page-level-freshness`（09-03 用户拍「先都不合」，需重新裁决）后再跑矩阵；
- **(b)** 矩阵臂显式设 `require_fresh=False` 跑**探索模式**，读数如实标 `degraded`，且结论只用于
  「预算够不够」不用于「检索质量」——这不是生产形态，必须写进报告限定语。

选 (b) 时过线标准降级为 `rag_calls > 0 ∧ rag_hollow_success == 0`（对账脚本已有这两个字段）。

## 目标

1. **干净条件读数**：swap < 80% 的窗口里拿到热 worker 单次 hybrid 的 p50 / p95（N ≥ 20），
   与首轮模型延迟（GLM 时段 7–13s）一起构成 T/R 的算术输入。
2. **重填两个数字**：`MIN_WINDOW_SECONDS` 与 `episode_tools.py:910` 的 30s 帽按
   「授窗 ≥ p95 + 首轮模型延迟，reserve 20 起」重算；每个数字在代码注释里写明**它是从哪次读数来的**
   （现注释只说「领域申报，来自生产实测」，没说哪一次——本单顺手补上出处）。
3. **矩阵证明**：复用 09-04 review 的 T120/R20 与 T90/R20 设计跑差分，证明新数字比旧数字多拿到检索
   （过线标准见「阻塞前置」），且**没有**把工具可见性挤没。
4. **生产回归口径**：切换后前 20 次真实 kb_search 里 `tool_timeout` 收场比例 ≤ 20%
   （来源 `users/*/runs/*/continuous-episode.json`，与 #22 验收同一把尺子）。

## 非目标（写死认领，别顺手做）

- ❌ 不动 `reserve` / `for_tier` / `MAX_TOTAL_SECONDS` / `ASK_TOOL_BATCH_TIMEOUT` 的**结构**（只重填上面两个数值；
  reserve 参与算术但不改默认值——去处：若矩阵证明 reserve 是主因，另立单，别在本单顺手改）。
- ❌ 不合、不改 KB 仓新鲜度判据（去处：用户裁决，见「阻塞前置」）。
- ❌ 不切 8792（去处：`docs/workflows/acceptance-workflow.md` §4，用户口令触发）。
- ❌ 不改 bge-m3 精度 / 不换嵌入模型（去处：#22 选项 C，产品级决策另立单）。
- ❌ 不为了凑样本在 swap > 80% 时段读 p95 当申报值（这是 #22 红线的原样继承）。
- ❌ 不在量测期间起第二个 bge-m3 进程（`kb_rag.retrieve` 的 `rag_worker` 单例是**进程级**的，
  任何新进程调它都会起自己的模型；要走生产 worker 只能经 8792 HTTP）。

## 证据路径表（先读这些，禁止臆测）

| 文件 | 看什么 |
|---|---|
| `docs/handoffs/inflight/perf-rag-worker-slimming.md` | 三刀合入后的生产读数、决策与被否方案、踩过的坑（探针进程组、readiness 503 body） |
| `~/.finance-runtime/rag-mem-probe-20260905/samples.csv` + `kb-cases/*.json` | 09-05 的全部一手读数；列含义见同目录 `probe.py` 头部；**复用勿重造**：发题用 `run_kb_probe.py`（每题一探针 user，经 8792 `/api/runs`） |
| `docs/verification/2026-09-04-budget-matrix-0904-review.md` §3 / §5 | T120/R20 与 T90/R20 的设计、五步计划裁决、为什么「先别跑」——本单是它说的那个「有了热 worker 的 p95 再回来」 |
| `intelligence/services/research_tool_registry.py:594,1254` | 两个地板的定义与字段语义（`min_window_seconds` = 成功一次至少几秒） |
| `intelligence/services/episode_tools.py:910,1514,1551` | 30s 帽、`retrieve_kb` 的 `tool_context.timeout(30.0)`、evidence_search 的申报点 |
| `intelligence/runtime/episode_tool_batch.py:217,300-320` | 地板如何变成**可见性**裁决（`hidden` + `min_window_seconds` 进菜单 JSON），改数字先想清楚这一层 |
| `finance-base-ab/shape_lib/budget_matrix_compare.py` | `rag_calls / rag_hits / rag_hollow_success / rag_timeout_killed / rag_stage_timeout / rag_worker_proof`；**复用勿重造** |
| `finance-base-ab/shape_lib/rag_hot_worker_probe.py` | 热 worker 单次成本探针；台架已在 `kernel.py` 里进程内预热（`run_via_adapter`） |
| `intelligence/tests/test_episode_tool_batch.py:983-1056`、`test_harness_reference_loop.py:392-460` | 改数字会碰红的守门测试（两条 loop 的菜单必须同一格同一字） |

## 步骤

1. **开工三连**：`git status --short && git branch --show-current`；从最新 `gitea/main` 开
   `perf/retrieval-budget-refill`，独立 worktree（`python3 scripts/worktree_board.py` 看板）。
2. **选窗口拿干净 p95**：等 swap < 80%（这台 16 GB 机器常年 > 80%，可能要停 Docker/IDE 或选深夜窗）；
   `sysctl -n vm.swapusage` 每次采样都记进产物，**申报值必须带成立条件**。N ≥ 20，经 8792 `/api/runs` 真实路径发题。
3. **算 T/R**：授窗 ≥ p95 + 首轮模型延迟（7–13s，用当日实测不用记忆值），reserve 20 起；
   写清楚每个候选数字的算术来源。先在纸面上判「新地板会不会把 kb_search 在常见轮次里藏起来」
   （拿 `episode_tool_batch` 的 `would_grant` 分布对照，别只看均值）。
4. **改数字 + 注释写出处**：`MIN_WINDOW_SECONDS`、`episode_tools.py:910`；跑
   `test_episode_tool_batch.py` / `test_harness_reference_loop.py` / `test_episode_tools.py`，
   **做一次变异测试**（把新数字改回旧值，确认守门测试变红）——没被变异证伪过的门禁是假门禁。
5. **跑矩阵**：T120/R20 与 T90/R20，新旧数字各一臂，`budget_matrix_compare.py` 出报告；
   报告里必须有 `rag_worker_proof`，出现 `COLD-WORKER-MATRIX` 就是台架没预热，读数作废重跑。
6. **收口**：全量门禁 + 收据（`bash scripts/run_main_gate.sh`，`check_test_receipt.py --expect-revision` 退出码 0）；
   开 PR（`python3 scripts/gitea_pr.py open --head perf/retrieval-budget-refill --title … --body-file PR.md`）；
   交接落 `docs/handoffs/inflight/perf-retrieval-budget-refill.md`；回写本 INDEX 的 #26 行与 #22 步骤 5 状态。
7. **台账取号**（若要登记预测）：`python3 scripts/claim_ledger_id.py claim --branch perf/retrieval-budget-refill`，
   禁止手工「当日 max+1」；台账另立，不沿用 `R-20260831-02`（那是算法层的单）。

## 验收

- [ ] 干净条件（swap < 80%）的 p50/p95 存在，N ≥ 20，每个样本带 swap 读数；**成立条件写在结论同一句里**。
- [ ] 两个数字改动都带注释出处（哪次读数、哪个文件、哪一天）；`git diff` 里没有第三个被顺手改的预算数字。
- [ ] 变异测试：新数字改回旧值 → 守门测试变红（贴出红的用例名）。
- [ ] 矩阵差分报告存在，含 `rag_worker_proof`，无 `COLD-WORKER-MATRIX`；过线标准按「阻塞前置」选定的那一条，
      并在报告首段写明选了 (a) 还是 (b)。
- [ ] 阴性对照：新地板下 `hidden` 里出现 kb_search 的轮次占比 **不高于** 旧地板（证明没把工具藏没）。
- [ ] 全量门禁绿 + 收据退出码 0；PR 里贴收据路径。
- [ ] INDEX #26 与 #22 状态已回写；交接文档落 `inflight/`。

## 红线

- **不合 `main`**：合并等用户明确确认（`gitea_pr.py merge` 必须显式 `--yes`，且口令来自用户）。
- **不切 8792**：切换走 `acceptance-workflow.md` §4 五步（账本 record/check + 回滚锚），本单只改代码。
- **不强推、不 `reset --hard`、不 `clean`**；提交用 pathspec，别 `git add -A`（主树与别的 agent 共用索引）。
- 解释器只用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（ruff 同 venv）。
- 量测期间不并行起第二个 bge-m3；不在 swap > 80% 的时段读 p95 当申报值。
- 不改 `require_fresh` 默认、不跳过 `freshness_report`。
