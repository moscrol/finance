#!/usr/bin/env python3
"""补评：对 provider 故障期间未打分的答案重跑盲评，重算聚合。

**不重跑任何 ask（答案原样保留）；只补 judge。产出修正收据（原文件不覆盖）。**

起因（2026-08-26 干净轮 `20260826T143558Z`）：judge 链在夜里断了
（`zhipu:URLError / openai:URLError`），15 份答案里 7 份记 unscored。这不是内容
失败——答案本身跑出来了、正文完好——但聚合只算「双方都 scored」的题，于是
`reading-baseline` 的边际贡献落到 `questions_usable: 1/5`。**拿那份收据下结论，
读到的是 1 题的噪声，不是 5 题的读数。**

为什么补评合法而不是「洗数据」：原脚本第 15 行的设计是**每份答案独立盲评**
（judge 只见问题 + 答案，不见臂标签），所以单独补评 7 份与整轮一起评在统计上
等价——洗牌顺序只决定评审次序，不进入单份分数。答案文本 sha256 前后逐条断言
不变，补评动不了「答得怎么样」，只补上「谁给它打分」。

三条不许越的线（都在代码里 fail-closed，不靠自觉）：
  1. 原文件绝不覆盖：``--output`` 指向输入即退出。
  2. 已打分的分数绝不重评：只碰 ``scored != True`` 且有正文的行。
  3. 补评再失败仍记 unscored：不编造分数，不把「评不出来」写成「评过了」。

用法：
    python3 scripts/rejudge_quality_ablation.py --run intelligence/eval/runs/X.json --dry-run
    . <(grep '^export ' ~/.local/bin/start-finance-workbench)   # 继承生产 provider 链
    python3 scripts/rejudge_quality_ablation.py --run intelligence/eval/runs/X.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.run_quality_ablation import (  # noqa: E402
    RUBRIC_DIMENSIONS,
    Question,
    aggregate_components,
    judge_answer,
    require_llm_ready,
)


def _fail(msg: str) -> "SystemExit":
    return SystemExit(f"❌ {msg}")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_run(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("kind") != "quality_ablation":
        raise _fail(f"不是 quality_ablation 收据：{path}")
    for key in ("questions", "answers", "aggregates"):
        if key not in payload:
            raise _fail(f"收据缺 {key}：{path}")
    return payload


def pending_indices(answers: list[dict[str, object]]) -> list[int]:
    """待补评的行：答出来了、但没打上分。

    ``ok=False`` 的行没有答案正文（judge 记的是「答案臂失败，未送评」），补评它
    等于凭空造一份读数——那类缺口只能靠重跑 ask 补，不归本脚本。
    """

    pending = []
    for i, rec in enumerate(answers):
        judge = rec.get("judge") or {}
        if judge.get("scored"):
            continue
        if not rec.get("ok"):
            continue
        if not str(rec.get("answer") or "").strip():
            continue
        pending.append(i)
    return pending


def baseline_absolute(answers: list[dict[str, object]]) -> dict[str, object]:
    """基线臂绝对分均值——门控前后对比用的那个头条数字。

    ⚠️ 跨轮比较的成立条件：绝对分只在同一 judge 下可比（见收据 ``judge_note``）。
    跨 run 比 7.6 → 9.2 时，两轮的 judge 必须是同一条链、同一套 rubric，否则读的
    是 judge 差异不是产品差异。这里只负责算出这一轮的值并附上样本量。
    """

    scored = [
        rec["judge"]
        for rec in answers
        if rec.get("arm") == "baseline" and (rec.get("judge") or {}).get("scored")
    ]
    total_n = sum(1 for rec in answers if rec.get("arm") == "baseline")
    if not scored:
        return {"mean_total": None, "questions_scored": 0, "questions_total": total_n}
    return {
        "mean_total": round(sum(j["total"] for j in scored) / len(scored), 3),
        "questions_scored": len(scored),
        "questions_total": total_n,
        "by_dim": {
            d: round(sum(j["scores"][d] for j in scored) / len(scored), 3)
            for d in RUBRIC_DIMENSIONS
        },
        "max_total": 20,
    }


def assert_only_judge_changed(
    answers: list[dict[str, object]],
    answers_before: dict[int, str],
    judged_before: dict[int, str],
) -> None:
    """补评后除 judge 外一切未变——答案正文与既有分数逐条对账。

    调用方（``rejudge_artifact``）目前没有改写答案的路径，这层是**防以后长出
    路径**：哪天有人给 judge_fn 传了整条记录、或加了「补评顺手修一下答案」的
    捷径，这里会当场炸而不是静静地把读数换掉。
    """

    for i, rec in enumerate(answers):
        if _sha256_text(str(rec.get("answer") or "")) != answers_before.get(i):
            raise _fail(f"答案 #{i} 被改写了——补评只补 judge，绝不动答案")
    for i, snapshot in judged_before.items():
        current = json.dumps(answers[i].get("judge"), ensure_ascii=False, sort_keys=True)
        if current != snapshot:
            raise _fail(f"答案 #{i} 原有分数被改动了——补评只碰未打分的行")


def rejudge_artifact(
    artifact: dict[str, object],
    *,
    judge_fn,
    seed: int,
    source_path: Path,
    source_sha256: str,
    now: datetime | None = None,
) -> dict[str, object]:
    """纯函数核心：吃一份 run 收据，吐一份补评后的新收据。

    judge 从参数注入 → 测试用确定性桩跑，不打真 LLM。
    """

    answers = [dict(rec) for rec in artifact["answers"]]  # type: ignore[index]
    questions = {
        str(q["case_id"]): Question(str(q["case_id"]), str(q["text"]), str(q["as_of"]))
        for q in artifact["questions"]  # type: ignore[union-attr]
    }
    answers_before = {
        i: _sha256_text(str(rec.get("answer") or "")) for i, rec in enumerate(answers)
    }
    judged_before = {
        i: json.dumps(rec.get("judge"), ensure_ascii=False, sort_keys=True)
        for i, rec in enumerate(answers)
        if (rec.get("judge") or {}).get("scored")
    }

    pending = pending_indices(answers)
    # 补评内部同样洗牌：份数少时位置效应弱，但保持与主轮同一条纪律，且种子入收据。
    order = list(pending)
    random.Random(seed).shuffle(order)

    rejudged: list[dict[str, object]] = []
    still_unscored: list[dict[str, object]] = []
    for idx in order:
        rec = answers[idx]
        case_id = str(rec["case_id"])
        question = questions.get(case_id)
        if question is None:
            raise _fail(f"答案 #{idx} 的 case_id 不在题集里：{case_id}")
        previous = dict(rec.get("judge") or {})
        verdict = judge_fn(question, str(rec["answer"]))
        row = {
            "arm": rec.get("arm"),
            "case_id": case_id,
            "previous_reason": previous.get("reason"),
            "scored": bool(verdict.get("scored")),
            "total": verdict.get("total"),
            "provider": verdict.get("provider"),
        }
        if verdict.get("scored"):
            verdict = {**verdict, "rejudged": True, "previous_reason": previous.get("reason")}
            rec["judge"] = verdict
            rejudged.append(row)
        else:
            # 补评也没成：保留原始失败记录，只叠一层「补评又试过一次」的痕迹。
            rec["judge"] = {
                **previous,
                "rejudge_attempted": True,
                "rejudge_reason": verdict.get("reason"),
            }
            row["rejudge_reason"] = verdict.get("reason")
            still_unscored.append(row)

    assert_only_judge_changed(answers, answers_before, judged_before)

    component_ids = [cid for cid in artifact["aggregates"]]  # type: ignore[union-attr]
    aggregates = aggregate_components(answers, component_ids)
    stamp = (now or datetime.now(timezone.utc)).isoformat()

    providers = sorted({str(r["provider"]) for r in rejudged if r.get("provider")})
    return {
        "kind": "quality_ablation_rejudge",
        "generated_at": stamp,
        "source_run": str(source_path),
        "source_sha256": source_sha256,
        "source_generated_at": artifact.get("generated_at"),
        "seed": artifact.get("seed"),
        "rejudge_seed": seed,
        "judge_note": artifact.get("judge_note"),
        "judge_continuity": (
            f"本轮 {len(rejudged)} 份为事后补评（provider 故障后重跑），"
            f"补评 provider={providers or '未记录'}；"
            "主轮已打分那些的 provider 未入账（该字段本次才加），"
            "跨臂分差可比性建立在两次都走同一条已配置 provider 链的假设上。"
        ),
        "rejudged": rejudged,
        "still_unscored": still_unscored,
        "questions": artifact["questions"],
        "answers": answers,
        "aggregates_before": artifact["aggregates"],
        "aggregates": aggregates,
        "baseline_absolute": baseline_absolute(answers),
    }


def _print_diff(artifact: dict[str, object]) -> None:
    before = artifact["aggregates_before"]
    after = artifact["aggregates"]
    print("\n== 修正读数（补评前 → 补评后）==")
    for cid, agg in after.items():  # type: ignore[union-attr]
        old = before.get(cid, {})  # type: ignore[union-attr]
        print(
            f"  {cid:<18} Δ={old.get('marginal_contribution_total')} → "
            f"{agg['marginal_contribution_total']}"
            f"（可用 {old.get('questions_usable')}/{old.get('questions_total')} → "
            f"{agg['questions_usable']}/{agg['questions_total']} 题）"
        )
        print(f"                     分维度={agg['marginal_by_dim']}")
    base = artifact["baseline_absolute"]
    print(
        f"\n  基线绝对分 均值={base['mean_total']}/20"  # type: ignore[index]
        f"（{base['questions_scored']}/{base['questions_total']} 题已评）"  # type: ignore[index]
        "  ⚠️ 绝对分只在同一 judge 下可比，跨轮对比前先确认两轮 judge 同链"
    )
    still = artifact["still_unscored"]
    if still:
        print(f"\n  ⚠️ 仍未打分 {len(still)} 份（不计入聚合，未编造）：")
        for row in still:  # type: ignore[union-attr]
            print(f"     {row['arm']:<18} {row['case_id']:<22} {row.get('rejudge_reason')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="待补评的 quality_ablation 收据")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="修正收据路径（默认 <原名>-rejudge.json）；指向原文件会被拒绝",
    )
    parser.add_argument("--seed", type=int, default=20260827, help="补评洗牌种子")
    parser.add_argument("--dry-run", action="store_true", help="只列出待补评行，不调 LLM")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = args.run.resolve()
    raw = source.read_text(encoding="utf-8")
    artifact = load_run(source)
    answers = artifact["answers"]  # type: ignore[assignment]
    pending = pending_indices(answers)  # type: ignore[arg-type]

    print(f"[run] {source}")
    print(f"[plan] 共 {len(answers)} 份答案，待补评 {len(pending)} 份（只补 judge，不重跑 ask）")
    for idx in pending:
        rec = answers[idx]  # type: ignore[index]
        reason = str((rec.get("judge") or {}).get("reason") or "")[:60]
        print(f"  #{idx:<3} {rec['arm']:<18} {rec['case_id']:<22} 原因={reason}")
    if not pending:
        print("没有待补评的行——原收据已完整。")
        return 0
    if args.dry_run:
        return 0

    output = args.output or source.with_name(f"{source.stem}-rejudge.json")
    if output.resolve() == source:
        raise _fail("--output 指向原文件；修正收据必须另存，原始读数不可覆盖")

    require_llm_ready()
    result = rejudge_artifact(
        artifact,
        judge_fn=lambda q, a: judge_answer(q, a),
        seed=args.seed,
        source_path=source,
        source_sha256=_sha256_text(raw),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_diff(result)
    print(f"\n原始收据（未改动）→ {source}")
    print(f"修正收据 → {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
