from __future__ import annotations

import json

import pytest

from intelligence.services.evidence_capabilities import (
    runtime_capabilities_for_frame,
)
from intelligence.services.research_contract import TurnIntent
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_control_core import (
    TurnControlCore,
    project_turn_decision,
)
from intelligence.services.turn_controller import TurnDecision


def _financial_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="昨天的反弹能持续多久",
        user_goal="判断反弹持续性",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("duration_assessment", "evidence_boundary"),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )


def test_market_long_tail_is_research_with_contract_and_retrieval() -> None:
    result = TurnControlCore().control("昨天的反弹能持续多久")

    assert result.terminal_kind == "research"
    assert result.needs_retrieval is True
    assert result.contract_required is True
    assert result.task_frame.market_scope == "A股"
    assert result.task_frame.raw_question == "昨天的反弹能持续多久"


def test_control_core_preserves_conversation_context_outside_task_frame() -> None:
    context = (
        "user: 昨天的反弹能持续多久\n"
        "assistant: 基准判断是短周期修复。"
    )

    result = TurnControlCore().control(
        "那它什么时候算失效",
        context=context,
    )

    assert result.conversation_context == context
    assert "conversation_context" not in result.task_frame.to_dict()


def test_market_forecast_runtime_uses_current_structure_without_causal_web_tools() -> (
    None
):
    result = TurnControlCore().control("昨天的反弹能持续多久")

    capabilities = runtime_capabilities_for_frame(result.task_frame)

    assert capabilities == ("market_data", "mainline_context")


def test_market_cause_runtime_keeps_time_aligned_news_and_web_tools() -> None:
    result = TurnControlCore().control("这一周行情下跌的主要原因是什么")

    capabilities = runtime_capabilities_for_frame(result.task_frame)

    assert "market_data" in capabilities
    assert "news_search" in capabilities
    assert "web_search" in capabilities


def test_plain_chat_is_non_research() -> None:
    result = TurnControlCore().control("你好")

    assert result.execution_route == "chat"
    assert result.terminal_kind == "non_research"
    assert result.contract_required is False
    assert result.needs_retrieval is False


def test_stable_knowledge_is_non_research() -> None:
    result = TurnControlCore().control("卫星互联网是什么")

    assert result.task_frame.evidence_policy == "stable_knowledge"
    assert result.terminal_kind == "non_research"
    assert result.needs_retrieval is False
    assert result.capabilities == ()


def test_definition_plus_current_market_fact_remains_research() -> None:
    result = TurnControlCore().control("什么是双红，现在哪些板块双红")

    assert result.task_frame.evidence_policy == "stable_knowledge"
    assert result.terminal_kind == "research"
    assert result.needs_retrieval is True
    assert "mainline_context" in result.capabilities


def test_financial_frame_cannot_be_downgraded_to_zero_retrieval() -> None:
    frame = _financial_frame()

    def fake_legacy(*_args, **_kwargs):
        return TurnDecision(
            lane="chat",
            needs_retrieval=False,
            needs_memory=False,
            needs_template=False,
            question_type=frame.question_type,
            task_frame=frame,
        )

    result = TurnControlCore(legacy_decide=fake_legacy).control(frame.raw_question)

    assert result.needs_retrieval is True
    assert result.contract_required is True
    assert result.terminal_kind == "research"
    assert result.capabilities == ("market_data", "mainline_context")


def test_frozen_decision_projects_control_without_calling_controller_again() -> None:
    frame = _financial_frame()
    intent = TurnIntent(
        primary_subject=frame.subject,
        secondary_topics=(),
        question_type=frame.question_type,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        timeframe=frame.timeframe,
        required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )
    decision = TurnDecision(
        lane="chat",
        needs_retrieval=False,
        needs_memory=False,
        needs_template=False,
        question_type=frame.question_type,
        capabilities=("market_news",),
        task_frame=frame,
        turn_intent=intent,
    )

    result = project_turn_decision(
        decision,
        task_frame=frame,
        turn_intent=intent,
    )

    assert result.task_frame is frame
    assert result.turn_intent is intent
    assert result.terminal_kind == "research"
    assert result.execution_route == "market_forecast"
    assert result.capabilities == ("market_data", "mainline_context")


def test_frozen_non_research_decision_is_not_upgraded_by_lexical_replanning() -> None:
    frame = TaskFrame(
        raw_question="当前市场主线是什么意思",
        user_goal="解释术语含义",
        question_type="concept_definition",
        subject="市场主线",
        subject_kind="concept",
        market_scope="A股",
        timeframe="",
        required_outputs=("definition",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="stable_knowledge",
        confidence=0.96,
    )
    decision = TurnDecision(
        lane="knowledge",
        needs_retrieval=False,
        needs_memory=False,
        needs_template=False,
        question_type=frame.question_type,
        task_frame=frame,
    )

    result = project_turn_decision(decision, task_frame=frame)

    assert result.terminal_kind == "non_research"
    assert result.needs_retrieval is False
    assert result.capabilities == ()


def test_research_legacy_aliases_cannot_expand_task_frame_capabilities() -> None:
    frame = _financial_frame()
    legacy_capabilities = (
        "memory",
        "market_quote",
        "market_news",
        "web_fetch",
        "graph",
        "filings",
        "financials",
    )

    def fake_legacy(_query: str) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=True,
            needs_template=True,
            question_type=frame.question_type,
            capabilities=legacy_capabilities,
            task_frame=frame,
        )

    result = TurnControlCore(legacy_decide=fake_legacy).control(frame.raw_question)

    assert result.capabilities == ("market_data", "mainline_context")
    assert set(result.capabilities).isdisjoint(legacy_capabilities)


