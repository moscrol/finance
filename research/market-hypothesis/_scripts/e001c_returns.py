import csv

from market_feature_store.db import connect

IN = "/tmp/e001c_pool.csv"
OUT = "/tmp/e001c_returns.csv"
DATES = ["2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17", "2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23"]
WINDOW = {"ret_3d": 3, "ret_5d": 5, "ret_7d": 7, "ret_10d": 10}

rows = list(csv.DictReader(open(IN)))
codes = {r["code"] for r in rows}
con = connect(read_only=True)
price_rows = con.execute("""
select stock_ts_code, trade_date, close
from fact_stock_daily
where trade_date between '2026-04-09' and '2026-04-23'
""").fetchall()
con.close()
prices = {}
for code, day, close in price_rows:
    if code in codes:
        prices.setdefault(code, {})[str(day)] = close
for r in rows:
    p = prices.get(r["code"], {})
    base = p.get(DATES[0])
    for field, idx in WINDOW.items():
        close = p.get(DATES[idx]) if idx < len(DATES) else None
        r[field] = "" if not base or not close else round((close / base - 1) * 100, 2)
    path = []
    for i, day in enumerate(DATES[1:], 1):
        close = p.get(day)
        if base and close:
            path.append((i, day, (close / base - 1) * 100))
    if path:
        peak = max(path, key=lambda x: x[2])
        last = path[-1][2]
        r["peak_ret"] = round(peak[2], 2)
        r["peak_day_n"] = peak[0]
        r["peak_date"] = peak[1]
        r["drawdown_after_peak"] = round(last - peak[2], 2)
    else:
        r["peak_ret"] = r["peak_day_n"] = r["peak_date"] = r["drawdown_after_peak"] = ""
fields = list(rows[0].keys())
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(f"written {len(rows)} {OUT}")
