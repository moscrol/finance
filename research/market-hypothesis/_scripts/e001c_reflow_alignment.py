import csv
from collections import Counter, defaultdict
from datetime import date

from market_feature_store.db import connect

IN = "research/market-hypothesis/E001-C-mainline-liquidity-pool.csv"
OUT = "/tmp/e001c_reflow_alignment.csv"
DATES = ["2026-04-10", "2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17", "2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23"]
idx = {d: i for i, d in enumerate(DATES, 1)}

rows = list(csv.DictReader(open(IN)))
code_set = {r["code"] for r in rows}
con = connect(read_only=True)
stock_sector_rows = con.execute("""
select stock_ts_code, sector_name
from fact_sector_stock_daily
where trade_date='2026-04-08'
  and stock_ts_code in (select stock_ts_code from fact_sector_stock_daily where trade_date='2026-04-08')
""").fetchall()
dr_0408 = {name for name, in con.execute("""
select sector_name
from fact_sector_daily
where trade_date='2026-04-08'
  and sw_l1 in ('电子','电力设备','通信')
  and pct_chg>0 and diff_ratio>10 and amount>500
""").fetchall()}
reflow_rows = con.execute("""
select sector_name, cast(trade_date as varchar) trade_date
from fact_sector_daily
where trade_date between '2026-04-10' and '2026-04-23'
  and pct_chg>0 and diff_ratio>10 and amount>500
""").fetchall()
con.close()

stock_sectors = defaultdict(set)
for code, sector in stock_sector_rows:
    if code in code_set and sector in dr_0408:
        stock_sectors[code].add(sector)
reflows = defaultdict(list)
for sector, day in reflow_rows:
    reflows[sector].append(day)

out = []
for r in rows:
    peak = r.get("peak_date")
    if not peak or peak not in idx:
        continue
    candidates = []
    for sec in stock_sectors.get(r["code"], set()):
        for day in reflows.get(sec, []):
            candidates.append((abs(idx[peak] - idx[day]), idx[peak] - idx[day], day, sec))
    if not candidates:
        r["nearest_reflow_date"] = ""
        r["nearest_reflow_sector"] = ""
        r["peak_minus_reflow_days"] = ""
    else:
        _, offset, day, sec = sorted(candidates, key=lambda x: (x[0], abs(x[1]), x[1]))[0]
        r["nearest_reflow_date"] = day
        r["nearest_reflow_sector"] = sec
        r["peak_minus_reflow_days"] = offset
    out.append(r)

fields = list(out[0].keys())
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(out)
print(f"written {len(out)} {OUT}")
print("all", Counter(r["peak_minus_reflow_days"] for r in out))
strong = [r for r in out if r["peak_ret"] and float(r["peak_ret"]) >= 20]
print("peak_ge20", len(strong), Counter(r["peak_minus_reflow_days"] for r in strong))