def test_clarification_is_not_reported_as_completed_research() -> None:
    result = TurnControlCore().control("这个反弹还能持续多久")

    assert result.execution_route == "clarify"
    assert result.terminal_kind == "clarification"
    assert result.contract_required is False
    assert result.needs_retrieval is False
    assert result.capabilities == ()
    assert result.clarification_questions


def test_pending_turn_intent_clarifies_once_and_preserves_task_semantics() -> None:
    core = TurnControlCore()
    first = core.control("这个反弹还能持续多久")

    assert first.turn_intent is not None
    assert first.turn_intent.pending_task_frame is not None
    assert (
        first.turn_intent.pending_task_frame["task_frame_hash"]
        == first.task_frame.task_frame_hash
    )

    resumed = core.control(
        "A股",
        previous_intent=first.turn_intent,
        previous_turn_id="msg-clarification",
    )

    assert resumed.terminal_kind == "research"
    assert resumed.clarification_questions == ()
    assert resumed.task_frame.raw_question == first.task_frame.raw_question
    assert resumed.task_frame.user_goal == first.task_frame.user_goal
    assert resumed.task_frame.required_outputs == first.task_frame.required_outputs
    assert resumed.turn_intent is not None
    assert resumed.turn_intent.pending_task_frame is None
    assert resumed.turn_intent.clarification_rounds == 1
    assert resumed.turn_intent.task_frame_hash == resumed.task_frame.task_frame_hash


def test_intent_projection_wins_over_unrelated_previous_frame() -> None:
    intent = TurnIntent(
        primary_subject="光模块",
        secondary_topics=(),
        question_type="theme_track",
        answer_owner="theme-research",
        comparison_entities=(),
        inherited_from_turn="msg-previous",
        timeframe="近一个月",
        required_outputs=("change_summary", "tracking_signals"),
    )

    def fake_legacy(_query: str) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=True,
            needs_template=True,
            turn_intent=intent,
        )

    result = TurnControlCore(legacy_decide=fake_legacy).control(
        "继续跟踪它",
        previous_frame=_financial_frame(),
    )

    assert result.task_frame.raw_question == "继续跟踪它"
    assert result.task_frame.question_type == "theme_track"
    assert result.task_frame.subject == "光模块"
    assert result.task_frame.timeframe == "近一个月"
    assert {"change_summary", "tracking_signals"}.issubset(
        result.task_frame.required_outputs
    )


def test_adapter_type_error_is_not_retried_as_a_different_call() -> None:
    calls = 0

    def broken_legacy(query: str) -> TurnDecision:
        nonlocal calls
        calls += 1
        raise TypeError(f"bug in adapter: {query}")

    try:
        TurnControlCore(legacy_decide=broken_legacy).control("市场怎么看")
    except TypeError as exc:
        assert "bug in adapter" in str(exc)
    else:  # pragma: no cover - the assertion above is the contract
        raise AssertionError("adapter TypeError must not be silently retried")
    assert calls == 1


@pytest.mark.parametrize(
    ("question_type", "lane", "evidence_policy"),
    (
        ("quick_fact", "knowledge", "current_fact_evidence"),
        ("theme_track", "research", "theme_tracking_evidence"),
        ("kol_review", "research", "source_critique_evidence"),
        (
            "comparison_analog",
            "research",
            "comparable_multi_source_evidence",
        ),
        ("trade_advice", "research", "conditional_thesis_evidence"),
    ),
)
def test_validated_route_projection_does_not_collapse_task_frame(
    question_type: str,
    lane: str,
    evidence_policy: str,
) -> None:
    def fake_legacy(_query: str) -> TurnDecision:
        return TurnDecision(
            lane=lane,  # type: ignore[arg-type]
            needs_retrieval=True,
            needs_memory=False,
            needs_template=lane == "research",
            question_type=question_type,
            subject="已验证主体",
            timeframe="最新可用日期",
            confidence=0.9,
        )

    result = TurnControlCore(legacy_decide=fake_legacy).control(
        "请按已验证路由处理这个请求"
    )

    assert result.task_frame.question_type == question_type
    assert result.task_frame.evidence_policy == evidence_policy
    assert result.execution_route == question_type


