# 审架构

对象：金融 Agent Harness（驾驭层）的约束归属与 P1 迁移契约，不是某道金融题的修补，也不是 Pi 压缩实现审计。

**结论：认可“代码守边界、模型管解释”的方向；v0.1 可作为方向稿，但还不能直接作为实施合同。** 需要补足四处：建议身份贯穿消费者、PLAN 真正允许放弃自己的计划、原请求身份与解释版本分离、旧正文校验退出哪些裁决权。下面给出一个 P1 切片建议，不另写一份竞争总架构，不修改并行 owner 的 spec。

- 主路线：**控制面**——明确“谁的要求、谁能修改、哪些消费者执行”。反路线是继续加关键词/题型例外/措辞提示，或把工具目录、预算和传输同时改掉。
- 产品源码、测试、配置均未改。原输出身份窄修复保留；原正文反例仍阻塞合入/发布。新增真实模型请求 **0**，未推送、合并或部署。
- 被审 v0.1：`~/fwp-wt-harness-simplification-1002/docs/superpowers/specs/2026-10-02-model-owned-harness-spec.md`，固定文档提交 `acc743c84`；其已核产品基线为 `3b78fda25`。
- 本轮源码/离线探针：`~/fwp-wt-owner-output-contract-1002`，固定 `6ef1d41e95790bc20f7b3a2c79db7bed38ea66c9`。**两个补丁栈不同，不互签验证收据。**

## 1. Knevo 参考边界

已读私有原始存档 `agent-memory/60_dialogues/knevo/2026-08-08-工具编排与step上限-44轮原文.md` 的 `load_skill` 记录与 finance-mode 段（约 L1350 起）。其中也有检索、来源、时间顺序、工作流等纪律，不是“没有规则”。

这些资料是对话、自述与部分工具观察，不是源码；不能认证它有哪些代码强制门，也不能比较规则总数或推出“少规则所以更强”。并行减法审计（`~/fwp-wt-harness-simplification-1002/docs/verification/2026-10-02-harness-simplification-review.md`）已撤回“我们自动门更多所以领先”的推理，本轮不反向神化另一方。

借鉴的是设计方向：计划可调整、工具/方法按需取、来源纪律明确、资料不足仍可有边界地回答。不是照抄技能数量、阈值或路由表。

## 2. 便宜的反例足以停止补词表，不足以认证替代方案

私有收据根：`~/.finance-runtime/reviews/knevo-takeover-20261002T140000Z/`。全部为作者标注的构造数据、局部函数入口，不是 Workbench HTTP 验收或独立质量评分。

### 2.1 复跑原会话的 21 个跨任务样例

`cross-task-seam-probe.py` → `cross-task-seam-result.json`。覆盖市场判断、定义、财务比较、风险、复核时点及空答/缺来源控制；没有往产品识别词表加入这些句子。

| 观察 | 数量 | 能说明什么 |
|---|---:|---|
| 与作者预期一致 | 8 | 包括空答、缺来源的拒绝控制，不是所有输入都被放过 |
| 错误内容被当成 fulfilled | 9 | 否定、错主体、错时段、错指标及仅边界文字等，词面仍相似 |
| 正确表达被判缺 | 4 | 两个改写；风险与复核时点的原句缺指定标记词 |

[实测] 新旧 `rows`、源码哈希、探针哈希完全一致。`task_fulfillment::_claim_text_present` 的词面代理不能保证语义正确；`answer_spans` 返回的是 claim 文本，不一定是公开稿中的字面片段。后者不能被下游当作已定位到正文的见证。

**9/21 和 4/21 不是产品误判率。** 这些有意构造的反例只否定保证，不估计总体分布。该门主要用于旧管线/专项 AnswerSpec 路径；连续 Episode 的结构/语义门是另一条链。这里没有证明整条产品链会放过每个反例，更没有证明删门后质量会提升。

### 2.2 把真实 verdict 喂给补写与缺口投影消费者

`optional-consumer-probe.py` → `optional-consumer-result.json`。仅替换 `llm_refine.synthesize_messages` 为固定返回，真实运行 `evaluate_answer_spec_fulfillment` → `repair_unfulfilled_answer`，另直接检查 `fail_closed_answer_spec`；没有自己捏造 verdict。

