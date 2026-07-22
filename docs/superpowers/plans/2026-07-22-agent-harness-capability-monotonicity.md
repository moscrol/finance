# Agent Harness 能力单调性与连续主循环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让未命中 skill 的金融长尾问题默认保留模型任务所有权，并证明数据库、工具、证据约束和 verifier 加入后，同一底模的回答能力不低于裸模型。

**Architecture:** 保留技术位、精确行情等确定性 head；其他问题先生成一次性的 `TaskFrame`，再进入保留完整 message history 的 `AgentEpisode`。工具/RAG/数据库属于行动面，预算/权限/EvidenceAtom/时效/任务完成度属于治理面；最终回答由模型自然生成，verifier 只做定向删句、修复或明确 gap。

**Tech Stack:** Python 3.11、dataclasses、现有 `ResearchDeadline`、`QueryLedger`、`ProviderTrace`、`ResearchState`、pytest、隔离 runtime；不引入新 Agent 框架，不直接修改 canonical `8792`。

---

## 外部资料如何转化为本项目方法

| 来源 | 可直接采用的方法 | Workbench 落点 | 不照搬的部分 |
|---|---|---|---|
| Anthropic tools for agents | 少量高影响工具、高信号返回、可行动错误、真实多工具任务 eval | 收敛 `research_tool_registry.py`；工具支持摘要/详情；评测工具调用、错误和上下文成本 | 不以“工具越多越强”为目标 |
| `learn-claude-code` | 模型拥有同一条 `messages → LLM → tool_result → messages` 主循环；hook 围绕循环而非重写循环 | 重写 `agent_research.run_agent_loop()` 为连续 `AgentEpisode` | 不把教学项目代码直接复制进生产 |
| MinusX Claude Code 逆向 | 同一消息历史、模型主导搜索、todo/状态防止长任务漂移 | 完整 history + `ResearchState` 双轨；查询由任务/假设/gap 产生 | “代码搜索不需要 RAG”不适用于金融时效与审计 |
| ECC/X Shortform | progressive disclosure、context budget、限定子 Agent、能力 eval、最多数轮迭代检索 | skill 只常驻描述；按需加载正文；工具消融；检索循环设停止条件 | 不按 skill/agent 数量衡量智能，不把全部 MCP 常驻上下文 |
| Cranot guide | compact 时保留当前任务、决定、todo 和关键读取，清理陈旧结果 | 为 `AgentEpisode` 定义明确 compaction contract | 该仓库是指南，不作为 Claude 内部实现证据 |

这些资料的共同方法不是“多做路由”，而是：**模型拥有认知循环，Harness 提供行动空间和治理边界，评测证明 Harness 带来增益。**

---

## 行动总表

| 优先级 | 行动 | 主要文件 | 可验收交付物 | 完成标准 |
|---|---|---|---|---|
| P0 | 建立裸模型对照 | 新增 `scripts/capability_monotonicity.py`、`intelligence/eval/capability_monotonicity.py` | 20–30 题 bare/current/episode 三臂报告 | Harness 任务分不低于裸模型；事实、时效、可审计性更高 |
| P0 | 建立 TaskFrame 语义 SSOT | 新增 `task_frame.py`；收敛 `query_understanding.py`、`turn_controller.py`、`conversation_orchestrator.py` | 原问题、目标、主体、默认市场、时间、输出、歧义、证据政策一次成型 | 后续 route/contract/presentation 不再覆盖问题语义 |
| P0 | no-skill 默认通用 owner | `conversation_orchestrator.py`、`task_fulfillment.py` | 每个非 chat/clarify turn 都有 task contract 和 answer status | 不再因 lane=knowledge 跳过 Agent；禁止 unknown→complete |
| P0 | 连续 AgentEpisode | `agent_research.py`、`research_state.py`、`generic_research_owner.py` | 同一 message history 持续追加 assistant/tool result | 模型能看到完整行动历史；ResearchState 是 notebook 而非历史替代品 |
| P1 | 收敛工具与检索边界 | `research_tool_registry.py`、`closed_loop_retrieval.py`、`evidence_judge.py`、`evidence_window.py` | 4–6 个高信号金融工具、progressive result、可行动错误 | 未审核误召回不再污染下一轮 query；工具重叠减少 |
| P1 | 统一自然回答与 verifier | `ask_synthesis.py`、`llm_refine.py`、`answer_model.py`、`task_fulfillment.py` | `ResearchOutcome → natural answer → sentence verifier` | 不再用题型模板替代长尾回答；失败按句处理 |
| P1 | 一条 trace/预算账本 | `provider_observability.py`、`conversation_orchestrator.py`、`llm_refine.py` | episode、工具、LLM、query、证据、预算连续 trace | 能精确定位语义在哪一步丢失、预算在哪一步消耗 |
| P2 | 删除有损 seam | `conversation_orchestrator.py`、`retrieval_planner.py` | 删除二次理解、lane 覆盖 qtype、重复完成度真值 | head route 回归不变；长尾路径投影层减少 |
| P2 | 候选 runtime 验收 | 新验证文档、`canonical-8792-cutover.md` | 三臂真实 E2E 与回滚记录 | 用户批准前不合并 main、不切 8792 |

