"""Bounded, read-only opening recall; late results never reach the episode."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import replace
from threading import BoundedSemaphore, Event
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from intelligence.services.agent_research import AgentEvidence, AgentToolContext
    from intelligence.services.research_contract import InformationCutoff, ResearchRunContext
    from intelligence.services.research_tool_registry import ToolRunResult

MEMORY_PREFETCH_SECONDS = 1.0
# Keep private recall a compact prior alongside market evidence. These budgets
# cover title/detail observation text (including omission notices), not ledgers.
MEMORY_RECALL_MAX_CHARS = 6000
MEMORY_RECALL_ITEM_MAX_CHARS = 1000
_TRUNCATION_MARK = "…[记忆已截断；完整内容保留在原台账]"
# No queue of private reads: stuck IO can occupy at most these two workers.
_SLOTS = BoundedSemaphore(2)
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="memory-prefetch")


def _gap(reason: str, *, message: str | None = None) -> tuple[AgentEvidence, ...]:
    from intelligence.services.agent_research import AgentEvidence, evidence_content_hash

    messages = {
        "empty": "用户记忆无相关命中；不得编造用户此前的看法。",
        "future_of_cutoff": "已找到相关用户记忆，但均晚于信息截止日，未交付正文；不代表没有记录。",
        "date_unavailable": "相关用户记忆中有记录日期无法核验的条目，已省略其正文；不代表没有记录。",
        "timeout": "用户记忆预取超时，尚未确认是否有相关记录。",
        "unavailable": "用户记忆读取失败，尚未确认是否有相关记录。",
        "busy": "用户记忆预取繁忙，本轮未读取。",
    }
    item = AgentEvidence(
        tool="memory_lookup",
        title="用户记忆缺口",
        detail=f"status={reason} {message if message is not None else messages[reason]}",
        source="用户记忆召回状态（缺口，非用户判断、非市场事实）",
        evidence_tier="user_memory_gap",
        io_effect="local_read",
    )
    return (replace(item, content_hash=evidence_content_hash(item)),)


def _budget_notice(truncated: int, omitted: int) -> AgentEvidence:
    return _gap(
        "bounded",
        message=(
            f"用户记忆按{MEMORY_RECALL_MAX_CHARS}字符预算展示；"
            f"{truncated}条正文已截断，{omitted}条记录已省略；"
            "完整内容保留在原台账；仅作先验，非市场事实。"
        ),
    )[0]


def project_memory_evidence(
    evidence: tuple[AgentEvidence, ...],
    *,
    information_cutoff: InformationCutoff | None,
) -> tuple[AgentEvidence, ...]:
    """One idempotent, dated and bounded view for opening and explicit recall.

    Filter before spending the budget, then prioritize corrections over older
    judgments. Hash the delivered excerpt so the two entry points share identity.
    Gap cards are control metadata, not undated user priors.
    """
    from intelligence.services.agent_research import evidence_content_hash
    from intelligence.services.closed_loop_retrieval import filter_future_dated, parse_source_date

    gaps = [item for item in evidence if item.evidence_tier == "user_memory_gap"]
    records = [item for item in evidence if item.evidence_tier != "user_memory_gap"]
    eligible, future = filter_future_dated(
        records, information_cutoff=information_cutoff, date_getter=lambda item: item.source_date,
    )
    if information_cutoff is not None and information_cutoff.source == "requested":
        undated = [item for item in eligible if parse_source_date(item.source_date) is None]
        eligible = [item for item in eligible if parse_source_date(item.source_date) is not None]
        if undated:
            gaps.extend(_gap("date_unavailable"))
    if not eligible and not gaps and future:
        gaps.extend(_gap("future_of_cutoff"))

    eligible.sort(key=lambda item: item.title != "用户纠偏原则")
    capped = [
        replace(item, detail=item.detail[: MEMORY_RECALL_ITEM_MAX_CHARS - len(_TRUNCATION_MARK)] + _TRUNCATION_MARK)
        if len(item.detail) > MEMORY_RECALL_ITEM_MAX_CHARS else item
        for item in eligible
    ]

    def cost(item: AgentEvidence) -> int:
        return len(item.title) + len(item.detail) + 2  # colon and join separator

    needs_notice = (
        any(len(item.detail) > MEMORY_RECALL_ITEM_MAX_CHARS for item in eligible)
        or sum(cost(item) for item in (*capped, *gaps)) > MEMORY_RECALL_MAX_CHARS
    )
    remaining = MEMORY_RECALL_MAX_CHARS - sum(cost(item) for item in gaps)
    if needs_notice:
        # Reserve the longest count representation before selecting any record.
        remaining -= cost(_budget_notice(len(capped), len(capped)))
    kept = []
    truncated = omitted = 0
    for original, item in zip(eligible, capped, strict=True):
        if cost(item) > remaining:
            omitted += 1
            continue
        kept.append(item)
        remaining -= cost(item)
        truncated += item.detail != original.detail
    if truncated or omitted:
        gaps.append(_budget_notice(truncated, omitted))
    return tuple(
        replace(item, content_hash=evidence_content_hash(item), io_effect="local_read")
        for item in (*kept, *gaps)
    )


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
    from intelligence.services.agent_research import AgentToolContext

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
        return project_memory_evidence(
            result.evidence,
            information_cutoff=context.information_cutoff,
        ) or _gap("empty")
    except FutureTimeout:
        return _gap("timeout")
    except Exception:
        return _gap("timeout" if deadline.expired else "unavailable")
    finally:
        cancelled.set()
        future.cancel()
