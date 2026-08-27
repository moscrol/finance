# 设计：按剩余预算选择 kb_search 检索档位

- 日期：2026-08-20
- 状态：已合 Gitea #275（`c6af3ec2`，2026-08-20）
- 取代：`2026-08-20-dsh-absorption-remaining-fixes.md`（已作废，根因写错）
- 真本源：`docs/prediction-ledger.md` 的 `R-20260817-02`；形状见 `docs/handoffs/2026-08-17-dispatch-d-retrieval-budget.md`
- 父稿：`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md` §4.2 第 6 条（机制在、分配策略未验证）
- dsh 接缝：`tools/pre-execute`（执行前按剩余时间选档；本 P0 **不**新建 Plugin / ToolPipeline）

## 0. 一句话

不是检索慢，也不是把一批工具的秒数均分。同一批工具**并发**共享一个墙钟窗口；窗口不够跑 hybrid 时，`kb_search` 在进稠密检索之前改走 BM25，带回部分结果，而不是整批 `tool_timeout`。

**判别变量**（台账原句，实施与验收只锁这一条）：剩余时间 → 检索档位。不是把窗口调大，不是按工具名加权切预算。

## 1. 范围

### 1.1 做

- 给 `kb_rag.retrieve` 增加一条**时间触发**的降档，与现有四条**能力触发**降档并列。
- 离线夹具锁死 `R-20260817-02` 的两种预算态：剩 4s → BM25 且有结果；剩 20s → hybrid。
- 降档必须写进现有遥测（`requested_mode` / `effective_mode` / `fallback_reason` / `degraded`），模型观测继续走已经存在的「降级就说出来」路径。

### 1.2 不做

- 不改 `ASK_TOOL_BATCH_TIMEOUT`、`MAX_BATCH_TOOL_CALLS`、`MAX_GLOBAL_TOOL_WORKERS`、`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`、`_REPAIR_SECONDS_CAP`、生产档位。这是 `R-20260816-07` / `R-20260816-21` 绊线。
- 不把第 5 个工具派发出去。`tool_budget_exhausted` 在每批第 5 个调用上是**次数闸**（上限 4），不是本单的失败形状。
- 不改 `ToolSpec` 字段，不新增 `cost_tier` / `estimated_duration_seconds`，不新建 `episode_tool_budget_strategy.py`，不做优先级加权分配。
- 不把「工具饥饿」（模型点了注册表里没有的能力，`#173` / `aeae5b15`）当成验收尺。那是另一条观测链，且该提交不在 `gitea/main`。
- 不在本单落地追问 `view()`。那份设计已经在 `2026-08-17-followup-angle-composer-design.md`，见 §9。
- 不引入 dsh TypeScript 插件，不改 Evidence Ledger / 语义核验。
- 不要求重放 live `run_20260817_094617_943922` 才能合入。离线夹具是合并闸；live 另拍。

## 2. 术语

| 词 | 含义 |
|---|---|
| **共享窗口** | 一批工具并发提交，共用一次 `stage_timeout`。整批墙钟是最慢那个的 `max()`，不是各工具耗时的 `sum()`。 |
| **次数闸** | `_select` 用 `min(MAX_BATCH_TOOL_CALLS, remaining_slots)` 截断候选人。超出的调用 `error=tool_budget_exhausted`。 |
| **时间闸** | 批次 `publish_cutoff` 到点后未完成的 future 记 `tool_timeout`。 |
| **检索档位** | `bm25`（关键词）→ `hybrid`（BM25 + 稠密向量 + RRF 融合）→ `rerank`（再加二次重排）。成本递增、召回语义递增。 |
| **能力降档** | 现有四条：`dense_dependency_missing` / `dense_dependency_cached_unavailable` / `persistent_worker_unavailable` / `legacy_cli_missing_*`。缺依赖才降，与剩余时间无关。 |
| **时间降档** | 本单新增：`fallback_reason="remaining_budget"`。有时间跑 hybrid 才跑；否则 BM25。 |
| **判别变量** | 预测台账里写死的那条因果链。验收必须能证明改的是它，而不是旁路常数。 |

人话：共享窗口像一桌菜共用 12 分钟出餐，不是把 12 分钟切成四份给四道菜。档位像交通工具——时间不够就改步行（BM25），不是把绿灯时长偷偷加长。

## 3. 已核实事实（实施时不要再探一遍）

来源：T-D 派单、`R-20260817-02`、`episode_tool_batch.py`、`kb_rag.py`、`agent_research.py`。均为代码或冻结 run 读数，不是推断。

