"""P2 budget/deadline invariants: policy projects into one root ledger.

These pin spec 7.2 with literals chosen in the test. Do not derive the
expected value by copying the production formula — that cannot disagree
with the code.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import time
from uuid import uuid4

import pytest

from intelligence.runtime.tier_promotion import apply_mode_promotion
from intelligence.services.mode_governor import ModeGovernor, ModeSignals
from intelligence.services.repair_coordinator import BudgetGrant
from intelligence.services.research_contract import (
    InformationCutoff,
    InMemoryRootBudgetLedger,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
    release_root_budget,
    root_budget_for_policy,
)
from intelligence.services.research_plan import ResearchPlan

_REPO = Path(__file__).resolve().parents[2]


def _fresh_episode(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def test_root_budget_initial_calls_equal_policy_max_steps() -> None:
    """G3: factory must project max_steps, not a hardcoded 12."""

    episode = _fresh_episode("p2-calls")
    policy = ResearchPolicy("standard", 6, 90.0, 20.0)
    try:
        ledger = root_budget_for_policy(policy, episode_id=episode)
        assert ledger.initial_calls == 6
        assert ledger.remaining_calls == 6
        assert ledger.hard_calls_cap == 8
    finally:
        release_root_budget(episode)


def test_root_budget_initial_seconds_exclude_synthesis_reserve() -> None:
    episode = _fresh_episode("p2-seconds")
    policy = ResearchPolicy("quick", 3, 30.0, 20.0)
    try:
        ledger = root_budget_for_policy(policy, episode_id=episode)
        assert ledger.initial_seconds == 10.0
        assert ledger.hard_seconds_cap == 30.0
        assert ledger.remaining_seconds == 10.0
        assert ledger.initial_calls == 3
        assert ledger.hard_calls_cap == 4
    finally:
        release_root_budget(episode)


def test_unknown_tier_hard_call_cap_falls_back_to_max_steps() -> None:
    episode = _fresh_episode("p2-custom")
    policy = ResearchPolicy("custom", 5, 40.0, 10.0)
    try:
        ledger = root_budget_for_policy(policy, episode_id=episode)
        assert ledger.initial_calls == 5
        assert ledger.hard_calls_cap == 5
        assert ledger.initial_seconds == 30.0
    finally:
        release_root_budget(episode)


def test_grant_refuses_calls_or_seconds_beyond_unallocated_headroom() -> None:
    ledger = InMemoryRootBudgetLedger(
        episode_id="p2-grant-headroom",
        initial_calls=2,
        hard_calls_cap=4,
        initial_seconds=10.0,
        hard_seconds_cap=20.0,
    )
    assert ledger.grant(
        BudgetGrant(
            grant_id="g-ok",
            episode_id="p2-grant-headroom",
            cycle=1,
            calls_granted=2,
            seconds_granted=5.0,
        )
    )
    assert ledger.allocated_calls == 4
    assert ledger.remaining_calls == 4
    assert ledger.allocated_seconds == 15.0

    assert (
        ledger.grant(
            BudgetGrant(
                grant_id="g-calls",
                episode_id="p2-grant-headroom",
                cycle=1,
                calls_granted=1,
                seconds_granted=1.0,
            )
        )
        is False
    )
    assert (
        ledger.grant(
            BudgetGrant(
                grant_id="g-seconds",
                episode_id="p2-grant-headroom",
                cycle=1,
                calls_granted=0,
                seconds_granted=6.0,
            )
        )
        is False
    )
    assert ledger.allocated_calls == 4
    assert ledger.allocated_seconds == 15.0


def test_consume_call_and_grant_keep_allocated_minus_remaining_identity() -> None:
    ledger = InMemoryRootBudgetLedger(
        episode_id="p2-identity",
        initial_calls=3,
        hard_calls_cap=5,
        initial_seconds=9.0,
        hard_seconds_cap=12.0,
    )
    ledger.consume_call(seconds=1.5)
    ledger.consume_call(seconds=1.5)
    assert ledger.remaining_calls == 1
    assert ledger.allocated_calls - ledger.remaining_calls == 2

    assert ledger.grant(
        BudgetGrant(
            grant_id="g-repair",
            episode_id="p2-identity",
            cycle=1,
            calls_granted=2,
            seconds_granted=3.0,
        )
    )
    assert ledger.allocated_calls == 5
    assert ledger.remaining_calls == 3
    assert ledger.allocated_calls - ledger.remaining_calls == 2


def test_stage_timeout_never_exceeds_remaining_minus_reserve() -> None:
    deadline = ResearchDeadline.from_timeout(10.0, synthesis_reserve=3.0)
    assert deadline.stage_timeout(100.0) == pytest.approx(7.0, abs=0.05)
    assert deadline.stage_timeout(1.0) == pytest.approx(1.0, abs=0.05)
    assert deadline.synthesis_timeout(100.0) == pytest.approx(10.0, abs=0.05)
    assert deadline.synthesis_timeout(2.0) == pytest.approx(2.0, abs=0.05)
    remaining = deadline.remaining()
    assert deadline.stage_timeout(100.0) <= remaining
    assert deadline.synthesis_timeout(100.0) <= remaining


def test_bounded_stage_child_cannot_outlive_parent_research_window() -> None:
    parent = ResearchDeadline.from_timeout(10.0, synthesis_reserve=3.0)
    child = parent.bounded_stage(100.0)
    assert child.expires_at <= parent.expires_at - parent.synthesis_reserve + 1e-9
    assert child.remaining() <= parent.stage_timeout(100.0) + 0.05


def test_deadline_and_root_seconds_can_exhaust_independently() -> None:
    """Spec P2 scenario 6: two clocks, two exhaustion orders."""

    wall = ResearchDeadline.from_timeout(8.0, synthesis_reserve=0.0)
    short_ledger = InMemoryRootBudgetLedger(
        episode_id="p2-seconds-first",
        initial_calls=2,
        hard_calls_cap=2,
        initial_seconds=2.0,
        hard_seconds_cap=2.0,
    )
    short_ledger.consume_seconds(seconds=2.0)
    assert short_ledger.remaining_seconds == 0.0
    assert wall.expired is False

    already_dead = ResearchDeadline(expires_at=time.monotonic() - 1.0)
    fat_ledger = InMemoryRootBudgetLedger(
        episode_id="p2-deadline-first",
        initial_calls=2,
        hard_calls_cap=2,
        initial_seconds=20.0,
        hard_seconds_cap=20.0,
    )
    assert already_dead.expired is True
    assert fat_ledger.remaining_seconds == 20.0


def test_deep_promotion_keeps_tier_caps_deadline_reserve_aligned() -> None:
    episode = _fresh_episode("p2-deep")
    policy = ResearchPolicy.for_tier("standard")
    context = ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=episode,
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
        trace_parent_id=episode,
        information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"),
        root_budget=root_budget_for_policy(policy, episode_id=episode),
    )
    try:
        decision = ModeGovernor().decide(
            ResearchPlan(
                task_summary="比较两类证据后回答用户问题",
                answer_elements=("直接判断", "依据"),
                hypotheses=("主假设",),
                evidence_needs=("盘面",),
                candidate_actions=("查询结构化数据",),
                open_gaps=(),
                requested_mode="deep",
            ),
            ModeSignals(evidence_domains=("盘面", "新闻")),
        )
        promoted = apply_mode_promotion(context, decision)
        root = promoted.root_budget
        assert root is not None
        assert promoted.policy.tier == "deep"
        assert promoted.policy.synthesis_reserve == 48.0
        assert promoted.deadline.synthesis_reserve == 48.0
        assert root.hard_calls_cap == 24
        assert root.hard_seconds_cap == 240.0
        assert root.remaining_calls == 24
        assert root.remaining_seconds == 192.0
        assert root.hard_seconds_cap - promoted.deadline.synthesis_reserve == 192.0
    finally:
        release_root_budget(episode)


def test_semantic_verifier_source_has_no_root_ledger_debit() -> None:
    """G4: judge is a deadline sub-grant, not a remaining_calls consumer."""

    source = (_REPO / "intelligence/services/episode_semantic_verifier.py").read_text(
        encoding="utf-8"
    )
    assert "consume_call" not in source
    assert "consume_seconds" not in source
    assert "root_budget" not in source
    assert "RootBudgetLedger" not in source
