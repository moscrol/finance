from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AnswerPhase = Literal[
    "verified_draft",
    "validated_synthesis",
    "verified_fallback",
    "decision_brief_fallback",
    "evidence_gap_fallback",
]

ANSWER_PHASES = frozenset(
    {
        "verified_draft",
        "validated_synthesis",
        "verified_fallback",
        "decision_brief_fallback",
        "evidence_gap_fallback",
    }
)


@dataclass(frozen=True)
class AnswerSnapshot:
    revision: int
    phase: AnswerPhase
    text: str
    final: bool

    def __post_init__(self) -> None:
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ValueError("revision must be an integer")
        if self.revision < 1:
            raise ValueError("revision must be positive")
        if not isinstance(self.phase, str) or self.phase not in ANSWER_PHASES:
            raise ValueError("unknown answer phase")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("answer text must be non-empty")
        if type(self.final) is not bool:
            raise ValueError("final must be boolean")
        if self.phase == "verified_draft" and self.final:
            raise ValueError("verified draft cannot be final")
        if self.phase != "verified_draft" and not self.final:
            raise ValueError("terminal phase must be final")

    def payload(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "phase": self.phase,
            "text": self.text,
            "final": self.final,
        }
