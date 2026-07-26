from __future__ import annotations

from datetime import date

import pytest

from intelligence.services.mode_governor import ModeGovernor, ModeSignals
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
    root_budget_for_policy,
)
from intelligence.services.research_plan import ResearchPlan


def _plan(mode: str) -> ResearchPlan:
    return ResearchPlan(
        task_summary="比较两类证据后回答用户问题",
        answer_elements=("直接判断", "依据"),
        hypotheses=("主假设",),
        evidence_needs=("盘面",),
        candidate_actions=("查询结构化数据",),
        open_gaps=(),
        requested_mode=mode,
    )


def _standard_context(*, episode_id: str) -> ResearchRunContext:
    policy = ResearchPolicy.for_tier("standard")
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=episode_id,
            question="比较本周市场驱动并检查反方证据",
            subject="A股市场",
            subject_kind="market",
            question_type="general_finance_qa",
            required_outputs=(),
            allowed_capabilities=("finance_query", "news_search"),
            research_tier="standard",
        ),
        deadline=ResearchDeadline.from_timeout(
            policy.total_seconds,
            synthesis_reserve=policy.synthesis_reserve,
        ),
        policy=policy,
        trace_parent_id=episode_id,
        information_cutoff=InformationCutoff(
            date(2026, 7, 24),
            "requested",
        ),
        root_budget=root_budget_for_policy(policy, episode_id=episode_id),
    )


def test_model_deep_request_requires_an_observable_condition() -> None:
    governor = ModeGovernor()

    denied = governor.decide(_plan("deep"), ModeSignals())
    approved = governor.decide(
        _plan("deep"),
        ModeSignals(evidence_domains=("盘面", "新闻")),
    )

    assert denied.effective_mode == "quick"
    assert denied.approved is False
    assert denied.reason == "no_observable_deep_condition"
    assert approved.effective_mode == "deep"
    assert approved.approved is True
    assert approved.observable_conditions == ("multiple_evidence_domains",)
    assert approved.research_tier == "deep"
    assert approved.tool_call_cap == 24
    assert approved.target_seconds == 240.0
    assert approved.max_repair_cycles == 3
    assert approved.max_branches == 3


def test_user_quick_mode_cannot_be_overridden_by_model() -> None:
    decision = ModeGovernor().decide(
        _plan("deep"),
        ModeSignals(
            user_mode="quick",
            independent_entities=2,
            evidence_domains=("盘面", "新闻"),
        ),
    )

    assert decision.requested_mode == "deep"
    assert decision.effective_mode == "quick"
    assert decision.approved is False
    assert decision.reason == "user_selected_quick"
    assert decision.research_tier == "standard"
    assert decision.tool_call_cap == 8
    assert decision.max_branches == 0


def test_user_deep_mode_can_promote_a_model_quick_plan() -> None:
    decision = ModeGovernor().decide(
        _plan("quick"),
        ModeSignals(user_mode="deep"),
    )

    assert decision.requested_mode == "deep"
    assert decision.effective_mode == "deep"
    assert decision.approved is True
    assert decision.reason == "user_selected_deep"
    assert decision.observable_conditions == ("explicit_user_deep",)


def test_model_quick_plan_stays_quick_even_when_task_is_complex() -> None:
    decision = ModeGovernor().decide(
        _plan("quick"),
        ModeSignals(
            independent_entities=3,
            evidence_domains=("盘面", "新闻"),
            complexity_flags=("causal_attribution",),
            uncovered_answer_elements=2,
        ),
    )

    assert decision.effective_mode == "quick"
    assert decision.approved is False
    assert decision.reason == "model_requested_quick"


@pytest.mark.parametrize(
    ("signals", "reason"),
    [
        (
            ModeSignals(
                evidence_domains=("盘面", "新闻"),
                dependencies_available=False,
            ),
            "deep_dependencies_unavailable",
        ),
        (
            ModeSignals(
                evidence_domains=("盘面", "新闻"),
                deep_deadline_available=False,
            ),
            "deep_deadline_unavailable",
        ),
    ],
)
def test_deep_request_fails_closed_when_runtime_cannot_honor_it(
    signals: ModeSignals,
    reason: str,
) -> None:
    decision = ModeGovernor().decide(_plan("deep"), signals)

    assert decision.effective_mode == "quick"
    assert decision.approved is False
    assert decision.reason == reason


