import csv

from market_feature_store.db import connect

START = "2026-04-08"
END = "2026-04-20"
FLOW_OUT = "research/market-hypothesis/strategy1-0408-0420-capacity-flow.csv"
DR_OUT = "research/market-hypothesis/strategy1-0408-0420-double-red-days.csv"

con = connect(read_only=True)
flow = con.execute("""
select cast(trade_date as varchar), total_amount, top3_industry_ratio,
       industry_1, industry_1_ratio, industry_2, industry_2_ratio, industry_3, industry_3_ratio,
       sh_index_pct_chg, advancers
from fact_market_daily
where trade_date between ? and ?
order by trade_date
""", [START, END]).fetchall()
dr = con.execute("""
select cast(trade_date as varchar), sw_l1, sector_name, pct_chg, diff_ratio, amount
from fact_sector_daily
where trade_date between ? and ?
  and pct_chg>0 and diff_ratio>10 and amount>500
order by trade_date, sw_l1, amount desc
""", [START, END]).fetchall()
con.close()

flow_rows = []
prev = None
for day, total, top3, i1, r1, i2, r2, i3, r3, sh, adv in flow:
    cur = tuple(x for x in [i1, i2, i3] if x)
    flow_rows.append({
        "trade_date": day,
        "total_amount": round(total or 0, 2),
        "top3_industry_ratio": round(top3 or 0, 2),
        "industry_1": i1,
        "industry_1_ratio": round(r1 or 0, 2),
        "industry_2": i2,
        "industry_2_ratio": round(r2 or 0, 2),
        "industry_3": i3,
        "industry_3_ratio": round(r3 or 0, 2),
        "sh_index_pct_chg": round(sh or 0, 2),
        "advancers": adv,
        "top3_changed": "" if prev is None else ("1" if set(cur) != set(prev) else "0"),
    })
    prev = cur
with open(FLOW_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(flow_rows[0].keys()))
    writer.writeheader()
    writer.writerows(flow_rows)

seen = {}
dr_rows = []
for day, sw, sec, pct, diff, amount in dr:
    prev_dates = seen.get(sec, [])
    if not prev_dates:
        phase = "窗口首发"
    elif prev_dates[-1] == day:
        phase = "同日重复"
    elif prev_dates[-1]:
        phase = "回流/延续"
    dr_rows.append({
        "trade_date": day,
        "sw_l1": sw,
        "sector_name": sec,
        "pct_chg": round(pct or 0, 2),
        "diff_ratio": round(diff or 0, 2),
        "amount": round(amount or 0, 2),
        "phase_in_window": phase,
        "prev_seen_dates": "、".join(prev_dates),
    })
    seen.setdefault(sec, []).append(day)
with open(DR_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(dr_rows[0].keys()))
    writer.writeheader()
    writer.writerows(dr_rows)
print(FLOW_OUT)
for r in flow_rows:
    print(r)
print(DR_OUT)
for r in dr_rows:
    print(r["trade_date"], r["phase_in_window"], r["sw_l1"], r["sector_name"], r["amount"])
