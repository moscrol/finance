"""对三臂差分实验的既有答案做多次盲评取中位（降判官方差，不重跑 ask）。

背景：20260827T191014Z 那轮实测同文本三评打出 12/13/15（±3/20），单评分辨率
不足以测 ≤3 分的效应。本脚本每份答案补评到 N 次，按总分取中位数重新聚合。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.exp_user_memory_diff import ARMS, BASELINE_ARM  # noqa: E402
from scripts.run_quality_ablation import (  # noqa: E402
    QUESTIONS,
    RUBRIC_DIMENSIONS,
    judge_answer,
    require_llm_ready,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--target-judgments", type=int, default=3, help="每份答案的总评次")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    require_llm_ready()
    src = Path(args.input)
    payload = json.loads(src.read_text(encoding="utf-8"))
    q_by_id = {q.case_id: q for q in QUESTIONS}

    for r in payload["answers"]:
        if not r.get("ok"):
            continue
        judgments = r.get("judgments") or []
        first = r.get("judge")
        if first and first.get("scored") and not judgments:
            judgments = [first]
        while len(judgments) < args.target_judgments:
            print(f"[rejudge] {r['case_id']} × {r['arm']} #{len(judgments) + 1} ...", flush=True)
            v = judge_answer(q_by_id[str(r["case_id"])], str(r["answer"]))
            if not v.get("scored"):
                print(f"[rejudge]   unscored: {v.get('reason')}", flush=True)
                break
            judgments.append(v)
        r["judgments"] = judgments
        scored = [j for j in judgments if j.get("scored")]
        if scored:
            median_total = statistics.median(j["total"] for j in scored)
            r["judge_median"] = {
                "scored": True,
                "n": len(scored),
                "total": median_total,
                "totals": [j["total"] for j in scored],
                "scores": {
                    d: statistics.median(j["scores"][d] for j in scored)
                    for d in RUBRIC_DIMENSIONS
                },
            }
        else:
            r["judge_median"] = {"scored": False, "n": 0}

    # 以中位分重新聚合（数学同 aggregate_arms，读数换 judge_median）
    base = {
        str(r["case_id"]): r
        for r in payload["answers"]
        if r["arm"] == BASELINE_ARM and (r.get("judge_median") or {}).get("scored")
    }
    summary: dict[str, object] = {}
    for arm in ARMS:
        rows = []
        for r in payload["answers"]:
            if r["arm"] != arm or not (r.get("judge_median") or {}).get("scored"):
                continue
            jm = r["judge_median"]
            row = {"case_id": r["case_id"], "total": jm["total"], "spread": jm["totals"]}
            b = base.get(str(r["case_id"]))
            if arm != BASELINE_ARM and b:
                row["delta_vs_coldstart"] = jm["total"] - b["judge_median"]["total"]
            rows.append(row)
        totals = [row["total"] for row in rows]
        deltas = [row["delta_vs_coldstart"] for row in rows if "delta_vs_coldstart" in row]
        summary[arm] = {
            "n": len(rows),
            "mean_median_total": round(sum(totals) / len(totals), 3) if totals else None,
            "mean_delta_vs_coldstart": (
                round(sum(deltas) / len(deltas), 3) if deltas else None
            ),
            "rows": rows,
        }
    payload["median_summary"] = summary

    out = Path(args.output or str(src).replace(".json", "-rejudged.json"))
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n===== 中位分三臂对比（以 coldstart 为基线）=====")
    for arm, s in summary.items():
        print(
            f"{arm}: mean(median)={s['mean_median_total']} "
            f"Δ={s['mean_delta_vs_coldstart']} n={s['n']}"
        )
    print(f"台账：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
