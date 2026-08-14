import argparse
import csv
import math
import statistics as st
from collections import defaultdict

from market_feature_store.db import connect

parser = argparse.ArgumentParser()
parser.add_argument("--sample-id", required=True)
parser.add_argument("--event-date", required=True)
parser.add_argument("--divergence-date", required=True)
args = parser.parse_args()

prefix = f"research/market-hypothesis/{args.sample_id}"
detail_out = f"{prefix}-strategy1-detail.csv"
summary_out = f"{prefix}-strategy1-summary.csv"

con = connect(read_only=True)
market = con.execute("""
select industry_1, industry_2, industry_3
from fact_market_daily where trade_date=?
""", [args.event_date]).fetchone()
if not market:
    raise SystemExit(f"missing market date {args.event_date}")
top_sw = {x.strip() for x in market if x}
dates = [str(x[0]) for x in con.execute("""
select trade_date from fact_market_daily
where trade_date >= ? order by trade_date limit 12
""", [args.divergence_date]).fetchall()]
dr_rows = con.execute("""
select sector_ts_code, sector_name, sw_l1, amount
from fact_sector_daily
where trade_date=? and pct_chg>0 and diff_ratio>10 and amount>500
""", [args.event_date]).fetchall()
stock_rows = con.execute("""
select stock_ts_code, stock_name, sw_l1, sw_industry, sector_ts_code,
       sector_name, pct_chg, amount, high_status_label
from fact_sector_stock_daily
where trade_date=? and pct_chg is not null and amount is not null
""", [args.event_date]).fetchall()
price_rows = con.execute("""
select stock_ts_code, cast(trade_date as varchar), close, pct_chg
from fact_stock_daily
where trade_date between ? and ?
""", [args.divergence_date, dates[-1]]).fetchall()
sw_pct = dict(con.execute("""
select sw_l1, pct_chg from fact_sw_l1_daily where trade_date=?
""", [args.divergence_date]).fetchall())
reflow_rows = con.execute("""
select sector_name, cast(trade_date as varchar)
from fact_sector_daily
where trade_date > ? and trade_date <= ?
  and pct_chg>0 and diff_ratio>10 and amount>500
""", [args.divergence_date, dates[-1]]).fetchall()
con.close()

dr = {code: (name, sw, amt) for code, name, sw, amt in dr_rows if sw and sw.strip() in top_sw}
stock_sectors = defaultdict(set)
pool = {}
for code, name, sw, ind, sec, sec_name, pct, amt, high in stock_rows:
    main = ((ind or "").split("-")[0] or sw or "").strip()
    if main not in top_sw or sec not in dr:
        continue
    w = (pct or 0) * math.sqrt(amt or 0)
    item = pool.setdefault(code, {"code": code, "name": name, "sw_l1": main, "pct_event": pct, "amount_event": amt, "weighted_event": -1, "high_event": high or "", "dr": set(), "dr_amount": 0})
    if w > item["weighted_event"]:
        item["pct_event"] = pct
        item["amount_event"] = amt
        item["weighted_event"] = w
        item["high_event"] = high or ""
    item["dr"].add(sec_name)
    item["dr_amount"] += dr[sec][2] or 0
    stock_sectors[code].add(sec_name)

prices = defaultdict(dict)
pcts = {}
for code, day, close, pct in price_rows:
    if code in pool:
        prices[code][day] = close
        if day == args.divergence_date:
            pcts[code] = pct

reflows = defaultdict(list)
for sec, day in reflow_rows:
    reflows[sec].append(day)
