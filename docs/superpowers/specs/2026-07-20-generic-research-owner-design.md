# Generic Research Owner Design

## 背景与架构判断

当前未命中专项 Skill 的问题仍由固定 Ask 管线主导：市场快照、图谱、Evidence Index、Wiki RAG、Web fallback 依次运行，`agent_research.py` 到后段才以补检索 Provider 身份加入，并只返回 candidate facts。它能选择白名单工具、改写查询和报告 gaps，但不能定义任务完成条件、停止前置无关检索或控制最终答案结构。

因此当前系统是“较强的 Skill 工作流 + Agent 补检索”，还不是成熟的通用研究 Agent。最优改造不是继续增加 Skill，也不是解除所有约束，而是新增受约束的 `GenericResearchOwner`：未命中专项 Owner 时，它拥有端到端研究控制权；确定性代码继续拥有事实、预算、工具权限和出口裁决权。

## 目标

1. 无专项 Owner 的长尾问题先形成可审计任务契约，再执行任何高成本检索。
2. GenericResearchOwner 根据 observation 决定下一步工具、查询改写、停止或报 gap。
3. 固定检索模块成为类型化工具，不再作为所有长尾问题的默认前置流水线。
4. Task-completion Gate 与 Grounding Gate 分离，分别检查“是否回答问题”和“答案是否有证据”。
5. 一轮研究只使用一份 deadline、查询账本、LLM 调用账本和 trace 上下文。
6. Presenter 根据已完成内容动态选段，证据不足时不得用通用模板补齐。

## 非目标

- 不引入 LangGraph 等新框架；现有 Python 编排足以实现状态机，避免迁移成本。
- 不在本批引入多 Sub-agent 并行；先把单 Owner 闭环做正确，再用评测证明是否需要并行。
- 不允许 Agent 动态创建工具、执行任意代码或突破白名单。
- 不把记忆当当前事实；记忆只作为 prior（先验）影响研究起点和篇幅。
- 不追求复制 Knevo 的宽松推断风格，保留本项目更严格的证据纪律。

## 控制流

```text
Turn Controller
  ├─ 确定性头部意图 → 固定 Owner / 确定性函数
  ├─ 专项 Skill 命中 → Skill Owner
  └─ 无 Owner 长尾 → ResearchTaskContract → GenericResearchOwner
                                           ├─ plan next action
                                           ├─ call typed tool
                                           ├─ observe evidence/gaps
                                           ├─ update fulfillment
                                           └─ finish / replan / explicit gap

ResearchResult → Task-completion Gate → Grounding Gate → Dynamic Presenter
```

Controller 只做一次受约束裁决。确定性规则优先；无头部命中时，现有软理解能力生成结构化任务契约。不得再调用一个语义 Skill Router 重算主体和类型。若 LLM 不可用，则生成保守的通用契约，并把无法可靠推断的 required output 标为待规划，而不是回到全量固定管线。

## 核心契约

### ResearchTaskContract

任务契约是长尾问题的单一事实源，包含：

- `task_id`、原始问题和解析后的用户目标；
- `subject`、`subject_kind`、question type 和时间范围；
- `required_outputs`：每项有稳定 id、描述、允许的证据类型和是否必须；
- `freshness_requirements`：实时、当日、最近披露或历史稳定事实；
- `allowed_capabilities`：从能力注册表钳制后的白名单；
- `research_tier`：quick、standard、deep；
- `stop_policy`：步数、时长、无信息增量阈值；
- `presentation_profile`：比较、解释、计算、事件或通用裁决。

LLM 可以提出 required outputs 和能力需求，但代码负责 schema 校验、白名单交集、预算上限和必要输出补全。

### ResearchRunContext

整个 turn 共享一个 `ResearchRunContext`：

- 根 `ResearchDeadline` 与 synthesis reserve；
- `QueryLedger`，对 tool、规范主体、查询和影响结果形态的参数做去重；
- `LLMCallLedger`；
- trace writer 和统一 parent run id；
- 当前工具权限与研究档位。

