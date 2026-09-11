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


GROUP_SEP = "|"


def join_group(stocks: Iterable[Any]) -> str | None:
    """Canonical text form of a leader group (sorted, ``|``-joined); None for an empty group."""
    items = sorted(str(s) for s in stocks)
    return GROUP_SEP.join(items) if items else None


@dataclass(frozen=True)
class TopResult:
    """The market's highest-board leader(s) on a day.

    创始人 2026-09-07 第六段：「最高标不要求唯一，可以并列多个」。``stocks`` is the whole
    group at the maximum board count (sorted); ``stock_ts_code`` / ``stock_name`` keep the
    first member for display only and must not be used to compare leaders.
    """

    trade_date: str
    status: str  # ok / none / field_null / data_gap
    stock_ts_code: str | None = None
    stock_name: str | None = None
    boards: int | None = None
    stocks: tuple[str, ...] = ()
    names: tuple[str | None, ...] = ()
    reason: str | None = None

    @property
    def tie_size(self) -> int:
        return len(self.stocks)

    @property
    def tied_stocks(self) -> tuple[str, ...]:
        return self.stocks if len(self.stocks) > 1 else ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date, "status": self.status,
            "stock_ts_code": self.stock_ts_code, "stock_name": self.stock_name,
            "boards": self.boards, "stocks": list(self.stocks), "names": list(self.names),
            "tie_size": self.tie_size, "reason": self.reason,
        }


@dataclass
class SuccessionNode:
    node_id: str
    leader_i: str | None
    leader_i_name: str | None
    leader_i_peak_boards: int | None
    break_day: str | None
    leader_i_group: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    leader_next: str | None = None
    leader_next_name: str | None = None
    leader_next_group: list[str] = field(default_factory=list)
    birth_day: str | None = None
    birth_boards: int | None = None
    handoff: bool | None = None
    gap_days: int | None = None
    path: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    shape_tags: dict[str, dict[str, Any]] = field(default_factory=dict)
    context_break: dict[str, Any] = field(default_factory=dict)
    context_birth: dict[str, Any] = field(default_factory=dict)
    forward: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    status_reason: str | None = None
    framework_version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        # Keep JSON fields native; the sidecar adapter may serialize them later.
        return {
            "node_id": self.node_id, "leader_i": self.leader_i,
            "leader_i_name": self.leader_i_name, "leader_i_peak_boards": self.leader_i_peak_boards,
            "leader_i_group": self.leader_i_group,
            "break_day": self.break_day, "candidates": self.candidates,
            "leader_next": self.leader_next, "leader_next_name": self.leader_next_name,
            "leader_next_group": self.leader_next_group,
            "birth_day": self.birth_day, "birth_boards": self.birth_boards,
            "handoff": self.handoff, "gap_days": self.gap_days, "path": self.path,
            "shape_tags": self.shape_tags, "context_break": self.context_break,
            "context_birth": self.context_birth, "forward": self.forward,
            "status": self.status, "status_reason": self.status_reason,
            "framework_version": self.framework_version,
        }


