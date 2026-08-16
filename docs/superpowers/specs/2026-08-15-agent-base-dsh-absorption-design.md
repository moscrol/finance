# 设计：Finance Agent 底座吸收 DeepSeek Harness 模式

日期：2026-08-15
状态：第 1–7 步已合 #61；第 8 步校准 #68 + 样本量锁 #69（30×15=450/臂）；对照未开
基线：实施分叉点 gitea/main@23e2a07e（生产当时实跑 cb09f895）
本文件：已落 main（不再只活在 `docs/dsh-absorption-spec`）
实施分支：feat/dsh-absorption-p0-seams（第 1–7 步）；其后校准/锁样本走独立 PR
基线复核收据：docs/superpowers/specs/2026-08-15-dsh-absorption-step1-baseline-receipt.md

> 初版此处写「基线：main@a189d6bd」，实施第 1 步复核时证伪：本地 `main` 落后
> `gitea/main` 19 个提交，且生产 8792 加载的 `cb09f895` 不在本地 `main` 上。
> 那 19 个提交改动的正是 §11 第 2–5 步要动的 `agent_episode.py` /
> `episode_protocol.py` 及其测试。详见上面那份收据。

## 0. 一句话结论

保留 Finance Workspace 当前的 Python Agent Runtime 作为生产主线，把 DeepSeek Harness（下文简称 dsh）当作通用运行时的参考实现和可选对照后端，不做整套迁移。

最值得吸收的不是 dsh 的 TypeScript 代码，而是它已经明确化的六个边界：

1. Durable Session Event 与 Live Extension Event 分离；
2. pre-execute -> execute -> post-execute -> finalizeContent -> result 工具流水线，加上 agent/pre-step、agent/request-error 等 Step 级扩展点；
3. 每个 Agent/Session 的 Scoped Context 和能力集；
4. 创建、恢复、取消、排空、销毁的回滚式生命周期；
5. Profile/Bundle 的组合式配置；
6. 从事件派生 UI、评测和公开结果 Projection。

金融领域的 Evidence Ledger、数据截止日、证据绑定、语义验证、修复准入和回检闭环仍由 Finance Workspace 自己拥有。dsh 不得绕过这些门禁。

## 1. 目标与非目标

### 1.1 目标

- 明确当前 Finance Runtime 与 dsh 的能力边界、重叠部分和互补部分。
- 为当前 Runtime 增加可复用的通用扩展接缝，减少后续接入 Claude/Pi/dsh 的成本。
- 让 dsh 可以作为一个独立 Runtime Backend 参与同题 A/B，而不复制金融领域服务。
- 建立可复核的结论来源、源码版本、运行变量和决策阈值。
- 用同一套金融领域 Harness 评估执行底座差异，避免把模型、数据或领域规则差异误判成底座优势。

### 1.2 非目标

- 不把 Finance Workspace 改写成 TypeScript/Node 工程。
- 不把 Cordis 全量引入 Python。
- 不用 dsh 的通用 Session Log 替换 Evidence Ledger。
- 不让通用 Runtime 决定金融事实、证据硬度或输出是否可发布。
- 不在本 Spec 中直接修改生产 Runtime、工具、数据库或评测题库。
- 不根据一次 Demo 宣称 dsh 或当前底座“更好”。

## 2. 术语和分层

### 2.1 通用底座（Generic Runtime）

负责“怎样运行 Agent”：模型调用、工具调度、预算、取消、恢复、Session、事件、权限、Sandbox、插件和 UI 投影。

### 2.2 领域 Harness（Finance Domain Harness）

负责“金融问题应该怎样研究”：数据源、检索、指标语义、截止日、证据身份、反证、金融输出契约、Evidence Ledger、结构验证和语义验证。

### 2.3 目标分层

