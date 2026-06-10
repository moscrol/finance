import csv

from market_feature_store.db import connect

START = "2026-04-08"
EVENT = "2026-06-03"
LIFE_OUT = "research/market-hypothesis/strategy1-double-red-lifecycle-since-0408-2026-06-03.csv"
FLOW_OUT = "research/market-hypothesis/strategy1-capacity-top3-flow-0408-0605.csv"

con = connect(read_only=True)
trade_dates = [str(x[0]) for x in con.execute("""
select trade_date from fact_market_daily
where trade_date between ? and ? order by trade_date
""", [START, EVENT]).fetchall()]
idx = {d: i for i, d in enumerate(trade_dates)}
market = con.execute("""
select industry_1, industry_2, industry_3
from fact_market_daily where trade_date=?
""", [EVENT]).fetchone()
top_sw = {x.strip() for x in market if x}
dr_rows = con.execute("""
select cast(trade_date as varchar), sector_name, sw_l1, pct_chg, diff_ratio, amount
from fact_sector_daily
where trade_date between ? and ?
  and pct_chg>0 and diff_ratio>10 and amount>500
order by trade_date
""", [START, EVENT]).fetchall()
flow_rows = con.execute("""
select cast(trade_date as varchar), total_amount, top3_industry_ratio,
       industry_1, industry_1_ratio, industry_2, industry_2_ratio, industry_3, industry_3_ratio,
       sh_index_pct_chg, advancers
from fact_market_daily
where trade_date between ? and '2026-06-05'
order by trade_date
""", [START]).fetchall()
con.close()

history = {}
event_rows = []
for day, sector, sw, pct, diff, amount in dr_rows:
    history.setdefault(sector, []).append(day)
for day, sector, sw, pct, diff, amount in dr_rows:
    if day != EVENT or (sw or "").strip() not in top_sw:
        continue
    prev = [d for d in history.get(sector, []) if d < EVENT]
    prev_count = len(prev)
    first_seen = history[sector][0]
    last_prev = prev[-1] if prev else ""
    gap = "" if not last_prev else idx[EVENT] - idx[last_prev]
    if prev_count == 0:
        lifecycle = "4.8以来首发双红"
        priority = "启动优先"
    elif gap <= 1:
        lifecycle = "连续/近邻延续双红"
        priority = "延续确认"
    elif gap <= 5:
        lifecycle = "近期回流双红"
        priority = "回流兑现/谨慎新买"
    else:
        lifecycle = "久违回流双红"
        priority = "二阶段重启/需区分补涨"
    if prev_count >= 3 and gap != "" and gap <= 5:
        repeat_note = "高频反复"
    elif prev_count >= 3:
        repeat_note = "历史多次"
    elif prev_count > 0:
        repeat_note = "历史出现"
    else:
        repeat_note = "历史未见"
    event_rows.append({
        "event_date": EVENT,
        "sector_name": sector,
        "sw_l1": sw,
        "pct_chg": round(pct, 2),
        "diff_ratio": round(diff, 2),
        "amount": round(amount, 2),
        "first_seen_since_0408": first_seen,
        "prev_count_since_0408": prev_count,
        "last_prev_date": last_prev,
        "gap_trading_days": gap,
        "lifecycle_since_0408": lifecycle,
        "strategy1a_priority": priority,
        "repeat_note": repeat_note,
        "all_seen_dates": "、".join(history[sector]),
    })
event_rows.sort(key=lambda r: (r["strategy1a_priority"], r["sw_l1"], -r["amount"]))
with open(LIFE_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(event_rows[0].keys()))
    writer.writeheader()
    writer.writerows(event_rows)

flow = []
prev_set = None
for day, total_amount, top3_ratio, i1, r1, i2, r2, i3, r3, sh, adv in flow_rows:
    cur = tuple(x for x in [i1, i2, i3] if x)
    cur_set = set(cur)
    changed = "" if prev_set is None else ("1" if cur_set != prev_set else "0")
    flow.append({
        "trade_date": day,
        "total_amount": round(total_amount or 0, 2),
        "top3_industry_ratio": round(top3_ratio or 0, 2),
        "industry_1": i1,
        "industry_1_ratio": round(r1 or 0, 2),
        "industry_2": i2,
        "industry_2_ratio": round(r2 or 0, 2),
        "industry_3": i3,
        "industry_3_ratio": round(r3 or 0, 2),
        "sh_index_pct_chg": round(sh or 0, 2),
        "advancers": adv,
        "top3_set_changed": changed,
    })
    prev_set = cur_set
with open(FLOW_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(flow[0].keys()))
    writer.writeheader()
    writer.writerows(flow)

print(LIFE_OUT)
for r in event_rows:
    print(r["lifecycle_since_0408"], r["sw_l1"], r["sector_name"], "prev", r["prev_count_since_0408"], "gap", r["gap_trading_days"], "prio", r["strategy1a_priority"])
print(FLOW_OUT)
print("flow_changes")
for r in flow:
    if r["top3_set_changed"] == "1" or r["trade_date"] in {START, EVENT, "2026-06-04", "2026-06-05"}:
        print(r["trade_date"], r["top3_industry_ratio"], r["industry_1"], r["industry_1_ratio"], r["industry_2"], r["industry_2_ratio"], r["industry_3"], r["industry_3_ratio"], "chg", r["top3_set_changed"])
