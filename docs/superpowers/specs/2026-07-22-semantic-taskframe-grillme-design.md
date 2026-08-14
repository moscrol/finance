# 长尾问题语义编译、深研循环与 Grill-Me 澄清设计

日期：2026-07-22  
状态：待用户评审（本文件只定义设计，不改变运行代码）

## 1. 背景与目标

当前 Workbench 的头部题型已经有确定性能力，例如 `market_technical`；但普通长尾问题仍可能经历：原问直接路由 → 错误的 `question_type` → 不相关检索 → 证据被有损压缩 → 模板化降级。真实失败例是“昨天的反弹你认为能持续多久”：它被降成 `knowledge/concept_definition`，检索结果混入生猪、旧 AI 资料和知乎/头条，最后流程显示完成，却没有回答持续时间、条件和失效点。

本设计的目标是：

1. 让 LLM 先理解用户要解决的任务，但只输出结构化任务草稿，不直接取得工具执行权。
2. 保留原问题、时间和上下文，默认未指明主体为 A 股市场，并标明这是产品默认而不是用户明示。
3. 借鉴 Grill-Me 的底层歧义消解方法，而不是把该 Skill 作为运行时流程。只对真正会改变答案的歧义做一次高信息增益追问；澄清答案合并回同一个任务，而不是另起一条失去上下文的任务。
4. 普通长尾走一次语义编译；需要因果解释、预测、比较或证伪的深度问题进入 2–4 假设的 Deep Research loop（深度研究循环）。
5. 工具、预算、证据闸门和出口 verifier（核验器）只能收束事实边界，不能把完整研究强行压成不相干的题材模板。
6. 保持现有确定性头部链路的低延迟和零无谓 LLM 调用。

### 非目标

- 不为每一种自然语言长尾问题创建一个 Skill。
- 不允许 LLM 直接决定白名单之外的工具、预算或最终状态。
- 第一版不引入全量 NLI（自然语言推理）模型，也不把 LLM judge 分数当作唯一事实门禁。
- 不把现有 `QueryEnvelope`、`TurnIntent`、`ResearchTaskContract` 之外再平行维护一套不可互转的语义对象；`TaskFrame` 是统一目标模型，迁移期允许它们作为投影/适配器。

## 2. 核心架构：TaskFrame 作为单一任务事实

新增一个窄接口、深实现的 `TaskInterpreter`。它对编排层隐藏 LLM、正则、上下文继承和日期解析的细节：

```python
TaskInterpreter.interpret(
    raw_question: str,
    conversation_context: ConversationContext,
    now: date,
    product_context: ProductContext,
) -> InterpretationResult
```

`InterpretationResult` 只能是 `TaskFrame` 或 `ClarificationRequest`。下游不再从原始字符串各自猜题型。

### 2.1 TaskFrame 字段

```text
raw_question             用户原话，永不覆盖
canonical_question       保留原意的规范化问法
subject                  {kind, name, identifier?, resolution_source}
time_window              {anchor_date, from_date, to_date, raw_phrase, resolution_source}
task_type                受控枚举，如 market_rebound_horizon、market_forecast、comparison、premise_check、general_finance_qa
decision_goal            用户想做的判断：持续性、归因、比较、验证、取数等
required_outputs        必须回答的输出槽位及其 evidence requirement
evidence_requirements    数据域、时效、来源层级、是否需反方/官方证据
query_variants           原问、规范化问法、假设/缺口查询；不可丢弃原问
ambiguities              非阻塞歧义与其影响
confidence               解析置信度和各字段来源
mode                     quick 或 deep
frame_id/frame_revision  可追踪的稳定标识
```

`resolution_source` 只允许 `explicit`、`inherited`、`product_default`、`inferred`；默认 A 股写为 `product_default`，不能伪装成用户明确提供。

### 2.2 统一 required outputs

任务输出槽位以结构化 ID 表示，例如“昨天的反弹你认为能持续多久”至少编译成：

