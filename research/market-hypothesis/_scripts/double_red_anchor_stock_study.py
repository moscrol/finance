import argparse
import csv
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Direct execution needs the repository root on sys.path before project imports.
from market_feature_store.db import connect  # noqa: E402


DEFAULT_SW_L1 = ["电子", "通信", "电力设备", "机械设备"]
DEFAULT_START = "2026-04-08"
DEFAULT_END = "2026-06-05"
DEFAULT_OUTPUT_DIR = Path("research/market-hypothesis")
HIGH_RANK = {"历史新高": 7, "3年新高": 6, "2年新高": 5, "1年新高": 4, "120日新高": 3, "60日新高": 2, "20日新高": 1, "": 0, None: 0}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--sw-l1", nargs="+", default=DEFAULT_SW_L1)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--prefix", default="double-red-anchor-stock")
    return parser.parse_args()


def rows_to_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def placeholders(items):
    return ",".join("?" for _ in items)


def safe_float(value):
    return float(value) if value is not None and value != "" else None


def round_or_blank(value, digits=2):
    return "" if value is None else round(value, digits)


def pct(n, d):
    return round(n / d * 100, 2) if d else ""


def mean(values):
    return round(st.mean(values), 2) if values else ""


def median(values):
    return round(st.median(values), 2) if values else ""


def interval_return(prices, code, start_date, end_date):
    start = prices.get((code, start_date), {}).get("close")
    end = prices.get((code, end_date), {}).get("close")
    if not start or not end:
        return None
    return (end / start - 1) * 100


def interval_path_stats(prices, code, dates, start_date, end_date):
    start = prices.get((code, start_date), {}).get("close")
    if not start:
        return None, None, None, "", ""
    path = []
    peak_close = None
    max_drawdown = 0.0
    for day in dates:
        if day < start_date or day > end_date:
            continue
        close = prices.get((code, day), {}).get("close")
        if not close:
            continue
        ret = (close / start - 1) * 100
        path.append((day, close, ret))
        peak_close = close if peak_close is None else max(peak_close, close)
        if peak_close:
            max_drawdown = min(max_drawdown, (close / peak_close - 1) * 100)
    if not path:
        return None, None, None, "", ""
    peak = max(path, key=lambda x: x[2])
    trough = min(path, key=lambda x: x[2])
    return peak[2], trough[2], max_drawdown, peak[0], trough[0]


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


