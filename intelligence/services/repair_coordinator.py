"""Provider-neutral repair goals and progress predicates.

The coordinator describes missing work; it never invents a query or selects a
tool. The primary model retains that decision inside the same episode.
"""

from __future__ import annotations

from dataclasses import dataclass
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
        if not after_pairs:
            return len(set(self.after_evidence_ids) - before_ids)
        before_outputs = set(self.before_covered_outputs)
        families = {
            family
            for evidence_id, family in after_pairs
            if evidence_id not in before_ids
            and family not in before_families
            and (
                not self.after_evidence_targets
                or any(
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
        }


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
) -> bool:
    if cycle < 1 or cycle > max_cycles:
        return False
    if not progress.coverage_delta.progressed:
        return False
    if remaining_calls is not None and remaining_calls <= 0:
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
) -> BudgetGrant | None:
    if not should_reenter(
        progress,
        cycle=goal.cycle,
        max_cycles=max_repair_cycles_for_tier(research_tier),
        remaining_calls=goal.remaining_calls,
        remaining_seconds=goal.remaining_seconds,
    ):
        return None
    calls = min(
        4,
        max(1, len(goal.missing_answer_elements) + len(goal.missing_evidence_modes)),
    )
    seconds = min(30.0, calls * 8.0)
    grant = BudgetGrant(
        grant_id=f"grant-{goal.repair_goal_id}",
        episode_id=goal.episode_id,
        cycle=goal.cycle,
        calls_granted=calls,
        seconds_granted=seconds,
    )
    return grant if root_budget.grant(grant) else None


__all__ = [
    "BudgetGrant",
    "CoverageDelta",
    "ProgressSnapshot",
    "RepairGoal",
    "build_repair_goal",
    "grant_for_progress",
    "max_repair_cycles_for_tier",
    "progress_from_ledger",
    "should_reenter",
]
