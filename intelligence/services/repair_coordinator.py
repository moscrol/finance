"""Provider-neutral repair goals and progress predicates.

The coordinator describes missing work; it never invents a query or selects a
tool. The primary model retains that decision inside the same episode.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4

from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.research_contract import RootBudgetLedger


@dataclass(frozen=True)
class CoverageDelta:
    new_evidence: int
    narrowed_gaps: int
    newly_supported_outputs: int

    @property
    def progressed(self) -> bool:
        return self.new_evidence >= 1 and (
            self.narrowed_gaps >= 1 or self.newly_supported_outputs >= 1
        )


@dataclass(frozen=True)
class ProgressSnapshot:
    before_evidence_ids: tuple[str, ...]
    after_evidence_ids: tuple[str, ...]
    before_covered_outputs: tuple[str, ...]
    after_covered_outputs: tuple[str, ...]
    before_open_gaps: tuple[str, ...]
    after_open_gaps: tuple[str, ...]
    independent_source_families: tuple[str, ...]
    before_evidence_source_families: tuple[tuple[str, str], ...] = ()
    after_evidence_source_families: tuple[tuple[str, str], ...] = ()
    before_evidence_targets: tuple[tuple[str, tuple[str, ...]], ...] = ()
    after_evidence_targets: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def effective_new_evidence(self) -> int:
        before_ids = set(self.before_evidence_ids)
        before_families = {
            family for _, family in self.before_evidence_source_families
        }
        after_pairs = tuple(self.after_evidence_source_families)
        after_targets = dict(self.after_evidence_targets)
        if not after_pairs or not after_targets:
            return 0
        before_outputs = set(self.before_covered_outputs)
        families = {
            family
            for evidence_id, family in after_pairs
            if evidence_id not in before_ids
            and family not in before_families
            and (
                any(
                    target not in before_outputs
                    for target in after_targets.get(evidence_id, ())
                )
            )
        }
        return len(families)

    @property
    def coverage_delta(self) -> CoverageDelta:
        return CoverageDelta(
            new_evidence=self.effective_new_evidence,
            narrowed_gaps=len(
                set(self.before_open_gaps) - set(self.after_open_gaps)
            ),
            newly_supported_outputs=len(
                set(self.after_covered_outputs) - set(self.before_covered_outputs)
            ),
        )

    def to_dict(self) -> dict[str, object]:
        delta = self.coverage_delta
        return {
            "before_evidence_ids": list(self.before_evidence_ids),
            "after_evidence_ids": list(self.after_evidence_ids),
            "before_covered_outputs": list(self.before_covered_outputs),
            "after_covered_outputs": list(self.after_covered_outputs),
            "before_open_gaps": list(self.before_open_gaps),
            "after_open_gaps": list(self.after_open_gaps),
            "independent_source_families": list(self.independent_source_families),
            "before_evidence_source_families": [
                list(item) for item in self.before_evidence_source_families
            ],
            "after_evidence_source_families": [
                list(item) for item in self.after_evidence_source_families
            ],
            "before_evidence_targets": [
                [evidence_id, list(targets)]
                for evidence_id, targets in self.before_evidence_targets
            ],
            "after_evidence_targets": [
                [evidence_id, list(targets)]
                for evidence_id, targets in self.after_evidence_targets
            ],
            "coverage_delta": {
                "new_evidence": delta.new_evidence,
                "narrowed_gaps": delta.narrowed_gaps,
                "newly_supported_outputs": delta.newly_supported_outputs,
            },
        }


@dataclass(frozen=True)
class BudgetGrant:
    grant_id: str
    episode_id: str
    cycle: int
    calls_granted: int
    seconds_granted: float


@dataclass(frozen=True)
class RepairGoal:
    episode_id: str
    repair_goal_id: str
    cycle: int
    missing_answer_elements: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    missing_evidence_modes: tuple[str, ...]
    attempted_actions: tuple[str, ...]
    evidence_progress: CoverageDelta
    remaining_calls: int
    remaining_seconds: float
    # 冷启动修复专用：主检索窗已烧穿时，允许修复轮在授予的窗口内重开工具。
    # 只由 admit_repair 在 grant_for_cold_restart 命中时置位，模型无权申请。
    reopen_tools: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "repair_goal_id": self.repair_goal_id,
            "cycle": self.cycle,
            "missing_answer_elements": list(self.missing_answer_elements),
            "unsupported_claims": list(self.unsupported_claims),
            "missing_evidence_modes": list(self.missing_evidence_modes),
            "attempted_actions": list(self.attempted_actions),
            "evidence_progress": {
                "new_evidence": self.evidence_progress.new_evidence,
                "narrowed_gaps": self.evidence_progress.narrowed_gaps,
                "newly_supported_outputs": self.evidence_progress.newly_supported_outputs,
            },
            "remaining_calls": self.remaining_calls,
            "remaining_seconds": self.remaining_seconds,
            "reopen_tools": self.reopen_tools,
        }


@dataclass(frozen=True)
class RepairAdmission:
    """One code-owned repair decision ready for an Episode to execute."""

    goal: RepairGoal
    grant: BudgetGrant
    delivery_only: bool = False


def _unique(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(value).strip() for value in (values or ()) if str(value).strip())
    )


def progress_from_ledger(
    before: EvidenceLedgerSnapshot,
    after: EvidenceLedgerSnapshot,
) -> ProgressSnapshot:
    return ProgressSnapshot(
        before_evidence_ids=before.evidence_ids,
        after_evidence_ids=after.evidence_ids,
        before_covered_outputs=before.covered_outputs,
        after_covered_outputs=after.covered_outputs,
        before_open_gaps=before.open_gaps,
        after_open_gaps=after.open_gaps,
        independent_source_families=after.independent_source_families,
        before_evidence_source_families=before.evidence_source_families,
        after_evidence_source_families=after.evidence_source_families,
        before_evidence_targets=before.evidence_targets,
        after_evidence_targets=after.evidence_targets,
    )


def build_repair_goal(
    *,
    episode_id: str,
    missing_outputs: tuple[str, ...] = (),
    missing_capabilities: tuple[str, ...] = (),
    rejected_claims: tuple[str, ...] = (),
    attempted_actions: tuple[str, ...] = (),
    previous_progress: ProgressSnapshot,
    remaining_calls: int,
    remaining_seconds: float,
    cycle: int = 1,
) -> RepairGoal:
    episode = str(episode_id or "").strip()
    if not episode:
        raise ValueError("episode_id must be non-empty")
    if cycle < 1:
        raise ValueError("repair cycle must be positive")
    return RepairGoal(
        episode_id=episode,
        repair_goal_id=f"repair-{episode}-{cycle}-{uuid4().hex[:10]}",
        cycle=cycle,
        missing_answer_elements=_unique(missing_outputs),
        unsupported_claims=_unique(rejected_claims),
        missing_evidence_modes=_unique(missing_capabilities),
        attempted_actions=_unique(attempted_actions),
        evidence_progress=previous_progress.coverage_delta,
        remaining_calls=max(0, int(remaining_calls)),
        remaining_seconds=max(0.0, float(remaining_seconds)),
    )


def should_reenter(
    progress: ProgressSnapshot,
    *,
    cycle: int,
    max_cycles: int,
    remaining_calls: int | None = None,
    remaining_seconds: float | None = None,
    tools_open: bool = True,
) -> bool:
    if cycle < 1 or cycle > max_cycles:
        return False
    if not progress.coverage_delta.progressed:
        return False
    if tools_open and remaining_calls is not None and remaining_calls <= 0:
        return False
    if remaining_seconds is not None and remaining_seconds < 1.0:
        return False
    return True


def max_repair_cycles_for_tier(research_tier: str) -> int:
    tier = str(research_tier or "").strip().lower()
    if tier == "deep":
        return 3
    if tier in {"quick", "standard"}:
        return 1
    raise ValueError(f"unsupported repair research tier: {research_tier}")


def grant_for_progress(
    goal: RepairGoal,
    progress: ProgressSnapshot,
    *,
    root_budget: RootBudgetLedger,
    research_tier: str,
    tools_open: bool = True,
) -> BudgetGrant | None:
    if not should_reenter(
        progress,
        cycle=goal.cycle,
        max_cycles=max_repair_cycles_for_tier(research_tier),
        remaining_calls=goal.remaining_calls,
        remaining_seconds=goal.remaining_seconds,
        tools_open=tools_open,
    ):
        return None
    work_units = min(
        4,
        max(1, len(goal.missing_answer_elements) + len(goal.missing_evidence_modes)),
    )
    calls = min(work_units, goal.remaining_calls) if tools_open else 0
    seconds = min(goal.remaining_seconds, 30.0, work_units * 8.0)
    if tools_open and calls <= 0:
        return None
    if seconds < 1.0:
        return None
    grant = BudgetGrant(
        grant_id=f"grant-{goal.repair_goal_id}",
        episode_id=goal.episode_id,
        cycle=goal.cycle,
        calls_granted=calls,
        seconds_granted=seconds,
    )
    return grant if root_budget.grant(grant) else None


def grant_for_cold_restart(
    goal: RepairGoal,
    progress: ProgressSnapshot,
    *,
    root_budget: RootBudgetLedger,
) -> BudgetGrant | None:
    """Grant one tool-open restart turn for an episode starved of evidence.

    进度闸（``should_reenter`` 的 ``coverage_delta.progressed``）要求主路径至少
    捞到 1 条证据才配修复——它挡的是「无进展还无限续命」的循环。但它把另一种
    形状一并挡死：检索窗被首个打偏的查询烧穿、末尾批量补发的检索在截止线上被
    集体判 ``tool_timeout``、episode 以**零证据**终局，而轮预算还有大量未分配
    余量（2026-08-13 R7-A3 实测：43s 失败终局，root 余量 ~257s）。

    冷启动是进度闸的镜像兜底，与 ``grant_for_delivery_repair`` 互斥：
    delivery 修复要求「有证据、没答案」，冷启动要求「有尝试、零证据」。
    三道准入缺一不可——

    - ``cycle == 1``：只给一发，失败不再续（防循环，与进度闸的目的一致）；
    - ``attempted_actions`` 非空：模型确实尝试过检索，是「饿死」不是「没干活」；
    - ``after_evidence_ids`` 为空：一旦有任何证据，走常规进度/交付通道。

    授予额度沿用进度修复的公式（≤30s、按缺口计工时），从 root 未分配余量铸造，
    失败即 fail closed。
    """

    if goal.cycle != 1:
        return None
    if progress.after_evidence_ids:
        return None
    if not goal.attempted_actions:
        return None
    if not goal.missing_answer_elements:
        return None
    if goal.remaining_calls < 1 or goal.remaining_seconds < 1.0:
        return None
    work_units = min(
        4,
        max(1, len(goal.missing_answer_elements) + len(goal.missing_evidence_modes)),
    )
    calls = min(work_units, goal.remaining_calls)
    seconds = min(goal.remaining_seconds, 30.0, work_units * 8.0)
    if calls < 1 or seconds < 1.0:
        return None
    grant = BudgetGrant(
        grant_id=f"cold-restart-{goal.repair_goal_id}",
        episode_id=goal.episode_id,
        cycle=goal.cycle,
        calls_granted=calls,
        seconds_granted=seconds,
    )
    return grant if root_budget.grant(grant) else None


def grant_for_delivery_repair(
    goal: RepairGoal,
    *,
    root_budget: RootBudgetLedger,
    research_tier: str,
    evidence_count: int,
) -> BudgetGrant | None:
    """Grant one tool-closed delivery turn from already collected evidence.

    Research continuation still requires provenance-backed coverage progress via
    :func:`grant_for_progress`.  This narrower grant exists for the opposite
    seam: the research turn timed out *after* collecting evidence but *before*
    it produced a draft or bindings.  Requiring an already-closed output gap in
    that state would make repair conditional on the work repair must perform.

    The grant cannot reopen tools, cannot run without evidence, and remains
    bounded by the code-owned tier cycle cap and root seconds ledger.
    """

    if evidence_count <= 0:
        return None
    if goal.cycle < 1 or goal.cycle > max_repair_cycles_for_tier(research_tier):
        return None
    if not goal.missing_answer_elements:
        return None
    if goal.remaining_seconds < 1.0:
        return None
    work_units = min(4, max(1, len(goal.missing_answer_elements)))
    seconds = min(goal.remaining_seconds, 30.0, work_units * 8.0)
    if seconds < 1.0:
        return None
    grant = BudgetGrant(
        grant_id=f"delivery-grant-{goal.repair_goal_id}",
        episode_id=goal.episode_id,
        cycle=goal.cycle,
        calls_granted=0,
        seconds_granted=seconds,
    )
    return grant if root_budget.grant(grant) else None


def grant_for_transient_model_retry(
    goal: RepairGoal,
    *,
    root_budget: RootBudgetLedger,
) -> BudgetGrant | None:
    """超时把修复窗口烧穿后，从 hard-cap 未分配余量再铸一笔秒数。

    修复授予是 ``min(剩余, 30, 缺口×8)``，常只有 8 秒；生产 ``llm_timeout``
    是 75 秒。第一次 ``complete`` 的 timeout 因此等于整笔授予，真实
    TimeoutError 会把 repair deadline 吃到 0——「失败后再看余量」这条
    重试闸门对超时是死代码。

    尺寸必须按 **root 未分配余量** 算，不能按 ``goal.remaining_seconds``：
    admission 已把后者替换成刚烧穿的那笔授予（生产实测 16s / 8s），按它
    重铸等于用同样大小的窗口对着 P50≈28s 的 provider 再撞一次——
    2026-08-13 R4 验收 A4/A5/A8/A9/A10 五题全是这个死法。

    这笔 grant 动的是 research 从未分配的 hard-cap 余量（synthesis
    reserve 那截），不重开工具槽，不突破单笔 30 秒帽。铸不出就 fail
    closed。grant_id 按 repair_goal 固定，同一 goal 第二次调用会被
    root ledger 拒掉，和熔断上限 1 对齐。
    """

    headroom = max(
        0.0,
        float(root_budget.hard_seconds_cap) - float(root_budget.allocated_seconds),
    )
    seconds = min(headroom, 30.0)
    if seconds < 1.0:
        return None
    grant = BudgetGrant(
        grant_id=f"transient-retry-{goal.repair_goal_id}",
        episode_id=goal.episode_id,
        cycle=goal.cycle,
        calls_granted=0,
        seconds_granted=seconds,
    )
    return grant if root_budget.grant(grant) else None


def admit_repair(
    *,
    episode_id: str,
    missing_outputs: tuple[str, ...] = (),
    missing_capabilities: tuple[str, ...] = (),
    rejected_claims: tuple[str, ...] = (),
    attempted_actions: tuple[str, ...] = (),
    previous_progress: ProgressSnapshot,
    remaining_calls: int,
    remaining_seconds: float,
    cycle: int,
    root_budget: RootBudgetLedger,
    research_tier: str,
    tools_open: bool = True,
    allow_delivery_repair: bool = True,
    delivery_candidate: bool = False,
    evidence_count: int = 0,
) -> RepairAdmission | None:
    """Build one goal and admit exactly one budget grant.

    The coordinator owns the policy choice between evidence-progress repair and
    tool-closed delivery repair. Callers receive one immutable decision and do
    not need to duplicate cycle, tier, or root-budget rules.
    """

    goal = build_repair_goal(
        episode_id=episode_id,
        missing_outputs=missing_outputs,
        missing_capabilities=missing_capabilities,
        rejected_claims=rejected_claims,
        attempted_actions=attempted_actions,
        previous_progress=previous_progress,
        remaining_calls=remaining_calls,
        remaining_seconds=remaining_seconds,
        cycle=cycle,
    )
    grant: BudgetGrant | None = None
    delivery_only = False
    cold_restart = False
    if not delivery_candidate:
        grant = grant_for_progress(
            goal,
            previous_progress,
            root_budget=root_budget,
            research_tier=research_tier,
            tools_open=tools_open,
        )
    if (
        grant is None
        and allow_delivery_repair
        and (not tools_open or delivery_candidate)
        and evidence_count > 0
        and missing_outputs
    ):
        grant = grant_for_delivery_repair(
            goal,
            root_budget=root_budget,
            research_tier=research_tier,
            evidence_count=evidence_count,
        )
        delivery_only = grant is not None
    if (
        grant is None
        and not delivery_candidate
        and evidence_count == 0
        and missing_outputs
    ):
        grant = grant_for_cold_restart(
            goal,
            previous_progress,
            root_budget=root_budget,
        )
        cold_restart = grant is not None
    if grant is None:
        return None
    return RepairAdmission(
        goal=replace(
            goal,
            remaining_calls=grant.calls_granted,
            remaining_seconds=grant.seconds_granted,
            reopen_tools=cold_restart,
        ),
        grant=grant,
        delivery_only=delivery_only,
    )


__all__ = [
    "BudgetGrant",
    "CoverageDelta",
    "ProgressSnapshot",
    "RepairAdmission",
    "RepairGoal",
    "admit_repair",
    "build_repair_goal",
    "grant_for_cold_restart",
    "grant_for_delivery_repair",
    "grant_for_progress",
    "grant_for_transient_model_retry",
    "max_repair_cycles_for_tier",
    "progress_from_ledger",
    "should_reenter",
]