def build_detail(args):
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
        date_pos = {d: i for i, d in enumerate(dates)}
        sw_ph = placeholders(args.sw_l1)
        dr_events = rows_to_dicts(con.execute(
            f"""
            SELECT cast(trade_date AS varchar) trade_date, sector_ts_code, sector_name, sw_l1,
                   pct_chg sector_pct, diff_ratio sector_diff, amount sector_amount
            FROM fact_sector_daily
            WHERE trade_date BETWEEN ? AND ?
              AND sw_l1 IN ({sw_ph})
              AND pct_chg > 0 AND diff_ratio > 10 AND amount > 500
            ORDER BY sector_ts_code, trade_date
            """,
            [args.start_date, args.end_date] + args.sw_l1,
        ))
        if not dr_events:
            raise RuntimeError("指定区间没有双红题材")
        sector_codes = sorted({r["sector_ts_code"] for r in dr_events})
        sector_ph = placeholders(sector_codes)
        stock_rows = rows_to_dicts(con.execute(
            f"""
            SELECT cast(trade_date AS varchar) trade_date, sector_ts_code, sector_name, sw_l1,
                   stock_ts_code, stock_name, pct_chg, amount, pct_chg_3d, pct_chg_5d, pct_chg_10d,
                   high_status_label, limit_times, fund_flow_1d, fund_flow_5d,
                   float_mcap_yi, free_float_mcap_yi, total_mcap_yi
            FROM fact_sector_stock_daily
            WHERE trade_date BETWEEN ? AND ?
              AND sector_ts_code IN ({sector_ph})
              AND pct_chg IS NOT NULL
              AND amount IS NOT NULL
            """,
            [args.start_date, args.end_date] + sector_codes,
        ))
        stock_codes = sorted({r["stock_ts_code"] for r in stock_rows})
        stock_ph = placeholders(stock_codes)
        price_rows = rows_to_dicts(con.execute(
            f"""
            SELECT cast(trade_date AS varchar) trade_date, stock_ts_code, close, pct_chg, amount
            FROM fact_stock_daily
            WHERE trade_date BETWEEN ? AND ?
              AND stock_ts_code IN ({stock_ph})
            """,
            [args.start_date, args.end_date] + stock_codes,
        )) if stock_codes else []
        sw_rows = rows_to_dicts(con.execute(
            f"""
            SELECT cast(trade_date AS varchar) trade_date, sw_l1, pct_chg
            FROM fact_sw_l1_daily
            WHERE trade_date BETWEEN ? AND ?
              AND sw_l1 IN ({sw_ph})
            """,
            [args.start_date, args.end_date] + args.sw_l1,
        ))
    finally:
        con.close()

    events_by_sector = defaultdict(list)
    event_by_key = {}
    for row in dr_events:
        events_by_sector[row["sector_ts_code"]].append(row)
        event_by_key[(row["trade_date"], row["sector_ts_code"])] = row

    stocks_by_day_sector = defaultdict(list)
    dr_hits_by_day_stock = defaultdict(set)
    stock_row_by_key = {}
    dr_sector_by_day = defaultdict(set)
    for row in dr_events:
        dr_sector_by_day[row["trade_date"]].add(row["sector_ts_code"])
    for row in stock_rows:
        key = (row["trade_date"], row["sector_ts_code"])
        stocks_by_day_sector[key].append(row)
        stock_row_by_key[(row["trade_date"], row["sector_ts_code"], row["stock_ts_code"])] = row
        if row["sector_ts_code"] in dr_sector_by_day.get(row["trade_date"], set()):
            dr_hits_by_day_stock[(row["trade_date"], row["stock_ts_code"])].add(row["sector_name"])

    prices = {(r["stock_ts_code"], r["trade_date"]): r for r in price_rows}
    sw_pct = {(r["sw_l1"], r["trade_date"]): r["pct_chg"] for r in sw_rows}

    detail = []
    for sector_code, events in events_by_sector.items():
        events = sorted(events, key=lambda r: date_pos[r["trade_date"]])
        if len(events) < 2:
            continue
        anchors = events[:3]
        pairs = [(0, 1, "d1_to_d2")]
        if len(anchors) >= 3:
            pairs.extend([(1, 2, "d2_to_d3"), (0, 2, "d1_to_d3")])
        for start_idx, end_idx, pair_label in pairs:
            start_event = anchors[start_idx]
            end_event = anchors[end_idx]
            start_date = start_event["trade_date"]
            end_date = end_event["trade_date"]
            day_after = dates[date_pos[start_date] + 1] if date_pos[start_date] + 1 < len(dates) else ""
            samples = stocks_by_day_sector.get((start_date, sector_code), [])
            weighted_items = []
            for sample in samples:
                weighted = (sample["pct_chg"] or 0) * math.sqrt(sample["amount"] or 0)
                weighted_items.append((sample["stock_ts_code"], weighted))
            weighted_items.sort(key=lambda x: x[1], reverse=True)
            rank_by_code = {code: i + 1 for i, (code, _) in enumerate(weighted_items)}
            n = len(weighted_items)
            top_n = max(1, math.ceil(n * 0.2)) if n else 0
            for sample in samples:
                code = sample["stock_ts_code"]
                weighted = (sample["pct_chg"] or 0) * math.sqrt(sample["amount"] or 0)
                rank = rank_by_code.get(code, n)
                percentile = 100.0 if n <= 1 else 100 * (1 - (rank - 1) / (n - 1))
                ret = interval_return(prices, code, start_date, end_date)
                if ret is None:
                    continue
                peak_ret, min_ret, max_dd, peak_date, trough_date = interval_path_stats(prices, code, dates, start_date, end_date)
                start_price_row = prices.get((code, start_date), {})
                next_price_row = prices.get((code, day_after), {}) if day_after else {}
                next_stock_pct = next_price_row.get("pct_chg")
                next_sw_pct = sw_pct.get((sample["sw_l1"], day_after)) if day_after else None
                path, rel, rel_strong = next_day_path(next_stock_pct, next_sw_pct)
                start_amount_daily = start_price_row.get("amount") or sample["amount"]
                next_amount_daily = next_price_row.get("amount")
                amount_keep = next_amount_daily / start_amount_daily if next_amount_daily is not None and start_amount_daily else None
                next_sector_row = stock_row_by_key.get((day_after, sector_code, code), {}) if day_after else {}
                dr_hits = dr_hits_by_day_stock.get((start_date, code), set())
                high_start = sample.get("high_status_label") or ""
                row = {
                    "sector_ts_code": sector_code,
                    "sector_name": start_event["sector_name"],
                    "sw_l1": start_event["sw_l1"],
                    "anchor_pair": pair_label,
                    "start_anchor": f"d{start_idx + 1}",
                    "end_anchor": f"d{end_idx + 1}",
                    "start_date": start_date,
                    "end_date": end_date,
                    "holding_days": date_pos[end_date] - date_pos[start_date],
                    "stock_ts_code": code,
                    "stock_name": sample["stock_name"],
                    "ret_anchor_pct": round(ret, 2),
                    "peak_ret_pct": round_or_blank(peak_ret),
                    "min_ret_pct": round_or_blank(min_ret),
                    "max_drawdown_pct": round_or_blank(max_dd),
                    "peak_date": peak_date,
                    "trough_date": trough_date,
                    "pct_start": round_or_blank(sample["pct_chg"]),
                    "amount_start": round_or_blank(sample["amount"]),
                    "weighted_start": round(weighted, 2),
                    "weighted_rank": rank,
                    "weighted_rank_pct": round(percentile, 2),
                    "weighted_top20": "1" if rank <= top_n else "0",
                    "high_start": high_start,
                    "high_start_rank": HIGH_RANK.get(high_start, 0),
                    "double_red_hits_start": len(dr_hits),
                    "double_red_sectors_start": "、".join(sorted(dr_hits))[:240],
                    "sector_pct_start": round_or_blank(start_event["sector_pct"]),
                    "sector_diff_start": round_or_blank(start_event["sector_diff"]),
                    "sector_amount_start": round_or_blank(start_event["sector_amount"]),
                    "end_sector_pct": round_or_blank(end_event["sector_pct"]),
                    "end_sector_diff": round_or_blank(end_event["sector_diff"]),
                    "end_sector_amount": round_or_blank(end_event["sector_amount"]),
                    "pct_3d_start": round_or_blank(sample.get("pct_chg_3d")),
                    "pct_5d_start": round_or_blank(sample.get("pct_chg_5d")),
                    "pct_10d_start": round_or_blank(sample.get("pct_chg_10d")),
                    "limit_times_start": sample.get("limit_times") or 0,
                    "fund_flow_1d_start": round_or_blank(sample.get("fund_flow_1d")),
                    "fund_flow_5d_start": round_or_blank(sample.get("fund_flow_5d")),
                    "float_mcap_yi": round_or_blank(sample.get("float_mcap_yi")),
                    "free_float_mcap_yi": round_or_blank(sample.get("free_float_mcap_yi")),
                    "total_mcap_yi": round_or_blank(sample.get("total_mcap_yi")),
                    "next_date": day_after,
                    "next_pct": round_or_blank(next_stock_pct),
                    "next_sw_pct": round_or_blank(next_sw_pct),
                    "next_rel_pct": round_or_blank(rel),
                    "next_day_path": path,
                    "next_rel_strong": "1" if rel_strong else "0",
                    "next_amount_keep": round_or_blank(amount_keep, 3),
                    "next_high": next_sector_row.get("high_status_label") or "",
                    "start_only_rule": "1" if rank <= top_n and (high_start or len(dr_hits) >= 3) else "0",
                    "start_plus_next_rule": "1" if rank <= top_n and (high_start or len(dr_hits) >= 3) and rel_strong else "0",
                    "label_top20_ret": "0",
                }
                detail.append(row)

    grouped = defaultdict(list)
    for row in detail:
        grouped[(row["sector_ts_code"], row["anchor_pair"], row["start_date"], row["end_date"])].append(row)
    for rows in grouped.values():
        valid = sorted(rows, key=lambda r: safe_float(r["ret_anchor_pct"]) or -999, reverse=True)
        top_n = max(1, math.ceil(len(valid) * 0.2)) if valid else 0
        top_codes = {r["stock_ts_code"] for r in valid[:top_n]}
        for row in rows:
            row["label_top20_ret"] = "1" if row["stock_ts_code"] in top_codes else "0"
    detail.sort(key=lambda r: (r["sw_l1"], r["sector_name"], r["anchor_pair"], -(safe_float(r["ret_anchor_pct"]) or -999)))
    return detail, events_by_sector


