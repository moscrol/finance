# T-D 派单：检索预算分配（**通用底座**）⚠ 立案不动手

- 日期：2026-08-17 ｜ 索引：`2026-08-17-dispatch-00-index.md`
- **层：通用底座**（spec §2.1 明列「工具调度、预算」）
- **dsh 接缝：`tools/pre-execute`**（dsh §5.1 强项：pre-execute → execute → post-execute →
  finalizeContent → result，支持 Guard）
- 信源路由：**通用层 → dsh 量接缝**＋ ai-agent-book / 马书讲原理
- **状态：本窗只记账，动手要用户另拍**（触 R-20260816-07 绊线）

## 0. 一句话

不是检索慢，是**一个 4~5 秒的工具排在 12 秒窗口的第四位**。

## 1. 现场（自包含）

基准 run：`run_20260817_094617_943922`，墙钟 156.6s
8792：`31ee58ce` / dirty=false / `code_matches_repo=true`

`tool_error` 实测：

```
kb_search    batch_grant_asked=30.0  stage_timeout_granted=11.955  queued_ms=2.2  → tool_timeout
news_search  同一批                                                              → tool_budget_exhausted
finalization reason=retrieval_deadline_closed
```

同批还有 `finance_query`×2（有行）与 `memory_lookup`（空），它们先跑完把窗口吃掉了。

## 2. 已排除的两条路（**别再走一遍**）

### ① 不是冷启动

`kb_rag` 本体实测：同进程冷调 **39.06s**，之后 **4.25s / 5.10s**（热态，`persistent_worker` 协议）。
8792 的常驻 worker 已在启动期 prewarm：`prewarm_latency_ms=38516`、`lifecycle=startup_prewarm`、
`model_load_count=1`。**冷启动不在请求路径里。**

这个形状正是 ai-agent-book `chapter3/retrieval-pipeline` 的架构（模型在进程 `__init__` 加载、
启动脚本逐个 health-gate 等就绪、之后只发 HTTP）——**我们已经实现了，别重做。**

### ② 不是串行，subagent 化也不解这题

`intelligence/runtime/episode_tool_batch.py` 用 `ThreadPoolExecutor` 同批**并发**提交。
代码注释原文：

> 一个批次里的工具是并发提交的，**但共享一个 deadline**（`stage_timeout(tool_batch_timeout_seconds())`），
> 而线程池 `MAX_GLOBAL_TOOL_WORKERS=8` 是**全局**的：3 个并发分支各发一批
> （每批至多 `MAX_BATCH_TOOL_CALLS=4`）就可能有 12 个调用抢 8 个 worker，
> 排队的那几秒照样从共享窗口里扣。

按 ai-agent-book ch10 总判据「**协作过程有没有引入单个 Agent 在生成时无法获得的新信息**」——
把同一批工具搬进子 Agent **没有新信息**，不构成开 subagent 的理由。

knevo 之所以能靠 sub-agent 缓解，机理是**独立 `bg_task_id` 的后台任务、不从父轮次窗口扣时间**
（生命周期隔离），**不是并行**。且 knevo 是**分档**的：轻档主线程快答（1–3 轮工具）、
中档主线程深检索（**4–8 轮，明确不派单**）、重档才派单——本 run 四工具一批正落在「中档＝不派单」。

**结论：继承同一条 episode deadline 的子 Agent 是纯亏**（多付 spawn 与交接成本；
ai-agent-book ch4 实验 4-3：交接质量不够时，开子 Agent 比自己干更差）。

## 3. 真正的方向（等用户拍板后才动）

按 §14 反推，这条挂 `tools/pre-execute`：**按剩余预算选检索档位**。

ch3 的混合检索本来就是分档的、成本递增：BM25（快）→ +稠密 → +rerank（慢）。
我们的档位现在是**静态**的（`kb_rag.DEFAULT_RAG_MODE = "hybrid"`），
四个 `fallback_reason` 全是**能力**触发（`dense_dependency_missing` /
`dense_dependency_cached_unavailable` / `persistent_worker_unavailable` /
`legacy_cli_missing_*`），**没有一个是按剩余时间选档**。

「剩 4 秒就只跑 BM25，别整批空手而归」——**书只给形状不给量纲**
（ai-agent-book ch3 是离线 pipeline，没有 deadline 压力）。档位阈值必须我们自己标定。

## 4. 顺带要更正 spec（本轨带）

`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md`：

- §4.1「已有能力」列了「root budget、deadline、**工具批次预算**和 repair cycle」；
- §4.2「需要继续补强的通用部分」五条里**没有它**。

而 2026-08-17 实测：工具批次预算把一个 4~5 秒的工具饿死了。
**机制存在 ≠ 分配策略对。** §4.1 那行该加限定，或 §4.2 补第 6 条。

## 5. 本窗禁令（R-20260816-07 绊线）

**不得**调整：`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`、`_REPAIR_SECONDS_CAP`、
生产档位、`ASK_TOOL_BATCH_TIMEOUT`、`MAX_GLOBAL_TOOL_WORKERS`、`MAX_BATCH_TOOL_CALLS`。

**尤其不得「只把数字调大」**——那正是 R-20260816-21 已经点名禁止的动作。
本轨在拿到用户批准前，交付物只有：账本立案 + spec §4.1/§4.2 更正。

## 6. 环境

- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
- ⚠ **在生产实例上做旁路测量会污染它自己的探针**：直调 `kb_rag.retrieve` 加载 BGE-m3 的
  39 秒里，8792 的 `/api/readiness` 会翻成 `not_ready`（`rag_query_protocol` 探测超时）。
  判据：`workers.rag.model_load_count` 没变就说明常驻 worker 没重载，红的是探针不是 worker。
- Gitea PR：`git credential fill` + `http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls`
- 合 main 必须等用户确认
- ⚠ 不要从 `/Users/a77/finance-workspace-private` 工作树提交（落后 main 293 提交，
  其 `docs/prediction-ledger.md` 相对 main 是 -573/+159 的旧版本）
