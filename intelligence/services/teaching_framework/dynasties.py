"""王朝链：区间涨幅高标的**王朝级**衔接与「分离确认」（创始人 2026-09-07 第十三段）。

第十三段原话（逐句在骨架 §1.3）：「第一波的区间涨幅靠前的品种，见顶后不是锁定了区间涨幅吗，这时候低位可能
就有新的品种衔接，但是你站在当时那个节点是看不出谁会是后续下一个区间涨幅靠前的品种，我们能做的就是在两个
区间涨幅前列品种都走出来后，回溯去看找这个衔接关系……一个高涨幅品种往往带领的是一个旧王朝，谁能抗住旧王朝
的覆灭走出来的新王朝，是怎么完成衔接的。我有个定义叫分离确认，因为旧的王朝覆灭会带来亏钱效应，而在亏钱效应
下酝酿走强的，往往就有新王朝的特质。但是这个区间高涨幅品种，可以是连板形式买也可以是趋势形式等。」

落法（全部确定性，**事后回溯**——两个王朝都走出来之后才有一节）：
- **波** 按平台八段切（第十段「平台当参照」）：主流主升 / 主流主升2.0 / 承接盘反复 的连续段是一波的顶部块；
  波的起点 = 顶部块之前紧邻的 共建主线 段首日（没有就是块首日）；见顶日 = 顶部块末日。
- **王朝** = 一波里区间涨幅前 ``top`` 的品种；区间涨幅 = 见顶日收盘 / 起点前一日收盘 − 1（「见顶后锁定了区间涨幅」）。
  ``cohort``（≥ top）是读数用的宽队列。载体形式：波内最高连板 ≥ 3 板为「连板」，否则「趋势」——原话「可以是连板形式
  也可以是趋势形式」，两种都算，只标不筛。
- **覆灭窗**（亏钱效应）= 见顶日之后第一天 → 下一波起点前一日；没有下一波的一波是 ``open``，不成节。
  第一段 = 见顶后第一个 左底向下 段（「抗住旧王朝的覆灭」最先看这一段）。
- **分离确认** = 新王朝成员在旧王朝覆灭窗里的相对强弱，两条并排：区间收益在全市场的分位 ≥ ``separation_percentile``
  （相对分离）；窗内是否创 ``separation_new_high_window`` 日新高（新高分离，「在亏钱效应下酝酿走强」）。基准是同窗
  所有有完整行情的个股。规则形态由 ``methodology_backtest.stats.readout`` 出四态：单位 = 一次覆灭窗里的一只个股，
  条件 = 相对分离，结果 = 进了新王朝前 ``cohort``。
- **关系描述**（第九段「衔接是关系描述」）：新成员在旧波的名次、是否出自旧王朝前 cohort、申万一级是否在旧王朝前 top
  的一级集合里、载体形式。不猜因果。
- **亏钱效应可量**（第十四段「亏钱效应也要可量」）：亏钱效应日 = 市场级旗标 ``tf.money_losing_day``（承接 5 日均值低于
  门槛，见 ``flags.py``）。每波报顶部块 / 覆灭窗 / 覆灭窗前 10 日里的亏钱日数（「旧王朝覆灭会带来亏钱效应」要量得出来，
  也要看亏钱效应是否先于平台的左底向下标注出现）；新王朝成员另算「亏钱日上的累计收益」及其分位——第三条分离确认
  ``separation_on_losing_days``，与整窗分离并排，回答「酝酿走强」是发生在亏钱日本身还是亏钱效应期间的其余日子。
"""

from __future__ import annotations

import bisect
from collections import Counter
from datetime import date
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from intelligence.services.methodology_backtest.stats import readout as stats_readout

