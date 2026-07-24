from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from intelligence.services.query_understanding import QueryEnvelope, understand_query
from intelligence.services.task_frame import TaskFrame, build_task_frame


def test_rebound_horizon_builds_stable_a_share_task_frame() -> None:
    question = "昨天的反弹能持续多久"

    envelope = understand_query(question)
    frame = envelope.task_frame

    assert frame is not None
    assert frame.raw_question == question
    assert frame.question_type == "market_forecast"
    assert frame.market_scope == "A股"
    assert frame.subject == "A股市场"
    assert frame.subject != question
    assert frame.timeframe == "最近交易日"
    assert {
        "current_baseline",
        "duration_assessment",
        "continuation_conditions",
        "invalidation_conditions",
        "evidence_boundary",
    }.issubset(frame.required_outputs)
    assert frame.to_dict()["task_frame_hash"] == frame.task_frame_hash
    with pytest.raises(FrozenInstanceError):
        frame.market_scope = "美股"  # type: ignore[misc]


def test_llm_alignment_can_only_supplement_code_owned_semantics() -> None:
    question = "昨天的反弹能持续多久"
    envelope = understand_query(question)
    content = """{
      "user_goal": "判断本轮反弹大致还能延续多久",
      "required_outputs": ["volume_confirmation"],
      "assumptions": ["把反弹理解为最近一个交易日的市场修复"],
      "ambiguities": ["观察窗口未明确，先按未来五个交易日评估"],
      "subject": "美股",
      "market_scope": "美股",
      "timeframe": "2020-01-01",
      "evidence_policy": "no_evidence"
    }"""

    frame = build_task_frame(
        question,
        envelope,
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert frame.user_goal == "判断本轮反弹大致还能延续多久"
    assert "volume_confirmation" not in frame.required_outputs
    assert "观察窗口未明确，先按未来五个交易日评估" in frame.ambiguities
    assert frame.clarification_question is None
    assert frame.subject == "A股市场"
    assert frame.market_scope == "A股"
    assert frame.timeframe == "最近交易日"
    assert frame.evidence_policy == "current_market_scenarios"


def test_llm_alignment_cannot_append_unowned_required_output() -> None:
    question = "固态电池产业链怎么分"
    envelope = understand_query(question)
    content = """{
      "user_goal": "梳理固态电池产业链",
      "required_outputs": ["llm_invented_output"],
      "assumptions": [],
      "ambiguities": []
    }"""

    frame = build_task_frame(
        question,
        envelope,
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert "chain_mapping" in frame.required_outputs
    assert "llm_invented_output" not in frame.required_outputs


@pytest.mark.parametrize(
    ("question", "required_outputs"),
    (
        (
            "低空经济和商业航天，未来一个月哪个更可能成为A股主线，为什么",
            {
                "comparison_conclusion",
                "supporting_evidence",
                "counterpoint",
                "invalidation_conditions",
            },
        ),
        (
            "如果电力板块涨停家数很多但成交占比和核心股承接下降，还能算主线吗",
            {
                "direct_assessment",
                "causal_chain",
                "counterpoint",
                "verification_conditions",
            },
        ),
        (
            "一个没有历史胜率的新题材，应该如何判断它是主线候选还是一天噪音",
            {
                "method",
                "evidence_hierarchy",
                "failure_modes",
                "verification_path",
            },
        ),
        (
            "那它什么时候算失效",
            {"invalidation_conditions", "supporting_evidence"},
        ),
    ),
)
def test_task_frame_preserves_explicit_long_tail_output_shape(
    question: str,
    required_outputs: set[str],
) -> None:
    frame = understand_query(question).task_frame

    assert frame is not None
    assert required_outputs.issubset(frame.required_outputs)


@pytest.mark.parametrize(
    ("question_type", "evidence_policy", "required_outputs"),
    (
        (
            "quick_fact",
            "current_fact_evidence",
            {"fact_value", "as_of_date", "evidence_boundary"},
        ),
        (
            "theme_track",
            "theme_tracking_evidence",
            {"change_summary", "supporting_evidence", "tracking_signals"},
        ),
        (
            "kol_review",
            "source_critique_evidence",
            {"claim_summary", "evidence_assessment", "biases_and_gaps"},
        ),
        (
            "comparison_analog",
            "comparable_multi_source_evidence",
            {"comparison_dimensions", "key_differences", "limits_of_analogy"},
        ),
        (
            "trade_advice",
            "conditional_thesis_evidence",
            {"conditional_thesis", "risk_signals", "invalidation_conditions"},
        ),
    ),
)
def test_route_table_types_keep_explicit_task_frame_semantics(
    question_type: str,
    evidence_policy: str,
    required_outputs: set[str],
) -> None:
    frame = build_task_frame(
        "按这个问题给出直接判断",
        QueryEnvelope(
            question_type=question_type,
            subject_kind="unknown",
            subject=None,
            decision_goal="回答用户的金融问题",
            timeframe=None,
            matched_by="explicit",
            confidence=0.9,
        ),
    )

    assert frame.question_type == question_type
    assert frame.evidence_policy == evidence_policy
    assert required_outputs.issubset(frame.required_outputs)
    assert frame.question_type != "general_finance_qa"


def test_task_frame_keeps_question_type_independent_from_shared_evidence_policy() -> None:
    frame = TaskFrame(
        raw_question="寻找历史类比",
        user_goal="比较相似性与差异",
        subject="AI行情",
        subject_kind="theme",
        market_scope="A股",
        timeframe=None,
        required_outputs=("comparison_dimensions",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="comparable_multi_source_evidence",
        confidence=0.9,
        question_type="comparison_analog",
    )

    restored = TaskFrame.from_dict(frame.to_dict())

    assert frame.question_type == "comparison_analog"
    assert restored is not None
    assert restored.question_type == "comparison_analog"


def test_task_frame_restores_legacy_payload_without_explicit_question_type() -> None:
    frame = build_task_frame(
        "2015互联网泡沫和现在AI行情有什么异同",
        QueryEnvelope(
            question_type="comparison_analog",
            subject_kind="theme",
            subject="AI行情",
            decision_goal="比较历史类比",
            timeframe=None,
            matched_by="explicit",
            confidence=0.9,
        ),
    )
    legacy_payload = frame.to_dict()
    legacy_payload.pop("question_type")

    restored = TaskFrame.from_dict(legacy_payload)

    assert restored is not None
    assert restored.question_type == "comparison_analog"
