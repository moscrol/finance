# Agent Capability Monotonicity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline execution with task-by-task checkpoints. The worktree is already isolated at `/Users/a77/.codex/worktrees/finance-architecture-p13`.

**Goal:** 让长尾研究在工具、证据和 verifier 加入后保持或提升裸模型能力，修复 ResearchState 断裂、完成语义失真、模板化出口和超时降级，同时保留头部确定性路径的真值硬门。

**Architecture:** 新增 turn-scoped `ResearchState` 作为 generic Agent、完成评估和自然语言出口的单一认知状态；`TurnIntent`、`ResearchTaskContract` 和 `AnswerSpec` 作为兼容投影。自然语言统一走 Grounded Composer→事实/因果 verifier→一次定向 repair，失败直接使用已验证 DecisionBrief 的确定性 renderer，不再调用旧 marker LLM fallback。

**Tech Stack:** Python 3、dataclass、FastAPI/SSE 现有 run/artifact 协议、pytest、现有 GLM provider、DuckDB/本地 evidence provider。

---

## Task 1: 建立 ResearchState 和三维完成语义

**Files:**
- Create: `intelligence/services/research_state.py`
- Modify: `intelligence/services/research_contract.py:469-543`
- Modify: `intelligence/services/generic_research_owner.py:22-140`
- Test: `intelligence/tests/test_research_state.py`
- Test: `intelligence/tests/test_generic_research_owner.py`

- [ ] **Step 1: 写失败测试**

在 `test_research_state.py` 添加：

```python
def test_state_tracks_hypothesis_support_counter_and_gap():
    state = ResearchState.from_contract(contract)
    state.add_hypothesis("h1", "风险偏好收缩是主要机制", kind="mechanism")
    state.add_evidence(
        EvidenceObservation(
            evidence_id="e1", tool="market_data", title="周窗口",
            detail="4/5 交易日下跌", source="local", source_date="2026-07-17",
            supports=("h1",), contradicts=(), evidence_tier="L4",
        )
    )
    state.add_gap("external_trigger", "外部触发事件未对齐", blocks=("cause_attribution",))
    assert state.hypotheses[0].supporting_evidence == ("e1",)
    assert state.gaps[0].gap_id == "external_trigger"

def test_causal_question_is_partial_when_external_trigger_is_missing():
    state = state_with_market_mechanism_only()
    report = state.evaluate_completion()
    assert report.causal_adequacy == "partial"
    assert report.task_coverage == "partial"
    assert report.status == "partial"

def test_factual_completion_does_not_imply_causal_completion():
    state = state_with_market_mechanism_only()
    report = state.evaluate_completion()
    assert report.factual_grounding == "fulfilled"
    assert report.causal_adequacy != "fulfilled"
    assert report.status != "completed"
```

- [ ] **Step 2: 运行失败测试**

运行：

```bash
python3 -m pytest -q intelligence/tests/test_research_state.py intelligence/tests/test_generic_research_owner.py
```

预期：新模块导入失败或 `ResearchState` 未定义。

- [ ] **Step 3: 实现状态对象**

在 `research_state.py` 定义冻结的 `EvidenceObservation`、可变的 `HypothesisState`、`ResearchGap`、`CompletionState` 和 `ResearchState`。`ResearchState.from_contract()` 从 `ResearchTaskContract` 建立任务边界；`add_evidence()` 去重 evidence ID 并维护支持/反驳关系；`evaluate_completion()` 分别计算事实绑定、因果充分性和任务覆盖，只有三者全部 fulfilled 才返回 completed。

在 `research_contract.py` 增加 `ResearchRunContext.state` 的可选引用和 `ResearchTaskContract.presentation_profile` 的 `methodology/general/finance` 值校验，但不删除现有序列化字段。

在 `generic_research_owner.py` 将 `CompletionReport` 改为从 `ResearchState.evaluate_completion()` 投影；保留旧 `to_dict()` 字段，新增三维状态，避免 API 破坏。

- [ ] **Step 4: 运行测试**

