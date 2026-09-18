# 审架构

本次审的是 **Harness（驾驭层：管理模型上下文、工具、权限、执行、验证和纠正的代码）**，不是金融领域正确性审计，也不是某次回答的评分。

- **主路线：运行时。** 先补保存失败、续跑、上下文恢复、插话入口；不重造领域控制面，不靠加提示词补执行缺口。
- **结论：已有三轮实质吸收，但不能宣称 pi / dsh 的有价值优势已全部兑现。** 不是“只改了接口名”，也不是“上游功能照搬越多越好”。现在最重要的是已有模块之间的行为合同及产品接线。
- **范围：只读源码审计 + 假模型/假工具探针。** 仅新增本报告、复现脚本及交接；不修改 runtime、权限、默认配置，不合并、不部署、不对生产做中断演练。
- **证据标签：** `[实测]` 包括实际读源码及本地机械执行；`[推断]` 是影响或方案判断。下列源码链接均于 **2026-09-18 实际打开正文，状态 VERIFIED**；规格仅证明设计意图，不能证明实现。没有后台审查工具，本报告由当前 agent 完成，不能冒称独立双审。

## 1. 固定对象与上游的一个重要区别

| 对象 | 固定 revision | 被读路径与状态 |
|---|---|---|
| 金融生产源码 | `bf662e9310ff751a4c31763815ee78fb7d6d5122` | `/private/tmp/finance-runtime-audit-bf662e93`，干净 detached 树 |
| pi | `853a80d26c90a14c1886f0ebb8ffaae133ca2185` | `/Users/a77/pi`，已跟踪源码干净，最终 status 干净 |
| dsh | `99f6f02fecdb7dff40c3fbc9470f5907c29f74ca` | 最初读 `/Users/a77/deepseek-harness`，该树仅有他人的未跟踪 `scratch-plugin/`；另建干净 `/private/tmp/dsh-runtime-audit-99f6f02f`，已读的 agent-loop / compaction 源码逐文件相同 |
| 审计产物基线 | `0a1cb8c44aaf2d19ae5f5809bf27119b709b8442` | 独立分支 `baseline/runtime-absorption-audit-0918`；相对生产 revision 的 runtime、services、`api/app.py`、`Composer.tsx` 无差异 |