1. 批次并发，共享 deadline。`episode_tool_batch.py` 注释原文：工具并发提交，但共享一个 `stage_timeout(tool_batch_timeout_seconds())`。
2. 冻结 run `run_20260817_094617_943922`：`kb_search` 的 `batch_grant_asked=30.0`、`stage_timeout_granted=11.955`、`queued_ms=2.2` → `tool_timeout`；同批第 5 个 `news_search` → `tool_budget_exhausted`；`finalization reason=retrieval_deadline_closed`。同批还有 `finance_query`×2 与 `memory_lookup`。
3. `kb_rag` 热态 4.25s / 5.10s；同进程冷调 39.06s。8792 常驻 worker 启动期 prewarm（`prewarm_latency_ms=38516`）。**冷启动不在请求路径。**
4. 现有降档全是能力触发，没有按剩余时间选档。`episode_tools.retrieve_kb` 写死 `mode="hybrid"`。
5. `_kb_search` 用 `context.timeout(DEFAULT_TOTAL_SECONDS)`（60s 名义）再经 `stage_timeout` 裁到剩余窗口，然后把这个秒数传进 `retrieve`。时间降档的输入就是这个已裁过的 `timeout`。
6. `ToolSpec.cost` 已是 `local|external`（会不会外呼），不是耗时档。不要复用这个字段。结构图有 `ToolSpec` 类，没有 `cost_tier` / `estimated_duration_seconds`。
7. 子研究 `_BranchBudgetView` 不铸新预算。把同批工具搬进子 Agent 不解这题。
8. `kb_rag.retrieve` 是汇合点，不是 episode 私有：`episode_tools.retrieve_kb`、`ask.py`（至少 3 处）、`evidence_providers.py`、`runtime/agent.py`、`workflows/daily_agent.py`、`prime.py` 都调用它。选档必须写在 `retrieve()` 里，调用方不写第二份阈值。
9. `DEFAULT_RAG_TIMEOUT = 90`。`wiki_rag_timeout` 默认 90 / 120 / 30，都 ≥ 15，生产默认路径不会误降。结构图确认 `select_mode_for_remaining` / `HYBRID_MIN_REMAINING_SECONDS` / `remaining_budget` 原因码**还不存在**。
10. `intelligence/tests/test_kb_rag.py` 多处 `timeout=5` 是**子进程墙钟**，用来测能力降档 / legacy 重试，不是「episode 只剩 5 秒」。15 秒切点生效后这些夹具会先走时间降档、测不到原原因码。实施时：
    - 断言先打 hybrid/dense/rerank 的夹具：`timeout=5` → `20`
    - `test_dense_dependency_failure_skips_fallback_without_budget`：既要先打 dense，又要在失败后剩余 < 1s 才跳过 BM25 重试。把 `timeout` 改成 `20`，并把 `time.monotonic` 的跳跃改成吃掉 ≥19s，保持「失败后不够再开一枪」。

## 4. 选型（写进 spec 以免实施时重开）

| 方案 | 做法 | 为什么不选 / 为什么选 |
|---|---|---|
| **A. 剩余时间 → 档位（本单）** | `timeout < 15s` 且请求的是稠密模式 → BM25 | 判别变量与台账一致；不碰绊线常数；hybrid 热态 5s 级，15s 以下改步行仍能交卷 |
| B. 按工具名加权切秒数 | 高优先级工具多分墙钟 | 并发批的成本是 `max()`，切秒数是串行模型。会让低优先级工具更早死，也改不了第 5 槽 |
| C. 把 30s 批次上限调大 | 改 `ASK_TOOL_BATCH_TIMEOUT` | 台账禁止；只推迟同类故障 |
| D. 把每批 4 槽调大 | 改 `MAX_BATCH_TOOL_CALLS` | 第 5 槽是次数闸，不是本预测；触绊线 |

可迁移点：任何「一批并发工具 + 总超时」的系统，先画 `max` 还是 `sum`，再谈分配。面试常问超时是共享 deadline 还是 per-task timeout，就是这一刀。

本仓已有相近形状：`2026-07-20-rag-worker-budget-isolation-design.md` 是闭环检索里「下一 aperture 预算不够就别发」。本单是**同一形状换切面**——单次 `kb_search` 的档位，而不是 broad/counter 的第二枪。不要重做那套 aperture 账本。

## 5. 真值表（实施不得改行，只能改实现）

纯函数，建议落在 `intelligence/services/kb_rag.py`：

```python
HYBRID_MIN_REMAINING_SECONDS = 15.0
REMAINING_BUDGET_FALLBACK = "remaining_budget"

def select_mode_for_remaining(
    requested: str,
    remaining_seconds: float,
) -> tuple[str, str | None]:
    """返回 (effective_mode, fallback_reason 或 None)。无 IO。"""
```

