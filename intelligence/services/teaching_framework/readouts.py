"""Teaching-framework readouts built on the shared statistics gate."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping, Sequence

from intelligence.services.methodology_backtest.stats import Readout, StageBucket, readout, stage_readouts

from .leader_succession import TopResult, join_group


def _as_mapping(node: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(node, Mapping):
        return node
    as_dict = getattr(node, "as_dict", None)
    if callable(as_dict):
        return as_dict()
    raise TypeError(f"unsupported succession node: {type(node).__name__}")


def eligible_baseline(
    result: Mapping[str, Any],
    calendar_dates: Iterable[str],
    *,
    context_by_date: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build the same matured, covered risk set used by succession events.

    A day without a prior leader group, with a source gap, or without a realized
    next leader group is excluded rather than treated as a failed handoff.  Tied
    leaders form one group (创始人：最高标不要求唯一).  Each row keeps the prior
    group and the anchor-day stage so the receipt can report tenure overlap and
    bucket by stage.
    """

    coverage = result["coverage"]
    tops: Mapping[str, TopResult] = result["tops"]
    dates = sorted(str(d)[:10] for d in calendar_dates)
    out: list[dict[str, Any]] = []
    for i in range(1, len(dates) - 1):
        day, prev_day, next_day = dates[i], dates[i - 1], dates[i + 1]
        if any(not coverage[d].is_complete for d in (prev_day, day, next_day)):
            continue
        prior = tops.get(prev_day)
        current = tops.get(day)
        if not prior or prior.status != "ok" or not current or current.status in {"field_null", "data_gap"}:
            continue
        prior_group = set(prior.stocks)
        # Non-break baseline dates keep at least one prior leader sealed and exclude
        # an overtaken group; otherwise they are a different event shape from a
        # low-level continuation.
        current_rows = {str(row.get("stock_ts_code")): row for row in coverage[day].rows}
        if not any(stock in current_rows for stock in prior_group):
            continue
        if current.status == "ok" and not set(current.stocks) & prior_group:
            continue
        candidates = {
            str(row.get("stock_ts_code"))
            for candidate_day in (prev_day, day, next_day)
            for row in coverage[candidate_day].rows
            if row.get("limit_times") is not None and float(row["limit_times"]) <= 2
            and str(row.get("stock_ts_code")) not in prior_group
        }
        successor: TopResult | None = None
        for future_day in dates[i:]:
            top = tops.get(future_day)
            if top is None or top.status in {"data_gap", "field_null"}:
                successor = None
                break
            if top.status == "ok" and not set(top.stocks) & prior_group:
                successor = top
                break
        if successor is None:
            continue
        stage = (context_by_date or {}).get(day, {}).get("stage_coarse")
        out.append(
            {
                "date": day,
                "index": i,
                "prior": join_group(prior_group),
                "stage": None if stage is None else str(stage),
                "handoff": bool(set(successor.stocks) & candidates),
                "successor": join_group(successor.stocks),
                "successor_birth_day": successor.trade_date,
                "successor_boards": successor.boards,
            }
        )
    return out


def _ok_nodes(nodes: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        (
            item
            for item in (_as_mapping(n) for n in nodes)
            if item.get("status") == "ok" and item.get("handoff") is not None
        ),
        key=lambda n: str(n.get("break_day")),
    )


def handoff_readout(
    nodes: Iterable[Mapping[str, Any]],
    *,
    baseline: Sequence[bool],
    min_n: int = 10,
) -> Readout:
    """Return the shared four-state readout for matured, valid event nodes."""

    events = _ok_nodes(nodes)
    return readout(
        [bool(n["handoff"]) for n in events],
        baseline_n=len(baseline),
        baseline_k=sum(bool(x) for x in baseline),
        min_n=min_n,
    )


def _stage_key(value: Any) -> str:
    return "gap" if value is None else str(value)


def baseline_by_stage(baseline_rows: Iterable[Mapping[str, Any]]) -> dict[str, list[bool]]:
    """Group baseline outcomes by anchor-day stage; ``None`` stage becomes ``gap``."""
    grouped: dict[str, list[bool]] = defaultdict(list)
    for row in baseline_rows:
        grouped[_stage_key(row.get("stage"))].append(bool(row["handoff"]))
    return dict(grouped)


def stage_handoff_readouts(
    nodes: Iterable[Mapping[str, Any]],
    baseline_by_stage: Mapping[str, Sequence[bool]],
    *,
    min_n: int = 10,
    q: float = 0.05,
) -> list[StageBucket]:
    """Group event nodes by break-stage and reuse the shared BH gate.

    ``ambiguous`` / ``no_evidence`` / missing stages are buckets of their own;
    nothing is folded into a neighbouring stage.
    """

    by_stage: dict[str, list[bool]] = defaultdict(list)
    for node in _ok_nodes(nodes):
        stage = _stage_key((node.get("context_break") or {}).get("stage_coarse"))
        by_stage[stage].append(bool(node["handoff"]))
    baselines = {
        stage: (len(values), sum(bool(v) for v in values))
        for stage, values in baseline_by_stage.items()
    }
    for stage in by_stage:
        baselines.setdefault(stage, (0, 0))
    return stage_readouts(by_stage, baselines, min_n=min_n, q=q)


