import csv

from market_feature_store.db import connect

IN = "/tmp/e001b_top30.csv"
OUT = "/tmp/e001b_0408_state.csv"

rows = list(csv.DictReader(open(IN)))
con = connect(read_only=True)
stock_rows = con.execute("""
select stock_ts_code, stock_name,
       coalesce(nullif(split_part(sw_industry,'-',1),''), sw_l1) sw_l1,
       sector_name, pct_chg, amount, high_status_label
from fact_sector_stock_daily
where trade_date='2026-04-08'
""").fetchall()
dr_rows = con.execute("""
select sector_ts_code, sector_name
from fact_sector_daily
where trade_date='2026-04-08'
  and pct_chg>0 and diff_ratio>10 and amount>500
""").fetchall()
con.close()
dr = {name for _code, name in dr_rows}
state = {}
for code, name, sw, sec, pct, amt, high in stock_rows:
    item = state.setdefault(code, {"sw_l1_0408": sw or "", "pct_0408": pct, "amount_0408": amt, "high_0408": high or "", "dr": set()})
    if pct is not None and (item["pct_0408"] is None or pct > item["pct_0408"]):
        item["pct_0408"] = pct
        item["amount_0408"] = amt
        item["high_0408"] = high or ""
    if sec in dr:
        item["dr"].add(sec)
for r in rows:
    s = state.get(r["code"], {})
    r["sw_l1_0408"] = s.get("sw_l1_0408", "")
    r["pct_0408"] = "" if s.get("pct_0408") is None else round(s["pct_0408"], 2)
    r["amount_0408"] = "" if s.get("amount_0408") is None else round(s["amount_0408"], 2)
    r["high_0408"] = s.get("high_0408", "")
    r["double_red_hits_0408"] = len(s.get("dr", []))
    r["double_red_sectors_0408"] = "、".join(sorted(s.get("dr", [])))[:120]
fields = list(rows[0].keys())
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(f"written {len(rows)} {OUT}")