Owner、工具、judge 和 composer 只能从该上下文派生更小的 deadline，不能创建新的独立总预算。

### Typed Tool Registry

每个工具注册：

- capability 名称和自然语言用途；
- 输入 schema、输出 schema；
- 适用主体、数据新鲜度和来源层级；
- 成本等级、默认 timeout；
- runner；
- 是否支持当前任务的 capability probe。

工具统一返回 `ToolObservation`：公开证据、内部 locator、ProviderTrace、typed gaps、查询 fingerprint 和 accepted evidence hashes。LLM 只能看到经公开投影和长度限制后的 observation；内部路径、错误堆栈和控制面统计不进入回答上下文。

初始工具复用现有能力：KB closed-loop、Web、财经新闻、知识图谱、Evidence Index、L3 官方补查、结构化行情。`closed_loop_retrieval.py` 继续负责 KB 工具内部的窄/宽/反检索与词面闸门，不再对所有问题自动执行。

## GenericResearchOwner 循环

循环每步执行以下状态转换：

1. 根据任务契约、required output fulfillment 和已观察结果选择一个工具动作或 `finish`。
2. 代码校验工具权限、参数、重复查询、预算和 deadline。
3. 工具返回 observation；EvidenceAtom 先经过现有词面/语义证据闸门，再进入 accepted evidence。
4. 确定性 fulfillment evaluator 更新每个 required output 的状态：`fulfilled`、`gap` 或 `missing`。
5. 若仍有 missing 且存在可执行能力，进入下一步；否则结束。

LLM 的 `finish(sufficient=true)` 只是建议，不能直接宣告任务完成。只有 fulfillment evaluator 证明全部必需输出为 fulfilled，或明确转为带原因的 gap，循环才能结束。

无信息增量采用证据 hash，而不是另加一次 LLM judge：连续两次工具动作没有新增 accepted EvidenceAtom 或新的 typed gap 时提前停止。这比语义相似度模型便宜、可回归，也能避免重复搜索。

## 研究档位与预算

- `quick`：最多 3 个工具动作，目标 30 秒，适合单一事实和轻量解释。
- `standard`：最多 6 个工具动作，目标 90 秒，适合比较、事件影响和一般长尾研究。
- `deep`：最多 12 个工具动作，目标 240 秒，只在用户明确要求深入、对象较多或证据冲突显著时启用。

Conversation run 本身是后台任务并通过 SSE 报进度，因此 deep 可以延长根 deadline，但必须显式展示研究档位。每档都为最终合成保留至少 20 秒或总预算的 20%，取较大者；检索阶段不能消费该储备。

高成本工具必须由 Owner 明确调用。Controller、任务契约生成和 Skill 路由共享一次理解结果，消除重复 LLM 分类。达到根 deadline 后只允许生成结构化 partial/gap，不再启动新工具或修订轮。

## 两道出口门禁

### Task-completion Gate

逐项检查 required outputs：

- 事实/比较项必须绑定至少一个通过闸门的 EvidenceAtom；
- 派生计算必须绑定输入证据和计算 lineage；
- 无法完成的项必须有 typed gap、失败原因和可验证的补数条件；
- `missing` 的必需项禁止完整研究答案出站。

### Grounding Gate

复用 `AnswerSpec → Claim/EvidenceAtom → deterministic validator → semantic judge`。它只判断所写内容能否由证据支持，不再承担“有没有回答用户”的职责。

门禁顺序固定为 completion 在前、grounding 在后。任一失败都 fail-closed：保留已完成部分和业务化 gaps，绝不落回污染模板。

## Dynamic Presenter

Base Finance 的五元素从强制模板降为可选段型库：

- 比较题选择比较维度、差异、反证和结论；
- 计算题选择数值、方法、截止日和失效条件；
- 事件题选择事件事实、传导链、受益/受损条件和验证窗口；
- 证据不足只展示可确认部分和 gaps。

Presenter 只能消费 completion gate 的公开投影。Agent transcript、工具计数、内部表名、raw quality issues 和 relation 路径仅进入 Inspector。

## 与现有层的整合及删除

