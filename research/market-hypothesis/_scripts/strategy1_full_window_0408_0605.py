import csv
import math
from collections import defaultdict

from market_feature_store.db import connect

START = "2026-04-08"
END = "2026-06-05"
PRICE_BASE = "2026-06-04"
DETAIL_OUT = "research/market-hypothesis/strategy1-0408-0605-selected-detail.csv"
BEST_OUT = "research/market-hypothesis/strategy1-0408-0605-selected-best.csv"
SUMMARY_OUT = "research/market-hypothesis/strategy1-0408-0605-selected-summary.csv"

HIGH_RANK = {"历史新高": 7, "3年新高": 6, "2年新高": 5, "1年新高": 4, "120日新高": 3, "60日新高": 2, "20日新高": 1, "": 0, None: 0}

con = connect(read_only=True)
dates = [str(x[0]) for x in con.execute("""
select trade_date from fact_market_daily where trade_date between ? and ? order by trade_date
""", [START, END]).fetchall()]
market = {str(d): {x.strip() for x in [i1, i2, i3] if x} for d, i1, i2, i3 in con.execute("""
select trade_date, industry_1, industry_2, industry_3 from fact_market_daily
where trade_date between ? and ?
""", [START, END]).fetchall()}
market_names = {str(d): (i1, i2, i3) for d, i1, i2, i3 in con.execute("""
select trade_date, industry_1, industry_2, industry_3 from fact_market_daily
where trade_date between ? and ?
""", [START, END]).fetchall()}
sector_rows = con.execute("""
select cast(trade_date as varchar), sector_ts_code, sector_name, sw_l1, amount
from fact_sector_daily
where trade_date between ? and ? and pct_chg>0 and diff_ratio>10 and amount>500
""", [START, END]).fetchall()
stock_rows = con.execute("""
select cast(trade_date as varchar), stock_ts_code, stock_name, sw_l1, sw_industry, sector_ts_code,
       sector_name, pct_chg, amount, high_status_label
from fact_sector_stock_daily
where trade_date between ? and ? and pct_chg is not null and amount is not null
""", [START, END]).fetchall()
stock_day = {(str(d), c): {"pct": pct, "close": close} for d, c, pct, close in con.execute("""
select cast(trade_date as varchar), stock_ts_code, pct_chg, close
from fact_stock_daily where trade_date between ? and ?
""", [START, PRICE_BASE]).fetchall()}
obs65 = {}
for code, name, pct, high in con.execute("""
select stock_ts_code, stock_name, max(pct_chg), max(high_status_label)
from fact_sector_stock_daily where trade_date=? group by stock_ts_code, stock_name
""", [END]).fetchall():
    obs65[code] = {"pct": pct, "high": high or ""}
sw_day = {(str(d), sw): pct for d, sw, pct in con.execute("""
select cast(trade_date as varchar), sw_l1, pct_chg from fact_sw_l1_daily
where trade_date between ? and ?
""", [START, PRICE_BASE]).fetchall()}
con.close()

sector_by_day = defaultdict(dict)
for day, sec_code, sec, sw, amount in sector_rows:
    sector_by_day[day][sec_code] = {"sector_name": sec, "sw_l1": (sw or "").strip(), "amount": amount}
stocks_by_day = defaultdict(list)
for row in stock_rows:
    stocks_by_day[row[0]].append(row)