运行同一 pytest 命令，预期所有新测试和已有 generic owner 测试通过。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/research_state.py intelligence/services/research_contract.py intelligence/services/generic_research_owner.py intelligence/tests/test_research_state.py intelligence/tests/test_generic_research_owner.py
git commit -m "feat: add turn-scoped research state and completion semantics"
```

## Task 2: 让 Agent loop 消费并更新 ResearchState

**Files:**
- Modify: `intelligence/services/agent_research.py:109-160,396-670`
- Modify: `intelligence/services/generic_research_owner.py:142-245`
- Test: `intelligence/tests/test_agent_research.py`

- [ ] **Step 1: 写失败测试**

添加：

```python
def test_agent_prompt_contains_hypothesis_gap_and_evidence_state():
    captured = []
    result = run_agent_loop(
        "test question",
        tools={"kb_search": lambda query: ([], "empty", empty_trace())},
        steps_budget=1,
        total_seconds=5,
        complete_fn=capture_complete(captured),
    )
    prompt = captured[0][1]
    assert "当前候选假设" in prompt
    assert "未解决缺口" in prompt
    assert "支持/反驳" in prompt

def test_empty_results_stop_only_when_state_has_no_information_gain():
    result = run_agent_loop(
        "test question",
        tools={"kb_search": lambda query: ([], "empty", empty_trace())},
        steps_budget=2,
        total_seconds=5,
        complete_fn=finish_after_empty_complete(),
    )
    assert result.stop_reason == "no_information_gain"
    assert result.state_revision >= 1

def test_agent_result_preserves_decision_brief_inputs():
    result = run_agent_loop(
        "test question",
        tools={"kb_search": lambda query: ([sample_evidence()], "hit", success_trace())},
        steps_budget=1,
        total_seconds=5,
        complete_fn=finish_with_assessment_complete(),
    )
    assert result.research_state is not None
    assert result.research_state.assessment
```

- [ ] **Step 2: 运行失败测试**

```bash
python3 -m pytest -q intelligence/tests/test_agent_research.py
```

预期：`AgentLoopResult` 没有 state/revision，prompt 没有状态字段。

- [ ] **Step 3: 实现状态注入和增量更新**

给 `AgentLoopResult` 增加 `research_state` 和 `state_revision`。`run_agent_loop()` 接收可选 `research_state`；每次工具返回后把 `AgentEvidence` 转换为 `EvidenceObservation`，更新 state。`_transcript_block()` 改成 `_research_state_block()`：先输出问题边界、候选假设、支持/反驳 evidence、gaps，再附最近两步工具摘要；单步 observation 仍截断，但不再承担全部记忆。

把 `no_information_steps >= 2` 改为：只有工具无证据且 state revision 未变化时才计数；新 gap、假设降级或冲突证据都算信息增益。

`finish` 时用 state assessment/gaps 合并 LLM 结果，不允许 LLM 的 `sufficient=true` 覆盖 state 的 partial。

- [ ] **Step 4: 运行测试**

```bash
python3 -m pytest -q intelligence/tests/test_agent_research.py intelligence/tests/test_generic_research_owner.py
```

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/agent_research.py intelligence/services/generic_research_owner.py intelligence/tests/test_agent_research.py
git commit -m "feat: make research loop hypothesis and gap aware"
```

## Task 3: 长尾 AnswerSpec 去除 generic theme 污染

**Files:**
- Modify: `intelligence/services/ask.py:1020-1300`
- Modify: `intelligence/services/answer_model.py:570-620,1610-1715`
- Modify: `intelligence/services/conversation_orchestrator.py:114-210`
- Test: `intelligence/tests/test_generic_research_owner.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: 写失败测试**

```python
def test_market_cause_generic_spec_has_no_industry_chain_schema():
    result = answer_query_for("这一周行情下跌的主要原因你认为是什么")
    assert result.answer_spec.research_spec.pack_id != "generic_theme"
    assert "industry_chain" not in result.answer_spec.research_spec.requested_sections

def test_general_long_tail_uses_question_profile_not_theme_research():
    result = answer_query_for("编排层为什么会导致模板化？")
    assert result.answer_spec.presentation_profile == "methodology"

