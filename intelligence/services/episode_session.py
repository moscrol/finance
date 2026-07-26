"""Provider-neutral continuation seam for one research Episode."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from intelligence.services.agent_runtime import AgentOutcome
from intelligence.services.repair_coordinator import RepairGoal


@runtime_checkable
class EpisodeSession(Protocol):
    """One immutable episode identity with same-history continuation."""

    episode_id: str
    outcome: AgentOutcome

    def resume(self, goal: RepairGoal) -> AgentOutcome: ...


class EpisodeSessionError(RuntimeError):
    """Raised when a continuation would violate the episode contract."""


class CallbackEpisodeSession:
    """Small adapter used by provider runtimes and deterministic tests.

    The callback receives the existing outcome and goal. It is intentionally
    not given a runtime object, so it cannot silently call ``run()`` again.
    Production adapters should close over their live provider history and
    tool/usage ledgers instead.
    """

    def __init__(
        self,
        *,
        episode_id: str,
        outcome: AgentOutcome,
        resume_callback: Callable[[AgentOutcome, RepairGoal], AgentOutcome],
    ) -> None:
        self.episode_id = str(episode_id or "").strip()
        if not self.episode_id:
            raise ValueError("episode_id must be non-empty")
        if not isinstance(outcome, AgentOutcome):
            raise TypeError("outcome must be AgentOutcome")
        if not callable(resume_callback):
            raise TypeError("resume_callback must be callable")
        self.outcome = outcome
        self._resume_callback = resume_callback
        self._closed = False
        self.resume_count = 0

    def resume(self, goal: RepairGoal) -> AgentOutcome:
        if self._closed:
            raise EpisodeSessionError("episode session is already closed")
        if not isinstance(goal, RepairGoal):
            raise TypeError("resume requires RepairGoal")
        if goal.episode_id != self.episode_id:
            raise EpisodeSessionError("repair goal episode identity mismatch")
        previous = self.outcome
        updated = self._resume_callback(previous, goal)
        if not isinstance(updated, AgentOutcome):
            raise TypeError("resume callback must return AgentOutcome")
        if updated.task_frame_hash != previous.task_frame_hash:
            raise EpisodeSessionError("resume changed task frame identity")
        if len(updated.events) < len(previous.events):
            raise EpisodeSessionError("resume discarded episode events")
        if tuple(updated.events[: len(previous.events)]) != previous.events:
            raise EpisodeSessionError("resume rewrote episode history")
        new_events = updated.events[len(previous.events) :]
        if not any(event.kind == "model_turn" for event in new_events):
            raise EpisodeSessionError("resume did not produce a new model action")
        self.outcome = updated
        self.resume_count += 1
        return updated

    def close(self) -> None:
        self._closed = True


__all__ = ["CallbackEpisodeSession", "EpisodeSession", "EpisodeSessionError"]