[实测] `direct_definition` 必需，`counterpoint` 可选：

1. 定义已交付、只缺可选项时，顶层判定仍是 **complete**。不能说 `required=False` 完全失效。
2. 定义也缺失时，`FulfillmentVerdict.missing_required` 同时返回必需项和可选项；它只按 item 状态筛选，item 本身没有 required 信息。
3. 补写函数据此生成“全部必需输出”的反馈，可选的反方分析也被点名必须补。
4. 固定模型只补定义，重验仍 **complete**，说明重验尊重可选性；风险在反馈误导，不是可选项必然否决终局。
5. 单独调用失败投影，可选项也进入“问题所需的直接回答”缺口文字。这是直接消费者观察；不声称本例成功补写后又触发了失败投影。

来源：`task_fulfillment.py::{FulfillmentVerdict.missing_required,evaluate_task_fulfillment,fail_closed_answer_spec}`；`ask_synthesis.py::repair_unfulfilled_answer`；`llm_refine.py::fulfillment_revision_user_content`；调用者 `conversation_orchestrator.py` 约 L3718–3786。

[推断] 若 P1 仅增加 origin 或将更多槽改成可选，旧消费者仍能把建议说回义务，造成额外补写或错误缺口。应以“真实生产者→真实消费者”验证身份保真，而不是只测新字段能序列化。

## 3. v0.1 的四项实施阻塞

### A. 义务来源不能止于装配器

`episode_factory.py::build_episode_context` 已有 advisory / 本次 forward-slot 可选实践；`episode_verifier.py::verify_episode_outcome` 也区分必需项缺失和可选 gap。不能重造这些能力。

但另一条投影 `conversation_orchestrator.py::_task_frame_required_output` 总构造 `required=True`；`_merge_frame_outputs` 和专项 owner 转接处又从字符串 ID 还原要求。加上 §2.2 的反馈信息损失，P1 需要覆盖：

```text
要求来源 → frame/contract 投影 → 当前提示与完成判定
                         → 缺口反馈 → 公开交付/持久化报告
```

**建议补入 v0.1 §3.3、§9、P1：** origin、有效必需性与请求对应关系不可在别名/owner/旧适配器中丢失；未采用建议不进入“欠用户”的缺口或补写指令。用户明确子问仍保留未答状态，不得因为删了一个系统槽就自动宣称已答。

### B. 现有 PLAN 能修订，但自己的清单只能增长

[源码] `research_plan.py::validate_plan_revision` 要求任务 ID 不变、revision 递增，同时禁止删除旧 `answer_elements`、`branch_goals`；perspectives 可标 `not_relevant`，但也不能直接删除。`FinanceResearchHarness.interpret_plan` 调用该验证；`ContinuousAgentEpisode` 记录 PLAN 并据此请求深度/子研究，却不据它改写 TaskFrame/要求合同。

这不是“没有计划”，而是**计划修订不等于任务解释修订**。复用 PLAN 的同时若不处理单调增加规则，模型连自己走错的一步也不能撤回。

**建议补入 v0.1 §4、P1：** 允许放弃/替换模型自拟的分析项，保留简短原因；用户原始要求仍独立保存。对已经派出的分支，撤计划不删除执行历史或免除费用/取消义务。先不改分支数量、调用帽或修复次数。

### C. TaskFrame hash 当前兼任不可变身份，不能现场直接 rebase

[源码] `TaskFrame.task_frame_hash` 哈希覆盖目标、题型、输出等字段；`_EpisodeLedger` 在启动时保存它，并写入每条事件。`AgentOutcome.__post_init__` 检查首事件与 outcome 哈希一致；`episode_verifier` 对合同/outcome 做同值检查。

`EpisodeState` 已有授权、证据、预算和入口快照，不是需要新造存储；但 `EpisodeAuthorizationSnapshot` 当前只接受合同版本 `1`，恢复要求合同/策略/目录精确匹配。它不是仅比权限集合。