@pytest.mark.parametrize(
    ("query", "question_type", "required_output"),
    (
        ("科创50你认为反弹空间有多少", "market_technical", "technical_levels"),
        ("瑞华泰的合理估值", "valuation_estimate", "valuation_assessment"),
        ("目前市场的主线是什么", "market_watch", "direct_assessment"),
    ),
)
def test_acceptance_questions_keep_their_semantics_without_controller_llm(
    query: str,
    question_type: str,
    required_output: str,
) -> None:
    result = TurnControlCore().control(
        query,
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    assert result.terminal_kind == "research"
    assert result.task_frame.question_type == question_type
    assert required_output in result.task_frame.required_outputs


def test_comparative_mainline_decision_overrides_single_theme_defaults() -> None:
    result = TurnControlCore().control(
        "低空经济和商业航天，未来一个月哪个更可能成为A股主线，为什么",
        llm_complete=lambda _messages: pytest.fail(
            "explicit comparative decision must not depend on controller LLM"
        ),
    )

    assert result.execution_route == "comparison"
    assert result.task_frame.question_type == "comparison"
    assert result.task_frame.subject is None
    assert result.task_frame.timeframe == "未来一个月"
    assert result.task_frame.required_outputs == (
        "comparison_conclusion",
        "supporting_evidence",
        "counterpoint",
        "invalidation_conditions",
    )
    assert {"market_data", "mainline_context"}.issubset(result.capabilities)


@pytest.mark.parametrize(
    ("query", "question_type", "required_output", "coarse_output"),
    (
        ("300750是哪家公司", "quick_fact", "fact_value", "direct_assessment"),
        (
            "光伏最近一个月有什么新变化",
            "theme_track",
            "change_summary",
            "chain_mapping",
        ),
        (
            "这份高盛AI算力研报核心假设站得住吗",
            "kol_review",
            "evidence_assessment",
            "chain_mapping",
        ),
        (
            "2015互联网泡沫和现在AI行情有什么异同",
            "comparison_analog",
            "limits_of_analogy",
            "chain_mapping",
        ),
        (
            "宁德时代要不要止损",
            "trade_advice",
            "conditional_thesis",
            "direct_assessment",
        ),
    ),
)
def test_default_controller_preserves_fine_grained_route_frame(
    query: str,
    question_type: str,
    required_output: str,
    coarse_output: str,
) -> None:
    result = TurnControlCore().control(
        query,
        llm_complete=lambda _messages: pytest.fail(
            "validated fine-grained route must not depend on controller LLM"
        ),
    )

    assert result.task_frame.question_type == question_type
    assert required_output in result.task_frame.required_outputs
    assert coarse_output not in result.task_frame.required_outputs
    assert result.execution_route == question_type
    assert result.terminal_kind == "research"


@pytest.mark.parametrize(
    "question_type",
    ("quick_fact", "theme_track", "kol_review", "comparison_analog", "trade_advice"),
)
def test_default_controller_rebases_injected_validated_route_row(
    question_type: str,
) -> None:
    content = json.dumps(
        {
            "route_id": question_type,
            "subject": "已验证主体",
            "timeframe": "最新可用日期",
            "confidence": 0.95,
            "reason": "已验证路由行",
        },
        ensure_ascii=False,
    )
    result = TurnControlCore().control(
        "请按已验证路由处理这个请求",
        llm_complete=lambda _messages: (content, object(), "ok"),
    )

    assert result.task_frame.question_type == question_type
    assert result.execution_route == question_type
    assert result.task_frame.subject == "已验证主体"
    assert result.task_frame.timeframe == "最新可用日期"


@pytest.mark.parametrize(
    ("question_type", "evidence_policy", "required_outputs", "expected"),
    (
        ("quick_fact", "current_fact_evidence", ("fact_value",), {"market_data"}),
        (
            "theme_track",
            "theme_tracking_evidence",
            ("change_summary",),
            {"graph_lookup", "news_search"},
        ),
        (
            "kol_review",
            "source_critique_evidence",
            ("claim_summary",),
            {"evidence_lookup", "web_search"},
        ),
        (
            "comparison_analog",
            "comparable_multi_source_evidence",
            ("limits_of_analogy",),
            {"kb_search", "graph_lookup", "evidence_lookup", "web_search"},
        ),
        (
            "trade_advice",
            "conditional_thesis_evidence",
            ("conditional_thesis",),
            {"market_data", "evidence_lookup"},
        ),
    ),
)
def test_runtime_capability_projection_uses_registry_namespace(
    question_type: str,
    evidence_policy: str,
    required_outputs: tuple[str, ...],
    expected: set[str],
) -> None:
    frame = TaskFrame(
        raw_question="请给出当前金融判断",
        user_goal="形成直接判断",
        question_type=question_type,
        subject="已验证主体",
        subject_kind="unknown",
        market_scope="A股",
        timeframe="最新可用日期",
        required_outputs=required_outputs,
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy=evidence_policy,
        confidence=0.9,
    )

    capabilities = runtime_capabilities_for_frame(frame)

    assert expected.issubset(capabilities)
    assert set(capabilities).issubset(
        {
            "market_data",
            "mainline_context",
            "kb_search",
            "graph_lookup",
            "evidence_lookup",
            "news_search",
            "web_search",
            "l3_lookup",
        }
    )
