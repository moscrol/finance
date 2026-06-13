import argparse
import csv
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from market_feature_store.db import connect
from market_feature_store.query import _zigzag

DEFAULT_START = "2026-04-08"
DEFAULT_END = "2026-06-05"
DEFAULT_OUTPUT_DIR = Path("research/market-hypothesis")
HIGH_RANK = {"历史新高": 7, "3年新高": 6, "2年新高": 5, "1年新高": 4, "120日新高": 3, "60日新高": 2, "20日新高": 1, "": 0, None: 0}
STRONG_NEXT_PATHS = {"抗住且相对强", "补跌但相对强"}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--top-pct", type=float, default=0.20)
    parser.add_argument("--forward-days", type=int, default=10)
    parser.add_argument("--min-rule-rows", type=int, default=20)
    return parser.parse_args()


def rows_to_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def placeholders(items):
    return ",".join("?" for _ in items)


def round_or_blank(value, digits=2):
    return "" if value is None or value == "" else round(value, digits)


def safe_float(value):
    if value is None or value == "":
        return None
    return float(value)


def median(values):
    values = [v for v in values if v is not None and v != ""]
    return round(st.median(values), 2) if values else ""


def mean(values):
    values = [v for v in values if v is not None and v != ""]
    return round(st.mean(values), 2) if values else ""


def pct(num, den):
    return round(num / den * 100, 2) if den else ""


def current_ma5_context(series, idx, window=60, swing_delta=700):
    recent = series[max(0, idx - window + 1): idx + 1]
    if not recent:
        return {}
    current = recent[-1]
    previous = series[idx - 1] if idx > 0 else None
    current_ma5 = float(current["ma5"])
    recent8 = recent[-8:]
    signs = []
    for left, right in zip(recent8, recent8[1:]):
        day_delta = float(right["ma5"]) - float(left["ma5"])
        if abs(day_delta) < 80:
            signs.append(0)
        elif day_delta > 0:
            signs.append(1)
        else:
            signs.append(-1)
    non_zero = [s for s in signs if s]
    sign_changes = sum(1 for a, b in zip(non_zero, non_zero[1:]) if a != b)
    recent_range = max(float(x["ma5"]) for x in recent8) - min(float(x["ma5"]) for x in recent8) if recent8 else 0
    is_shock = len(recent8) >= 6 and (sign_changes >= 3 or recent_range < swing_delta)
    pivots = []
    for pivot_idx, kind in _zigzag([float(x["ma5"]) for x in recent], swing_delta):
        row = recent[pivot_idx]
        if row["date"] == current["date"] and is_shock:
            continue
        pivots.append({**row, "kind": "波峰" if kind == "峰" else "波谷"})
    all_ma5 = [float(x["ma5"]) for x in recent]
    peak_ma5 = max(all_ma5)
    trough_ma5 = min(all_ma5)
    amplitude = peak_ma5 - trough_ma5
    if is_shock:
        position = "震荡区间"
    elif amplitude <= 1e-9:
        position = "窄幅震荡区"
    elif current_ma5 >= peak_ma5 * 0.85:
        position = "高位区"
    elif current_ma5 <= trough_ma5 + amplitude * 0.25:
        position = "低位区"
    else:
        position = "中位区"
    if is_shock:
        trend = "震荡"
    elif previous is None:
        trend = "缺少昨日可比数据"
    else:
        prev_ma5 = float(previous["ma5"])
        if abs(current_ma5 - prev_ma5) <= 1e-9:
            trend = "震荡"
        elif current_ma5 > prev_ma5:
            trend = "上升"
        else:
            trend = "下降"
    if is_shock and recent8:
        start = recent8[0]
        interval_type = "当前震荡区间"
        interval_delta = current_ma5 - float(start["ma5"])
    elif pivots:
        start = pivots[-1]
        interval_type = f"{start['kind']}→当前"
        interval_delta = current_ma5 - float(start["ma5"])
    else:
        start = recent8[0] if recent8 else current
        interval_type = "当前区间"
        interval_delta = current_ma5 - float(start["ma5"])
    favorable = trend == "上升" or (position in {"低位区", "中位区"} and interval_delta > 0)
    risk = (position == "高位区" and trend == "下降") or (interval_type.startswith("波峰") and interval_delta < 0)
    return {
        "ma5_value": round(current_ma5, 2),
        "ma5_position": position,
        "ma5_trend": trend,
        "ma5_interval_type": interval_type,
        "ma5_interval_delta": round(interval_delta, 2),
        "ma5_favorable": favorable,
        "ma5_risk": risk,
    }


def build_ma5_contexts(con, end_date):
    rows = con.execute(
        """
        SELECT cast(trade_date AS varchar), advancers
        FROM fact_market_daily
        WHERE trade_date <= ? AND advancers IS NOT NULL
        ORDER BY trade_date
        """,
        [end_date],
    ).fetchall()
    series = []
    for idx, (day, advancers) in enumerate(rows):
        window = [r[1] for r in rows[max(0, idx - 4): idx + 1]]
        series.append({"date": str(day), "advancers": advancers, "ma5": round(sum(window) / len(window), 2)})
    return {row["date"]: current_ma5_context(series, idx) for idx, row in enumerate(series)}


def classify_lifecycle(index, prev_gap):
    if index == 1:
        return "d1新启动"
    if index == 2:
        return "d2二次回流"
    if index == 3:
        return "d3三次确认"
    if prev_gap is not None and prev_gap >= 8:
        return "久违回流/成熟重启"
    return "多次回流成熟段"


def lifecycle_family(stages):
    joined = "、".join(stages)
    if "d1新启动" in joined:
        return "d1"
    if "d2二次回流" in joined:
        return "d2"
    if "d3三次确认" in joined:
        return "d3"
    if "久违回流/成熟重启" in joined:
        return "mature_restart"
    if "多次回流成熟段" in joined:
        return "mature_reflow"
    return "unknown"


def next_day_path(stock_pct, sw_pct):
    if stock_pct is None or sw_pct is None:
        return "unknown", None, False
    rel = stock_pct - sw_pct
    if stock_pct >= 0 and stock_pct >= sw_pct:
        return "抗住且相对强", rel, True
    if stock_pct < 0 and stock_pct >= sw_pct:
        return "补跌但相对强", rel, True
    if stock_pct >= 0 and stock_pct < sw_pct:
        return "上涨但弱于行业", rel, False
    return "补跌且弱于行业", rel, False


