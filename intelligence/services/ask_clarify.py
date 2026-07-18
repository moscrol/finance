"""澄清追问前置门（clarify-then-act）：问题明确模糊时先反问，不硬答。

只在「明确模糊」时触发（宁可放行不误拦），三种情形：
1. 空问题；
2. 问题本身就是空泛触发词（「随便」「帮我看看」「分析一下」「看看」）；
3. 去掉空泛触发词和语气填充词后没有任何实质内容（如「帮我随便看看吧」）。

带任何实体/题材/意图词面的问题一律放行——宁可答偏也不打断正常流程，
保证默认行为对既有明确问题逐字节不变。追问内容是确定性的结构化问题
（对象/口径/日期三问），不走 LLM：零成本、可单测、不会自己编问题。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 与 question_router.CLARIFY_TRIGGERS 对齐，另补同义空泛词面。
VAGUE_TRIGGERS = (
    "随便", "帮我看看", "分析一下", "看看", "帮我分析", "看一下",
    "怎么看", "怎么样", "如何",
)

# 语气/填充词：剥掉后判断是否还剩实质内容。
_FILLER_PATTERN = re.compile(
    r"帮我|给我|麻烦|请|你|您|一下|一波|吧|呢|啊|呀|哦|了|的|今天|现在|最近"
    r"|[\s，。、！？!?~…；;:：\"'（）()\[\]【】-]+"
)

DEFAULT_QUESTIONS = (
    "看什么对象？题材/板块还是个股（给名字或代码）？",
    "要哪一类内容？盘面数据（涨跌/成交/资金）、逻辑与证据链，还是历史判断回检？",
    "哪个日期或时间段？不说就取最新交易日。",
)


@dataclass
class ClarifyDecision:
    """澄清判定结果：需要追问时给出确定性的结构化问题列表。"""

    needs_clarification: bool
    reason: str = ""
    questions: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [f"问题过于模糊，先确认再检索（{self.reason}）："]
        lines.extend(f"{i}. {q}" for i, q in enumerate(self.questions, 1))
        return lines


def _strip_vague(text: str) -> str:
    out = text
    for token in VAGUE_TRIGGERS:
        out = out.replace(token, "")
    return _FILLER_PATTERN.sub("", out)


def clarify_for_query(query: str) -> ClarifyDecision:
    """确定性澄清门：只拦「明确模糊」的问题，其余一律放行。"""
    text = str(query or "").strip()
    if not text:
        return ClarifyDecision(
            needs_clarification=True,
            reason="空问题",
            questions=list(DEFAULT_QUESTIONS),
        )
    if text in VAGUE_TRIGGERS:
        return ClarifyDecision(
            needs_clarification=True,
            reason=f"问题只有空泛词面「{text}」",
            questions=list(DEFAULT_QUESTIONS),
        )
    residue = _strip_vague(text)
    if not residue:
        return ClarifyDecision(
            needs_clarification=True,
            reason="去掉空泛词面后没有实质检索目标",
            questions=list(DEFAULT_QUESTIONS),
        )
    return ClarifyDecision(needs_clarification=False)