---

## Task 0：先建立能力单调性红线

**Files:**
- Create: `scripts/capability_monotonicity.py`
- Create: `intelligence/eval/capability_monotonicity.py`
- Modify: `scripts/semantic_acceptance.py`
- Test: `intelligence/tests/test_capability_monotonicity.py`
- Test: `intelligence/tests/test_semantic_acceptance.py`

- [x] **Step 1: 写三臂评测 fixture。**

每个 case 固定 `question、conversation_context、model、temperature、timeout、as_of`，分别保存：A 裸模型；B 当前 Workbench；C 连续 AgentEpisode。首批必须包含“昨天的反弹能持续多久”“目前市场的主线是什么”“一个没有现成 skill 的陌生题材怎么判断”。

- [x] **Step 2: 定义能力评分对象。**

```python
@dataclass(frozen=True)
class TaskCapabilityScore:
    directness: int
    coverage: int
    relevance: int
    truth_boundary: int
    usefulness: int
```

关键词检查仅作为协议门，不能计作能力分数。保存 `latency、llm_calls、tool_calls、fallback_reason`，用于解释质量变化。

- [x] **Step 3: 写非劣化断言。**

同一 case 若 `harness_score + 0.2 < bare_score`，标记 `capability_regression`；即使 HTTP 200、run completed、关键词齐全也必须失败。

- [x] **Step 4: 运行测试确认当前失败被捕获。**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q intelligence/tests/test_capability_monotonicity.py intelligence/tests/test_semantic_acceptance.py`

Expected: 当前“反弹持续多久”失败 run 被判为能力回归，不能靠新增关键词转绿。

---

## Task 1：建立 `TaskFrame` 单一语义事实源

**Files:**
- Create: `intelligence/services/task_frame.py`
- Modify: `intelligence/services/query_understanding.py`
- Modify: `intelligence/services/turn_controller.py`
- Modify: `intelligence/services/conversation_orchestrator.py:1360-1435,1608-1685,2124-2178`
- Test: `intelligence/tests/test_task_frame.py`
- Test: `intelligence/tests/test_turn_controller.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: 定义不可变 TaskFrame。**

```python
@dataclass(frozen=True)
class TaskFrame:
    raw_question: str
    user_goal: str
    subject: str | None
    subject_kind: str
    market_scope: str
    timeframe: str | None
    required_outputs: tuple[str, ...]
    assumptions: tuple[str, ...]
    ambiguities: tuple[str, ...]
    clarification_question: str | None
    evidence_policy: str
    confidence: float
```

默认金融市场为 A 股；`raw_question` 永不被 contextual query 覆盖。

- [ ] **Step 2: 合并规则与一次 LLM 对齐。**

规则负责明确实体、日期和高置信 head；LLM 只补 `user_goal、required_outputs、assumptions、ambiguities`。只有歧义会改变主体、工具或结论时追问一次，否则声明假设继续执行。

- [ ] **Step 3: 删除语义二次覆盖。**

后续 `TurnIntent、ResearchContract、route、retrieval、presentation` 只读取 TaskFrame；删除 `routing_envelope = understand_query(contextual_query)` 对 question type/subject 的再裁决。

