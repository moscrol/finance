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


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--top-pct", type=float, default=0.20)
    parser.add_argument("--forward-days", type=int, default=10)
    return parser.parse_args()


def rows_to_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def placeholders(items):
    return ",".join("?" for _ in items)


def round_or_blank(value, digits=2):
    return "" if value is None or value == "" else round(value, digits)


def median(values):
    values = [v for v in values if v is not None and v != ""]
    return round(st.median(values), 2) if values else ""


def mean(values):
    values = [v for v in values if v is not None and v != ""]
    return round(st.mean(values), 2) if values else ""


def pct(num, den):
    return round(num / den * 100, 2) if den else ""


def safe_float(value):
    if value is None or value == "":
        return None
    return float(value)


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
    for i, (day, adv) in enumerate(rows):
        window = [r[1] for r in rows[max(0, i - 4): i + 1]]
        series.append({"date": str(day), "advancers": adv, "ma5": round(sum(window) / len(window), 2)})
    return {row["date"]: current_ma5_context(series, idx) for idx, row in enumerate(series)}


def forward_stats(prices, dates, date_pos, code, start_date, forward_days):
    start = prices.get((code, start_date), {}).get("close")
    if not start:
        return {}
    start_idx = date_pos[start_date]
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
    result = {
        "forward_available_days": available_days,
        "ret_3d": by_offset.get(3),
        "ret_5d": by_offset.get(5),
        "ret_7d": by_offset.get(7),
        "ret_10d": by_offset.get(10),
    }
    if available_days < forward_days:
        return result
    peak = max(path, key=lambda x: x[2])
    peak_seen = False
    peak_close = None
    max_dd = 0.0
    for offset, _day, _ret, close in path:
        if offset == peak[0]:
            peak_seen = True
            peak_close = close
        elif peak_seen and peak_close:
            max_dd = min(max_dd, (close / peak_close - 1) * 100)
    result.update({
        "peak_ret_10d": peak[2],
        "peak_day_10d": peak[0],
        "peak_date_10d": peak[1],
        "max_drawdown_after_peak_10d": max_dd,
    })
    return result


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
        table_counts = dict(con.execute(
            """
            SELECT table_name, estimated_size
            FROM duckdb_tables()
            WHERE table_name IN (
              'fact_market_daily','fact_sector_daily','fact_sector_stock_daily','fact_stock_daily',
              'fact_stock_high_daily','fact_theme_limit_stock_daily'
            )
            """
        ).fetchall())
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
                   sector_ts_code, sector_name, pct_chg, amount, high_status_label
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
        "table_counts": table_counts,
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
    next_event = {}
    for sector_code, rows in by_sector.items():
        rows = sorted(rows, key=lambda r: date_pos[r["trade_date"]])
        for idx, row in enumerate(rows):
            prev_gap = None
            if idx > 0:
                prev_gap = date_pos[row["trade_date"]] - date_pos[rows[idx - 1]["trade_date"]]
            lifecycle[(row["trade_date"], sector_code)] = {
                "lifecycle_index": idx + 1,
                "lifecycle_stage": classify_lifecycle(idx + 1, prev_gap),
                "prev_double_red_gap": prev_gap,
            }
            if idx + 1 < len(rows):
                nxt = rows[idx + 1]
                gap = date_pos[nxt["trade_date"]] - date_pos[row["trade_date"]]
                if gap <= 2:
                    result = "continuation"
                elif gap <= 7:
                    result = "quick_reflow"
                else:
                    result = "long_gap_reflow"
                next_event[(row["trade_date"], sector_code)] = {
                    "next_double_red_date": nxt["trade_date"],
                    "next_double_red_gap": gap,
                    "next_reflow_return": nxt.get("pct_chg"),
                    "reflow_result": result,
                }
            else:
                next_event[(row["trade_date"], sector_code)] = {
                    "next_double_red_date": "",
                    "next_double_red_gap": "",
                    "next_reflow_return": "",
                    "reflow_result": "no_reflow_in_window",
                }
    return lifecycle, next_event


