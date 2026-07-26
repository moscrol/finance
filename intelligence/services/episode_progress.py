"""Project private Episode events into replayable user-facing progress.

The Episode ledger contains model messages, queries, tool identities, hashes,
and provider diagnostics.  None of those values may cross the public Run/SSE
seam.  This module is the single projection and persistence owner for live
continuous-runtime progress.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import re
from threading import RLock

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.run_store import RunStore


_PROGRESS_STATUSES = frozenset({"running", "completed", "failed"})
_PROGRESS_STAGES = frozenset(
    {"understanding", "planning", "research", "repair", "verification", "finalizing"}
)
_SAFE_KEY = re.compile(r"^[a-z][a-z0-9_-]*(?::[a-z0-9_-]+)*$")


@dataclass(frozen=True)
class EpisodeProgress:
    """One public milestone with no model- or provider-controlled prose."""

    key: str
    stage: str
    message: str
    status: str

    def __post_init__(self) -> None:
        key = str(self.key or "").strip().lower()
        stage = str(self.stage or "").strip().lower()
        message = str(self.message or "").strip()
        status = str(self.status or "").strip().lower()
        if not _SAFE_KEY.fullmatch(key):
            raise ValueError("progress key must be a safe non-empty identity")
        if stage not in _PROGRESS_STAGES:
            raise ValueError("unsupported progress stage")
        if not message:
            raise ValueError("progress message must be non-empty")
        if status not in _PROGRESS_STATUSES:
            raise ValueError("unsupported progress status")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "status", status)

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "stage": self.stage,
            "message": self.message,
            "status": self.status,
        }


_EVENT_PROJECTIONS: dict[str, tuple[str, str, str]] = {
    "plan": ("planning", "已形成研究计划。", "completed"),
    "mode_decision": ("planning", "已按任务复杂度确认研究深度。", "completed"),
    "tool_request": ("research", "正在核对计划所需资料。", "running"),
    "tool_result": ("research", "已取得一批可核验资料。", "completed"),
    "tool_error": ("research", "一项资料未取得，正在调整研究路径。", "completed"),
    "branch_started": ("research", "已启动并行的只读补充研究。", "running"),
    "branch_completed": ("research", "一项补充研究已返回证据。", "completed"),
    "branch_failed": ("research", "一项补充研究未取得结果，主研究继续。", "completed"),
    "repair_goal": ("repair", "核验发现关键缺口，正在定向补证。", "running"),
    "finalization": ("finalizing", "证据收集完成，正在组织回答。", "running"),
    "finalization_recovery_started": (
        "finalizing",
        "正在基于已取得证据恢复最终回答。",
        "running",
    ),
    "finish": ("finalizing", "研究回答已形成，正在完成最终核验。", "completed"),
}


def project_episode_progress(event: EpisodeEvent) -> EpisodeProgress | None:
    """Return a fixed public projection, ignoring every event payload value."""

    projection = _EVENT_PROJECTIONS.get(event.kind)
    if projection is None:
        return None
    stage, message, status = projection
    return EpisodeProgress(
        key=f"episode:{event.sequence}:{event.kind}",
        stage=stage,
        message=message,
        status=status,
    )


class RunEpisodeProgressPublisher:
    """Persist one progress event to both trace and replayable SSE exactly once."""

    def __init__(
        self,
        *,
        run_store: RunStore,
        run_id: str,
        conversation_id: str,
        message_id: str,
        is_cancelled: Callable[[], bool] | None = None,
        event_id_prefix: str = "",
    ) -> None:
        if not isinstance(run_store, RunStore):
            raise TypeError("run_store must be a RunStore")
        self._run_store = run_store
        self._run_id = str(run_id or "").strip()
        self._conversation_id = str(conversation_id or "").strip()
        self._message_id = str(message_id or "").strip()
        self._is_cancelled = is_cancelled or (lambda: False)
        self._event_id_prefix = str(event_id_prefix or "")
        if not self._run_id or not self._conversation_id or not self._message_id:
            raise ValueError("progress publisher identities must be non-empty")
        self._published: set[str] = set()
        self._lock = RLock()

    def publish(self, progress: EpisodeProgress) -> None:
        if not isinstance(progress, EpisodeProgress):
            raise TypeError("progress must be EpisodeProgress")
        with self._lock:
            if self._is_cancelled() or progress.key in self._published:
                return
            prefixed_key = f"{self._event_id_prefix}{progress.key}"
            finished_at = (
                datetime.now().astimezone().isoformat()
                if progress.status != "running"
                else None
            )
            step = self._run_store.append_step(
                self._run_id,
                step_id=f"continuous:{prefixed_key}",
                name=progress.stage,
                status=progress.status,
                output_summary=progress.message,
                finished_at=finished_at,
            )
            self._run_store.append_stream_event(
                self._run_id,
                event_id=(
                    f"{self._event_id_prefix}continuous:progress:{progress.key}"
                ),
                event_type="trace.step",
                payload={"step": step},
                conversation_id=self._conversation_id,
                message_id=self._message_id,
            )
            self._published.add(progress.key)


__all__ = [
    "EpisodeProgress",
    "RunEpisodeProgressPublisher",
    "project_episode_progress",
]
