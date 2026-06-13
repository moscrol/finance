import csv

samples = [
    ("E001-2026-04-08", "research/market-hypothesis/E001-D-combo-summary.csv", "score_3_full"),
    ("E002-2026-04-10", "research/market-hypothesis/E002-2026-04-10-strategy1-summary.csv", "strategy1_full"),
    ("E003-2026-05-11", "research/market-hypothesis/E003-2026-05-11-strategy1-summary.csv", "strategy1_full"),
    ("E004-2026-04-14", "research/market-hypothesis/E004-2026-04-14-strategy1-summary.csv", "strategy1_full"),
]
OUT = "research/market-hypothesis/strategy1-cross-sample-summary.csv"
rows = []
for sid, path, full_name in samples:
    data = list(csv.DictReader(open(path)))
    all_row = next(r for r in data if r["group"] == "all")
    full = next(r for r in data if r["group"] == full_name)
    rows.append({
        "sample_id": sid,
        "all_n": all_row["n"],
        "all_med_peak": all_row["med_peak"],
        "all_peak_ge20_pct": all_row["peak_ge20_pct"],
        "full_n": full["n"],
        "full_med_peak": full["med_peak"],
        "full_peak_ge20_pct": full["peak_ge20_pct"],
        "full_reflow_same_next_pct": full["reflow_same_next_pct"],
    })
with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print(OUT)
for r in rows:
    print(r)
