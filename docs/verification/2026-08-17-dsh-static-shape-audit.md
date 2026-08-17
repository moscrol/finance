# T-E 交付：dsh 静态形状对照（三分类清单）

- 日期：2026-08-17 ｜ 执行：主 agent（本会话）｜ 交接：`docs/handoffs/2026-08-17-dispatch-e-dsh-static-shape-audit.md`
- 依据：spec `2026-08-15-agent-base-dsh-absorption-design.md` §9.5（本轨随 PR #132 新增）
  ＋ `2026-08-17-followup-angle-composer-design.md` §14 反推口令
- **成立于**：本仓 revision `31ee58ce6c45`（8792 当前生产快照，`code_matches_repo=true`）；
  dsh 侧只经 `DSH_SOURCE_INDEX` 的 pin，未连真实 dsh。**dsh pin 变更须重跑本清单。**
- 未跑 live、未改代码、未烧 LLM 配额。

## 0. 两条纪律（先声明，否则本清单会被读成整改单）

1. **「能挂上」≠ 生产改去跑 dsh。** 只检验边界像不像插件。
2. **「挂不上」≠ 我们没拆好。** dsh 不判「这数对不对」（spec §5.2）——
   语义核验与 Evidence Ledger 挂不上是**正确结果**，不得据此立整改项。

---

## 1. ① 挂得上，且**已实测跑通**

**关键发现：spec §11 第 7 步的前半段其实做过了。**
`intelligence/runtime/dsh_stub_runtime.py` 存在，用脚本化 stub 走现有
`HeadlessToolGateway` 的 JSON/HTTP 面把窄协议跑通，不 import dsh SDK、不拉起 Node。

`ADAPTER_PROTOCOL_KEYS` 共 **7 项**（解析器读出，非行号）：

| 协议键 | 本仓对应 | 证据 |
|---|---|---|
| `task_frame` | `services/task_frame.TaskFrame` | **[实测]** stub import 并跨桥 |
| `episode_scope` | `services/episode_scope.EpisodeScope` | **[实测]** |
| `tool_definitions` | `services/research_tool_registry`（**12 个工具**，解析器计数） | **[实测]** |
| `tool_calls` | `HeadlessToolGateway.call` | **[实测]** |
| `tool_results` | 同上，`public_agent_evidence` 投影 | **[实测]** |
| `durable_events` | `services/agent_runtime.EpisodeEvent` + `episode_projection.DurableEventProjection` | **[实测]** |
| `final_outcome` | `services/agent_runtime.AgentOutcome` | **[实测]** |

**这 7 项是「形状对」的经验证据，不是推断。** 它们已经真的跨过一次边界。

工具 12 个（`_DEFAULT_TOOL_METADATA`）：`finance_query` `evidence_search` `kb_search`
`web_search` `news_search` `graph_lookup` `evidence_lookup` `memory_lookup` `l3_lookup`
`market_data` `financial_data` `mainline_context`。

stub 还写死了三条禁止双写（spec §8.3），值得记：`tool_call_id` 就是网关 `request_id` 不另造号；
模型可见结果只走 `public_agent_evidence`，`internal_locator`/DuckDB 路径/凭证不过桥；
durable 事件来自网关 snapshot，不另开 Session 账本。

## 2. ② 只能塞进 tool 的 `execute`（dsh 只宿主流水线）

| 组件 | 说明 | 证据 |
|---|---|---|
| `finance_query` / `market_data` / `financial_data` / `l3_lookup` 等领域工具 | schema 挂 `ctx.tools`，**A 股语义全在 `execute` 里** | **[实测]** 见 §1 的 12 工具表 |
| 截止日 / 新鲜度 floor / honesty 门 | 形状挂 `tools/pre-execute`，**判据仍是领域的** | [推断] 未逐一验证挂点 |
| 「按剩余预算选检索档位」（T-D 想要的那个） | 同上挂 `tools/pre-execute` | [推断] **尚未实现**，见 §5 |

