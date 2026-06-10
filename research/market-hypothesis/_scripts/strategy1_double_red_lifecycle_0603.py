import csv

from market_feature_store.db import connect

EVENT = "2026-06-03"
OUT = "research/market-hypothesis/strategy1-double-red-lifecycle-2026-06-03.csv"

con = connect(read_only=True)
dates = [str(x[0]) for x in con.execute("""
select trade_date from fact_market_daily
where trade_date <= ? order by trade_date desc limit 6
""", [EVENT]).fetchall()][::-1]
prev_dates = dates[:-1]
rows = con.execute("""
select cast(trade_date as varchar), sector_name, sw_l1, pct_chg, diff_ratio, amount
from fact_sector_daily
where trade_date in (select trade_date from fact_market_daily where trade_date <= ? order by trade_date desc limit 6)
  and pct_chg>0 and diff_ratio>10 and amount>500
""", [EVENT]).fetchall()
con.close()
seen = {}
event_rows = []
for day, name, sw, pct, diff, amount in rows:
    if day != EVENT:
        seen.setdefault(name, []).append(day)
for day, name, sw, pct, diff, amount in rows:
    if day != EVENT:
        continue
    prev = seen.get(name, [])
    if not prev:
        lifecycle = "新晋双红"
    elif prev and prev[-1] == prev_dates[-1]:
        lifecycle = "连续/延续双红"
    else:
        lifecycle = "回流双红"
    event_rows.append({
        "event_date": EVENT,
        "sector_name": name,
        "sw_l1": sw,
        "pct_chg": round(pct, 2),
        "diff_ratio": round(diff, 2),
        "amount": round(amount, 2),
        "prev_5d_count": len(prev),
        "prev_5d_dates": "、".join(prev),
        "lifecycle": lifecycle,
    })
event_rows.sort(key=lambda r: (r["lifecycle"], r["sw_l1"], -r["amount"]))
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(event_rows[0].keys()))
    writer.writeheader()
    writer.writerows(event_rows)
print("dates", dates)
print(OUT)
for r in event_rows:
    print(r["lifecycle"], r["sw_l1"], r["sector_name"], r["prev_5d_count"], r["amount"])
