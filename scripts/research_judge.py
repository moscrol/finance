#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Direct execution needs the repository root on sys.path before project imports.
from intelligence.services.research_judge import judge_research_target  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="判断公司/题材当前证据层级和下一步动作。")
    parser.add_argument("target", help="公司名或题材名，例如：铭普光磁、贝达药业、光刻胶")
    parser.add_argument("--concept", help="限定关联概念，例如：AI服务器电源", default=None)
    parser.add_argument("--kb-wiki", help="知识库 wiki 根目录，默认读取项目配置", default=None)
    parser.add_argument("--max-evidence", type=int, default=8, help="最多输出多少条已有证据")
    parser.add_argument("--market-signal", action="store_true", help="手动标记已有盘面触发信号")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = judge_research_target(
        args.target,
        kb_wiki=args.kb_wiki,
        concept=args.concept,
        max_evidence=args.max_evidence,
        has_market_signal=args.market_signal,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
