#!/usr/bin/env python3
"""量表达契约有没有真进 prompt，以及它在 prompt 里占多大比重。

防的失败形状：**表达契约「接线完成」但不变成正文结构**。这类缺口有四层，逐层排除
才能定位，只看答案里有没有标题会把四层混成一句「没生效」——

1. 意图门没开（`*_guidance_for_query` 返回空）；
2. 入口没走合成分支（`cli ask` 默认 `compose=False`，契约注入点在
   `ask.py` 的 `if options.compose:` 里面，那条路一次模型都不调）；
3. 预算不够，合成抛 `LLMDeadlineExceeded` 降级模板（`--llm-timeout` 默认 60 秒，
   还要在 brief/composer/judge 之间分）；
4. 契约进了 prompt，但在长 prompt 里占比太低，模型按实质答对却不照格式。

本脚本一次分清 1、2、4：用 `compose=True, synthesize=False`（抄 Episode 编排器
`conversation_orchestrator.py` 的条件）只造 prompt、不调合成模型，然后在
`prepared_synthesis_messages` 里找标记并报占比。第 3 层看运行表头那句
「LLM 合成超过共享截止时间」。

2026-09-11 实测：定价二分契约 782 字，正门 prompt 27,958 字，占 2.8%，
五个标记全在 prompt 里，答案两段标题却都没出现。**占比是自变量**——台架里契约
占几分之一时模型 100% 照做，所以台架遵从率只能声明上界。

用法：

    python3 scripts/probe_contract_in_prompt.py "英维克涨这么多了还能追吗" \\
        --markers 产业证据变化,定价状态,无事前预期来源 --contract-chars 782
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", help="问句，用真实用户会打的那句，别简化")
    parser.add_argument(
        "--markers",
        required=True,
        help="逗号分隔的契约标记；用契约文本里的字面小标题，别用同义词",
    )
    parser.add_argument(
        "--contract-chars",
        type=int,
        default=0,
        help="契约文本字数（由 *_guidance_for_query 算），给了才报占比",
    )
    parser.add_argument("--dump", help="把 prompt 全文落到这个路径，便于人工读")
    parser.add_argument("--json", action="store_true", help="只打 JSON，便于脚本消费")
    args = parser.parse_args()

    from intelligence.services.ask import AskOptions, answer_query

    result = answer_query(
        AskOptions(query=args.query, compose=True, synthesize=False, use_llm=False)
    )
    messages = result.prepared_synthesis_messages or []
    blob = "\n".join(str(message.get("content", "")) for message in messages)
    markers = [marker.strip() for marker in args.markers.split(",") if marker.strip()]

    payload = {
        "query": args.query,
        "question_type": getattr(result.question_plan, "question_type", None),
        "message_count": len(messages),
        "prompt_chars": len(blob),
        "markers_in_prompt": {marker: (marker in blob) for marker in markers},
    }
    if args.contract_chars:
        payload["contract_chars"] = args.contract_chars
        payload["contract_share"] = round(args.contract_chars / max(len(blob), 1), 4)

    if args.dump:
        Path(args.dump).write_text(blob, encoding="utf-8")
        payload["dump"] = args.dump

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"question_type = {payload['question_type']!r}")
    print(f"prompt = {payload['prompt_chars']} 字（{payload['message_count']} 条消息）")
    if args.contract_chars:
        print(f"契约 = {args.contract_chars} 字，占 {payload['contract_share']:.2%}")
    for marker, present in payload["markers_in_prompt"].items():
        print(f"  {'✅' if present else '❌'} prompt 内含 {marker!r}")
    missing = [marker for marker, present in payload["markers_in_prompt"].items() if not present]
    if missing:
        print("\n标记不在 prompt 里 → 先查意图门与 include_*_guidance 开关，别怪模型。")
    else:
        print("\n标记都在 prompt 里 → 答案仍无结构的话，是占比/位置问题，不是接线问题。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