结论：这一档**可接受，不是债**。对错仍由 Evidence / Verifier 判，符合 spec §12「接口优先于迁移」。

## 3. ③-a 焊死了（**待拆的债**，仅此一条经实测确认）

### 公开答案的投影出口不唯一

`public_answer=` 全仓赋值点共 **16 处**（不含 tests），**全在
`intelligence/services/episode_semantic_verifier.py` 一个文件里**——文件收敛是好的，
但**出口不收敛**：

- 13 处经 `_gap_answer(...)` / `_generic_gap_answer(...)`（挂着 `degraded_fallback` 的兜底章法）
- **3 处自己拼串绕过**：`f"{notice}\n\n{public}"`、`public`、`f"{public}\n{gap}"`

dsh 的 session-projection 接缝要求**「必须同步」**——同一份终局事实必须只有一条 `view()`。
三个旁路出口直接违反它。

**这就是 T-B 的根，且比 T-B 交接里写的更严重**：交接只点了瞬时故障投影那一条旁路，
实际有 **3 条**。修 T-B 时若只并掉那一条，另外两条仍在。

⚠ **T-B 交接需按本条更新。**

## 4. ③-b 领域真源（挂不上是**正确结果**，不立整改项）

| 组件 | 为什么挂不上 |
|---|---|
| `episode_semantic_verifier`（金融语义判据） | dsh 无「对错」通用接缝 |
| Evidence Ledger / evidence hash / output binding | dsh Session Log 不能替代（spec §5.2 明写） |
| `structural_verifier` | 同上 |
| 新鲜度 floor / `information_cutoff` 判据 | 领域真源 |
| D3 | 领域计算，经 tool/storage 露出结构对象；**禁止从 Markdown 反解析** |

**这一档不产生任何待办。** 把它写成整改项，就是去「修」一个本该那样的东西。

## 5. 顺带纠正 T-D 一条推断 → 实测

T-D 交接里我写过「subagent 化不解检索超时，因为子 Agent 若继承同一条 episode deadline
就是纯亏」——当时是**推断**。现在有直接代码证据：

`intelligence/runtime/sub_research.py` 的 `_BranchBudgetView` docstring 原文：

> **A non-minting child view whose consumption debits one parent ledger.**

即**子研究分支不铸新预算，消耗直接记在父账本上**。所以我们确实**没有** knevo 那种
「独立 `bg_task_id` 后台任务、不从父窗口扣时间」的生命周期隔离。

**T-D 那条结论成立，证据等级从 [推断] 升为 [实测]。**
同时这也说明：真要抄 knevo 的形状，缺的**不是** subagent 机制（`SubResearchCoordinator` /
`SubResearchWorker` / `BranchRequest` / `BranchResult` 都在），**缺的是不铸币的那层能铸币**——
是预算模型的改动，不是拓扑的改动。

## 6. 本轨发现的一条新差距（现状 vs spec §14 要求）

followup spec §14 对 P0 compose 的要求：

> compose 必须能当 `view()` 用——输入冻结 state，输出整份芯片，**无 IO、无模型、无订阅**。
> LLM 润色不能进这条函数，否则在 dsh 上会撕掉「同步一致性切面」。

**现状不满足**：`intelligence/services/followups.py` **import 了 `llm_refine`**，
`_llm_followups` 调 `llm_refine.complete(...)`，且 `generate_followups` 的
`use_llm: bool = True` **默认开**。**[实测]**

⚠ 这**不是**说 spec 被违反了——§14 是对**新** compose 的前瞻要求，`followups.py` 是存量。
但**若新 compose 复用 `followups.py`，就会把 LLM 带进 `view()`**。
这条差距应在 P0 实施计划里显式处理（拆成「纯 view + 可选 LLM 增强」两层，或另写）。

## 7. 原待判三项 —— **已于同日补完，三条全部落在①档**

### 7.1 foresight → `ctx.commands`（＋ `ctx.jobs`）：**挂得上，没焊死**

