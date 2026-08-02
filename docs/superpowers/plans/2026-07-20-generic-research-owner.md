# Generic Research Owner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让未命中专项 Skill 的长尾问题由受约束的 GenericResearchOwner 主导研究闭环，而不是由固定 Ask 管线先跑、Agent 末尾补搜。

**Architecture:** 用 `ResearchTaskContract` 定义用户目标、required outputs、证据要求、能力白名单和研究档位；用共享 `ResearchRunContext` 串联 deadline、QueryLedger、LLMCallLedger 和 ProviderTrace。Generic Owner 通过类型化工具循环收集 observation，由确定性 completion gate 决定完成或 gap，再交给 grounding gate 和动态 Presenter。

**Tech Stack:** Python 3.11、dataclasses、现有 `ResearchDeadline`/`QueryLedger`/`LLMCallLedger`、`ProviderTrace`、`AnswerSpec`/`EvidenceAtom`、pytest；不引入新的 Agent 框架。

---

## 文件地图

- Create: `intelligence/services/generic_research_owner.py`：任务契约驱动的单 Owner 状态机。
- Modify: `intelligence/services/research_contract.py`：任务契约、required output、研究档位和共享运行上下文。
- Modify: `intelligence/services/provider_observability.py`：给 ProviderTrace 增加可选 parent run/step 标识，保持旧序列化字段兼容。
- Modify: `intelligence/services/agent_research.py`：把现有工具 runner 适配成 typed `ToolObservation`，保留循环底层执行能力。
- Create: `intelligence/services/research_tool_registry.py`：能力、输入输出、成本和 runner 的白名单注册表。
- Modify: `intelligence/services/ask.py`：Owner 路径、工具适配、结果水化和 legacy Skill 路径分界。
- Modify: `intelligence/services/conversation_orchestrator.py`：无 Owner 时提前交给 Generic Owner，并传递单一运行上下文。
- Modify: `intelligence/services/turn_controller.py`：生成/校验长尾任务契约所需字段。
- Modify: `intelligence/services/retrieval_planner.py`：移除独立 LLM 控制角色，保留确定性 provider metadata/钳制工具。
- Modify: `intelligence/services/answer_model.py`：completion gate 投影和动态 presentation profile。
- Modify: `intelligence/services/ask_synthesis.py`：只合成 completion gate 允许的公开 claim。
- Test: `intelligence/tests/test_generic_research_owner.py`：状态机、白名单、完成度和停止条件。
- Test: `intelligence/tests/test_agent_research.py`：工具适配和既有 loop 回归。
- Test: `intelligence/tests/test_conversation_orchestrator.py`：无 Owner 的入口、trace 和预算。
- Create: `intelligence/tests/fixtures/long_tail_cases.json`：版本化长尾题集元数据，不存密钥或大数据。

## Task 1: 定义任务契约和 required output 状态

**Files:**
- Modify: `intelligence/services/research_contract.py`
- Create: `intelligence/tests/test_generic_research_owner.py`

- [ ] **Step 1: 写契约 round-trip 测试**

```python
def test_research_task_contract_round_trips_required_outputs():
    contract = ResearchTaskContract(
        task_id="t1",
        question="科创50的支撑位在哪",
        subject="科创50",
        subject_kind="index",
        required_outputs=(
            RequiredOutput("support_levels", "支撑区间", ("market_ohlcv",), True),
            RequiredOutput("as_of", "数据截止日", ("market_ohlcv",), True),
        ),
        allowed_capabilities=("market_data",),
        research_tier="quick",
        presentation_profile="calculation",
    )
    assert ResearchTaskContract.from_dict(contract.to_dict()) == contract
```

- [ ] **Step 2: 增加契约类型**

实现 `RequiredOutput(id, description, evidence_types, required)`、`OutputStatus(output_id, status, evidence_ids, gap)`、`ResearchPolicy(tier, max_steps, total_seconds, synthesis_reserve)`、`ResearchTaskContract` 和 `ResearchRunContext(contract, deadline, policy, query_ledger, llm_ledger, trace_parent_id)`。`from_dict()` 对未知档位、空 id、未注册 capability 返回 `ResearchContractError`。

- [ ] **Step 3: 运行契约测试**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py -k 'contract'`

Expected: PASS；序列化字段和 required output 状态完整保留。

- [ ] **Step 4: 提交**

```bash
git add intelligence/services/research_contract.py intelligence/tests/test_generic_research_owner.py
git commit -m "feat: add long-tail research task contract"
```

## Task 2: 建立 Typed Tool Registry 和共享运行上下文

**Files:**
- Create: `intelligence/services/research_tool_registry.py`
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/services/research_contract.py`
- Test: `intelligence/tests/test_generic_research_owner.py`
- Test: `intelligence/tests/test_agent_research.py`

