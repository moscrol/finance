import csv
import math
from collections import defaultdict

from market_feature_store.db import connect

START = "2026-04-08"
END = "2026-04-20"
CORE_OUT = "research/market-hypothesis/strategy1-0408-0420-core-detail.csv"
TRANS_OUT = "research/market-hypothesis/strategy1-0408-0420-cohort-transitions.csv"
ROT_OUT = "research/market-hypothesis/strategy1-0408-0420-non-top3-rotation.csv"

con = connect(read_only=True)
trade_dates = [str(x[0]) for x in con.execute("""
select trade_date from fact_market_daily
where trade_date between ? and '2026-04-21'
order by trade_date
""", [START]).fetchall()]
event_dates = [d for d in trade_dates if d <= END]
next_date = {d: trade_dates[i + 1] for i, d in enumerate(trade_dates[:-1])}
market_rows = con.execute("""
select cast(trade_date as varchar), industry_1, industry_2, industry_3
from fact_market_daily where trade_date between ? and ?
""", [START, END]).fetchall()
market = {d: {x.strip() for x in [i1, i2, i3] if x} for d, i1, i2, i3 in market_rows}
sector_rows = con.execute("""
select cast(trade_date as varchar), sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount
from fact_sector_daily
where trade_date between ? and ? and pct_chg>0 and diff_ratio>10 and amount>500
""", [START, END]).fetchall()
stock_rows = con.execute("""
select cast(trade_date as varchar), stock_ts_code, stock_name, sw_l1, sw_industry, sector_ts_code,
       sector_name, pct_chg, amount, high_status_label
from fact_sector_stock_daily
where trade_date between ? and ? and pct_chg is not null and amount is not null
""", [START, END]).fetchall()
stock_div_rows = con.execute("""
select cast(trade_date as varchar), stock_ts_code, pct_chg, close
from fact_stock_daily
where trade_date between ? and '2026-04-21'
""", [START]).fetchall()
sw_div_rows = con.execute("""
select cast(trade_date as varchar), sw_l1, pct_chg
from fact_sw_l1_daily
where trade_date between ? and '2026-04-21'
""", [START]).fetchall()
con.close()

sectors_by_day = defaultdict(dict)
for day, sec_code, sec, sw, pct, diff, amount in sector_rows:
    sectors_by_day[day][sec_code] = {"sector_name": sec, "sw_l1": (sw or "").strip(), "amount": amount}
stocks_by_day = defaultdict(list)
for row in stock_rows:
    stocks_by_day[row[0]].append(row)
stock_day = {(d, c): {"pct": pct, "close": close} for d, c, pct, close in stock_div_rows}
sw_day = {(d, sw): pct for d, sw, pct in sw_div_rows}

