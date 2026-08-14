import csv

from market_feature_store.db import connect

IN = "/tmp/e001_divergence.csv"
OUT = "/tmp/e001_returns.csv"
DATES = ["2026-04-09", "2026-04-16", "2026-04-23"]

rows = list(csv.DictReader(open(IN)))
con = connect(read_only=True)
price = {
    (code, str(day)): close
    for code, day, close in con.execute("""
select stock_ts_code, trade_date, close
from fact_stock_daily
where trade_date in ('2026-04-09','2026-04-16','2026-04-23')
""").fetchall()
}
con.close()

for r in rows:
    c0 = price.get((r["code"], DATES[0]))
    c5 = price.get((r["code"], DATES[1]))
    c10 = price.get((r["code"], DATES[2]))
    r["ret_5d_from_0409"] = "" if not c0 or not c5 else round((c5 / c0 - 1) * 100, 2)
    r["ret_10d_from_0409"] = "" if not c0 or not c10 else round((c10 / c0 - 1) * 100, 2)

fields = list(rows[0].keys())
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(f"written {len(rows)} {OUT}")
