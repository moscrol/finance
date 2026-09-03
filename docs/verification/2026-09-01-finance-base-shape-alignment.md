# 收据：金融 Agent 底座形状对齐（2026-09-01）

实施树：`/Users/a77/finance-base-ab/`（不进 `intelligence/`，不改 8792 / 启动器）。
spec：`docs/superpowers/specs/2026-09-01-finance-base-shape-alignment-design.md`

**验收：包装门按预算上游重判为绿。** 原 §7.3 逐项工具序硬门仍红——那是 90/60/30 授权额的下游，不是外壳分叉，也不是模型选工具噪声。attempt-4 的「同臂噪声」读数撤回。未新跑任何一次（配额仍 16）。`compare.py` 已改：硬门 = 首轮 `task_frame_hash` + `input_tokens`±3 + `financial_data` ∈ 首轮 `tool_calls`；全序进 `budget_downstream`。原红结果留在 `out/attempt-4-aligned/compare-result.json`，重判在 `compare-result-rejudged.json`。

## 哨兵

| 项 | 值 |
|---|---|
| resolved 快照 | `/Users/a77/.finance-runtime/finance-workspace-5be00c4f563e` |
| `source_revision` 前/后 | `5be00c4f563e2c1b502df28db034f7ba52ea8d1d` / 同 |
| `agent_episode.__file__` | 快照内 `intelligence/runtime/agent_episode.py` |
| 快照 porcelain 前/后 | 空 |
| 8792 `/api/health` | 200 `healthy`，`continuous_glm` / `glm-5.3` |
| `start-finance-workbench` | 未改（mtime 2026-08-31 17:56:18） |

## 包装门（绿）

- `pi-shape`：`ai` → `agent_core` → `finance_agent`；`ai` 不 import `finance_agent`。
- `dsh-shape`：`spine.boot()` 顺序 llm → tools → loop → finance_domain；loop 不 import `dsh_stub_runtime` / 工具执行体。
- 全树无运行时 `@earendil-works` / `cordis` / `deepseek-harness`。
- `pi-shape/README.md` 写明：`agent_core` = adapter + `GLMAgentRuntime`，≠ Episode，≠ 官方 `pi-agent-core`。
- 三臂 cwd = resolved 快照；`PYTHONPATH` 不含 `finance-workspace-private`；用户账在 `finance-base-ab/out/users/`，未写生产 users。
- 三臂 `used_adapter_episode=true`、同 revision、同 `glm-5.3`。「没另装一条执行路径」成立。

## 对照怎么打（与 spec §7.2 / §8 的差）

`live_probe ask` 实际是 `POST /api/runs` → `_run_ask` / `answer_query`，**不**经 `ContinuousTurnAdapter`。
对照臂按 §8 图走同一条 `_run_conversation_turn`（独立 users、快照 cwd）。未起 sidecar，未打生产 conversations。

偏离 §7.2 是正确的偏离：否则对照臂会变成引擎 B，硬门必漂。

隔离配方里有三处 env 是从 `live_probe.sidecar_zsh` 抄来的，**不是**生产启动器。见下表。这是 spec §7.1 的漏（只钉代码同源、没钉环境同源），收据此前把它写成对齐了——现更正。

## env delta（source 启动器之后）

启动器：`~/.local/bin/start-finance-workbench`。`compare.sh` 先 `. <(grep '^export ' "$LAUNCHER")`，再覆盖/新增。

| 变量 | 启动器 / 8792 | 本轮实验 | 来源 | 行为影响 |
|---|---|---|---|---|
| `RAG_WORKER_ENABLED` | `1` | attempt-2：`0`（抄 sidecar）；attempt-3：继承 `1` | 见各轮 | attempt-2 是已知混淆项。attempt-3 对齐生产，并在三臂前 `kb_rag.prewarm`（39.8s，`state=ready`）。 |
| `WORKBENCH_GROUNDED_PRESENTER` | 未设；代码默认 `"1"`（`ask_types.py`） | `0` | 抄 sidecar（marker lane） | 连续 adapter 主路径通常不走 grounded composer；仍属未披露的偏移 |
| `WORKBENCH_PERSIST_LLM_CONTEXT` | 未设（生产不设） | `1` | 抄 sidecar | 多落 `llm_context.json`，不改工具选择 |
| `WORKBENCH_REPO_ROOT` | symlink `…/finance-workspace-runtime` | resolved 快照 | 本单 §4.1 | 代码同源，故意 |
| `FORESIGHT_USERS_DIR` | `~/.local/share/finance-workbench/users` | `finance-base-ab/out/users` | 隔离 | 故意；未写生产账 |
| `FORESIGHT_USER` | `linxiaoqi5111` | `shape-pi` / `shape-dsh` / `live-probe` | 隔离 | 故意 |
| `PYTHONPATH` | symlink 路径 | shape + `finance-base-ab`；cwd=快照 | §4.1 | 故意 |
| `ASK_CONTINUOUS_RUNTIME` | `on` | `on`（钉死） | 与启动器同 | 无偏移 |
| `AGENT_RUNTIME_BACKEND` | `continuous_glm` | `continuous_glm`（钉死） | 与启动器同 | 无偏移 |