def top_by_day(coverage: Mapping[str, CoverageDay] | Mapping[str, Iterable[Mapping[str, Any]]]) -> dict[str, TopResult]:
    """Compute the top group for every calendar day, fail-closed on NULL; ties are a group, not an error."""
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
        leaders = sorted((r for r, b in parsed if b == max_boards), key=lambda r: str(r.get("stock_ts_code")))
        if max_boards < 3:
            result[day] = TopResult(day, "none", boards=max_boards)
        else:
            stocks = tuple(str(r.get("stock_ts_code")) for r in leaders)
            names = tuple(r.get("stock_name") for r in leaders)
            result[day] = TopResult(day, "ok", stocks[0], names[0], max_boards, stocks=stocks, names=names)
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
        if not a or not b or a.status != "ok" or b.status != "ok":
            continue
        for stock in a.stocks:
            if stock in b.stocks:
                continue
            row = _row_for(coverage, current, stock)
            if row is None or row.get("limit_times") is None:
                continue
            try:
                prior_boards = int(float(row["limit_times"]))
            except (TypeError, ValueError):
                continue
            if b.boards is not None and b.boards > prior_boards:
                events.append({
                    "event_day": current,
                    "previous_top": stock,
                    "previous_top_boards": prior_boards,
                    "overtaken_by": join_group(b.stocks),
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
    # A missing source day looks like "off table" and would fake a re-entry.
    has_missing_day = any(p.get("coverage") == "missing" for p in path)

    rebound: str | bool = False
    nshape: str | bool = False
    if has_null_limit or has_missing_day:
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
    river_db_path: Any | None = None,
    river_entity: str = "上证指数",
) -> dict[str, Any]:
    """Build succession nodes and overtaken events from a calendar and limit rows.

    ``river_db_path``（工单 #35）：非空时，把锚点日 / 诞生日的河切片挂进
    ``context_break`` / ``context_birth``（``river_anchor.river_context_dict``），
    **教学标签字段原样保留**——handoff 读数与不传时逐字节相同。
    """
    params = params or {}
    dates = sorted({_date(d) for d in calendar_dates})
    coverage = build_coverage(dates, rows, covered_dates=covered_dates)
    tops = top_by_day(coverage)
    overtaken = detect_overtaken(dates, tops, coverage)
    nodes: list[SuccessionNode] = []
    # Days where some but not all members of a tied leader group broke: the
    # market's highest board is still one of yesterday's leaders, so by the
    # founder's definition (「前一天的市场最高连板第二天不是了，那就是断板日」) this
    # is not a break.  Counted so the alternative reading can be sized.
    partial_breaks: list[dict[str, Any]] = []

    def _enrich(base: dict[str, Any], day: str, *, cutoff: str) -> dict[str, Any]:
        """教学标签 ∪ 河切片。河读失败不挡主路径——上下文是附加，不是条件。"""
        out = dict(base)
        if river_db_path is None:
            return out
        try:
            from intelligence.services.river_anchor import river_context_dict
            from intelligence.services.river import slice_river

            sl = slice_river(day, river_entity, knowledge_cutoff=cutoff, db_path=river_db_path)
            river = river_context_dict(sl)
            # 教学标签优先：同名键不被河切片覆盖（stage_coarse 等决定 handoff 分桶）。
            merged = {**river, **out}
            merged["river_enriched"] = True
            return merged
        except Exception as exc:  # noqa: BLE001 — 上下文附加失败不能拖垮断板检测
            out.setdefault("river_enrich_error", f"{type(exc).__name__}: {exc}"[:160])
            return out

    for i, day in enumerate(dates):
        if i == 0:
            continue
        previous = dates[i - 1]
        prior = tops.get(previous)
        now = coverage[day]
        # A break requires a prior top group and a covered current day where none
        # of its members is sealed.  Missing source days are data gaps, never breaks.
        if not prior or prior.status != "ok":
            continue
        prior_group = list(prior.stocks)
        prior_key = join_group(prior_group) or ""
        prior_names = GROUP_SEP.join(str(n) for n in prior.names) if prior.names else None

        def new_node(node_day: str) -> SuccessionNode:
            node_hash = hashlib.sha256(f"{prior_key}|{node_day}".encode()).hexdigest()[:16]
            node = SuccessionNode(node_hash, prior_key, prior_names, prior.boards, node_day, leader_i_group=list(prior_group))
            base_ctx = dict((context_by_date or {}).get(node_day, {}))
            base_ctx.setdefault("anchor_as_of", node_day)
            base_ctx.setdefault("knowledge_cutoff", node_day)
            node.context_break = _enrich(base_ctx, node_day, cutoff=str(node_day))
            return node

        if now.status == "missing":
            gap_node = new_node(day)
            gap_node.status, gap_node.status_reason = "unverifiable", "data_gap"
            nodes.append(gap_node)
            continue
        still_sealed = [s for s in prior_group if _row_for(coverage, day, s) is not None]
        if still_sealed:
            if len(still_sealed) < len(prior_group):
                partial_breaks.append({"day": day, "group": prior_group, "still_sealed": still_sealed})
            continue  # the market's highest is still one of yesterday's leaders
        base = new_node(day)
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
                    if lt_num <= 2 and str(row.get("stock_ts_code")) not in prior_group:
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
            if t.status == "field_null":
                base.status, base.status_reason = "unverifiable", t.status
                break
            # The next leader group must be wholly new: a member of the broken
            # group re-emerging at the top is not a succession.
            if t.status == "ok" and not set(t.stocks) & set(prior_group):
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
        base.leader_next_group = list(next_top.stocks)
        base.leader_next = join_group(next_top.stocks)
        base.leader_next_name = GROUP_SEP.join(str(n) for n in next_top.names) if next_top.names else None
        base.birth_day, base.birth_boards = birth_day, next_top.boards
        base.gap_days = next_idx - i
        candidate_codes = {str(c.get("stock")) for c in base.candidates}
        handoff_members = [s for s in next_top.stocks if s in candidate_codes]
        # 「衔接」 holds when any member of the new top group came out of the
        # low-board candidates; the members are listed so an all-members reading
        # can be derived from the same rows.
        base.handoff = bool(handoff_members)
        # Shape tags describe what each successor did *before* its current streak
        # (断板反包 / N 字 are re-entries).  The lookback window therefore starts
        # ``rebound_window_days`` before the streak began, not before birth day;
        # anchored at birth, a 4+ board successor would fill the window with its
        # own streak and every shape would read false.
        lookback = int(params.get("rebound_window_days", 5) or 5)
        for stock in next_top.stocks:
            streak_start = next_idx
            while streak_start > 0 and _row_for(coverage, dates[streak_start - 1], stock) is not None:
                streak_start -= 1
            start = max(0, streak_start - lookback)
            base.path[stock] = _make_path(coverage, dates[start : next_idx + 1], stock)
            base.shape_tags[stock] = _unknown_shape(base.path[stock], params)
        base.forward = {
            "realized": True, "anchor_as_of": day, "target": birth_day, "knowledge_cutoff": birth_day,
            "leader_next_size": len(next_top.stocks), "handoff_members": handoff_members,
        }
        cutoff = _date(knowledge_cutoff) if knowledge_cutoff is not None else None
        if cutoff is not None and cutoff >= birth_day:
            base_ctx = dict((context_by_date or {}).get(birth_day, {}))
            base_ctx.setdefault("context_target", birth_day)
            base_ctx.setdefault("knowledge_cutoff", cutoff)
            base.context_birth = _enrich(base_ctx, birth_day, cutoff=str(cutoff))
        else:
            base.context_birth = {"context_target": birth_day, "knowledge_cutoff": cutoff, "status": "withheld_until_cutoff"}
        nodes.append(base)
    return {"nodes": nodes, "overtaken": overtaken, "coverage": coverage, "tops": tops, "partial_breaks": partial_breaks}


build_leader_succession = build_succession

__all__ = [
    "GROUP_SEP", "SuccessionNode", "TopResult", "build_succession", "build_leader_succession",
    "detect_overtaken", "join_group", "top_by_day",
]
