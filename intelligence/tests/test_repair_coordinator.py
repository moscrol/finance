from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.repair_coordinator import (
    build_repair_goal,
    grant_for_progress,
    progress_from_ledger,
    should_reenter,
)
from intelligence.services.research_contract import InMemoryRootBudgetLedger


def _snap(*, evidence: tuple[str, ...], covered: tuple[str, ...], gaps: tuple[str, ...], family: str):
    return EvidenceLedgerSnapshot(
        evidence_ids=evidence,
        covered_outputs=covered,
        open_gaps=gaps,
        independent_source_families=(family,),
        evidence_source_families=tuple((item, family) for item in evidence),
    )


def test_progress_snapshot_is_ledger_derived_and_same_family_does_not_count() -> None:
    before = _snap(evidence=("e1",), covered=(), gaps=("counterpoint",), family="market")
    same_family = _snap(
        evidence=("e1", "e2"),
        covered=(),
        gaps=("counterpoint",),
        family="market",
    )
    no_progress = progress_from_ledger(before, same_family)
    assert no_progress.effective_new_evidence == 0
    assert not no_progress.coverage_delta.progressed

    after = EvidenceLedgerSnapshot(
        evidence_ids=("e1", "e2"),
        covered_outputs=("counterpoint",),
        open_gaps=(),
        independent_source_families=("market", "news"),
        evidence_source_families=(("e1", "market"), ("e2", "news")),
    )
    progress = progress_from_ledger(before, after)
    assert progress.effective_new_evidence == 1
    assert progress.coverage_delta.progressed


def test_repair_goal_has_no_query_authority_and_budget_grant_respects_hard_cap() -> None:
    before = _snap(evidence=(), covered=(), gaps=("counterpoint",), family="market")
    after = _snap(evidence=("e1",), covered=("direct",), gaps=("counterpoint",), family="news")
    progress = progress_from_ledger(before, after)
    goal = build_repair_goal(
        episode_id="episode-1",
        missing_outputs=("counterpoint",),
        missing_capabilities=("news_search",),
        attempted_actions=("market_data:A股",),
        previous_progress=progress,
        remaining_calls=3,
        remaining_seconds=42,
    )
    assert not hasattr(goal, "next_query")
    assert should_reenter(progress, cycle=1, max_cycles=1)
    root = InMemoryRootBudgetLedger(
        initial_calls=3,
        hard_calls_cap=4,
        initial_seconds=30,
        hard_seconds_cap=38,
    )
    assert (
        grant_for_progress(
            goal,
            progress,
            root_budget=root,
            research_tier="quick",
        )
        is None
    )
    # The deterministic grant is 2 calls/16 seconds, which exceeds this cap.
    assert root.remaining_calls == 3

    accepted_root = InMemoryRootBudgetLedger(
        initial_calls=3,
        hard_calls_cap=5,
        initial_seconds=30,
        hard_seconds_cap=60,
    )
    grant = grant_for_progress(
        goal,
        progress,
        root_budget=accepted_root,
        research_tier="quick",
    )
    assert grant is not None
    assert accepted_root.remaining_calls == 5
    accepted_root.consume_call(seconds=8)
    assert accepted_root.remaining_calls == 4


def test_grant_for_progress_rejects_cycle_above_code_owned_tier_cap() -> None:
    before = _snap(evidence=(), covered=(), gaps=("counterpoint",), family="market")
    after = _snap(
        evidence=("e1",),
        covered=("direct",),
        gaps=("counterpoint",),
        family="news",
    )
    progress = progress_from_ledger(before, after)
    goal = build_repair_goal(
        episode_id="episode-1",
        missing_outputs=("counterpoint",),
        previous_progress=progress,
        remaining_calls=3,
        remaining_seconds=42,
        cycle=2,
    )
    root = InMemoryRootBudgetLedger(
        initial_calls=3,
        hard_calls_cap=5,
        initial_seconds=30,
        hard_seconds_cap=60,
    )

    assert (
        grant_for_progress(
            goal,
            progress,
            root_budget=root,
            research_tier="quick",
        )
        is None
    )
    assert root.remaining_calls == 3


def test_root_budget_rejects_a_grant_from_another_episode() -> None:
    before = _snap(evidence=(), covered=(), gaps=("counterpoint",), family="market")
    after = _snap(
        evidence=("e1",), covered=("direct",), gaps=("counterpoint",), family="news"
    )
    progress = progress_from_ledger(before, after)
    goal = build_repair_goal(
        episode_id="episode-2",
        missing_outputs=("counterpoint",),
        previous_progress=progress,
        remaining_calls=3,
        remaining_seconds=42,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-1",
        initial_calls=3,
        hard_calls_cap=5,
        initial_seconds=30,
        hard_seconds_cap=60,
    )
    assert (
        grant_for_progress(
            goal,
            progress,
            root_budget=root,
            research_tier="quick",
        )
        is None
    )


def test_root_budget_debits_model_seconds_without_spending_a_tool_call() -> None:
    root = InMemoryRootBudgetLedger(
        episode_id="episode-1",
        initial_calls=3,
        hard_calls_cap=5,
        initial_seconds=30,
        hard_seconds_cap=60,
    )

    root.consume_seconds(seconds=4.5)

    assert root.remaining_calls == 3
    assert root.remaining_seconds == 25.5
