"""repair_policy 第一刀（M1–M4）：判据拆两侧后，授予逐字段不变。

对照 `docs/superpowers/specs/2026-09-02-repair-policy-state-machine.md` §3.3：

- M1 `should_reenter` 四条闸 → 领域两条（`repair_is_warranted`）∧ 预算两条
  （`can_afford_repair`）；M4 `max_repair_cycles_for_tier` 随领域侧走
  （`cycle_within_tier`）。
- M2 `grant_for_progress` 四种职责 → 领域闸 / 预算窗 / 记账三段，各自具名。
- M3 `work_units` 公式 → 领域出格数（`repair_work_units`），预算折调用
  （`calls_for_work_units`）。

金标来自拆分前 `fed88564` 的 `repair_coordinator`，脚本一次性跑出后钉在这里；
所有 `grant_id` / `cycle` / `calls_granted` / `seconds_granted` 逐字段比对。
"""

from __future__ import annotations

import itertools

import pytest

from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.repair_coordinator import (
    BudgetGrant,
    ProgressSnapshot,
    RepairGoal,
    calls_for_work_units,
    can_afford_repair,
    cycle_within_tier,
    grant_for_backfill,
    grant_for_cold_restart,
    grant_for_delivery_repair,
    grant_for_progress,
    grant_for_transient_model_retry,
    max_repair_cycles_for_tier,
    progress_from_ledger,
    repair_is_warranted,
    repair_work_units,
    size_repair_window,
)
from intelligence.services.research_contract import InMemoryRootBudgetLedger


def _snap(*, evidence, covered, gaps, family) -> EvidenceLedgerSnapshot:
    return EvidenceLedgerSnapshot(
        evidence_ids=evidence,
        covered_outputs=covered,
        open_gaps=gaps,
        independent_source_families=(family,),
        evidence_source_families=tuple((item, family) for item in evidence),
        evidence_targets=tuple((item, covered) for item in evidence),
    )


PROGRESSED = progress_from_ledger(
    _snap(evidence=(), covered=(), gaps=("counterpoint",), family="market"),
    _snap(evidence=("e1",), covered=("direct",), gaps=("counterpoint",), family="news"),
)
STALLED = progress_from_ledger(
    _snap(evidence=("e1",), covered=(), gaps=("direct",), family="market"),
    _snap(evidence=("e1",), covered=(), gaps=("direct",), family="market"),
)
STARVED = progress_from_ledger(
    _snap(evidence=(), covered=(), gaps=("direct",), family="market"),
    _snap(evidence=(), covered=(), gaps=("direct",), family="market"),
)


def _goal(
    *,
    mae: int = 1,
    mem: int = 0,
    rc: int = 3,
    rs: float = 42.0,
    cycle: int = 1,
    progress: ProgressSnapshot = PROGRESSED,
) -> RepairGoal:
    # repair_goal_id 固定，金标里的 grant_id 才能逐字比。
    return RepairGoal(
        episode_id="ep",
        repair_goal_id=f"repair-ep-{cycle}-fixed",
        cycle=cycle,
        missing_answer_elements=tuple(f"out{i}" for i in range(mae)),
        unsupported_claims=(),
        missing_evidence_modes=tuple(f"cap{i}" for i in range(mem)),
        attempted_actions=(),
        evidence_progress=progress.coverage_delta,
        remaining_calls=rc,
        remaining_seconds=rs,
    )


def _ledger(
    *, calls: int = 8, seconds: float = 300.0, allocated_seconds: float = 30.0
) -> InMemoryRootBudgetLedger:
    return InMemoryRootBudgetLedger(
        episode_id="ep",
        initial_calls=1,
        hard_calls_cap=calls,
        initial_seconds=allocated_seconds,
        hard_seconds_cap=seconds,
    )


def _fields(grant: BudgetGrant | None):
    if grant is None:
        return None
    return (grant.grant_id, grant.cycle, grant.calls_granted, grant.seconds_granted)


# --- M1 / M4：四条闸 = 领域两条 ∧ 预算两条 ---------------------------------