[实测] 8792 `/api/health` 报 `source_revision=bf662e9310ff…`、`source_dirty=false`、`code_matches_repo=true`、`backend=continuous_glm`、continuous mode 为 on。说明本审计固定的主要源码已部署；**不证明每个特性开关开启，不证明当前研究质量**。[健康接口](http://127.0.0.1:8792/api/health)

### pi 不能只读新 Harness 规格

[实测] pi 的成熟实现是 `Agent` / `agent-loop.ts` 与 coding-agent 的 `AgentSession` / `SessionManager`。与此同时，新 `packages/agent/src/harness/agent-harness.ts` 在此 revision 的 `prompt`、`resume`、`abort`、`steer`、`followUp`、`executeAction` 等方法仍返回 `HarnessNotImplemented`，`create` 发现已有记录也拒绝恢复。

新目录的 reducer、session 等已有实质实现，**不是整个目录都为空**；但不能把完整的 `harness.md` 规格当成已经能执行的全套运行时。以下分别以“成熟实现”和“目标合同”引用，不用后者制造金融 Agent 的虚假落差。

来源：[pi AgentHarness](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/agent/src/harness/agent-harness.ts#L347-L430)、[reducer](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/agent/src/harness/reducer.ts#L506)、[成熟 loop](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/agent/src/agent-loop.ts)、[AgentSession](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/coding-agent/src/core/agent-session.ts)。

## 2. 谁拥有循环

“拥有循环”指执行在本进程，可直接注入控制；“租用循环”指另一 CLI / 服务拥有执行，只能在工具入口设闸。两者不能平均成“都用了 SDK”。

| 路径 | 形态 | 本轮判断边界 |
|---|---|---|
| Workbench `continuous_glm` | **拥有**：`TurnOrchestrator → continuous_turn_adapter → ContinuousAgentEpisode` | 本次重点；名称中的 GLM 是兼容名，适配器可使用不同 provider |
| `sdk_glm` / `sdk_gpt` | **拥有**：SDK 在本进程执行 | 可注入工具与取消；不等同于拥有本仓 Episode 的逐步存储与恢复能力 |
| `codex_headless` | **租用**：外部 Codex CLI | benchmark-only，不能替 Workbench 主线背书 |
| `DshStubRuntime` / `HarnessReferenceLoop` | **拥有测试循环** | 是接缝验证/参考实现，不是已经接入真实 dsh 或 pi 的生产后端 |
| CLI `ask/chat` | 本仓拥有其编排 | 不与 Workbench Episode 合同混同；B 引擎还包含 ownerless 长尾循环，不能一概说全是固定流水线 |

来源：[工厂](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/agent_runtime_factory.py)、[API 装配](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/api/app.py#L494-L578)、[产品正门](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/docs/agent-product-door.md)、[dsh stub](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/dsh_stub_runtime.py)。

## 3. 已经吸收的东西：不能抹掉三轮实质进展

1. **08-15 dsh 接缝吸收**：事件分层、工具阶段管线、EpisodeScope（当前任务权限与上下文范围）、RuntimeHandle（生命周期）、配置与投影。工具授权有实际检查，不只是提示词。
2. **09-02 ResearchHarness 解耦**：金融提示、计划解释、取证结果、终止准入、修复及发布等领域决定，经接缝与 loop 分离；参考 loop 用来检验替换。这里不复述旧文档的方法数，当前以协议和生成的 `docs/runtime/harness-seams.md` 为准。
3. **09-07 runtime-base P0–P4 已合入**：模型可见消息重建、逐步日志与 state、意图/结算、恢复判定、取消原因、inbox 三事实、生成器单步驱动、竞态测试。P4 合入不等于恢复驱动自动完成。

实现来源：[EpisodeScope 与 ToolPipeline](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/episode_scope.py)、[registry.execute](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/research_tool_registry.py#L1148)、[ResearchHarness](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/research_harness.py#L388)、[工单 INDEX](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/docs/superpowers/specs/2026-09-01-workorders-INDEX.md)、[runtime-base 规格](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md)。

[实测] 预算预占、绝对截止、子任务预算不能自造额度、并行结果按模型顺序返回、取消后阻止迟到结果发布，已有代码与针对性测试。金融证据编号、日期口径、来源准入和公开稿发布权仍由领域层拥有；**这部分不能为了追上通用 coding agent 而删掉**。

来源：[工具批执行](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/episode_tool_batch.py)、[子研究预算视图](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/sub_research.py#L68)、[ResearchHarness](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/research_harness.py)。

## 4. 发现项与价值优先级

### F1 · L5 · P0：保存失败继续执行，内容完成与可靠保存没有分清

**反模式：告知不等于行动。**

[实测] `_EpisodeLedger._persist` / `put_state` 失败后将 `_store=None`，记录失败并继续内存执行。现有竞态测试刻意要求 `outcome.status == completed`。探针模拟模型结算保存失败，得到：

```json
{"outcome_status":"completed","durable_phase":"model_pending","restore_action":"retry_model","store_failures":["append#6:OSError"]}
```

这不是“没有记录错误”：内存 finish 有 `store_failures`。问题是磁盘与内容完成语义分离后，恢复读到的仍是待重试意图。[推断] 之后若直接接上自动恢复，可能重复模型费用，或重复允许重放的动作；本轮没有制造真实重复计费。

**建议：** 保留内存草稿，但默认 durable（关键状态可靠落盘）模式遇必需存储失败，禁止新派发，明确“内容已生成/未可靠保存”；已有在途动作按取消与不确定结果规则收口。不必把进度通知失败也升级为致命错误。可选临时模式应事前选择，不能中途悄悄降为临时模式后仍宣称可靠完成。

**已有计划：** `2026-09-08-research-foundation-optimization-design.md` **OPT-08** 已写此取舍，应沿该合同落实，不另起架构。

来源：[ledger](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/agent_episode.py#L295-L386)、[故障测试](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/tests/conformance/races/test_race_store_failure_vs_memory_ledger.py)、[OPT-08](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/docs/superpowers/specs/2026-09-08-research-foundation-optimization-design.md#L226-L237)。

### F2 · L5 · P1：有恢复判定，尚未把计划接成跨进程续跑

**反模式：告知不等于行动。**

[实测] `restore_episode` 已做实际工作：按 state、预留 ID 和结算，返回 `ResumePlan`，或合成取消/中断终态；测试遍历崩溃前缀。这不是空接口。但 `ContinuousAgentEpisode.restore` 仍只是调用它；`manual_drive().step()` 驱动的是当前进程的生成器，不接收 `ResumePlan`，不能重建一个已死进程的生成器局部状态。

全树检查调用方后，Workbench 启动恢复是 `requeue_incomplete_runs → _resume_conversation_run → submit_conversation`，以原用户问题重新提交，而非消费 Episode 恢复计划。同名的 repair `resume` 使用内存 continuation，不能与崩溃恢复混为一谈。

**建议：** 把计划交给实际 driver，恢复模型输入、证据、inbox、消耗预算和未决意图；已结算 ID 不重跑，未知效果只在允许安全重放/有执行方幂等保障时重试。先完成 F1，再启用自动驱动。验收以重启后“不重发已确认工作、预算不重置”而非“能列 open episodes”为准。

来源：[恢复实现](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/episode_restore.py)、[restore/manual_drive](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/agent_episode.py#L1068-L1140)、[启动重排队](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/api/app.py#L2302-L2349)、[P4 原交接的已知边界](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/docs/handoffs/inflight/feat-runtime-base-p4-races-oracle.md)。原交接合入状态已旧，只采其边界，合入看工单 INDEX。

### F3 · L3/L5 · P0：截断回复的停止原因未穿透到工具执行

**反模式：默认开放。**

[实测] 流式 provider 适配器写 `_finish_reason`，但 `_turn_from_message` 不读取它，`ModelTurn` 也没有承载停止原因。探针喂入 `_finish_reason=length` 和语法合法的工具参数，得到：`adapter_error=""`、`tool_calls_released=1`、runner 实际执行、Episode completed。

这里的风险不是 JSON 一定坏，而是**语法合法也不证明模型完整表达了参数意图**。pi 成熟 loop 明确拒绝执行长度截断回复中的全部工具调用，回灌结构化错误让模型重发；其测试专门覆盖“参数合法但内容被截短”。

**建议：** provider 停止原因归一化进入 `ModelTurn` / 事件，拒绝该不完整回复里的调用，再按原因有界恢复；不要把所有错误都变成无条件重试。当前金融受限工具面降低了不可逆风险，本轮不据此声称存在下单或任意写盘漏洞。

来源：[provider 信封](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/llm_refine.py#L1353-L1428)、[转换器](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/glm_agent_runtime.py#L656-L758)、[ModelTurn](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/agent_runtime.py#L116)、[pi 拒执行](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/agent/src/agent-loop.ts#L223-L239)、[pi 测试](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/agent/test/agent-loop.test.ts#L371-L442)。

### F4 · L2/L3 · P1：历史折叠正确保留了引用，但原文回读合同不闭合

**反模式：告知不等于行动。**

[实测] 本仓历史折叠保留近期整批工具结果、E 号与原始 durable 事件，配对不变；这比盲目截断更适合金融证据。它不等于“语义无损”：模型可见的细节已经移除，能绑定 E 号不等于能重新阅读细节。

压缩提示为“需要原文可再查同一工具”；实际同工具同参数被 `_seen_queries` 拒成 `duplicate_query`。探针强制开折叠，前三次查不同 query，第四次回读第一条：`compacted=true`，收到 `duplicate_query`，runner 未再次执行。测试通过只能证明绑定没断，不能证明理解所需的原文可达。

本仓已有 `read_history_result`（历史研究原件）和 `evidence_lookup`（按实体名精确匹配本地索引），**不应笼统宣称“没有任何原文读取”**；但二者不等于通用的本 Episode E 号回读。源码默认折叠开关关闭，本轮没有取得生产进程实际开关证据，故不宣称 8792 当前必遭此问题。

**建议：** 保留去重防空转，给已取回证据一个受预算控制的直接回读入口，或让去重返回已存原结果；不要靠模型改写 query 绕过去重、重新联网取一个可能已变化的版本。绑定仍用原 E 号/内容 hash，回读不是新增证据。

进一步值得吸收：pi AgentSession 与 dsh compaction-basic 都有按上下文压力触发、窗口溢出分类、压缩进展判据及有限重试。本仓此折叠模块主要按批次年龄处理，不能视为完整的上下文溢出恢复系统。

来源：[折叠模块](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/episode_history_compaction.py#L33-L43)、[去重](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/episode_tool_batch.py#L560-L584)、[工具定义](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/research_tool_registry.py)、[pi 压力/溢出](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/coding-agent/src/core/agent-session.ts#L2106-L2229)、[dsh 压力/溢出](https://github.com/deepseek-ai/deepseek-harness/blob/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca/packages/compaction/compaction-basic/src/index.ts#L134-L230)。

### F5 · L5 · P1：子研究有预算与证据汇总，缺独立可靠事件存储

**反模式：告知不等于行动。**

[实测] `ContinuousSubResearchWorker.run` 创建 `ContinuousAgentEpisode` 时不传 store；完整事件只存在于 outcome，转成 `BranchResult` 后保留证据、调用量、批次账等摘要，未保留整条可恢复流。不能说“没有子研究”或“没有父子关联”：它们都有，父子预算共账也有；缺的是父子整棵运行树的恢复闭环。

[推断] 深研究中断后，父恢复仅凭汇总难以保证精确认领已经完成的分支。建议沿 OPT-08 建独立子 episode 存储引用，继承取消/预算约束，不把所有子事件塞入父正文，不复制父完整上下文。

来源：[worker](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/continuous_sub_research.py#L52-L107)、[协调器](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/sub_research.py)、[生命周期边界](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/runtime_handle.py)。

### F6 · L5/L6 · P1：插话底座与 CLI 已有，日常 Workbench 未兑现同等体验

**反模式：告知不等于行动。**

[实测] inbox 已有 `next_step` / `next_turn`，并记录 inserted / claimed / discarded；CLI `steer` 可投递 spool、等待回执、列 open episodes。成熟 pi 也区分 steering（下一步改变方向）与 follow-up（本轮结束后再处理）。

Workbench 的 `Composer.submit` 在 `running` 时直接 return，按钮切为停止；不是运行中插话入口。全树调用检查也没有发现 API 把该输入接到 episode inbox。`wakeup` 在当前实现中只记账，不实际唤醒。

**建议：** 产品层明确“改变正在做的事”和“做完再补一题”两种动作，返回真正的投递/认领回执，权限仍由领域准入检查；消息确认后不能因重启丢失。普通追问卡片不是这个能力。

来源：[inbox](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/episode_inbox.py)、[steer CLI](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/cli.py#L5063-L5150)、[Composer](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/webapp/src/components/Composer.tsx#L55-L58)、[pi 队列](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/coding-agent/src/core/agent-session.ts#L1388-L1450)。

### F7 · L3/L4 · P2：扩展新工具前，副作用属性应显式且保守

**反模式：默认开放。**

[实测] 本仓 `ToolSpec.replay` 默认 `safe`，批次执行没有逐工具 parallel/exclusive 声明；已有 capability 和 `io_effect` 约束，`local_only` 拒绝未知 IO，不是全盘默认开放。dsh 工具调度有有限并发、独占屏障、启动前重判模式与按模型顺序结算。

[实测] 工具面也不能简单说成“绝无写入”：`save_history_research` 会保存受限研究产物，注册时沿用 `replay=safe` 默认；执行侧已有 case transaction、同内容返回 unchanged 和版本冲突检查。因此本轮不把该工具直接判成“必然重复写入”，但安全声明应显式指向这些保障，不能靠新作者记住默认值。[历史产物保存实现](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/historical_research/episode.py#L720-L795)

[推断] 在当前受限研究工具面，缺独占声明不是最急的生产漏洞；一旦扩大插件/外部写入面，默认 safe 及“全都能并行”会放大风险。届时应默认未知不可重放/不可并行，逐工具认证；不能以“想吸收全部优势”为由直接开放任意 shell、联网写库或下单。

取消也有不同取舍：dsh 等已启动 Promise 结算后到边界；本仓为及时返回采用取消信号与发布守卫，Python 线程不等于已被强杀。不能只因两边都有 `cancel` 就声称外部工作停止语义相同。

来源：[ToolSpec](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/research_tool_registry.py#L885-L942)、[本仓派发与取消](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/runtime/episode_tool_batch.py#L735-L825)、[dsh 调度](https://github.com/deepseek-ai/deepseek-harness/blob/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca/packages/core/agent-loop/src/tool-calls.ts#L185-L245)。

## 5. 六层判定、约束三筛与独立验证

以下“通过”仅指本轮被查的运行时范围，不是全仓安全认证。

| 层 | 判定 | 理由 |
|---|---|---|
| L1 提示词 | 通过 | 工具行为契约与结构性能力/预算检查分层；金融解释权留在 ResearchHarness。未做前缀缓存命中效果审计 |
| L2 上下文 | 缺口 | F4：折叠后可引用不等于可回读；尚未据此证明完整压力/溢出恢复 |
| L3 工具 | 缺口 | F3 截断调用放行；F4 去重与回读冲突；F7 扩展默认属性 |
| L4 安全 | 缺口 | 已有 capability/IO 硬门应保留；F7 重放/并发默认值需在扩展前收紧，不声称本轮发现越权写生产 |
| L5 韧性 | 缺口 | F1/F2/F5/F6：失败合同、续跑驱动、子树持久化、产品插话 |
| L6 可观测 | 通过 | 逐步事件、provider/工具收据、预算与失败原因、健康 revision 均有；不等于独立质量验证通过 |

**约束三筛：** 判断约束在保可靠性下限，还是限制强模型发挥。

- 能力授权、预算先占、绝对截止、来源/日期/内容身份：**保下限**；模型更强也不能凭空拥有权限或过去的数据。
- 受限工具边界（研究产物保存不等于任意写入）与子研究不持最终发布权：**保下限**；不因复制 coding agent 特性而放开。
- 成功 query 永久去重：防外呼死循环这半是**保下限**，但把“读取已存结果”也拒掉是**封上限**。改写为拒重复外部执行，而不是拒读已有证据。
- 整批配对与近期尾段保留：**保下限**；固定批数作为唯一内存策略会限制长研究，补按需回读与压力策略，而非撤销配对保护。
- `admit_finish` 的证据绑定完整性：**保下限**。语义删句/成稿规则是否误伤属于另一项领域审计，本轮没有把它包装成已验通过，也不建议借 runtime 改造之名加更多输出模板。

**生产公式后三项：约束=有；验证=有；纠正=有，但纠正的产品闭环不完整。** 不是模型笨，也不是所有层都缺席。

**独立验证：** 运行时授权与参数检查消费结构化调用；发布侧有确定性检查与可配置 LLM 判官。API 将同一个 `GLMModelClient` 作为 primary_judge 注入，另一次调用不保证不同模型/信源；本轮没做盲评或跨模型效果验证。以上测试是机器检查合同，不是让实现模型给自己的金融答案打高分。

来源：[API verifier 装配](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/api/app.py#L579-L582)、[判官模式](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/judge_mode.py)、[语义验证](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/bf662e9310ff751a4c31763815ee78fb7d6d5122/intelligence/services/episode_semantic_verifier.py)。

## 6. 建议的炼化方式，而非把两套框架一起塞进来

[推断] 继续自有 runtime + 稳定 ResearchHarness 接缝，比立即整体迁移更合算：领域契约、预算、证据和修复已深度接线；pi 新 Harness 执行层尚未完成，dsh 整体引入还涉及 TypeScript/Python 桥、生命周期与运维。整体替换只有在同模型、同工具、同预算的实测明显获益时才值得承担迁移成本。

| 方案 | 取舍 |
|---|---|
| 继续按行为合同吸收 | **推荐**：保住金融领域所有权；需要自己维护明确挑选的运行时能力 |
| 整体换成成熟 pi / dsh | 可减少部分通用循环维护，但需要迁移领域桥、取消/预算/恢复语义；不能只看 demo |
| 两套框架与自有底座同时叠加 | 不推荐：多份状态、调度和恢复所有者容易打架 |
| 继续加提示词解释当前缺口 | 不推荐：提示词不能修复保存失败或唤醒执行者 |

优先次序：

1. **P0：F1 保存失败合同、F3 停止原因贯通。** 可分区提交，但都属同一运行时路线。
2. **P1：F2 跨进程 driver + F5 子树引用；F4 原文回读/压力管理；F6 Workbench 插话。** 恢复 driver 不得先于失败语义接通。
3. **P2：F7 安全属性；按真实需要引入会话分叉、供应商拓展或插件生命周期。** pi 的会话树确有价值，适合从相同证据尝试不同假设；不等于必须先复制 coding UI、shell、主题及所有插件生态。
4. **验收：同一领域合同、同模型、同冻结数据/工具输出、同预算的对照。** 分开统计研究交付、成本、耗时、恢复成功、重复派发、丢消息与原文可达；没有产品级证据的能力标“实现/待接线/待验”，不要给没有分母的“炼化百分比”。

pi 会话树来源：[SessionManager](https://github.com/earendil-works/pi/blob/853a80d26c90a14c1886f0ebb8ffaae133ca2185/packages/coding-agent/src/core/session-manager.ts#L1261-L1485)。这里提出按需借鉴，不把它误写成金融仓已有的情景树或子研究就是同一种对象。

## 7. 检查、收据与可复现步骤

### 已执行

**A. 干净生产源码快照的针对性测试：**

```bash
cd /private/tmp/finance-runtime-audit-bf662e93
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_store.py \
  intelligence/tests/test_episode_restore.py \
  intelligence/tests/test_episode_messages.py \
  intelligence/tests/test_episode_inbox.py \
  intelligence/tests/test_episode_steer.py \
  intelligence/tests/test_episode_history_compaction.py \
  intelligence/tests/test_episode_history_compaction_loop.py \
  intelligence/tests/test_runtime_handle.py \
  intelligence/tests/test_research_harness.py \
  intelligence/tests/test_sub_research_tool.py intelligence/tests/conformance
```

**263 passed, 3 skipped, 1 xfailed，12.91s。** 日志 `/private/tmp/runtime-audit-tests-bf662e93.log`；收据 `/Users/a77/.finance-runtime/test-receipts/20260918T065717Z-bf662e93.json`。skip/xfail 不能当已通过。

**B. 补充工具批次、适配器、折叠接线与保存失败测试：** 90 passed，2.03s；日志 `/private/tmp/runtime-audit-extra-tests-bf662e93.log`；收据 `/Users/a77/.finance-runtime/test-receipts/20260918T070538Z-bf662e93.json`。A/B 有重叠，不加总为唯一测试数量。

**C. 三个反例：** `scripts/audit_runtime_absorption.py` 是观察脚本，不把当前问题行为钉成正确合同；脚本使用现有测试夹具，存储全在内存。最初探针及输出在 `/private/tmp/runtime-audit-probes-bf662e93.{py,json}`；仓内脚本去除了噪声时间字段并恢复环境变量，已在固定被审树复跑，三个观测一致，输出 `/private/tmp/runtime-audit-probes-final-bf662e93.json`。脚本 Ruff 与 `git diff --check` 通过。可在固定被审树运行产物分支里的脚本：

```bash
cd /private/tmp/finance-runtime-audit-bf662e93
PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  /private/tmp/finance-runtime-audit-report-0918/scripts/audit_runtime_absorption.py
```

### 未执行与不能推出的结论

- 没有 paid/live 模型对照、真实浏览器用户验收、生产 kill/restart、外部工具取消排空演练；不能说金融研究效果超过 pi/dsh 或三轮改造前。
- 没跑全仓 Python/前端/E2E 等价 CI；本轮不合并，不拿针对性检查充当合入门禁。
- 没安装上游 JS 依赖、没跑 pi/dsh 全测试。上游行为结论来自固定源码及其测试正文，不冒充上游测试本轮已绿。
- 未确认生产历史折叠开关，不把潜在反例说成已发生的生产事件。

## 8. 成立条件与留给接手者的提醒

- `tree=/private/tmp/finance-runtime-audit-bf662e93`；`revision=bf662e9310ff751a4c31763815ee78fb7d6d5122`；两批测试 `dirty=false`。
- `interpreter=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13；使用专用依赖环境，没有用宿主 python 跑 pytest。
- 正门：`AGENTS.md`、用户偏好、项目笔记、能力图谱、`docs/agent-product-door.md`、08-15 吸收 / 09-02 解耦 / 09-07 runtime-base 规格与工单 INDEX、09-08 OPT-08。
- 负面断言已经做全树同义检索及正门核对，结论限定到上述固定路径；不根据一个猜错路径的 ENOENT 下结论。
- `design_ssot=verified`：从 `harness-reference gitea/main@62debded014aac5c9ab6e57efd39776bf31e9ec7` 读取 `DESIGN-stack.md` 与 `PLAYBOOK.md` 约束三筛。代码地图在新 detached 树为 empty，只利用正门命中，未用空结构图作证。
- 原工作树 detached `b4a35fa2` 的他人未跟踪产物未碰。审计产物独立，不覆盖他人的 `inflight/HEAD.md`。
- 本报告是固定版本发现清单，**不是第二份常驻能力图谱**。未来修复后应更新权威能力图谱与对应交接，不凭本报告的历史结论继续说“还没做”。

工具沉淀盘点：三反例已从临时脚本归档到 `scripts/audit_runtime_absorption.py`，不只留聊天。当前是项目夹具驱动的观察工具，尚不是通用门禁；只读审计不擅自改变旧失败合同或变异 runtime。通用失败形状已由 agent-memory 的 `contract-vs-delivery-mismatch`、`kept-history-is-not-replayable-history` 覆盖，不另造知识清单。`harness-reference` 工作树有他人未提交 `BUILD.md` 且 HEAD 落后其 `gitea/main`，本轮不碰它的目录，只读权威提交。

可迁移知识点：**函数存在 ≠ 产品可达 ≠ 故障时仍成立 ≠ 效果提升。** 本次三个最小反例的共同点是：单模块测试可以全绿，而生产需要的是模块交界处的一致合同。优先用假模型与确定性工具压接缝，再把昂贵真实模型留给质量与收益验证。
