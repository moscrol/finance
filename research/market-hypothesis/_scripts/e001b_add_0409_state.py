import csv

from market_feature_store.db import connect

IN = "/tmp/e001b_0408_state.csv"
OUT = "/tmp/e001b_full.csv"

rows = list(csv.DictReader(open(IN)))
con = connect(read_only=True)
stock = {
    code: (pct, amt)
    for code, pct, amt in con.execute("""
select stock_ts_code, pct_chg, amount
from fact_stock_daily
where trade_date='2026-04-09'
""").fetchall()
}
sw = dict(con.execute("""
select sw_l1, pct_chg
from fact_sw_l1_daily
where trade_date='2026-04-09'
""").fetchall())
con.close()
for r in rows:
    pct, amt = stock.get(r["code"], (None, None))
    sw_pct = sw.get(r["sw_l1_0408"])
    r["pct_0409"] = "" if pct is None else round(pct, 2)
    r["amount_0409"] = "" if amt is None else round(amt, 2)
    r["sw_pct_0409"] = "" if sw_pct is None else round(sw_pct, 2)
    r["rel_0409"] = "" if pct is None or sw_pct is None else round(pct - sw_pct, 2)
fields = list(rows[0].keys())
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(f"written {len(rows)} {OUT}")