def load_data(args):
    con = connect(read_only=True)
    try:
        dates = [str(r[0]) for r in con.execute(
            """
            SELECT trade_date
            FROM fact_market_daily
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            [args.start_date, args.end_date],
        ).fetchall()]
        if not dates:
            raise RuntimeError("指定区间没有交易日")
        market_rows = rows_to_dicts(con.execute(
            """
            SELECT cast(trade_date AS varchar) trade_date, industry_1, industry_2, industry_3,
                   advancers, limit_up, limit_down, total_amount
            FROM fact_market_daily
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            [args.start_date, args.end_date],
        ))
        dr_events = rows_to_dicts(con.execute(
            """
            SELECT cast(trade_date AS varchar) trade_date, sector_ts_code, sector_name, sw_l1,
                   pct_chg, diff_ratio, amount
            FROM fact_sector_daily
            WHERE trade_date BETWEEN ? AND ?
              AND pct_chg > 0 AND diff_ratio > 10 AND amount > 500
            ORDER BY sector_ts_code, trade_date
            """,
            [args.start_date, args.end_date],
        ))
        stock_rows = rows_to_dicts(con.execute(
            """
            SELECT cast(trade_date AS varchar) trade_date, stock_ts_code, stock_name, sw_l1, sw_industry,
                   sector_ts_code, sector_name, pct_chg, amount, high_status_label,
                   pct_chg_10d, pct_chg_20d, limit_times, float_mcap_yi
            FROM fact_sector_stock_daily
            WHERE trade_date BETWEEN ? AND ?
              AND pct_chg IS NOT NULL AND amount IS NOT NULL
            """,
            [args.start_date, args.end_date],
        ))
        stock_codes = sorted({r["stock_ts_code"] for r in stock_rows})
        stock_ph = placeholders(stock_codes) if stock_codes else "''"
        price_rows = rows_to_dicts(con.execute(
            f"""
            SELECT cast(trade_date AS varchar) trade_date, stock_ts_code, stock_name, close, pct_chg, amount
            FROM fact_stock_daily
            WHERE trade_date BETWEEN ? AND ?
              AND stock_ts_code IN ({stock_ph})
            """,
            [args.start_date, args.end_date] + stock_codes,
        )) if stock_codes else []
        sw_rows = rows_to_dicts(con.execute(
            """
            SELECT cast(trade_date AS varchar) trade_date, sw_l1, pct_chg
            FROM fact_sw_l1_daily
            WHERE trade_date BETWEEN ? AND ?
            """,
            [args.start_date, args.end_date],
        ))
        limit_theme_rows = rows_to_dicts(con.execute(
            """
            SELECT cast(trade_date AS varchar) trade_date, sector_ts_code, sector_name, sw_l1,
                   COUNT(DISTINCT stock_ts_code) AS limit_count
            FROM fact_theme_limit_stock_daily
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY 1,2,3,4
            """,
            [args.start_date, args.end_date],
        ))
        limit_stock_rows = rows_to_dicts(con.execute(
            """
            SELECT DISTINCT cast(trade_date AS varchar) trade_date, stock_ts_code
            FROM fact_theme_limit_stock_daily
            WHERE trade_date BETWEEN ? AND ?
            """,
            [args.start_date, args.end_date],
        ))
        ma5_contexts = build_ma5_contexts(con, args.end_date)
    finally:
        con.close()
    return {
        "dates": dates,
        "market_rows": market_rows,
        "dr_events": dr_events,
        "stock_rows": stock_rows,
        "price_rows": price_rows,
        "sw_rows": sw_rows,
        "limit_theme_rows": limit_theme_rows,
        "limit_stock_rows": limit_stock_rows,
        "ma5_contexts": ma5_contexts,
    }


def build_limit_maps(limit_theme_rows, limit_stock_rows):
    theme_count = {}
    sw_count = Counter()
    sw_sector_counts = defaultdict(list)
    stock_hit = {(r["trade_date"], r["stock_ts_code"]) for r in limit_stock_rows}
    for row in limit_theme_rows:
        key = (row["trade_date"], row["sector_ts_code"])
        count = int(row["limit_count"] or 0)
        theme_count[key] = count
        sw_key = (row["trade_date"], row.get("sw_l1") or "")
        sw_count[sw_key] += count
        sw_sector_counts[sw_key].append((row["sector_ts_code"], count))
    rank = {}
    for sw_key, items in sw_sector_counts.items():
        items = sorted(items, key=lambda x: (-x[1], x[0]))
        for idx, (sector_code, _count) in enumerate(items, start=1):
            rank[(sw_key[0], sw_key[1], sector_code)] = idx
    return theme_count, sw_count, rank, stock_hit


def build_lifecycle(dr_events, date_pos):
    by_sector = defaultdict(list)
    for row in dr_events:
        by_sector[row["sector_ts_code"]].append(row)
    lifecycle = {}
    dr_event_keys = set()
    sector_reflow_dates = {}
    for sector_code, rows in by_sector.items():
        rows = sorted(rows, key=lambda r: date_pos[r["trade_date"]])
        sector_reflow_dates[sector_code] = [row["trade_date"] for row in rows]
        for idx, row in enumerate(rows):
            prev_gap = None
            if idx > 0:
                prev_gap = date_pos[row["trade_date"]] - date_pos[rows[idx - 1]["trade_date"]]
            lifecycle[(row["trade_date"], sector_code)] = {
                "lifecycle_index": idx + 1,
                "lifecycle_stage": classify_lifecycle(idx + 1, prev_gap),
                "prev_double_red_gap": prev_gap,
            }
            dr_event_keys.add((row["trade_date"], sector_code))
    return lifecycle, dr_event_keys, sector_reflow_dates


