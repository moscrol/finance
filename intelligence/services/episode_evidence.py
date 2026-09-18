"""Versioned private evidence checkpoint; not a public projection or replay permit.

Provider content_hash is an existing identity (not a signature of every field).
The snapshot digest additionally covers dates, ownership, structured values and
presentation order. Neither digest authenticates a user or an external source.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import math
from typing import TYPE_CHECKING

from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.agent_runtime import _json_copy

if TYPE_CHECKING:
    from collections.abc import Iterable
    from intelligence.services.evidence_ledger import EvidenceLedger

_FIELDS = frozenset({
    "schema_version", "kind", "episode_id", "information_cutoff", "entries",
    "presented_hashes", "covered_outputs", "open_gaps", "sha256",
})
_STRING_FIELDS = (
    "tool", "title", "detail", "source", "internal_locator", "evidence_tier",
    "independent_key", "freshness", "content_hash", "publisher_kind", "document_type",
)
# Explicit v1 schema: a new AgentEvidence field must make capture fail closed
# until its persistence/validation semantics have been deliberately chosen.
_ATOM_FIELDS = frozenset((*_STRING_FIELDS,
    "source_date", "supports", "contradicts", "derived_from", "observations",
    "reexcerpted", "pointer_dropped", "structural_neighbor_demoted", "deep_read",
))


def _object(value: object, expected: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"evidence {name} fields are incomplete or unknown")
    return value


def _strings(value: object, *, canonical: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("evidence field requires a string list")
    if canonical and (any(not item or item != item.strip() for item in value) or len(set(value)) != len(value)):
        raise ValueError("evidence identities must be unique nonempty canonical strings")
    return tuple(value)


def _digest(body: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _atom(raw: object) -> AgentEvidence:
    atom = _object(raw, _ATOM_FIELDS, "atom")
    if any(not isinstance(atom[key], str) for key in _STRING_FIELDS):
        raise ValueError("evidence atom text fields must be strings")
    identity = atom["content_hash"]
    if not identity or identity != identity.strip():
        raise ValueError("evidence content identity must be canonical and nonempty")
    if atom["source_date"] is not None and not isinstance(atom["source_date"], str):
        raise ValueError("evidence source_date must be a string or None")
    kwargs = dict(atom)
    for key in ("supports", "contradicts", "derived_from"):
        kwargs[key] = _strings(atom[key])
    if type(atom["deep_read"]) is not bool or (
        atom["reexcerpted"] is not None and type(atom["reexcerpted"]) is not bool
    ):
        raise ValueError("evidence boolean markers cannot be coerced")
    for key in ("pointer_dropped", "structural_neighbor_demoted"):
        value = atom[key]
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("evidence counters must be nonnegative integers or None")
    if not isinstance(atom["observations"], list):
        raise ValueError("evidence observations must be a list")
    observations = []
    for raw_observation in atom["observations"]:
        observation = _object(raw_observation, frozenset({"subject", "as_of", "metric", "value"}), "observation")
        if any(not isinstance(observation[key], str) for key in ("subject", "as_of", "metric")):
            raise ValueError("evidence observation text must be strings")
        value = observation["value"]
        try:
            finite = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError("evidence observation value must be a finite number")
        observations.append(StructuredObservation(**observation))
    kwargs["observations"] = tuple(observations)
    item = AgentEvidence(**kwargs)
    if _json_copy(asdict(item), path="atom") != atom:
        raise ValueError("evidence atom cannot be reconstructed without loss")
    return item


@dataclass(frozen=True)
class EvidenceCheckpointEntry:
    atom: AgentEvidence
    targets: tuple[str, ...]
    branch_owner: str | None
    cutoff_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "atom": _json_copy(asdict(self.atom), path="atom"),
            "targets": list(self.targets), "branch_owner": self.branch_owner,
            "cutoff_status": self.cutoff_status,
        }


@dataclass(frozen=True)
class EpisodeEvidenceSnapshot:
    episode_id: str
    information_cutoff: date | None
    entries: tuple[EvidenceCheckpointEntry, ...]
    presented_hashes: tuple[str, ...]
    covered_outputs: tuple[str, ...]
    open_gaps: tuple[str, ...]

    @property
    def presented_evidence(self) -> tuple[AgentEvidence, ...]:
        by_hash = {entry.atom.content_hash: entry.atom for entry in self.entries}
        return tuple(by_hash[digest] for digest in self.presented_hashes)

    def to_dict(self) -> dict[str, object]:
        body = {
            "schema_version": 1, "kind": "episode_evidence", "episode_id": self.episode_id,
            "information_cutoff": self.information_cutoff.isoformat() if self.information_cutoff else None,
            "entries": [entry.to_dict() for entry in self.entries],
            "presented_hashes": list(self.presented_hashes),
            "covered_outputs": list(self.covered_outputs), "open_gaps": list(self.open_gaps),
        }
        return {**body, "sha256": _digest(body)}

    @classmethod
    def from_dict(cls, payload: object, *, episode_id: str) -> EpisodeEvidenceSnapshot:
        from intelligence.services.evidence_ledger import _clean, _cutoff_status

        raw = _object(_json_copy(payload, path="evidence_snapshot"), _FIELDS, "snapshot")
        if type(raw["schema_version"]) is not int or raw["schema_version"] != 1 or raw["kind"] != "episode_evidence":
            raise ValueError("unsupported evidence snapshot version/kind")
        if not isinstance(raw["episode_id"], str) or raw["episode_id"] != episode_id or not episode_id or episode_id != episode_id.strip():
            raise ValueError("evidence snapshot episode identity mismatch")
        body = {key: value for key, value in raw.items() if key != "sha256"}
        if not isinstance(raw["sha256"], str) or raw["sha256"] != _digest(body):
            raise ValueError("evidence snapshot digest mismatch")
        cutoff = raw["information_cutoff"]
        if cutoff is not None:
            if not isinstance(cutoff, str):
                raise ValueError("evidence cutoff must be an ISO date or None")
            parsed_cutoff = date.fromisoformat(cutoff)
            if parsed_cutoff.isoformat() != cutoff:
                raise ValueError("evidence cutoff must be canonical")
            cutoff = parsed_cutoff
        if not isinstance(raw["entries"], list):
            raise ValueError("evidence entries must be a list")
        entries = []
        identities: set[str] = set()
        all_targets: set[str] = set()
        for record in raw["entries"]:
            entry = _object(record, frozenset({"atom", "targets", "branch_owner", "cutoff_status"}), "entry")
            atom = _atom(entry["atom"])
            if atom.content_hash in identities:
                raise ValueError("duplicate evidence content identity")
            identities.add(atom.content_hash)
            targets = _strings(entry["targets"], canonical=True)
            if not set(_clean((*atom.supports, *atom.contradicts))).issubset(targets):
                raise ValueError("evidence targets omit atom support/contradiction links")
            all_targets.update(targets)
            owner = entry["branch_owner"]
            if owner is not None and (not isinstance(owner, str) or not owner or owner != owner.strip()):
                raise ValueError("evidence branch owner must be canonical or None")
            status = _cutoff_status(atom, cutoff)
            if status is None or status != entry["cutoff_status"]:
                raise ValueError("evidence source date/cutoff status mismatch")
            entries.append(EvidenceCheckpointEntry(atom, targets, owner, status))
        presented = _strings(raw["presented_hashes"], canonical=True)
        if not set(presented).issubset(identities):
            raise ValueError("presented evidence is absent from the ledger")
        covered = _strings(raw["covered_outputs"], canonical=True)
        gaps = _strings(raw["open_gaps"], canonical=True)
        if list(covered) != sorted(covered) or list(gaps) != sorted(gaps) or not set(covered).issubset(all_targets):
            raise ValueError("evidence coverage/gaps do not reconcile with targets")
        return cls(episode_id, cutoff, tuple(entries), presented, covered, gaps)


def capture_evidence_snapshot(
    *, episode_id: str, ledger: EvidenceLedger, presented_evidence: Iterable[AgentEvidence],
) -> dict[str, object]:
    return ledger.to_recovery_snapshot(episode_id=episode_id, presented_evidence=presented_evidence)
