# 金融 Agent：产品门 / 两条引擎 / 积木

评接口深浅、找「入口」、宣称「我们没有 X」之前读本页。
能力有哪些节点仍以能力图谱为准，本页不抄工具表、不写死个数。

**深模块** = 调用方每学一单位接口能驱动多少行为。接口包括签名、不变量、必须知道的配置。数参数个数当深浅，会把测试旋钮当成生产门。

## 先分四层，不要压成一句「架构」

| 层 | 人话 | 代表物 | 是不是门 |
|---|---|---|---|
| **产品门** | 人/UI/脚本真正走进来的地方 | 见下一节 | 是 |
| **引擎** | 进门之后怎么跑一轮研究 | A 连续 Episode；B 写死流程 `answer_query` | 不是门 |
| **组装** | 把零件接到引擎上 | `GLMAgentRuntime`、`episode_factory.build_episode_context`、`episode_tools`、`default_registry` | 不是门 |
| **积木** | 引擎内部的零件 | `ResearchToolRegistry`、`llm_refine`、`perspective_lab`、数据块注册表 | 不是门 |

删掉积木，复杂度会散到每条引擎；删掉门，人会找不到入口。两件事不要混着打分。

## 产品门（当前该走的入口）

| 谁 | 走哪扇门 | 合同 |
|---|---|---|
| 人 / 编码 agent 一次性提问 | `python3 -m intelligence.cli ask "<问题>"` | 默认只收问题字符串；`--wiki-rag-mode` 等是逃生口 |
| 同一会话追问 | `python3 -m intelligence.cli chat` | 首轮仍是 ask 管线 |
| 显式要模型自己选工具 | `python3 -m intelligence.cli agent` | opt-in，默认不影响 ask/chat |
| Workbench 对话 UI | `POST /api/conversations` → `TurnOrchestrator.run_turn` | 有 `conversation_id` / `run_id`；不要用 CLI 冒充这套 id |
| 复盘写入（另一条面） | `python3 -m market_feature_store.cli daily-full` | 飞书 Bitable 写入已退役 |
| 飞书 IM（已退役，不是门） | `python3 -m intelligence.cli feishu-bot` | exit 2，不连 WebSocket。与 Bitable 写入退役是两件事 |

编码任务「仓库里有没有现成实现」走 `python3 scripts/code_map.py query "<问题>"`，不是本页，也不是问答门。空图不得写成架构结论。

### 历史发现研究

入口仍是 Workbench 对话，例如「这一波农业怎么走出来的，找出值得检验的特征」→「以前有没有类似，失败案例也看看」→「把观察窗口改成……」。`TaskFrame.history_intent` 区分事后发现与历史比较，随 `TurnIntent` 跨轮传递；普通概念解释与明确取消历史研究不会继承该权限。用户明确限定日期时，历史计算、普通结构化查询与原件读取共用范围门。

`historical_research` 是引擎 A 上的领域应用：有类型 `history_query` 负责精确代码的日轴、受支持的时间特征、类比及声明窗口全集比较；`read_history_result` 读取原件；`save_history_research` 保存候选、失败与修订。它们复用 `finance_query` capability，预算、工具循环与取消仍由 Episode 管理。完整分母与模型预览分离，原件只经 RunStore 写入；案例修订与普通取消/产物写入均有并发保护。

当前结果均是探索研究：相似案例不等于独立验证，重叠窗口不当作独立样本；不支持的组合定义明确返回缺口。L2、晚间卖方与晨汇未同步目标范围为 `pending_sync`，没有安排同步。严格时点认证、样本独立性与正式方法晋升继续消费基础评价器合同；本工具不颁发认证。

实现和分期验收见 [历史发现 spec](superpowers/specs/2026-09-09-historical-discovery-research-design.md) 与 [执行计划](superpowers/plans/2026-09-09-historical-discovery.md)。部署状态以运行服务 `/api/health` 的 revision 为准，仓内存在代码不等于线上已更新。

## 两条引擎（调度器后面）

一个调度器（`conversation_orchestrator` / `TurnOrchestrator`）+ 两条引擎。两条都调 LLM，差别是**流程谁定**：

| 引擎 | 实现 | 何时用 |
|---|---|---|
| **A**（Workbench 生产默认） | `continuous_turn_adapter` → `ContinuousAgentEpisode` | 模型按契约自选只读工具 |
| **B** | `ask.answer_query` | CLI `ask`/`chat` 的固定管线；Workbench 里两种情形（见下） |

