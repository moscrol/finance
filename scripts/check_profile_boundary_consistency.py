#!/usr/bin/env python3
"""画像里「能不能给买卖/策略」的口径，必须三处一致。

## 为什么需要这个检查

同一份画像可能在 anti_patterns、reasoning_patterns 和 voice_guidance
各自声明输出边界。边界按调用方身份与授权用途分档时，这三处应同步。
若只改其中一处，画像就会自相矛盾——而矛盾的画像比过时的画像更糟：
下游取到哪一条取决于它读了哪个字段，行为变得不可预测，且没人会发现。

## 判定

把三处里提到买卖/仓位/荐股/策略的句子各归一档：

- ``blanket``  —— 无条件禁止（没有任何适用范围限定词）
- ``scoped``   —— 带适用范围：指向 ``output_policy`` 档位，或自带持牌/授权/个股 vs 板块的限定

分档后的正解是三处散文**都指向** ``output_policy`` 这一个结构化字段，而不是各自复述一遍口径——
复述三遍正是「只改一处就矛盾」的根因。

全 ``blanket`` 或全 ``scoped`` 都算自洽；**混着就是矛盾**，退出码 1。
本工具不判断哪一档「对」——那是用户的裁定权，这里只保证三处说的是同一件事。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TOPIC_WORDS = ("买卖", "仓位", "荐股", "交易建议", "组合策略", "选股与组合")
PROHIBITION = ("不出", "不输出", "不给", "不做", "禁止", "不提供", "不荐")
SCOPE_WORDS = (
    "持牌", "授权", "机构", "团队内部", "未授权", "个人用户", "目标用户",
    "个股层面", "板块层面", "大盘和板块", "按用途", "按场景",
    # 分档后的正规写法：散文指向结构化字段，而不是各自复述一遍口径
    "output_policy", "owner_personal", "product_general", "licensed_institutional", "档",
)


def _loci(profile: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for i, x in enumerate(profile.get("anti_patterns") or []):
        out.append((f"anti_patterns[{i}]", x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)))
    for i, x in enumerate(profile.get("reasoning_patterns") or []):
        text = x.get("rule", "") if isinstance(x, dict) else str(x)
        out.append((f"reasoning_patterns[{i}]", text))
    vg = profile.get("voice_guidance")
    if vg is not None:
        out.append(("voice_guidance", vg if isinstance(vg, str) else json.dumps(vg, ensure_ascii=False)))
    return [(w, t) for w, t in out if any(k in t for k in TOPIC_WORDS)]


def classify(text: str, where: str = "") -> str:
    """``anti_patterns`` 里「列着」本身就是禁止，不需要再出现否定词。"""
    if any(s in text for s in SCOPE_WORDS):
        return "scoped"
    if any(p in text for p in PROHIBITION):
        return "blanket"
    if where.startswith("anti_patterns"):
        return "blanket"
    return "neutral"


def check(profile: dict[str, Any]) -> dict[str, Any]:
    loci = _loci(profile)
    graded = [{"where": w, "verdict": classify(t, w), "text": t} for w, t in loci]
    kinds = {g["verdict"] for g in graded} - {"neutral"}
    return {
        "profile_id": profile.get("id"),
        "loci": graded,
        "consistent": len(kinds) <= 1,
        "verdicts": sorted(kinds),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="检查画像里买卖/策略口径的三处声明是否一致（只读）")
    ap.add_argument("profiles", nargs="+", type=Path)
    args = ap.parse_args(argv)
    bad = 0
    for path in args.profiles:
        res = check(json.loads(path.read_text(encoding="utf-8")))
        mark = "✓ 自洽" if res["consistent"] else "✗ 矛盾"
        print(f"{mark}  {res['profile_id']}（{len(res['loci'])} 处提到买卖/策略，口径 {res['verdicts'] or ['—']}）")
        for g in res["loci"]:
            print(f"      [{g['verdict']:<7}] {g['where']}: {g['text'][:90]}")
        if not res["consistent"]:
            bad += 1
            print("      ↑ 这些声明不是同一个口径；只改其中一处会让下游行为取决于它读了哪个字段")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