@pytest.mark.parametrize(
    ("signals", "condition"),
    [
        (ModeSignals(independent_entities=2), "multiple_independent_entities"),
        (
            ModeSignals(complexity_flags=("valuation",)),
            "complexity:valuation",
        ),
        (
            ModeSignals(uncovered_answer_elements=1),
            "material_uncovered_answer_element",
        ),
    ],
)
def test_each_approved_complexity_signal_is_auditable(
    signals: ModeSignals,
    condition: str,
) -> None:
    decision = ModeGovernor().decide(_plan("deep"), signals)

    assert decision.effective_mode == "deep"
    assert condition in decision.observable_conditions
    assert decision.to_dict()["observable_conditions"] == list(
        decision.observable_conditions
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"user_mode": "turbo"},
        {"independent_entities": -1},
        {"uncovered_answer_elements": -1},
        {"complexity_flags": ("route_named_complexity",)},
    ],
)
def test_mode_signals_reject_invalid_control_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ModeSignals(**kwargs)


def test_approved_deep_mode_promotes_the_existing_context_atomically() -> None:
    context = _standard_context(episode_id="mode-promotion")
    root = context.root_budget
    assert root is not None
    decision = ModeGovernor().decide(
        _plan("deep"),
        ModeSignals(evidence_domains=("盘面", "新闻")),
    )
    before_deadline = context.deadline.expires_at

    promoted = ModeGovernor().apply(context, decision)

    assert promoted.contract is context.contract
    assert promoted.information_cutoff == context.information_cutoff
    assert promoted.root_budget is root
    assert promoted.policy.tier == "deep"
    assert promoted.deadline.expires_at > before_deadline
    assert root.hard_calls_cap == 24
    assert root.remaining_calls == 24
    assert root.hard_seconds_cap == 240.0
    assert root.remaining_seconds == 192.0


def test_deep_promotion_is_idempotent_and_never_mints_a_second_ledger() -> None:
    context = _standard_context(episode_id="mode-promotion-idempotent")
    decision = ModeGovernor().decide(
        _plan("deep"),
        ModeSignals(complexity_flags=("valuation",)),
    )

    first = ModeGovernor().apply(context, decision)
    second = ModeGovernor().apply(first, decision)

    assert second.root_budget is context.root_budget
    assert second.root_budget is not None
    assert second.root_budget.remaining_calls == 24
    assert second.root_budget.remaining_seconds == 192.0
    assert second.deadline.expires_at == first.deadline.expires_at


def test_denied_or_quick_decision_preserves_the_original_context() -> None:
    context = _standard_context(episode_id="mode-no-promotion")
    decision = ModeGovernor().decide(_plan("quick"), ModeSignals())

    assert ModeGovernor().apply(context, decision) is context
    assert context.root_budget is not None
    assert context.root_budget.hard_calls_cap == 8
    assert context.root_budget.remaining_calls == 6


def test_root_budget_promotion_is_episode_bound_increase_only_and_capped() -> None:
    context = _standard_context(episode_id="mode-ledger-authority")
    root = context.root_budget
    assert root is not None

    assert (
        root.promote_caps(
            episode_id="foreign-episode",
            promotion_id="promotion-foreign",
            hard_calls_cap=24,
            hard_seconds_cap=240.0,
        )
        is False
    )
    assert (
        root.promote_caps(
            episode_id="mode-ledger-authority",
            promotion_id="promotion-too-large",
            hard_calls_cap=25,
            hard_seconds_cap=240.0,
        )
        is False
    )
    assert (
        root.promote_caps(
            episode_id="mode-ledger-authority",
            promotion_id="promotion-lower",
            hard_calls_cap=7,
            hard_seconds_cap=89.0,
        )
        is False
    )
    assert root.hard_calls_cap == 8
    assert root.hard_seconds_cap == 90.0