def test_partial_causal_result_is_not_completed():
    result = answer_query_for("这一周行情下跌的主要原因你认为是什么")
    assert result.completion_report["status"] == "partial"
```

- [ ] **Step 2: 运行失败测试**

```bash
python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_conversation_orchestrator.py
```

- [ ] **Step 3: 实现 profile 投影**

在 `answer_model.py` 增加 `resolve_answer_profile(question_type, query)`：金融研究、方法论、回答质检、精确取数分别返回最小 requested sections。`_answer_generic_owner()` 不再无条件调用 `resolve_theme_research_spec()`；market cause 使用 causal profile，methodology 使用 explanation profile，只有题材/个股研究使用 theme/company schema。

保留 `presentation_kind="generic_research"` 向后兼容，但 renderer 使用 profile，不展示产业链/公司映射占位。

在 orchestrator 中将 `CompletionReport.status` 直接投影为 partial/completed；外部原因缺口不能被 optional output 绕过。

- [ ] **Step 4: 运行测试**

```bash
python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_answer_model.py
```

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/ask.py intelligence/services/answer_model.py intelligence/services/conversation_orchestrator.py intelligence/tests/test_generic_research_owner.py intelligence/tests/test_conversation_orchestrator.py
git commit -m "fix: keep long-tail answer profiles out of theme schema"
```

## Task 4: 统一 Grounded Composer，并把 DecisionBrief 设为最强 fallback

**Files:**
- Modify: `intelligence/services/ask_synthesis.py:1176-1535`
- Modify: `intelligence/services/llm_refine.py:733-845,1282-1325`
- Modify: `intelligence/services/answer_model.py:1530-1715`
- Modify: `intelligence/services/conversation_orchestrator.py:629-700`
- Test: `intelligence/tests/test_answer_model.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: 写失败测试**

```python
def test_composer_timeout_renders_decision_brief_not_marker_template():
    result = run_synthesis_with_provider_failure()
    assert "通用研究" not in result.synthesis
    assert "候选来源（待核验）" not in result.synthesis
    assert result.synthesis.startswith("本周行情下跌的主要原因")

def test_grounded_prompt_does_not_require_fixed_line_count_or_registry_copy():
    messages = build_grounded_messages_for("开放问题")
    text = "\n".join(item["content"] for item in messages)
    assert "正文硬上限 12" not in text
    assert "逐字复制" not in text

def test_invalid_engineering_term_is_warning_for_methodology():
    spec = methodology_spec("RAG 怎么做")
    issues = validate_llm_answer("RAG 是检索增强生成。", spec)
    assert not any(issue.severity == "error" for issue in issues)
```

- [ ] **Step 2: 运行失败测试**

```bash
python3 -m pytest -q intelligence/tests/test_answer_model.py intelligence/tests/test_conversation_orchestrator.py
```

- [ ] **Step 3: 简化 Grounded prompt**

将 `_SYNTHESIS_SYSTEM_PROMPT` 的事实边界、日期、买卖权限和引用要求保留为短规则；删除固定 claim 数、12 行、标题枚举、无 marker 过渡句和逐字 registry 复制。小节由 DecisionBrief 的 `core_tension` 和问题 profile 建议，不强制填满。

`claim_binding_revision_user_content()` 改为“仅修复 validator 指出的 evidence binding/越界句，保留其余措辞”，不再强制复制 registry 行。

- [ ] **Step 4: 改 fallback**

在 `answer_model.py` 增加 `render_decision_brief_fallback(DecisionBrief, profile)`：最多输出直接判断、最强证据、最大缺口三块；通过 `humanize()` 清除工具名、路径、证据计数和内部状态。

在 `promote_grounded_answer()` 和 `synthesize_prepared_answer()` 中，Grounded Composer/semantic judge/stream 任一失败都调用 DecisionBrief fallback，不再启动旧 `synthesize_messages_stream()` marker 路径。旧路径保留环境变量 shadow，不进入默认用户输出。

- [ ] **Step 5: 运行测试**

```bash
python3 -m pytest -q intelligence/tests/test_answer_model.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_generic_research_owner.py
```

- [ ] **Step 6: 提交**

```bash
git add intelligence/services/ask_synthesis.py intelligence/services/llm_refine.py intelligence/services/answer_model.py intelligence/services/conversation_orchestrator.py intelligence/tests/test_answer_model.py intelligence/tests/test_conversation_orchestrator.py
git commit -m "fix: make grounded composer and decision brief the only answer exit"
```

## Task 5: 按题型裁剪质量注入与工程词/标题门禁

**Files:**
- Modify: `intelligence/services/answer_quality.py:36-120`
- Modify: `intelligence/services/ask.py:1390-1455`
- Modify: `intelligence/services/answer_model.py:38-64,1009-1160`
- Modify: `intelligence/services/ask_synthesis.py:91-130`
- Test: `intelligence/tests/test_answer_quality.py`
- Test: `intelligence/tests/test_answer_model.py`

- [ ] **Step 1: 写失败测试**

```python
def test_methodology_quality_context_is_small_and_relevant():
    block = quality_context_for("methodology", "quick").to_prompt_block()
    assert len(block) < 1800
    assert "个股 12 切入路径" not in block