~~~text
用户问题 / 对话上下文
  -> 领域任务解析与金融 Research Contract
  -> AgentRuntime Protocol
       -> 当前 Continuous Runtime
       -> dsh Runtime Adapter（对照）
       -> 其它 SDK Adapter（可选）
  -> 统一 Finance Tool Registry
  -> Evidence Ledger + Structural/Semantic Verifier
  -> 统一公开答案、Trace、评测 Artifact
~~~

关键约束：dsh 是 Runtime 的平行实现，不是叠在现有 Agent 上的第二个 Agent Loop。双重 Loop 会造成重复预算、重复 Session、重复工具调用和无法判断的 Trace。

## 3. 结论来源与证据等级

### 3.1 Finance Workspace 的本地来源

以下文件是本 Spec 对当前底座判断的主要依据：

| 来源 | 用途 |
|---|---|
| docs/layered-rebuild-roadmap.md | 现有底座/领域层拆分、219 模块/122K 行统计、约 5,200 行 Loop 骨架与约 7,511 行领域逻辑的历史测量 |
| docs/handoffs/2026-07-31-harness-goal-and-references.md | 通用 Harness 与领域 Harness 的目标边界、SDK 只覆盖 Loop 半边的判断 |
| intelligence/services/agent_runtime.py | AgentRuntime、ResumableAgentRuntime 和 AgentOutcome 契约 |
| intelligence/runtime/agent_runtime_factory.py | Runtime Backend 选择、provider-neutral 约束和 readiness |
| intelligence/runtime/agent_episode.py | Continuous Episode 的计划、工具、预算、修复、子研究和终局过程 |
| intelligence/services/research_tool_registry.py | ToolSpec、能力授权、参数规范化、produces、Observation 和 Tool Result |
| intelligence/runtime/episode_tool_batch.py | 工具批次并发、去重、计时、Query Ledger 和发布门 |
| intelligence/services/episode_session.py | 同一 Episode 历史续接、身份保持和关闭契约 |
| scripts/layer_audit.py | services 不得依赖 runtime 的依赖倒置门禁 |
| scripts/run_agent_runtime_benchmark.py | 现有 Runtime Backend 对照入口 |
| scripts/run_agent_episode_ab.py | 现有 Episode/领域组装对照入口 |

### 3.2 dsh 源码版本

本 Spec 以 dsh master 在以下 commit 的源码为准：

~~~text
47f943859bef60e4160492346772ded9b24f765a
~~~

公开仓库：
https://github.com/deepseek-ai/deepseek-harness/tree/47f943859bef60e4160492346772ded9b24f765a

已建立本地可检索的 sparse checkout：

~~~text
/Users/a77/finance-workspace-private/tmp/dsh-source-index
~~~

当前本地副本包含 docs、packages/core、packages/bundle/base、packages/llm、apps/cli 和 packages/host，目录被 .gitignore 的 tmp/ 忽略，不会进入 Finance 生产仓库。

> `packages/llm` 是第 1 步复核时补进 cone 的：base bundle 只声明挂载哪些 adapter，
> Provider 能力（能否接 OpenAI 兼容网关）的判据在 `packages/llm/llm-pi-ai/README.md`，
> 不在 cone 里就只能靠 `git show` 取证，本地复现路径是断的。

进入该目录后可以直接检索：

~~~bash
cd /Users/a77/finance-workspace-private/tmp/dsh-source-index
git grep -n "agent/pre-step\|tools/pre-execute\|session/event"
git grep -n "ReactLoopAgent\|interface Agent\|SessionEvent"
~~~

需要重建副本时，必须检出本节 pinned commit，不得检出 master；克隆不加 --depth，否则 master 前移后无法回到该 commit：

~~~bash
DSH_INDEX=/Users/a77/finance-workspace-private/tmp/dsh-source-index
DSH_COMMIT=47f943859bef60e4160492346772ded9b24f765a
git clone --filter=blob:none --no-checkout \
  https://github.com/deepseek-ai/deepseek-harness.git "$DSH_INDEX"