- [ ] **Step 1: 写白名单和去重测试**

```python
def test_tool_registry_rejects_unregistered_tool():
    registry = default_tool_registry(fake_tools())
    with pytest.raises(UnknownResearchTool):
        registry.resolve("shell_exec")

def test_same_query_is_single_flight_in_owner_context():
    context = make_run_context()
    assert context.query_ledger.claim("web_search", "科创50 新闻", "limit=5")
    assert not context.query_ledger.claim("web_search", "科创50 新闻", "limit=5")
```

- [ ] **Step 2: 实现 `ToolSpec` 和 `ToolObservation`**

`ToolSpec` 保存 `name/capability/input_schema/output_schema/cost/freshness/runner`；`ToolObservation` 保存公开 evidence、内部 locator、ProviderTrace、typed gaps、query fingerprint 和 evidence hashes。registry 的 `resolve()` 只返回白名单工具。

- [ ] **Step 3: 适配现有工具**

把 `build_default_tools()`、`build_graph_tools()`、market data、L3 和 news/web runner 封装为 registry entries。每次 runner 只接收 `ResearchRunContext` 派生的 `AgentToolContext`，不得内部创建新的总 deadline。

- [ ] **Step 4: 运行工具测试**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_agent_research.py -k 'tool or ledger or context'`

Expected: PASS；非法工具不执行，重复 query 不发第二次外呼，已有 agent loop 测试保持通过。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/research_tool_registry.py intelligence/services/research_contract.py intelligence/services/agent_research.py intelligence/tests/test_generic_research_owner.py intelligence/tests/test_agent_research.py
git commit -m "feat: add typed research tool registry and shared context"
```

## Task 2a: 给 ProviderTrace 增加父子 step 可观测字段

**Files:**
- Modify: `intelligence/services/provider_observability.py`
- Test: `intelligence/tests/test_p1b_runtime.py`

- [ ] **Step 1: 写向后兼容测试**

```python
def test_provider_trace_parent_fields_are_optional_and_round_trip():
    trace = ProviderTrace("web", "web_search", "success", parent_id="run-1", step_id="s-1")
    raw = trace.to_dict()
    assert raw["parent_id"] == "run-1"
    assert ProviderTrace.from_dict(raw).step_id == "s-1"
    assert ProviderTrace("web", "web_search", "success").parent_id is None
```

- [ ] **Step 2: 增加字段与 from_dict**

在 frozen dataclass 末尾增加 `parent_id: str | None = None`、`step_id: str | None = None`，`to_dict()` 保持旧字段不丢失，新增 `from_dict()` 对旧 trace 缺字段使用 `None`。

- [ ] **Step 3: 运行测试并提交**

Run: `python3 -m pytest -q intelligence/tests/test_p1b_runtime.py -k 'provider_trace or trace'`

Expected: PASS。

```bash
git add intelligence/services/provider_observability.py intelligence/tests/test_p1b_runtime.py
git commit -m "feat: add parent step identifiers to provider traces"
```

## Task 3: 实现 GenericResearchOwner 状态机和确定性 completion evaluator

**Files:**
- Create: `intelligence/services/generic_research_owner.py`
- Modify: `intelligence/services/answer_model.py`
- Test: `intelligence/tests/test_generic_research_owner.py`

- [ ] **Step 1: 写 finish 不可信和提前停止测试**

```python
def test_llm_finish_true_is_rejected_when_required_output_is_missing():
    result = run_owner(contract=contract_with_required("support_levels"), actions=[finish(True)])
    assert result.completion.status == "gap"
    assert result.completion.outputs[0].status == "missing"

def test_two_steps_without_new_evidence_stop_with_no_information_gain():
    result = run_owner(actions=[web_empty(), web_empty(), web_empty()])
    assert result.stop_reason == "no_information_gain"
    assert result.step_count == 2
```

- [ ] **Step 2: 实现循环接口**

```python
def run_generic_research(
    contract: ResearchTaskContract,
    *,
    context: ResearchRunContext,
    registry: ResearchToolRegistry,
    decide: DecideAction,
) -> ResearchResult:
    ...
```

