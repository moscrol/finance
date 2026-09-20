"""Opt-in reasoning guidance, not evidence, a lens registry or a completion gate."""

from __future__ import annotations

import os

ENV_FLAG = "FINANCE_RESEARCH_REASONING"
HEADING = "【研究求证意识 v1】"

# Existing task kinds, not a taxonomy of allowed explanations. Unknown kinds
# stay unchanged until their owner opts in; factual lookup needs no extra work.
_RESEARCH_TYPES = frozenset({
    "market_watch", "market_review", "dated_market_review", "market_forecast",
    "market_cause", "stock_deep_dive", "valuation_estimate", "theme_analysis",
    "news_impact", "financial_analysis", "theme_track", "kol_review",
    "comparison_analog", "comparison", "trade_advice", "event_forecast",
    "fact_check", "methodology_discussion", "general_finance_qa",
})

_GUIDANCE = HEADING + "\n" + """
这是研究习惯，不是市场证据、固定步骤或新增回答栏目。先回应用户实际问题；
即使题型属于研究，单纯查数、定义或已能直接回答的问题也不展开机制讨论。
需要解释或判断时，从待解释的现象出发追问：什么约束、激励或机制可能产生它？
按问题与证据自行选择、组合或放弃解释框架，没有封闭视角菜单；不默认从宏观或流动性开始。
把已观察事实、候选解释与尚未验证的假设分开；相关或同时发生不能单独证明因果。
存在实质歧义时考虑有根据的竞争性解释，不为凑数量编反方。优先寻找能区分解释、
或推翻当前判断的证据，而非重复支持材料；证据日期与当时可知时间必须对齐。
观察返回后检查关键假设是否仍成立，必要时改变下一次取证方向、降低确信或放弃解释；
不得为了保住原结论机械换视角。无法区分时保留未知，并给出真正会改变判断的观察条件。
材料缺失或过时不等于事件未发生。机制推断不能冒充已核实的资金迁移或参与者行为。
只在本轮读取权限、工具菜单、调用与时间预算内取证；不新增权限、必查工具或强制反思轮次。
合成阶段仅使用已提供材料，不暗示补查已经发生；证据已足够或无法补齐时直接收口。
回答呈现必要的依据、边界和判断变化即可，不复述这份指令，不为展示分析而扩写。
""".strip()

_OBSERVATION_GUIDANCE = (
    "研究求证意识 v1：刚返回的材料改变了哪个关键假设？"
    "若有根据的解释仍难区分，下一次读取应能区分它们；"
    "出现反证可修订或放弃解释，不为保住结论换说法。"
    "查不到不等于不存在，新增证据数量不等于假设获支持。"
    "证据已足够、问题只是查数或预算不容补查时直接作答并保留边界；不强制追加轮次。"
)


def enabled_for(question_type: str) -> bool:
    return (
        os.environ.get(ENV_FLAG, "off").strip().lower() in {"1", "on", "true", "yes"}
        and question_type in _RESEARCH_TYPES
    )


def guidance(question_type: str) -> str:
    return "\n\n" + _GUIDANCE if enabled_for(question_type) else ""


def observation_guidance(question_type: str) -> str:
    return _OBSERVATION_GUIDANCE if enabled_for(question_type) else ""