def summarize_group(anchor_pair, visibility, condition, rows):
    returns = [safe_float(r["ret_anchor_pct"]) for r in rows if safe_float(r["ret_anchor_pct"]) is not None]
    peaks = [safe_float(r["peak_ret_pct"]) for r in rows if safe_float(r["peak_ret_pct"]) is not None]
    drawdowns = [safe_float(r["max_drawdown_pct"]) for r in rows if safe_float(r["max_drawdown_pct"]) is not None]
    return {
        "anchor_pair": anchor_pair,
        "visibility": visibility,
        "condition": condition,
        "n": len(rows),
        "unique_stocks": len({r["stock_ts_code"] for r in rows}),
        "unique_sectors": len({r["sector_ts_code"] for r in rows}),
        "avg_ret": mean(returns),
        "med_ret": median(returns),
        "win_rate_pct": pct(sum(v > 0 for v in returns), len(returns)),
        "ret_ge10_pct": pct(sum(v >= 10 for v in returns), len(returns)),
        "ret_ge20_pct": pct(sum(v >= 20 for v in returns), len(returns)),
        "top20_ret_capture_pct": pct(sum(r["label_top20_ret"] == "1" for r in rows), len(rows)),
        "avg_peak": mean(peaks),
        "med_peak": median(peaks),
        "peak_ge10_pct": pct(sum(v >= 10 for v in peaks), len(peaks)),
        "peak_ge20_pct": pct(sum(v >= 20 for v in peaks), len(peaks)),
        "med_max_drawdown": median(drawdowns),
    }