def receipt_summary(
    nodes: Iterable[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize exclusions so N and p0 cannot hide sample selection.

    ``baseline_overlapping_windows`` counts baseline days whose three-day
    candidate window overlaps the previous baseline day's window (calendar index
    distance <= 2); ``baseline_tenures`` is the number of distinct prior leaders
    behind the baseline days.  Both are reported, not corrected for.
    """

    rows = [_as_mapping(n) for n in nodes]
    indexes = sorted(int(r["index"]) for r in baseline_rows if r.get("index") is not None)
    overlaps = sum(1 for a, b in zip(indexes, indexes[1:]) if b - a <= 2)
    return {
        "nodes_total": len(rows),
        "nodes_ok": sum(n.get("status") == "ok" for n in rows),
        "nodes_open": sum(n.get("status") == "open" for n in rows),
        "nodes_unverifiable": sum(n.get("status") == "unverifiable" for n in rows),
        "nodes_unverifiable_by_reason": dict(
            sorted(Counter(str(n.get("status_reason")) for n in rows if n.get("status") == "unverifiable").items())
        ),
        "baseline_n": len(baseline_rows),
        "baseline_k": sum(bool(r["handoff"]) for r in baseline_rows),
        "baseline_tenures": len({r.get("prior") for r in baseline_rows}),
        "baseline_overlapping_windows": overlaps,
    }


def succession_diagnostics(
    result: Mapping[str, Any],
    baseline_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Cross-tabs that show *what* the handoff measure is responding to.

    The event rate and the baseline rate are only comparable if they respond to
    the same thing.  These tables let a reader check that directly: handoff by
    successor board count, by gap days, and the baseline outcome by distance to
    the next break.  They are descriptive counts, not verdicts.
    """

    nodes = [_as_mapping(n) for n in result["nodes"]]
    ok = [n for n in nodes if n.get("status") == "ok" and n.get("handoff") is not None]

    def n_k(items: Iterable[Mapping[str, Any]]) -> dict[str, int]:
        items = list(items)
        return {"n": len(items), "k": sum(bool(x["handoff"]) for x in items)}

    by_birth_boards = {
        str(boards): n_k(n for n in ok if n.get("birth_boards") == boards)
        for boards in sorted({n.get("birth_boards") for n in ok}, key=lambda b: (b is None, b))
    }
    by_gap_days = {
        str(gap): n_k(n for n in ok if n.get("gap_days") == gap)
        for gap in sorted({n.get("gap_days") for n in ok}, key=lambda g: (g is None, g))
    }
    break_days = sorted(str(n.get("break_day")) for n in nodes if n.get("break_day"))
    dates = sorted(result["tops"])
    index_of = {d: i for i, d in enumerate(dates)}
    break_index = sorted(index_of[d] for d in break_days if d in index_of)
    by_distance: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in baseline_rows:
        i = int(row["index"])
        nxt = next((b for b in break_index if b > i), None)
        by_distance["no_break_after" if nxt is None else str(nxt - i)].append(row)
    baseline_by_distance = {
        key: n_k(items)
        for key, items in sorted(
            by_distance.items(),
            key=lambda kv: (not kv[0].isdigit(), int(kv[0]) if kv[0].isdigit() else 0),
        )
    }
    top_status = Counter(t.status for t in result["tops"].values())
    # 创始人：最高标不要求唯一。How often the top is a tie, and how the handoff
    # measure reads on tied successors, are shown rather than folded away.
    tie_sizes = Counter(str(t.tie_size) for t in result["tops"].values() if t.status == "ok")
    by_next_size = {
        str(size): n_k(n for n in ok if len(n.get("leader_next_group") or ()) == size)
        for size in sorted({len(n.get("leader_next_group") or ()) for n in ok})
    }
    partial_breaks = result.get("partial_breaks") or []
    return {
        "event_handoff_by_birth_boards": by_birth_boards,
        "event_handoff_by_gap_days": by_gap_days,
        "event_handoff_by_leader_next_size": by_next_size,
        "baseline_handoff_by_distance_to_next_break": baseline_by_distance,
        "top_status_days": dict(sorted(top_status.items())),
        "top_tie_size_days": dict(sorted(tie_sizes.items(), key=lambda kv: int(kv[0]))),
        # Days where only part of a tied leader group broke; not breaks under the
        # founder's definition, listed so the other reading can be sized.
        "partial_break_days": len(partial_breaks),
        "partial_breaks": [{"day": p["day"], "group": p["group"], "still_sealed": p["still_sealed"]} for p in partial_breaks],
    }
