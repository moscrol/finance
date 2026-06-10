import csv
import math

from market_feature_store.db import connect

TOP_SW = {"电子", "电力设备", "通信"}
OUT = "/tmp/e001_candidates.csv"

con = connect(read_only=True)
dr_rows = con.execute("""
select sector_ts_code, sector_name
from fact_sector_daily
where trade_date='2026-04-08'
  and sw_l1 in ('电子','电力设备','通信')
  and pct_chg>0 and diff_ratio>10 and amount>500
""").fetchall()
dr = dict(dr_rows)

stock_rows = con.execute("""
select stock_ts_code, stock_name, sw_l1, sw_industry, sector_ts_code,
       sector_name, pct_chg, amount, high_status_label
from fact_sector_stock_daily
where trade_date='2026-04-08' and pct_chg>0 and amount is not null
""").fetchall()

agg = {}
for code, name, sw, ind, sec, sec_name, pct, amt, high in stock_rows:
    main = (ind or "").split("-")[0] or sw
    if main not in TOP_SW:
        continue
    item = agg.setdefault(code, {"code": code, "name": name, "sw": main, "w": -1, "dr": set()})
    w = (pct or 0) * math.sqrt(amt or 0)
    if w > item["w"]:
        item.update({"pct": pct, "amt": amt, "w": w, "high": high or ""})
    if sec in dr:
        item["dr"].add(sec_name)

out = []
for sw in sorted(TOP_SW):
    group = [x for x in agg.values() if x["sw"] == sw]
    for rank, x in enumerate(sorted(group, key=lambda y: y["w"], reverse=True)[:20], 1):
        out.append([sw, rank, x["code"], x["name"], round(x["pct"], 2), round(x["amt"], 2), round(x["w"], 2), len(x["dr"]), "、".join(sorted(x["dr"]))[:120], x["high"]])

with open(OUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["sw_l1", "rank", "code", "name", "pct_0408", "amount_0408", "weighted_0408", "double_red_hits", "double_red_sectors", "high_0408"])
    writer.writerows(out)

print(f"written {len(out)} {OUT}")
con.close()
