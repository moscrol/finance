from __future__ import annotations

import pytest

from intelligence.services.evidence_capabilities import (
    runtime_capabilities_for_frame,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_control_core import TurnControlCore
from intelligence.services.turn_controller import TurnDecision


def _financial_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="昨天的反弹能持续多久",
        user_goal="判断反弹持续性",
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

    result = TurnControlCore(legacy_decide=fake_legacy).control(
        frame.raw_question
    )

    assert result.needs_retrieval is True
    assert result.contract_required is True
    assert result.terminal_kind == "research"
    assert {"market_data", "news_search"}.issubset(result.capabilities)


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
    ("evidence_policy", "required_outputs", "expected"),
    (
        ("current_fact_evidence", ("fact_value",), {"market_data"}),
        (
            "theme_tracking_evidence",
            ("change_summary",),
            {"graph_lookup", "news_search"},
        ),
        (
            "source_critique_evidence",
            ("claim_summary",),
            {"evidence_lookup", "web_search"},
        ),
        (
            "comparable_multi_source_evidence",
            ("limits_of_analogy",),
            {"kb_search", "graph_lookup", "evidence_lookup", "web_search"},
        ),
        (
            "conditional_thesis_evidence",
            ("conditional_thesis",),
            {"market_data", "evidence_lookup"},
        ),
    ),
)
def test_runtime_capability_projection_uses_registry_namespace(
    evidence_policy: str,
    required_outputs: tuple[str, ...],
    expected: set[str],
) -> None:
    frame = TaskFrame(
        raw_question="请给出当前金融判断",
        user_goal="形成直接判断",
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