def _legacy_should_reenter(
    progress, *, cycle, max_cycles, remaining_calls, remaining_seconds, tools_open
) -> bool:
    """拆分前 `should_reenter` 的四条闸，按原顺序。这是被拆的合同，不是实现。"""

    if cycle < 1 or cycle > max_cycles:
        return False
    if not progress.coverage_delta.progressed:
        return False
    if tools_open and remaining_calls <= 0:
        return False
    if remaining_seconds < 1.0:
        return False
    return True


_TIER_FOR_CAP = {1: "quick", 3: "deep"}


def test_should_reenter_splits_into_domain_and_budget_sides() -> None:
    grid = itertools.product(
        (0, 1, 2, 3, 4), (1, 3), (True, False), (0, 1, 3), (0.5, 1.0, 8.0), (True, False)
    )
    true_count = 0
    for cycle, max_cycles, progressed, rc, rs, tools_open in grid:
        progress = PROGRESSED if progressed else STALLED
        legacy = _legacy_should_reenter(
            progress,
            cycle=cycle,
            max_cycles=max_cycles,
            remaining_calls=rc,
            remaining_seconds=rs,
            tools_open=tools_open,
        )
        split = repair_is_warranted(
            progress, cycle=cycle, research_tier=_TIER_FOR_CAP[max_cycles]
        ) and can_afford_repair(
            remaining_calls=rc, remaining_seconds=rs, tools_open=tools_open
        )
        assert split == legacy, (cycle, max_cycles, progressed, rc, rs, tools_open)
        true_count += legacy
    # 拆分前脚本实跑：360 格里 40 格放行。数字对不上说明网格或合同被改了。
    assert true_count == 40


def test_domain_side_never_reads_budget() -> None:
    # 余量为 0 / 0.5s 也不影响领域判定——预算是另一侧的事。
    assert repair_is_warranted(PROGRESSED, cycle=1, research_tier="quick")
    assert repair_is_warranted(PROGRESSED, cycle=3, research_tier="deep")
    assert not repair_is_warranted(PROGRESSED, cycle=2, research_tier="quick")
    assert not repair_is_warranted(PROGRESSED, cycle=0, research_tier="deep")
    assert not repair_is_warranted(STALLED, cycle=1, research_tier="deep")
    for tier in ("quick", "standard", "deep"):
        cap = max_repair_cycles_for_tier(tier)
        assert cycle_within_tier(cap, research_tier=tier)
        assert not cycle_within_tier(cap + 1, research_tier=tier)
        assert not cycle_within_tier(0, research_tier=tier)


def test_budget_side_never_reads_tier_or_progress() -> None:
    assert can_afford_repair(remaining_calls=0, remaining_seconds=8.0, tools_open=False)
    assert not can_afford_repair(remaining_calls=0, remaining_seconds=8.0, tools_open=True)
    assert can_afford_repair(remaining_calls=1, remaining_seconds=1.0, tools_open=True)
    assert not can_afford_repair(remaining_calls=1, remaining_seconds=0.99, tools_open=True)
    assert not can_afford_repair(remaining_calls=5, remaining_seconds=0.5, tools_open=False)


# --- M3：格数（领域）× 换算（预算） = 旧 work_units 公式 ------------------------


def test_work_units_times_conversion_equals_legacy_formula() -> None:
    for mae, mem, rc, tools_open in itertools.product(
        range(0, 6), range(0, 4), range(0, 7), (True, False)
    ):
        goal = _goal(mae=mae, mem=mem, rc=rc)
        legacy_units = min(4, max(1, mae + mem))
        legacy_calls = min(legacy_units, rc) if tools_open else 0
        assert repair_work_units(goal) == mae + mem
        assert (
            calls_for_work_units(
                repair_work_units(goal), remaining_calls=rc, tools_open=tools_open
            )
            == legacy_calls
        ), (mae, mem, rc, tools_open)