**B 在 Workbench 里接两种题，别只记住第一种**（2026-08-30 修正，此前本行写「仅三条确定性题型」，三处都已漂）：

1. **确定性题型 → D 块流水线**：`DETERMINISTIC_OWNER_TYPES` 实为**五条**——`external_market` / `dated_market_review` / `market_watch` / `watchlist_digest` / `disclosure_scan`（`continuous_turn_adapter.py:111`，个数以该常量为准，勿写死）。**`quick_fact` 已被明确移出**（`:108`，R-20260828-05：排名/过滤/区间取值必须进 episode 才碰得到 `finance_query`）。
2. **ownerless 长尾 → `generic_research_owner` 循环**：`research_task_contract` 非空时 `_answer_query_impl` **整条早退**、D 块一次不跑（`ask.py:3055-3059`）；契约只在 `conversation_orchestrator.py:2809` 设上，条件是「研究题 + 无专属椅子」（`:2245`）。这一条是 `run_agent_loop`，**不是写死流程**——把 B 整体说成「写死流程」会把它接长尾的能力漏掉。

A 与 B 的门禁不对等：语义判官（`episode_semantic_verifier`）、结构门、修复轮**只在 A**；B 有 `gate_receipt` / `CompletionReport` / `evidence_judge` / 输出质检。差的成因是分层——判官在 `runtime/`，B 在 `services/`，不得反向 import。现状与并轨计划见 `docs/superpowers/specs/2026-08-30-engine-b-into-a-strangler-design.md` §1.3。

不要把 `ask.answer_query` 写成「金融 Agent 的唯一深模块」。它是引擎 B。也不要为「少学零件」再加 `answer_door` / `EpisodeBuilder`：组装已经在 `GLMAgentRuntime` 和 `episode_factory`。

### 生产里谁在拼 `AskOptions`（为什么不加 `answer_door`）

不含测试。再加一层 `resolve_answer_door(query)` 通不过删除测试：删掉它，调用方仍要自带策略字段。

| 调用方 | 怎么进 | 是不是「只传 query」 |
|---|---|---|
| `cli ask` | `AskWorkflowOptions` → `run_ask` → 再填 `AskOptions`（浅拷贝还在） | 否，经 CLI 默认填充 |
| `cli chat` / `cli agent` | 直接 `AskOptions` | 否 |
| 飞书 IM | `feishu-bot` **exit 2**；文件里还留着 `_run_ask_workflow`，`run()` 到不了 | 已退役，不是门 |
| `research_owner.py` | 直接 `AskOptions`，带 `compose` / `deadline` / `question_type_override` 等 | 否，策略调用方 |
| Workbench `app.py` `_run_ask` | 直接 `AskOptions` + `answer_query`，走 run/store | 否，UI 合同 |

问金融问题走上一节 CLI `ask`；问「仓库里有没有现成实现」走 `python3 scripts/code_map.py query`。仓库里没有第四套 Python `answer_door`。真浅的若还要收，是删掉 `AskWorkflowOptions` 那次字段拷贝，不是再加转发。

## 积木（常见误判）

这些可以很深，但**调用方不是人，是引擎**：

- `ResearchToolRegistry`：授权、参数规范化、同 key 只跑一次、截止日期过滤。不是 `{name: runner}` 字典。超时/重试在 Episode 批次循环，不要搬进注册表（`services/` 不得 import `runtime/`）。
- `llm_refine`：传输（重试/流式/预算）+ 任务提示词焊在一个文件。不要合成万能 `generate(task_type)`。
- `perspective_lab.active_runtime_prompt`：视角注入门。模块里还有路径 helper，不要把整文件当成四方法闭环。
- 数据块（D0/D6/D9…）：意图门控在块自己的 `applies()`。调用方若要关某一块，只传 `AskOptions.enabled_providers`（或 `evidence_registry.without_providers(...)`）。**不要**再给每个块一个 `include_*_block`。

`force_moneyflow_block` 是「日报强制取 L2」，不是允许开关，仍留在 `AskOptions`。
`include_scenario_guidance` / `include_track_guidance` 是表达契约，不是数据块。

## 失败形状（本页要挡住的）

对着积木的公开方法数打「浅」、建议再包一层工厂、建议把超时重试塞进注册表——都是把积木当成了门。先问：调用方是人、是调度器、还是引擎内部？

把 `feishu-bot` 当问答正门，或把「飞书 Bitable 写入已退役」写成连 IM 长连接也没了——两扇门不是同一件事。IM 入口现在 exit 2。
