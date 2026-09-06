"""Teaching-framework readouts built on the shared statistics gate."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from intelligence.services.methodology_backtest.stats import Readout, StageBucket, readout, stage_readouts

from .leader_succession import TopResult


def _as_mapping(node: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(node, Mapping):
        return node
    as_dict = getattr(node, "as_dict", None)
    if callable(as_dict):
        return as_dict()
    raise TypeError(f"unsupported succession node: {type(node).__name__}")


def eligible_baseline(result: Mapping[str, Any], calendar_dates: Iterable[str]) -> list[dict[str, Any]]:
    """Build the same matured, covered risk set used by succession events.

    A day without a unique prior leader, with a source gap/tie, or without a
    realized next leader is excluded rather than treated as a failed handoff.
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
        if not prior or prior.status != "ok" or not current or current.status in {"tie", "field_null", "data_gap"}:
            continue
        # Non-break baseline dates exclude an overtaken predecessor; otherwise
        # they are a different event shape from a low-level continuation.
        current_rows = {str(row.get("stock_ts_code")): row for row in coverage[day].rows}
        prior_row = current_rows.get(str(prior.stock_ts_code))
        if prior_row is None:
            continue
        if current.status == "ok" and current.stock_ts_code != prior.stock_ts_code:
            continue
        candidates = {
            str(row.get("stock_ts_code"))
            for candidate_day in (prev_day, day, next_day)
            for row in coverage[candidate_day].rows
            if row.get("limit_times") is not None and float(row["limit_times"]) <= 2
            and str(row.get("stock_ts_code")) != str(prior.stock_ts_code)
        }
        successor: TopResult | None = None
        for future_day in dates[i:]:
            top = tops.get(future_day)
            if top is None or top.status in {"data_gap", "tie", "field_null"}:
                successor = None
                break
            if top.status == "ok" and top.stock_ts_code != prior.stock_ts_code:
                successor = top
                break
        if successor is None:
            continue
        out.append({"date": day, "stage": None, "handoff": successor.stock_ts_code in candidates})
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


def stage_handoff_readouts(
    nodes: Iterable[Mapping[str, Any]],
    baseline_by_stage: Mapping[str, Sequence[bool]],
    *,
    min_n: int = 10,
    q: float = 0.05,
) -> list[StageBucket]:
    """Group event nodes by break-stage and reuse the shared BH gate."""

    by_stage: dict[str, list[bool]] = defaultdict(list)
    for node in _ok_nodes(nodes):
        stage = str((node.get("context_break") or {}).get("stage_coarse") or "gap")
        by_stage[stage].append(bool(node["handoff"]))
    baselines = {
        stage: (len(values), sum(bool(v) for v in values))
        for stage, values in baseline_by_stage.items()
    }
    for stage in by_stage:
        baselines.setdefault(stage, (0, 0))
    return stage_readouts(by_stage, baselines, min_n=min_n, q=q)


def receipt_summary(nodes: Iterable[Mapping[str, Any]], baseline: Sequence[bool]) -> dict[str, Any]:
    """Summarize exclusions so N and p0 cannot hide sample selection."""

    rows = [_as_mapping(n) for n in nodes]
    return {
        "nodes_total": len(rows),
        "nodes_ok": sum(n.get("status") == "ok" for n in rows),
        "nodes_open": sum(n.get("status") == "open" for n in rows),
        "nodes_unverifiable": sum(n.get("status") == "unverifiable" for n in rows),
        "baseline_n": len(baseline),
        "baseline_k": sum(bool(v) for v in baseline),
        "overlap_count": sum(bool(n.get("overlap")) for n in rows),
    }
