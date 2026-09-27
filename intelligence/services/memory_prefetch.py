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
        "future_of_cutoff": "已找到相关用户记忆，但均晚于信息截止日，未交付正文；不代表没有记录。",
        "date_unavailable": "相关用户记忆的记录日期无法核验，未交付正文；不代表没有记录。",
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
        # The opening skips ResearchToolRegistry.execute, so it must apply the
        # information cutoff itself: an as-of question may not see notes the
        # user wrote after that date (the market prefetch uses the same as_of).
        from intelligence.services.closed_loop_retrieval import filter_future_dated, parse_source_date

        eligible, future_evidence = filter_future_dated(
            result.evidence,
            information_cutoff=context.information_cutoff,
            date_getter=lambda item: item.source_date,
        )
        # Legacy undated notes can still be current priors, but cannot establish
        # what was known at an explicitly requested historical cutoff.
        undated = []
        if context.information_cutoff.source == "requested":
            undated = [item for item in eligible if parse_source_date(item.source_date) is None]
            eligible = [item for item in eligible if parse_source_date(item.source_date) is not None]
        if not eligible:
            return _gap(
                "date_unavailable"
                if undated
                else "future_of_cutoff"
                if future_evidence
                else "empty"
            )
        return tuple(
            replace(item, content_hash=evidence_content_hash(item), io_effect="local_read")
            for item in eligible
        )
    except FutureTimeout:
        return _gap("timeout")
    except Exception:
        return _gap("timeout" if deadline.expired else "unavailable")
    finally:
        cancelled.set()
        future.cancel()