## 两轮题

### 尝试 1（已归档 `out/attempt-1-knowledge-lane/`）

题：`贵州茅台的申万一级行业是什么？`

三臂都判成 `concept_definition` / `lane=knowledge`。adapter `handle` 因 `terminal_kind != research` 拒收，走 `lane_direct_answer`。工具名序列 `[]==[]`，假绿。正文结构对齐（食品饮料）。

### 尝试 2（当前 `out/*.json`，降级检索车道）

题：`2024年贵州茅台营业总收入是多少亿元？`

本轮三臂 `RAG_WORKER_ENABLED=0`（生产为 `1`），故读数不覆盖健康检索路径。三臂 `kb_search` 全部 `tool_error`（pi 1/1、dsh 2/2、live-probe 1/1），live-probe 的 `evidence_search` 也 error；错误原文在 `continuous-episode.json` 为「kb_search 超时」。

| 臂 | question_type | used_adapter_episode | stop_reason | 工具名序列 |
|---|---|---|---|---|
| pi-shape | financial_analysis | true | invalid_repair_finish | kb_search, financial_data |
| dsh-shape | financial_analysis | true | invalid_repair_finish | financial_data, l3_lookup, kb_search, kb_search |
| live-probe | financial_analysis | true | invalid_repair_finish | l3_lookup, financial_data, evidence_search, kb_search |

三臂正文同一句诚实闸（核验未完成 / 12 条证据 / 截至 2026-09-01）。这是同一种失败，不是同一种成功；守门断言未被健康路径触达。pi 臂模型曾由 2025 年报反推 2024 收入，被核验绑定（有 kb 超时的份）压掉。

**工具序差在本轮不能解释成采样噪声。** n=1/臂时噪声与外壳分叉不可分；而且差是在 `kb_search` 硬失败后的改道区间量的——故障恢复的发散，不是温度 0.0 的基线采样。

## 尝试 2b：同臂重复（live-probe×2，同一降级车道）[实测]

目的：在**与 attempt-2 相同的 env**（含 `RAG_WORKER_ENABLED=0`）上量噪声底。同臂真值分叉必为 0，自己跟自己的差就是噪声。

题与 attempt-2 相同。未改 RAG，未重跑 pi/dsh。产物：`out/live-probe-repeat-1.json`、`out/live-probe-repeat-2.json`、`out/live-probe-repeat-compare.json`。

| 次 | 用户 | stop_reason | 工具名序列 |
|---|---|---|---|
| attempt-2 live-probe | live-probe | invalid_repair_finish | l3_lookup, financial_data, evidence_search, kb_search |
| repeat-1 | live-probe-r1 | invalid_repair_finish | l3_lookup, financial_data, kb_search, evidence_search |
| repeat-2 | live-probe-r2 | repair_model_stop | kb_search, financial_data, l3_lookup |

`same_arm_sequences_equal=false`。三次 live-probe 互不相等，也都不等于 attempt-2 的 pi / dsh。repeat-2 甚至换了停因，正文走出诚实闸、写出了 2025 年报 1720.54 亿元。

**降级车道上的噪声底：[实测] 非零，且量级不小于跨臂差。** 因此「attempt-2 跨臂工具序差」不能单独证明外壳分叉——同臂自己就分叉。

**仍不能据此改判硬门。** 这是故障恢复区间的噪声底。

## 尝试 3：`RAG_WORKER_ENABLED=1` 三臂 [实测]

只翻 RAG 这一项（presenter=0 / persist=1 仍抄 sidecar）。`compare.sh` 不再覆盖 `RAG_WORKER_ENABLED`，三臂前预热。

- 预热：`out/rag-prewarm.json` — `enabled=true`，`state=ready`，`prewarm_latency_ms=39821`，`model_load_count=1`。
- 8792 `/api/health` 与 `/api/health/ready` 跑前跑后均为 200；revision 未变；porcelain 空。
- 产物：`out/*.json`（当前）与归档 `out/attempt-3-rag-on/`。

