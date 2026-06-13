import csv

from market_feature_store.db import connect

OUT = "/tmp/e001b_top30.csv"

con = connect(read_only=True)
rows = con.execute("""
select a.stock_ts_code, a.stock_name, a.close close_0409, b.close close_0423,
       round((b.close / a.close - 1) * 100, 2) ret_10d
from fact_stock_daily a
join fact_stock_daily b using(stock_ts_code)
where a.trade_date='2026-04-09'
  and b.trade_date='2026-04-23'
  and a.close > 0
order by ret_10d desc
limit 30
""").fetchall()
con.close()
rows = [
    tuple("" if v is None else str(v).replace("\x00", "") for v in row)
    for row in rows
]

with open(OUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["code", "name", "close_0409", "close_0423", "ret_10d"])
    writer.writerows(rows)
print(f"written {len(rows)} {OUT}")