def build_rank_maps(stock_rows, dr_event_keys):
    by_day_sector = defaultdict(list)
    for row in stock_rows:
        weighted = (row["pct_chg"] or 0) * math.sqrt(row["amount"] or 0)
        row["weighted"] = weighted
        by_day_sector[(row["trade_date"], row["sector_ts_code"])].append(row)
    rank_info = {}
    prior_top_hit_days = defaultdict(list)
    amount_rank_info = {}
    for key, rows in by_day_sector.items():
        ranked = sorted(rows, key=lambda r: (-(r.get("weighted") or 0), r["stock_ts_code"]))
        topn = max(1, math.ceil(len(ranked) * 0.2))
        for idx, row in enumerate(ranked, start=1):
            info = {"rank": idx, "count": len(ranked), "topn": topn, "top20": idx <= topn}
            rank_info[(key[0], key[1], row["stock_ts_code"])] = info
            if key in dr_event_keys and idx <= topn:
                prior_top_hit_days[(row["stock_ts_code"], key[1])].append(key[0])
        amount_ranked = sorted(rows, key=lambda r: (-(r.get("amount") or 0), r["stock_ts_code"]))
        for idx, row in enumerate(amount_ranked, start=1):
            amount_rank_info[(key[0], key[1], row["stock_ts_code"])] = idx
    return rank_info, amount_rank_info, prior_top_hit_days


def classify_stock_identity(item):
    high_rank = HIGH_RANK.get(item.get("high_event"), 0)
    prior_hits = int(item.get("prior_top20_hits", 0) or 0)
    pct20 = safe_float(item.get("pct_chg_20d_event"))
    amount = safe_float(item.get("amount_event")) or 0
    min_weight_rank = int(item.get("min_weight_rank_in_sector", 999) or 999)
    min_amount_rank = int(item.get("min_amount_rank_in_sector", 999) or 999)
    if item.get("cross_sw_mapping"):
        return "旁支映射"
    if prior_hits == 0 and high_rank <= 2 and (pct20 is None or pct20 < 20):
        return "低位补涨"
    if amount >= 50 or min_amount_rank <= 3:
        if high_rank >= 3 or prior_hits >= 1:
            return "容量趋势核心"
    if item.get("limit_stock_hit") or min_weight_rank <= 2 or high_rank >= 6:
        return "阶段核心"
    if prior_hits >= 2:
        return "多阶段核心"
    return "弹性跟随"


def path_stats(prices, dates, date_pos, code, entry_date, forward_days):
    start = prices.get((code, entry_date), {}).get("close")
    if not start or entry_date not in date_pos:
        return {}
    start_idx = date_pos[entry_date]
    path = []
    for offset in range(0, forward_days + 1):
        idx = start_idx + offset
        if idx >= len(dates):
            break
        day = dates[idx]
        close = prices.get((code, day), {}).get("close")
        if close:
            path.append((offset, day, (close / start - 1) * 100, close))
    if not path:
        return {}
    by_offset = {offset: ret for offset, _day, ret, _close in path}
    available_days = max(offset for offset, *_rest in path)
    future = [p for p in path if p[0] > 0]
    if not future:
        return {"forward_available_days": available_days}
    trough = min(future, key=lambda x: x[2])
    peak = max(future, key=lambda x: x[2])
    max_dd = 0.0
    rolling_peak_close = start
    rolling_peak_offset = 0
    rolling_peak_day = entry_date
    dd_anchor = (0, entry_date)
    for offset, day, _ret, close in path:
        if close > rolling_peak_close:
            rolling_peak_close = close
            rolling_peak_offset = offset
            rolling_peak_day = day
        dd = (close / rolling_peak_close - 1) * 100
        if dd < max_dd:
            max_dd = dd
            dd_anchor = (rolling_peak_offset, rolling_peak_day)
    final_offset, final_day, final_ret, _final_close = path[-1]
    if trough[2] <= -5 and peak[2] >= 5 and trough[0] < peak[0]:
        label = "先亏后涨"
    elif trough[2] <= -5 and peak[2] >= 5 and peak[0] < trough[0]:
        label = "先涨后跌"
    elif peak[2] < 3 and trough[2] <= -5:
        label = "一路走弱"
    elif trough[2] > -3 and peak[2] >= 5:
        label = "直接走强"
    elif trough[2] <= -5:
        label = "震荡下探"
    else:
        label = "窄幅震荡"
    return {
        "forward_available_days": available_days,
        "ret_3d": by_offset.get(3),
        "ret_5d": by_offset.get(5),
        "ret_7d": by_offset.get(7),
        "ret_10d": by_offset.get(10),
        "peak_ret_10d": peak[2],
        "peak_day_10d": peak[0],
        "peak_date_10d": peak[1],
        "mae_10d": trough[2],
        "mae_day_10d": trough[0],
        "mae_date_10d": trough[1],
        "max_drawdown_10d": max_dd,
        "drawdown_anchor_day_10d": dd_anchor[0],
        "drawdown_anchor_date_10d": dd_anchor[1],
        "final_day": final_offset,
        "final_date": final_day,
        "final_ret": final_ret,
        "path_label": label,
    }


def reflow_exit_stats(prices, dates, date_pos, sector_reflow_dates, sector_info, code, entry_date, sector_codes):
    start = prices.get((code, entry_date), {}).get("close")
    if not start or entry_date not in date_pos:
        return {"reflow_exit_available": False, "reflow_exit_status": "missing_entry_price"}
    entry_idx = date_pos[entry_date]
    candidates = []
    for sector_code in sector_codes:
        for day in sector_reflow_dates.get(sector_code, []):
            if day in date_pos and date_pos[day] > entry_idx:
                candidates.append((date_pos[day] - entry_idx, day, sector_code))
                break
    if not candidates:
        return {"reflow_exit_available": False, "reflow_exit_status": "no_reflow_after_entry"}
    gap, exit_date, sector_code = sorted(candidates, key=lambda x: (x[0], x[2]))[0]
    exit_close = prices.get((code, exit_date), {}).get("close")
    sector_name = sector_info.get(sector_code, {}).get("sector_name", "")
    if not exit_close:
        return {
            "reflow_exit_available": False,
            "reflow_exit_status": "missing_exit_price",
            "reflow_exit_date": exit_date,
            "reflow_exit_sector": sector_name,
            "reflow_exit_gap_days": gap,
        }
    path = []
    for idx in range(entry_idx, date_pos[exit_date] + 1):
        day = dates[idx]
        close = prices.get((code, day), {}).get("close")
        if close:
            path.append((idx - entry_idx, day, (close / start - 1) * 100, close))
    future = [p for p in path if p[0] > 0]
    if not future:
        return {
            "reflow_exit_available": False,
            "reflow_exit_status": "missing_path_price",
            "reflow_exit_date": exit_date,
            "reflow_exit_sector": sector_name,
            "reflow_exit_gap_days": gap,
        }
    trough = min(future, key=lambda x: x[2])
    peak = max(future, key=lambda x: x[2])
    return {
        "reflow_exit_available": True,
        "reflow_exit_status": "ok",
        "reflow_exit_date": exit_date,
        "reflow_exit_sector": sector_name,
        "reflow_exit_gap_days": gap,
        "reflow_exit_ret": (exit_close / start - 1) * 100,
        "reflow_exit_mae": trough[2],
        "reflow_exit_peak_ret": peak[2],
    }