| 臂 | stop_reason | 工具名序列 | kb_search | 其它 |
|---|---|---|---|---|
| pi-shape | repair_model_stop | l3_lookup, evidence_search, financial_data, kb_search | tool_timeout（阶段预算约 25s） | l3/financial_data 成功；evidence_search timeout |
| dsh-shape | repair_model_stop | l3_lookup, financial_data, evidence_search, kb_search | tool_timeout（约 19–26s） | 同上 |
| live-probe | repair_model_stop | kb_search, financial_data, l3_lookup | tool_timeout（约 26s） | financial_data 成功；l3_lookup 也 timeout |

三臂正文都走出诚实闸，给出同一条推算：2025 年报 1720.54 亿元、同比 -1.2% → 2024 ≈ **1741 亿元**。结构比对绿。`financial_data` 三臂都成功——这是相对 attempt-2 多出来的成功段。

`kb_search` 仍全超时。worker 已在、索引已热，失败因是 episode 剩下的 `stage_timeout_granted` ≈ 20–26s，不是 attempt-2 那种无 worker 重载。所以本轮也**还不是**「kb 检索成功的健康路径」。

硬门仍红：三臂工具序互不相同。健康车道上同臂×2 没做，因此「差是采样噪声」在 RAG=1 上仍是 [推断]；加上 2b 在坏车道上同臂已经不稳，外壳分叉也没有单独证据。

**硬门不改判。** attempt-3 单独不够。见 attempt-4。

## 尝试 4：对齐启动器环境 + 同臂×2 [实测]

`compare.sh` 不再覆盖 `WORKBENCH_GROUNDED_PRESENTER` / `WORKBENCH_PERSIST_LLM_CONTEXT`。隔离只留 users 目录、resolved `WORKBENCH_REPO_ROOT`、实验 `FORESIGHT_USER`。`out/attempt-4-env.json`：`align_mismatches=[]`。

预热 46.2s，`state=ready`。8792 health/ready 跑前跑后 200，revision 未变。

三臂（`out/attempt-4-aligned/`）：

| 臂 | stop_reason | 工具名序列 |
|---|---|---|
| pi-shape | repair_model_stop | financial_data, l3_lookup, kb_search, kb_search |
| dsh-shape | repair_model_stop | financial_data, l3_lookup, kb_search, evidence_search |
| live-probe | repair_deadline_exhausted | kb_search, financial_data, evidence_search, financial_data |

同臂重复（同一对齐环境、预热后再跑）：

| 次 | 序列 | stop_reason |
|---|---|---|
| control（上表 live-probe） | kb_search, financial_data, evidence_search, financial_data | repair_deadline_exhausted |
| a4r1 | financial_data, l3_lookup, evidence_search, kb_search | repair_model_stop |
| a4r2 | l3_lookup, financial_data, kb_search, evidence_search | repair_model_stop |

`same_arm_sequences_equal=false`。五次 live-probe 家族互不相等，也不等于 pi/dsh。

**上一版把这读成「对齐环境上的选工具噪声」——错。** 见下一节。当时决定「不改 `compare.py`」已作废：门已按预算上游改，不是改成比工具集合凑绿。

## 尝试 4 更正：授权额决定序列，不是模型 [实测]

全部从 `out/attempt-4-aligned/` 和 6 份 `continuous-episode.json` 重读。没有新跑。

生效预算（standard tier；代码路径已对过）：

| 环节 | 值 | 出处 |
|---|---|---|
| `ResearchPolicy.for_tier("standard")` | 6 步 / 90.0s / reserve 20 | `research_contract.py` |
| `effective_timeout = min(policy.total_seconds, timeout)` | min(90, 300) → **90** | `episode_factory.py` |
| synthesis reserve（`financial_analysis` 不在 heavy 集） | min(75, 60) → **60** | `glm_agent_runtime.py` |
| `reserve = min(60, 90×2/3)` | **60** | `episode_factory.py` |
| `stage_timeout = max(0, remaining − 60)` | 研究阶段无例外 | `research_contract.py` |

整个 episode 只有约 30 秒可派发工具。每轮 LLM 的 5–33 秒记在同一只钟上。`remaining_slots` 从 6 走到 3，次数闸从未生效。研究阶段 15 次派发：`stage_granted == ep_remaining − 60`，无例外。对照臂 repair 后两发 granted=30 而 rem−60 为负——repair 公式不同，另记。