每步先校验 action 和 context，再调用工具、接受 EvidenceAtom、更新 `OutputStatus`。`finish(sufficient=True)` 只能作为建议；只有所有 required outputs fulfilled 或每个未完成项都有 gap 时结束。

- [ ] **Step 3: 实现 deterministic completion gate**

事实输出要求至少一个 accepted EvidenceAtom；派生计算要求输入 evidence ids 和 lineage；gap 必须包含 code、原因和补数条件。`missing` 必需项阻止完整答案。

- [ ] **Step 4: 运行状态机测试**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py`

Expected: PASS；LLM 不能绕过 completion gate，重复无增量动作按策略停止。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/generic_research_owner.py intelligence/services/answer_model.py intelligence/tests/test_generic_research_owner.py
git commit -m "feat: add constrained generic research owner loop"
```

## Task 4: 将无 Owner 入口切到 GenericResearchOwner

**Files:**
- Modify: `intelligence/services/turn_controller.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/services/retrieval_planner.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`
- Test: `intelligence/tests/test_generic_research_owner.py`

- [ ] **Step 1: 写入口顺序测试**

```python
def test_ownerless_long_tail_skips_fixed_pipeline(monkeypatch):
    calls = []
    for name in ("collect_market_snapshot", "collect_graph", "collect_evidence_index", "collect_wiki_rag"):
        original = getattr(evidence_providers, name)
        monkeypatch.setattr(evidence_providers, name, lambda *a, _name=name, **k: calls.append(_name))
    result = orchestrator.run_turn(
        conversation_id="c1", run_id="r1", assistant_message_id="m1",
        query="某公司最近怎么看", skill_mode="auto", selected_skill_ids=(),
    )
    assert any(step["name"] == "generic_research_owner" for step in load_trace("r1"))
    assert calls == []
```

- [ ] **Step 2: 生成保守长尾契约**

Controller 已有确定性 head/skill owner 时保持原路；没有 owner 时生成 `ResearchTaskContract`。契约生成失败时使用 `question_answer + evidence + counterpoint + gap` 的保守 required outputs，不启动全量固定 provider。

- [ ] **Step 3: 接入 Owner 并保留 Skill 快车道**

orchestrator 在 `answer_owner is None` 且非确定性 head 时直接调用 Generic Owner；Skill Owner 和 market technical 不经过 Generic Owner。Ask 只负责构造工具上下文和将 `ResearchResult` 水化为 AnswerSpec。

- [ ] **Step 4: 移除 retrieval planner 的第二个 LLM 控制点**

`retrieval_planner.py` 保留 `clamp_plan()` 和 provider metadata 给 registry 使用；不再在 generic path 调用 `plan_retrieval()`。旧兼容 CLI 的 rules 模式继续可用。

- [ ] **Step 5: 运行入口顺序测试**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_conversation_orchestrator.py -k 'ownerless or generic or fixed_pipeline or planner'`

Expected: PASS；长尾只由 Owner 决定第一步工具，确定性 head/Skill 回归不变。

- [ ] **Step 6: 提交**

```bash
git add intelligence/services/turn_controller.py intelligence/services/conversation_orchestrator.py intelligence/services/ask.py intelligence/services/retrieval_planner.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_generic_research_owner.py
git commit -m "feat: route ownerless turns through generic research owner"
```

## Task 5: 动态 Presenter 与两道出口门禁

**Files:**
- Modify: `intelligence/services/answer_model.py`
- Modify: `intelligence/services/ask_synthesis.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_generic_research_owner.py`
- Test: `intelligence/tests/test_answer_model.py`

- [ ] **Step 1: 写动态选段和 fail-closed 测试**

```python
def test_missing_output_never_gets_filled_by_base_finance_template():
    result = render_owner_result(missing=("counterpoint",))
    assert "客户验证" not in result.text
    assert "证据缺口" in result.text

def test_grounding_failure_after_completion_is_fail_closed():
    result = render_owner_result(grounding_passed=False)
    assert result.phase == "evidence_gap_fallback"
    assert result.answer_spec.presentation_kind == "evidence_gap"
```

- [ ] **Step 2: 实现 presentation profiles**

按 `calculation/comparison/event/explanation/general` 选择段落；只投影 fulfilled outputs 和业务化 gaps。Agent transcript、provider 计数、内部路径和 raw quality issue 进入 Inspector。

- [ ] **Step 3: 固定门禁顺序**

orchestrator 先调用 completion gate，再调用现有 grounding validator/judge。grounding 失败时保留已验证 claims 和 gaps，不启动无约束修订轮。

- [ ] **Step 4: 运行出口测试**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_answer_model.py -k 'presentation or completion or grounding or gap'`

