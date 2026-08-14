import csv
import math

from market_feature_store.db import connect

IN = "/tmp/e001b_full.csv"
OUT = "/tmp/e001b_full_engine.csv"

rows = list(csv.DictReader(open(IN)))
codes = {r["code"] for r in rows}
con = connect(read_only=True)
stock_rows = con.execute("""
select stock_ts_code, coalesce(nullif(split_part(sw_industry,'-',1),''), sw_l1) sw_l1,
       pct_chg, amount
from fact_sector_stock_daily
where trade_date='2026-04-08' and pct_chg>0 and amount is not null
""").fetchall()
con.close()
agg = {}
for code, sw, pct, amt in stock_rows:
    w = (pct or 0) * math.sqrt(amt or 0)
    item = agg.get((sw, code))
    if item is None or w > item["w"]:
        agg[(sw, code)] = {"code": code, "sw": sw, "w": w}
rank_map = {}
for sw in sorted({x["sw"] for x in agg.values()}):
    group = [x for x in agg.values() if x["sw"] == sw]
    for rank, x in enumerate(sorted(group, key=lambda y: y["w"], reverse=True)[:20], 1):
        rank_map[x["code"]] = (sw, rank, round(x["w"], 2))
for r in rows:
    sw, rank, w = rank_map.get(r["code"], ("", "", ""))
    r["engine_sw_0408"] = sw
    r["engine_rank_0408"] = rank
    r["engine_weighted_0408"] = w
fields = list(rows[0].keys())
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(f"written {len(rows)} {OUT}")