| 臂 | 首轮 LLM(s) | 逐次授权额 | 真正跑成 |
|---|---|---|---|
| pi | 8.98 | 20.3 → 11.5 → 3.5 → 0.0 | financial_data, l3_lookup |
| dsh | 5.71 | 24.1 → 14.8 → 8.3 → 0.0 | financial_data, l3_lookup |
| 对照 | 32.57 | 0.0 → 0.0（后两发 repair=30） | 研究阶段无；repair 才跑成一次 financial_data |
| 重复1 | 6.35 | 23.3 → 14.8 → 6.0 → 0.0 | financial_data, l3_lookup |
| 重复2 | 4.73 | 24.3 → 24.3 → 17.1 → 0.0 | l3_lookup, financial_data |

对照臂首轮 LLM 烧了 32.57 秒，30 秒窗口在工具起来前就穿了。授权额 ≤0 时不进线程池，直接伪造 `tool_timeout`（`episode_tool_batch.py`）。模型看到的是 `{"ok": false, "error": "tool_timeout", "detail": ""}`，和真跑十几秒再超时逐字相同。它换工具再试，序列分叉。

三处更正上一版读数：

1. 「知识库检索照样超时，是剩给它的二十来秒」——六次 run 里 `kb_search` 0/8 成功、`evidence_search` 0/4 成功。其中 kb 4/8、evidence 2/4 是授权额为 0、根本没派发。真跑过的只有重复2 的 17.1s 和中断那次 a4r1 的 23.2s。
2. 「对齐了」只对齐了环境变量。`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS=300` 被 tier 的 90s 硬顶截掉。`LLM_TIMEOUT=180` 这条链路不读（引擎 B）。生效是常量 `DEFAULT_GLM_LLM_TIMEOUT=75.0`——每个 `model_turn` 的 `timeout_configured` 都是 75.0。`attempt-4-env.json` 的 `align_mismatches: []` 是真的，它断言的是环境变量，不是生效值。
3. 改成「比工具集合」也过不了。pi `{financial_data, l3_lookup, kb_search}`、dsh 多一个 `evidence_search`、对照 `{kb_search, financial_data, evidence_search}`——三个全序集合两两不等。集合差同样来自窗口里塞得下几个。

外壳没搬坏：六次 run 首轮 `task_frame_hash` 全是 `e6ee9044…`；`input_tokens` 是 12734 / 12735 / 12736 / 12737（极差 ≤3）。`financial_data` 出现在 6/6 的首轮 `tool_calls`。三臂装配出的提示词、工具清单、契约实质相同。从第二轮起是钟在说话。

**首轮集合并不是零方差**（对上一句的收窄）：对照 `{kb_search, financial_data}`，重复2 `{l3_lookup, financial_data}`，pi/dsh `{financial_data}`。所以硬门没有做成「首轮集合相等」——那会红，而且红的是首轮多点了一个名字，不是包装。做成了：hash 相同 + token 带 + `financial_data` 必在。`first_turn_set_mismatch` 记在重判 JSON 里，不卡门。

换题救不了这条全序门：短题一样烧 30 秒窗口，`kb_search` 需要 >17s 也没变。要留逐项序门，得先修预算（抬 tier、reserve 随剩余缩、或首轮 LLM 不记在工具钟上）。那是 Episode / 生产单，本单红线是不改 Episode。

8792：[推断] `_run_conversation_turn` 是 8792 chat 轮次的同一段代码，同一套 launcher env，所以生产也在 90/60/30 上跑。没碰 8792。

取证坑：工具事件的 `at` 是落盘时刻不是执行时刻（重复2 的 `financial_data` 请求与结果 `at` 只差 6ms，`elapsed_ms` 却是 633.5）。可信字段是 `episode_remaining_at_dispatch` / `turn_elapsed_at_dispatch` / `queued_ms` / `elapsed_ms`。账本摘录：`out/attempt-4-aligned/budget-chain.json`。

## §9.4 compare.sh

attempt-2 / 3 / 4 **当时**退出码 1（逐项序门）。重判后当前 `out/compare-result.json` 退出 0（新包装门）；attempt-4 归档仍保留原红 `compare-result.json`。

LLM 次数：1×3 + 2×3 + 2b×2 + 3×3 + 4×3 + 4 同臂×2 = 16。未换模型、未加跑。

## 未做（仍属红线）

- 未改 Episode / stub / benchmark 契约 / 8792 / 启动器。
- 未把 `live_probe ask` 当对照臂真入口。
- 未修 90/60/30；`kb_search` 在对齐环境上仍被阶段预算打死。要「检索成功」或恢复逐项序门，是另一单。
