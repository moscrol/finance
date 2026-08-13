from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.repair_coordinator import (
    RepairAdmission,
    admit_repair,
    build_repair_goal,
    grant_for_cold_restart,
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
    # The deterministic grant is 2 calls/30 seconds, which exceeds this cap.
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


def test_single_gap_repair_still_gets_full_window() -> None:
    """缺口数不得缩小修复窗：一次 LLM 调用的成本由固定延迟地板主导。

    旧公式 ``min(剩余, 30, 缺口×8)`` 给 1 缺口 8s、3 缺口 24s——都低于
    生产中转 P50≈28s 的单次调用地板，注定超时还白烧授予。2026-08-13
    R7/R21 收据：16/24s 窗 0/5 全超时，30s 窗 5/5 全成功。
    """
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(
        evidence=("e1",), covered=("direct",), gaps=(), family="news"
    )
    progress = progress_from_ledger(before, after)
    goal = build_repair_goal(
        episode_id="episode-floor",
        missing_outputs=("direct",),
        previous_progress=progress,
        remaining_calls=3,
        remaining_seconds=120.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-floor",
        initial_calls=3,
        hard_calls_cap=8,
        initial_seconds=120.0,
        hard_seconds_cap=240.0,
    )

    grant = grant_for_progress(
        goal,
        progress,
        root_budget=root,
        research_tier="quick",
    )

    assert grant is not None
    # 1 个缺口，旧公式会给 8s；现在必须给满窗 30s。
    assert grant.seconds_granted == 30.0


def test_single_gap_delivery_repair_gets_full_window() -> None:
    goal = build_repair_goal(
        episode_id="episode-floor-delivery",
        missing_outputs=("direct",),
        previous_progress=progress_from_ledger(
            _snap(evidence=(), covered=(), gaps=("direct",), family="market"),
            _snap(evidence=("e1",), covered=(), gaps=("direct",), family="market"),
        ),
        remaining_calls=0,
        remaining_seconds=120.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-floor-delivery",
        initial_calls=1,
        hard_calls_cap=8,
        initial_seconds=120.0,
        hard_seconds_cap=240.0,
    )

    grant = grant_for_delivery_repair(
        goal,
        root_budget=root,
        research_tier="quick",
        evidence_count=5,
    )

    assert grant is not None
    assert grant.calls_granted == 0
    assert grant.seconds_granted == 30.0


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
    # 同一 (goal, attempt) 再铸一次被 grant_id 拒掉（幂等防呆）；
    # 不同 attempt 各铸各的——熔断次数由调用方管，账本只管余量。
    assert grant_for_transient_model_retry(goal, root_budget=root) is None
    assert (
        grant_for_transient_model_retry(goal, root_budget=root, attempt=2) is None
    ), "余量已耗尽时第二 attempt 也必须 fail closed"


def test_transient_retry_second_attempt_mints_with_distinct_grant_id() -> None:
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(
        evidence=("e1",), covered=(), gaps=("direct",), family="news"
    )
    goal = build_repair_goal(
        episode_id="episode-retry-2",
        missing_outputs=("direct",),
        previous_progress=progress_from_ledger(before, after),
        remaining_calls=0,
        remaining_seconds=8.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-retry-2",
        initial_calls=1,
        hard_calls_cap=2,
        initial_seconds=10.0,
        hard_seconds_cap=100.0,
    )

    first = grant_for_transient_model_retry(goal, root_budget=root, attempt=1)
    second = grant_for_transient_model_retry(goal, root_budget=root, attempt=2)

    assert first is not None and second is not None
    assert first.grant_id == f"transient-retry-{goal.repair_goal_id}"
    assert second.grant_id == f"transient-retry-{goal.repair_goal_id}-2"
    assert first.grant_id != second.grant_id
    # 各铸各的 30s 帽，仍受 hard cap 约束。
    assert first.seconds_granted == 30.0
    assert second.seconds_granted == 30.0
    assert root.allocated_seconds == 70.0


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


def _starved_progress():
    """主路径零证据的进度快照：R7-A3 的形状。"""
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    return progress_from_ledger(before, after)


def test_cold_restart_admits_starved_episode_with_tool_open_grant() -> None:
    """零证据 + 有尝试 + 有余量 → 一发带工具的冷启动窗口。

    2026-08-13 R7-A3：检索窗被首个打偏的查询烧穿，末尾批量补发的检索在
    截止线上集体 ``tool_timeout``，episode 43s 零证据终局——而 root 余量
    还有 ~257s。进度闸（要求 ≥1 新证据）把这种「饿死」和「没干活」一起
    挡死；冷启动只放行前者。
    """
    progress = _starved_progress()
    root = InMemoryRootBudgetLedger(
        episode_id="episode-starved",
        initial_calls=2,
        hard_calls_cap=8,
        initial_seconds=30.0,
        hard_seconds_cap=300.0,
    )

    admission = admit_repair(
        episode_id="episode-starved",
        missing_outputs=("direct", "counterpoint"),
        attempted_actions=("finance_query:duckdb", "kb_search:rag"),
        previous_progress=progress,
        remaining_calls=6,
        remaining_seconds=257.0,
        cycle=1,
        root_budget=root,
        research_tier="standard",
        tools_open=False,
        cold_restart_candidate=True,
        evidence_count=0,
    )

    assert isinstance(admission, RepairAdmission)
    assert admission.goal.reopen_tools is True
    assert admission.delivery_only is False
    assert admission.grant.grant_id.startswith("cold-restart-")
    assert admission.grant.calls_granted >= 1
    assert admission.goal.remaining_calls == admission.grant.calls_granted
    # 沿用进度修复的额度公式：≤30s 满窗（缺口缩放项已删，见 _REPAIR_SECONDS_CAP）。
    assert 0.0 < admission.grant.seconds_granted <= 30.0
    assert admission.goal.remaining_seconds == admission.grant.seconds_granted


def test_cold_restart_requires_adapter_observed_starvation() -> None:
    """不带 cold_restart_candidate 的 admit_repair 不会漏进冷启动。

    饿死判据（stop_reason == deadline_exhausted 且零证据）由 adapter 观察后
    显式传入；坐标器对没有这个标记的零证据 episode（如 model_finish 拒答）
    保持原有拒收。R9-A3 实测教训：不能拿「试过工具」当判据——首个模型轮
    吃光窗口的形状零 trace，但同样是饿死。
    """
    progress = _starved_progress()
    root = InMemoryRootBudgetLedger(
        episode_id="episode-no-flag",
        initial_calls=2,
        hard_calls_cap=8,
        initial_seconds=30.0,
        hard_seconds_cap=300.0,
    )

    admission = admit_repair(
        episode_id="episode-no-flag",
        missing_outputs=("direct",),
        attempted_actions=(),
        previous_progress=progress,
        remaining_calls=6,
        remaining_seconds=257.0,
        cycle=1,
        root_budget=root,
        research_tier="standard",
        tools_open=False,
        cold_restart_candidate=False,
        evidence_count=0,
    )

    assert admission is None
    assert root.allocated_seconds == 30.0


def test_cold_restart_fires_for_zero_trace_starvation() -> None:
    """R9-A3 形状：首个模型轮吃光窗口、零 trace 零证据，也要放行。"""
    progress = _starved_progress()
    root = InMemoryRootBudgetLedger(
        episode_id="episode-zero-trace",
        initial_calls=2,
        hard_calls_cap=8,
        initial_seconds=30.0,
        hard_seconds_cap=300.0,
    )

    admission = admit_repair(
        episode_id="episode-zero-trace",
        missing_outputs=("direct",),
        attempted_actions=(),
        previous_progress=progress,
        remaining_calls=6,
        remaining_seconds=257.0,
        cycle=1,
        root_budget=root,
        research_tier="standard",
        tools_open=False,
        cold_restart_candidate=True,
        evidence_count=0,
    )

    assert isinstance(admission, RepairAdmission)
    assert admission.goal.reopen_tools is True
    assert admission.grant.calls_granted >= 1


def test_cold_restart_refuses_when_any_evidence_exists() -> None:
    """一旦有证据，走常规进度/交付通道；冷启动只救零证据。"""
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(evidence=("e1",), covered=(), gaps=("direct",), family="news")
    progress = progress_from_ledger(before, after)
    goal = build_repair_goal(
        episode_id="episode-has-evidence",
        missing_outputs=("direct",),
        attempted_actions=("finance_query:duckdb",),
        previous_progress=progress,
        remaining_calls=4,
        remaining_seconds=100.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-has-evidence",
        initial_calls=1,
        hard_calls_cap=8,
        initial_seconds=30.0,
        hard_seconds_cap=300.0,
    )

    assert grant_for_cold_restart(goal, progress, root_budget=root) is None


def test_cold_restart_is_single_shot_cycle_one_only() -> None:
    """cycle 2 不给：冷启动失败不再续命，防的是进度闸原本防的循环。"""
    progress = _starved_progress()
    goal = build_repair_goal(
        episode_id="episode-cycle2",
        missing_outputs=("direct",),
        attempted_actions=("finance_query:duckdb",),
        previous_progress=progress,
        remaining_calls=4,
        remaining_seconds=100.0,
        cycle=2,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-cycle2",
        initial_calls=1,
        hard_calls_cap=8,
        initial_seconds=30.0,
        hard_seconds_cap=300.0,
    )

    assert grant_for_cold_restart(goal, progress, root_budget=root) is None


def test_cold_restart_fails_closed_without_root_headroom() -> None:
    """root 余量不够时 fail closed，不铸空头授予。"""
    progress = _starved_progress()
    goal = build_repair_goal(
        episode_id="episode-broke",
        missing_outputs=("direct",),
        attempted_actions=("finance_query:duckdb",),
        previous_progress=progress,
        remaining_calls=4,
        remaining_seconds=100.0,
    )
    root = InMemoryRootBudgetLedger(
        episode_id="episode-broke",
        initial_calls=1,
        hard_calls_cap=8,
        initial_seconds=30.0,
        hard_seconds_cap=30.0,
    )

    assert grant_for_cold_restart(goal, progress, root_budget=root) is None
    assert root.allocated_seconds == 30.0


def test_delivery_candidate_never_falls_through_to_cold_restart() -> None:
    """delivery 候选（有证据没答案）与冷启动（有尝试零证据）互斥。

    admit_repair 的分流顺序若写错，一个 delivery 候选在授予失败后可能
    漏进冷启动拿到工具——那会把「交付修复不得重开检索」的边界打穿。
    """
    before = _snap(evidence=(), covered=(), gaps=("direct",), family="market")
    after = _snap(evidence=("e1",), covered=(), gaps=("direct",), family="news")
    progress = progress_from_ledger(before, after)
    root = InMemoryRootBudgetLedger(
        episode_id="episode-delivery-x",
        initial_calls=1,
        hard_calls_cap=8,
        initial_seconds=30.0,
        # 余量 0：delivery 授予必然失败，验证不会漏到冷启动。
        hard_seconds_cap=30.0,
    )

    admission = admit_repair(
        episode_id="episode-delivery-x",
        missing_outputs=("direct",),
        attempted_actions=("finance_query:duckdb",),
        previous_progress=progress,
        remaining_calls=0,
        remaining_seconds=8.0,
        cycle=1,
        root_budget=root,
        research_tier="standard",
        tools_open=False,
        delivery_candidate=True,
        cold_restart_candidate=True,
        evidence_count=1,
    )

    assert admission is None


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