| 输入 `requested` | 输入 `remaining_seconds` | `effective` | `fallback_reason` |
|---|---|---|---|
| `hybrid` / `dense` / `rerank` | `4.0` | `bm25` | `remaining_budget` |
| `hybrid` / `dense` / `rerank` | `11.955`（现场授予，回归用） | `bm25` | `remaining_budget` |
| `hybrid` / `dense` / `rerank` | `20.0` | 与 requested 相同 | `None` |
| `bm25` | 任意正数 | `bm25` | `None`（已经是步行，不再标降档） |
| 任意稠密模式 | `0` 或负数 | 不进入 retrieve；现有 `TimeoutError` / `timeout<=0.001` 路径 | — |

**15.0 怎么来的（标定，不是占位）：**

- 必须 `> 4.0` 且 `≤ 20.0`，否则台账夹具无意义。
- 必须 `> 11.955`，否则冻结现场仍走 hybrid，预测结不了。
- 热态 hybrid 5.10s × 1.25（与 RAG aperture 同一安全系数）≈ 6.4s，这是**下界**；现场 12s 窗口里 hybrid 仍然超时，说明这条调用的实际耗时高于热态探针，切点按现场授予加余量取 15。
- 以后若有分位实测要改切点，另开台账行，本单常数保持 15.0。

`retrieve()` 里调用顺序：

1. 时间降档（本单）：稠密模式且 `timeout < 15` → 改 `mode=bm25`，打 `degraded` + `remaining_budget`。**不要对稠密 worker 发请求。**
2. 能力降档（已有）：依赖缺失再降 BM25，原因码保持原四条，不覆盖成 `remaining_budget`。
3. 真正查询。

`requested_mode` 始终记调用方原请求（episode 默认 `hybrid`）。`effective_mode` 记实跑。有命中也要把降级说明拼进 observation——`_describe_retrieval_degradation` 已经做这件事，新原因码只要出现在 `fallback_reason` 就会被带上。

## 6. 落点

改动面刻意小。新行为是选档，不是新流水线。

| 文件 | 职责 |
|---|---|
| `intelligence/services/kb_rag.py` | **唯一切点。** 常数 + `select_mode_for_remaining`；`retrieve()` 在发 worker 之前调用。`requested_mode` 记入参（episode 仍传 `hybrid`），`effective_mode` 记实跑 |
| `intelligence/services/episode_tools.py` | **不改切点、不写第二份阈值。** `retrieve_kb` 继续 `mode="hybrid"` + 把已裁过的 `timeout` 传入；时间降档发生在 `retrieve()` 内部，这样 ask 路径同样生效 |
| `intelligence/services/agent_research.py` | 不改观测拼接，除非单测发现 `remaining_budget` 没出现在模型可见文本里 |
| `intelligence/tests/test_retrieval_tier_by_remaining_budget.py` | 新建。纯函数表 + retrieve 不碰稠密路径的桩 |

不新建 `intelligence/runtime/` 模块。选档懂的是检索档位（领域），不是循环调度；`services` 不得 import `runtime` 的门禁保持不变。

`tools/pre-execute` 在本仓的对应物就是：**执行体拿到 timeout 之后、发稠密请求之前**这一跳。P0 不先做通用 `ToolPipeline` Protocol（那是父稿 §7.1 的更大 P0，本单不搭脚手架）。

## 7. 验收

### 7.1 合并闸（离线，必须）

文件：`intelligence/tests/test_retrieval_tier_by_remaining_budget.py`

1. **4s 夹具**：`select_mode_for_remaining("hybrid", 4.0) == ("bm25", "remaining_budget")`。`retrieve(..., mode="hybrid", timeout=4.0)` 在桩里**零次**稠密/rerank 调用，返回的 telemetry `effective_mode=="bm25"` 且 `degraded is True`。有命中（用 BM25 桩命中）不算失败。
2. **20s 夹具**：`"hybrid", 20.0` → `("hybrid", None)`。retrieve 走 hybrid 路径（桩记录 requested=hybrid、未打 `remaining_budget`）。
3. **现场授予**：`11.955` 与 4s 同行，必须 BM25。
4. **变异**：把选档改成常量 `hybrid`（或把 `HYBRID_MIN_REMAINING_SECONDS` 改成 `0`）时，4s 夹具必须红。这是台账写的变异，不是可选。
5. **已是 bm25**：不打 `remaining_budget`，避免「降级」噪声。
6. **能力降档夹具**：`test_kb_rag.py` 里原先 `timeout=5` 且断言先 hybrid 的用例改为 `timeout=20` 后仍绿；原因码仍是 `dense_dependency_*`，不是 `remaining_budget`。
7. **回归**：现有 `test_agent_research.py` 里能力降档观测、`test_episode_tool_batch.py` 次数闸（第 5 个 `tool_budget_exhausted`）继续绿。

### 7.2 明确不算通过

- 第 5 个 `news_search` 被派发。
- `tool_hunger.jsonl` 计数下降。
- 只把批次 30s 调到 60s 之后 live 不再超时。
- 没有变异测试。

