from __future__ import annotations

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.turn_control_core import TurnControlCore


RUNTIME_CAPABILITIES = {
    "market_data",
    "mainline_context",
    "kb_search",
    "graph_lookup",
    "evidence_lookup",
    "news_search",
    "web_search",
    "l3_lookup",
}


@pytest.mark.parametrize(
    ("question", "expected_capabilities", "expected_output"),
    (
        (
            "昨天的反弹能持续多久",
            {"market_data", "news_search"},
            "duration_assessment",
        ),
        (
            "科创50你认为反弹空间有多少",
            {"market_data"},
            "technical_levels",
        ),
        (
            "瑞华泰的合理估值",
            {"market_data", "evidence_lookup"},
            "valuation_assessment",
        ),
        (
            "这一周行情下跌的主要原因是什么",
            {"market_data", "news_search"},
            "causal_chain",
        ),
        (
            "目前市场的主线是什么",
            {"market_data", "mainline_context"},
            "direct_assessment",
        ),
    ),
)
def test_acceptance_questions_build_one_bounded_episode_contract(
    question: str,
    expected_capabilities: set[str],
    expected_output: str,
) -> None:
    control = TurnControlCore().control(
        question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="episode-test",
        capabilities=control.capabilities,
        tier="standard",
        today="2026-07-22",
        latest_data_date="2026-07-21",
    )

    contract = context.contract
    assert contract.task_frame_hash == control.task_frame.task_frame_hash
    assert contract.question_type == control.task_frame.question_type
    assert expected_output in {item.output_id for item in contract.required_outputs}
    assert expected_capabilities.issubset(contract.allowed_capabilities)
    assert set(contract.allowed_capabilities).issubset(RUNTIME_CAPABILITIES)
    assert set(contract.evidence_plan.mandatory_capabilities).issubset(
        contract.allowed_capabilities
    )
    assert context.policy.tier == "standard"
    assert context.deadline.synthesis_reserve == context.policy.synthesis_reserve
    assert context.today == "2026-07-22"
    assert context.latest_data_date == "2026-07-21"


def test_episode_factory_rejects_unknown_runtime_capability() -> None:
    control = TurnControlCore().control("昨天的反弹能持续多久")

    with pytest.raises(ValueError, match="unknown runtime capability"):
        build_episode_context(
            control.task_frame,
            task_id="episode-test",
            capabilities=(*control.capabilities, "shell"),
        )


def test_episode_timeout_override_cannot_inflate_policy_budget() -> None:
    control = TurnControlCore().control("昨天的反弹能持续多久")
    context = build_episode_context(
        control.task_frame,
        task_id="episode-test",
        capabilities=control.capabilities,
        tier="quick",
        timeout=300,
    )

    assert context.deadline.remaining() <= context.policy.total_seconds


def test_episode_context_can_reallocate_but_not_inflate_synthesis_reserve() -> None:
    control = TurnControlCore().control("目前市场的主线是什么")
    context = build_episode_context(
        control.task_frame,
        task_id="episode-test",
        capabilities=control.capabilities,
        tier="standard",
        timeout=90.0,
        synthesis_reserve=45.0,
    )

    assert context.policy.total_seconds == 90.0
    assert context.policy.synthesis_reserve == 45.0
    assert context.deadline.synthesis_reserve == 45.0
    assert context.deadline.remaining() <= 90.0
    assert context.deadline.stage_timeout(90.0) <= 45.0