[推断] 循环中直接 `rebase_task_frame`，然后只替换某处 hash，会出现旧事件、新提示、旧恢复快照的分裂；重新调用初始 `build_episode_context` 也不能作为修订实现，它会重新装配 deadline/资源上下文。

**建议补入 v0.1 §4.2、§10、§13：** 明确区分请求锚点、解释 revision 与存储格式版本，并同时规定派发、验收、恢复读哪一版。不能靠取消 hash 检查“支持修订”。建议方案见 §6。

### D. “结构通过”与“语义正确”需要明确旧门退出表

v0.1 §7 已说结构检查不能证明全文正确，但 P1/P3/P4 的责任仍可能被读成“先把旧门全保留，最后再说”。§2.1 已证明旧门并非可靠语义裁判。

**建议补入 v0.1 §7、P1/P3 的分界：** P1 就要让建议缺失失去阻断/驱动补写的权力；不能延后到 P3 才实现 P1 的验收条件。词面覆盖、marker 和 claim-to-prose 相似性若保留为诊断，应显式 observation-only，不能据此签“语义正确”。哪些旧拒收路径退出、哪些完整性拒收保留，写入同一切片计划。

这不是现在把 `complete` 放宽或全部关闸。原语义反例仍是正常失败测试；替代方案尚未验证，原身份补丁依然不可发布。

## 4. 谁拥有循环与六层巡检

按参考清单的口径，“拥有”包括 SDK 在本进程内运行、可注入控制；不等于每个状态转换都由我们编写。

| 后端/引擎 | 循环形态 | 证据 |
|---|---|---|
| `continuous_glm`（provider-neutral，名字是历史兼容名） | 拥有 | `glm_agent_runtime.py::GLMAgentRuntime` → `ContinuousAgentEpisode` |
| `sdk_glm` | 拥有：SDK 在本进程 | `openai_agents_runtime.py` 构造工具/上下文并 `Runner.run` |
| `sdk_gpt` | 拥有：SDK 在本进程 | 同上；另有单工具响应适配，不能假设与自建 loop 行为完全相同 |
| `codex_headless` | 租用 | `codex_headless_runtime.py` 的外部进程/网关；benchmark-only，不属本轮开启范围 |
| 固定 `answer_query` 引擎 | 拥有固定流程，不是自主循环 | `docs/agent-product-door.md`；不能用 CLI ask 代替 Workbench 会话合同 |

| 层 | 本次判断 | 证据与范围 |
|---|---|---|
| L1 提示词/约束 | 缺口 | 题型/系统建议升级为必需槽；marker 限制表达。稳定指令与动态输入已有拆分，缺的不是再堆提示 |
| L2 上下文 | 缺口（覆盖证据未齐） | 工具观察预算、registry 限长和历史折叠已存在；本轮没逐入口证明聚合上限/子研究卫生。折叠为开关路径，不能说默认全启，也不能据此诊断 R19 超时 |
| L3 工具 | 通过（已查授权与参数入口） | `ResearchToolRegistry.authorized_specs/prepare/execute` 从同一注册表读取；新按需目录尚非本轮验收范围 |
| L4 安全 | 通过（已查调用前边界） | `authorization_denial` 在 runner 前检查 capability/材料 scope；local-only 的未知 IO 不放行。没有做完整安全审计 |
| L5 韧性 | 缺口 | 已有有界补写、重验、Episode 修复/恢复；但建议混入必需反馈，误判会指导模型修错。不能描述成“没有纠正路径” |
| L6 可观测 | 缺口 | 已有原因码、事件、模型/派发意图与持久化状态；建议来源在消费者链丢失，`answer_spans` 不是必然的正文位置。不是“没有日志” |

发现项：L1 **行为硬编码**（题型/措辞决定交付门）；L5 **行为硬编码**（错误的必需反馈）；L6 **告知不等于行动**（记录了新解释/建议不证明消费者采用）。L2 的未证范围是审查边界，不作为缺少预算实现的负面断言。

生产公式后三项：**约束=有，验证=有，纠正=有；职责与可靠性仍有缺口。** 不能用它们“存在”或旧单测绿签整体架构通过。