### 7.3 live（不合入条件，用户另拍）

同题重放仅用于结 `R-20260817-02`，不是 PR 闸。结案仍要：剩余窗口不足时 `kb_search` 以 BM25 **返回部分结果**，终局原因不再是 `retrieval_deadline_closed`。单次 live 不得 `confirmed`。

## 8. 禁令（正写：本单只改选档）

本单只改「发检索之前选哪一档」。下面这些名字出现在 diff 里就打回：

`ASK_TOOL_BATCH_TIMEOUT`、`DEFAULT_TOOL_BATCH_TIMEOUT_SECONDS`、`MAX_BATCH_TOOL_CALLS`、`MAX_GLOBAL_TOOL_WORKERS`、`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`、`_REPAIR_SECONDS_CAP`、`ToolSpec` 新字段、`PriorityWeightedStrategy`、`episode_tool_budget_strategy.py`。

## 9. 相邻工作（本文件不是它们的 spec）

| 主题 | 去哪 | 本单关系 |
|---|---|---|
| 追问芯片 `view()` / `compose_followups(state)` | `2026-08-17-followup-angle-composer-design.md` | **`gitea/main` 已有** `compose_followups(state, polish=False)`，默认零模型；`polish=True` 才走 LLM 润色。本单不改 followups。当前脏树 `feat/reading-rules-baseline-batch1` 还没有这个函数，实施必须从 `gitea/main` 开新树。 |
| 公开答案唯一 `view()` | 已合 `#134` / `9a243936` | 完结，不重做 |
| 未知工具需求观测 | `#173` 派单；实现在 `feat/tool-hunger-telemetry`（`aeae5b15`），未入 `gitea/main` | 词「饥饿」不要用在本单验收 |
| 运行时 reserve / cutoff 缝 | `2026-07-28-runtime-budget-cutoff-seam-hardening-design.md` | 合成预留与信息截止日，不是检索档位。代码地图正门会命中它，不要当成本单 |
| 闭环 aperture 预算 | `2026-07-20-rag-worker-budget-isolation-design.md` | 「下一枪别发」；本单是「这一枪降档」。互补，不重做 |

## 10. 成立条件

- 实施树：从最新 `gitea/main` 新建 `fix/retrieval-tier-remaining-budget` 干净 worktree。**不要**在 `feat/reading-rules-baseline-batch1` 或其它脏树上改。
- 解释器：`.venv-workbench/bin/python`
- 台账行：`R-20260817-02` 保持 `pending` 直到 live 另拍；本单只交付离线闸与实现。
- 审核者：用户（77）。代码地图核对见 §12。

## 11. 交付清单

- [x] `select_mode_for_remaining` + 常数 `HYBRID_MIN_REMAINING_SECONDS = 15.0`
- [x] `retrieve()` 在稠密请求前应用时间降档
- [x] `fallback_reason="remaining_budget"` 能出现在模型可见 observation
- [x] `test_retrieval_tier_by_remaining_budget.py`：4s / 11.955 / 20s / 变异 / 已是 bm25
- [x] 次数闸与能力降档回归绿
- [x] `test_kb_rag.py` 能力降档夹具 `timeout=5` → `20`
- [x] 本 spec 实施收据（合入后勾选，不改真值表）

## 12. 代码地图核对（2026-08-20）

正门：`feat/code-map-facade` worktree 上 `python3 scripts/code_map.py`。当前主检出树 `.code-review-graph/graph.db` 仍是空壳，**不能**当结构结论。

| 项 | 读数 |
|---|---|
| 图 | `node_count=17424`，`built_at_sha=89fd6a6e`；HEAD `4ab58793` 只改 `scripts/code_map.py`，结构层标 stale、与本单无关 |
| CLI `query` 结构层 | `uvx code-review-graph search` 本问 hits=[]（召回失败 ≠ 没有符号）。结构结论改走同一份 `graph.db` 的 FTS + 当前树源码 |
| 正门层 | 命中 RAG / 预算类 spec（`2026-07-20` aperture、`2026-07-28` reserve）。正门压过：那些不是本单 |
| `retrieve` | `kb_rag.py:700` 存在；`select_mode_for_remaining` / `HYBRID_MIN_REMAINING_SECONDS` 节点数 0 |
| `retrieve_kb` | `episode_tools.py` 与 `ask.py` 各有一枚同名嵌套函数，都进 `kb_rag.retrieve` |
| `compose_followups` | facade / `gitea/main` 已有；本脏树没有。本单不碰 |
| `MAX_BATCH_TOOL_CALLS` | FTS 未建节点（模块级常数）；源码 `episode_tool_batch.py` 仍是 4。不改 |

结论：切点、真值表、非目标成立。唯一要写进实施的遗漏是 `timeout=5` 的能力降档夹具。