def test_size_repair_window_fails_closed_on_tiny_cap_and_no_calls() -> None:
    assert size_repair_window(
        work_units=1, remaining_calls=0, remaining_seconds=8.0, tools_open=True, seconds_cap=None
    ) is None
    assert size_repair_window(
        work_units=1, remaining_calls=3, remaining_seconds=0.9, tools_open=True, seconds_cap=None
    ) is None
    assert size_repair_window(
        work_units=1, remaining_calls=3, remaining_seconds=42.0, tools_open=True, seconds_cap=12.5
    ) == (1, 12.5)
    assert size_repair_window(
        work_units=0, remaining_calls=0, remaining_seconds=8.0, tools_open=False, seconds_cap=None
    ) == (0, 8.0)


# --- 金标：五种授予逐字段（拆分前 fed88564 实跑值） -------------------------------


@pytest.mark.parametrize(
    ("goal_kw", "kw", "ledger_kw", "expected"),
    [
        (
            dict(mae=1, mem=1, rc=3, rs=42.0),
            dict(research_tier="quick", tools_open=True),
            dict(calls=5, seconds=60.0),
            ("grant-repair-ep-1-fixed", 1, 2, 30.0),
        ),
        (
            dict(mae=1, rc=0, rs=8.0),
            dict(research_tier="quick", tools_open=False),
            dict(calls=2, seconds=16.0, allocated_seconds=8.0),
            ("grant-repair-ep-1-fixed", 1, 0, 8.0),
        ),
        (
            dict(mae=5, mem=2, rc=6, rs=120.0, cycle=3),
            dict(research_tier="deep", tools_open=True),
            dict(),
            ("grant-repair-ep-3-fixed", 3, 4, 30.0),
        ),
        (dict(cycle=4), dict(research_tier="deep", tools_open=True), dict(), None),
        (dict(progress=STALLED), dict(research_tier="deep", tools_open=True), dict(), None),
        (dict(rc=0), dict(research_tier="quick", tools_open=True), dict(), None),
        (dict(rs=0.5), dict(research_tier="quick", tools_open=True), dict(), None),
        (
            dict(mae=0, mem=0, rc=3, rs=42.0),
            dict(research_tier="quick", tools_open=True),
            dict(),
            ("grant-repair-ep-1-fixed", 1, 1, 30.0),
        ),
        (
            dict(mae=1, rc=3, rs=42.0),
            dict(research_tier="quick", tools_open=True, seconds_cap=12.5),
            dict(),
            ("grant-repair-ep-1-fixed", 1, 1, 12.5),
        ),
        (
            dict(mae=1, rc=3, rs=0.9),
            dict(research_tier="quick", tools_open=True, seconds_cap=30.0),
            dict(),
            None,
        ),
    ],
)
def test_grant_for_progress_golden(goal_kw, kw, ledger_kw, expected) -> None:
    goal = _goal(**goal_kw)
    progress = goal_kw.get("progress", PROGRESSED)
    grant = grant_for_progress(goal, progress, root_budget=_ledger(**ledger_kw), **kw)
    assert _fields(grant) == expected


@pytest.mark.parametrize(
    ("goal_kw", "kw", "ledger_kw", "expected"),
    [
        (
            dict(mae=1, rc=0, rs=8.0),
            dict(research_tier="standard", evidence_count=1),
            dict(calls=2, seconds=16.0, allocated_seconds=1.0),
            ("delivery-grant-repair-ep-1-fixed", 1, 0, 8.0),
        ),
        (dict(mae=1, rc=0, rs=8.0, cycle=2), dict(research_tier="quick", evidence_count=1), dict(), None),
        (dict(mae=1, rc=0, rs=8.0), dict(research_tier="quick", evidence_count=0), dict(), None),
        (dict(mae=0, rc=0, rs=8.0), dict(research_tier="quick", evidence_count=1), dict(), None),
        (
            dict(mae=1, rc=0, rs=120.0),
            dict(research_tier="quick", evidence_count=5),
            dict(),
            ("delivery-grant-repair-ep-1-fixed", 1, 0, 30.0),
        ),
        (dict(mae=1, rc=0, rs=0.5), dict(research_tier="quick", evidence_count=5), dict(), None),
    ],
)
def test_grant_for_delivery_repair_golden(goal_kw, kw, ledger_kw, expected) -> None:
    grant = grant_for_delivery_repair(_goal(**goal_kw), root_budget=_ledger(**ledger_kw), **kw)
    assert _fields(grant) == expected


