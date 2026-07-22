from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from intelligence.services.query_understanding import understand_query
from intelligence.services.task_frame import build_task_frame


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
    assert "volume_confirmation" in frame.required_outputs
    assert "观察窗口未明确，先按未来五个交易日评估" in frame.ambiguities
    assert frame.clarification_question is None
    assert frame.subject == "A股市场"
    assert frame.market_scope == "A股"
    assert frame.timeframe == "最近交易日"
    assert frame.evidence_policy == "current_market_scenarios"