PEAK_STAGES = ("主流主升", "主流主升2.0", "承接盘反复")
BUILD_STAGE = "共建主线"
FIRST_DOWN_STAGE = "左底向下"
LIMIT_LEADER_BOARDS = 3  # 与连板链 / 区间链同一条尺子
FORM_LIMIT, FORM_TREND = "连板", "趋势"


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _quartiles(values: Sequence[float]) -> dict[str, float] | None:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    ordered = sorted(vals)

    def nearest_rank(q: float) -> float:
        k = max(1, int(round(q * len(ordered) + 0.5)))
        return round(ordered[min(len(ordered), k) - 1], 3)

    return {"p25": nearest_rank(0.25), "median": round(median(ordered), 3), "p75": nearest_rank(0.75), "n": len(ordered)}


def _share(items: Sequence[Any], predicate) -> float | None:
    if not items:
        return None
    return round(sum(1 for x in items if predicate(x)) / len(items), 4)


def segment_waves(stage_rows: Iterable[tuple[Any, Any]], calendar: Sequence[Any]) -> list[dict[str, Any]]:
    """Cut the platform's daily stage sequence into waves (dynasties).

    ``stage_rows`` are ``(trade_date, cycle_stage)`` for the reference days; ``calendar`` is the
    ordered trading calendar (must cover the reference days and at least one day before / after).
    A wave whose peak block starts on the very first reference day has no visible start
    (``truncated``); a wave with no following wave has an open collapse (``open``).
    """
    cal = [_date(d) for d in calendar]
    cal_i = {d: i for i, d in enumerate(cal)}
    rows = sorted(((_date(d), str(s)) for d, s in stage_rows if d is not None and s is not None), key=lambda x: x[0])
    segs: list[dict[str, Any]] = []
    for d, s in rows:
        if segs and segs[-1]["stage"] == s:
            segs[-1]["end"] = d
            segs[-1]["days"] += 1
        else:
            segs.append({"stage": s, "start": d, "end": d, "days": 1})
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(segs):
        if segs[i]["stage"] in PEAK_STAGES:
            j = i
            while j + 1 < len(segs) and segs[j + 1]["stage"] in PEAK_STAGES:
                j += 1
            blocks.append((i, j))
            i = j + 1
        else:
            i += 1

    def wave_start(i0: int) -> date:
        if i0 - 1 >= 0 and segs[i0 - 1]["stage"] == BUILD_STAGE:
            return segs[i0 - 1]["start"]
        return segs[i0]["start"]

    def shift(d: date, n: int) -> date | None:
        k = cal_i.get(d)
        if k is None or not (0 <= k + n < len(cal)):
            return None
        return cal[k + n]

    waves: list[dict[str, Any]] = []
    for bi, (i0, i1) in enumerate(blocks):
        start, peak_end = wave_start(i0), segs[i1]["end"]
        nxt = wave_start(blocks[bi + 1][0]) if bi + 1 < len(blocks) else None
        truncated = i0 == 0 or (i0 - 1 == 0 and segs[0]["stage"] == BUILD_STAGE)
        collapse_start = shift(peak_end, 1)
        collapse_end = shift(nxt, -1) if nxt else None
        first_down_end = next((s["end"] for s in segs if s["start"] > peak_end and s["stage"] == FIRST_DOWN_STAGE), None)
        if collapse_end is not None and first_down_end is not None and first_down_end > collapse_end:
            first_down_end = None
        stages_in_collapse: Counter[str] = Counter()
        for d, s in rows:
            if collapse_start and d >= collapse_start and (collapse_end is None or d <= collapse_end):
                stages_in_collapse[s] += 1
        waves.append({
            "wave_idx": bi,
            "start": start,
            "start_prev": shift(start, -1),
            "peak_end": peak_end,
            "block": [segs[x]["stage"] for x in range(i0, i1 + 1)],
            "block_days": sum(segs[x]["days"] for x in range(i0, i1 + 1)),
            "wave_days": (cal_i[peak_end] - cal_i[start] + 1) if start in cal_i and peak_end in cal_i else None,
            "collapse_start": collapse_start,
            "collapse_end": collapse_end,
            "collapse_days": (cal_i[collapse_end] - cal_i[collapse_start] + 1) if collapse_start in cal_i and collapse_end in cal_i else None,
            "first_down_end": first_down_end,
            "stages_in_collapse": dict(stages_in_collapse),
            "status": "truncated" if truncated else ("open" if collapse_end is None else "ok"),
        })
    return waves


