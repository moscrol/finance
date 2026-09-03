"""三臂用户记忆差分实验（一次性实验脚本，默认不提交、不进生产）。

回答产品化问题：个人经验闭环值几分？策展附带库能补回几分？

臂设计（旋钮 = `ask --user`，生产真实参数，不改任何生产代码）：
  veteran     users/ablation-veteran-probe   = linxiaoqi5111 全套沉淀的拷贝（养熟）
  coldstart   users/ablation-coldstart-probe = 空目录（新用户首日）
  shared_pack users/ablation-shared-probe    = 策展后的方法论附带库（13 卡 + 7 纠偏）

读数（以 coldstart 为基线）：
  veteran − coldstart  = 个人闭环全家桶贡献
  shared  − coldstart  = 附带库贡献（产品「数据库附带」的价值）
  veteran − shared     = 附带库距离养熟还差几分

题集/盲评/聚合数学复用 run_quality_ablation（同 rubric 同判官同方差纪律，
|Δ| ≲ 2.4/20 视为噪声底）。judge 只见问题+答案，不见臂标签。

用法：
  . <(grep '^export ' ~/.local/bin/start-finance-workbench)
  .venv-workbench/bin/python scripts/exp_user_memory_diff.py --max-questions 1   # smoke
  .venv-workbench/bin/python scripts/exp_user_memory_diff.py                     # 全量 6 题
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.run_quality_ablation import (  # noqa: E402
    QUESTIONS,
    RUBRIC_DIMENSIONS,
    Question,
    judge_answer,
    load_questions_file,
    require_llm_ready,
)

ARMS: dict[str, str] = {
    "veteran": "ablation-veteran-probe",
    "coldstart": "ablation-coldstart-probe",
    "shared_pack": "ablation-shared-probe",
}
BASELINE_ARM = "coldstart"


def run_ask_as_user(
    question: Question,
    *,
    user: str,
    exports_dir: str,
    timeout: float,
) -> dict[str, object]:
    """与 run_quality_ablation.run_ask 同构，唯一差别：--user 参数化。"""

    cmd = [
        sys.executable,
        "-m",
        "intelligence.cli",
        "ask",
        question.text,
        "--date",
        question.as_of,
        "--compose",
        "--user",
        user,
        "--no-score",
        "--no-clarify",
        "--exports-dir",
        exports_dir,
    ]
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(os.environ),
            cwd=str(REPO),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"ask 超时（>{timeout}s）", "answer": ""}
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    answer = (proc.stdout or "").strip()
    if len(answer) < 200:
        return {
            "ok": False,
            "error": f"exit={proc.returncode} 答案过短({len(answer)}字) "
            f"stderr尾={(proc.stderr or '')[-300:]}",
            "answer": answer,
            "elapsed_sec": elapsed,
        }
    return {
        "ok": True,
        "answer": answer,
        "elapsed_sec": elapsed,
        "exit_code": proc.returncode,
        "lint_flagged": proc.returncode != 0,
    }


def aggregate_arms(answers: list[dict[str, object]]) -> dict[str, object]:
    """每臂 vs coldstart 基线，只聚合双方都 scored 的题（数学与消融台同构）。"""

    base_by_case = {str(r["case_id"]): r for r in answers if r["arm"] == BASELINE_ARM}
    out: dict[str, object] = {}
    for arm in ARMS:
        if arm == BASELINE_ARM:
            scored = [
                r for r in answers if r["arm"] == arm and (r.get("judge") or {}).get("scored")
            ]
            out[arm] = {
                "questions_scored": len(scored),
                "mean_total": (
                    round(sum(r["judge"]["total"] for r in scored) / len(scored), 3)
                    if scored
                    else None
                ),
            }
            continue
        rows = []
        for r in answers:
            if r["arm"] != arm:
                continue
            base = base_by_case.get(str(r["case_id"]))
            jr, jb = r.get("judge") or {}, (base or {}).get("judge") or {}
            if not (jr.get("scored") and jb.get("scored")):
                rows.append({"case_id": r["case_id"], "usable": False})
                continue
            rows.append(
                {
                    "case_id": r["case_id"],
                    "usable": True,
                    "coldstart_total": jb["total"],
                    "arm_total": jr["total"],
                    "delta_total": jr["total"] - jb["total"],
                    "delta_by_dim": {
                        d: jr["scores"][d] - jb["scores"][d] for d in RUBRIC_DIMENSIONS
                    },
                }
            )
        usable = [row for row in rows if row.get("usable")]
        out[arm] = {
            "questions_usable": len(usable),
            "questions_total": len(rows),
            "mean_total": (
                round(sum(row["arm_total"] for row in usable) / len(usable), 3)
                if usable
                else None
            ),
            "delta_vs_coldstart_total": (
                round(sum(row["delta_total"] for row in usable) / len(usable), 3)
                if usable
                else None
            ),
            "delta_by_dim": (
                {
                    d: round(sum(row["delta_by_dim"][d] for row in usable) / len(usable), 3)
                    for d in RUBRIC_DIMENSIONS
                }
                if usable
                else None
            ),
            "rows": rows,
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-questions", type=int, default=0, help="0=全部 6 题")
    parser.add_argument(
        "--questions-file", type=Path, default=None, help="自定义题集 JSON（[{case_id,text,as_of}]）"
    )
    parser.add_argument("--ask-timeout", type=float, default=420.0)
    parser.add_argument("--seed", type=int, default=20260828, help="盲评洗牌种子")
    parser.add_argument(
        "--exports-dir", default="/tmp/exp-user-memory-diff-exports", help="ask 产物隔离目录"
    )
    parser.add_argument("--output", default=None)
    parser.add_argument("--partial", default=None, help="增量落盘 JSONL（断点续跑用）")
    args = parser.parse_args()

    require_llm_ready()
    for probe in ARMS.values():
        probe_dir = REPO / "intelligence" / "users" / probe
        if not probe_dir.is_dir():
            raise SystemExit(f"探针目录缺失：{probe_dir}（先建探针再跑）")

    base_questions = (
        load_questions_file(args.questions_file) if args.questions_file else QUESTIONS
    )
    questions = base_questions[: args.max_questions] if args.max_questions else base_questions
    Path(args.exports_dir).mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = Path(
        args.output or REPO / "intelligence" / "eval" / "runs" / f"{ts}-user-memory-diff.json"
    )
    # 增量落盘（被打断不丢已花的 LLM 调用）+ 断点续跑（重启跳过已完成格）。
    partial_path = Path(args.partial or REPO / "intelligence" / "eval" / "runs" / "user-memory-diff.partial.jsonl")
    answers: list[dict[str, object]] = []
    done: set[tuple[str, str]] = set()
    if partial_path.exists():
        for line in partial_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            answers.append(row)
            done.add((str(row["case_id"]), str(row["arm"])))
        if done:
            print(f"[resume] 从 {partial_path} 续跑，已完成 {len(done)} 格", flush=True)

    # 1) 串行跑 ask（避免 DuckDB 单写锁与资源争抢；顺序 = 题 × 臂）
    for q in questions:
        for arm, probe_user in ARMS.items():
            if (q.case_id, arm) in done:
                continue
            print(f"[ask] {q.case_id} × {arm} (user={probe_user}) ...", flush=True)
            res = run_ask_as_user(
                q, user=probe_user, exports_dir=args.exports_dir, timeout=args.ask_timeout
            )
            status = "ok" if res.get("ok") else f"FAIL: {res.get('error')}"
            print(f"[ask] {q.case_id} × {arm} → {status} ({res.get('elapsed_sec', 0):.0f}s)", flush=True)
            row = {
                "case_id": q.case_id,
                "arm": arm,
                "probe_user": probe_user,
                **res,
            }
            answers.append(row)
            with partial_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 2) 盲评：按种子洗牌防位置效应；judge 不见臂标签
    judge_order = [i for i, r in enumerate(answers) if r.get("ok")]
    random.Random(args.seed).shuffle(judge_order)
    q_by_id = {q.case_id: q for q in questions}
    for idx in judge_order:
        r = answers[idx]
        print(f"[judge] {r['case_id']} (盲评) ...", flush=True)
        verdict = judge_answer(q_by_id[str(r["case_id"])], str(r["answer"]))
        r["judge"] = verdict
    for r in answers:
        if not r.get("ok"):
            r["judge"] = {"scored": False, "reason": r.get("error", "ask 失败")}

    # 3) 聚合 + 落盘（答案全文保留，供 rejudge / 人工复核）
    aggregates = aggregate_arms(answers)
    payload = {
        "experiment": "user-memory-three-arm-diff",
        "ts": ts,
        "seed": args.seed,
        "arms": ARMS,
        "baseline_arm": BASELINE_ARM,
        "questions": [q.case_id for q in questions],
        "noise_floor_note": "沿用 eval-harness-variance-governance：|Δ|≲2.4/20 视为噪声底",
        "aggregates": aggregates,
        "answers": answers,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 三臂差分（以 coldstart 为基线）=====")
    for arm, agg in aggregates.items():
        if arm == BASELINE_ARM:
            print(f"{arm}: mean={agg['mean_total']} scored={agg['questions_scored']}")
        else:
            print(
                f"{arm}: mean={agg['mean_total']} Δ vs coldstart={agg['delta_vs_coldstart_total']} "
                f"(usable {agg['questions_usable']}/{agg['questions_total']})"
            )
    print(f"\n台账：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