git -C "$DSH_INDEX" sparse-checkout init --cone
git -C "$DSH_INDEX" sparse-checkout set \
  docs packages/core packages/bundle/base packages/llm apps/cli packages/host
git -C "$DSH_INDEX" checkout --force "$DSH_COMMIT"
git -C "$DSH_INDEX" rev-parse HEAD
~~~

关键 dsh 源码证据：

| dsh 来源 | 结论 |
|---|---|
| docs/architecture.md | Cordis 服务、Plugin Tree、Profile/Bundle、Session Event、Capability Seam 和 Turn Flow |
| packages/core/README.md | Session、System Prompt、Tools、Agent、Agent Loop 的产品 API spine |
| packages/core/agent-loop/README.md | Loop 生命周期、取消、恢复、并发工具、错误恢复、插件扩展点 |
| packages/core/agent-loop/src/agent.ts | 具体 Agent Driver、Inbox、Turn/Step 和工具调度实现 |
| packages/core/session/src/types.ts | Durable Session Event 的类型和可重建边界 |
| packages/core/tools/src/types.ts | Tool 定义、执行模式、结果和 Schema 类型 |
| packages/bundle/base/README.md | Base Bundle 提供的模型、工具、持久化、策略、凭证和 Telemetry |
| packages/bundle/base/cordis.patch.yml | Base Bundle 实际挂载的插件行；LLM adapter 只有 llm-deepseek 与 llm-pi-ai，默认模型 deepseek-official/deepseek-v4-flash |
| packages/llm/llm-pi-ai/README.md | 多 provider adapter；手写声明路由可接 OpenAI 兼容网关（配置而非改代码）；凭证走 apiKeyEnv 或 ctx.credentials seam；无 profile 时休眠零路由 |
| apps/cli/README.md | Profile、Bundle、CLI、Web 和 Headless 入口 |

源码快照、GitHub 链接和本 Spec 的判断必须绑定同一个 commit；禁止拿最新 master 的未记录变更回填历史结论。

## 4. 当前底座评估

### 4.1 已有能力

当前 Finance Workspace 已经具备一个可替换 Runtime 的核心形状：

- AgentRuntime / ResumableAgentRuntime Protocol；
- Continuous Episode 的 plan、tool、observe、repair、finish 链路；
- root budget、deadline、工具批次预算和 repair cycle；
- ToolSpec 的金融能力、成本、新鲜度、查询范围和 produces 声明；
- EvidenceLedger、ProviderTrace、evidence hash 和 output binding；
- Structural Verifier 与金融语义 Semantic Verifier；
- Sub-research 分支、独立预算和结果合并；
- continuous_glm、sdk_gpt、codex_headless 等 Runtime Backend 选择；
- services 不得 import runtime 的分层门禁。

这不是“Prompt + 几个工具”的原型，而是已经有领域正确性和运行时审计能力的专用 Agent Runtime。

### 4.2 需要继续补强的通用部分

以下问题来自当前路线和既有实测，应在实施前重新执行对应检查，不把历史状态直接当作当前主线状态：

1. 上下文压缩和证据保留还没有统一的通用策略；
2. Continuous 与另一条引擎在 fulfillment、Trace 和公开状态上的契约仍需完全对齐；
3. 工具能力声明、授权、Prompt 可见性和实际可达性仍需要单一 Scope；
4. Episode 的关闭、取消、后台分支排空和重启恢复需要统一生命周期对象；
5. Runtime、工具、Profile 和评测变量仍有一部分依赖环境变量和入口侧组合。

这些属于通用底座的可观测性和装配问题，不能通过放宽金融验证门来解决。

## 5. dsh 能力评估

### 5.1 dsh 的强项