- `current_baseline`：以最近一个有效交易日描述反弹状态；
- `duration_assessment`：给出持续时间的区间/倾向，而非无条件断言；
- `continuation_conditions`：量能、宽度、核心方向等可观察条件；
- `invalidation_conditions`：什么变化会证伪当前判断；
- `evidence_boundary`：数据截止日、缺口和证据层级。

槽位由 `TaskFrame` 生成 `ResearchTaskContract`，随后映射到现有 `TurnIntent`/`QueryEnvelope`。迁移期下游仍可读取旧字段，但不得反过来覆盖 `TaskFrame.required_outputs`、`subject` 或 `answer_owner`。

## 3. 受约束的 LLM 语义编译

### 3.1 LLM 的权限边界

LLM 只返回 `TaskFrameDraft` JSON：主体、时间、任务类型、目标、所需输出、歧义、深度建议和查询变体。它不得返回事实、证据 ID、工具调用、预算数值或“已完成”状态。

代码随后做：

1. JSON schema、枚举、长度和字段完整性校验。
2. 相对日期按交易日历解析；用户说“昨天”时绑定最近有效交易日，而不是系统自然日盲算。
3. 主体代码、市场范围、能力白名单和 `ResearchDeadline` 预算钳制。
4. 与确定性头部检测交叉验证；高置信头部优先保留现有 zero-LLM 路径。
5. LLM 不可用、输出 malformed 或置信度过低时，使用保守的 `general_finance_qa + TaskFrame` fallback；绝不能把所有未知问题改成 `concept_definition`。

这实现“LLM 有语义解析权、代码有执行权”：比完全规则路由能理解隐含意图，比完全 LLM agent 可测、可回归、可限制成本。

### 3.2 默认 A 股与冲突判定

Finance Workbench 产品上下文默认 `subject = A股市场`。下列情况不应自动覆盖：

- 用户明确写了美股、港股、商品、猪价、汇率、某个行业或个股；
- 会话继承主体与新问题冲突；
- “这个/那波/昨天”缺少可唯一绑定的前文实体或日期；
- 市场范围不同会改变数据源、交易日历或结论。

不冲突时直接继续，并在内部 trace 标记推断来源；展示层可用一句自然语言说明“按 A 股市场理解”。

## 4. 受限歧义消解器（借鉴 Grill-Me 原理，不直接调用 Skill）

Grill-Me 类工具适合“把需求问清楚”的协作阶段，可能连续追问多轮；Workbench 的在线问答目标不同：用户已经提出了问题，系统应优先回答，而不是把问答变成需求访谈。因此只抽取它的四个工程原理：保存原问题、显式建模不确定性、按信息增益选择问题、回答后回灌同一任务状态。

### 4.1 先判断是否值得追问

`AmbiguityResolver` 对每个不确定字段计算：

```text
impact = 是否会改变 subject / data provider / route / required_outputs / 结论方向
confidence = 当前解析置信度
default_safety = 产品默认是否足以安全继续
```

只有 `impact=high`、`confidence` 低且 `default_safety=false` 时才阻塞。字段缺失但不改变执行的情况直接采用假设并记录 `assumption`。因此：

- “昨天的反弹你认为能持续多久”没有显式写主体，但产品默认 A 股足够安全，直接按 A 股最近有效交易日研究；
- “这个反弹还能持续多久”没有可绑定的前文实体，可能在大盘、行业、个股之间切换数据和结论，才需要追问；
- 只是不知道用户喜欢几段文字、是否要图表，不得阻塞研究。

### 4.2 ClarificationBudget

澄清本身也受运行时预算约束，不依赖外部 Grill-Me Skill：

```text
max_blocking_rounds       默认 1（一个任务最多一次阻塞追问）
max_question_count/turn   1（一次只发一个问题）
max_clarification_time    3 秒内完成候选生成；不启动检索等待答案
fallback_after_exhaustion 采用最安全的产品默认并显式声明，或返回 gap
```

只有高风险、用户明确要求“继续帮我拆解”的交互模式才允许把 `max_blocking_rounds` 提高到 2；金融日常问答默认不启用。这样既消解关键歧义，又避免多轮追问吞掉研究预算和用户耐心。