def build_event_candidates(args, data):
    dates = data["dates"]
    date_pos = {d: i for i, d in enumerate(dates)}
    market_top = {}
    market_names = {}
    for row in data["market_rows"]:
        inds = [x.strip() for x in [row.get("industry_1"), row.get("industry_2"), row.get("industry_3")] if x]
        market_top[row["trade_date"]] = set(inds)
        market_names[row["trade_date"]] = inds
    dr_by_day = defaultdict(dict)
    for row in data["dr_events"]:
        dr_by_day[row["trade_date"]][row["sector_ts_code"]] = row
    stocks_by_day = defaultdict(list)
    for row in data["stock_rows"]:
        stocks_by_day[row["trade_date"]].append(row)
    prices = {(r["stock_ts_code"], r["trade_date"]): r for r in data["price_rows"]}
    sw_pct = {(r["sw_l1"], r["trade_date"]): r["pct_chg"] for r in data["sw_rows"]}
    theme_count, sw_count, theme_rank, stock_hit = build_limit_maps(data["limit_theme_rows"], data["limit_stock_rows"])
    lifecycle, dr_event_keys, sector_reflow_dates = build_lifecycle(data["dr_events"], date_pos)
    rank_info, amount_rank_info, prior_top_hit_days = build_rank_maps(data["stock_rows"], dr_event_keys)
    sector_info = {}
    for row in data["dr_events"]:
        sector_info[row["sector_ts_code"]] = {
            "sector_name": row.get("sector_name") or "",
            "sw_l1": row.get("sw_l1") or "",
        }
    candidates = []
    for day in dates:
        top = market_top.get(day, set())
        if not top:
            continue
        dr = {code: event for code, event in dr_by_day.get(day, {}).items() if (event.get("sw_l1") or "").strip() in top}
        if not dr:
            continue
        pool = {}
        for row in stocks_by_day.get(day, []):
            sector_code = row["sector_ts_code"]
            if sector_code not in dr:
                continue
            main = ((row.get("sw_industry") or "").split("-")[0] or row.get("sw_l1") or "").strip()
            if main not in top:
                continue
            weighted = (row["pct_chg"] or 0) * math.sqrt(row["amount"] or 0)
            item = pool.setdefault(row["stock_ts_code"], {
                "event_date": day,
                "stock_ts_code": row["stock_ts_code"],
                "stock_name": row["stock_name"],
                "sw_l1": main,
                "pct_event": row["pct_chg"],
                "amount_event": row["amount"],
                "weighted_event": weighted,
                "high_event": row.get("high_status_label") or "",
                "pct_chg_10d_event": row.get("pct_chg_10d"),
                "pct_chg_20d_event": row.get("pct_chg_20d"),
                "limit_times_event": row.get("limit_times") or 0,
                "float_mcap_yi": row.get("float_mcap_yi"),
                "sector_codes": set(),
                "sector_names": set(),
                "sector_sws": set(),
            })
            if weighted > item["weighted_event"]:
                item.update({
                    "pct_event": row["pct_chg"],
                    "amount_event": row["amount"],
                    "weighted_event": weighted,
                    "high_event": row.get("high_status_label") or "",
                    "pct_chg_10d_event": row.get("pct_chg_10d"),
                    "pct_chg_20d_event": row.get("pct_chg_20d"),
                    "limit_times_event": row.get("limit_times") or 0,
                    "float_mcap_yi": row.get("float_mcap_yi"),
                })
            item["sector_codes"].add(sector_code)
            item["sector_names"].add(row["sector_name"])
            item["sector_sws"].add(dr[sector_code].get("sw_l1") or "")
        if not pool:
            continue
        weights = sorted([x["weighted_event"] for x in pool.values()], reverse=True)
        weight_cut = weights[max(1, math.ceil(len(weights) * args.top_pct)) - 1]
        next_day = dates[date_pos[day] + 1] if date_pos[day] + 1 < len(dates) else ""
        for item in pool.values():
            weighted_top = item["weighted_event"] >= weight_cut
            high_or_dr3 = bool(item["high_event"]) or len(item["sector_codes"]) >= 3
            if not (weighted_top and high_or_dr3):
                continue
            next_stock_pct = prices.get((item["stock_ts_code"], next_day), {}).get("pct_chg") if next_day else None
            next_sw_pct = sw_pct.get((item["sw_l1"], next_day)) if next_day else None
            path, rel, rel_strong = next_day_path(next_stock_pct, next_sw_pct)
            sector_counts = [theme_count.get((day, code), 0) for code in item["sector_codes"]]
            sector_ranks = [theme_rank.get((day, item["sw_l1"], code)) for code in item["sector_codes"] if theme_rank.get((day, item["sw_l1"], code))]
            lifecycle_items = [lifecycle.get((day, code), {}) for code in item["sector_codes"]]
            lifecycle_stages = sorted({x.get("lifecycle_stage", "") for x in lifecycle_items if x.get("lifecycle_stage")})
            lifecycle_indexes = [x.get("lifecycle_index") for x in lifecycle_items if x.get("lifecycle_index")]
            weight_ranks = []
            amount_ranks = []
            prior_hits = 0
            for code in item["sector_codes"]:
                info = rank_info.get((day, code, item["stock_ts_code"]), {})
                if info.get("rank"):
                    weight_ranks.append(info["rank"])
                amount_rank = amount_rank_info.get((day, code, item["stock_ts_code"]), None)
                if amount_rank:
                    amount_ranks.append(amount_rank)
                prior_hits += sum(1 for hit_day in prior_top_hit_days.get((item["stock_ts_code"], code), []) if date_pos[hit_day] < date_pos[day])
            max_limit_count = max(sector_counts) if sector_counts else 0
            limit_stock_hit = (day, item["stock_ts_code"]) in stock_hit
            limit_strong = max_limit_count >= 2 or limit_stock_hit
            limit_medium = max_limit_count == 1 and not limit_stock_hit
            limit_tag = "limit_strong" if limit_strong else "limit_medium" if limit_medium else "limit_weak"
            ma5 = data["ma5_contexts"].get(day, {})
            cross_sw_mapping = bool(item["sector_sws"]) and item["sw_l1"] not in item["sector_sws"]
            candidate = {
                "event_date": day,
                "next_day": next_day,
                "stock_ts_code": item["stock_ts_code"],
                "stock_name": item["stock_name"],
                "sw_l1": item["sw_l1"],
                "top3_industries": "/".join(market_names.get(day, [])),
                "pct_event": round(item["pct_event"], 2),
                "amount_event": round(item["amount_event"], 2),
                "weighted_event": round(item["weighted_event"], 2),
                "weight_cut": round(weight_cut, 2),
                "high_event": item["high_event"],
                "pct_chg_10d_event": round_or_blank(item.get("pct_chg_10d_event")),
                "pct_chg_20d_event": round_or_blank(item.get("pct_chg_20d_event")),
                "limit_times_event": item.get("limit_times_event") or 0,
                "float_mcap_yi": round_or_blank(item.get("float_mcap_yi"), 1),
                "double_red_hits": len(item["sector_codes"]),
                "event_sector_codes": "、".join(sorted(item["sector_codes"])),
                "event_sectors": "、".join(sorted(item["sector_names"])),
                "sector_sws": "、".join(sorted(item["sector_sws"])),
                "cross_sw_mapping": cross_sw_mapping,
                "lifecycle_stages": "、".join(lifecycle_stages),
                "lifecycle_family": lifecycle_family(lifecycle_stages),
                "max_lifecycle_index": max(lifecycle_indexes) if lifecycle_indexes else "",
                "prior_top20_hits": prior_hits,
                "min_weight_rank_in_sector": min(weight_ranks) if weight_ranks else "",
                "min_amount_rank_in_sector": min(amount_ranks) if amount_ranks else "",
                "next_day_path": path,
                "next_day_rel_pct": round_or_blank(rel),
                "next_day_confirmed": rel_strong,
                "limit_theme_hit": max_limit_count > 0,
                "limit_theme_count_max": max_limit_count,
                "limit_theme_count_sum": sum(sector_counts),
                "limit_stock_hit": limit_stock_hit,
                "limit_sw_count": sw_count.get((day, item["sw_l1"]), 0),
                "limit_theme_rank_in_sw": min(sector_ranks) if sector_ranks else "",
                "limit_tag": limit_tag,
                "ma5_value": ma5.get("ma5_value", ""),
                "ma5_position": ma5.get("ma5_position", ""),
                "ma5_trend": ma5.get("ma5_trend", ""),
                "ma5_interval_type": ma5.get("ma5_interval_type", ""),
                "ma5_interval_delta": ma5.get("ma5_interval_delta", ""),
                "ma5_favorable": ma5.get("ma5_favorable", False),
                "ma5_risk": ma5.get("ma5_risk", False),
            }
            candidate["stock_identity"] = classify_stock_identity(candidate)
            candidates.append(candidate)
    candidates.sort(key=lambda r: (r["event_date"], -float(r["weighted_event"])))
    return candidates, prices, sector_reflow_dates, sector_info