def build_factor_summary(detail):
    predicates = [
        ("start_only", "all", lambda r: True),
        ("start_only", "weighted_top20", lambda r: r["weighted_top20"] == "1"),
        ("start_only", "high_start", lambda r: bool(r["high_start"])),
        ("start_only", "double_red_hits>=2", lambda r: int(r["double_red_hits_start"]) >= 2),
        ("start_only", "double_red_hits>=3", lambda r: int(r["double_red_hits_start"]) >= 3),
        ("start_only", "pct_start>=5", lambda r: (safe_float(r["pct_start"]) or -999) >= 5),
        ("start_only", "amount_start>=10", lambda r: (safe_float(r["amount_start"]) or -999) >= 10),
        ("start_only", "weighted_top20+high", lambda r: r["weighted_top20"] == "1" and bool(r["high_start"])),
        ("start_only", "weighted_top20+double_red_hits>=2", lambda r: r["weighted_top20"] == "1" and int(r["double_red_hits_start"]) >= 2),
        ("start_only", "weighted_top20+double_red_hits>=3", lambda r: r["weighted_top20"] == "1" and int(r["double_red_hits_start"]) >= 3),
        ("start_only", "start_only_rule", lambda r: r["start_only_rule"] == "1"),
        ("start_plus_next", "next_rel_strong", lambda r: r["next_rel_strong"] == "1"),
        ("start_plus_next", "weighted_top20+next_rel_strong", lambda r: r["weighted_top20"] == "1" and r["next_rel_strong"] == "1"),
        ("start_plus_next", "high+next_rel_strong", lambda r: bool(r["high_start"]) and r["next_rel_strong"] == "1"),
        ("start_plus_next", "double_red_hits>=3+next_rel_strong", lambda r: int(r["double_red_hits_start"]) >= 3 and r["next_rel_strong"] == "1"),
        ("start_plus_next", "start_plus_next_rule", lambda r: r["start_plus_next_rule"] == "1"),
    ]
    out = []
    pairs = sorted({r["anchor_pair"] for r in detail})
    for pair in ["all"] + pairs:
        pair_rows = detail if pair == "all" else [r for r in detail if r["anchor_pair"] == pair]
        for visibility, condition, pred in predicates:
            rows = [r for r in pair_rows if pred(r)]
            out.append(summarize_group(pair, visibility, condition, rows))
    return out