### 4.3 ClarificationRequest

```text
frame_id
question                 只问一个会改变执行的问题
options                  2–4 个具体选项，含推荐项（如适用）
why_it_matters           说明不同选择会改变什么
blocking                 true 时禁止检索；false 时允许带假设继续
raw_question             原问快照
pending_fields           待确认的 TaskFrame 字段
```

例：用户第一次问“这个反弹还能持续多久”，上下文没有明确标的时，只问：“你说的反弹是 A 股大盘，还是某个行业/个股？如果没有特指，我按 A 股大盘分析。” 不应先检索一轮再让用户纠正。

协议规则：

- 一次只问一个最有信息增益的澄清问题；不发送问卷。
- 默认每个任务最多一次阻塞追问；超过预算后必须按安全默认继续或诚实返回缺口，不能循环追问。
- `blocking=true` 时不启动 provider、agent loop 或 synthesis；只记录等待状态。
- 用户回答后合并到同一 `frame_id`，保留 revision 和原问；不重新从新字符串猜意图。
- 非阻塞歧义可采用明确假设继续，但答案必须显示假设和影响范围。
- 用户对系统判断的明确纠正继续写入 correction ledger，并作为后续 TaskInterpreter 的上下文，而不是偷偷改写历史答案。

## 5. 检索与证据：原问锚定、假设分支、闭环收敛

检索顺序固定保留：

```text
Q0 原始问题
  → Q1 TaskFrame 规范化问题
  → H1/H2（支持与反方）查询
  → G gap 查询（只针对缺失 required output）
```

`closed_loop_retrieval.py` 不再把“第一条命中内容”拼进 broad/counter query。后续查询只能由 `TaskFrame + Hypothesis + Gap` 生成，且携带 subject、time_window、as_of 和证据类型锚点。

查询去重使用现有 `query_ledger.py`：key 至少包含 `frame_id/frame_revision`、provider、规范化 query、as_of、corpus revision；同一 turn 并发同 key 只执行一次，跨 provider 的 trace 仍保留。

`evidence_window.py` 的词面过滤只能做第一道筛选；语义闸门必须额外检查：主体是否一致、日期是否在 TaskFrame 窗口内、来源是否满足 evidence requirement、是否把二手观点误当成当前事实。没有通过的命中可记录为 rejected/weak evidence，但不能进入 public claims。

## 6. Deep Research loop

当 `mode=deep`，或 `task_type` 属于预测、周度归因、比较、因果解释、证伪/反方等复杂类型时，走统一循环：

```text
TaskFrame
  → 生成 2–4 个工作假设（支持、反方、替代解释、数据缺口）
  → 在一个共享 ResearchDeadline 下并行取证
  → evidence_judge 做主体/时效/语义闸门
  → 更新 ResearchState（假设、证据、矛盾、缺口、预算、trace）
  → 只对未满足槽位定向 repair
  → grounded compose
  → factual/causal/task-fulfillment 三重出口核验
```

假设是内部工作对象，不得直接当作事实输出。每个最终判断必须能回到 EvidenceAtom；不能确认时输出候选机制、支持证据、反证和缺口，而不是“来源列表 + 泛化下一步”。

预算原则：父 turn 只有一个 `ResearchDeadline`；并行 stage 使用 `child_deadline = min(parent_deadline, now + slice)`，synthesis 保留现有 reserve。LLM 调用、provider 调用和 agent loop 共用同一账本，禁止固定管线和 agent loop 各算一份预算。

## 7. 路由与状态接缝

### 7.1 路由规则

- `turn_controller.py` 只根据已校验的 TaskFrame 选 lane/owner；不能再从原文重复猜题。
- `route_table.py` 仍是头部能力的 SSOT（单一事实源）。确定性头部仅在高置信显式特征下绕过语义编译。
- `conversation_orchestrator.py` 删除或收紧 `decision.lane == "knowledge"` 即覆盖 `QUESTION_CONCEPT_DEFINITION` 的逻辑（约 2174 行）；knowledge 是执行 lane，不是问题类型。
- 所有 lane（包括 knowledge/general/deep）都必须生成非空 required outputs 或明确的 clarification；不能以 `generic_contract=None` 绕过 `task_fulfillment`。
- provider/skill 只能选择能力和证据源，不能改写 `subject`、`task_type`、`required_outputs` 或 `answer_owner`；不兼容时 fail-closed 并回传 trace。

