"""C 类：板块角色逐日标签、板块级赚钱效应集合与「周均线下方赚钱效应不在成交占比前三」的原料。

Pure and fail-closed, like ``flags.py``: a sector whose window is incomplete or whose
inputs are NULL gets NULL, never an inferred zero.  Everything here is the founder's
vocabulary or the platform's (骨架 §3 / §3.2 / §8.1):

* 量板块 = 「容量占比前三的申万一级里的板块」（07-03 答疑 1）→ the sector's ``sw_l1`` is one of
  the day's ``industry_1..3``;
* 价板块 = 「5 日涨幅靠前但量能不足以进占比前三的板块」, 「靠前」取前 10（第十段）;
* 锐度 = 两个分量：区间涨幅名次（3 / 5 / 10 日，= 板块级短期 RPS）与涨停家数映射（第三、四轮）,
  合成方式待定，两列都出;
* 赚钱效应板块集合 = 「聚类分析……特征可以组合，要联立分析，不一定要直接锁死答案」（第六、七段）→
  several definitions side by side, none of them the answer;
* 双红 = 回测层 ``dual_red_strict`` 的口径（pct > 0 ∧ diff_ratio > 10 ∧ amount > 500）.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping

from intelligence.services.methodology_backtest.labels import DUAL_RED_AMOUNT_GT, DUAL_RED_DIFF_RATIO_GT

RPS_WINDOWS = (3, 5, 10)
PRICE_TOP_N = 10          # 第十段「取前 10」
MONEY_EFFECT_TOP_N = 10

MONEY_EFFECT_DEFINITIONS = ("limit_top10", "dual_red", "rps5_top10", "rank_mean_top10")

SECTOR_LABELS = (
    "rps_3d_rank", "rps_5d_rank", "rps_10d_rank",
    "role_volume_top3", "role_price_top10",
    "limit_up_count", "sharpness_limit_rank",
    "dual_red_strict",
    *(f"money_effect.{d}" for d in MONEY_EFFECT_DEFINITIONS),
)


def _date(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10]) if v is not None else None


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and x not in (float("inf"), float("-inf")) else None


def _rank_desc(values: Mapping[str, float], tiebreak: Mapping[str, float] | None = None) -> dict[str, int]:
    """1 = largest; ties broken by ``tiebreak`` (larger first) then by code, so ranks are deterministic."""
    order = sorted(values, key=lambda c: (-values[c], -(tiebreak or {}).get(c, 0.0), c))
    return {code: i + 1 for i, code in enumerate(order)}


def build_sector_roles(
    sector_rows: Iterable[Mapping[str, Any]],
    heat_rows: Iterable[Mapping[str, Any]],
    market_rows: Iterable[Mapping[str, Any]],
    *,
    calendar: Iterable[Any],
) -> dict[str, Any]:
    """Return ``{"sectors": [per (day, sector) dict], "days": [per-day summary dict]}``.

    ``sector_rows`` are ``fact_sector_daily`` (trade_date, sector_ts_code, sector_name, sw_l1,
    pct_chg, amount, diff_ratio); ``heat_rows`` are ``fact_theme_limit_heat_daily`` final rows
    (trade_date, sector_ts_code, limit_up_count, fd_amount); ``market_rows`` carry
    ``industry_1..3``.  ``calendar`` orders the days and decides window contiguity.
    """
    days = sorted({_date(d) for d in calendar if _date(d) is not None})
    idx = {d: i for i, d in enumerate(days)}
    by_day: dict[date, dict[str, dict[str, Any]]] = {}
    for row in sector_rows:
        d, code = _date(row.get("trade_date")), row.get("sector_ts_code")
        if d is None or code is None or d not in idx:
            continue
        by_day.setdefault(d, {}).setdefault(str(code), dict(row))
    heat_by_day: dict[date, dict[str, dict[str, Any]]] = {}
    for row in heat_rows:
        d, code = _date(row.get("trade_date")), row.get("sector_ts_code")
        if d is None or code is None:
            continue
        heat_by_day.setdefault(d, {}).setdefault(str(code), dict(row))
    top3_by_day: dict[date, set[str] | None] = {}
    for row in market_rows:
        d = _date(row.get("trade_date"))
        names = [row.get(k) for k in ("industry_1", "industry_2", "industry_3")]
        top3_by_day[d] = {str(n) for n in names if n} or None

    sectors_out: list[dict[str, Any]] = []
    days_out: list[dict[str, Any]] = []
    for d in days:
        today = by_day.get(d)
        if not today:
            days_out.append({"trade_date": d, "sectors": 0, "status": "sector_rows_absent"})
            continue
        i = idx[d]
        top3 = top3_by_day.get(d)
        heat = heat_by_day.get(d)  # None → the heat table did not cover the day
        # 区间涨幅名次：每个窗口只对窗口内每日都有行且日历连续的板块排名。
        ranks: dict[int, dict[str, int]] = {}
        for n in RPS_WINDOWS:
            if i < n - 1:
                ranks[n] = {}
                continue
            window_days = days[i - n + 1 : i + 1]
            compounded: dict[str, float] = {}
            for code in today:
                growth = 1.0
                ok = True
                for wd in window_days:
                    row = by_day.get(wd, {}).get(code)
                    pct = _num(row.get("pct_chg")) if row else None
                    if pct is None:
                        ok = False
                        break
                    growth *= 1.0 + pct / 100.0
                if ok:
                    compounded[code] = (growth - 1.0) * 100.0
            ranks[n] = _rank_desc(compounded)
        limit_counts = {code: _num(h.get("limit_up_count")) for code, h in (heat or {}).items()}
        limit_counts = {c: v for c, v in limit_counts.items() if v is not None and v > 0}
        fd = {code: (_num(h.get("fd_amount")) or 0.0) for code, h in (heat or {}).items()}
        limit_rank = _rank_desc(limit_counts, fd) if heat is not None else {}
        amounts = {code: _num(row.get("amount")) for code, row in today.items()}
        amount_rank = _rank_desc({c: v for c, v in amounts.items() if v is not None})

        per_sector: dict[str, dict[str, Any]] = {}
        for code, row in sorted(today.items()):
            sw_l1 = row.get("sw_l1")
            pct, diff, amt = _num(row.get("pct_chg")), _num(row.get("diff_ratio")), _num(row.get("amount"))
            rec: dict[str, Any] = {
                "trade_date": d, "sector_ts_code": code, "sector_name": row.get("sector_name"), "sw_l1": sw_l1,
                "rps_3d_rank": ranks[3].get(code), "rps_5d_rank": ranks[5].get(code), "rps_10d_rank": ranks[10].get(code),
                "role_volume_top3": None if (top3 is None or sw_l1 is None) else (str(sw_l1) in top3),
                "limit_up_count": None if heat is None else int(limit_counts.get(code, 0)),
                "sharpness_limit_rank": limit_rank.get(code) if heat is not None else None,
                "dual_red_strict": None if None in (pct, diff, amt) else (pct > 0 and diff > DUAL_RED_DIFF_RATIO_GT and amt > DUAL_RED_AMOUNT_GT),
            }
            rps5 = rec["rps_5d_rank"]
            if rps5 is None or rec["role_volume_top3"] is None:
                rec["role_price_top10"] = None
            else:
                rec["role_price_top10"] = rps5 <= PRICE_TOP_N and not rec["role_volume_top3"]
            per_sector[code] = rec
        # 赚钱效应板块集合，几套并排：涨停家数前 10 / 严格双红 / 5 日涨幅前 10 / 三个名次均值前 10。
        mean_rank_inputs = {
            code: [r for r in (limit_rank.get(code), ranks[5].get(code), amount_rank.get(code)) if r is not None]
            for code in per_sector
        }
        mean_rank = {code: sum(rs) / len(rs) for code, rs in mean_rank_inputs.items() if len(rs) == 3}
        mean_rank_order = _rank_desc({c: -v for c, v in mean_rank.items()})  # smaller mean rank = stronger
        for code, rec in per_sector.items():
            rec["money_effect.limit_top10"] = None if heat is None else (limit_rank.get(code, 10**6) <= MONEY_EFFECT_TOP_N)
            rec["money_effect.dual_red"] = rec["dual_red_strict"]
            rec["money_effect.rps5_top10"] = None if rec["rps_5d_rank"] is None else rec["rps_5d_rank"] <= MONEY_EFFECT_TOP_N
            rec["money_effect.rank_mean_top10"] = None if code not in mean_rank_order else mean_rank_order[code] <= MONEY_EFFECT_TOP_N
            sectors_out.append(rec)
        summary: dict[str, Any] = {"trade_date": d, "sectors": len(per_sector), "status": "ok", "top3_l1": sorted(top3) if top3 else None, "heat_covered": heat is not None}
        for definition in MONEY_EFFECT_DEFINITIONS:
            members = [rec for rec in per_sector.values() if rec[f"money_effect.{definition}"] is True]
            known = [rec for rec in members if rec["sw_l1"] is not None]
            outside = [rec for rec in known if top3 is not None and str(rec["sw_l1"]) not in top3]
            summary[f"{definition}.size"] = len(members)
            summary[f"{definition}.known_l1"] = len(known)
            summary[f"{definition}.outside_top3_share"] = (len(outside) / len(known)) if (known and top3 is not None) else None
        days_out.append(summary)
    return {"sectors": sectors_out, "days": days_out}


def money_effect_rule_rows(
    day_summaries: Iterable[Mapping[str, Any]],
    market_context: Mapping[str, Mapping[str, Any]],
    *,
    definition: str,
    outside_share_gt: float = 0.5,
) -> dict[str, Any]:
    """Rows for the candidate rule 「周均线下方，赚钱效应往往不在成交占比前三的主流板块」（骨架 §3.2）.

    Condition = the index closed below the weekly MA that day (``tf.above_week_ma == 0``);
    outcome = more than ``outside_share_gt`` of the money-effect set (by ``definition``) sits
    in a 申万一级 outside the day's top three by turnover.  Baseline = above-MA days, same
    outcome.  Days without a known MA side, without a top-three, or with an empty set are
    excluded and counted.  Returns the success lists and exclusion counts; the four-state
    verdict is produced by ``methodology_backtest.stats.readout`` at the call site.
    """
    below: list[bool] = []
    above: list[bool] = []
    excluded = {"no_ma_side": 0, "no_top3_or_empty_set": 0}
    for s in day_summaries:
        if s.get("status") != "ok":
            continue
        ctx = market_context.get(str(s["trade_date"])[:10], {})
        side = ctx.get("above_week_ma")
        share = s.get(f"{definition}.outside_top3_share")
        if side is None:
            excluded["no_ma_side"] += 1
            continue
        if share is None:
            excluded["no_top3_or_empty_set"] += 1
            continue
        outcome = share > outside_share_gt
        (below if float(side) == 0 else above).append(outcome)
    return {"definition": definition, "outside_share_gt": outside_share_gt, "below_ma": below, "above_ma": above, "excluded": excluded}


__all__ = [
    "MONEY_EFFECT_DEFINITIONS", "MONEY_EFFECT_TOP_N", "PRICE_TOP_N", "RPS_WINDOWS", "SECTOR_LABELS",
    "build_sector_roles", "money_effect_rule_rows",
]