def build_sector_summary(detail):
    groups = defaultdict(list)
    for row in detail:
        groups[(row["sw_l1"], row["sector_name"], row["sector_ts_code"], row["anchor_pair"], row["start_date"], row["end_date"])].append(row)
    out = []
    for key, rows in sorted(groups.items()):
        sw_l1, sector_name, sector_code, pair, start_date, end_date = key
        returns = [safe_float(r["ret_anchor_pct"]) for r in rows if safe_float(r["ret_anchor_pct"]) is not None]
        peaks = [safe_float(r["peak_ret_pct"]) for r in rows if safe_float(r["peak_ret_pct"]) is not None]
        top_ret = sorted(rows, key=lambda r: safe_float(r["ret_anchor_pct"]) or -999, reverse=True)[:8]
        top_weighted = sorted(rows, key=lambda r: safe_float(r["weighted_start"]) or -999, reverse=True)[:8]
        top_ret_stocks = "、".join(f"{r['stock_name']}({r['ret_anchor_pct']}%)" for r in top_ret)
        top_weighted_stocks = "、".join(f"{r['stock_name']}({r['weighted_start']})" for r in top_weighted)
        out.append({
            "sw_l1": sw_l1,
            "sector_name": sector_name,
            "sector_ts_code": sector_code,
            "anchor_pair": pair,
            "start_date": start_date,
            "end_date": end_date,
            "n": len(rows),
            "avg_ret": mean(returns),
            "med_ret": median(returns),
            "win_rate_pct": pct(sum(v > 0 for v in returns), len(returns)),
            "ret_ge10_pct": pct(sum(v >= 10 for v in returns), len(returns)),
            "ret_ge20_pct": pct(sum(v >= 20 for v in returns), len(returns)),
            "avg_peak": mean(peaks),
            "med_peak": median(peaks),
            "start_only_rule_n": sum(r["start_only_rule"] == "1" for r in rows),
            "start_plus_next_rule_n": sum(r["start_plus_next_rule"] == "1" for r in rows),
            "top_ret_stocks": top_ret_stocks,
            "top_weighted_start_stocks": top_weighted_stocks,
        })
    return out


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    detail, events_by_sector = build_detail(args)
    factor_summary = build_factor_summary(detail)
    sector_summary = build_sector_summary(detail)
    detail_path = output_dir / f"{args.prefix}-detail.csv"
    factor_path = output_dir / f"{args.prefix}-factor-summary.csv"
    sector_path = output_dir / f"{args.prefix}-sector-summary.csv"
    write_csv(detail_path, detail)
    write_csv(factor_path, factor_summary)
    write_csv(sector_path, sector_summary)
    print(f"detail: {detail_path} rows={len(detail)}")
    print(f"factor_summary: {factor_path} rows={len(factor_summary)}")
    print(f"sector_summary: {sector_path} rows={len(sector_summary)}")
    print(f"sectors_with_double_red: {len(events_by_sector)}")


if __name__ == "__main__":
    main()
