"""repair_policy 第一刀（M1–M4）：判据拆两侧后，授予逐字段不变。

对照 `docs/superpowers/specs/2026-09-02-repair-policy-state-machine.md` §3.3：

- M1 `should_reenter` 四条闸 → 领域两条（`repair_is_warranted`）∧ 预算两条
  （`can_afford_repair`）；M4 `max_repair_cycles_for_tier` 随领域侧走
  （`cycle_within_tier`）。
- M2 `grant_for_progress` 四种职责 → 领域闸 / 预算窗 / 记账三段，各自具名。
- M3 `work_units` 公式 → 领域出格数（`repair_work_units`），预算折调用
  （`calls_for_work_units`）。
- M6 三个 candidate 判据 + 两个 stop_reason 集合从 `runtime/continuous_turn_adapter`
  搬到 `services/repair_coordinator.classify_repair_failure`（领域失败分类）；
  adapter 只叠「交付修复只许一次」这一条底座的账。

金标来自拆分前 `fed88564` 的 `repair_coordinator`，脚本一次性跑出后钉在这里；
所有 `grant_id` / `cycle` / `calls_granted` / `seconds_granted` 逐字段比对。
"""

from __future__ import annotations

import ast
import itertools
from pathlib import Path

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_verifier import VerifiedEpisodeOutcome
from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.generic_research_owner import CompletionReport
from intelligence.runtime.repair_budget import (
    calls_for_work_units,
    can_afford_repair,
    grant_for_backfill,
    grant_for_cold_restart,
    grant_for_delivery_repair,
    grant_for_progress,
    grant_for_transient_model_retry,
    size_repair_window,
)
from intelligence.services.repair_coordinator import (
    COLD_RESTART_STOP_REASONS,
    DELIVERY_REPAIR_STOP_REASONS,
    BudgetGrant,
    ProgressSnapshot,
    RepairGoal,
    classify_repair_failure,
    cycle_within_tier,
    max_repair_cycles_for_tier,
    progress_from_ledger,
    repair_is_warranted,
    repair_work_units,
)
from intelligence.services.research_contract import InMemoryRootBudgetLedger
from intelligence.services.track_contract import TRACK_CONTRACT_OUTPUT_ID_SET


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


# --- M6：失败分类搬到领域侧，与 adapter 原内联表达式逐格相等 ---------------------


_EVIDENCE = AgentEvidence(
    tool="market_data",
    title="t",
    detail="d",
    source="s",
    content_hash="h1",
)
_BINDING = OutputEvidenceBinding("direct_assessment", ("h1",))
_TRACK_SLOT = next(iter(sorted(TRACK_CONTRACT_OUTPUT_ID_SET)))


def _verified(*, stop_reason, has_evidence, draft, has_binding, structural_missing):
    outcome = AgentOutcome(
        task_frame_hash="tf",
        status="partial",
        draft=draft,
        evidence=(_EVIDENCE,) if has_evidence else (),
        traces=(),
        gaps=(),
        stop_reason=stop_reason,
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "tf"}),),
        bindings=(_BINDING,) if has_binding else (),
        usage=AgentUsage(),
    )
    structural = VerifiedEpisodeOutcome(
        outcome=outcome,
        completion=CompletionReport(status="partial", outputs=()),
        verified_status="partial",
        missing_outputs=structural_missing,
    )
    return outcome, structural


def _legacy_candidates(outcome, structural, *, missing_outputs, rejected_claims, semantic_gap_outputs):
    """adapter `_resume_for_gap` 拆分前的三条内联表达式（去掉 allow_delivery_repair）。"""

    from intelligence.services.track_contract import is_contract_rewrite_only

    delivery = bool(
        outcome.stop_reason in {"sdk_invalid_finish", "sdk_invalid_repair_finish", "sdk_timeout"}
        and outcome.evidence
        and structural.missing_outputs
        and (not outcome.draft.strip() or not outcome.bindings)
    )
    cold = outcome.stop_reason in {"deadline_exhausted", "model_unavailable"} and not outcome.evidence
    rewrite = is_contract_rewrite_only(
        missing_outputs, rejected_claims=rejected_claims, semantic_gap_outputs=semantic_gap_outputs
    )
    return delivery, cold, rewrite