rows = []
for day in dates:
    idx = dates.index(day)
    div = dates[idx + 1] if idx + 1 < len(dates) and dates[idx + 1] <= PRICE_BASE else ""
    top = market.get(day, set())
    dr = {code: s for code, s in sector_by_day[day].items() if s["sw_l1"] in top}
    if not dr:
        continue
    pool = {}
    for _, code, name, sw, ind, sec_code, sec_name, pct, amount, high in stocks_by_day[day]:
        main = ((ind or "").split("-")[0] or sw or "").strip()
        if main not in top or sec_code not in dr:
            continue
        weighted = (pct or 0) * math.sqrt(amount or 0)
        item = pool.setdefault(code, {"code": code, "name": name, "sw_l1": main, "pct_event": pct, "amount_event": amount, "weighted": -1, "high_event": high or "", "sectors": set()})
        if weighted > item["weighted"]:
            item.update({"pct_event": pct, "amount_event": amount, "weighted": weighted, "high_event": high or ""})
        item["sectors"].add(sec_name)
    if not pool:
        continue
    vals = sorted([x["weighted"] for x in pool.values()], reverse=True)
    cut = vals[max(1, len(vals)//5)-1]
    for item in pool.values():
        sp = stock_day.get((div, item["code"]), {}).get("pct") if div else None
        ip = sw_day.get((div, item["sw_l1"])) if div else None
        if sp is None or ip is None:
            path = "unknown"
            rel = ""
        elif sp >= 0 and sp >= ip:
            path = "抗住且相对强"
            rel = sp - ip
        elif sp < 0 and sp >= ip:
            path = "补跌但相对强"
            rel = sp - ip
        elif sp >= 0 and sp < ip:
            path = "上涨但弱于行业"
            rel = sp - ip
        else:
            path = "补跌且弱于行业"
            rel = sp - ip
        weighted_top20 = item["weighted"] >= cut
        high_or_dr3 = bool(item["high_event"]) or len(item["sectors"]) >= 3
        rel_strong = path in {"抗住且相对强", "补跌但相对强"}
        full = weighted_top20 and high_or_dr3 and rel_strong
        if not full:
            continue
        entry_close = stock_day.get((day, item["code"]), {}).get("close")
        close64 = stock_day.get((PRICE_BASE, item["code"]), {}).get("close")
        pct65 = obs65.get(item["code"], {}).get("pct")
        est_close65 = close64 * (1 + pct65 / 100) if close64 and pct65 is not None else None
        ret65 = (est_close65 / entry_close - 1) * 100 if entry_close and est_close65 else ""
        ret64 = (close64 / entry_close - 1) * 100 if entry_close and close64 else ""
        reason = []
        reason.append("加权Top20")
        reason.append("新高" if item["high_event"] else "双红>=3")
        reason.append(path)
        i1, i2, i3 = market_names.get(day, ("", "", ""))
        rows.append({
            "event_date": day,
            "divergence_date": div,
            "code": item["code"],
            "name": item["name"],
            "sw_l1": item["sw_l1"],
            "top3_industries": "/".join([x for x in [i1, i2, i3] if x]),
            "pct_event": round(item["pct_event"], 2),
            "amount_event": round(item["amount_event"], 2),
            "weighted_event": round(item["weighted"], 2),
            "high_event": item["high_event"],
            "double_red_hits": len(item["sectors"]),
            "event_sectors": "、".join(sorted(item["sectors"]))[:180],
            "pct_divergence": "" if sp is None else round(sp, 2),
            "rel_divergence": "" if rel == "" else round(rel, 2),
            "divergence_path": path,
            "high_0605": obs65.get(item["code"], {}).get("high", ""),
            "pct_0605": "" if pct65 is None else round(pct65, 2),
            "ret_to_0604_pct": "" if ret64 == "" else round(ret64, 2),
            "ret_to_0605_est_pct": "" if ret65 == "" else round(ret65, 2),
            "selection_reason": "+".join(reason),
        })

rows.sort(key=lambda r: (r["event_date"], -float(r["weighted_event"])))
with open(DETAIL_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

best = {}
for r in rows:
    code = r["code"]
    score = HIGH_RANK.get(r["high_0605"], 0) * 100000 + HIGH_RANK.get(r["high_event"], 0) * 10000 + float(r["ret_to_0605_est_pct"] or -999) * 10 + float(r["weighted_event"])
    if code not in best or score > best[code][0]:
        best[code] = (score, r)
best_rows = [x[1] for x in best.values()]
best_rows.sort(key=lambda r: (-(HIGH_RANK.get(r["high_0605"],0)), -(float(r["ret_to_0605_est_pct"] or -999)), -float(r["weighted_event"])))
with open(BEST_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(best_rows[0].keys()))
    writer.writeheader()
    writer.writerows(best_rows)

summary = defaultdict(lambda: {"selected_events":0, "stocks":set()})
for r in rows:
    summary[r["event_date"]]["selected_events"] += 1
    summary[r["event_date"]]["stocks"].add(r["code"])
summary_rows = [{"event_date": d, "selected_rows": v["selected_events"], "unique_stocks": len(v["stocks"])} for d, v in sorted(summary.items())]
with open(SUMMARY_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
    writer.writeheader()
    writer.writerows(summary_rows)

print(DETAIL_OUT, len(rows))
print(BEST_OUT, len(best_rows))
print(SUMMARY_OUT)
for r in best_rows[:40]:
    print(r["name"], r["code"], r["event_date"], r["sw_l1"], r["high_event"], r["high_0605"], r["ret_to_0605_est_pct"], r["selection_reason"], r["event_sectors"][:50])