def build_risk_detail(args, candidates, data, prices, sector_reflow_dates, sector_info):
    dates = data["dates"]
    date_pos = {d: i for i, d in enumerate(dates)}
    rows = []
    for candidate in candidates:
        entry_modes = [("双红当日收盘买", candidate["event_date"], "未等承接")]
        if candidate.get("next_day") and candidate.get("next_day_confirmed"):
            entry_modes.append(("次日承接后买", candidate["next_day"], candidate.get("next_day_path") or ""))
        for entry_mode, entry_date, entry_filter in entry_modes:
            stats = path_stats(prices, dates, date_pos, candidate["stock_ts_code"], entry_date, args.forward_days)
            sector_codes = [x for x in str(candidate.get("event_sector_codes") or "").split("、") if x]
            reflow_stats = reflow_exit_stats(prices, dates, date_pos, sector_reflow_dates, sector_info, candidate["stock_ts_code"], entry_date, sector_codes)
            row = dict(candidate)
            row["entry_mode"] = entry_mode
            row["entry_date"] = entry_date
            row["entry_filter"] = entry_filter
            row["full_forward_window"] = bool(stats.get("forward_available_days", 0) >= args.forward_days)
            for key in [
                "forward_available_days", "ret_3d", "ret_5d", "ret_7d", "ret_10d",
                "peak_ret_10d", "peak_day_10d", "peak_date_10d", "mae_10d", "mae_day_10d",
                "mae_date_10d", "max_drawdown_10d", "drawdown_anchor_day_10d", "drawdown_anchor_date_10d",
                "final_day", "final_date", "final_ret", "path_label",
            ]:
                value = stats.get(key, "")
                row[key] = round_or_blank(value) if isinstance(value, float) else value
            for key in [
                "reflow_exit_available", "reflow_exit_status", "reflow_exit_date", "reflow_exit_sector",
                "reflow_exit_gap_days", "reflow_exit_ret", "reflow_exit_mae", "reflow_exit_peak_ret",
            ]:
                value = reflow_stats.get(key, "")
                row[key] = round_or_blank(value) if isinstance(value, float) else value
            mae = safe_float(row.get("mae_10d"))
            row["mae_le_-5"] = mae is not None and mae <= -5
            row["mae_le_-8"] = mae is not None and mae <= -8
            row["mae_le_-10"] = mae is not None and mae <= -10
            peak = safe_float(row.get("peak_ret_10d"))
            row["peak_ge_5"] = peak is not None and peak >= 5
            row["peak_ge_10"] = peak is not None and peak >= 10
            rows.append(row)
    rows.sort(key=lambda r: (r["entry_mode"], r["event_date"], -float(r["weighted_event"])))
    return rows