- [ ] **Step 4: 删除 `knowledge → concept_definition`。**

lane 只表示执行策略，不能重写用户语义。“昨天的反弹能持续多久”必须保持市场持续性任务，而不是概念定义。

- [ ] **Step 5: 固定三个回归。**

断言 TaskFrame 默认 A 股、最近交易日可解析、subject 不是整句问题，并且 route/contract/verifier 共享同一个 `task_frame_hash`。

---

## Task 2：把 Generic Owner 改成连续 `AgentEpisode`

**Files:**
- Modify: `intelligence/services/agent_research.py:591-900`
- Modify: `intelligence/services/research_state.py`
- Modify: `intelligence/services/generic_research_owner.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_agent_research.py`
- Test: `intelligence/tests/test_generic_research_owner.py`

- [ ] **Step 1: 保存真实消息历史。**

```python
messages = [system_message, task_frame_message]
while budget.allows():
    assistant = complete(messages)
    messages.append(assistant)
    observation = execute_selected_tool(assistant)
    messages.append(observation.as_tool_message())
```

第二轮 LLM 必须看到第一轮 assistant/tool 消息；禁止只重发 system + 900 字摘要。

- [ ] **Step 2: 保留 ResearchState 双轨。**

`ResearchState` 继续保存假设、支持/反证、gap、required outputs 和 Evidence ID，用于审计与 compaction；它不再替代消息历史。

- [ ] **Step 3: 定义 compaction contract。**

只在上下文达到阈值时压缩；必须保留原问题、TaskFrame、当前决定、未解决 gap、关键 Evidence ID、工具调用和失败恢复记录。清理过期搜索正文，不清理任务和决策理由。

- [ ] **Step 4: no-skill 默认接管。**

除 chat/clarify、确定性 head 和用户显式 skill 外，Generic Owner 一律接管，不再依赖 lane 必须等于 `research`。Controller 不可用时仍进入通用 owner，而不是零 LLM 固定管线。

- [ ] **Step 5: 跑连续性测试。**

用 scripted completion 连续调用两个工具，断言完整 history、预算、重复查询拦截、白名单和 synthesis reserve 同时有效。

---

## Task 3：收敛工具面并阻断检索自污染

**Files:**
- Modify: `intelligence/services/research_tool_registry.py`
- Modify: `intelligence/services/closed_loop_retrieval.py`
- Modify: `intelligence/services/evidence_judge.py`
- Modify: `intelligence/services/evidence_window.py`
- Test: `intelligence/tests/test_closed_loop_retrieval.py`
- Test: `intelligence/tests/test_evidence_judge.py`
- Test: `intelligence/tests/test_evidence_window.py`

- [ ] **Step 1: 对 Agent 暴露少量深工具。**

优先形成 `market_snapshot、search_finance、fetch_primary_source、get_entity_context、get_relation_evidence`；DuckDB、RAG、web/news provider 保留在工具内部，避免重叠工具让模型选择困难。

- [ ] **Step 2: 查询只从 TaskFrame/假设/gap 产生。**

未通过相关性闸门的 narrow hit 不得成为 broad/counter query 的扩展词；被拒结果只留在审计 trace。

- [ ] **Step 3: 区分审计保留与回答可用。**

semantic judge 失败时进入 `unjudged` 桶；只有满足主体、时间和问题目标最低相关性的证据才进入回答窗口，否则 Agent 必须改写查询、换工具或报告 gap。

- [ ] **Step 4: 增加 progressive disclosure。**

工具默认返回短摘要、日期、来源类型、Evidence ID、cursor 和恢复建议；模型请求 detail 后才读取全文。工具错误必须包含 `error_type、what_was_tried、retry_allowed、suggested_change`。

- [ ] **Step 5: 运行工具消融。**

比较 bare、market-only、KB-only、web-only、all-tools；任何让平均相关性下降的工具从默认池移到按需能力。

---

## Task 4：统一自然回答、verifier 和答案状态

