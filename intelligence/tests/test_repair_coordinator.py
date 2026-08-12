from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.repair_coordinator import (
    RepairAdmission,
    admit_repair,
    build_repair_goal,
    grant_for_delivery_repair,
    grant_for_progress,
    grant_for_transient_model_retry,
    progress_from_ledger,
    should_reenter,
    BudgetGrant,
)
from intelligence.services.research_contract import InMemoryRootBudgetLedger


def _snap(*, evidence: tuple[str, ...], covered: tuple[str, ...], gaps: tuple[str, ...], family: str):
    return EvidenceLedgerSnapshot(
        evidence_ids=evidence,
        covered_outputs=covered,
        open_gaps=gaps,
        independent_source_families=(family,),
        evidence_source_families=tuple((item, family) for item in evidence),
        evidence_targets=tuple((item, covered) for item in evidence),
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
        evidence_targets=(("e1", ()), ("e2", ("counterpoint",))),
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
        episode_id="episode-1",
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
        episode_id="episode-1",
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
    assert root.remaining_calls == 3


def test_closed_research_window_grants_seconds_without_tool_calls() -> None:
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(
        evidence=("e1",),
        covered=("direct",),
        gaps=(),
        family="market",
    )
    progress = progress_from_ledger(before, after)
    goal = build_repair_goal(
        episode_id="episode-1",
        missing_outputs=("direct",),
        rejected_claims=("claim_index:0",),
        previous_progress=progress,
        remaining_calls=0,
        remaining_seconds=8.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-1",
        initial_calls=1,
        hard_calls_cap=2,
        initial_seconds=8.0,
        hard_seconds_cap=16.0,
    )
    root.consume_call(seconds=8.0)

    grant = grant_for_progress(
        goal,
        progress,
        root_budget=root,
        research_tier="quick",
        tools_open=False,
    )

    assert grant is not None
    assert grant.calls_granted == 0
    assert grant.seconds_granted == 8.0
    assert root.allocated_calls == 1
    assert root.remaining_calls == 0
    assert root.remaining_seconds == 8.0


def test_admit_repair_returns_one_execution_ready_delivery_admission() -> None:
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(
        evidence=("e1",), covered=(), gaps=("direct",), family="news"
    )
    progress = progress_from_ledger(before, after)
    root = InMemoryRootBudgetLedger(
        episode_id="episode-admission",
        initial_calls=1,
        hard_calls_cap=2,
        initial_seconds=8.0,
        hard_seconds_cap=16.0,
    )
    root.consume_seconds(seconds=1.0)

    admission = admit_repair(
        episode_id="episode-admission",
        missing_outputs=("direct",),
        previous_progress=progress,
        remaining_calls=0,
        remaining_seconds=8.0,
        cycle=1,
        root_budget=root,
        research_tier="standard",
        tools_open=False,
        allow_delivery_repair=True,
        delivery_candidate=True,
        evidence_count=1,
    )

    assert isinstance(admission, RepairAdmission)
    assert admission.goal.episode_id == "episode-admission"
    assert admission.goal.remaining_calls == 0
    assert admission.grant.calls_granted == 0
    assert admission.delivery_only is True


def test_delivery_repair_does_not_relabel_unbound_evidence_as_research_progress() -> None:
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = EvidenceLedgerSnapshot(
        evidence_ids=("e1",),
        covered_outputs=(),
        open_gaps=("direct",),
        independent_source_families=("news",),
        evidence_source_families=(("e1", "news"),),
        evidence_targets=(("e1", ()),),
    )
    progress = progress_from_ledger(before, after)
    assert not progress.coverage_delta.progressed
    goal = build_repair_goal(
        episode_id="episode-delivery",
        missing_outputs=("direct",),
        previous_progress=progress,
        remaining_calls=0,
        remaining_seconds=8.0,
    )
    research_root = InMemoryRootBudgetLedger(
        episode_id="episode-delivery",
        initial_calls=1,
        hard_calls_cap=2,
        initial_seconds=1.0,
        hard_seconds_cap=9.0,
    )
    research_root.consume_seconds(seconds=1.0)

    assert (
        grant_for_progress(
            goal,
            progress,
            root_budget=research_root,
            research_tier="standard",
            tools_open=False,
        )
        is None
    )
    grant = grant_for_delivery_repair(
        goal,
        root_budget=research_root,
        research_tier="standard",
        evidence_count=1,
    )

    assert grant is not None
    assert grant.calls_granted == 0
    assert grant.seconds_granted == 8.0


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


def test_grant_for_transient_model_retry_mints_seconds_from_headroom() -> None:
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(
        evidence=("e1",), covered=(), gaps=("direct",), family="news"
    )
    goal = build_repair_goal(
        episode_id="episode-retry",
        missing_outputs=("direct",),
        previous_progress=progress_from_ledger(before, after),
        remaining_calls=0,
        remaining_seconds=8.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-retry",
        initial_calls=1,
        hard_calls_cap=2,
        initial_seconds=10.0,
        hard_seconds_cap=30.0,
    )
    assert root.grant(
        BudgetGrant(
            grant_id="grant-first",
            episode_id="episode-retry",
            cycle=1,
            calls_granted=0,
            seconds_granted=8.0,
        )
    )

    retry = grant_for_transient_model_retry(goal, root_budget=root)

    assert retry is not None
    assert retry.calls_granted == 0
    # 尺寸按 root 未分配余量（30-18=12）铸，不按 goal.remaining_seconds（8）：
    # 后者是 admission 塞回来的、刚被超时烧穿的那笔授予，按它重铸等于用同样
    # 大小的窗口再撞一次同一个慢 provider（R4 生产 A4/A5/A8/A9/A10 的死法）。
    assert retry.seconds_granted == 12.0
    assert retry.grant_id == f"transient-retry-{goal.repair_goal_id}"
    assert root.allocated_seconds == 30.0
    # 同一 goal 再铸一次被 grant_id 拒掉，和熔断上限 1 对齐。
    assert grant_for_transient_model_retry(goal, root_budget=root) is None


def test_grant_for_transient_model_retry_fails_closed_at_hard_cap() -> None:
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(
        evidence=("e1",), covered=(), gaps=("direct",), family="news"
    )
    goal = build_repair_goal(
        episode_id="episode-full",
        missing_outputs=("direct",),
        previous_progress=progress_from_ledger(before, after),
        remaining_calls=0,
        remaining_seconds=8.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-full",
        initial_calls=1,
        hard_calls_cap=2,
        initial_seconds=10.0,
        hard_seconds_cap=18.0,
    )
    assert root.grant(
        BudgetGrant(
            grant_id="grant-first",
            episode_id="episode-full",
            cycle=1,
            calls_granted=0,
            seconds_granted=8.0,
        )
    )

    assert grant_for_transient_model_retry(goal, root_budget=root) is None
    assert root.allocated_seconds == 18.0


def test_grant_for_transient_model_retry_caps_headroom_mint_at_thirty_seconds() -> None:
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(
        evidence=("e1",), covered=(), gaps=("direct",), family="news"
    )
    goal = build_repair_goal(
        episode_id="episode-cap",
        missing_outputs=("direct",),
        previous_progress=progress_from_ledger(before, after),
        remaining_calls=0,
        remaining_seconds=8.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-cap",
        initial_calls=1,
        hard_calls_cap=2,
        initial_seconds=20.0,
        hard_seconds_cap=100.0,
    )

    retry = grant_for_transient_model_retry(goal, root_budget=root)

    assert retry is not None
    # 余量 80 秒也只铸 30：单笔 30 秒帽不因余量充裕而放大。
    assert retry.seconds_granted == 30.0
    assert root.allocated_seconds == 50.0
