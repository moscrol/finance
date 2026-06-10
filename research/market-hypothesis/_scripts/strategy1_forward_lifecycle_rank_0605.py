import csv

CAND = "research/market-hypothesis/strategy1-forward-2026-06-04-0605-ranked.csv"
LIFE = "research/market-hypothesis/strategy1-double-red-lifecycle-2026-06-03.csv"
OUT = "research/market-hypothesis/strategy1-forward-2026-06-04-0605-lifecycle-ranked.csv"

life = {r["sector_name"]: r["lifecycle"] for r in csv.DictReader(open(LIFE))}
rows = list(csv.DictReader(open(CAND)))
for r in rows:
    secs = [s for s in r["event_sectors"].split("、") if s]
    labels = [life.get(s, "未知") for s in secs]
    new_count = sum(x == "新晋双红" for x in labels)
    cont_count = sum(x == "连续/延续双红" for x in labels)
    reflow_count = sum(x == "回流双红" for x in labels)
    r["new_double_red_hits"] = new_count
    r["continued_double_red_hits"] = cont_count
    r["reflow_double_red_hits"] = reflow_count
    if new_count and not cont_count and not reflow_count:
        r["theme_lifecycle_bias"] = "纯新晋"
    elif new_count >= cont_count + reflow_count:
        r["theme_lifecycle_bias"] = "新晋主导"
    elif cont_count or reflow_count:
        r["theme_lifecycle_bias"] = "延续/回流主导"
    else:
        r["theme_lifecycle_bias"] = "未知"
    base = float(r["forward_score"] or -999)
    r["forward_score_lifecycle"] = "" if r["forward_score"] == "" else round(base + new_count * 2 - reflow_count * 1, 2)
rows.sort(key=lambda r: (r["portfolio_tier"] not in {"核心优选", "观察优选"}, -(float(r["forward_score_lifecycle"] or -999)), r["name"]))
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print(OUT)
for r in rows:
    if r["portfolio_tier"] in {"核心优选", "观察优选"}:
        print(r["portfolio_tier"], r["name"], r["code"], r["forward_score_lifecycle"], r["theme_lifecycle_bias"], r["new_double_red_hits"], r["continued_double_red_hits"], r["event_sectors"][:60])