Expected: PASS；没有证据的段落不会由 Base Finance 模板自动补齐。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/answer_model.py intelligence/services/ask_synthesis.py intelligence/services/conversation_orchestrator.py intelligence/tests/test_generic_research_owner.py intelligence/tests/test_answer_model.py
git commit -m "fix: enforce task completion before grounded presentation"
```

## Task 6: 统一预算、trace 和研究档位

**Files:**
- Modify: `intelligence/services/research_contract.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/services/generic_research_owner.py`
- Test: `intelligence/tests/test_generic_research_owner.py`
- Test: `intelligence/tests/test_p1b_runtime.py`

- [ ] **Step 1: 写档位和合成保留测试**

```python
def test_quick_tier_has_three_tool_steps_and_synthesis_reserve():
    context = make_run_context(tier="quick")
    assert context.policy.max_steps == 3
    assert context.deadline.synthesis_timeout(context.policy.total_seconds) >= 20

def test_owner_tool_trace_keeps_parent_run_and_step_id():
    result = run_owner()
    assert all(trace.parent_id == result.run_id for trace in result.traces)
```

- [ ] **Step 2: 实现 `ResearchPolicy` 和 quick/standard/deep policy**

在 `research_contract.py` 定义 `ResearchPolicy(tier, max_steps, total_seconds, synthesis_reserve)`；使用 quick=3 步/30 秒、standard=6 步/90 秒、deep=12 步/240 秒；所有档位保留至少 20 秒或总预算 20% 的 synthesis reserve。Owner、tool、judge 和 composer 只派生子 deadline。

- [ ] **Step 3: 串联统一账本和 trace**

每个 owner step 写 parent run id、task contract version、tool、normalized query、预算前后值、evidence hashes、fulfillment 变化和 stop reason。`QueryLedger` 在工具实际外呼前 claim，失败不写成功缓存。

- [ ] **Step 4: 运行运行时测试**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_p1b_runtime.py -k 'budget or deadline or trace or query'`

Expected: PASS；不存在重复总预算、越过 synthesis reserve 或断裂 trace。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/research_contract.py intelligence/services/conversation_orchestrator.py intelligence/services/agent_research.py intelligence/services/generic_research_owner.py intelligence/tests/test_generic_research_owner.py intelligence/tests/test_p1b_runtime.py
git commit -m "fix: unify generic owner budgets and traces"
```

## Task 7: 长尾基准集、回归和真实 E2E

**Files:**
- Create: `intelligence/tests/fixtures/long_tail_cases.json`
- Modify: `intelligence/tests/test_generic_research_owner.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `docs/superpowers/plans/2026-07-20-generic-research-owner.md`

- [ ] **Step 1: 建立最小版本化题集**

题集至少包含：结构化取数、技术计算、当前事件、多对象比较、因果解释、产业链探索、反方检索、不可得数据、连续追问和明确 deep 请求；每题登记 required outputs、允许工具、最低证据、预期 gap、tier 和禁止模板。

- [ ] **Step 2: 运行 mocked benchmark**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py -k 'benchmark'`

Expected: 每题均能判断 completion/gap，且无固定管线误调用、重复 query 或控制面泄漏。

- [ ] **Step 3: 运行定向回归**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_agent_research.py intelligence/tests/test_answer_model.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_p1b_runtime.py`

Expected: 新增失败为 0；既有宿主环境失败与 baseline 分开记录。

- [ ] **Step 4: 运行全量测试和静态检查**

Run: `python3 -m compileall -q intelligence/services && python3 -m pytest -q intelligence/tests && git diff --check`

Expected: 编译和 diff 检查通过；全量结果完整记录，不能用“多数通过”替代。

- [ ] **Step 5: 运行临时 runtime E2E**

对未命中 Skill 的问题、重复追问、当前事件、结构化行情和不可得数据分别调用 Conversation API。检查正文、task contract、owner steps、ProviderTrace、budget ledger、SSE 阶段、completion/gap、grounding 和 latency。

- [ ] **Step 6: 写验收记录并提交**

```bash
git add intelligence/tests/fixtures/long_tail_cases.json intelligence/tests/test_generic_research_owner.py intelligence/tests/test_conversation_orchestrator.py docs/superpowers/plans/2026-07-20-generic-research-owner.md
git commit -m "docs: record generic research owner benchmark"
```
