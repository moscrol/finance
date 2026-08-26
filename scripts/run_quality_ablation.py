#!/usr/bin/env python3
"""质量层消融：默认盒 vs 盒减一颗，真实 LLM 答案 + 盲评 rubric，输出组件边际贡献。

开关板第 0-3 步只回答「这颗拧得动吗」（结构层）；本脚本回答「关了这颗，答案差多少分」
——设计稿预留的那份「另一份评测」（质量棘轮）。两者刻意分开：结构读数用 scripted
模型零成本可重复，质量读数要花真 LLM 调用，混在一份 artifact 里会互相污染。

臂设计：每题一个**共享基线臂**（默认全开）+ 每颗组件一个关断臂。关法用组件的
**真实生产旋钮**（env / CLI flag），不经过开关板（生产不读表）：

    reading-baseline   env FINANCE_READING_BASELINE=0   （判读基线整段不注入）
    evidence-judge     env ASK_EVIDENCE_JUDGE=off       （证据裁判关闭）
    kb-rag             flag --no-wiki-rag               （知识库 W 源关闭）

评审：每份答案**独立盲评**——judge 只见问题+答案，不见臂标签；评审顺序按种子洗牌，
防止位置效应。rubric 复用 capability_monotonicity 的五维 0-4
（directness / coverage / relevance / truth_boundary / usefulness），总分 sum/20。
judge 输出解析失败 = 该份记 unscored，不编造、不计入聚合。

前置（fail-closed）：需要 LLM key（建议 `. <(grep '^export ' \
~/.local/bin/start-finance-workbench)` 继承生产 provider 链与 FINANCE_WS /
KNOWLEDGE_WIKI 数据根）；无 key 直接退出，绝不产出模板答案冒充读数。

用法：
    python3 scripts/run_quality_ablation.py --dry-run          # 只打印执行计划
    python3 scripts/run_quality_ablation.py                    # 三颗 × 六题全跑
    python3 scripts/run_quality_ablation.py --components kb-rag --max-questions 2
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

RUBRIC_DIMENSIONS = ("directness", "coverage", "relevance", "truth_boundary", "usefulness")
_JUDGE_ANSWER_CHARS = 6000  # 声明式截断：限定语在 prompt 里排在答案之前

# 关断臂用生产旋钮，与开关板种子表的 close_via 一致（表是登记，这里是执行）。
COMPONENTS: dict[str, dict[str, object]] = {
    "reading-baseline": {
        "env": {"FINANCE_READING_BASELINE": "0"},
        "flags": (),
        "close_via": "env:FINANCE_READING_BASELINE=0",
    },
    "evidence-judge": {
        "env": {"ASK_EVIDENCE_JUDGE": "off"},
        "flags": (),
        "close_via": "env:ASK_EVIDENCE_JUDGE=off",
    },
    "kb-rag": {
        "env": {},
        "flags": ("--no-wiki-rag",),
        "close_via": "flag:--no-wiki-rag",
    },
}


@dataclass(frozen=True)
class Question:
    case_id: str
    text: str
    as_of: str


# 前五道与 capability_monotonicity 默认题集同源（含 as_of 锚定，跨臂可比）；
# 第六道补题材类：kb-rag / reading-baseline 在该题型上最该发力。
QUESTIONS: tuple[Question, ...] = (
    Question("rebound-duration", "昨天的反弹能持续多久（只讨论 A 股整体市场，不讨论个股）", "2026-07-22"),
    Question("index-rebound-space", "科创50你认为反弹空间有多少", "2026-07-22"),
    Question("ruihuatai-valuation", "瑞华泰的合理估值", "2026-07-22"),
    Question("weekly-market-cause", "这一周行情下跌的主要原因是什么", "2026-07-22"),
    Question("current-mainline", "目前市场的主线是什么", "2026-07-22"),
    Question("theme-liquid-cooling", "液冷服务器这个题材现在处于什么阶段", "2026-07-22"),
)

_JUDGE_SYSTEM = (
    "你是金融研究答案的盲评审。你只看到问题和一份答案，不知道它出自哪个系统配置。"
    "按五个维度各打 0-4 分（0=缺失或错误，1=严重不足，2=部分达标，3=基本完整，4=完全达标）：\n"
    "directness=是否直接回答了问题；coverage=关键面是否覆盖（数据/证据/反面/验证点）；"
    "relevance=内容是否切题不注水；truth_boundary=是否诚实标注数据边界与不确定性、无编造痕迹；"
    "usefulness=对做研究决策的人是否可用。\n"
    '严格输出 JSON：{"directness":0,"coverage":0,"relevance":0,"truth_boundary":0,'
    '"usefulness":0,"justification":"一句话"}'
)


def _fail(msg: str) -> "SystemExit":
    return SystemExit(f"❌ {msg}")


def require_llm_ready() -> None:
    from intelligence.services import llm_refine

    if not llm_refine.detect_providers():
        raise _fail(
            "未配置 LLM key——质量臂不许用模板答案冒充读数。"
            "先 `. <(grep '^export ' ~/.local/bin/start-finance-workbench)` 再跑。"
        )


def run_ask(
    question: Question,
    *,
    extra_env: dict[str, str],
    extra_flags: tuple[str, ...],
    exports_dir: str,
    timeout: float,
) -> dict[str, object]:
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
        "quality-ablation",
        "--no-score",
        # 澄清短路会用 2 秒返回一句反问冒充答案，两臂都短路时分差恒 0（假读数）。
        "--no-clarify",
        "--exports-dir",
        exports_dir,
        *extra_flags,
    ]
    env = {**os.environ, **extra_env}
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(REPO),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"ask 超时（>{timeout}s）", "answer": ""}
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    answer = (proc.stdout or "").strip()
    # answer_lint 质检门用非零退出码表达「已交卷但标低置信」——那是答案的属性，
    # 不是失败；判失败会把整臂丢掉。只有「没有实质答案」才算失败。
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


def _parse_judge_payload(payload: object) -> dict[str, object] | None:
    """严格解析五维打分；任何缺失/越界返回 None（调用方决定重试或记 unscored）。"""

    if not isinstance(payload, dict):
        return None
    scores: dict[str, int] = {}
    for dim in RUBRIC_DIMENSIONS:
        try:
            value = int(payload.get(dim))
        except (TypeError, ValueError):
            return None
        if not 0 <= value <= 4:
            return None
        scores[dim] = value
    return {
        "scored": True,
        "scores": scores,
        "total": sum(scores.values()),
        "normalized": round(sum(scores.values()) / 20.0, 4),
        "justification": str(payload.get("justification") or "")[:200],
    }


def judge_answer(question: Question, answer: str, *, attempts: int = 2) -> dict[str, object]:
    """盲评一份答案；解析失败重试一次（带更硬的格式提示）。

    首轮实测：12k 字答案的评审输出偶发非 JSON，theme 题因此整题报废
    （基线未评 = 三个组件全部失去该题）。重试一次能救回大多数瞬时格式失误；
    仍失败则记 unscored——绝不编造分数。
    """

    from intelligence.services import llm_refine

    body = answer
    truncated = False
    if len(body) > _JUDGE_ANSWER_CHARS:
        body = body[:_JUDGE_ANSWER_CHARS]
        truncated = True
    header = "（以下答案已按预算截断，只保留开头部分）\n" if truncated else ""
    base_prompt = f"问题：{question.text}\n\n{header}答案：\n{body}"
    last_reason = "未尝试"
    for attempt in range(max(1, attempts)):
        prompt = base_prompt
        if attempt > 0:
            prompt = (
                "上一次输出无法解析。这次**只输出 JSON 对象本身**，"
                "不要任何解释、markdown 围栏或其他文字。\n\n" + base_prompt
            )
        content, _provider, reason = llm_refine.complete(
            [
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            timeout=90.0,
            temperature=0.1,
        )
        if content is None:
            # 无 key / 预算不足：重试同样会失败，直接放弃。
            return {"scored": False, "reason": reason, "attempts": attempt + 1}
        parsed = _parse_judge_payload(llm_refine._extract_json(content))
        if parsed is not None:
            parsed["attempts"] = attempt + 1
            return parsed
        last_reason = "judge 输出无法解析为合法五维 JSON"
    return {"scored": False, "reason": last_reason, "attempts": max(1, attempts)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--components", default="all", help="all 或逗号分隔的组件名")
    parser.add_argument("--max-questions", type=int, default=len(QUESTIONS))
    parser.add_argument("--ask-timeout", type=float, default=420.0)
    parser.add_argument("--seed", type=int, default=20260826, help="盲评洗牌种子")
    parser.add_argument(
        "--exports-dir",
        default=str(Path(os.environ.get("FINANCE_WS", REPO)) / "market_feature_store" / "exports"),
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="只打印执行计划，不调任何 LLM")
    args = parser.parse_args()

    if args.components == "all":
        component_ids = list(COMPONENTS)
    else:
        component_ids = [c.strip() for c in args.components.split(",") if c.strip()]
        unknown = [c for c in component_ids if c not in COMPONENTS]
        if unknown:
            raise _fail(f"未知组件：{unknown}（可选：{', '.join(COMPONENTS)}）")

    questions = QUESTIONS[: max(1, args.max_questions)]
    plan = [("baseline", None, q) for q in questions] + [
        (cid, COMPONENTS[cid], q) for cid in component_ids for q in questions
    ]
    print(f"[plan] 基线 {len(questions)} 答 + 关断 {len(component_ids)}×{len(questions)} 答，"
          f"共 {len(plan)} 次 ask + 盲评")
    if args.dry_run:
        for arm, spec, q in plan:
            knob = spec["close_via"] if spec else "默认全开"
            print(f"  {arm:<18} {q.case_id:<22} {knob}")
        return 0

    require_llm_ready()

    answers: list[dict[str, object]] = []
    for arm, spec, q in plan:
        extra_env = dict(spec["env"]) if spec else {}
        extra_flags = tuple(spec["flags"]) if spec else ()
        print(f"[ask] {arm} × {q.case_id} …", flush=True)
        result = run_ask(
            q,
            extra_env=extra_env,
            extra_flags=extra_flags,
            exports_dir=args.exports_dir,
            timeout=args.ask_timeout,
        )
        answers.append({"arm": arm, "case_id": q.case_id, **result})
        print(
            f"       {'ok' if result.get('ok') else '失败: ' + str(result.get('error'))} "
            f"({result.get('elapsed_sec', 0):.0f}s, {len(str(result.get('answer') or ''))} 字)",
            flush=True,
        )

    # 盲评：洗牌后逐份独立打分，judge 不见 arm 标签。
    order = list(range(len(answers)))
    random.Random(args.seed).shuffle(order)
    by_case = {q.case_id: q for q in questions}
    for idx in order:
        rec = answers[idx]
        if not rec.get("ok"):
            rec["judge"] = {"scored": False, "reason": "答案臂失败，未送评"}
            continue
        print(f"[judge] #{idx}（盲）…", flush=True)
        rec["judge"] = judge_answer(by_case[str(rec["case_id"])], str(rec["answer"]))

    # 聚合：每颗组件 = 平均(关断臂总分) − 平均(同题基线总分)，只聚合双方都 scored 的题。
    baseline_by_case = {
        str(r["case_id"]): r for r in answers if r["arm"] == "baseline"
    }
    aggregates: dict[str, object] = {}
    for cid in component_ids:
        rows = []
        for r in answers:
            if r["arm"] != cid:
                continue
            base = baseline_by_case.get(str(r["case_id"]))
            jr, jb = r.get("judge") or {}, (base or {}).get("judge") or {}
            if not (jr.get("scored") and jb.get("scored")):
                rows.append({"case_id": r["case_id"], "usable": False})
                continue
            delta_total = jr["total"] - jb["total"]
            rows.append(
                {
                    "case_id": r["case_id"],
                    "usable": True,
                    "baseline_total": jb["total"],
                    "ablated_total": jr["total"],
                    "delta_total": delta_total,
                    "delta_by_dim": {
                        d: jr["scores"][d] - jb["scores"][d] for d in RUBRIC_DIMENSIONS
                    },
                }
            )
        usable = [row for row in rows if row.get("usable")]
        aggregates[cid] = {
            "close_via": COMPONENTS[cid]["close_via"],
            "questions_usable": len(usable),
            "questions_total": len(rows),
            # 边际贡献 = 关掉后掉的分（正数=组件在涨分）。
            "marginal_contribution_total": (
                round(-sum(row["delta_total"] for row in usable) / len(usable), 3)
                if usable
                else None
            ),
            "marginal_by_dim": (
                {
                    d: round(-sum(row["delta_by_dim"][d] for row in usable) / len(usable), 3)
                    for d in RUBRIC_DIMENSIONS
                }
                if usable
                else None
            ),
            "rows": rows,
        }

    artifact = {
        "kind": "quality_ablation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "judge_note": "同一 judge 评所有臂，标签盲；分差可比，绝对分不可跨 judge 比",
        "questions": [q.__dict__ for q in questions],
        "answers": answers,
        "aggregates": aggregates,
    }
    output = args.output or (
        REPO
        / "intelligence"
        / "eval"
        / "runs"
        / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-quality-ablation.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n== 组件边际贡献（关掉后平均掉分，正=在涨分）==")
    for cid, agg in aggregates.items():
        print(
            f"  {cid:<18} Δ={agg['marginal_contribution_total']}"
            f"（可用 {agg['questions_usable']}/{agg['questions_total']} 题）"
            f" 分维度={agg['marginal_by_dim']}"
        )
    print(f"\n收据 → {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
