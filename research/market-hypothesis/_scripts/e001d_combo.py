import csv
import statistics as st

BASE = "research/market-hypothesis/E001-C-mainline-liquidity-pool.csv"
ALIGN = "research/market-hypothesis/E001-C-reflow-peak-alignment.csv"
OUT = "/tmp/e001d_combo_summary.csv"
DETAIL = "/tmp/e001d_combo_detail.csv"

rows = list(csv.DictReader(open(ALIGN)))
valid = [r for r in rows if r.get("peak_ret")]
cut_n = max(1, len(valid) // 5)
weighted_cut = sorted([float(r["weighted_0408"]) for r in valid], reverse=True)[cut_n - 1]

def flag(r):
    weighted_top = float(r["weighted_0408"]) >= weighted_cut
    high_or_dr = bool(r["high_0408"]) or int(r["double_red_hits"]) >= 3
    rel_strong = r["divergence_path"] in {"抗住且相对强", "补跌但相对强"}
    return weighted_top, high_or_dr, rel_strong

for r in valid:
    a, b, c = flag(r)
    r["combo_weighted_top20"] = "1" if a else "0"
    r["combo_high_or_dr3"] = "1" if b else "0"
    r["combo_rel_strong"] = "1" if c else "0"
    r["combo_score"] = str(int(a) + int(b) + int(c))
    r["combo_full"] = "1" if a and b and c else "0"
    r["peak_ge10"] = "1" if float(r["peak_ret"]) >= 10 else "0"
    r["peak_ge15"] = "1" if float(r["peak_ret"]) >= 15 else "0"
    r["peak_ge20"] = "1" if float(r["peak_ret"]) >= 20 else "0"
    r["reflow_same_next"] = "1" if r["peak_minus_reflow_days"] in {"0", "1"} else "0"

fields = list(valid[0].keys())
with open(DETAIL, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(valid)

def pct(n, d):
    return round(n / d * 100, 2) if d else ""

def summarize(name, xs):
    if not xs:
        return [name, 0, "", "", "", "", "", "", ""]
    peaks = [float(r["peak_ret"]) for r in xs]
    return [
        name,
        len(xs),
        round(st.mean(peaks), 2),
        round(st.median(peaks), 2),
        pct(sum(r["peak_ge10"] == "1" for r in xs), len(xs)),
        pct(sum(r["peak_ge15"] == "1" for r in xs), len(xs)),
        pct(sum(r["peak_ge20"] == "1" for r in xs), len(xs)),
        pct(sum(r["reflow_same_next"] == "1" for r in xs), len(xs)),
        round(st.mean(float(r["drawdown_after_peak"]) for r in xs if r["drawdown_after_peak"]), 2),
    ]

summary = [
    summarize("all", valid),
    summarize("weighted_top20", [r for r in valid if r["combo_weighted_top20"] == "1"]),
    summarize("high_or_dr3", [r for r in valid if r["combo_high_or_dr3"] == "1"]),
    summarize("rel_strong", [r for r in valid if r["combo_rel_strong"] == "1"]),
    summarize("score_0", [r for r in valid if r["combo_score"] == "0"]),
    summarize("score_1", [r for r in valid if r["combo_score"] == "1"]),
    summarize("score_2", [r for r in valid if r["combo_score"] == "2"]),
    summarize("score_3_full", [r for r in valid if r["combo_score"] == "3"]),
]
with open(OUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["group", "n", "avg_peak", "med_peak", "peak_ge10_pct", "peak_ge15_pct", "peak_ge20_pct", "reflow_same_next_pct", "avg_drawdown_after_peak"])
    writer.writerows(summary)
print(f"weighted_cut {weighted_cut}")
print(f"written {OUT}")
print(f"written {DETAIL}")