**Files:**
- Modify: `intelligence/services/ask_synthesis.py`
- Modify: `intelligence/services/llm_refine.py`
- Modify: `intelligence/services/answer_model.py`
- Modify: `intelligence/services/task_fulfillment.py`
- Test: `intelligence/tests/test_daily_agent_grounded.py`
- Test: `intelligence/tests/test_answer_model.py`
- Test: `intelligence/tests/test_task_fulfillment.py`

- [ ] **Step 1: Composer 同时看到原问题、TaskFrame、ResearchOutcome。**

DecisionBrief/claim registry 可以保留，但不能成为原问题的替代品；模型必须看到用户目标、默认假设和当前 gap。

- [ ] **Step 2: verifier 按句处理。**

拒绝某句时只删改对应句；不把整份长尾回答替换成日报、题材、概念或固定研究模板。LLM 完全不可用时才使用最小 verified-gap renderer。

- [ ] **Step 3: 允许安全的通用分析框架。**

当前事实没有证据时，模型可以输出明确标注的“通用判断框架”，但不得把它写成当前市场事实；同时列出需要补的实时数据。这保留裸模型解释力，又不突破真值边界。

- [ ] **Step 4: 统一 answer status。**

每个需要回答的 turn 都生成 contract；`answer_status` 只由 TaskFulfillment 产生，禁止 `unknown → complete`。transport/research/answer 三种状态继续分离。

---

## Task 5：统一 trace、预算并删除有损 seam

**Files:**
- Modify: `intelligence/services/provider_observability.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/services/llm_refine.py`
- Modify: `intelligence/services/retrieval_planner.py`
- Test: `intelligence/tests/test_provider_observability.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: 给每个事件统一身份。**

记录 `run_id、episode_id、parent_event_id、task_frame_hash、tool、query、reason、budget_before/after、result_count、evidence_ids`。

- [ ] **Step 2: planner/judge/composer 共用账本。**

每次 LLM 和工具调用都记录用途和预算；检索不得消费 synthesis reserve；重复查询按 tool/query/content hash 审计。

- [ ] **Step 3: 逐一删除被新结构替代的 seam。**

删除二次 `understand_query`、lane 覆盖 qtype、无 contract 的完成状态、从未审核 hit 自动扩展 query。每删一处先跑对应测试，避免一次性重写 3,600 行 orchestrator。

---

## Task 6：隔离 runtime 验收与发布门禁

**Files:**
- Create: `docs/verification/agent-harness-capability-monotonicity-2026-07-22.md`
- Modify: `docs/verification/agent-capability-monotonicity-2026-07-20.md`
- Modify: `docs/workbench/canonical-8792-cutover.md`

- [ ] **Step 1: 跑全量 intelligence 测试。**

Run: `env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q intelligence/tests`

Expected: 不新增失败；基线环境失败单列，不用 skip 掩盖。

- [ ] **Step 2: 候选 runtime 跑真实三臂 E2E。**

至少测试四题：反弹持续性、当前主线、陌生题材、美联储降息对 A 股影响。保存 bare/current/episode 的答案、trace、as_of、answer_status、工具调用和评分。

- [ ] **Step 3: 同时满足六个发布条件。**

1. no-skill 不套日报/题材/概念模板；
2. answer status 与用户可见答案一致；
3. 当前事实都有日期与 EvidenceAtom；
4. episode 减少语义丢失和重复检索；
5. Harness 平均任务分不低于裸模型；
6. 没有一题依靠关键词命中掩盖答非所问。

- [ ] **Step 4: 再申请合并和切换。**

候选 runtime 通过后才提交 review；合并 `main` 和切换 `8792` 仍须用户明确批准。

---

## 自审结论

- 本计划不重复已经完成的 P13 owner、Grounded Presenter 和预算修复，而是补齐 P13 未证明的四件事：裸模型非劣化、TaskFrame 单一语义事实源、连续消息历史、工具消融。
- 保留 RAG、结构化数据库、EvidenceAtom、ProviderTrace、权限和预算；它们属于行动面/治理面，不是问题根因。
- 不增加更多路由和 skill 来覆盖长尾；skill 只作为按需加载的策略知识或确定性能力。
- 本计划只新增计划文档，不修改业务代码、不合并 `main`、不切换 canonical `8792`。