独立验证：本轮评分者就是本评审作者，读取源码、构造的 claim/source/公开正文及返回结构；无隔离评审者、无真实模型作答。复跑只是可重复，不是独立互证。

## 5. 约束三筛：保留什么、减少什么

| 已有约束 | 判词 | 改写方向 |
|---|---|---|
| 可信用户原题、明确请求与材料归属不可被模型覆盖 | 保下限 | 继续保存原件与来源；歧义请求澄清，不用新词表替用户确认 |
| capability/read scope、根截止、调用帽、取消 | 保下限 | 调用前守住；语义修订不能授予或刷新 |
| 引用存在、证据身份/日期/集合口径、假设与事实区分 | 保下限 | 保留机器可查部分；不把存在 ID 等同于支持整句 |
| 启发式题型自动生成不可撤销槽 | 封上限 | 变成模型可拒绝/调整的建议；不得删用户要求 |
| PLAN 自拟分析项只能增加 | 封上限 | 可撤回计划，保留执行账与用户任务；不增加修订预算 |
| marker/词元重合认证“正文已回答且有据” | 封上限 | 移出语义认证权；诊断与全文复核分账，不加否定词白名单 |
| 因未完成项投影为缺口 | 拦输出但可改写成拦输入 | 先隔离不合法来源与权限；建议不驱动整篇降级，能交付的部分诚实保留。现函数已保留带引用事实/公司，不能说它总清空全部数据 |
| 单轮补写必须重验且计入同一账本 | 保下限 | 保留有界纠正；只反馈真正未满足的用户义务/完整性问题 |

事实结构与口径定义不是应删的“硬规则”。强模型同样需要它们；这次减的是代码对任务解释与表达的过度管辖权。

## 6. P1 切片建议：只推进语义权限，不重写整套执行系统

以下是**待并行 spec owner 采纳的实施建议**，不是已生效的协议或完整施工计划。

### 6.1 唯一在线入口：复用 PLAN

- `PLAN` 承载可选的解释修订提案；`FinanceResearchHarness` 做纯校验，当前 Episode owner 串行应用。不加一个每题必调的规划服务/模型回合。
- Controller / alignment 保留初始解释建议；`rebase_task_frame` 可作纯投影积木，不再成为另一个独立写入当前解释的入口。
- 不按型号授予不同语义权限。首次接线可以按执行后端分阶段，但不能把未接线后端或旧管线宣称为已完成 P1，也不能静默降回不可修订路线。
- 模型自拟计划项允许删改；用户明确义务另存引用。对非结构化问句保留完整原请求，不假装代码已穷尽抽出每一个语义要求。

选择 PLAN 是因为已有 revision、记录和 loop 接收点；不用单独 alignment 服务，是为了避免第二位解释 owner 和额外默认调用。代价是必须改当前 PLAN 单调规则与运行时消费者，不能只扩 schema。

### 6.2 版本：保持旧任务锚点，另记可修订解释

建议在新契约版本中：

| 身份 | 语义 | 使用者 |
|---|---|---|
| 根请求/episode 锚点 | 原请求、材料和入口身份固定；旧 `task_frame_hash` 不现场改义 | 历史事件、预算、取消、任务归属 |
| 当前解释 revision + 内容摘要 | 可调整的题型/主体解释/时间解释/计划及要求投影 | 提示、派发意图、当前完成检查、交付报告 |
| schema/contract version | 存储与协议格式，不是模型计划次数 | snapshot 读写、恢复、兼容路径 |

复用 `EpisodeState`、授权/证据快照和现有事件通道，不另建数据库或第二本预算账。新事件引用旧→新版本，旧事件/证据原件不重签。先以现有单写者边界完成修订提交，再派发工具；陈旧提案返回可恢复错误。

第一刀可以拒收“解释修订与工具调用同一响应”的组合，并告知模型拆开；普通 PLAN+工具的历史协议不要因此无故全删。已有在途工具必须结算与归属，不能因计划撤回免账；旧证据重新判适用性，不能只换标签沿用。

**恢复兼容必须同行：** 当前授权快照对完整 v1 合同精确比较。v2 需要同时核根授权与已接受解释版本，不能继续拿当前解释和启动合同强行相等，也不能只放宽比较。旧 v1 在途任务按旧读法续接/诊断，未知版本拒绝，缺字段不猜成新权限；不热迁移旧 episode。