- Plugin/Service Seam：服务定义、Provider、Consumer 分离，扩展通过插件挂载；
- Typed Event Taxonomy：Durable Session Event 和 Live Agent/Tool Event 分离；
- Session Event Sourcing：从事件派生模型历史、UI、恢复、Fork 和 Transcript；
- 工具执行流水线：pre-execute -> execute -> post-execute -> finalizeContent -> result，并支持 Guard；
- Scoped Context：每个 Agent 可以拥有独立工具、Prompt、策略和注册范围；
- 生命周期纪律：创建、发布、恢复、取消、排空、销毁是有回滚边界的事务；
- Profile/Bundle：通过有序配置层组合 Web、Headless、模型、工具和策略；
- 通用产品壳：Web、CLI、Headless、插件安装和配置检查开箱可用。

### 5.2 dsh 的边界

- 默认不理解金融数据截止日、证据等级、Evidence Binding 或 A 股语义；
- dsh 的通用 Tool Schema 不能替代 capability/cost/freshness/query_scope/produces；
- dsh 的 Session Log 不能替代金融 Evidence Ledger；
- dsh 是 TypeScript/Node 工程，接入 Python 金融服务需要跨语言边界；
- dsh 仍处于 Developer Preview，兼容性变更是公开声明的风险；
- 通用压缩、Code Mode 或工具结果投影若没有金融保留规则，可能静默丢失反证。

## 6. 对照矩阵

| 维度 | Finance Workspace | dsh | 结论 |
|---|---|---|---|
| Loop | 金融研究 Loop，含预算、修复、证据交付 | 通用 React Loop，插件化扩展 | dsh 可提供通用生命周期参考，不能替代领域 Loop |
| 工具 | 金融语义和证据产出强 | 通用 Schema、Guard、执行流水线强 | 两套元数据叠加，不互相覆盖 |
| Session | Episode 历史和 Evidence Ledger | Event-sourced Session、Fork、Resume | 吸收事件/Projection，保留领域账本 |
| 权限 | 以授权能力和数据门禁为主 | 通用 Approval、Sandbox、Policy | dsh 的执行策略可补强，金融门禁仍由本仓拥有 |
| 可替换性 | 已有 Runtime Protocol 和 layer audit | Plugin/Service/Scope 更系统 | 吸收 Scope、Provider/Consumer 词汇和契约 |
| 配置 | Factory、Mode、环境变量较多 | Profile/Bundle 层次化组合 | 建立 ResearchProfile，不照搬整行覆盖 |
| UI/Headless | 已有 Workbench、API、CLI 和 Headless | Web/CLI/Headless 完整产品壳 | dsh 可作产品壳对照，不必迁移领域服务 |
| 领域正确性 | Evidence、Verifier、回检闭环 | 默认无金融语义 | 当前底座明显占优 |
| 语言成本 | Python 直接复用本地数据和 RAG | TypeScript/Node，需要桥接 | 完整迁移成本高，Adapter 优先 |
| 评测 | 金融题库、绑定、回检指标 | 通用运行时测试 | 同一领域评测必须在两边复用 |

## 7. 吸收设计

### 7.1 P0：显式工具流水线

当前已有参数解析、授权、去重、预算、执行、Trace、Evidence 和 Observation，但这些步骤分散在 registry、batch 和 runner 中。

增加一个领域无关的 Pipeline Protocol，金融工具通过 Adapter 注入领域规则：

~~~python
class ToolPipeline(Protocol):
    def prepare(self, request: ToolRequest, scope: EpisodeScope) -> PreparedTool: ...
    def authorize(self, tool: PreparedTool, scope: EpisodeScope) -> Authorization: ...
    def pre_execute(self, tool: PreparedTool, scope: EpisodeScope) -> None: ...
    def execute(self, tool: PreparedTool, scope: EpisodeScope) -> ToolRunResult: ...
    def post_execute(self, result: ToolRunResult, scope: EpisodeScope) -> ToolRunResult: ...
    def project_result(self, result: ToolRunResult) -> PublicToolResult: ...
~~~

与 dsh 的对应关系：prepare/authorize/pre_execute 合并承担 tools/pre-execute 与 Guard 的职责，execute/post_execute 对应同名阶段，project_result 覆盖 dsh 中 definition-owned finalizeContent 和 tools/result 两段。