def summarize_group(entry_mode, group_dim, group_value, rows):
    full = [r for r in rows if r.get("full_forward_window") and r.get("mae_10d") not in ("", None)]
    mae = [safe_float(r.get("mae_10d")) for r in full]
    peak = [safe_float(r.get("peak_ret_10d")) for r in full]
    ret5 = [safe_float(r.get("ret_5d")) for r in full]
    ret10 = [safe_float(r.get("ret_10d")) for r in full]
    dd = [safe_float(r.get("max_drawdown_10d")) for r in full]
    reflow_full = [r for r in rows if r.get("reflow_exit_available") and r.get("reflow_exit_ret") not in ("", None)]
    reflow_ret = [safe_float(r.get("reflow_exit_ret")) for r in reflow_full]
    reflow_mae = [safe_float(r.get("reflow_exit_mae")) for r in reflow_full]
    reflow_peak = [safe_float(r.get("reflow_exit_peak_ret")) for r in reflow_full]
    med_mae = median(mae)
    med_peak = median(peak)
    if med_mae != "" and med_peak != "" and med_mae < 0:
        reward_risk = round(med_peak / abs(med_mae), 2)
    else:
        reward_risk = ""
    return {
        "entry_mode": entry_mode,
        "group_dim": group_dim,
        "group": group_value,
        "rows": len(rows),
        "full_rows": len(full),
        "unique_stocks": len({r["stock_ts_code"] for r in rows}),
        "median_mae_10d": med_mae,
        "mean_mae_10d": mean(mae),
        "mae_le_-5_pct": pct(sum(1 for r in full if r.get("mae_le_-5")), len(full)),
        "mae_le_-8_pct": pct(sum(1 for r in full if r.get("mae_le_-8")), len(full)),
        "mae_le_-10_pct": pct(sum(1 for r in full if r.get("mae_le_-10")), len(full)),
        "median_peak_ret_10d": med_peak,
        "median_ret_5d": median(ret5),
        "median_ret_10d": median(ret10),
        "median_max_drawdown_10d": median(dd),
        "reward_risk_median": reward_risk,
        "reflow_exit_rows": len(reflow_full),
        "reflow_exit_available_pct": pct(len(reflow_full), len(rows)),
        "median_reflow_exit_ret": median(reflow_ret),
        "reflow_exit_win_pct": pct(sum(1 for x in reflow_ret if x is not None and x > 0), len(reflow_ret)),
        "median_reflow_exit_mae": median(reflow_mae),
        "median_reflow_exit_peak_ret": median(reflow_peak),
    }


def build_group_summary(detail):
    rows = []
    entry_modes = sorted({r["entry_mode"] for r in detail})
    group_defs = [
        ("all", lambda r: "all"),
        ("lifecycle_family", lambda r: r.get("lifecycle_family") or "unknown"),
        ("lifecycle_stages", lambda r: r.get("lifecycle_stages") or "unknown"),
        ("stock_identity", lambda r: r.get("stock_identity") or "unknown"),
        ("ma5_risk", lambda r: "ma5_risk" if r.get("ma5_risk") else "not_ma5_risk"),
        ("ma5_favorable", lambda r: "ma5_favorable" if r.get("ma5_favorable") else "not_ma5_favorable"),
        ("ma5_position_trend", lambda r: f"{r.get('ma5_position')}/{r.get('ma5_trend')}"),
        ("limit_tag", lambda r: r.get("limit_tag") or "unknown"),
        ("next_day_path", lambda r: r.get("next_day_path") or "unknown"),
        ("path_label", lambda r: r.get("path_label") or "unknown"),
        ("lifecycle+ma5_risk+limit", lambda r: f"{r.get('lifecycle_family')}|{'ma5_risk' if r.get('ma5_risk') else 'not_ma5_risk'}|{r.get('limit_tag')}"),
        ("lifecycle+identity", lambda r: f"{r.get('lifecycle_family')}|{r.get('stock_identity')}"),
        ("ma5_risk+limit", lambda r: f"{'ma5_risk' if r.get('ma5_risk') else 'not_ma5_risk'}|{r.get('limit_tag')}"),
        ("identity+limit", lambda r: f"{r.get('stock_identity')}|{r.get('limit_tag')}"),
    ]
    for entry_mode in entry_modes:
        mode_rows = [r for r in detail if r["entry_mode"] == entry_mode]
        for group_dim, getter in group_defs:
            buckets = defaultdict(list)
            for row in mode_rows:
                buckets[getter(row)].append(row)
            for group, group_rows in buckets.items():
                rows.append(summarize_group(entry_mode, group_dim, group, group_rows))
    rows.sort(key=lambda r: (r["entry_mode"], r["group_dim"], str(r["group"])))
    return rows


def risk_score(row):
    full_rows = int(row.get("full_rows") or 0)
    if not full_rows:
        return -999
    mae8 = safe_float(row.get("mae_le_-8_pct")) or 0
    mae10 = safe_float(row.get("mae_le_-10_pct")) or 0
    med_mae = safe_float(row.get("median_mae_10d")) or 0
    reward_risk = safe_float(row.get("reward_risk_median"))
    penalty = 0 if reward_risk in (None, "") else max(0, 1 - reward_risk) * 10
    return mae8 * 1.3 + mae10 * 1.8 + abs(min(0, med_mae)) * 4 + penalty