def test_finance_deep_context_keeps_hardness_and_gap_rules():
    block = quality_context_for("stock_deep_dive", "deep").to_prompt_block()
    assert "证据" in block and "反证" in block

def test_heading_is_warning_not_whole_answer_rejection():
    issues = validate_llm_answer("## 传导机制\n结论。", methodology_spec("方法论"))
    assert not any(issue.code == "disallowed_heading" and issue.severity == "error" for issue in issues)
```

- [ ] **Step 2: 实现选择性注入**

将固定清单拆成按 `question_type` 和 `research_tier` 的 blocks；每次最多注入三块，其余只保留在 lint/eval。方法论和 answer_review 不强制 Finance 五元素。

工程词门禁改为：金融正文中的内部路径、计数、artifact 名称仍 error；方法论题中的 `RAG/BM25/DuckDB` 允许，必要时通过 humanizer 做展示清洗。标题改为 warning + 清洗，不整行剔除带有正常论证的段落。

- [ ] **Step 3: 运行测试并提交**

```bash
python3 -m pytest -q intelligence/tests/test_answer_quality.py intelligence/tests/test_answer_model.py
git add intelligence/services/answer_quality.py intelligence/services/ask.py intelligence/services/answer_model.py intelligence/services/ask_synthesis.py intelligence/tests/test_answer_quality.py intelligence/tests/test_answer_model.py
git commit -m "fix: scope quality guidance and presentation warnings by question"
```

## Task 6: 实现缺口驱动 L3 和证据窗口预算

**Files:**
- Modify: `intelligence/services/ask_types.py:180-210`
- Modify: `intelligence/services/evidence_providers.py:120-180`
- Modify: `intelligence/services/agent_research.py:480-670`
- Modify: `intelligence/services/ask.py:1400-1590`
- Test: `intelligence/tests/test_l3_evidence.py`
- Test: `intelligence/tests/test_agent_research.py`
- Test: `intelligence/tests/test_evidence_providers.py`

- [ ] **Step 1: 写失败测试**

```python
def test_l3_is_requested_only_when_gap_blocks_hard_company_claim():
    state = state_with_gap("customer_validation", blocks=("company_relation",))
    assert should_request_l3(state) is True

def test_l3_is_not_requested_for_market_mechanism_without_company_claim():
    state = state_with_market_mechanism_only()
    assert should_request_l3(state) is False

def test_evidence_window_respects_total_budget_and_keeps_counterevidence():
    window = build_evidence_window(items, max_chars=1200)
    assert len(window.text) <= 1200
    assert window.counterevidence_ids