1. `agent_research.py` 保留循环和工具 adapter，但从 Ask 后段 Provider 升级为 Owner 执行引擎；其用户可见“Agent 补检索”section 删除。
2. `retrieval_planner.py` 的独立 LLM 规划角色删除，白名单钳制和 provider metadata 合并进 typed tool registry，避免两个 Planner 争夺控制权。
3. `ask.py` 的固定通用管线保留给现有 Skill Owner 和兼容 CLI；GenericResearchOwner 路径不先跑全套 providers。
4. `closed_loop_retrieval.py`、`evidence_judge.py` 作为 KB 工具内部和 EvidenceAtom 入库前的纵深防御继续保留。
5. `output_review.py` 继续作为 Inspector advisory，不与 completion 或 grounding gate 合并。
6. 保留一个 rollback flag 控制 GenericResearchOwner 的 on/off，但默认行为和 runtime 只有一套，不维护两份分支实现。

## Trace 与可观测性

每个 Owner step 生成稳定 step id，并记录：

- 输入任务契约版本；
- 选择的工具、理由、规范查询和预算前后值；
- ProviderTrace 与 evidence hash；
- required output fulfillment 变化；
- 停止原因；
- completion 和 grounding 两道门禁结果。

工具内部 trace 使用 parent step id 串回同一 turn。公共 API 只投影业务状态，如“正在核对公告”或“缺少指数历史行情”，不暴露控制面数据。

## 错误与降级

- 任务契约解析失败：使用保守 schema 默认值并记录 `contract_fallback`。
- Planner LLM 不可用：基于 required outputs 和 capability metadata 选择最低成本的确定性首个工具；不能证明完成则报 gap。
- 工具失败：保留 trace，允许换 provider 或换能力；没有替代工具时写 typed gap。
- 重复查询：QueryLedger 拦截并把“已执行、无新增”作为 observation，不重复外呼。
- deadline/步数耗尽：返回 partial/gap，停止所有新副作用。
- quality 失败：不展示失败正文，用户看到已核验部分和业务化 gaps。

## 测试与评测

### 契约和状态机测试

- 无专项 Skill 时必须由 GenericResearchOwner 接管，且固定 Wiki/图谱/Web 不得先运行。
- 专项 Skill 和确定性头部行为不变。
- LLM 不能选择未授权工具或突破步数、时长、调用预算。
- 相同 tool/query/参数在一个 turn 内只执行一次，不同查询可继续。
- `finish(sufficient=true)` 但 required output 缺失时必须被拒绝。
- completion 通过、grounding 失败时仍 fail-closed。
- 所有 tool trace、owner step 和门禁结果属于同一 parent run。
- 控制面字段不进入主正文。
- dynamic presenter 不填充没有证据的段落。

### 真实长尾基准集

建立版本化长尾题集，至少覆盖：精确取数、计算、当前事件、多对象比较、因果解释、产业链探索、观点反证、不可得数据、连续追问和明确深研。每题登记：

- 预期任务契约和 required outputs；
- 允许/禁止工具；
- 最低证据类型；
- 预期完成或 gap；
- 最大工具数与延迟档位；
- 禁止出现的模板和控制面文本。

核心指标为 task completion rate、grounded claim rate、诚实 gap rate、无关 provider 调用率、重复工具调用率、模板污染率、P50/P95 延迟和错误 degrade 率。不能再以单元测试数量或“组件存在”代替能力验收。

### 端到端验收

在临时 runtime 对代表性长尾问题运行完整 Conversation API，检查正文、AnswerSpec、task contract、owner steps、ProviderTrace、预算账本和 SSE。至少证明：

1. 未命中 Skill 后仍能形成完整研究任务，而不是 `base_finance_fallback`；
2. RAG 只在任务需要文本证据时调用；
3. Agent 能根据空结果或矛盾结果改写查询/换工具；
4. required outputs 满足后能提前停止；
5. 数据不可得时输出短而准确的 gap；
6. 已聊过标的的追问使用记忆作为 prior 做增量研究；
7. 主正文无工程术语、表名、证据计数和 raw quality issue。

