"""Public, versioned snapshots for progressively available answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AnswerPhase = Literal[
    "verified_draft",
    "validated_synthesis",
    "verified_fallback",
]

VERIFIED_DRAFT: AnswerPhase = "verified_draft"
VALIDATED_SYNTHESIS: AnswerPhase = "validated_synthesis"
VERIFIED_FALLBACK: AnswerPhase = "verified_fallback"
_TERMINAL_PHASES = frozenset({VALIDATED_SYNTHESIS, VERIFIED_FALLBACK})
_PHASES = frozenset({VERIFIED_DRAFT, *_TERMINAL_PHASES})


@dataclass(frozen=True)
class AnswerSnapshot:
    """One complete answer revision exposed through the stream contract."""

    revision: int
    phase: AnswerPhase
    text: str
    final: bool

    def __post_init__(self) -> None:
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise TypeError("revision must be an integer")
        if self.revision < 1:
            raise ValueError("revision must be at least 1")
        if self.phase not in _PHASES:
            raise ValueError("phase is not supported")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if not self.text.strip():
            raise ValueError("text must not be empty")
        if not isinstance(self.final, bool):
            raise TypeError("final must be a boolean")
        if self.phase == VERIFIED_DRAFT and self.final:
            raise ValueError("final must be false for a verified draft")
        if self.phase in _TERMINAL_PHASES and not self.final:
            raise ValueError("final must be true for a terminal phase")

    def to_payload(self) -> dict[str, object]:
        """Return the exact public event payload without internal metadata."""

        return {
            "revision": self.revision,
            "phase": self.phase,
            "text": self.text,
            "final": self.final,
        }