金融层继续负责：截止日、查询语义、证据来源、hash、freshness、gaps 和 output binding。

验收：

- 每次工具调用都有唯一 tool_call_id 和完整阶段事件；
- 被授权工具集合、Prompt 可见工具集合、实际执行工具集合可以逐次对账；
- 任意阶段失败都转为结构化 Tool Result，不让结算代码成为新的失败源；
- EvidenceLedger 只接收成功且可追踪的 post_execute 结果；
- 现有工具行为、Episode 批次和 Runtime benchmark 在不降低金融门禁的前提下通过。

### 7.2 P0：EpisodeScope 与能力可达性

工具可能“定义了但没注册”“注册了但没授权”“授权了但 Prompt 不可见”或“可见但实际入口不调用”。单独维护 capability floor、plan mapping 和入口分支容易再次漂移。

建立一个显式 EpisodeScope，至少包含：

~~~text
episode_id
user_id
task_frame_hash
allowed_tools
allowed_capabilities
policy
root_budget
information_cutoff
evidence_ledger
event_sink
~~~

由 Scope 一次性派生 tool registry、model-visible schemas、execution authorization、trace context 和 evidence context。

验收：

- scope.dump() 能列出每个工具的定义、授权、可见性和执行状态；
- 新增工具若只存在于测试注册表而不在生产 Scope，审计命令必须报警；
- memory_lookup 这类能力必须有一条从入口到实际调用的可达性收据；
- 领域层不 import Runtime 实现，继续由 layer_audit.py 守住依赖方向。

### 7.3 P0：统一 Runtime 生命周期

当前 EpisodeSession 已有 resume/close，但通用 Runtime、子研究、Provider 请求和后台任务的取消/排空边界需要统一表达。

引入 RuntimeHandle 概念，生命周期固定为：

~~~text
created -> started -> running -> cancel_requested -> draining -> closed
~~~

要求：

- close() 幂等；
- close() 后不允许发布新的 Agent、Tool 或 Event；
- cancel 只阻止尚未派发的工作，并排空已启动的只读工作；
- 子研究必须携带 parent/branch lineage；
- resume 必须保持 task frame hash、Episode ID 和既有事件前缀不变。

验收：

- 取消、超时、Provider 失败、进程重启四类场景都有事件收据；
- 没有 orphan tool call、未结算 budget 或关闭后的事件；
- Episode、Session、Headless Gateway 测试覆盖上述状态转换。

### 7.4 P1：Durable Event 与 Projection

将当前 EpisodeEvent 明确分成两类：

~~~text
Durable：task / plan / model_turn / tool_call / tool_result / repair_goal / finish
Live：agent status / queue timing / UI progress / provider heartbeat
~~~

所有模型可见内容必须能从 Durable Event 重建；Trace、Workbench、评测和 API 响应都从 Projection 生成，不能直接读取 Runtime 内部状态。

金融约束：

- evidence hash、source、source_date、status、gaps 不得在 Projection 中丢失；
- 私有路径、凭证、内部 locator 只能留在内部 Artifact；
- Evidence Ledger 是金融事实的权威来源，Session Event 只记录它的引用和变更轨迹。

验收：

- 从 Durable Event 重建的 model messages 与实际发送边界一致；
- 从同一 Event 同时生成 UI、Trace、评测 Artifact，三者的 tool_call_id 可对账；
- 重放不触发真实工具副作用。

### 7.5 P1：ResearchProfile

将当前散落的 Runtime、工具、预算和模式配置收拢成不可变 Profile：

~~~text
quick-research
deep-research
daily-review
read-only
benchmark
headless
~~~

Profile 至少声明：

~~~text
runtime_backend
provider/model
allowed_tools
budget/deadline
repair_policy
verifier_chain
output_contract
~~~