idx = {d: i for i, d in enumerate(dates)}
rows = []
for x in pool.values():
    code = x["code"]
    base = prices[code].get(args.divergence_date)
    r = {
        "sample_id": args.sample_id,
        "event_date": args.event_date,
        "divergence_date": args.divergence_date,
        "code": code,
        "name": x["name"],
        "sw_l1": x["sw_l1"],
        "pct_event": round(x["pct_event"], 2),
        "amount_event": round(x["amount_event"], 2),
        "weighted_event": round(x["weighted_event"], 2),
        "high_event": x["high_event"],
        "double_red_hits": len(x["dr"]),
        "double_red_amount_sum": round(x["dr_amount"], 2),
        "double_red_sectors": "、".join(sorted(x["dr"]))[:160],
    }
    for label, offset in [("ret_3d", 3), ("ret_5d", 5), ("ret_7d", 7), ("ret_10d", 10)]:
        day = dates[offset] if offset < len(dates) else None
        close = prices[code].get(day) if day else None
        r[label] = "" if not base or not close else round((close / base - 1) * 100, 2)
    path = []
    for day in dates[1:]:
        close = prices[code].get(day)
        if base and close:
            path.append((idx[day], day, (close / base - 1) * 100))
    if not path:
        continue
    peak = max(path, key=lambda z: z[2])
    r["peak_ret"] = round(peak[2], 2)
    r["peak_day_n"] = peak[0]
    r["peak_date"] = peak[1]
    r["drawdown_after_peak"] = round(path[-1][2] - peak[2], 2)
    sp = pcts.get(code)
    ip = sw_pct.get(x["sw_l1"])
    r["pct_divergence"] = "" if sp is None else round(sp, 2)
    r["sw_pct_divergence"] = "" if ip is None else round(ip, 2)
    if sp is None or ip is None:
        r["divergence_path"] = "unknown"
    elif sp >= 0 and sp >= ip:
        r["divergence_path"] = "抗住且相对强"
    elif sp < 0 and sp >= ip:
        r["divergence_path"] = "补跌但相对强"
    elif sp >= 0 and sp < ip:
        r["divergence_path"] = "上涨但弱于行业"
    else:
        r["divergence_path"] = "补跌且弱于行业"
    candidates = []
    for sec in stock_sectors[code]:
        for day in reflows.get(sec, []):
            candidates.append((abs(idx[r["peak_date"]] - idx[day]), idx[r["peak_date"]] - idx[day], day, sec))
    if candidates:
        _, off, day, sec = sorted(candidates, key=lambda z: (z[0], abs(z[1]), z[1]))[0]
        r["nearest_reflow_date"] = day
        r["nearest_reflow_sector"] = sec
        r["peak_minus_reflow_days"] = off
    else:
        r["nearest_reflow_date"] = r["nearest_reflow_sector"] = r["peak_minus_reflow_days"] = ""
    rows.append(r)

cut = sorted([float(r["weighted_event"]) for r in rows], reverse=True)[max(1, len(rows)//5)-1]
for r in rows:
    a = float(r["weighted_event"]) >= cut
    b = bool(r["high_event"]) or int(r["double_red_hits"]) >= 3
    c = r["divergence_path"] in {"抗住且相对强", "补跌但相对强"}
    r["strategy1_score"] = int(a) + int(b) + int(c)
    r["strategy1_full"] = "1" if a and b and c else "0"
    r["reflow_same_next"] = "1" if r["peak_minus_reflow_days"] in {0, 1, "0", "1"} else "0"

fields = list(rows[0].keys())
with open(detail_out, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

def pct(n, d):
    return round(n / d * 100, 2) if d else ""

def summ(name, xs):
    if not xs:
        return [name, 0, "", "", "", "", ""]
    peaks = [float(r["peak_ret"]) for r in xs]
    return [name, len(xs), round(st.mean(peaks), 2), round(st.median(peaks), 2), pct(sum(p >= 10 for p in peaks), len(xs)), pct(sum(p >= 20 for p in peaks), len(xs)), pct(sum(r["reflow_same_next"] == "1" for r in xs), len(xs))]
summary = [summ("all", rows)] + [summ(f"score_{i}", [r for r in rows if r["strategy1_score"] == i]) for i in range(4)] + [summ("strategy1_full", [r for r in rows if r["strategy1_full"] == "1"])]
with open(summary_out, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["group", "n", "avg_peak", "med_peak", "peak_ge10_pct", "peak_ge20_pct", "reflow_same_next_pct"])
    writer.writerows(summary)
print(args.sample_id, "pool", len(pool), "valid", len(rows), "weighted_cut", round(cut, 2))
print(detail_out)
print(summary_out)