@pytest.mark.parametrize(
    ("goal_kw", "kw", "expected"),
    [
        (dict(mae=2, rc=6, rs=257.0, progress=STARVED), dict(), ("cold-restart-repair-ep-1-fixed", 1, 2, 30.0)),
        (dict(mae=1, rc=4, rs=100.0, cycle=2, progress=STARVED), dict(), None),
        (dict(mae=1, rc=4, rs=100.0, progress=PROGRESSED), dict(), None),
        (dict(mae=0, rc=4, rs=100.0, progress=STARVED), dict(), None),
        (dict(mae=1, rc=0, rs=100.0, progress=STARVED), dict(), None),
        (dict(mae=6, mem=2, rc=2, rs=100.0, progress=STARVED), dict(), ("cold-restart-repair-ep-1-fixed", 1, 2, 30.0)),
        (dict(mae=1, rc=4, rs=100.0, progress=STARVED), dict(seconds_cap=15.0), ("cold-restart-repair-ep-1-fixed", 1, 1, 15.0)),
    ],
)
def test_grant_for_cold_restart_golden(goal_kw, kw, expected) -> None:
    goal = _goal(**goal_kw)
    grant = grant_for_cold_restart(goal, goal_kw["progress"], root_budget=_ledger(), **kw)
    assert _fields(grant) == expected


@pytest.mark.parametrize(
    ("goal_kw", "kw", "ledger_kw", "expected"),
    [
        (
            dict(mae=0, mem=1, rc=3, rs=100.0),
            dict(original_seconds=40.0, seconds_cap=30.0),
            dict(calls=4, seconds=40.0, allocated_seconds=20.0),
            ("backfill-repair-ep-1-fixed", 1, 1, 10.0),
        ),
        (dict(mem=1, rc=3, rs=100.0), dict(original_seconds=40.0, tools_open=False), dict(), None),
        (dict(mem=0, rc=3, rs=100.0), dict(original_seconds=40.0), dict(), None),
        (dict(mem=1, rc=0, rs=100.0), dict(original_seconds=40.0), dict(), None),
        (dict(mem=1, rc=3, rs=0.5), dict(original_seconds=40.0), dict(), None),
        (dict(mem=1, rc=3, rs=100.0), dict(original_seconds=200.0), dict(), ("backfill-repair-ep-1-fixed", 1, 1, 30.0)),
    ],
)
def test_grant_for_backfill_golden(goal_kw, kw, ledger_kw, expected) -> None:
    grant = grant_for_backfill(_goal(**goal_kw), root_budget=_ledger(**ledger_kw), **kw)
    assert _fields(grant) == expected


def test_grant_for_transient_model_retry_golden() -> None:
    goal = _goal(rc=0, rs=8.0)

    ledger = _ledger(calls=2, seconds=30.0, allocated_seconds=18.0)
    assert _fields(grant_for_transient_model_retry(goal, root_budget=ledger)) == (
        "transient-retry-repair-ep-1-fixed", 1, 0, 12.0,
    )
    assert grant_for_transient_model_retry(goal, root_budget=ledger) is None

    ledger = _ledger(calls=2, seconds=100.0, allocated_seconds=10.0)
    assert _fields(grant_for_transient_model_retry(goal, root_budget=ledger, attempt=1)) == (
        "transient-retry-repair-ep-1-fixed", 1, 0, 30.0,
    )
    assert _fields(grant_for_transient_model_retry(goal, root_budget=ledger, attempt=2)) == (
        "transient-retry-repair-ep-1-fixed-2", 1, 0, 30.0,
    )

    ledger = _ledger(calls=2, seconds=18.0, allocated_seconds=18.0)
    assert grant_for_transient_model_retry(goal, root_budget=ledger) is None

    ledger = _ledger(calls=2, seconds=100.0, allocated_seconds=10.0)
    assert _fields(
        grant_for_transient_model_retry(goal, root_budget=ledger, seconds_cap=12.5)
    ) == ("transient-retry-repair-ep-1-fixed", 1, 0, 12.5)
