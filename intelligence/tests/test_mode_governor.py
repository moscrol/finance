from __future__ import annotations

from datetime import date

import pytest

from intelligence.runtime.tier_promotion import apply_mode_promotion
from intelligence.services.mode_governor import ModeGovernor, ModeSignals
from intelligence.services.research_contract import (
    PRODUCT_MAX_SECONDS,
    PRODUCT_MAX_TOOL_CALLS,
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


def test_governance_promotes_complex_task_even_when_the_model_never_asked() -> None:
    """模型没交 deep PLAN，但可观察条件够多 → 治理侧自行升档。

    **这条原来断言的是相反的行为**（`test_model_quick_plan_stays_quick_even_when_
    task_is_complex`）。改的是设计不是修 bug：2026-08-17 生产模型换成 GLM 后
    deep 归零，同日同码 gpt 交 PLAN 30% 而 glm 0%，链断了 12 天而门禁全绿。
    升档不该挂在「模型愿不愿意交 PLAN」上。

    读数留痕：`requested_mode` 仍如实记 "quick"，reason 明写是治理侧发起——
    台账上能一眼看出这次 deep 不是模型要的。
    """

    decision = ModeGovernor().decide(
        _plan("quick"),
        ModeSignals(
            independent_entities=3,
            evidence_domains=("盘面", "新闻"),
            complexity_flags=("causal_attribution",),
            uncovered_answer_elements=2,
        ),
    )

    assert decision.requested_mode == "quick"
    assert decision.effective_mode == "deep"
    assert decision.approved is True
    assert decision.reason == "observable_complexity_without_plan"
    assert len(decision.observable_conditions) >= 2


def test_model_quick_plan_stays_quick_when_evidence_is_thin() -> None:
    """只有一条可观察条件时仍然不升——模型没提，就要更多佐证。

    没有这条，上面那条用「模型说 quick 一律升 deep」也能全绿。
    """

    decision = ModeGovernor().decide(
        _plan("quick"),
        ModeSignals(independent_entities=3),
    )

    assert decision.observable_conditions == ("multiple_independent_entities",)
    assert decision.effective_mode == "quick"
    assert decision.approved is False
    assert decision.reason == "model_requested_quick"


@pytest.mark.parametrize("blocked", ["dependencies", "deadline"])
def test_governance_initiated_deep_still_respects_the_two_preconditions(
    blocked: str,
) -> None:
    """治理侧发起也不能绕过 deep 的两个前置——绕过就成了「新开一条没人管的路」。"""

    decision = ModeGovernor().decide(
        _plan("quick"),
        ModeSignals(
            independent_entities=3,
            evidence_domains=("盘面", "新闻"),
            complexity_flags=("causal_attribution",),
            uncovered_answer_elements=2,
            dependencies_available=blocked != "dependencies",
            deep_deadline_available=blocked != "deadline",
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
        (
            ModeSignals(separable_branches=1),
            "separable_sub_research_branch",
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
        {"separable_branches": -1},
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

    promoted = apply_mode_promotion(context, decision)

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

    first = apply_mode_promotion(context, decision)
    second = apply_mode_promotion(first, decision)

    assert second.root_budget is context.root_budget
    assert second.root_budget is not None
    assert second.root_budget.remaining_calls == 24
    assert second.root_budget.remaining_seconds == 192.0
    assert second.deadline.expires_at == first.deadline.expires_at


def test_denied_or_quick_decision_preserves_the_original_context() -> None:
    context = _standard_context(episode_id="mode-no-promotion")
    decision = ModeGovernor().decide(_plan("quick"), ModeSignals())

    assert apply_mode_promotion(context, decision) is context
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
    # 产品硬顶绑常数不绑字面量：2026-09-06 加 max 档把顶从 24/240 抬到 48/600，
    # 「越过顶就拒」这条判据不变。
    assert (
        root.promote_caps(
            episode_id="mode-ledger-authority",
            promotion_id="promotion-too-large",
            hard_calls_cap=PRODUCT_MAX_TOOL_CALLS + 1,
            hard_seconds_cap=240.0,
        )
        is False
    )
    assert (
        root.promote_caps(
            episode_id="mode-ledger-authority",
            promotion_id="promotion-too-long",
            hard_calls_cap=24,
            hard_seconds_cap=PRODUCT_MAX_SECONDS + 1.0,
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