### 7.2 状态平面

继续分离：

- `transport_status`：SSE/HTTP 是否结束；
- `research_status`：研究阶段是否完成、部分完成或超时；
- `answer_status`：用户问题是否满足 required outputs。

LLM 不可用、研究超时或证据不足时，允许 transport 完成，但 `answer_status` 只能是 `partial/missing/evidence_gap`。不能因为 fallback 生成了文本就标记 complete。

## 8. 验收与回归

### 必须通过

1. **反弹持续性**：输入“昨天的反弹你认为能持续多久”，默认 A 股；`task_type` 不得是 `concept_definition`；anchor 为最近有效交易日；输出含 duration、continuation、invalidation、evidence boundary；不得出现生猪、旧 AI、知乎/头条污染。
2. **真正歧义**：无上下文输入“这个反弹还能持续多久”，返回一个 `ClarificationRequest`，不产生检索调用。
3. **当前主线**：输入“目前市场的主线是什么，给我你的判断依据”，输出直接主线判断、同日盘面依据、反方/缺口；只给来源列表必须被判 partial。
4. **复杂深研**：周度下跌原因或“明天反弹还是继续下跌”至少产生支持与反方两个假设；原问和派生查询均进入 ledger，预算和 ProviderTrace 连续。
5. **技术位回归**：`科创50的支撑点位在哪` 仍走 `market_technical`，零无谓 LLM，数字与失效条件不变。
6. **供应商失败**：LLM 不可用时不会降为 `concept_definition`；若无足够证据，输出问题相关 gap，且 `answer_status != complete`。

### 指标

- `task_frame_accuracy`：主体、日期、task_type、required outputs 的 golden set 准确率；
- `clarification_precision`：只有会改变答案的歧义才追问；
- `direct_answer_rate`：长尾问题中真正覆盖 required outputs 的比例；
- `template_reuse_rate`：不同 task frame 的结构/措辞相似度，防止“都变成同一模板”；
- `irrelevant_evidence_rate`：最终 claims 绑定的证据中主体/日期不匹配比例；
- `budget_duplication_rate`：同 turn 重复 provider/LLM 调用比例；
- `trace_continuity`：Q0、TaskFrame、假设、查询、EvidenceAtom、最终 claim 可串联比例。

## 9. 迁移与发布顺序

1. **Shadow（影子）**：TaskInterpreter 只生成 TaskFrame/Clarification trace，不改变现有路由；对真实长尾回放评估字段准确率和模板相似度。
2. **Consumer switch**：普通长尾先消费 TaskFrame；确定性头部保持原路径。
3. **Clarification gate**：仅对 blocking ambiguity 启用前置追问；保留用户跳过/默认 A 股的显式行为。
4. **Deep mode**：先对预测、归因、比较启用 2–4 假设循环；共享预算和 ledger 后再扩大范围。
5. **删除重复逻辑**：迁移完成后移除 knowledge→concept_definition 覆盖、无契约 generic bypass，以及 retrieval 命中反哺 broad query 的路径。

## 10. 方案取舍

- **全量 LLM-first**：理解能力强，但 provider 不可用时不可控，延迟/成本高；不适合作为所有头部路径默认。
- **本设计的 Hybrid Semantic Compiler**：把 LLM 放在最有价值的语义边界，代码钳制执行，兼顾长尾理解与可回归性。
- **全量 Deep Research**：证据更完整，但简单问题被拖慢、预算放大；因此只对复杂 task frame 触发。

这套分层可迁移到客服、法律检索和代码 agent：模型负责把自然语言编译成任务，工具负责增量取证，出口负责证明“回答了什么”，而不是用入口 prompt 逼模型套格式。
