import csv

CAND = "research/market-hypothesis/strategy1-forward-2026-06-04-0605-ranked.csv"
LIFE = "research/market-hypothesis/strategy1-double-red-lifecycle-since-0408-2026-06-03.csv"
OUT = "research/market-hypothesis/strategy1-forward-2026-06-04-0605-lifecycle-since0408-ranked.csv"

life = {r["sector_name"]: r for r in csv.DictReader(open(LIFE))}
rows = list(csv.DictReader(open(CAND)))
for r in rows:
    secs = [s for s in r["event_sectors"].split("、") if s]
    start = sum(life.get(s, {}).get("strategy1a_priority") == "启动优先" for s in secs)
    restart = sum(life.get(s, {}).get("strategy1a_priority") == "二阶段重启/需区分补涨" for s in secs)
    cont = sum(life.get(s, {}).get("strategy1a_priority") == "延续确认" for s in secs)
    cautious = sum(life.get(s, {}).get("strategy1a_priority") == "回流兑现/谨慎新买" for s in secs)
    r["since0408_start_hits"] = start
    r["since0408_restart_hits"] = restart
    r["since0408_continue_hits"] = cont
    r["since0408_recent_reflow_hits"] = cautious
    if start:
        bias = "4.8以来首发启动"
    elif restart >= max(cont, cautious, 1):
        bias = "二阶段重启/补涨主导"
    elif cont:
        bias = "延续确认主导"
    else:
        bias = "未识别"
    r["since0408_lifecycle_bias"] = bias
rows.sort(key=lambda r: (r["portfolio_tier"] not in {"核心优选", "观察优选"}, -(float(r["forward_score"] or -999)), r["name"]))
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print(OUT)
for r in rows:
    if r["portfolio_tier"] in {"核心优选", "观察优选"}:
        print(r["portfolio_tier"], r["name"], r["code"], r["since0408_lifecycle_bias"], "restart", r["since0408_restart_hits"], "cont", r["since0408_continue_hits"], r["event_sectors"][:70])
