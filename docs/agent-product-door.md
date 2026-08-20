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

编码任务「仓库里有没有现成实现」另走代码地图 spec，不是本页，也不是问答门。

## 两条引擎（调度器后面）

一个调度器（`conversation_orchestrator` / `TurnOrchestrator`）+ 两条引擎。两条都调 LLM，差别是**流程谁定**：

| 引擎 | 实现 | 何时用 |
|---|---|---|
| **A**（Workbench 生产默认） | `continuous_turn_adapter` → `ContinuousAgentEpisode` | 模型按契约自选只读工具 |
| **B** | `ask.answer_query` | CLI `ask`/`chat` 的固定管线；Workbench 里仅 `external_market` / `quick_fact` / `dated_market_review` 三条确定性题型（`DETERMINISTIC_OWNER_TYPES`） |

不要把 `ask.answer_query` 写成「金融 Agent 的唯一深模块」。它是引擎 B。也不要为「少学零件」再加 `answer_door` / `EpisodeBuilder`：组装已经在 `GLMAgentRuntime` 和 `episode_factory`。

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
