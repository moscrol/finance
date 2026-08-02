"""Fail-closed durable-memory promotion from reviewed provenance only."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import re
from typing import Literal


MemoryKind = Literal[
    "decision_lesson",
    "user_correction",
    "user_preference",
    "volatile_fact",
    "model_judgment",
]
TargetLayer = Literal["durable_experience", "none"]
_MEMORY_KINDS = frozenset(
    {
        "decision_lesson",
        "user_correction",
        "user_preference",
        "volatile_fact",
        "model_judgment",
    }
)
_TERMINAL_VERDICTS = frozenset({"hit", "partial", "miss"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    kind: MemoryKind
    content: str
    checkpoint_id: str = ""
    correction_ts: str = ""
    is_volatile: bool = False

    def __post_init__(self) -> None:
        candidate_id = str(self.candidate_id or "").strip()
        content = str(self.content or "").strip()
        if not candidate_id:
            raise ValueError("memory candidate_id must be non-empty")
        if self.kind not in _MEMORY_KINDS:
            raise ValueError("unsupported memory candidate kind")
        if not content:
            raise ValueError("memory candidate content must be non-empty")
        if not isinstance(self.is_volatile, bool):
            raise ValueError("memory candidate is_volatile must be boolean")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "checkpoint_id", str(self.checkpoint_id or "").strip())
        object.__setattr__(self, "correction_ts", str(self.correction_ts or "").strip())


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    eligible: bool
    target_layer: TargetLayer
    reason: str
    content_sha256: str
    provenance: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.reason.strip():
            raise ValueError("promotion decision identity/reason must be non-empty")
        if self.target_layer not in {"durable_experience", "none"}:
            raise ValueError("unsupported promotion target layer")
        if self.eligible != (self.target_layer == "durable_experience"):
            raise ValueError("promotion eligibility and target layer disagree")
        if not _SHA256_RE.fullmatch(self.content_sha256):
            raise ValueError("promotion decision requires a content SHA-256")

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "eligible": self.eligible,
            "target_layer": self.target_layer,
            "reason": self.reason,
            "content_sha256": self.content_sha256,
            "provenance": dict(self.provenance),
        }


def _rejected(candidate: MemoryCandidate, reason: str) -> PromotionDecision:
    return PromotionDecision(
        candidate.candidate_id,
        False,
        "none",
        reason,
        _content_sha256(candidate.content),
    )


def _approved(
    candidate: MemoryCandidate,
    reason: str,
    provenance: tuple[tuple[str, str], ...],
) -> PromotionDecision:
    return PromotionDecision(
        candidate.candidate_id,
        True,
        "durable_experience",
        reason,
        _content_sha256(candidate.content),
        provenance,
    )


def promotion_metadata(
    decision: PromotionDecision,
    content: str,
) -> dict[str, object]:
    """Validate one approved decision against the exact content being written."""

    if not isinstance(decision, PromotionDecision):
        raise TypeError("decision must be PromotionDecision")
    normalized = str(content or "").strip()
    if not normalized:
        raise ValueError("promoted content must be non-empty")
    if not decision.eligible or decision.target_layer != "durable_experience":
        raise ValueError("promotion decision is not eligible")
    if _content_sha256(normalized) != decision.content_sha256:
        raise ValueError("promotion decision does not bind this content")
    return {
        "candidate_id": decision.candidate_id,
        "reason": decision.reason,
        "content_sha256": decision.content_sha256,
        "provenance": dict(decision.provenance),
    }


class MemoryGate:
    """Decide eligibility; file writers remain separate adapters."""

    def decide(
        self,
        candidate: MemoryCandidate,
        *,
        checkpoints: Sequence[Mapping[str, object]],
        verdicts: Sequence[Mapping[str, object]],
        corrections: Sequence[Mapping[str, object]],
    ) -> PromotionDecision:
        if not isinstance(candidate, MemoryCandidate):
            raise TypeError("candidate must be MemoryCandidate")
        if candidate.is_volatile or candidate.kind == "volatile_fact":
            return _rejected(candidate, "volatile_content_forbidden")
        if candidate.kind == "model_judgment":
            return _rejected(candidate, "unreviewed_model_judgment")
        if candidate.kind == "decision_lesson":
            return self._checkpoint_decision(candidate, checkpoints, verdicts)
        return self._correction_decision(candidate, corrections)

    @staticmethod
    def _checkpoint_decision(
        candidate: MemoryCandidate,
        checkpoints: Sequence[Mapping[str, object]],
        verdicts: Sequence[Mapping[str, object]],
    ) -> PromotionDecision:
        checkpoint_id = candidate.checkpoint_id
        if not checkpoint_id:
            return _rejected(candidate, "checkpoint_provenance_required")
        checkpoint_exists = any(
            str(item.get("id") or "").strip() == checkpoint_id
            for item in checkpoints
            if isinstance(item, Mapping)
        )
        if not checkpoint_exists:
            return _rejected(candidate, "checkpoint_not_found")
        latest_terminal = ""
        for item in verdicts:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("id") or "").strip() != checkpoint_id:
                continue
            verdict = str(item.get("verdict") or "").strip()
            if verdict in _TERMINAL_VERDICTS:
                latest_terminal = verdict
        if not latest_terminal:
            return _rejected(candidate, "terminal_verdict_required")
        return _approved(
            candidate,
            "reviewed_checkpoint_lesson",
            (
                ("checkpoint_id", checkpoint_id),
                ("verdict", latest_terminal),
            ),
        )

    @staticmethod
    def _correction_decision(
        candidate: MemoryCandidate,
        corrections: Sequence[Mapping[str, object]],
    ) -> PromotionDecision:
        if not candidate.correction_ts:
            return _rejected(candidate, "correction_provenance_required")
        matches = []
        for item in corrections:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("ts") or "").strip() != candidate.correction_ts:
                continue
            eligible_texts = {
                str(item.get("correction") or "").strip(),
                str(item.get("principle") or "").strip(),
            }
            if candidate.content in eligible_texts:
                matches.append(item)
        if len(matches) != 1:
            return _rejected(candidate, "correction_provenance_mismatch")
        return _approved(
            candidate,
            "explicit_user_correction",
            (
                ("correction_ts", candidate.correction_ts),
                ("record_type", candidate.kind),
            ),
        )


__all__ = [
    "MemoryCandidate",
    "MemoryGate",
    "MemoryKind",
    "PromotionDecision",
    "TargetLayer",
    "promotion_metadata",
]
