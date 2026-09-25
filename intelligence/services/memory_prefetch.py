"""Bounded, read-only opening recall; late results never reach the episode."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import replace
from threading import BoundedSemaphore, Event
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from intelligence.services.agent_research import AgentEvidence, AgentToolContext
    from intelligence.services.research_contract import ResearchRunContext
    from intelligence.services.research_tool_registry import ToolRunResult

MEMORY_PREFETCH_SECONDS = 1.0
# No queue of private reads: stuck IO can occupy at most these two workers.
_SLOTS = BoundedSemaphore(2)
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="memory-prefetch")


def _gap(reason: str) -> tuple[AgentEvidence, ...]:
    from intelligence.services.agent_research import AgentEvidence, evidence_content_hash

    messages = {
        "empty": "用户记忆无相关命中；不得编造用户此前的看法。",
        "timeout": "用户记忆预取超时，尚未确认是否有相关记录。",
        "unavailable": "用户记忆读取失败，尚未确认是否有相关记录。",
        "busy": "用户记忆预取繁忙，本轮未读取。",
    }
    item = AgentEvidence(
        tool="memory_lookup",
        title="用户记忆缺口",
        detail=f"status={reason} {messages[reason]}",
        source="用户记忆预取状态（缺口，非用户判断、非市场事实）",
        evidence_tier="user_memory_gap",
        io_effect="local_read",
    )
    return (replace(item, content_hash=evidence_content_hash(item)),)


def collect_opening_memory(
    runner: Callable[[str, AgentToolContext], ToolRunResult],
    *,
    query: str,
    context: ResearchRunContext,
) -> tuple[AgentEvidence, ...]:
    """Use the same runner as the tool, without taking a model tool slot.

    The child deadline intersects the root research window. Threads cannot be
    killed during filesystem IO; admission is bounded and timed-out results
    remain private to the worker, never published to a later turn.
    """
    from intelligence.services.agent_research import AgentToolContext, evidence_content_hash

    deadline = context.deadline.bounded_stage(MEMORY_PREFETCH_SECONDS)
    if deadline.expired:
        return _gap("timeout")
    if not _SLOTS.acquire(blocking=False):
        return _gap("busy")
    cancelled = Event()
    tool_context = AgentToolContext(
        deadline=deadline,
        is_cancelled=lambda: cancelled.is_set() or deadline.expired,
        information_cutoff=context.information_cutoff,
    )
    try:
        future = _POOL.submit(runner, query, tool_context)
    except Exception:
        _SLOTS.release()
        return _gap("unavailable")
    future.add_done_callback(lambda _future: _SLOTS.release())
    try:
        result = future.result(timeout=deadline.remaining())
        if deadline.expired:
            return _gap("timeout")
        if not result.evidence:
            return _gap("empty" if result.trace.status == "empty" else "unavailable")
        return tuple(
            replace(item, content_hash=evidence_content_hash(item), io_effect="local_read")
            for item in result.evidence
        )
    except FutureTimeout:
        return _gap("timeout")
    except Exception:
        return _gap("timeout" if deadline.expired else "unavailable")
    finally:
        cancelled.set()
        future.cancel()
