import csv

IN = "research/market-hypothesis/strategy1-forward-2026-06-04-0605.csv"
OUT = "research/market-hypothesis/strategy1-forward-2026-06-04-0605-ranked.csv"

rows = list(csv.DictReader(open(IN)))
for r in rows:
    if r["strategy1_full"] != "1" or r["reflow_on_obs"] != "1":
        r["forward_score"] = ""
        r["portfolio_tier"] = ""
        continue
    pct65 = float(r["pct_obs"] or 0)
    weighted = float(r["weighted_event"])
    rel = float(r["rel_div"] or 0)
    reflow_count = len([x for x in r["reflow_sectors_obs"].split("、") if x])
    score = weighted * 0.12 + rel * 2.0 + reflow_count * 3.0 + pct65 * 2.5
    r["forward_score"] = round(score, 2)
    if pct65 >= 0 and score >= 25:
        r["portfolio_tier"] = "核心优选"
    elif pct65 >= -2 and score >= 20:
        r["portfolio_tier"] = "观察优选"
    elif score >= 15:
        r["portfolio_tier"] = "回流兑现/不追"
    else:
        r["portfolio_tier"] = "备选"
rows.sort(key=lambda r: (r["portfolio_tier"] not in {"核心优选", "观察优选"}, -(float(r["forward_score"] or -999)), r["name"]))
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print(OUT)
print("core", sum(r["portfolio_tier"] == "核心优选" for r in rows), "watch", sum(r["portfolio_tier"] == "观察优选" for r in rows))
