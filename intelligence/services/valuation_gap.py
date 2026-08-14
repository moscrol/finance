"""估值与预期差（P2-10）：框架 + 缺口提示版，不给精确目标价.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md P2-10：
系统更强在题材/证据/盘面，估值维度先只做四问框架与缺口提示——

1. 当前市值隐含什么预期？
2. 逻辑兑现需要多少收入/利润？
3. 市场是否已经提前定价？
4. 同链公司市值/弹性如何比较？

注意（手册原文）：估值数据质量要求更高，初期不强行给精确目标价；
本模块只判断"证据链里有没有回答这四问的材料"，缺的写显式缺口。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VALUATION_QUESTIONS = [
    "当前市值隐含什么预期",
    "逻辑兑现需要多少收入/利润",
    "市场是否已经提前定价",
    "同链公司市值/弹性如何比较",
]

_QUESTION_RULES: list[tuple[str, tuple[str, ...], str]] = [
    (
        VALUATION_QUESTIONS[0],
        ("市值", "估值", "PE", "PS", "隐含"),
        "缺市值锚：先拿到当前市值与可比口径（PE/PS/市值/单GW 等），才能谈隐含预期",
    ),
    (
        VALUATION_QUESTIONS[1],
        ("收入", "利润", "业绩", "兑现", "测算", "空间"),
        "缺兑现测算：题材逻辑没有换算成'需要多少收入/利润才撑得住'，容易讲故事",
    ),
    (
        VALUATION_QUESTIONS[2],
        ("提前定价", "已定价", "预期差", "抢跑", "透支", "涨幅已"),
        "缺定价程度判断：不知道市场已经 price in 多少，无法区分新 alpha 和旧共识",
    ),
    (
        VALUATION_QUESTIONS[3],
        ("同链", "可比", "对比", "市值对比", "弹性对比"),
        "缺同链市值对比：同题材公司市值/弹性横比是最便宜的估值 sanity check",
    ),
]


@dataclass
class ValuationGapNote:
    answered: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"answered": list(self.answered), "gaps": list(self.gaps)}

    def to_prompt_block(self) -> str:
        lines = ["## 估值与预期差四问（框架版：只提缺口，不给目标价）"]
        for q in self.answered:
            lines.append(f"- 有材料可答：{q}")
        for g in self.gaps:
            lines.append(f"- ⚠️{g}")
        return "\n".join(lines)


def check_valuation_gaps(evidence_lines: list[str] | None) -> ValuationGapNote:
    note = ValuationGapNote()
    text = "\n".join(str(x or "") for x in (evidence_lines or []))
    for question, terms, gap in _QUESTION_RULES:
        if any(t in text for t in terms):
            note.answered.append(question)
        else:
            note.gaps.append(gap)
    return note
