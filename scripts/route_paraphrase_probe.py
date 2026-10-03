#!/usr/bin/env python3
"""路由改写稳定性探针：同一道题换种说法，题型判定还一样吗？只读、不调模型。

动机（2026-10-01 质检 P1）：8792 栈输在「没见过的改写题」上（react 0.857 vs
8792 0.567），而题型判定是正则。本脚本把 uq15 原题和 ``route_paraphrase_v1.jsonl``
里的改写（口语 / 调序 / 极简各一条）都送进生产同款的 ``decide_turn``（确定性层，
不调 LLM），以「lane/question_type」为路由身份，报：

- consistency：改写题的 question_type 与原题一致的比例（按 style 分开）；
- fallback：落进兜底 research/``general_finance_qa`` 的比例（原题、改写分开）；
- clarify：被反问用户的次数（题面都自带主体，理想为 0）；
- llm_fallback：确定性层认不出、要交给 LLM 控制器决定的次数（弱模型当控制器时的高风险面）；
- 每条不一致的明细（原题型 → 改写题型）。

一致不等于正确：原题本身也可能路由错了，所以同时报兜底率。**必须在有知识库的
机器上跑**（实体锚点要查库）；沙箱里锚点全空，数字会严重失真——输出里会打印
锚点命中数，命中为 0 时请别引用结果。
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
# 直接 `python3 scripts/xxx.py` 运行时 sys.path[0] 是 scripts/，intelligence 包不可见。
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
CASES = REPO / "intelligence" / "eval" / "cases"
FALLBACK = "general_finance_qa"


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(seeds_path: Path, paraphrases_path: Path) -> dict:
    from intelligence.services.query_resolution import QueryResolver
    from intelligence.services.turn_controller import decide_turn

    resolver = QueryResolver()

    def _no_llm(*_args, **_kwargs):  # 探针只量确定性层；需要 LLM 的分支记为 llm_fallback
        raise RuntimeError("route probe: controller LLM disabled")

    def route(question: str) -> tuple[str, bool]:
        """返回「用户实际会走的路」：decide_turn 的 lane/question_type。

        只看信封 question_type 会量错层：日期复盘的信封是 general_finance_qa，
        真正把它送进日报工作流的是 turn_controller（2026-10-01 Mac 首轮读数）。
        """
        resolution = resolver.resolve(question)
        decision = decide_turn(question, llm_complete=_no_llm, resolver=resolver)
        label = f"{decision.lane}/{decision.question_type}"
        if decision.llm_failure_reason:
            label += "(llm_fallback)"
        reasons[label] = decision.reason
        return label, resolution.anchor is not None

    reasons: dict[str, str] = {}

    seeds = {row["id"]: row["question"] for row in _load_jsonl(seeds_path)}
    seed_route: dict[str, str] = {}
    anchors = 0
    for seed_id, question in seeds.items():
        seed_route[seed_id], anchored = route(question)
        anchors += anchored
    by_style: dict[str, Counter] = defaultdict(Counter)
    mismatches = []
    para_fallback = 0
    para_labels: list[str] = []
    rows = _load_jsonl(paraphrases_path)
    for row in rows:
        qt, anchored = route(row["question"])
        para_labels.append(qt)
        anchors += anchored
        para_fallback += qt.removesuffix("(llm_fallback)") == f"research/{FALLBACK}"
        expected = seed_route[row["seed"]]
        same = qt == expected
        by_style[row["style"]]["same" if same else "diff"] += 1
        if not same:
            mismatches.append({"seed": row["seed"], "style": row["style"], "seed_type": expected, "paraphrase_type": qt})
    total_same = sum(c["same"] for c in by_style.values())
    all_labels = list(seed_route.values()) + para_labels
    clarify = sum(label.startswith("clarify/") for label in all_labels)
    llm_fallback = sum(label.endswith("(llm_fallback)") for label in all_labels)
    return {
        "seeds": len(seeds),
        "paraphrases": len(rows),
        "anchor_hits": anchors,
        "consistency": round(total_same / len(rows), 3) if rows else None,
        "consistency_by_style": {s: round(c["same"] / (c["same"] + c["diff"]), 3) for s, c in sorted(by_style.items())},
        "clarify_count": clarify,
        "llm_fallback_count": llm_fallback,
        "routed_total": len(all_labels),
        "seed_fallback_rate": round(sum(v.removesuffix("(llm_fallback)") == f"research/{FALLBACK}" for v in seed_route.values()) / len(seeds), 3) if seeds else None,
        "paraphrase_fallback_rate": round(para_fallback / len(rows), 3) if rows else None,
        "seed_routes": seed_route,
        "mismatches": mismatches,
        "reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=Path, default=CASES / "uq15_questions.jsonl")
    parser.add_argument("--paraphrases", type=Path, default=CASES / "route_paraphrase_v1.jsonl")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run(args.seeds, args.paraphrases)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"原题 {report['seeds']} / 改写 {report['paraphrases']} / 实体锚点命中 {report['anchor_hits']}")
    if not report["anchor_hits"]:
        print("  ⚠ 锚点命中为 0：知识库不可用，以下数字不可引用")
    print(f"  改写一致率 {report['consistency']}  按风格 {report['consistency_by_style']}")
    print(f"  兜底率 原题 {report['seed_fallback_rate']} / 改写 {report['paraphrase_fallback_rate']}")
    print(f"  clarify（反问用户）{report['clarify_count']}/{report['routed_total']}（题面都自带主体，理想为 0）")
    print(f"  确定性层认不出、交给 LLM 控制器 {report['llm_fallback_count']}/{report['routed_total']}（弱模型当控制器时的高风险面）")
    print("  原题实际路由:")
    for seed_id, label in report["seed_routes"].items():
        print(f"    {seed_id} {label}  ← {report['reasons'].get(label, '')[:40]}")
    for m in report["mismatches"]:
        print(f"  ✗ {m['seed']} [{m['style']}] {m['seed_type']} → {m['paraphrase_type']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
