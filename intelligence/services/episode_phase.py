"""Audit projection of Episode phase transitions.

This is a sidecar, not a second event log. Durable kinds stay in
``episode_event_lanes``; public UX copy stays in ``episode_progress``;
run/report status stays in ``status_projection``.  Phase traces reconstruct
``from → to`` for operators and tests without changing control flow.

Fail policy matches ``episode_projection`` at the artifact boundary: illegal
or post-terminal moves are kept in ``anomalies`` instead of aborting a
finished research turn.  The recorder itself must not raise into the loop.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from intelligence.services.agent_runtime import EpisodeEvent


EpisodePhase = Literal[
    "planning",
    "research",
    "finalizing",
    "structural_verify",
    "semantic_verify",
    "repair",
    "completed",
    "partial",
    "degraded",
    "failed",
    "cancelled",
]

PROCESS_PHASES: frozenset[str] = frozenset(
    {
        "planning",
        "research",
        "finalizing",
        "structural_verify",
        "semantic_verify",
        "repair",
    }
)
TERMINAL_PHASES: frozenset[str] = frozenset(
    {
        "completed",
        "partial",
        "degraded",
        "failed",
        "cancelled",
    }
)
EPISODE_PHASES: frozenset[str] = PROCESS_PHASES | TERMINAL_PHASES

# Durable event kinds that mark a process phase. ``finish`` stays in
# finalizing: resume appends another finish onto the same ledger, so a finish
# event is not the public terminal (see P0 C3).
_KIND_PHASE: Mapping[str, str] = {
    "task": "planning",
    "configure": "planning",
    "plan": "planning",
    "mode_decision": "planning",
    "model_turn": "research",
    "model_error": "research",
    "tool_request": "research",
    "tool_result": "research",
    "tool_error": "research",
    "tool_closed": "research",
    "branch_started": "research",
    "branch_completed": "research",
    "branch_failed": "research",
    "branch_tool": "research",
    "invalid_action": "research",
    "repair_goal": "repair",
    "repair_reentry": "repair",
    "repair_model_retry": "repair",
    "finalization": "finalizing",
    "finalization_recovery_started": "finalizing",
    "finalization_recovery_outcome": "finalizing",
    "finish": "finalizing",
}


def _allowed_pairs() -> frozenset[tuple[str, str]]:
    pairs: set[tuple[str, str]] = {
        ("planning", "research"),
        ("planning", "finalizing"),
        ("planning", "structural_verify"),
        ("research", "finalizing"),
        ("research", "repair"),
        ("research", "structural_verify"),
        ("finalizing", "structural_verify"),
        ("finalizing", "repair"),
        ("structural_verify", "semantic_verify"),
        ("structural_verify", "repair"),
        ("semantic_verify", "repair"),
        ("repair", "structural_verify"),
        ("repair", "semantic_verify"),
        ("repair", "research"),
        ("repair", "finalizing"),
    }
    for source in PROCESS_PHASES:
        for terminal in TERMINAL_PHASES:
            pairs.add((source, terminal))
    return frozenset(pairs)


ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = _allowed_pairs()


@dataclass(frozen=True)
class PhaseHints:
    """Adapter-only facts that durable events cannot reconstruct."""

    structural_verify: bool = False
    semantic_verify: bool = False
    public_status: str | None = None
    reason_code: str = ""
    remaining_calls: int | None = None
    remaining_seconds: float | None = None
    evidence_count: int | None = None
    repair_attempts: int = 0

    def snapshot(self) -> dict[str, object]:
        return {
            "remaining_calls": self.remaining_calls,
            "remaining_seconds": self.remaining_seconds,
            "evidence_count": self.evidence_count,
            "repair_attempts": self.repair_attempts,
        }


@dataclass(frozen=True)
class PhaseTransition:
    from_phase: str | None
    trigger: str
    to_phase: str
    reason_code: str
    remaining_calls: int | None = None
    remaining_seconds: float | None = None
    evidence_count: int | None = None
    repair_attempts: int | None = None
    terminal_claimed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "from_phase": self.from_phase,
            "trigger": self.trigger,
            "to_phase": self.to_phase,
            "reason_code": self.reason_code,
            "remaining_calls": self.remaining_calls,
            "remaining_seconds": self.remaining_seconds,
            "evidence_count": self.evidence_count,
            "repair_attempts": self.repair_attempts,
            "terminal_claimed": self.terminal_claimed,
        }


@dataclass(frozen=True)
class PhaseTrace:
    transitions: tuple[PhaseTransition, ...] = ()
    illegal_transitions: tuple[str, ...] = ()
    post_terminal_triggers: tuple[str, ...] = ()

    @property
    def terminal_phases(self) -> tuple[str, ...]:
        return tuple(
            item.to_phase
            for item in self.transitions
            if item.to_phase in TERMINAL_PHASES
        )

    @property
    def has_anomalies(self) -> bool:
        return bool(self.illegal_transitions or self.post_terminal_triggers)

    def anomalies_to_dict(self) -> dict[str, list[str]]:
        payload: dict[str, list[str]] = {}
        if self.illegal_transitions:
            payload["illegal_transitions"] = list(self.illegal_transitions)
        if self.post_terminal_triggers:
            payload["post_terminal_triggers"] = list(self.post_terminal_triggers)
        return payload

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "transitions": [item.to_dict() for item in self.transitions],
            "terminal_phases": list(self.terminal_phases),
        }
        anomalies = self.anomalies_to_dict()
        if anomalies:
            payload["anomalies"] = anomalies
        return payload


class PhaseRecorder:
    """Append-only phase seam. Illegal moves are flagged, not thrown."""

    def __init__(self) -> None:
        self._phase: str | None = None
        self._seen_seq = 0
        self._terminal = False
        self._transitions: list[PhaseTransition] = []
        self._illegal: list[str] = []
        self._post_terminal: list[str] = []

    @property
    def current_phase(self) -> str | None:
        return self._phase

    def ingest_events(
        self,
        events: Iterable[EpisodeEvent],
        *,
        remaining_calls: int | None = None,
        remaining_seconds: float | None = None,
        evidence_count: int | None = None,
        repair_attempts: int | None = None,
    ) -> None:
        for event in events:
            if event.sequence <= self._seen_seq:
                continue
            self._seen_seq = event.sequence
            to_phase = _KIND_PHASE.get(event.kind)
            if to_phase is None:
                continue
            self.record(
                to_phase,
                trigger=event.kind,
                reason_code=str(event.payload.get("stop_reason") or event.kind),
                remaining_calls=remaining_calls,
                remaining_seconds=remaining_seconds,
                evidence_count=evidence_count,
                repair_attempts=repair_attempts,
            )

    def record(
        self,
        to_phase: str,
        *,
        trigger: str,
        reason_code: str,
        remaining_calls: int | None = None,
        remaining_seconds: float | None = None,
        evidence_count: int | None = None,
        repair_attempts: int | None = None,
        terminal_claimed: bool = False,
    ) -> None:
        destination = str(to_phase or "").strip()
        if destination not in EPISODE_PHASES:
            self._illegal.append(f"{self._phase} -> {destination} ({trigger})")
            return
        if self._terminal:
            self._post_terminal.append(str(trigger or destination))
            return
        if self._phase == destination:
            return
        if (
            self._phase is not None
            and (self._phase, destination) not in ALLOWED_TRANSITIONS
        ):
            self._illegal.append(f"{self._phase} -> {destination} ({trigger})")
        claimed = bool(terminal_claimed) or destination in TERMINAL_PHASES
        self._transitions.append(
            PhaseTransition(
                from_phase=self._phase,
                trigger=str(trigger or destination),
                to_phase=destination,
                reason_code=str(reason_code or destination),
                remaining_calls=remaining_calls,
                remaining_seconds=remaining_seconds,
                evidence_count=evidence_count,
                repair_attempts=repair_attempts,
                terminal_claimed=claimed,
            )
        )
        self._phase = destination
        if destination in TERMINAL_PHASES:
            self._terminal = True

    def trace(self) -> PhaseTrace:
        return PhaseTrace(
            transitions=tuple(self._transitions),
            illegal_transitions=tuple(self._illegal),
            post_terminal_triggers=tuple(self._post_terminal),
        )


def project_phase_transitions(
    events: Iterable[EpisodeEvent],
    *,
    hints: PhaseHints | None = None,
) -> PhaseTrace:
    """Rebuild a phase sequence from durable events plus adapter hints.

    Verify/repair interleaving that happens *between* events cannot be
    recovered here; use :class:`PhaseRecorder` at the adapter seams.
    """

    notes = hints or PhaseHints()
    recorder = PhaseRecorder()
    snap = notes.snapshot()
    recorder.ingest_events(events, **snap)
    if notes.structural_verify:
        recorder.record(
            "structural_verify",
            trigger="structural_verifier",
            reason_code="structural_verify",
            **snap,
        )
    if notes.semantic_verify:
        recorder.record(
            "semantic_verify",
            trigger="semantic_verifier",
            reason_code="semantic_verify",
            **snap,
        )
    status = str(notes.public_status or "").strip()
    if status:
        recorder.record(
            status,
            trigger="public_outcome",
            reason_code=str(notes.reason_code or status),
            terminal_claimed=True,
            **snap,
        )
    return recorder.trace()


__all__ = [
    "ALLOWED_TRANSITIONS",
    "EPISODE_PHASES",
    "EpisodePhase",
    "PROCESS_PHASES",
    "PhaseHints",
    "PhaseRecorder",
    "PhaseTrace",
    "PhaseTransition",
    "TERMINAL_PHASES",
    "project_phase_transitions",
]