Profile 需要提供 dump_effective_config()；覆盖配置必须显式声明并做 Schema 校验，不采用 dsh 的“替换整行后其余字段全部消失”作为默认行为。

### 7.6 P1：上下文压缩接缝

借鉴 dsh 在 agent/pre-step 和 agent/request-error 上提供压缩/恢复扩展点的做法，但先只建设接口和观测，不立即启用有损压缩。

任何压缩 Preview 必须保留：

~~~text
source / source_date / status / content_hash / gaps
~~~

在真实 continuous_glm 运行中收集 max turn input、Evidence 数量、压缩后 binding 完整度，再决定是否实现确定性摘要或证据分层投影。

### 7.7 P2：Code Mode 与插件加载

只有在工具 Schema 成本和跨工具组合成为可测瓶颈时，才评估 dsh Code Mode。第一版不得隐藏 Evidence Ledger 的逐工具记录，也不得让代码执行绕过只读、截止日和 Query Ledger。

完整动态 Plugin Loader 同样暂缓；先用 Python Protocol + Profile + entry point 实现稳定接缝，等跨领域复用需求出现后再评估插件包格式。

## 8. dsh Adapter 设计

### 8.1 位置

新增 Adapter 只能位于 intelligence/runtime/，实现现有的 ResumableAgentRuntime。领域服务不得 import Adapter 或 dsh SDK；继续由入口层通过 Runtime Factory 选择实现。

### 8.2 跨语言边界

dsh 的 TypeScript Agent 通过一个窄协议调用现有 Python Domain Gateway。协议只传递：

~~~text
task frame
episode scope
tool definitions
tool call
tool result
durable event
final outcome
~~~

不允许把 DuckDB、Evidence Ledger 或内部文件路径直接暴露给 dsh。对照实验先使用 JSON/stdio 或本地 HTTP；不要先引入新的外部服务。

### 8.3 禁止的双写

- dsh Session 与 Finance Episode 不得各自拥有独立的事实账本；
- 一个工具调用只能有一个 Finance tool_call_id；
- dsh 的模型可见结果必须回到 Finance Tool Result Projection；
- dsh 的最终文本必须重新经过现有 Structural/Semantic Verifier。

## 9. A/B 对比设计

### 9.1 实验臂

| Arm | 说明 |
|---|---|
| A | 当前 continuous_glm，作为生产基线；名字中的 glm 不代表实际 Provider |
| B | dsh Runtime Adapter，共用 Finance Domain Harness |
| C（可选） | 已有 sdk_gpt，用于通用 SDK 对照 |

### 9.2 固定变量

- 同一模型和 Provider；
- 同一问题、对话上下文、Task Frame 和 task frame hash；
- 同一数据快照、information_cutoff 和知识库 revision；
- 同一 Tool Registry、Tool Schema、Evidence Ledger 和 Verifier；
- 同一总 deadline、call budget、repair budget 和输出契约；
- 同一失败注入集合：超时、空检索、参数错误、Provider 503、取消、重启。

### 9.3 观测指标

领域质量：

- task fulfillment；
- evidence-bound output rate；
- unsupported numeric/date claim count；
- counterpoint/gap honesty；
- semantic verifier pass/repaired/rejected。

Runtime 质量：

- tool invalid/denied/failed rate；
- first model turn timeout rate；
- repair recovery rate；
- P50/P95 wall time；
- input/output token 和每个阶段耗时；
- Arm B 的跨语言桥接耗时，单独记录，不并入 Runtime 耗时；
- cancel、resume、restart 的成功率；
- Trace 与事件对账完整率。

工程成本：

- Adapter 代码量；
- 新增领域工具的接入代码量；
- TypeScript/Python 双份契约数量；
- 部署依赖和冷启动时间；
- 运行时故障定位所需步骤。

### 9.4 建议判定线

以下是实施前的候选门槛，不是现有实测结论：

