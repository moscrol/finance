"""Deterministic highest-board leader succession builder.

The event detector is intentionally independent from storage.  It returns plain
records that the sidecar writer can persist and keeps the two clocks explicit:
``context_break`` is anchor-time, while ``forward`` and ``context_birth`` are
realized only after the successor is known.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .coverage import CoverageDay, build_coverage, normalize_hhmmss


def _date(value: Any) -> str:
    return str(value)[:10]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class TopResult:
    trade_date: str
    status: str  # ok / none / tie / field_null / data_gap
    stock_ts_code: str | None = None
    stock_name: str | None = None
    boards: int | None = None
    tied_stocks: tuple[str, ...] = ()
    reason: str | None = None

    @property
    def unique(self) -> bool:
        return self.status == "ok"

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date, "status": self.status,
            "stock_ts_code": self.stock_ts_code, "stock_name": self.stock_name,
            "boards": self.boards, "tied_stocks": self.tied_stocks, "reason": self.reason,
        }


@dataclass
class SuccessionNode:
    node_id: str
    leader_i: str | None
    leader_i_name: str | None
    leader_i_peak_boards: int | None
    break_day: str | None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    leader_next: str | None = None
    leader_next_name: str | None = None
    birth_day: str | None = None
    birth_boards: int | None = None
    handoff: bool | None = None
    gap_days: int | None = None
    path: list[dict[str, Any]] = field(default_factory=list)
    shape_tags: dict[str, Any] = field(default_factory=dict)
    context_break: dict[str, Any] = field(default_factory=dict)
    context_birth: dict[str, Any] = field(default_factory=dict)
    forward: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    status_reason: str | None = None
    hindsight: bool = False
    framework_version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        # Keep JSON fields native; the sidecar adapter may serialize them later.
        return {
            "node_id": self.node_id, "leader_i": self.leader_i,
            "leader_i_name": self.leader_i_name, "leader_i_peak_boards": self.leader_i_peak_boards,
            "break_day": self.break_day, "candidates": self.candidates,
            "leader_next": self.leader_next, "leader_next_name": self.leader_next_name,
            "birth_day": self.birth_day, "birth_boards": self.birth_boards,
            "handoff": self.handoff, "gap_days": self.gap_days, "path": self.path,
            "shape_tags": self.shape_tags, "context_break": self.context_break,
            "context_birth": self.context_birth, "forward": self.forward,
            "status": self.status, "status_reason": self.status_reason,
            "hindsight": self.hindsight, "framework_version": self.framework_version,
        }


def top_by_day(coverage: Mapping[str, CoverageDay] | Mapping[str, Iterable[Mapping[str, Any]]]) -> dict[str, TopResult]:
    """Compute unique top for every calendar day, fail-closed on NULL and ties."""
    result: dict[str, TopResult] = {}
    for day, value in coverage.items():
        day = _date(day)
        if not isinstance(value, CoverageDay):
            items = tuple(value or ())
            cday = CoverageDay(day, "covered" if items else "covered_empty", items)
        else:
            cday = value
        if cday.status == "missing":
            result[day] = TopResult(day, "data_gap", reason="source_day_absent")
            continue
        rows = list(cday.rows)
        if not rows:
            result[day] = TopResult(day, "none")
            continue
        valid = [r for r in rows if r.get("limit_times") is not None]
        if not valid:
            result[day] = TopResult(day, "field_null", reason="limit_times_null")
            continue
        parsed: list[tuple[dict[str, Any], int]] = []
        for row in valid:
            try:
                parsed.append((row, int(float(row["limit_times"]))))
            except (TypeError, ValueError):
                continue
        if not parsed:
            result[day] = TopResult(day, "field_null", reason="limit_times_malformed")
            continue
        max_boards = max(b for _, b in parsed)
        leaders = [r for r, b in parsed if b == max_boards]
        if max_boards < 3:
            result[day] = TopResult(day, "none", boards=max_boards)
        elif len(leaders) > 1:
            tied = tuple(sorted(str(r.get("stock_ts_code")) for r in leaders))
            result[day] = TopResult(day, "tie", boards=max_boards, tied_stocks=tied)
        else:
            row = leaders[0]
            result[day] = TopResult(day, "ok", str(row.get("stock_ts_code")), row.get("stock_name"), max_boards)
    return result


def _row_for(coverage: Mapping[str, CoverageDay], day: str, stock: str) -> dict[str, Any] | None:
    cday = coverage.get(day)
    if not cday or cday.status == "missing":
        return None
    for row in cday.rows:
        if str(row.get("stock_ts_code")) == str(stock):
            return row
    return None


def detect_overtaken(
    calendar_dates: Iterable[Any],
    tops: Mapping[str, TopResult],
    coverage: Mapping[str, CoverageDay],
) -> list[dict[str, Any]]:
    """Record every adjacent day where the previous top remains limit-up but is surpassed."""
    dates = sorted(_date(d) for d in calendar_dates)
    events: list[dict[str, Any]] = []
    for previous, current in zip(dates, dates[1:]):
        a, b = tops.get(previous), tops.get(current)
        if not a or not b or a.status != "ok" or b.status != "ok" or a.stock_ts_code == b.stock_ts_code:
            continue
        row = _row_for(coverage, current, a.stock_ts_code)
        if row is None or row.get("limit_times") is None:
            continue
        try:
            prior_boards = int(float(row["limit_times"]))
        except (TypeError, ValueError):
            continue
        if b.boards is not None and b.boards > prior_boards:
            events.append({
                "event_day": current,
                "previous_top": a.stock_ts_code,
                "previous_top_boards": prior_boards,
                "overtaken_by": b.stock_ts_code,
                "overtaken_by_boards": b.boards,
                "event_granularity": "daily",
            })
    return events


def _unknown_shape(path: list[dict[str, Any]], params: Mapping[str, Any]) -> dict[str, Any]:
    def vals(name: str) -> list[Any]:
        return [p.get(name) for p in path]

    limit_values = vals("limit_times")
    in_table = [bool(p.get("in_table")) for p in path]
    has_null_limit = any(p.get("in_table") and p.get("limit_times") is None for p in path)
    def tri(predicate: bool, unknown: bool = False) -> str | bool:
        return "unknown" if unknown else predicate

    rebound = False
    nshape = False
    # Any missing limit value in an observed path prevents guessing shape.
    if has_null_limit:
        rebound = nshape = "unknown"
    else:
        for i in range(1, len(path)):
            # A re-entry requires an observed off-table interval immediately before
            # the later limit-up day; continuous rows are continuation, not shape.
            if not in_table[i] or in_table[i - 1]:
                continue
            before = limit_values[:i]
            if any(isinstance(v, (int, float)) and v >= 2 for v in before):
                rebound = True
            # N shape is specifically a one-to-two trading-day hiatus after a
            # first board, rather than an arbitrarily long absence.
            off_days = 0
            for k in range(i - 1, -1, -1):
                if in_table[k]:
                    break
                off_days += 1
            if off_days in (1, 2) and any(v == 1 for v in before):
                nshape = True
    open_unknown = any(p.get("in_table") and p.get("open_times") is None for p in path)
    birth = path[-1] if path else {}
    seal = birth.get("open_times")
    instant_threshold = str(params.get("instant_seal_time", "09:35"))
    try:
        seal_num = None if seal is None else float(seal)
    except (TypeError, ValueError):
        seal_num = None
    if seal_num is None or birth.get("first_limit_time") is None:
        one_word: str | bool = "unknown"
    else:
        one_word = seal_num == 0 and birth["first_limit_time"] <= instant_threshold
    circ_unknown = any(p.get("in_table") and (p.get("amount") is None or p.get("circ_mv") is None) for p in path)
    ratio = None
    for p in path:
        if p.get("in_table") and p.get("amount") is not None and p.get("circ_mv") not in (None, 0):
            try:
                ratio = float(p["amount"]) / float(p["circ_mv"])
            except (TypeError, ValueError, ZeroDivisionError):
                ratio = None
    high_turnover = "unknown" if circ_unknown else None  # threshold intentionally unassigned in v0
    return {
        "rebound_after_break": rebound,
        "n_shape": nshape,
        "reseal": "unknown" if open_unknown else (bool(seal_num is not None and seal_num >= 1)),
        "one_word_or_instant": one_word,
        "high_turnover": high_turnover,
        "turnover_ratio": ratio,
    }


def _make_path(coverage: Mapping[str, CoverageDay], days: list[str], stock: str) -> list[dict[str, Any]]:
    path: list[dict[str, Any]] = []
    for day in days:
        cday = coverage.get(day)
        row = _row_for(coverage, day, stock)
        path.append({
            "day": day,
            "in_table": row is not None,
            "limit_times": row.get("limit_times") if row else None,
            "open_times": row.get("open_times") if row else None,
            "first_limit_time": normalize_hhmmss(row.get("first_limit_time")) if row else None,
            "up_stat": row.get("up_stat") if row else None,
            "amount": row.get("amount") if row else None,
            "circ_mv": row.get("circ_mv") if row else None,
            "coverage": cday.status if cday else "missing",
        })
    return path


def build_succession(
    calendar_dates: Iterable[Any],
    rows: Iterable[Any] | Mapping[Any, Iterable[Any]],
    *,
    covered_dates: Iterable[Any] | None = None,
    params: Mapping[str, Any] | None = None,
    knowledge_cutoff: Any | None = None,
    context_by_date: Mapping[str, Mapping[str, Any]] | None = None,
    framework_version: str | None = None,
) -> dict[str, Any]:
    """Build succession nodes and overtaken events from a calendar and limit rows."""
    params = params or {}
    dates = sorted({_date(d) for d in calendar_dates})
    coverage = build_coverage(dates, rows, covered_dates=covered_dates)
    tops = top_by_day(coverage)
    overtaken = detect_overtaken(dates, tops, coverage)
    nodes: list[SuccessionNode] = []
    for i, day in enumerate(dates):
        if i == 0:
            continue
        previous = dates[i - 1]
        prior = tops.get(previous)
        now = coverage[day]
        # A break requires a unique prior top and a covered current day where it is
        # absent.  Missing source days are data gaps, never breaks.
        if not prior or prior.status != "ok":
            continue
        if now.status == "missing":
            continue
        prev_row = _row_for(coverage, day, prior.stock_ts_code or "")
        if prev_row is not None:
            continue  # still sealed; an overtaken event is recorded separately
        node_hash = hashlib.sha256(f"{prior.stock_ts_code}|{day}".encode()).hexdigest()[:16]
        base = SuccessionNode(node_hash, prior.stock_ts_code, prior.stock_name, prior.boards, day)
        base.context_break = dict((context_by_date or {}).get(day, {}))
        base.context_break.setdefault("anchor_as_of", day)
        base.context_break.setdefault("knowledge_cutoff", day)
        # Candidate window is T-1/T/T+1 and must have complete source coverage.
        win_idx = [j for j in (i - 1, i, i + 1) if 0 <= j < len(dates)]
        win_days = [dates[j] for j in win_idx]
        if any(coverage[d].status == "missing" for d in win_days):
            base.status, base.status_reason = "unverifiable", "data_gap"
            nodes.append(base)
            continue
        for cday in win_days:
            for row in coverage[cday].rows:
                lt = row.get("limit_times")
                if lt is not None:
                    try:
                        lt_num = int(float(lt))
                    except (TypeError, ValueError):
                        continue
                    if lt_num <= 2 and str(row.get("stock_ts_code")) != str(prior.stock_ts_code):
                        base.candidates.append({"stock": row.get("stock_ts_code"), "name": row.get("stock_name"), "day": cday, "limit_times": lt_num})
        # De-dupe candidate stock while retaining first observation.
        seen: set[Any] = set()
        base.candidates = [c for c in base.candidates if not (c["stock"] in seen or seen.add(c["stock"]))]
        next_top: TopResult | None = None
        next_idx: int | None = None
        for j in range(i, len(dates)):
            d = dates[j]
            t = tops[d]
            if t.status == "data_gap":
                base.status, base.status_reason = "unverifiable", "data_gap"
                break
            if t.status in {"tie", "field_null"}:
                base.status, base.status_reason = "unverifiable", t.status
                break
            if t.status == "ok" and t.stock_ts_code != prior.stock_ts_code:
                next_top, next_idx = t, j
                break
        if base.status != "ok":
            nodes.append(base)
            continue
        if next_top is None:
            base.status, base.status_reason = "open", "tail_no_successor"
            nodes.append(base)
            continue
        birth_day = dates[next_idx]
        # Any source gap between the anchor and realized birth invalidates the link.
        if any(coverage[d].status == "missing" for d in dates[i - 1 : next_idx + 1]):
            base.status, base.status_reason = "unverifiable", "data_gap"
            nodes.append(base)
            continue
        base.leader_next, base.leader_next_name, base.birth_day, base.birth_boards = next_top.stock_ts_code, next_top.stock_name, birth_day, next_top.boards
        base.gap_days = next_idx - i
        base.handoff = any(str(c.get("stock")) == str(next_top.stock_ts_code) for c in base.candidates)
        lookback = int(params.get("rebound_window_days", 5) or 5)
        start = max(0, next_idx - lookback + 1)
        base.path = _make_path(coverage, dates[start : next_idx + 1], next_top.stock_ts_code or "")
        base.shape_tags = _unknown_shape(base.path, params)
        base.forward = {"realized": True, "anchor_as_of": day, "target": birth_day, "knowledge_cutoff": birth_day}
        cutoff = _date(knowledge_cutoff) if knowledge_cutoff is not None else None
        if cutoff is not None and cutoff >= birth_day:
            base.context_birth = dict((context_by_date or {}).get(birth_day, {}))
            base.context_birth.setdefault("context_target", birth_day)
            base.context_birth.setdefault("knowledge_cutoff", cutoff)
        else:
            base.context_birth = {"context_target": birth_day, "knowledge_cutoff": cutoff, "status": "withheld_until_cutoff"}
        nodes.append(base)
    return {"nodes": nodes, "overtaken": overtaken, "coverage": coverage, "tops": tops}


build_leader_succession = build_succession

__all__ = [
    "SuccessionNode", "TopResult", "build_succession", "build_leader_succession",
    "detect_overtaken", "top_by_day",
]
