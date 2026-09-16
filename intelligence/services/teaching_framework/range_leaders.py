"""区间涨幅高标链：一段区间内涨幅最高的一组品种（前 N），以及「衔接」的关系描述。

创始人 2026-09-07 第九段：「衔接就是看看上一个高标和下一个高标的关系，一个消亡另一个诞生是怎么衔接
的，但不是每次都是高低连板的衔接，也要看区间涨幅，就是这个载体的形式。也可以理解成一段区间内的涨幅
高的品种和后续涨幅高的品种，他们是怎么衔接转换的。」第十段：「这个取前 10 吧窗口」；窗口沿平台梯队
高度 20 / 60 / 90 / 120 日。

落法（全部确定性）：
- 每个窗口每天一组「区间涨幅高标」= 该窗口复合涨幅前 ``top`` 的品种（并列按代码），窗口不完整不排名。
- 「消亡」= 昨天在组里、今天不在；「诞生」= 今天在组里、昨天不在。组的容量固定，所以同一天消亡与诞生
  一一对应——按名次顺序配对成一次「衔接」，不猜因果，只描述关系：同不同申万一级、诞生者昨天是否已在
  近旁（前 ``context`` 名内 = 递进，之外 = 突入）、消亡者今天是滑落还是跌出、双方是否连板高标（涨停
  ≥ 3 板）、消亡者在组里待了几天。
- 「衔接的形式分布」是读数：创始人第九段说衔接是关系描述，不是二值判定；候选规则等分布看过再立。
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from statistics import median
from typing import Any, Iterable, Mapping

LIMIT_LEADER_BOARDS = 3  # 与连板高标链 top(d) 的门槛一致：涨停 ≥ 3 板才算连板高标

FORM_LABELS = ("同L1·递进", "同L1·突入", "跨L1·递进", "跨L1·突入", "L1未知")


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_range_leaders(
    ranked_rows: Iterable[Mapping[str, Any]],
    *,
    calendar: Iterable[Any],
    windows: Iterable[int],
    top: int,
    context: int = 30,
) -> dict[str, Any]:
    """Return ``{"leaders": [...], "handoffs": [...], "days": {window: [per-day summary]}}``.

    ``ranked_rows`` carry one row per (window_days, trade_date, stock) for the top ``context``
    ranks: ``rank``, ``gain_pct``, ``stock_name``, ``sw_l1`` (may be NULL), ``limit_times``
    (NULL when the stock did not limit up that day).  ``calendar`` orders the days; a day with
    no ranked rows for a window is a gap for that window (no leaders, no handoffs).
    """
    days = [_date(d) for d in calendar]
    by_window: dict[int, dict[date, dict[int, dict[str, Any]]]] = {int(w): {} for w in windows}
    for row in ranked_rows:
        w, d, rank = _int(row.get("window_days")), _date(row.get("trade_date")), _int(row.get("rank"))
        if w not in by_window or d is None or rank is None:
            continue
        by_window[w].setdefault(d, {})[rank] = dict(row)

    leaders_out: list[dict[str, Any]] = []
    handoffs_out: list[dict[str, Any]] = []
    days_out: dict[int, list[dict[str, Any]]] = {}
    for w in sorted(by_window):
        tenure: dict[str, int] = {}
        prev_set: dict[str, int] | None = None  # stock -> rank yesterday (top only)
        prev_ctx: dict[str, int] = {}  # stock -> rank yesterday within context
        prev_rows: dict[int, dict[str, Any]] = {}
        summaries: list[dict[str, Any]] = []
        for d in days:
            ranks = by_window[w].get(d)
            if not ranks:
                summaries.append({"trade_date": d, "status": "no_ranked_rows"})
                prev_set, prev_ctx, prev_rows, tenure = None, {}, {}, {}
                continue
            top_rows = {r: ranks[r] for r in sorted(ranks) if r <= top}
            cur_set = {str(row["stock_ts_code"]): r for r, row in top_rows.items()}
            cur_ctx = {str(row["stock_ts_code"]): r for r, row in ranks.items()}
            new_tenure = {code: (tenure.get(code, 0) + 1) for code in cur_set}
            for r, row in top_rows.items():
                code = str(row["stock_ts_code"])
                leaders_out.append({
                    "window_days": w, "trade_date": d, "rank": r, "stock_ts_code": code, "stock_name": row.get("stock_name"),
                    "gain_pct": row.get("gain_pct"), "sw_l1": row.get("sw_l1"), "limit_times": _int(row.get("limit_times")),
                    "tenure_day": new_tenure[code], "prev_rank": prev_ctx.get(code),
                })
            births: list[str] = []
            exits: list[str] = []
            if prev_set is not None:
                births = sorted((c for c in cur_set if c not in prev_set), key=lambda c: cur_set[c])
                exits = sorted((c for c in prev_set if c not in cur_set), key=lambda c: prev_set[c])
            pairs = list(zip(births, exits))
            unpaired_births = births[len(pairs):]
            unpaired_exits = exits[len(pairs):]
            forms: Counter[str] = Counter()
            for birth, exit_code in pairs:
                b_row = top_rows[cur_set[birth]]
                e_row = prev_rows[prev_set[exit_code]] if prev_set is not None else {}
                birth_prev_rank = prev_ctx.get(birth)
                b_l1, e_l1 = b_row.get("sw_l1"), e_row.get("sw_l1")
                same_l1 = None if (b_l1 is None or e_l1 is None) else (str(b_l1) == str(e_l1))
                form = _form(same_l1, birth_prev_rank)
                forms[form] += 1
                handoffs_out.append({
                    "window_days": w, "trade_date": d,
                    "birth_stock": birth, "birth_name": b_row.get("stock_name"), "birth_rank": cur_set[birth],
                    "birth_prev_rank": birth_prev_rank, "birth_sw_l1": b_l1, "birth_limit_times": _int(b_row.get("limit_times")),
                    "birth_gain_pct": b_row.get("gain_pct"),
                    "exit_stock": exit_code, "exit_name": e_row.get("stock_name"), "exit_prev_rank": prev_set[exit_code],
                    "exit_next_rank": cur_ctx.get(exit_code), "exit_sw_l1": e_l1, "exit_limit_times": _int(e_row.get("limit_times")),
                    "exit_tenure_days": tenure.get(exit_code), "same_l1": same_l1, "form": form,
                })
            tenth = top_rows.get(min(len(top_rows), top)) if top_rows else None
            summaries.append({
                "trade_date": d, "status": "ok", "members": len(cur_set), "births": len(births), "exits": len(exits),
                "unpaired_births": len(unpaired_births), "unpaired_exits": len(unpaired_exits),
                "entry_gain_pct": tenth.get("gain_pct") if tenth else None,
                "top_gain_pct": top_rows[min(top_rows)].get("gain_pct") if top_rows else None,
                "l1_distinct": len({str(row.get("sw_l1")) for row in top_rows.values() if row.get("sw_l1") is not None}),
                "limit_leaders": sum(1 for row in top_rows.values() if (_int(row.get("limit_times")) or 0) >= LIMIT_LEADER_BOARDS),
                "forms": dict(forms),
            })
            prev_set, prev_ctx, prev_rows, tenure = cur_set, cur_ctx, dict(top_rows), new_tenure
        days_out[w] = summaries
    return {"leaders": leaders_out, "handoffs": handoffs_out, "days": days_out}


def _form(same_l1: bool | None, birth_prev_rank: int | None) -> str:
    if same_l1 is None:
        return "L1未知"
    progression = "递进" if birth_prev_rank is not None else "突入"
    return f"{'同L1' if same_l1 else '跨L1'}·{progression}"


def handoff_readouts(result: Mapping[str, Any], reference: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """衔接的形式分布 per window (+ per platform stage when a reference is given).

    Everything here is a readout: how often the group turns over, how long a leader lasts, which
    forms the handoffs take, where the entry threshold (the ``top``-th gain) sits — the numbers
    the founder said should come from history rather than be declared.
    """
    out: dict[str, Any] = {}
    handoffs_by_window: dict[int, list[Mapping[str, Any]]] = {}
    for h in result.get("handoffs", []):
        handoffs_by_window.setdefault(int(h["window_days"]), []).append(h)
    for w, summaries in result.get("days", {}).items():
        ok = [s for s in summaries if s.get("status") == "ok"]
        hs = handoffs_by_window.get(int(w), [])
        forms = Counter(str(h["form"]) for h in hs)
        births_per_day = [s["births"] for s in ok]  # the first day of a run has no yesterday and counts 0
        entry = [float(s["entry_gain_pct"]) for s in ok if s.get("entry_gain_pct") is not None]
        tenures = [int(h["exit_tenure_days"]) for h in hs if h.get("exit_tenure_days") is not None]
        readout: dict[str, Any] = {
            "days_ok": len(ok), "days_gap": len(summaries) - len(ok), "handoffs": len(hs),
            "births_per_day_mean": round(sum(births_per_day) / len(births_per_day), 3) if births_per_day else None,
            "exit_tenure_days_median": median(tenures) if tenures else None,
            "exit_tenure_days_p25_p75": _quartiles(tenures),
            "forms": {form: forms.get(form, 0) for form in FORM_LABELS},
            "form_shares": {form: round(forms.get(form, 0) / len(hs), 4) for form in FORM_LABELS} if hs else {},
            "birth_is_limit_leader_share": _share(hs, lambda h: (h.get("birth_limit_times") or 0) >= LIMIT_LEADER_BOARDS),
            "exit_was_limit_leader_share": _share(hs, lambda h: (h.get("exit_limit_times") or 0) >= LIMIT_LEADER_BOARDS),
            "exit_fell_out_of_context_share": _share(hs, lambda h: h.get("exit_next_rank") is None),
            "entry_gain_pct_quartiles": _quartiles(entry),
            "l1_distinct_median": median([s["l1_distinct"] for s in ok]) if ok else None,
        }
        if reference:
            by_stage: dict[str, dict[str, list[float]]] = {}
            for s in ok:
                stage = str((reference.get(str(s["trade_date"])[:10]) or {}).get("cycle_stage") or "unlabeled")
                bucket = by_stage.setdefault(stage, {"births": [], "entry_gain_pct": [], "limit_leaders": [], "l1_distinct": []})
                bucket["births"].append(float(s["births"]))
                if s.get("entry_gain_pct") is not None:
                    bucket["entry_gain_pct"].append(float(s["entry_gain_pct"]))
                bucket["limit_leaders"].append(float(s["limit_leaders"]))
                bucket["l1_distinct"].append(float(s["l1_distinct"]))
            readout["by_reference_stage"] = {
                stage: {
                    "n": len(v["births"]),
                    "births_per_day_mean": round(sum(v["births"]) / len(v["births"]), 3),
                    "entry_gain_pct_median": round(median(v["entry_gain_pct"]), 3) if v["entry_gain_pct"] else None,
                    "limit_leaders_median": median(v["limit_leaders"]),
                    "l1_distinct_median": median(v["l1_distinct"]),
                }
                for stage, v in sorted(by_stage.items())
            }
            stage_forms: dict[str, Counter[str]] = {}
            for h in hs:
                stage = str((reference.get(str(h["trade_date"])[:10]) or {}).get("cycle_stage") or "unlabeled")
                stage_forms.setdefault(stage, Counter())[str(h["form"])] += 1
            readout["form_shares_by_reference_stage"] = {
                stage: {form: round(c.get(form, 0) / sum(c.values()), 4) for form in FORM_LABELS}
                for stage, c in sorted(stage_forms.items()) if sum(c.values())
            }
        out[str(w)] = readout
    return out


def cross_chain(result: Mapping[str, Any], succession_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """两条链的交叉：连板高标链的每个节点，其前任 / 继任在断板日 / 诞生日是否也是某个窗口的区间涨幅高标。"""
    membership: dict[tuple[date, str], set[int]] = {}
    for row in result.get("leaders", []):
        membership.setdefault((row["trade_date"], str(row["stock_ts_code"])), set()).add(int(row["window_days"]))
    nodes = 0
    leader_i_in = Counter()
    leader_next_in = Counter()
    for node in succession_rows:
        nodes += 1
        break_day, birth_day = _date(node.get("break_day")), _date(node.get("birth_day"))
        for code in _group(node.get("leader_i_group_json"), node.get("leader_i")):
            for w in membership.get((break_day, code), ()):
                leader_i_in[str(w)] += 1
        if birth_day is not None:
            for code in _group(node.get("leader_next_group_json"), node.get("leader_next")):
                for w in membership.get((birth_day, code), ()):
                    leader_next_in[str(w)] += 1
    return {
        "succession_nodes": nodes,
        "leader_i_in_range_top_on_break_day": dict(sorted(leader_i_in.items())),
        "leader_next_in_range_top_on_birth_day": dict(sorted(leader_next_in.items())),
        "note": "counts are node-members × windows; a member sitting in several windows' groups is counted once per window",
    }


def _group(group_json: Any, fallback: Any) -> list[str]:
    import json

    if group_json:
        try:
            parsed = json.loads(str(group_json))
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except ValueError:
            pass
    return [str(fallback)] if fallback else []


def _share(rows: list[Mapping[str, Any]], predicate) -> float | None:
    if not rows:
        return None
    return round(sum(1 for r in rows if predicate(r)) / len(rows), 4)


def _quartiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)

    def nearest_rank(q: float) -> float:
        k = max(1, int(round(q * len(ordered) + 0.5)))
        return ordered[min(len(ordered), k) - 1]

    return {"p25": nearest_rank(0.25), "median": median(ordered), "p75": nearest_rank(0.75), "n": len(ordered)}
