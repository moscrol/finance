"""空观察池：Episode 内恰好一次换口径。输入加法，不改发布门。

某个 ``finance_query`` / ``sector_daily`` 池在预取空表且首轮 0 行时，
换同窗成交额前排。第二次仍空就停。与 ``plan_issue_backfill`` 互斥。
``market_watch`` 不触发。历史题继承 as-of，不得打到库尖。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from intelligence.services.episode_issues import BackfillPlan


FALLBACK_CALL_ID = "empty-pool-fallback-1"
FALLBACK_LIMIT = 8
_BACKFILL_MUTEX_CAPS = frozenset({"finance_query", "market_data"})
_AMOUNT_ORDER = ({"field": "amount", "direction": "desc"},)
_DEFAULT_DIMENSIONS = ("trade_date", "sector_name")


@dataclass(frozen=True)
class EmptyToolCall:
    name: str
    arguments: Mapping[str, object]
    empty: bool


@dataclass(frozen=True)
class FallbackProposal:
    tool: str
    original_arguments: Mapping[str, object]
    fallback_arguments: Mapping[str, object]
    as_of: str
    call_id: str = FALLBACK_CALL_ID

    def request_extras(self) -> dict[str, object]:
        return {
            "fallback_query": True,
            "original_arguments": dict(self.original_arguments),
            "as_of": self.as_of,
        }


def prefetch_pool_is_empty(items: Iterable[object]) -> bool:
    """无预取、或条目没有有效 observations，都算空表。"""

    for item in items:
        observations = getattr(item, "observations", None)
        if observations:
            return False
    return True


def fallback_already_attempted(events: Iterable[object]) -> bool:
    for event in events:
        kind = getattr(event, "kind", None)
        payload = getattr(event, "payload", None)
        if not isinstance(payload, Mapping):
            continue
        # 声明也算「已尝试」：application_tool_call 落账后、tool_request 前若崩溃，恢复时
        # 不能再对同一个 call_id 声明第二次（两条同 id 的 assistant.tool_calls 同样是非法请求）。
        if kind == "application_tool_call" and str(payload.get("call_id") or "").startswith(
            "empty-pool-fallback"
        ):
            return True
        if kind != "tool_request":
            continue
        if payload.get("fallback_query") is True:
            return True
        if str(payload.get("call_id") or "").startswith("empty-pool-fallback"):
            return True
    return False


def apply_fallback_backfill_mutex(
    plan: BackfillPlan | None,
    events: Iterable[object],
) -> BackfillPlan | None:
    """事后补枪看到桌上已经换过口径，就不要再对同一能力开第二枪。"""

    if plan is None:
        return None
    if not fallback_already_attempted(events):
        return plan
    remaining = tuple(
        cap for cap in plan.missing_capabilities if cap not in _BACKFILL_MUTEX_CAPS
    )
    if not remaining:
        return None
    return BackfillPlan(
        codes=plan.codes,
        missing_outputs=plan.missing_outputs,
        missing_capabilities=remaining,
    )


def propose_empty_pool_fallback(
    *,
    question_type: str,
    as_of: str | None,
    cutoff_source: str | None,
    prefetch_empty: bool,
    first_results: tuple[EmptyToolCall, ...],
    authorized_tools: frozenset[str],
    already_attempted: bool,
    in_repair: bool,
    backfill_plan: BackfillPlan | None,
) -> FallbackProposal | None:
    if str(question_type or "") == "market_watch":
        return None
    if already_attempted or in_repair:
        return None
    if not prefetch_empty:
        return None
    if "finance_query" not in authorized_tools:
        return None
    if backfill_plan is not None:
        missing = frozenset(backfill_plan.missing_capabilities or ())
        if missing & _BACKFILL_MUTEX_CAPS:
            return None

    sector_calls = tuple(
        call
        for call in first_results
        if call.name == "finance_query"
        and str(call.arguments.get("dataset") or "") == "sector_daily"
    )
    if not sector_calls:
        return None
    if any(not call.empty for call in sector_calls):
        return None

    original = sector_calls[0]
    resolved = _resolve_as_of(
        as_of,
        dict(original.arguments),
        cutoff_source,
    )
    if resolved is None:
        return None
    fallback_arguments = _amount_rank_arguments(dict(original.arguments), resolved)
    if _same_amount_rank(original.arguments, fallback_arguments):
        return None
    return FallbackProposal(
        tool="finance_query",
        original_arguments=dict(original.arguments),
        fallback_arguments=fallback_arguments,
        as_of=resolved,
    )


def _iso_day(value: object) -> str | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    day = text[:10]
    if day[4:5] != "-" or day[7:8] != "-":
        return None
    return day


def _resolve_as_of(
    as_of: str | None,
    original_arguments: Mapping[str, object],
    cutoff_source: str | None,
) -> str | None:
    window = original_arguments.get("time_range")
    end = None
    if isinstance(window, Mapping):
        end = _iso_day(window.get("end"))
    requested = _iso_day(as_of)
    if cutoff_source == "requested" and requested:
        resolved = requested
    elif end:
        resolved = end
    elif requested:
        resolved = requested
    else:
        return None
    if cutoff_source == "requested" and requested and resolved > requested:
        return requested
    return resolved


def _amount_rank_arguments(
    original: Mapping[str, object],
    as_of: str,
) -> dict[str, object]:
    metrics = [
        str(item)
        for item in (original.get("metrics") or ())
        if str(item).strip()
    ]
    if "amount" not in metrics:
        metrics.append("amount")
    dimensions = [
        str(item)
        for item in (original.get("dimensions") or _DEFAULT_DIMENSIONS)
        if str(item).strip()
    ] or list(_DEFAULT_DIMENSIONS)
    try:
        limit = int(original.get("limit") or FALLBACK_LIMIT)
    except (TypeError, ValueError):
        limit = FALLBACK_LIMIT
    return {
        "dataset": "sector_daily",
        "metrics": metrics,
        "dimensions": dimensions,
        "time_range": {"start": as_of, "end": as_of},
        "order_by": [dict(item) for item in _AMOUNT_ORDER],
        "limit": max(1, min(limit, FALLBACK_LIMIT)),
    }


def _is_amount_desc(order_by: object) -> bool:
    if not isinstance(order_by, (list, tuple)) or not order_by:
        return False
    first = order_by[0]
    if not isinstance(first, Mapping):
        return False
    return (
        str(first.get("field") or "") == "amount"
        and str(first.get("direction") or "").lower() == "desc"
    )


def _same_amount_rank(
    original: Mapping[str, object],
    fallback: Mapping[str, object],
) -> bool:
    if str(original.get("dataset") or "") != "sector_daily":
        return False
    if original.get("filters"):
        return False
    metrics = original.get("metrics") or ()
    if "amount" not in metrics:
        return False
    if not _is_amount_desc(original.get("order_by")):
        return False
    original_limit = original.get("limit")
    try:
        same_limit = int(original_limit) <= FALLBACK_LIMIT
    except (TypeError, ValueError):
        same_limit = False
    return same_limit and fallback["order_by"] == [
        dict(item) for item in _AMOUNT_ORDER
    ]


__all__ = [
    "FALLBACK_CALL_ID",
    "FALLBACK_LIMIT",
    "EmptyToolCall",
    "FallbackProposal",
    "apply_fallback_backfill_mutex",
    "fallback_already_attempted",
    "prefetch_pool_is_empty",
    "propose_empty_pool_fallback",
]
