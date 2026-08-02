"""兜底类型不能当权威 override，否则会压掉认得出问题的规则。

会话路径（用户在工作台里实际走的那条）把 contract.question_type 原样作为
question_type_override 传给 plan_answer_question。信封（understand_query）对
"大盘""市场"这类泛指主语给不出具体类型，只能退到 general_finance_qa——那是
"上游没认出来"，不是"确定是通用问题"。

它被当成 confidence 1.0 的权威判断后，"今天大盘处于什么阶段？当前主线是哪几个
方向？" 在 CLI 里是 market_review、在工作台里是 general_finance_qa，于是走不到
_answer_market_review，主线数据块根本没被构建，答案只能写"主线未知"——而
DuckDB 里半导体近 20 日出现 15 天、AI算力 15 天的结构一直都在。
"""
from __future__ import annotations

import pytest

from intelligence.services.answer_orchestrator import (
    QUESTION_GENERAL,
    plan_answer_question,
)

# 会话路径的真实调用形态：override 就是信封的兜底值。
FALLBACK_OVERRIDE_CASES = [
    ("今天大盘处于什么阶段？当前主线是哪几个方向？", "market_review"),
    ("今天市场主线是什么", "market_review"),
    ("大盘现在什么阶段", "market_review"),
    ("今天赚钱效应如何", "market_review"),
    ("明天大盘怎么看", "market_forecast"),
    ("后市如何演绎", "market_forecast"),
]


@pytest.mark.parametrize("query,expected", FALLBACK_OVERRIDE_CASES)
def test_fallback_override_does_not_defeat_the_classifier(query: str, expected: str) -> None:
    with_override = plan_answer_question(
        query,
        question_type_override=QUESTION_GENERAL,
    ).question_type
    without_override = plan_answer_question(query).question_type

    assert without_override == expected
    assert with_override == expected, (
        f"会话路径传入兜底 override 后把「{query}」判成 {with_override}，"
        f"CLI 判成 {without_override}；同一个问题必须同一个答法"
    )


def test_genuinely_generic_question_stays_generic() -> None:
    """兜底值不再权威，但也不能因此把闲聊硬升级成市场问题。"""
    assert (
        plan_answer_question("给我讲个笑话", question_type_override=QUESTION_GENERAL).question_type
        == QUESTION_GENERAL
    )


@pytest.mark.parametrize(
    "override",
    ["theme_analysis", "stock_deep_dive", "market_forecast", "financial_analysis"],
)
def test_specific_override_is_still_authoritative(override: str) -> None:
    """上游确实认出了类型时，它仍然说了算——多轮对话要靠这个延续主题。"""
    plan = plan_answer_question("今天大盘处于什么阶段", question_type_override=override)

    assert plan.question_type == override
    assert plan.confidence == 1.0


def test_unknown_override_still_raises() -> None:
    with pytest.raises(ValueError):
        plan_answer_question("今天大盘什么阶段", question_type_override="not_a_type")