- 判定前必须固定题集规模和每臂重复次数，并说明 5 个百分点的差异在该样本量下可与噪声区分；样本量不足时先扩大题集或重复次数，不得直接判定；
- B 不能让 evidence-bound output rate 下降超过 5 个百分点；
- B 不能增加未经绑定的数字/日期断言；
- B 在 P95 延迟、修复成功率、恢复能力或维护成本中至少有一项达到明确改善，才值得进入长期维护；
- 比较 P50/P95 延迟时必须把跨语言桥接耗时单独拆出：桥接导致的劣势记为 Adapter 实现成本，不作为底座优劣的证据；
- 任意 Arm 的 Trace/Projection 对账失败，直接判该 Arm 不可发布；
- dsh Developer Preview 升级后必须重跑同一固定题集，不能用源码更新后看起来更好替代回归。

## 10. 风险与控制

| 风险 | 控制 |
|---|---|
| TypeScript/Python 协议漂移 | 以 Finance AgentRuntime 和 JSON Schema 为唯一边界，生成/对账协议快照 |
| dsh 双写 Session/Evidence | Finance Evidence Ledger 保持唯一事实拥有者 |
| 通用压缩丢金融证据 | 先观测，压缩必须保留五类证据字段 |
| dsh 配置覆盖导致隐式变化 | Profile 使用 typed merge 和 effective-config dump |
| Provider 或模型差异污染 A/B | 固定 Provider/model，Artifact 记录 resolved 值 |
| Developer Preview 兼容性变化 | pin commit、保留 sparse checkout、每次升级重跑 benchmark |
| 外部源码许可证边界 | 不把 dsh 源码复制进生产仓库；本 Spec 只保存 MIT 仓库的 commit、路径和链接 |
| 迁移范围失控 | P0 只做通用接缝，P2 Code Mode/Plugin Loader 必须有指标触发 |

## 11. 实施顺序

1. 复核基线：运行 layer_audit.py、现有 Runtime benchmark 和单元测试，保存 revision、环境、Provider、数据截止日；同时确认 dsh base bundle 在 pinned commit 下有 Arm A 实际 Provider/模型的适配器，没有则先解决模型可比性再继续。
2. 建立 EpisodeScope 和 Tool Pipeline 的 Protocol，不改变现有行为。
3. 为现有工具注册表接入阶段事件和可达性 Dump。
4. 统一 Runtime Handle 生命周期，补取消、排空、恢复和重启测试。
5. 将 EpisodeEvent 分类为 Durable/Live，并生成统一 Projection。
6. 建立 ResearchProfile 和 effective-config 收据。
7. 先用 scripted dsh stub 验证 Adapter 协议，再连接本地 dsh sparse checkout。
8. 运行 A/B 题集和失败注入，按第 9 节指标形成决策收据。
   2026-08-16：先半段 45× Arm A 已跑（#68，v=0.1375，30×3 压不住 5pp）；
   已按裁定加重复锁 30×15=450/臂（#69）。5pp 门槛不放宽。对照仍未开。
9. 只有决策收据显示通用能力有净收益，才考虑长期保留 dsh Adapter；否则保留模式吸收，不保留运行时依赖。

## 12. 最终决策规则

- 领域正确性优先：任何底座收益都不能牺牲证据绑定和金融语义验证。
- 接口优先于迁移：先吸收 dsh 的接口和不变量，再考虑引入实现。
- 对照优先于感觉：同题、同数据、同模型、同预算才能比较底座。
- 本地可观测优先于源码相似：dsh 的设计能否解决当前真实故障，必须由收据证明。
- 生产主线保持 Python：在 dsh 没有证明其在恢复、观测、维护成本上产生净收益前，不改变当前领域服务和生产 Runtime。

最终判断：

> Finance Workspace 当前已经拥有足够强的专用底座。dsh 最适合被吸收为通用运行时设计参考和可替换对照臂；真正应该落地的是事件、Scope、生命周期、工具流水线、Profile 和 Projection，而不是整套 Cordis 或 TypeScript 代码。
