#!/usr/bin/env python3
"""研究员拍估值 最终稿质检门（exit-code 门）。

定位：researcher-valuation skill 的硬关卡，体例同
stock-deep-dive/scripts/answer_lint.py：按「维度 → 同义关键词组」做覆盖率匹配，
命中任一关键词即算覆盖；目标是拦「整个视角漏掉」，不是拦措辞。

额外红线：出现单点目标价句式（如"目标价 X 元"）直接 FAIL——
契约只允许条件化的估值区间。

用法::

    python3 skills/researcher-valuation/scripts/valuation_lint.py <answer.md>
    python3 skills/researcher-valuation/scripts/valuation_lint.py --list-dims

退出码 0 = 可交付，1 = 有缺失维度或触发红线，2 = 用法错误。
只读脚本：不抓数据、不写任何库。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 每个维度：(维度名, 说明, [关键词组——命中任一即覆盖])
_DIMS: list[tuple[str, str, list[str]]] = [
    (
        "valuation_status",
        "估值现状：PE/PS/EV 分位（历史 + 同业横截面）",
        ["PE", "PS", "EV", "市盈率", "市销率", "分位", "估值水平", "估值现状"],
    ),
    (
        "peer_band",
        "可比公司估值带：同链/同商业模式区间",
        ["可比公司", "估值带", "同业", "可比集", "同类公司", "对标"],
    ),
    (
        "implied_expectation",
        "隐含增长率反推：市场已经 price in 了多少",
        ["隐含", "price in", "反推", "已计入", "已定价", "隐含增速"],
    ),
    (
        "scenario_table",
        "情景估值表：悲观/中性/乐观 + 每情景可验证条件",
        ["悲观", "中性", "乐观", "情景", "三种情形", "分情景"],
    ),
    (
        "evidence_audit",
        "证据审计：硬数据 vs 研报推断（L1 降权）与缺口",
        ["硬证据", "硬数据", "研报推断", "L1", "证据缺口", "证据审计", "数据缺口"],
    ),
    (
        "conditional_conclusion",
        "条件化结论：升级/降级/证伪条件，不许单一定论",
        ["如果", "若", "触发条件", "一旦", "证伪", "升级条件", "降级"],
    ),
]

# 单点目标价红线：契约禁止输出"目标价 X 元"式结论
_TARGET_PRICE_RE = re.compile(r"目标价[^，。;\n]{0,12}?\d+(?:\.\d+)?\s*元")


def lint(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """返回 (缺失维度列表, 红线违规列表)；两者皆空 = 可交付。"""
    missing = [
        (name, desc)
        for name, desc, keywords in _DIMS
        if not any(kw in text for kw in keywords)
    ]
    violations = [
        f"单点目标价红线：检测到「{m.group(0)}」——只能给条件化估值区间"
        for m in _TARGET_PRICE_RE.finditer(text)
    ]
    return missing, violations


def main() -> int:
    parser = argparse.ArgumentParser(description="研究员拍估值最终稿质检门")
    parser.add_argument("answer", nargs="?", help="最终稿 markdown 文件路径")
    parser.add_argument("--list-dims", action="store_true", help="列出全部维度后退出")
    args = parser.parse_args()

    if args.list_dims:
        for name, desc, _ in _DIMS:
            print(f"  - {name}: {desc}")
        return 0

    if not args.answer:
        print("用法错误：缺少最终稿文件路径（或用 --list-dims）", file=sys.stderr)
        return 2
    path = Path(args.answer)
    if not path.is_file():
        print(f"用法错误：文件不存在 {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    missing, violations = lint(text)
    total = len(_DIMS)
    covered = total - len(missing)

    if missing or violations:
        if missing:
            print(f"MISSING ({covered}/{total} 维度覆盖):")
            for name, desc in missing:
                print(f"  - {name}: {desc}")
        for v in violations:
            print(f"VIOLATION: {v}")
        print("\n按缺失维度补写/删除违规句后重跑本脚本；两轮仍不过 → 答案开头标注低置信再交付。")
        return 1

    print(f"OK: {covered}/{total} 维度全覆盖且无红线违规，可交付。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
