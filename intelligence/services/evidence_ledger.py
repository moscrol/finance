"""Append-only evidence state for one continuous research episode.

The ledger is deliberately narrower than ``ResearchState``: it records
provider evidence and the small coverage projection needed by repair logic.
It does not own the user's decision or presentation state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from threading import RLock
from typing import Callable, Iterable, Literal

from intelligence.services.agent_research import AgentEvidence


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _source_family(item: AgentEvidence) -> str:
    return (
        str(item.independent_key or "").strip()
        or str(item.source or "").strip()
        or str(item.tool or "").strip()
        or "unknown"
    )


def _valid_for_cutoff(item: AgentEvidence, cutoff: date | None) -> bool:
    if cutoff is None or not item.source_date:
        return True
    try:
        return date.fromisoformat(str(item.source_date)[:10]) <= cutoff
    except ValueError:
        return False


EvidenceCutoffStatus = Literal["verified", "undated", "unbounded"]


def _cutoff_status(
    item: AgentEvidence,
    cutoff: date | None,
) -> EvidenceCutoffStatus | None:
    if not item.source_date:
        return "undated"
    try:
        source_date = date.fromisoformat(str(item.source_date)[:10])
    except ValueError:
        return None
    if cutoff is None:
        return "unbounded"
    return "verified" if source_date <= cutoff else None


@dataclass(frozen=True)
class EvidenceLedgerSnapshot:
    evidence_ids: tuple[str, ...]
    covered_outputs: tuple[str, ...]
    open_gaps: tuple[str, ...]
    independent_source_families: tuple[str, ...]
    evidence_source_families: tuple[tuple[str, str], ...] = ()
    evidence_targets: tuple[tuple[str, tuple[str, ...]], ...] = ()
    evidence_cutoff_status: tuple[tuple[str, EvidenceCutoffStatus], ...] = ()
    evidence_branch_owners: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_ids": list(self.evidence_ids),
            "covered_outputs": list(self.covered_outputs),
            "open_gaps": list(self.open_gaps),
            "independent_source_families": list(self.independent_source_families),
            "evidence_source_families": [
                list(item) for item in self.evidence_source_families
            ],
            "evidence_targets": [
                [evidence_id, list(targets)]
                for evidence_id, targets in self.evidence_targets
            ],
            "evidence_cutoff_status": [
                list(item) for item in self.evidence_cutoff_status
            ],
            "evidence_branch_owners": [
                list(item) for item in self.evidence_branch_owners
            ],
        }


class EvidenceLedger:
    """Thread-safe append-only evidence collection with immutable snapshots."""

    def __init__(self, *, information_cutoff: date | None = None) -> None:
        self._cutoff = information_cutoff
        self._items: dict[str, AgentEvidence] = {}
        self._targets: dict[str, tuple[str, ...]] = {}
        self._branch_owners: dict[str, str] = {}
        self._covered_outputs: set[str] = set()
        self._open_gaps: set[str] = set()
        self._lock = RLock()

    @property
    def information_cutoff(self) -> date | None:
        return self._cutoff

    def append(
        self,
        evidence: AgentEvidence | Iterable[AgentEvidence],
        *,
        covered_outputs: Iterable[str] = (),
        open_gaps: Iterable[str] = (),
    ) -> tuple[str, ...]:
        """Append cutoff-valid, content-hash-addressed evidence.

        Empty hashes are ignored because they cannot support a repair or a
        citation. Re-appending an existing hash is idempotent and never
        replaces the original provider atom.
        """

        return self._append_values(
            evidence,
            covered_outputs=covered_outputs,
            open_gaps=open_gaps,
        )

    def branch_sink(self, branch_id: str) -> "BranchEvidenceSink":
        owner = str(branch_id or "").strip()
        if not owner:
            raise ValueError("branch_id must be non-empty")
        return BranchEvidenceSink(
            branch_id=owner,
            _append_fn=self._append_from_branch,
            _snapshot_fn=self.snapshot,
        )

    def _append_values(
        self,
        evidence: AgentEvidence | Iterable[AgentEvidence],
        *,
        covered_outputs: Iterable[str] = (),
        open_gaps: Iterable[str] = (),
        branch_id: str | None = None,
    ) -> tuple[str, ...]:
        values = (evidence,) if isinstance(evidence, AgentEvidence) else tuple(evidence)
        added: list[str] = []
        requested_outputs = _clean(covered_outputs)
        with self._lock:
            for item in values:
                if not isinstance(item, AgentEvidence):
                    raise TypeError("evidence ledger accepts AgentEvidence values")
                content_hash = str(item.content_hash or "").strip()
                if not content_hash or not _valid_for_cutoff(item, self._cutoff):
                    continue
                if content_hash in self._items:
                    continue
                self._items[content_hash] = item
                self._targets[content_hash] = _clean(
                    (*requested_outputs, *item.supports, *item.contradicts)
                )
                if branch_id is not None:
                    self._branch_owners[content_hash] = branch_id
                added.append(content_hash)
            if added:
                self._covered_outputs.update(requested_outputs)
            self._open_gaps.update(_clean(open_gaps))
        return tuple(added)

    def _append_from_branch(
        self,
        branch_id: str,
        evidence: AgentEvidence | Iterable[AgentEvidence],
    ) -> tuple[str, ...]:
        owner = str(branch_id or "").strip()
        if not owner:
            raise ValueError("branch_id must be non-empty")
        return self._append_values(evidence, branch_id=owner)

    def mark_output_covered(
        self,
        output_id: str,
        *,
        evidence_ids: Iterable[str],
    ) -> bool:
        value = str(output_id or "").strip()
        ids = _clean(evidence_ids)
        if not value or not ids:
            return False
        with self._lock:
            if any(evidence_id not in self._items for evidence_id in ids):
                return False
            for evidence_id in ids:
                self._targets[evidence_id] = _clean(
                    (*self._targets.get(evidence_id, ()), value)
                )
            self._covered_outputs.add(value)
            return True

    def close_gap(self, gap: str) -> None:
        value = str(gap or "").strip()
        if value:
            with self._lock:
                self._open_gaps.discard(value)

    def open_gap(self, gap: str) -> None:
        value = str(gap or "").strip()
        if value:
            with self._lock:
                self._open_gaps.add(value)

    def items(self) -> tuple[AgentEvidence, ...]:
        with self._lock:
            return tuple(self._items.values())

    def snapshot(self) -> EvidenceLedgerSnapshot:
        with self._lock:
            families = tuple(
                (content_hash, _source_family(item))
                for content_hash, item in self._items.items()
            )
            unique_families = _clean(family for _, family in families)
            return EvidenceLedgerSnapshot(
                evidence_ids=tuple(self._items),
                covered_outputs=tuple(sorted(self._covered_outputs)),
                open_gaps=tuple(sorted(self._open_gaps)),
                independent_source_families=unique_families,
                evidence_source_families=families,
                evidence_targets=tuple(self._targets.items()),
                evidence_cutoff_status=tuple(
                    (
                        content_hash,
                        _cutoff_status(item, self._cutoff) or "undated",
                    )
                    for content_hash, item in self._items.items()
                ),
                evidence_branch_owners=tuple(self._branch_owners.items()),
            )


@dataclass(frozen=True)
class BranchEvidenceSink:
    """Narrow append-only view granted to one read-only research branch."""

    branch_id: str
    _append_fn: Callable[
        [str, AgentEvidence | Iterable[AgentEvidence]], tuple[str, ...]
    ]
    _snapshot_fn: Callable[[], EvidenceLedgerSnapshot]

    def append(
        self,
        evidence: AgentEvidence | Iterable[AgentEvidence],
    ) -> tuple[str, ...]:
        return self._append_fn(self.branch_id, evidence)

    def snapshot(self) -> EvidenceLedgerSnapshot:
        return self._snapshot_fn()


__all__ = [
    "BranchEvidenceSink",
    "EvidenceCutoffStatus",
    "EvidenceLedger",
    "EvidenceLedgerSnapshot",
]