```

- [ ] **Step 2: 实现**

保留 `use_l3_lookup` 兼容开关，但默认由 `ResearchState` 的 blocking gap 决定；显式 CLI 开关仍可强制开启。新增 `should_request_l3(state)`。

新增 evidence window builder，按相关性、hardness、freshness、独立来源和假设覆盖排序，在总字符/token 预算内至少保留一条关键反证。不要按 provider 固定顺序拼接。

- [ ] **Step 3: 运行测试并提交**

```bash
python3 -m pytest -q intelligence/tests/test_l3_evidence.py intelligence/tests/test_agent_research.py intelligence/tests/test_evidence_providers.py
git add intelligence/services/ask_types.py intelligence/services/evidence_providers.py intelligence/services/agent_research.py intelligence/services/ask.py intelligence/tests/test_l3_evidence.py intelligence/tests/test_agent_research.py intelligence/tests/test_evidence_providers.py
git commit -m "feat: make l3 and evidence windows gap driven"
```

## Task 7: 增加能力单调性和 fallback 保真评测

**Files:**
- Create: `intelligence/eval/capability_monotonicity.py`
- Modify: `intelligence/tests/test_agent_eval.py`
- Modify: `intelligence/tests/test_auto_eval.py`
- Create: `intelligence/tests/fixtures/capability_monotonicity_cases.json`

- [ ] **Step 1: 写评测 fixtures 和失败测试**

fixture 至少包含：周下跌原因、方法论 RAG、关系题、缺 L3 客户题、个股长尾、Composer timeout。测试断言输出结构包含 `directness/task_coverage/grounding/fallback_fidelity/template_signature` 字段。

- [ ] **Step 2: 实现确定性指标**

`capability_monotonicity.py` 提供：

- `directness_score`：首段是否直接复述并回答问题目标；
- `task_coverage_score`：必需输出被 fulfilled 或明确 gap 覆盖；
- `grounding_score`：事实 claim 与 EvidenceAtom 的比例；
- `control_plane_leak_score`：工程词、路径、计数、候选状态泄漏；
- `template_signature`：标题/段落功能序列；
- `fallback_fidelity`：fallback 是否保留 DecisionBrief 的 direct_answer/core_tension。

支持最小 prompt vs Workbench 的配对结果，但不自动将语言多样性当质量；评测输出只做 advisory，不自动回灌生产 prompt。

- [ ] **Step 3: 运行测试并提交**

```bash
python3 -m pytest -q intelligence/tests/test_agent_eval.py intelligence/tests/test_auto_eval.py
git add intelligence/eval/capability_monotonicity.py intelligence/tests/test_agent_eval.py intelligence/tests/test_auto_eval.py intelligence/tests/fixtures/capability_monotonicity_cases.json
git commit -m "test: add capability monotonicity and fallback fidelity eval"
```

## Task 8: 真实 E2E、隔离 runtime 和交接

**Files:**
- Modify: `docs/workbench/canonical-8792-cutover.md`
- Create: `docs/verification/agent-capability-monotonicity-2026-07-20.md`
- Modify: `/Users/a77/agent-memory/20_projects/finance-workspace-private.md`

- [ ] **Step 1: 运行全套 intelligence 测试**

```bash
python3 -m pytest -q intelligence/tests
```

记录新失败与基线失败，不以“全绿”替代真实 E2E。

- [ ] **Step 2: 创建 clean detached runtime**

从本分支 clean commit 创建 `/Users/a77/.finance-runtime/finance-workspace-<sha>`，启动非 8792 隔离端口，健康检查通过后再运行真实 provider。

- [ ] **Step 3: 跑原问题和最小长尾矩阵**

至少运行：

```text
这一周行情下跌的主要原因你认为是什么
编排层为什么会导致模板化？
液冷和 PCB 谁在产业链上游？
某公司和某客户是否已确认合作？
科创50的支撑点位在哪
```

保存 run ID、runtime commit、answer artifact、report、decision brief、provider trace 和 fallback reason。

- [ ] **Step 4: 验收硬条件**

- market technical 零 LLM、数字和截止日正确；
- 长尾首段直接回答，不出现 generic theme、候选来源、空 marker；
- Composer 超时仍能交付 DecisionBrief 短答；
- causal gap 为 partial，不伪装 completed；
- 内部工程字段只进 Inspector，不进用户正文；
- 工具和写库权限未扩大。

- [ ] **Step 5: 写验证报告和交接**

在 verification 文档记录结果、已知缺口和是否可以切 8792；项目记忆只追加架构决策与运行 commit，不写聊天流水。未得到用户明确合并许可前，不合并 `main`。