def build_rule_candidates(args, summary):
    rows = []
    non_actionable_dims = {"path_label", "lifecycle_stages", "next_day_path"}
    for row in summary:
        if row.get("group_dim") in non_actionable_dims:
            continue
        full_rows = int(row.get("full_rows") or 0)
        if full_rows < args.min_rule_rows:
            continue
        med_mae = safe_float(row.get("median_mae_10d"))
        mae8 = safe_float(row.get("mae_le_-8_pct")) or 0
        mae10 = safe_float(row.get("mae_le_-10_pct")) or 0
        reward_risk = safe_float(row.get("reward_risk_median"))
        if med_mae is None:
            continue
        if med_mae <= -5 or mae8 >= 30 or mae10 >= 15:
            if med_mae <= -8 or mae10 >= 30:
                level = "高风险提示候选"
            elif med_mae <= -5 or mae8 >= 30:
                level = "高回撤观察候选"
            else:
                level = "边际风险候选"
            suggestion = "输出个股并标注高风险因素" if level == "高风险提示候选" else "输出观察并标注等待承接"
            if row["entry_mode"] == "双红当日收盘买" and reward_risk is not None and reward_risk >= 1.2:
                suggestion = "输出个股但标注不建议盘后追买"
            rows.append({
                "entry_mode": row["entry_mode"],
                "risk_level": level,
                "suggestion": suggestion,
                "group_dim": row["group_dim"],
                "group": row["group"],
                "full_rows": row["full_rows"],
                "median_mae_10d": row["median_mae_10d"],
                "mae_le_-5_pct": row["mae_le_-5_pct"],
                "mae_le_-8_pct": row["mae_le_-8_pct"],
                "mae_le_-10_pct": row["mae_le_-10_pct"],
                "median_peak_ret_10d": row["median_peak_ret_10d"],
                "reward_risk_median": row["reward_risk_median"],
                "risk_score": round(risk_score(row), 2),
            })
    rows.sort(key=lambda r: (-float(r["risk_score"]), r["entry_mode"], r["group_dim"], str(r["group"])))
    return rows


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value, suffix=""):
    return "样本不足" if value in ("", None) else f"{value}{suffix}"


def pick(summary, entry_mode, group_dim, group):
    for row in summary:
        if row["entry_mode"] == entry_mode and row["group_dim"] == group_dim and row["group"] == group:
            return row
    return {}


def top_rows(rows, n=8):
    return rows[:n]


def reflow_pick(summary, entry_mode, group_dim, groups):
    out = []
    for group in groups:
        row = pick(summary, entry_mode, group_dim, group)
        if row:
            out.append(row)
    return out


def markdown_table(rows, columns):
    if not rows:
        return "样本不足"
    lines = ["| " + " | ".join(title for title, _key in columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, "")) for _title, key in columns) + " |")
    return "\n".join(lines)