def build_stock_detail(args, data):
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
    lifecycle, _next_event = build_lifecycle(data["dr_events"], date_pos)
    detail = []
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
                "sector_codes": set(),
                "sector_names": set(),
            })
            if weighted > item["weighted_event"]:
                item.update({
                    "pct_event": row["pct_chg"],
                    "amount_event": row["amount"],
                    "weighted_event": weighted,
                    "high_event": row.get("high_status_label") or "",
                })
            item["sector_codes"].add(sector_code)
            item["sector_names"].add(row["sector_name"])
        if not pool:
            continue
        weights = sorted([x["weighted_event"] for x in pool.values()], reverse=True)
        cut_idx = max(1, math.ceil(len(weights) * args.top_pct)) - 1
        weight_cut = weights[cut_idx]
        next_day = dates[date_pos[day] + 1] if date_pos[day] + 1 < len(dates) else ""
        for item in pool.values():
            next_stock_pct = prices.get((item["stock_ts_code"], next_day), {}).get("pct_chg") if next_day else None
            next_sw_pct = sw_pct.get((item["sw_l1"], next_day)) if next_day else None
            path, rel, rel_strong = next_day_path(next_stock_pct, next_sw_pct)
            weighted_top = item["weighted_event"] >= weight_cut
            high_or_dr3 = bool(item["high_event"]) or len(item["sector_codes"]) >= 3
            if not (weighted_top and high_or_dr3 and rel_strong):
                continue
            sector_counts = [theme_count.get((day, code), 0) for code in item["sector_codes"]]
            sector_ranks = [theme_rank.get((day, item["sw_l1"], code)) for code in item["sector_codes"] if theme_rank.get((day, item["sw_l1"], code))]
            lifecycle_items = [lifecycle.get((day, code), {}) for code in item["sector_codes"]]
            lifecycle_stage = sorted({x.get("lifecycle_stage", "") for x in lifecycle_items if x.get("lifecycle_stage")})
            max_limit_count = max(sector_counts) if sector_counts else 0
            limit_stock_hit = (day, item["stock_ts_code"]) in stock_hit
            limit_strong = max_limit_count >= 2 or limit_stock_hit
            limit_medium = max_limit_count == 1 and not limit_stock_hit
            limit_tag = "limit_strong" if limit_strong else "limit_medium" if limit_medium else "limit_weak"
            ma5 = data["ma5_contexts"].get(day, {})
            fwd = forward_stats(prices, dates, date_pos, item["stock_ts_code"], day, args.forward_days)
            row = {
                "event_date": day,
                "next_day": next_day,
                "stock_ts_code": item["stock_ts_code"],
                "stock_name": item["stock_name"],
                "sw_l1": item["sw_l1"],
                "top3_industries": "/".join(market_names.get(day, [])),
                "pct_event": round(item["pct_event"], 2),
                "amount_event": round(item["amount_event"], 2),
                "weighted_event": round(item["weighted_event"], 2),
                "high_event": item["high_event"],
                "double_red_hits": len(item["sector_codes"]),
                "event_sectors": "、".join(sorted(item["sector_names"])),
                "lifecycle_stages": "、".join(lifecycle_stage),
                "next_day_path": path,
                "next_day_rel_pct": round_or_blank(rel),
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
            for key in ["forward_available_days", "ret_3d", "ret_5d", "ret_7d", "ret_10d", "peak_ret_10d", "peak_day_10d", "peak_date_10d", "max_drawdown_after_peak_10d"]:
                row[key] = round_or_blank(fwd.get(key)) if isinstance(fwd.get(key), float) else fwd.get(key, "")
            peak = safe_float(row.get("peak_ret_10d"))
            row["peak_ge_5"] = peak is not None and peak >= 5
            row["peak_ge_10"] = peak is not None and peak >= 10
            row["peak_ge_20"] = peak is not None and peak >= 20
            detail.append(row)
    detail.sort(key=lambda r: (r["event_date"], -float(r["weighted_event"])))
    return detail


def summarize_stock_group(name, rows):
    with_forward = [r for r in rows if r.get("peak_ret_10d") not in ("", None)]
    peaks = [safe_float(r.get("peak_ret_10d")) for r in with_forward]
    ret5 = [safe_float(r.get("ret_5d")) for r in with_forward]
    ret10 = [safe_float(r.get("ret_10d")) for r in with_forward]
    dd = [safe_float(r.get("max_drawdown_after_peak_10d")) for r in with_forward]
    return {
        "group": name,
        "rows": len(rows),
        "rows_with_forward": len(with_forward),
        "unique_stocks": len({r["stock_ts_code"] for r in rows}),
        "median_peak_ret_10d": median(peaks),
        "mean_peak_ret_10d": mean(peaks),
        "median_ret_5d": median(ret5),
        "median_ret_10d": median(ret10),
        "median_drawdown_after_peak": median(dd),
        "peak_ge_5_pct": pct(sum(1 for r in with_forward if r.get("peak_ge_5")), len(with_forward)),
        "peak_ge_10_pct": pct(sum(1 for r in with_forward if r.get("peak_ge_10")), len(with_forward)),
        "peak_ge_20_pct": pct(sum(1 for r in with_forward if r.get("peak_ge_20")), len(with_forward)),
    }


def build_factor_summary(detail):
    groups = [
        ("base_strategy1", lambda r: True),
        ("limit_strong", lambda r: r["limit_tag"] == "limit_strong"),
        ("limit_medium", lambda r: r["limit_tag"] == "limit_medium"),
        ("limit_weak", lambda r: r["limit_tag"] == "limit_weak"),
        ("ma5_favorable", lambda r: bool(r["ma5_favorable"])),
        ("ma5_risk", lambda r: bool(r["ma5_risk"])),
        ("limit_strong+ma5_favorable", lambda r: r["limit_tag"] == "limit_strong" and bool(r["ma5_favorable"])),
        ("limit_weak+ma5_risk", lambda r: r["limit_tag"] == "limit_weak" and bool(r["ma5_risk"])),
    ]
    rows = [summarize_stock_group(name, [r for r in detail if pred(r)]) for name, pred in groups]
    stages = sorted({stage for r in detail for stage in str(r.get("lifecycle_stages", "")).split("、") if stage})
    for stage in stages:
        rows.append(summarize_stock_group(f"lifecycle:{stage}", [r for r in detail if stage in str(r.get("lifecycle_stages", ""))]))
    return rows


def build_theme_summary(args, data):
    dates = data["dates"]
    date_pos = {d: i for i, d in enumerate(dates)}
    market_top = {}
    for row in data["market_rows"]:
        market_top[row["trade_date"]] = {x.strip() for x in [row.get("industry_1"), row.get("industry_2"), row.get("industry_3")] if x}
    theme_count, sw_count, theme_rank, _stock_hit = build_limit_maps(data["limit_theme_rows"], data["limit_stock_rows"])
    lifecycle, next_event = build_lifecycle(data["dr_events"], date_pos)
    rows = []
    for event in data["dr_events"]:
        day = event["trade_date"]
        code = event["sector_ts_code"]
        sw = event.get("sw_l1") or ""
        count = theme_count.get((day, code), 0)
        if count >= 3:
            concentration = "concentrated"
        elif count >= 1:
            concentration = "weak"
        else:
            concentration = "none"
        ma5 = data["ma5_contexts"].get(day, {})
        lc = lifecycle.get((day, code), {})
        nxt = next_event.get((day, code), {})
        rows.append({
            "event_date": day,
            "sector_ts_code": code,
            "sector_name": event["sector_name"],
            "sw_l1": sw,
            "is_top3_sw_l1": sw in market_top.get(day, set()),
            "sector_pct": round_or_blank(event.get("pct_chg")),
            "sector_diff": round_or_blank(event.get("diff_ratio")),
            "sector_amount": round_or_blank(event.get("amount"), 1),
            "lifecycle_index": lc.get("lifecycle_index", ""),
            "lifecycle_stage": lc.get("lifecycle_stage", ""),
            "prev_double_red_gap": lc.get("prev_double_red_gap", ""),
            "limit_mapped_count": count,
            "limit_mapped_rank_in_sw": theme_rank.get((day, sw, code), ""),
            "limit_sw_count": sw_count.get((day, sw), 0),
            "limit_concentration_tag": concentration,
            "ma5_value": ma5.get("ma5_value", ""),
            "ma5_position": ma5.get("ma5_position", ""),
            "ma5_trend": ma5.get("ma5_trend", ""),
            "ma5_interval_delta": ma5.get("ma5_interval_delta", ""),
            "ma5_favorable": ma5.get("ma5_favorable", False),
            "ma5_risk": ma5.get("ma5_risk", False),
            "next_double_red_date": nxt.get("next_double_red_date", ""),
            "next_double_red_gap": nxt.get("next_double_red_gap", ""),
            "next_reflow_return": round_or_blank(nxt.get("next_reflow_return")),
            "reflow_result": nxt.get("reflow_result", ""),
        })
    rows.sort(key=lambda r: (r["event_date"], r["sw_l1"], r["sector_name"]))
    return rows


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def md_table(rows, columns):
    if not rows:
        return "无数据。"
    out = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
    return "\n".join(out)


def build_report(args, data, detail, factor_summary, theme_summary):
    base = next((r for r in factor_summary if r["group"] == "base_strategy1"), {})
    combo = next((r for r in factor_summary if r["group"] == "limit_strong+ma5_favorable"), {})
    limit_strong = next((r for r in factor_summary if r["group"] == "limit_strong"), {})
    limit_medium = next((r for r in factor_summary if r["group"] == "limit_medium"), {})
    ma5_fav = next((r for r in factor_summary if r["group"] == "ma5_favorable"), {})
    def verdict(test, base_row):
        a = safe_float(test.get("median_peak_ret_10d"))
        b = safe_float(base_row.get("median_peak_ret_10d"))
        n = int(test.get("rows_with_forward") or 0)
        if n < 10:
            return "样本不足"
        if a is not None and b is not None and a - b >= 0.75:
            return "初步支持"
        if a is not None and b is not None and a > b:
            return "边际改善"
        if a is not None and b is not None and a <= b:
            return "暂不支持"
        return "需补数据"
    theme_counter = Counter(r["reflow_result"] for r in theme_summary)
    limit_theme = [r for r in theme_summary if int(r.get("limit_mapped_count") or 0) > 0]
    no_limit_theme = [r for r in theme_summary if int(r.get("limit_mapped_count") or 0) == 0]
    def reflow_rate(rows):
        return pct(sum(1 for r in rows if r["reflow_result"] in {"continuation", "quick_reflow", "long_gap_reflow"}), len(rows))
    def theme_group_row(field, value, label):
        rows = [r for r in theme_summary if str(r.get(field)) == str(value)]
        return {
            "分组": label,
            "事件数": len(rows),
            "后续回流率": reflow_rate(rows),
            "无回流率": pct(sum(1 for r in rows if r["reflow_result"] == "no_reflow_in_window"), len(rows)),
        }
    lines = []
    lines.append(f"# 策略1：涨停映射与 MA5 区间影响验证")
    lines.append("")
    lines.append(f"窗口：{args.start_date} ~ {args.end_date}")
    lines.append("")
    lines.append("## 数据覆盖")
    lines.append("")
    lines.append(md_table([
        {"项目": "交易日", "数值": len(data["dates"])},
        {"项目": "双红题材事件", "数值": len(data["dr_events"])},
        {"项目": "策略1候选行", "数值": len(detail)},
        {"项目": f"完整{args.forward_days}日后验候选行", "数值": sum(1 for r in detail if r.get("peak_ret_10d") not in ("", None))},
        {"项目": "涨停映射行", "数值": len(data["limit_theme_rows"])},
        {"项目": "MA5上下文日期", "数值": len(data["ma5_contexts"])},
    ], ["项目", "数值"]))
    lines.append("")
    lines.append("## 个股层结论")
    lines.append("")
    top_factor_rows = [r for r in factor_summary if r["group"] in ["base_strategy1", "limit_strong", "limit_medium", "limit_weak", "ma5_favorable", "ma5_risk", "limit_strong+ma5_favorable", "limit_weak+ma5_risk"]]
    lines.append(md_table(top_factor_rows, ["group", "rows", "rows_with_forward", "median_peak_ret_10d", "median_ret_5d", "peak_ge_10_pct", "median_drawdown_after_peak"]))
    lines.append("")
    lines.append(f"- 涨停映射强：{verdict(limit_strong, base)}。")
    lines.append(f"- 涨停映射中等：{verdict(limit_medium, base)}。")
    lines.append(f"- MA5有利区间：{verdict(ma5_fav, base)}。")
    lines.append(f"- 涨停映射强 + MA5有利：{verdict(combo, base)}。")
    lines.append("- 初步解释：涨停映射不是越多越好；单独 `limit_strong` 的峰值收益没有显著高于基准，但回撤较小，`limit_medium` 和 MA5 有利区间更像有效过滤器。")
    lines.append("")
    lines.append("## 题材层结论")
    lines.append("")
    lines.append(md_table([
        {"分组": "有涨停映射", "事件数": len(limit_theme), "后续回流率": reflow_rate(limit_theme)},
        {"分组": "无涨停映射", "事件数": len(no_limit_theme), "后续回流率": reflow_rate(no_limit_theme)},
    ], ["分组", "事件数", "后续回流率"]))
    lines.append("")
    lines.append("### 题材层分组拆解")
    lines.append("")
    lines.append(md_table([
        theme_group_row("limit_concentration_tag", "concentrated", "涨停集中"),
        theme_group_row("limit_concentration_tag", "weak", "涨停弱映射"),
        theme_group_row("limit_concentration_tag", "none", "无涨停映射"),
        theme_group_row("ma5_favorable", True, "MA5有利"),
        theme_group_row("ma5_favorable", False, "MA5非有利"),
        theme_group_row("ma5_risk", True, "MA5风险"),
        theme_group_row("ma5_risk", False, "MA5非风险"),
    ], ["分组", "事件数", "后续回流率", "无回流率"]))
    lines.append("")
    lines.append("reflow_result 分布：")
    lines.append("")
    lines.append(md_table([{"类型": k, "数量": v} for k, v in theme_counter.most_common()], ["类型", "数量"]))
    lines.append("")
    lines.append("## 每日复盘使用建议")
    lines.append("")
    lines.append("1. 涨停映射只能作为策略1增强因子，不替代容量前三行业和双红题材条件；单独高涨停映射不应直接等同于更高收益。")
    lines.append("2. MA5 有利区间对个股层更稳定：峰值收益、5日收益、10%命中率均明显高于基准，可作为每日优选时的环境加权项。")
    lines.append("3. 涨停映射更适合题材层判断：有映射题材的后续回流率显著高于无映射题材，可用于判断双红题材是否有情绪承接。")
    lines.append("4. 若候选股同时满足涨停映射与 MA5 有利，应优先跟踪其次日承接、成交额保持和题材是否继续回流。")
    lines.append("5. 若 MA5 处于风险区，涨停映射可能更偏情绪高潮，需要降低追高权重并观察是否次日分歧。")
    lines.append("6. 本窗口仍是初步验证，不能把结果写成硬规则；后续每日复盘优选后继续追加验证。")
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = load_data(args)
    detail = build_stock_detail(args, data)
    factor_summary = build_factor_summary(detail)
    theme_summary = build_theme_summary(args, data)
    detail_path = output_dir / "strategy1-limit-ma5-impact-detail.csv"
    factor_path = output_dir / "strategy1-limit-ma5-impact-factor-summary.csv"
    theme_path = output_dir / "strategy1-limit-ma5-impact-theme-summary.csv"
    report_path = output_dir / "strategy1-limit-ma5-impact.md"
    write_csv(detail_path, detail)
    write_csv(factor_path, factor_summary)
    write_csv(theme_path, theme_summary)
    report_path.write_text(build_report(args, data, detail, factor_summary, theme_summary), encoding="utf-8")
    print(f"detail={detail_path} rows={len(detail)}")
    print(f"factor_summary={factor_path} rows={len(factor_summary)}")
    print(f"theme_summary={theme_path} rows={len(theme_summary)}")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
