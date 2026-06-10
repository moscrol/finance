import csv
import math

from market_feature_store.db import connect

OUT = "/tmp/e001c_pool.csv"
TOP_SW = {"电子", "电力设备", "通信"}

con = connect(read_only=True)
dr_rows = con.execute("""
select sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount
from fact_sector_daily
where trade_date='2026-04-08'
  and sw_l1 in ('电子','电力设备','通信')
  and pct_chg>0 and diff_ratio>10 and amount>500
""").fetchall()
stock_rows = con.execute("""
select stock_ts_code, stock_name, sw_l1, sw_industry, sector_ts_code,
       sector_name, pct_chg, amount, high_status_label
from fact_sector_stock_daily
where trade_date='2026-04-08'
  and pct_chg is not null and amount is not null
""").fetchall()
con.close()

dr = {code: {"name": name, "sw": sw, "pct": pct, "diff": diff, "amount": amt} for code, name, sw, pct, diff, amt in dr_rows}
agg = {}
for code, name, sw, ind, sec, sec_name, pct, amt, high in stock_rows:
    main = (ind or "").split("-")[0] or sw
    if main not in TOP_SW or sec not in dr:
        continue
    item = agg.setdefault(code, {"code": code, "name": name, "sw_l1": main, "pct_0408": pct, "amount_0408": amt, "weighted_0408": -1, "high_0408": high or "", "dr": set(), "dr_amount": 0})
    w = (pct or 0) * math.sqrt(amt or 0)
    if w > item["weighted_0408"]:
        item["pct_0408"] = pct
        item["amount_0408"] = amt
        item["weighted_0408"] = w
        item["high_0408"] = high or ""
    item["dr"].add(sec_name)
    item["dr_amount"] += dr[sec]["amount"] or 0

rows = []
for x in agg.values():
    rows.append([x["code"], x["name"], x["sw_l1"], round(x["pct_0408"], 2), round(x["amount_0408"], 2), round(x["weighted_0408"], 2), x["high_0408"], len(x["dr"]), round(x["dr_amount"], 2), "、".join(sorted(x["dr"]))[:160]])
rows.sort(key=lambda r: (r[2], -r[5]))
with open(OUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["code", "name", "sw_l1", "pct_0408", "amount_0408", "weighted_0408", "high_0408", "double_red_hits", "double_red_amount_sum", "double_red_sectors"])
    writer.writerows(rows)
print(f"written {len(rows)} {OUT}")
