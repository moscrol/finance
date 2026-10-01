#!/usr/bin/env python3
"""路由改写稳定性探针：同一道题换种说法，题型判定还一样吗？只读、不调模型。

动机（2026-10-01 质检 P1）：8792 栈输在「没见过的改写题」上（react 0.857 vs
8792 0.567），而题型判定是正则。本脚本把 uq15 原题和 ``route_paraphrase_v1.jsonl``
里的改写（口语 / 调序 / 极简各一条）都送进生产同款的 ``QueryResolver.resolve``，报：

- consistency：改写题的 question_type 与原题一致的比例（按 style 分开）；
- fallback：落进兜底 ``general_finance_qa`` 的比例（原题、改写分开）；
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

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "intelligence" / "eval" / "cases"
FALLBACK = "general_finance_qa"


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(seeds_path: Path, paraphrases_path: Path) -> dict:
    from intelligence.services.query_resolution import QueryResolver

    resolver = QueryResolver()

    def route(question: str) -> tuple[str, bool]:
        resolution = resolver.resolve(question)
        return resolution.envelope.question_type, resolution.anchor is not None

    seeds = {row["id"]: row["question"] for row in _load_jsonl(seeds_path)}
    seed_route: dict[str, str] = {}
    anchors = 0
    for seed_id, question in seeds.items():
        seed_route[seed_id], anchored = route(question)
        anchors += anchored
    by_style: dict[str, Counter] = defaultdict(Counter)
    mismatches = []
    para_fallback = 0
    rows = _load_jsonl(paraphrases_path)
    for row in rows:
        qt, anchored = route(row["question"])
        anchors += anchored
        para_fallback += qt == FALLBACK
        expected = seed_route[row["seed"]]
        same = qt == expected
        by_style[row["style"]]["same" if same else "diff"] += 1
        if not same:
            mismatches.append({"seed": row["seed"], "style": row["style"], "seed_type": expected, "paraphrase_type": qt})
    total_same = sum(c["same"] for c in by_style.values())
    return {
        "seeds": len(seeds),
        "paraphrases": len(rows),
        "anchor_hits": anchors,
        "consistency": round(total_same / len(rows), 3) if rows else None,
        "consistency_by_style": {s: round(c["same"] / (c["same"] + c["diff"]), 3) for s, c in sorted(by_style.items())},
        "seed_fallback_rate": round(sum(v == FALLBACK for v in seed_route.values()) / len(seeds), 3),
        "paraphrase_fallback_rate": round(para_fallback / len(rows), 3) if rows else None,
        "seed_routes": seed_route,
        "mismatches": mismatches,
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
    for m in report["mismatches"]:
        print(f"  ✗ {m['seed']} [{m['style']}] {m['seed_type']} → {m['paraphrase_type']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
