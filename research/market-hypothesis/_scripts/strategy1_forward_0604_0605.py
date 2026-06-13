import csv
import math
from collections import defaultdict

from market_feature_store.db import connect

EVENT = "2026-06-03"
DIV = "2026-06-04"
OBS = "2026-06-05"
OUT = "research/market-hypothesis/strategy1-forward-2026-06-04-0605.csv"

con = connect(read_only=True)
market = con.execute("""
select industry_1, industry_2, industry_3
from fact_market_daily where trade_date=?
""", [EVENT]).fetchone()
top_sw = {x.strip() for x in market if x}
dr_event = con.execute("""
select sector_ts_code, sector_name, sw_l1, amount
from fact_sector_daily
where trade_date=? and pct_chg>0 and diff_ratio>10 and amount>500
""", [EVENT]).fetchall()
stock_event = con.execute("""
select stock_ts_code, stock_name, sw_l1, sw_industry, sector_ts_code,
       sector_name, pct_chg, amount, high_status_label
from fact_sector_stock_daily
where trade_date=? and pct_chg is not null and amount is not null
""", [EVENT]).fetchall()
stock_div = dict(con.execute("""
select stock_ts_code, pct_chg
from fact_stock_daily where trade_date=?
""", [DIV]).fetchall())
sw_div = dict(con.execute("""
select sw_l1, pct_chg from fact_sw_l1_daily where trade_date=?
""", [DIV]).fetchall())
dr_obs = {name for name, in con.execute("""
select sector_name
from fact_sector_daily
where trade_date=? and pct_chg>0 and diff_ratio>10 and amount>500
""", [OBS]).fetchall()}
stock_obs_rows = con.execute("""
select stock_ts_code, pct_chg, amount, high_status_label, high_status, high_status_label
from fact_sector_stock_daily
where trade_date=?
""", [OBS]).fetchall()
con.close()

dr = {code: (name, sw, amt) for code, name, sw, amt in dr_event if sw and sw.strip() in top_sw}
pool = {}
stock_sectors = defaultdict(set)
for code, name, sw, ind, sec, sec_name, pct, amt, high in stock_event:
    main = ((ind or "").split("-")[0] or sw or "").strip()
    if main not in top_sw or sec not in dr:
        continue
    weighted = (pct or 0) * math.sqrt(amt or 0)
    item = pool.setdefault(code, {
        "code": code, "name": name, "sw_l1": main,
        "pct_event": pct, "amount_event": amt, "weighted_event": -1,
        "high_event": high or "", "dr": set(), "dr_amount": 0,
    })
    if weighted > item["weighted_event"]:
        item["pct_event"] = pct
        item["amount_event"] = amt
        item["weighted_event"] = weighted
        item["high_event"] = high or ""
    item["dr"].add(sec_name)
    item["dr_amount"] += dr[sec][2] or 0
    stock_sectors[code].add(sec_name)

obs = {}
for code, pct, amt, high_label, high_status, high_label2 in stock_obs_rows:
    if code not in pool:
        continue
    item = obs.get(code)
    if item is None or (pct is not None and pct > item["pct_obs"]):
        obs[code] = {"pct_obs": pct or 0, "amount_obs": amt or 0, "high_obs": high_label or high_label2 or ""}

valid = list(pool.values())
cut = sorted([x["weighted_event"] for x in valid], reverse=True)[max(1, len(valid)//5)-1]
rows = []
for x in valid:
    code = x["code"]
    sp = stock_div.get(code)
    ip = sw_div.get(x["sw_l1"])
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
    reflow_secs = sorted(stock_sectors[code] & dr_obs)
    a = x["weighted_event"] >= cut
    b = bool(x["high_event"]) or len(x["dr"]) >= 3
    c = path in {"抗住且相对强", "补跌但相对强"}
    score = int(a) + int(b) + int(c)
    o = obs.get(code, {"pct_obs": "", "amount_obs": "", "high_obs": ""})
    rows.append({
        "code": code,
        "name": x["name"],
        "sw_l1": x["sw_l1"],
        "pct_event": round(x["pct_event"], 2),
        "amount_event": round(x["amount_event"], 2),
        "weighted_event": round(x["weighted_event"], 2),
        "weighted_top20": "1" if a else "0",
        "high_event": x["high_event"],
        "double_red_hits": len(x["dr"]),
        "high_or_dr3": "1" if b else "0",
        "pct_div": "" if sp is None else round(sp, 2),
        "sw_pct_div": "" if ip is None else round(ip, 2),
        "rel_div": "" if rel == "" else round(rel, 2),
        "divergence_path": path,
        "rel_strong": "1" if c else "0",
        "strategy1_score": score,
        "strategy1_full": "1" if score == 3 else "0",
        "reflow_on_obs": "1" if reflow_secs else "0",
        "reflow_sectors_obs": "、".join(reflow_secs)[:160],
        "pct_obs": o["pct_obs"],
        "amount_obs": o["amount_obs"],
        "high_obs": o["high_obs"],
        "event_sectors": "、".join(sorted(x["dr"]))[:160],
    })
rows.sort(key=lambda r: (r["strategy1_full"] != "1", r["reflow_on_obs"] != "1", -float(r["weighted_event"]), r["name"]))
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print("top_sw", ",".join(sorted(top_sw)))
print("pool", len(rows), "weighted_cut", round(cut, 2), "full", sum(r["strategy1_full"] == "1" for r in rows), "full_reflow", sum(r["strategy1_full"] == "1" and r["reflow_on_obs"] == "1" for r in rows))
print(OUT)