core_rows = []
sector_cores = defaultdict(lambda: defaultdict(dict))
for day in event_dates:
    div = next_date.get(day)
    top = market.get(day, set())
    dr = {code: s for code, s in sectors_by_day[day].items() if s["sw_l1"] in top}
    if not dr or not div:
        continue
    pool = {}
    memberships = defaultdict(set)
    for _, code, name, sw, ind, sec_code, sec_name, pct, amount, high in stocks_by_day[day]:
        main = ((ind or "").split("-")[0] or sw or "").strip()
        if main not in top or sec_code not in dr:
            continue
        weighted = (pct or 0) * math.sqrt(amount or 0)
        item = pool.setdefault(code, {"code": code, "name": name, "sw_l1": main, "pct_event": pct, "amount_event": amount, "weighted": -1, "high": high or "", "sectors": set()})
        if weighted > item["weighted"]:
            item.update({"pct_event": pct, "amount_event": amount, "weighted": weighted, "high": high or ""})
        item["sectors"].add(sec_name)
        memberships[code].add(sec_name)
    if not pool:
        continue
    vals = sorted([x["weighted"] for x in pool.values()], reverse=True)
    cut = vals[max(1, len(vals)//5)-1]
    for item in pool.values():
        sd = stock_day.get((div, item["code"]), {})
        sp = sd.get("pct")
        ip = sw_day.get((div, item["sw_l1"]))
        rel = None if sp is None or ip is None else sp - ip
        if sp is None or ip is None:
            path = "unknown"
        elif sp >= 0 and sp >= ip:
            path = "抗住且相对强"
        elif sp < 0 and sp >= ip:
            path = "补跌但相对强"
        elif sp >= 0 and sp < ip:
            path = "上涨但弱于行业"
        else:
            path = "补跌且弱于行业"
        a = item["weighted"] >= cut
        b = bool(item["high"]) or len(item["sectors"]) >= 3
        c = path in {"抗住且相对强", "补跌但相对强"}
        score = int(a) + int(b) + int(c)
        full = score == 3
        if not full:
            continue
        for sec in item["sectors"]:
            row = {
                "event_date": day,
                "divergence_date": div,
                "sector_name": sec,
                "code": item["code"],
                "name": item["name"],
                "sw_l1": item["sw_l1"],
                "pct_event": round(item["pct_event"], 2),
                "amount_event": round(item["amount_event"], 2),
                "weighted_event": round(item["weighted"], 2),
                "high_event": item["high"],
                "double_red_hits": len(item["sectors"]),
                "pct_divergence": "" if sp is None else round(sp, 2),
                "rel_divergence": "" if rel is None else round(rel, 2),
                "divergence_path": path,
            }
            core_rows.append(row)
            sector_cores[sec][day][item["code"]] = item["name"]

with open(CORE_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(core_rows[0].keys()))
    writer.writeheader()
    writer.writerows(core_rows)

def names(d):
    return "、".join(list(d.values())[:12])

def avg_ret(codes, d0, d1):
    vals = []
    for c in codes:
        a = stock_day.get((d0, c), {}).get("close")
        b = stock_day.get((d1, c), {}).get("close")
        if a and b:
            vals.append((b / a - 1) * 100)
    return "" if not vals else round(sum(vals) / len(vals), 2)

trans = []
for sec, by_day in sector_cores.items():
    ds = sorted(by_day)
    if len(ds) < 2:
        continue
    seen = set()
    for i in range(1, len(ds)):
        prev_day, cur_day = ds[i-1], ds[i]
        prev = by_day[prev_day]
        cur = by_day[cur_day]
        sustained_codes = set(prev) & set(cur)
        new_codes = set(cur) - seen - set(prev)
        repeat_new_codes = set(cur) - set(prev)
        dropped_codes = set(prev) - set(cur)
        sustained = {c: cur[c] for c in sustained_codes}
        new = {c: cur[c] for c in new_codes}
        repeat_new = {c: cur[c] for c in repeat_new_codes}
        dropped = {c: prev[c] for c in dropped_codes}
        trans.append({
            "sector_name": sec,
            "prev_date": prev_day,
            "cur_date": cur_day,
            "prev_core_n": len(prev),
            "cur_core_n": len(cur),
            "sustained_n": len(sustained),
            "new_core_n": len(new),
            "rotated_in_n": len(repeat_new),
            "dropped_n": len(dropped),
            "sustained_names": names(sustained),
            "new_core_names": names(new),
            "rotated_in_names": names(repeat_new),
            "dropped_names": names(dropped),
            "prev_core_ret_to_cur_pct": avg_ret(prev.keys(), prev_day, cur_day),
            "sustained_ret_to_cur_pct": avg_ret(sustained.keys(), prev_day, cur_day),
            "dropped_ret_to_cur_pct": avg_ret(dropped.keys(), prev_day, cur_day),
        })
        seen.update(prev.keys())
    seen.update(by_day[ds[-1]].keys())
with open(TRANS_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(trans[0].keys()))
    writer.writeheader()
    writer.writerows(trans)

rot = []
for day, sec_code, sec, sw, pct, diff, amount in sector_rows:
    if (sw or "").strip() not in market.get(day, set()):
        rot.append({"trade_date": day, "sw_l1": sw, "sector_name": sec, "amount": round(amount or 0, 2), "pct_chg": round(pct or 0, 2), "diff_ratio": round(diff or 0, 2)})
with open(ROT_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rot[0].keys()))
    writer.writeheader()
    writer.writerows(rot)

print(CORE_OUT, len(core_rows))
print(TRANS_OUT, len(trans))
for r in sorted(trans, key=lambda x: (-x["cur_core_n"], x["sector_name"]))[:30]:
    print(r)
print(ROT_OUT, len(rot))
