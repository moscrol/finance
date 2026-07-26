from __future__ import annotations

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.turn_control_core import TurnControlCore


RUNTIME_CAPABILITIES = {
    "finance_query",
    "evidence_search",
    "market_data",
    "financial_data",
    "mainline_context",
    "kb_search",
    "graph_lookup",
    "evidence_lookup",
    "news_search",
    "web_search",
    "l3_lookup",
}


def test_evidence_grounded_tasks_receive_broad_model_owned_read_tools() -> None:
    control = TurnControlCore().control(
        "目前固态电池产业景气度处于什么阶段，给出数据依据",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="broad-read-tools",
        capabilities=control.capabilities,
    )

    assert {"finance_query", "evidence_search"}.issubset(
        context.contract.allowed_capabilities
    )
    assert "finance_query" not in {
        item.capability for item in context.contract.evidence_plan.requirements
    }
    assert "evidence_search" not in {
        item.capability for item in context.contract.evidence_plan.requirements
    }


@pytest.mark.parametrize(
    ("question", "expected_capabilities", "expected_output"),
    (
        (
            "昨天的反弹能持续多久",
            {"market_data", "mainline_context"},
            "duration_assessment",
        ),
        (
            "科创50你认为反弹空间有多少",
            {"market_data"},
            "technical_levels",
        ),
        (
            "瑞华泰的合理估值",
            {"market_data", "financial_data", "evidence_lookup"},
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


def test_market_cause_requires_time_aligned_news_evidence() -> None:
    control = TurnControlCore().control(
        "这一周行情下跌的主要原因是什么",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="market-cause-evidence-plan",
        capabilities=control.capabilities,
    )

    assert context.contract.evidence_plan.profile == "time_aligned_market_causal"
    assert set(context.contract.evidence_plan.mandatory_capabilities) == {
        "market_data",
        "news_search",
    }


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


def test_valuation_contract_has_current_anchor_scenarios_and_invalidation() -> None:
    control = TurnControlCore().control("瑞华泰的合理估值")
    context = build_episode_context(
        control.task_frame,
        task_id="valuation-contract",
        capabilities=("evidence_lookup",),
        timeout=30.0,
    )

    outputs = {
        item.output_id: item.description for item in context.contract.required_outputs
    }
    assert {
        "valuation_assessment",
        "financial_business_anchor",
        "scenario_range",
        "evidence_boundary",
        "invalidation_conditions",
    }.issubset(outputs)
    assert all(
        term in outputs["valuation_assessment"]
        for term in ("当前市场锚点", "方法", "假设")
    )
    assert "market_data" in context.contract.allowed_capabilities
    assert "financial_data" in context.contract.allowed_capabilities
    assert set(context.contract.evidence_plan.mandatory_capabilities) == {
        "market_data",
        "financial_data",
    }
    financial_anchor = next(
        item
        for item in context.contract.required_outputs
        if item.output_id == "financial_business_anchor"
    )
    assert financial_anchor.evidence_types[0] == "financial_data"
    assert "evidence_lookup" in financial_anchor.evidence_types
    assert "market_data" not in financial_anchor.evidence_types
    assert "web_search" not in financial_anchor.evidence_types


@pytest.mark.parametrize(
    ("question", "expected_mode"),
    (
        (
            "一个没有历史胜率的新题材，应该如何判断它是主线候选还是一天噪音",
            "model_reasoning",
        ),
        (
            "如果电力板块涨停家数很多但成交占比和核心股承接下降，还能算主线吗",
            "user_premise",
        ),
        ("目前市场的主线是什么", "evidence"),
    ),
)
def test_episode_factory_projects_task_semantics_into_grounding_modes(
    question: str,
    expected_mode: str,
) -> None:
    control = TurnControlCore().control(
        question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="grounding-mode-test",
        capabilities=control.capabilities,
    )

    assert {
        item.grounding_mode for item in context.contract.required_outputs
    } == {expected_mode}
    if expected_mode in {"model_reasoning", "user_premise"}:
        assert context.contract.allowed_capabilities == ()
        assert context.contract.evidence_plan.requirements == ()
