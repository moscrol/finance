"""Provider-neutral continuation seam for one research Episode."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from intelligence.services.agent_runtime import AgentOutcome
from intelligence.services.evidence_ledger import EvidenceLedger, EvidenceLedgerSnapshot
from intelligence.services.repair_coordinator import RepairGoal
from intelligence.services.runtime_handle import (
    RuntimeHandle,
    RuntimeHandleCancelled,
    RuntimeHandleClosed,
)


@runtime_checkable
class EpisodeSession(Protocol):
    """One immutable episode identity with same-history continuation."""

    episode_id: str
    outcome: AgentOutcome
    evidence_ledger: EvidenceLedger
    initial_evidence_snapshot: EvidenceLedgerSnapshot

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
        evidence_ledger: EvidenceLedger | None = None,
        initial_evidence_snapshot: EvidenceLedgerSnapshot | None = None,
        runtime_handle: RuntimeHandle | None = None,
    ) -> None:
        self.episode_id = str(episode_id or "").strip()
        if not self.episode_id:
            raise ValueError("episode_id must be non-empty")
        if not isinstance(outcome, AgentOutcome):
            raise TypeError("outcome must be AgentOutcome")
        if not callable(resume_callback):
            raise TypeError("resume_callback must be callable")
        if runtime_handle is not None and runtime_handle.episode_id != self.episode_id:
            # 生命周期收据挂错 Episode 比没有收据更糟：查案会查到别人头上。
            raise ValueError("runtime handle episode identity mismatch")
        self.outcome = outcome
        self.evidence_ledger = evidence_ledger or EvidenceLedger()
        self.initial_evidence_snapshot = (
            initial_evidence_snapshot or self.evidence_ledger.snapshot()
        )
        self._resume_callback = resume_callback
        self._closed = False
        self.resume_count = 0
        # 公开只读约定：调用方（adapter、测试、事后分诊）经它取生命周期收据。
        # 缺省 None 时本类行为与接线前逐字节一致。
        self.runtime_handle = runtime_handle

    def resume(self, goal: RepairGoal) -> AgentOutcome:
        if self._closed:
            raise EpisodeSessionError("episode session is already closed")
        if self.runtime_handle is None:
            return self._resume_validated(goal)
        # resume 是**未派发的新工作**：cancel/close 之后必须被这道门挡住
        # （spec §7.3「cancel 只阻止尚未派发的工作」「close 后不得发布新
        # Agent/Tool/Event」）。映射回 EpisodeSessionError 是因为这是本类
        # 对外的既有失败词表，调用方不该为接了 Handle 就多学一种异常。
        try:
            self.runtime_handle.begin_work("session_resume")
        except (RuntimeHandleClosed, RuntimeHandleCancelled) as exc:
            raise EpisodeSessionError(str(exc)) from exc
        try:
            return self._resume_validated(goal)
        finally:
            self.runtime_handle.end_work("session_resume")

    def _resume_validated(self, goal: RepairGoal) -> AgentOutcome:
        """五条 resume 不变量的唯一拥有点（episode 身份、task frame hash、
        事件不丢、前缀不改写、必须产生新 model_turn）。RuntimeHandle 不复述
        这些，它只管生命周期门。"""

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
        if self.runtime_handle is not None:
            # 关闭理由取最后一次落账的 outcome 终态：四类验收场景（取消/超时/
            # Provider 失败/正常完成）在收据上的判别子就是它。
            self.runtime_handle.close(
                reason=(
                    "session_closed:"
                    + (self.outcome.stop_reason or self.outcome.status or "unknown")
                )
            )


__all__ = ["CallbackEpisodeSession", "EpisodeSession", "EpisodeSessionError"]
