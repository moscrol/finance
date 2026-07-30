"""CLI 与会话两条路径必须对同一个问题给出同一个类型。

这条接缝真实咬过一次：意图识别的规则加在 _classify_question_type 里，
plan_answer_question（CLI）会调用它，而 build_turn_intent（会话，也就是用户
在工作台里实际走的那条）直接取 envelope.question_type，绕过了整层兜底。
结果 "今天大盘处于什么阶段？当前主线是哪几个方向？" 在 CLI 里是 market_review、
在工作台里是 general_finance_qa，走进通用问答分支，主线答不出来。

修分类器而不修这条接缝，等于只修好了没人用的那条路径。
"""
from __future__ import annotations

import pytest

from intelligence.services.answer_orchestrator import plan_answer_question, understand_query
from intelligence.services.research_contract import build_turn_intent

SHARED_CASES = [
    ("今天大盘处于什么阶段？当前主线是哪几个方向？", "market_review"),
    ("今天市场主线是什么", "market_review"),
    ("大盘现在什么阶段", "market_review"),
    ("今天赚钱效应如何", "market_review"),
    ("明天大盘怎么看", "market_forecast"),
    ("后市如何演绎", "market_forecast"),
    ("固态电池现在处于什么阶段", "theme_analysis"),
    ("天赐材料这只股票怎么看", "stock_deep_dive"),
    ("宁德时代最近有什么公告", "news_impact"),
]


@pytest.mark.parametrize("query,expected", SHARED_CASES)
def test_cli_and_conversation_agree_on_question_type(query: str, expected: str) -> None:
    envelope = understand_query(query, matched_theme=None, anchor=None)

    cli_type = plan_answer_question(query).question_type
    conversation_type = build_turn_intent(query, envelope).question_type

    assert cli_type == expected
    assert conversation_type == expected, (
        f"会话路径把「{query}」判成 {conversation_type}，CLI 判成 {cli_type}；"
        "两条路径必须共用 resolve_question_type"
    )


def test_task_frame_still_wins_over_the_classifier() -> None:
    """已确立的任务框架优先于逐句分类——多轮对话里主题是延续的。"""
    from intelligence.services.task_frame import TaskFrame

    query = "今天大盘处于什么阶段"
    envelope = understand_query(query, matched_theme=None, anchor=None)
    frame = TaskFrame(
        raw_question=query,
        user_goal="跟进固态电池",
        question_type="theme_analysis",
        subject="固态电池",
        subject_kind="theme",
        market_scope="a_share",
        timeframe=None,
        required_outputs=(),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="local_first",
        confidence=0.9,
    )

    intent = build_turn_intent(query, envelope, task_frame=frame)

    assert intent.question_type == "theme_analysis"
