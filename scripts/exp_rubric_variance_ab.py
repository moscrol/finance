#!/usr/bin/env python3
"""rubric 各版本的判官复评方差对照（一次性实验脚本，默认不提交、不进生产）。

回答一个此前只是[推断]的问题：**把 rubric 从抽象判据改写成可数锚点，判官的
复评方差真的更小吗？**

依据链：ai-agent-book ch6「Rubric 四准则 ④ 自包含评估」说该这么写；本仓
2026-08-01 实测（`eval-harness-variance-governance.md`）同判官下数值型断言翻转
0%、措辞型 67%。两者都支持「可核对的判据更稳」，但**都不是对这两版 rubric 的
直接测量**。本脚本补的就是这一刀。

设计：
- 判官与答案全部**钉死**，唯一变量是 rubric 版本。答案取自 2026-08-26 那轮的
  收据（不重新问问题，只花判官调用）。
- 每份答案在每个版本下重复盲评 N 次。文本逐字相同 → 真值 Δ 必为 0，
  观测到的散布就是该版本下的判官噪声。
- **调用顺序按种子打乱且两版交错**：判官/网关在几分钟里会漂，不交错的话
  「后跑的那版方差大」会被读成「那版 rubric 差」。

用法：
    . <(grep '^export ' ~/.local/bin/start-finance-workbench)
    export LLM_JUDGE_MODEL=gpt-5.6-sol      # 判官与合成模型分开
    .venv-workbench/bin/python scripts/exp_rubric_variance_ab.py --repeats 3
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.run_quality_ablation import (  # noqa: E402
    JUDGE_SYSTEMS,
    _JUDGE_OVERRIDE,
    Question,
    judge_noise_floor,
    judge_answer,
    resolve_judge,
)

# 源收据在**仓外的另一棵树**里（那轮实验的产物），所以从 home 推导而不是写死。
# 换机器 / 换树用 --source 覆盖。
DEFAULT_SOURCE = (
    Path.home()
    / "fwp-wt-capability-switchboard-main"
    / "intelligence/eval/runs/20260826T101858Z-quality-ablation.json"
)


def load_baseline_answers(path: Path) -> list[tuple[Question, str]]:
    """取源收据里**基线臂**且已打分的那些答案（关断臂不需要，测的是判官不是组件）。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = {
        str(q["case_id"]): Question(str(q["case_id"]), str(q["text"]), str(q["as_of"]))
        for q in payload["questions"]
    }
    out: list[tuple[Question, str]] = []
    for rec in payload["answers"]:
        if rec.get("arm") != "baseline" or not (rec.get("judge") or {}).get("scored"):
            continue
        question = questions.get(str(rec["case_id"]))
        if question is not None:
            out.append((question, str(rec["answer"])))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--repeats", type=int, default=3, help="每份答案每版重复评几次")
    parser.add_argument("--max-answers", type=int, default=0, help="0=全部")
    parser.add_argument("--seed", type=int, default=20260831)
    parser.add_argument(
        "--judge-independence", choices=("require", "allow-correlated"),
        default="allow-correlated",
        help="本实验测的是同判官下的复评散布，异构性不是成立条件；默认放行并如实记录",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path.home() / ".finance-runtime" / "rubric-variance-ab.json",
    )
    args = parser.parse_args()

    info = resolve_judge(require_independent=(args.judge_independence == "require"))
    _JUDGE_OVERRIDE["provider"] = info.pop("override")
    print(f"[judge] {info['judge']}  独立性={info['independence']}  合成={info['composer']}")

    answers = load_baseline_answers(args.source)
    if args.max_answers > 0:
        answers = answers[: args.max_answers]
    versions = sorted(JUDGE_SYSTEMS)
    calls = [
        (idx, version, rep)
        for idx in range(len(answers))
        for version in versions
        for rep in range(args.repeats)
    ]
    random.Random(args.seed).shuffle(calls)
    print(
        f"[plan] {len(answers)} 份答案 × {len(versions)} 版 × {args.repeats} 次 "
        f"= {len(calls)} 次判官调用（顺序已打乱交错）"
    )

    results: dict[str, dict[int, list[int]]] = {v: {} for v in versions}
    log: list[dict[str, object]] = []
    started = time.time()
    for n, (idx, version, rep) in enumerate(calls, start=1):
        question, answer = answers[idx]
        t0 = time.time()
        verdict = judge_answer(question, answer, rubric_version=version)
        elapsed = time.time() - t0
        ok = bool(verdict.get("scored"))
        if ok:
            results[version].setdefault(idx, []).append(int(verdict["total"]))
        print(
            f"  [{n:>3}/{len(calls)}] {version:<18} {question.case_id:<22} "
            f"#{rep + 1} {elapsed:5.1f}s "
            + (f"total={verdict['total']}" if ok else f"✗ {verdict.get('reason')}"),
            flush=True,
        )
        log.append(
            {
                "case_id": question.case_id,
                "rubric_version": version,
                "repeat": rep + 1,
                "scored": ok,
                "total": verdict.get("total") if ok else None,
                # 2026-08-31 质检点名：初版只存 total，导致「truth_boundary 从 3
                # 掉到 0、总分跳 4」是**反推**不是实测——而 current-mainline 的
                # 极差 6 超过单维满分 4，整段抖动不可能只来自那一维。存五维序列，
                # 下轮直接钉死是哪几维在动。
                "scores": verdict.get("scores") if ok else None,
                "pitfalls": verdict.get("pitfalls") if ok else None,
                "reason": None if ok else verdict.get("reason"),
                "elapsed_sec": round(elapsed, 2),
            }
        )

    floors: dict[str, dict[str, object]] = {}
    for version in versions:
        calibration = [
            {"case_id": answers[idx][0].case_id, "totals": totals}
            for idx, totals in sorted(results[version].items())
        ]
        floors[version] = judge_noise_floor(calibration)

    receipt = {
        "kind": "rubric_variance_ab",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_run": str(args.source),
        "seed": args.seed,
        "repeats": args.repeats,
        "judge": info,
        "elapsed_sec": round(time.time() - started, 1),
        "design_note": (
            "唯一变量是 rubric 版本：判官、答案文本、重复次数全部钉死，调用顺序打乱交错。"
            "测的是同一份文本重复盲评的散布（真值 Δ 必为 0）。"
        ),
        "independence_caveat": (
            "缺的是 grok-cli 这条**独立客户端**（余额耗尽 HTTP 402），不是跨家族本身："
            "本轮 composer=zhipu/glm-5.3、judge=gpt-5.6-sol，按 model_family() 是 "
            "glm vs gpt，**已跨家族**。收据里若出现 independence=weak，"
            "那是 14:49 旧分类器打的戳（家族判据 ec930c1e 14:52 才落）。"
            "异构性影响**分数效度**、不影响本实验测的**复评散布**；"
            "但样本只有一种判官配置，结论不可外推到别的判官。"
        ),
        "calls": log,
        "noise_floors": floors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("\n== 各版本的判官复评噪声 ==")
    for version in versions:
        floor = floors[version]
        if not floor.get("measured"):
            print(f"  {version:<18} 未测到：{floor.get('reason')}")
            continue
        spreads = [q["spread"] for q in floor["questions"] if q.get("usable")]
        print(
            f"  {version:<18} sd={floor['sd_judging']:<7} "
            f"单题Δ的sd={floor['sd_delta_single_question']:<7} "
            f"题数={floor['questions_measured']} "
            f"各题极差={spreads}"
        )
    measured = [v for v in versions if floors[v].get("measured")]
    if len(measured) >= 2:
        # 以第一版为基准两两比。初版写死 len==2，加了 v3 之后这段直接不打印，
        # 等于三版对照跑完却拿不到比值（2026-08-31 质检点名）。
        base = measured[0]
        sa = float(floors[base]["sd_judging"])
        n_a = int(floors[base]["questions_measured"])
        for other in measured[1:]:
            sb = float(floors[other]["sd_judging"])
            print(f"\n  sd({other}) / sd({base}) = {sb / sa:.3f}（<1 表示 {other} 更稳）")
        print(
            f"  ⚠ 样本量 {n_a} 题 × {args.repeats} 次：这是方向性读数，"
            "不足以对方差比做显著性判定。"
        )
    print(f"\n收据 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