def test_classify_repair_failure_matches_adapter_inline_predicates() -> None:
    stop_reasons = (
        "model_finish",
        "sdk_timeout",
        "sdk_invalid_finish",
        "sdk_invalid_repair_finish",
        "deadline_exhausted",
        "model_unavailable",
        "repair_model_stop",
    )
    missing_variants = ((), ("direct_assessment",), (_TRACK_SLOT,))
    seen = {"delivery": 0, "cold_restart": 0, "contract_rewrite": 0}
    for stop_reason, has_evidence, draft, has_binding, structural_missing, semantic, rejected in (
        itertools.product(
            stop_reasons,
            (True, False),
            ("", "  ", "有稿"),
            (True, False),
            missing_variants,
            ((), ("counterpoint",)),
            ((), ("claim_index:0",)),
        )
    ):
        outcome, structural = _verified(
            stop_reason=stop_reason,
            has_evidence=has_evidence,
            draft=draft,
            has_binding=has_binding,
            structural_missing=structural_missing,
        )
        missing_outputs = tuple(dict.fromkeys((*structural_missing, *semantic)))
        shape = classify_repair_failure(
            outcome,
            structural,
            missing_outputs=missing_outputs,
            rejected_claims=rejected,
            semantic_gap_outputs=semantic,
        )
        legacy = _legacy_candidates(
            outcome,
            structural,
            missing_outputs=missing_outputs,
            rejected_claims=rejected,
            semantic_gap_outputs=semantic,
        )
        assert (shape.delivery, shape.cold_restart, shape.contract_rewrite) == legacy, (
            stop_reason, has_evidence, draft, has_binding, structural_missing, semantic, rejected
        )
        seen["delivery"] += shape.delivery
        seen["cold_restart"] += shape.cold_restart
        seen["contract_rewrite"] += shape.contract_rewrite
    # 三类各自都在网格里真的出现过，否则等价断言是空话。
    assert all(count > 0 for count in seen.values()), seen


def test_stop_reason_sets_moved_verbatim() -> None:
    assert DELIVERY_REPAIR_STOP_REASONS == frozenset(
        {"sdk_invalid_finish", "sdk_invalid_repair_finish", "sdk_timeout"}
    )
    assert COLD_RESTART_STOP_REASONS == frozenset({"deadline_exhausted", "model_unavailable"})
    # 「模型主动收场」不是饿死：零证据 model_finish 不得被分类成冷启动。
    outcome, structural = _verified(
        stop_reason="model_finish",
        has_evidence=False,
        draft="",
        has_binding=False,
        structural_missing=("direct_assessment",),
    )
    shape = classify_repair_failure(
        outcome, structural, missing_outputs=("direct_assessment",), rejected_claims=(), semantic_gap_outputs=()
    )
    assert shape == shape.__class__(delivery=False, cold_restart=False, contract_rewrite=False)


def test_adapter_no_longer_owns_failure_classification() -> None:
    """棘轮（状态机 spec §5 第 4 条）：两个 stop_reason 集合与三条判据不得回焊到底座。"""

    source = Path("intelligence/runtime/continuous_turn_adapter.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_constants = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "_DELIVERY_REPAIR_STOP_REASONS" not in module_constants
    assert "_COLD_RESTART_STOP_REASONS" not in module_constants
    imported = {
        (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        for alias in node.names
    }
    assert ("intelligence.services.track_contract", "is_contract_rewrite_only") not in imported
    # 准入半之后 adapter 连领域函数都不直接调了：申请一律经 harness。
    for symbol in (
        "classify_repair_failure",
        "classify_repair_need",
        "repair_is_warranted",
        "warrant_repair",
        "cycle_within_tier",
        "repair_work_units",
    ):
        assert ("intelligence.services.repair_coordinator", symbol) not in imported, symbol
    assert "sdk_invalid_repair_finish" not in source
    assert "self._harness.classify_repair_need(" in source
    assert "self._harness.warrant_repair(" in source


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
    # 金标是「领域判定 + 预算算术」一起铸出来的值；领域那半现在由 harness 算好递进去。
    research_tier = kw.pop("research_tier")
    grant = grant_for_progress(
        goal,
        root_budget=_ledger(**ledger_kw),
        warranted=repair_is_warranted(progress, cycle=goal.cycle, research_tier=research_tier),
        work_units=repair_work_units(goal),
        **kw,
    )
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
    goal = _goal(**goal_kw)
    research_tier = kw.pop("research_tier")
    grant = grant_for_delivery_repair(
        goal,
        root_budget=_ledger(**ledger_kw),
        cycle_allowed=cycle_within_tier(goal.cycle, research_tier=research_tier),
        **kw,
    )
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
    grant = grant_for_cold_restart(
        goal,
        goal_kw["progress"],
        root_budget=_ledger(),
        work_units=repair_work_units(goal),
        **kw,
    )
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