用户表里点名「别焊进 ask s03」。**实测：`intelligence/services/ask.py` 里 `foresight` 命中数 = 0。**

真实调用面只有一处：`intelligence/server.py` `from intelligence.services import foresight, interactions`，
挂在独立路由 `GET /api/foresight` 后面（`_api_foresight()`）。

排除两个假阳性：`keychain_credentials.py` 命中的是 keychain 服务名字符串
`com.foresight.workbench.llm`；`followups.py` 命中的是 docstring 里的对比说明，**都不是调用**。

判定：**挂得上，不用改 loop 图**——它已经是「领域计算 + 独立命令入口」，
对应 `ctx.commands`；`load_asked_memory` / `append_asked_memory` 的 IO 走 `ctx.storage`。
若日频主动发问要调度，那一半挂 `ctx.jobs`。**[实测]**

### 7.2 skills 桥 → `ctx.skills`：**挂得上，且渐进披露已成立**

`SkillSpec` 字段（解析器读出）：`name` `description` `script` `citation_source`
`parser` `needs_vault` `limit`。`SKILL_REGISTRY` 注册 **1** 个（`serenity-alpha`）。

这正是 dsh `ctx.skills` 的形状：**声明与执行体分离**——模型上下文里只进 `description`，
`script` 到调用时才跑，正文不进窗口。**渐进披露在效果上已经成立。[实测]**

⚠ **「只注册 1 个」不是形状缺陷，是刻意的领域约束**（其余 skill 会拉实时数据或写库，
破 agent 只读 + 无外呼红线，见 CLAUDE.md）。不得据此立整改项——
这正是 §0 纪律 2 的适用场合。

### 7.3 芯片 UI / 投影 → `ConversationNode`：**挂得上，只读边界干净**

对 `episode_projection.py` 与 `status_projection.py` 扫
`llm_refine|provider|httpx|requests|subprocess|open(|.write(|execute(|commit()`：
**两份都是 0 命中**。即两条投影是纯的，满足 `view()` 合同。**[实测]**

> **与 §6 形成对照，值得记**：同样是「投影」，`episode_projection` / `status_projection`
> 干净，而 `followups.py` 却 import 了 `llm_refine`。**说明本仓不是不会写纯投影，
> 是追问这条线没按投影写。** 这让 §6 那条差距从「能力问题」降为「这一处没照做」，
> 修起来是局部的。

## 8. 总结

| 档 | 数量 | 是不是债 |
|---|---|---|
| ① 挂得上 | 7 项协议（已实测跨桥）+ 12 工具 + **foresight / skills 桥 / 两条投影**（§7） | 否 |
| ② 只能塞 `execute` | 3 类 | 否，可接受 |
| ③-a **焊死了** | **1 条**（公开答案 3 个旁路出口） | **是，归 T-B** |
| ③-b 领域真源 | 5 类 | 否，正确结果 |
| 待判 | **0**（原 3 项已于 §7 补完） | — |

**本轨已收口。** 全清单成立于 revision `31ee58ce6c45`；dsh pin 变更须重跑（spec §9.5 末条）。

### 结论：焊点只有一处，其余形状是对的

量完一圈，本仓**只有一个真焊点**——公开答案投影的 3 个旁路出口。其余组件要么挂得上，
要么是「只能塞 `execute`」（可接受），要么是领域真源（挂不上才对）。

这个结果本身值得记：**说明 §7.1–7.6 那批接缝确实落到位了**，
不是「合了 PR 但形状没变」。第 8 步 A/A′ 该测的是这批接缝的**收益**，而不是它们**在不在**——
在不在，本轨已经回答了。

**Arm B 降级的对价已付。** 本轨找出的这一样，A vs A′ 永远测不出来：
三条旁路**都能出答案**，只是出的话不一样——跑分只看分不看话。
同理 §6 那条（`followups.py` 把 LLM 带进 `view()`）也是跑分看不见的。
**两样都不是「谁跑得更好」的问题，是「形状对不对」的问题。**