def build_report(args, detail, summary, rules):
    event_all = pick(summary, "双红当日收盘买", "all", "all")
    next_all = pick(summary, "次日承接后买", "all", "all")
    reflow_event_all = event_all
    reflow_next_all = next_all
    high_rules = top_rows(rules, 10)
    lifecycle_event = [r for r in summary if r["entry_mode"] == "双红当日收盘买" and r["group_dim"] == "lifecycle_family"]
    lifecycle_event = sorted(lifecycle_event, key=lambda r: risk_score(r), reverse=True)
    identity_event = [r for r in summary if r["entry_mode"] == "双红当日收盘买" and r["group_dim"] == "stock_identity"]
    identity_event = sorted(identity_event, key=lambda r: risk_score(r), reverse=True)
    combo_event = [r for r in summary if r["entry_mode"] == "双红当日收盘买" and r["group_dim"] in {"lifecycle+ma5_risk+limit", "lifecycle+identity"}]
    combo_event = sorted([r for r in combo_event if int(r.get("full_rows") or 0) >= args.min_rule_rows], key=lambda r: risk_score(r), reverse=True)[:12]
    full_detail = [r for r in detail if r.get("full_forward_window")]
    rejected = [r for r in full_detail if r["entry_mode"] == "双红当日收盘买" and r.get("next_day_path") not in STRONG_NEXT_PATHS]
    rejected_mae8 = pct(sum(1 for r in rejected if r.get("mae_le_-8")), len(rejected))
    confirmed = [r for r in full_detail if r["entry_mode"] == "次日承接后买"]
    confirmed_mae8 = pct(sum(1 for r in confirmed if r.get("mae_le_-8")), len(confirmed))
    lines = []
    lines.append("# Strategy1 回撤风险验证")
    lines.append("")
    lines.append(f"- 区间：{args.start_date} ~ {args.end_date}")
    lines.append(f"- 前瞻窗口：{args.forward_days} 个交易日")
    lines.append("- 买入点：双红当日收盘买、次日承接后买")
    lines.append("- 核心风险指标：`mae_10d`，即买入后窗口内最低收盘收益")
    lines.append("- 当前同时给出两套口径：10日路径风险统计，以及 `reflow_exit` 同题材下一次回流日尾盘卖出统计。")
    lines.append("- `次日承接后买` 的价格口径是次日收盘价作为买入基准。")
    lines.append("- `reflow_exit` 口径：沿候选命中的同题材，寻找买入日之后第一次再次双红的题材日，用该日个股收盘价作为卖出价。")
    lines.append("")
    lines.append("## 总体结论")
    lines.append("")
    lines.append("| 买入点 | 事件数 | 完整窗口 | MAE中位数 | -8%回撤占比 | 峰值收益中位数 | 收益/回撤比 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for row in [event_all, next_all]:
        if row:
            lines.append(f"| {row['entry_mode']} | {row['rows']} | {row['full_rows']} | {fmt(row['median_mae_10d'], '%')} | {fmt(row['mae_le_-8_pct'], '%')} | {fmt(row['median_peak_ret_10d'], '%')} | {fmt(row['reward_risk_median'])} |")
    lines.append("")
    lines.append("## 回流日尾盘卖出口径")
    lines.append("")
    lines.append("| 买入点 | 可计算回流卖出样本 | 覆盖率 | 回流卖出收益中位数 | 回流卖出胜率 | 回流前MAE中位数 | 回流前峰值中位数 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for row in [reflow_event_all, reflow_next_all]:
        if row:
            lines.append(f"| {row['entry_mode']} | {row['reflow_exit_rows']} | {fmt(row['reflow_exit_available_pct'], '%')} | {fmt(row['median_reflow_exit_ret'], '%')} | {fmt(row['reflow_exit_win_pct'], '%')} | {fmt(row['median_reflow_exit_mae'], '%')} | {fmt(row['median_reflow_exit_peak_ret'], '%')} |")
    lines.append("")
    lines.append("### 回流卖出关键分组")
    lines.append("")
    reflow_key_rows = []
    reflow_key_rows.extend(reflow_pick(summary, "双红当日收盘买", "lifecycle_family", ["d1", "d2", "d3", "mature_reflow"]))
    reflow_key_rows.extend(reflow_pick(summary, "双红当日收盘买", "limit_tag", ["limit_strong", "limit_medium", "limit_weak"]))
    reflow_key_rows.extend(reflow_pick(summary, "双红当日收盘买", "ma5_position_trend", ["中位区/上升", "高位区/上升", "中位区/下降", "震荡区间/震荡"]))
    lines.append(markdown_table(reflow_key_rows, [
        ("维度", "group_dim"), ("分组", "group"), ("可计算样本", "reflow_exit_rows"),
        ("回流收益中位数", "median_reflow_exit_ret"), ("回流胜率", "reflow_exit_win_pct"),
        ("回流前MAE", "median_reflow_exit_mae"),
    ]))
    lines.append("")
    lines.append("## 次日承接过滤效果")
    lines.append("")
    lines.append(f"- 未等承接的完整样本中，次日弱承接/未知承接事件数：{len(rejected)}，其中 `MAE <= -8%` 占比：{fmt(rejected_mae8, '%')}。")
    lines.append(f"- 次日承接确认后买的完整样本数：{len(confirmed)}，其中 `MAE <= -8%` 占比：{fmt(confirmed_mae8, '%')}。")
    lines.append("- 如果弱承接组回撤占比显著更高，策略一应输出个股时同步标注“弱承接风险”，而不是把名单伪装成无风险优选。")
    lines.append("")
    lines.append("## 生命周期风险排序")
    lines.append("")
    lines.append(markdown_table(top_rows(lifecycle_event, 8), [
        ("阶段", "group"), ("完整样本", "full_rows"), ("MAE中位数", "median_mae_10d"),
        ("-8%占比", "mae_le_-8_pct"), ("峰值中位数", "median_peak_ret_10d"), ("收益/回撤", "reward_risk_median"),
    ]))
    lines.append("")
    lines.append("## 个股身份风险排序")
    lines.append("")
    lines.append(markdown_table(top_rows(identity_event, 8), [
        ("身份", "group"), ("完整样本", "full_rows"), ("MAE中位数", "median_mae_10d"),
        ("-8%占比", "mae_le_-8_pct"), ("峰值中位数", "median_peak_ret_10d"), ("收益/回撤", "reward_risk_median"),
    ]))
    lines.append("")
    lines.append("## 高风险组合")
    lines.append("")
    lines.append(markdown_table(combo_event, [
        ("维度", "group_dim"), ("组合", "group"), ("完整样本", "full_rows"),
        ("MAE中位数", "median_mae_10d"), ("-8%占比", "mae_le_-8_pct"), ("峰值中位数", "median_peak_ret_10d"),
    ]))
    lines.append("")
    lines.append("## 规则候选")
    lines.append("")
    lines.append(markdown_table(high_rules, [
        ("建议", "suggestion"), ("风险级别", "risk_level"), ("买入点", "entry_mode"),
        ("维度", "group_dim"), ("条件", "group"), ("完整样本", "full_rows"),
        ("MAE中位数", "median_mae_10d"), ("-8%占比", "mae_le_-8_pct"),
    ]))
    lines.append("")
    lines.append("## 每日复盘使用口径")
    lines.append("")
    lines.append("### 可以输出个股")
    lines.append("")
    lines.append("- `d1/d2` 更适合做新启动/二次确认；`d3` 以后不是一概危险，而是进入结构分化。")
    lines.append("- `d3` 之后重点看两类：低位补涨是否真正获得题材映射，高位是否形成抱团核心。")
    lines.append("- 题材存在涨停映射或个股自身涨停映射，并且次日承接相对强时，可标为更高置信度。")
    lines.append("")
    lines.append("### 输出但标注风险")
    lines.append("")
    lines.append("- 多次回流成熟段：输出个股时必须标注“成熟段追高/抱团或补涨分化风险”。")
    lines.append("- MA5 震荡或回落：输出个股时必须标注“环境回撤风险”。")
    lines.append("- 个股已高位新高但题材级涨停映射弱：标注“个股强、题材映射不足”。")
    lines.append("")
    lines.append("### 不给无风险优选")
    lines.append("")
    lines.append("- 成熟段或 d3 以后 + MA5 风险/震荡回落 + `limit_weak`：可以输出名单，但必须标注为高危险系数组合。")
    lines.append("- 弱承接后仍想买入：必须标注“承接失败/回撤风险高”。")
    lines.append("- 低位补涨或旁支映射如果没有题材涨停映射、也没有容量核心，只能标注观察，不应写成主选。")
    lines.append("")
    lines.append("## 输出文件")
    lines.append("")
    lines.append("- `strategy1-drawdown-risk-detail.csv`")
    lines.append("- `strategy1-drawdown-risk-group-summary.csv`")
    lines.append("- `strategy1-drawdown-risk-rule-candidates.csv`")
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = load_data(args)
    candidates, prices, sector_reflow_dates, sector_info = build_event_candidates(args, data)
    detail = build_risk_detail(args, candidates, data, prices, sector_reflow_dates, sector_info)
    summary = build_group_summary(detail)
    rules = build_rule_candidates(args, summary)
    detail_path = output_dir / "strategy1-drawdown-risk-detail.csv"
    summary_path = output_dir / "strategy1-drawdown-risk-group-summary.csv"
    rules_path = output_dir / "strategy1-drawdown-risk-rule-candidates.csv"
    report_path = output_dir / "strategy1-drawdown-risk.md"
    write_csv(detail_path, detail)
    write_csv(summary_path, summary)
    write_csv(rules_path, rules)
    report_path.write_text(build_report(args, detail, summary, rules), encoding="utf-8")
    print(f"candidates={len(candidates)} detail_rows={len(detail)} summary_rows={len(summary)} rule_candidates={len(rules)}")
    print(detail_path)
    print(summary_path)
    print(rules_path)
    print(report_path)


if __name__ == "__main__":
    main()