def _form(max_boards: Any) -> str:
    boards = _num(max_boards)
    return FORM_LIMIT if boards is not None and boards >= LIMIT_LEADER_BOARDS else FORM_TREND


def build_dynasties(
    waves: Sequence[Mapping[str, Any]],
    wave_gains: Mapping[int, Iterable[Mapping[str, Any]]],
    collapse_stats: Mapping[int, Iterable[Mapping[str, Any]]],
    *,
    top: int,
    cohort: int,
    separation_percentile: float,
    index_returns: Mapping[int, float | None] | None = None,
    min_n: int = 10,
    money_losing: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble dynasties, their handoffs and the readouts.

    ``wave_gains[wave_idx]`` rows: ``stock_ts_code, stock_name, gain_pct, sw_l1, max_boards`` for every
    stock with a close on both the day before the wave start and the peak day.
    ``collapse_stats[wave_idx]`` rows (completed collapses only): ``stock_ts_code, ret_pct, max_dd_pct,
    new_high, first_leg_ret_pct`` for every stock with a close on both ends of the collapse window, plus
    ``losing_ret_pct`` (compounded return over the window's money-losing days; None when there are none).
    ``index_returns[wave_idx]`` is the index return over the collapse window (None when unknown).
    ``money_losing[wave_idx]`` carries the 亏钱效应 counts of the wave: ``peak_block`` / ``collapse`` /
    ``lead`` (the 10 days before the collapse starts), each ``{"days": labelled days, "flagged": 亏钱日}``,
    and ``collapse_days`` (the flagged dates themselves).
    """
    if cohort < top:
        raise ValueError("cohort 必须 ≥ top")
    money_losing = money_losing or {}
    ranked: dict[int, list[dict[str, Any]]] = {}
    rank_of: dict[int, dict[str, int]] = {}
    for w in waves:
        rows = [dict(r) for r in wave_gains.get(int(w["wave_idx"]), []) if _num(r.get("gain_pct")) is not None]
        rows.sort(key=lambda r: (-float(r["gain_pct"]), str(r["stock_ts_code"])))
        ranked[int(w["wave_idx"])] = rows
        rank_of[int(w["wave_idx"])] = {str(r["stock_ts_code"]): n + 1 for n, r in enumerate(rows)}

    members_out: list[dict[str, Any]] = []
    handoffs_out: list[dict[str, Any]] = []
    wave_readouts: list[dict[str, Any]] = []
    handoff_readouts: list[dict[str, Any]] = []
    pooled: dict[str, dict[str, Any]] = {
        f"top{top}": {"units": [], "base_n": 0, "base_k": 0},
        f"cohort{cohort}": {"units": [], "base_n": 0, "base_k": 0},
    }
    for k, w in enumerate(waves):
        wi = int(w["wave_idx"])
        rows = ranked[wi]
        own_stats = {str(r["stock_ts_code"]): dict(r) for r in collapse_stats.get(wi, [])}
        for n, r in enumerate(rows[:cohort], start=1):
            code = str(r["stock_ts_code"])
            own = own_stats.get(code, {})
            members_out.append({
                "wave_idx": wi, "rank": n, "wave_start": w["start"], "peak_end": w["peak_end"],
                "collapse_start": w.get("collapse_start"), "collapse_end": w.get("collapse_end"), "wave_status": w["status"],
                "stock_ts_code": code, "stock_name": r.get("stock_name"), "wave_gain_pct": _num(r.get("gain_pct")),
                "sw_l1": r.get("sw_l1"), "max_boards": None if _num(r.get("max_boards")) is None else int(float(r["max_boards"])),
                "form": _form(r.get("max_boards")),
                "collapse_ret_pct": _num(own.get("ret_pct")), "collapse_max_dd_pct": _num(own.get("max_dd_pct")),
            })
        top_rows, cohort_rows = rows[:top], rows[:cohort]
        wave_readouts.append({
            "wave_idx": wi, "status": w["status"], "start": str(w["start"]), "peak_end": str(w["peak_end"]), "block": list(w["block"]),
            "block_days": w["block_days"], "wave_days": w.get("wave_days"),
            "collapse": [None if w.get("collapse_start") is None else str(w["collapse_start"]), None if w.get("collapse_end") is None else str(w["collapse_end"])],
            "collapse_days": w.get("collapse_days"), "first_down_end": None if w.get("first_down_end") is None else str(w["first_down_end"]),
            "stages_in_collapse": dict(w.get("stages_in_collapse") or {}),
            "ranked_stocks": len(rows),
            "entry_gain_pct": {f"top{top}": _num(top_rows[-1]["gain_pct"]) if len(top_rows) >= top else None,
                               f"cohort{cohort}": _num(cohort_rows[-1]["gain_pct"]) if len(cohort_rows) >= cohort else None},
            "forms": {f"top{top}": dict(Counter(_form(r.get("max_boards")) for r in top_rows)),
                      f"cohort{cohort}": dict(Counter(_form(r.get("max_boards")) for r in cohort_rows))},
            "l1_distinct": {f"top{top}": len({r.get("sw_l1") for r in top_rows if r.get("sw_l1")}),
                            f"cohort{cohort}": len({r.get("sw_l1") for r in cohort_rows if r.get("sw_l1")})},
            "money_losing": _money_losing_readout(money_losing.get(wi)),
        })
        # ---- handoff k → k+1 (needs a completed collapse and a next wave) ----
        if w["status"] == "open" or k + 1 >= len(waves) or w.get("collapse_end") is None:
            continue
        nw = waves[k + 1]
        nwi = int(nw["wave_idx"])
        stats = own_stats
        all_ret = sorted(float(s["ret_pct"]) for s in stats.values() if _num(s.get("ret_pct")) is not None)
        if not all_ret:
            handoff_readouts.append({"handoff": f"W{wi}→W{nwi}", "status": "no_collapse_rows"})
            continue
        n_all = len(all_ret)
        med_ret = median(all_ret)

        def pct(x: float) -> float:
            return round(100.0 * bisect.bisect_left(all_ret, x) / n_all, 2)

        threshold_pct = 100.0 * float(separation_percentile)
        # 亏钱日上的累计收益：只有窗内真有亏钱日、且该股每个亏钱日都有行时才有值；「其余日子」= 覆灭窗里亏钱日之外的日子。
        losing_all = sorted(float(s["losing_ret_pct"]) for s in stats.values() if _num(s.get("losing_ret_pct")) is not None)
        other_all = sorted(float(s["other_ret_pct"]) for s in stats.values() if _num(s.get("other_ret_pct")) is not None)

        def pct_losing(x: float) -> float | None:
            return None if not losing_all else round(100.0 * bisect.bisect_left(losing_all, x) / len(losing_all), 2)

        def pct_other(x: float) -> float | None:
            return None if not other_all else round(100.0 * bisect.bisect_left(other_all, x) / len(other_all), 2)

        new_rows = ranked[nwi][:cohort]
        old_top_l1 = {r.get("sw_l1") for r in top_rows if r.get("sw_l1")}
        old_rank = rank_of[wi]
        new_codes_top = {str(r["stock_ts_code"]) for r in ranked[nwi][:top]}
        new_codes_cohort = {str(r["stock_ts_code"]) for r in new_rows}
        for n, r in enumerate(new_rows, start=1):
            code = str(r["stock_ts_code"])
            s = stats.get(code, {})
            ret = _num(s.get("ret_pct"))
            percentile = None if ret is None else pct(ret)
            losing_ret = _num(s.get("losing_ret_pct"))
            losing_pct = None if losing_ret is None else pct_losing(losing_ret)
            other_ret = _num(s.get("other_ret_pct"))
            other_pct = None if other_ret is None else pct_other(other_ret)
            handoffs_out.append({
                "old_wave_idx": wi, "new_wave_idx": nwi, "new_rank": n, "stock_ts_code": code, "stock_name": r.get("stock_name"),
                "new_wave_gain_pct": _num(r.get("gain_pct")), "sw_l1": r.get("sw_l1"), "form": _form(r.get("max_boards")),
                "old_wave_rank": old_rank.get(code), "in_old_cohort": (old_rank.get(code) is not None and old_rank[code] <= cohort),
                "l1_in_old_top": None if not r.get("sw_l1") else (r.get("sw_l1") in old_top_l1),
                "collapse_ret_pct": ret, "collapse_ret_percentile": percentile, "collapse_max_dd_pct": _num(s.get("max_dd_pct")),
                "first_leg_ret_pct": _num(s.get("first_leg_ret_pct")),
                "new_high_in_collapse": None if s.get("new_high") is None else bool(s["new_high"]),
                "separation_relative": None if percentile is None else (percentile >= threshold_pct),
                "separation_new_high": None if s.get("new_high") is None else bool(s["new_high"]),
                "losing_days_ret_pct": losing_ret, "losing_days_ret_percentile": losing_pct,
                "separation_on_losing_days": None if losing_pct is None else (losing_pct >= threshold_pct),
                "other_days_ret_pct": other_ret, "other_days_ret_percentile": other_pct,
                "separation_on_other_days": None if other_pct is None else (other_pct >= threshold_pct),
            })
        # pooled units for the statistical gate: every stock in this collapse window, ordered by code
        for key, target in ((f"top{top}", new_codes_top), (f"cohort{cohort}", new_codes_cohort)):
            bucket = pooled[key]
            for code in sorted(stats):
                ret = _num(stats[code].get("ret_pct"))
                if ret is None:
                    continue
                bucket["base_n"] += 1
                hit = code in target
                bucket["base_k"] += int(hit)
                if pct(ret) >= threshold_pct:
                    bucket["units"].append(hit)
        handoff_readouts.append(_handoff_readout(
            wi, nwi, w, nw, rows, ranked[nwi], stats, all_ret, med_ret, pct, threshold_pct,
            top=top, cohort=cohort, index_ret=(index_returns or {}).get(wi),
            losing_all=losing_all, pct_losing=pct_losing, money_losing=money_losing.get(wi),
            other_all=other_all, pct_other=pct_other,
        ))

    separation = {
        key: stats_readout(bucket["units"], baseline_n=bucket["base_n"], baseline_k=bucket["base_k"], min_n=min_n).to_dict()
        for key, bucket in pooled.items()
    }
    completed = [h for h in handoff_readouts if h.get("status", "ok") == "ok"]
    return {
        "waves": list(waves), "members": members_out, "handoffs": handoffs_out,
        "readouts": {
            "waves": wave_readouts,
            "handoffs": handoff_readouts,
            "separation_gate": {
                "unit": "one stock in one completed collapse window; condition = collapse-window return percentile ≥ separation_percentile; outcome = member of the next dynasty",
                "cycles": len(completed), "cycle_note": "four-state is on pooled stock-units; with this few cycles the cycle-level split is reported per handoff, not judged",
                **separation,
            },
        },
    }


def _money_losing_readout(counts: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Per wave: how much 亏钱效应 the peak block, the collapse window and the 10 days before it carried."""
    if not counts:
        return None

    def block(key: str) -> dict[str, Any] | None:
        b = counts.get(key)
        if not b:
            return None
        days, flagged = int(b.get("days") or 0), int(b.get("flagged") or 0)
        return {"days": days, "flagged": flagged, "share": round(flagged / days, 4) if days else None}

    dates = [str(d) for d in (counts.get("collapse_days") or [])]
    return {"peak_block": block("peak_block"), "lead_10d": block("lead"), "collapse": block("collapse"),
            "collapse_first_flagged_day": dates[0] if dates else None, "collapse_flagged_days": dates}


def _days_subset_readout(key, old_s, new_s, all_vals, pct_fn, threshold_pct) -> dict[str, Any] | None:
    """Old / new members' compounded return over a subset of the collapse window's days, against all stocks."""
    if not all_vals or pct_fn is None:
        return None
    med = median(all_vals)
    old_v = [float(s[key]) for s in old_s if _num(s.get(key)) is not None]
    new_v = [float(s[key]) for s in new_s if _num(s.get(key)) is not None]
    return {
        "days_ret_pct_all": _quartiles(all_vals),
        "old_ret_pct": _quartiles(old_v), "new_ret_pct": _quartiles(new_v),
        "new_ret_percentile": _quartiles([pct_fn(v) for v in new_v]),
        "new_share_above_median": _share(new_v, lambda v: v > med),
        "new_share_separation": _share(new_v, lambda v: pct_fn(v) >= threshold_pct),
    }


def _handoff_readout(
    wi, nwi, w, nw, old_ranked, new_ranked, stats, all_ret, med_ret, pct, threshold_pct, *, top, cohort, index_ret,
    losing_all=(), pct_losing=None, money_losing=None, other_all=(), pct_other=None,
):
    """One completed handoff, for the founder to read: 亏钱效应、旧王朝的覆灭、新王朝的分离、两者的关系。"""
    n_all = len(all_ret)
    old_rank = {str(r["stock_ts_code"]): n + 1 for n, r in enumerate(old_ranked)}
    losing_all, other_all = list(losing_all), list(other_all)
    out: dict[str, Any] = {
        "handoff": f"W{wi}→W{nwi}", "status": "ok", "old_wave_status": w["status"],
        "old_wave": [str(w["start"]), str(w["peak_end"])], "collapse": [str(w["collapse_start"]), str(w["collapse_end"])],
        "collapse_days": w.get("collapse_days"), "first_down_end": None if w.get("first_down_end") is None else str(w["first_down_end"]),
        "new_wave": [str(nw["start"]), str(nw["peak_end"])], "stages_in_collapse": dict(w.get("stages_in_collapse") or {}),
        "money_losing": {
            "index_ret_pct": None if index_ret is None else round(float(index_ret), 3),
            "median_stock_ret_pct": round(med_ret, 3), "stocks": n_all,
            "share_stocks_positive": round(sum(1 for r in all_ret if r > 0) / n_all, 4),
            "share_new_high_all": _share([s for s in stats.values() if s.get("new_high") is not None], lambda s: bool(s["new_high"])),
            "losing_days": len((money_losing or {}).get("collapse_days") or []),
            "other_days": (money_losing or {}).get("collapse_other_days"),
            "losing_days_ret_pct_all": _quartiles(losing_all),
            "other_days_ret_pct_all": _quartiles(other_all),
            "counts": _money_losing_readout(money_losing),
        },
    }
    decile_codes = [c for c, s in stats.items() if _num(s.get("ret_pct")) is not None and pct(float(s["ret_pct"])) >= threshold_pct]
    for key, size in ((f"top{top}", top), (f"cohort{cohort}", cohort)):
        old_rows, new_rows = old_ranked[:size], new_ranked[:size]
        old_codes = [str(r["stock_ts_code"]) for r in old_rows]
        new_codes = [str(r["stock_ts_code"]) for r in new_rows]
        old_l1 = {str(r["sw_l1"]) for r in old_rows if r.get("sw_l1")}
        new_l1 = {str(r["sw_l1"]) for r in new_rows if r.get("sw_l1")}
        old_s = [stats[c] for c in old_codes if c in stats and _num(stats[c].get("ret_pct")) is not None]
        new_s = [stats[c] for c in new_codes if c in stats and _num(stats[c].get("ret_pct")) is not None]
        new_pcts = [pct(float(s["ret_pct"])) for s in new_s]
        hit = sum(1 for c in decile_codes if c in set(new_codes))
        base_rate = size / n_all if n_all else None
        cond_rate = (hit / len(decile_codes)) if decile_codes else None
        out[key] = {
            "old_in_collapse": {
                "ret_pct": _quartiles([float(s["ret_pct"]) for s in old_s]),
                "max_dd_pct": _quartiles([float(s["max_dd_pct"]) for s in old_s if _num(s.get("max_dd_pct")) is not None]),
                "share_positive": _share(old_s, lambda s: float(s["ret_pct"]) > 0),
                "first_leg_ret_pct": _quartiles([float(s["first_leg_ret_pct"]) for s in old_s if _num(s.get("first_leg_ret_pct")) is not None]),
            },
            "new_in_collapse": {
                "covered": len(new_s), "members": len(new_codes),
                "ret_pct": _quartiles([float(s["ret_pct"]) for s in new_s]),
                "max_dd_pct": _quartiles([float(s["max_dd_pct"]) for s in new_s if _num(s.get("max_dd_pct")) is not None]),
                "ret_percentile": _quartiles(new_pcts),
                "share_positive": _share(new_s, lambda s: float(s["ret_pct"]) > 0),
                "share_above_median": _share(new_s, lambda s: float(s["ret_pct"]) > med_ret),
                "share_separation_relative": _share(new_pcts, lambda p: p >= threshold_pct),
                "share_separation_new_high": _share([s for s in new_s if s.get("new_high") is not None], lambda s: bool(s["new_high"])),
                "first_leg_ret_pct": _quartiles([float(s["first_leg_ret_pct"]) for s in new_s if _num(s.get("first_leg_ret_pct")) is not None]),
            },
            # 第十四段：亏钱日本身上的强弱 与 亏钱日之外的日子，与整窗分离并排——「酝酿走强」发生在哪些日子。
            "on_losing_days": _days_subset_readout("losing_ret_pct", old_s, new_s, losing_all, pct_losing, threshold_pct),
            "on_other_days": _days_subset_readout("other_ret_pct", old_s, new_s, other_all, pct_other, threshold_pct),
            "relation": {
                "new_members_old_wave_rank": _quartiles([old_rank[c] for c in new_codes if c in old_rank]),
                "new_members_from_old_cohort": sum(1 for c in new_codes if old_rank.get(c, 10**9) <= cohort),
                "new_members_l1_in_old_share": _share([r for r in new_rows if r.get("sw_l1")], lambda r: str(r["sw_l1"]) in old_l1),
                "l1_jaccard": round(len(old_l1 & new_l1) / len(old_l1 | new_l1), 4) if (old_l1 or new_l1) else None,
                "l1_old": dict(Counter(str(r["sw_l1"]) for r in old_rows if r.get("sw_l1"))),
                "l1_new": dict(Counter(str(r["sw_l1"]) for r in new_rows if r.get("sw_l1"))),
                "forms_old": dict(Counter(_form(r.get("max_boards")) for r in old_rows)),
                "forms_new": dict(Counter(_form(r.get("max_boards")) for r in new_rows)),
            },
            "lift_separation_relative": {
                "condition_n": len(decile_codes), "became_new_member": hit,
                "rate": None if cond_rate is None else round(cond_rate, 5), "base_rate": None if base_rate is None else round(base_rate, 5),
                "lift": None if not (cond_rate and base_rate) else round(cond_rate / base_rate, 2),
            },
        }
    return out