### 6.3 同一切片必须贯穿的消费点

1. `task_frame` / `research_contract`：保留原题、用户要求引用、建议来源与解释版本；别名仅处理身份，不决定要求来源。
2. `research_plan` / `research_harness` / `agent_episode`：一个提案入口、一位应用 owner；沿用原 deadline/root budget/call ledger/cancel，不重新跑初始 context 工厂。
3. `episode_factory` / `episode_protocol` / `episode_verifier`：当前解释真正决定建议投递；当前用户要求与完整性边界决定验收。模型声明“我改完了”不自证已答。
4. 如果 P1 会影响旧/专项输出，`conversation_orchestrator` 的输出投影和 §2.2 的补写/失败投影也须保真；否则明确把这些路径留在旧契约，不称全入口完成。
5. 持久化与恢复：写入/读回同一组版本；新版本终稿不能用旧版本见证通过，旧工具结果不能冒充新范围的已核证据。

本切片不改工具目录、方法投递、模型参数、缓冲模式、修复次数或授权资源。也不把全部语义误判都编码为新确定性校验器。

### 6.4 先用性质验证机制，再谈质量比较

优先在既有测试与 Workbench 入口冻结回放里核对：

- 合法修订改变真实后续提示/派发/验收，而非只加日志；恢复读回也一致。
- 同样一个通用机制处理轻任务与多步任务；改变公司名、日期、表达后，来源/权限性质不变。
- 模型可撤自拟步骤，但无法删除用户原题/明确子问，无法凭材料指令扩权。
- 必需项缺失 + 可选项缺失时，补写只追真正义务；仅缺建议不触发补写/整篇降级。
- 修订不刷新余额、deadline 或取消；迟到结果记旧归属并结算。
- 拒绝陈旧提案、新旧版本混绑、未提交修订就派发；旧 v1 读回不变。
- 保留合法改写与否定/错主体/错时段/仅边界等对照，不能拿 marker 命中或内部 complete 代替全文判断。

这轮已见样例是诊断集，不是留出题。真实模型配对仍需另行预注册/授权；R19 封存、凭据退役、正式240格未放行；R17不重跑，R18不接管。没有证据证明新设计更快、质量更高或总体不退步。

## 7. 成立条件与接续

- 源码树/branch：`~/fwp-wt-owner-output-contract-1002` / `fix/owner-output-contract-1002`。
- 被测 revision：`6ef1d41e95790bc20f7b3a2c79db7bed38ea66c9`；探针前后 `dirty=false`。本报告与交接是其后的文档改动，不重签旧代码收据。
- 解释器：`/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`；Python 3.12.13、httpx 0.28.1、pytest 8.3.5、pydantic 2.13.4。共享环境的 httpx 漂移未被当成锁环境。
- 正门：本树 `AGENTS.md`、`CLAUDE.md`、`docs/agent-product-door.md`；并行减法审计/v0.1 spec；原分支身份交接；上列源码符号。代码地图 empty，不作为缺少实现的证据。
- `design_ssot=present`：`harness-reference gitea/main@849c62090b6f7e83eb0c99a0b15da7344a5a82fe:DESIGN-stack.md` 与 `PLAYBOOK.md`，保存副本 SHA256 与 `git show` 逐份相同。没有编辑该仓脏树。
- 本轮验证：21例确定性复跑 + 可选要求消费者探针；未重跑全仓/前端/浏览器，未做隔离独审或自然模型收益评估。Python guard 不等于 OS 沙箱。
- 原 `owner-output-contract-20261002T100000Z/closeout.json` 与 Agent Memory 索引已读回，确实存在；不再把压缩摘要里的“可能未收尾”当当前事实。历史 **632P/1F** 仍是历史相关范围读数，不是本轮全量。

下一步：先让 v0.1 owner 对齐 §3 四项与 §6 单入口/版本建议，锁定实施基线及旧路径退出面，再实施一个 P1 切片。原身份候选不带红合入，也不在此枝顺手开展预算或工具目录改造。
