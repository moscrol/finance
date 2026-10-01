"""路由探针第三轮（2026-10-01）：分析题不再被当成定义题、题材前的语法成分、调序盘面题。

1. 「X 的逻辑 / 原因 / 风险……是什么」此前判 concept_definition → knowledge 车道 +
   needs_retrieval=False，模型凭记忆零检索作答；定义判断排在公司锚 / 题材识别之前，连
   「亨通光电的核心逻辑是什么」都吞掉。12 道分析题 11 道中招。
2. 「支撑**这轮**光纤光缆行情……」：题材词左邻是 CJK 就被否决（R13-A3 防「立新能源」），
   语法成分（这轮 / 的 / 布局……）也一并误杀，uq15-q05 调序改写丢题材。
3. 「今天成交额多少？大盘表现怎么样？」：今天与大盘不在同一分句，uq15-q14 调序改写丢盘面。

注入临时知识库的路由探针：改写一致率 0.844 → 0.889（调序 0.867 → 1.0）。
"""

from __future__ import annotations

import pytest

from intelligence.services.query_understanding import (
    _definition_subject,
    has_clean_theme_occurrence,
    is_market_watch_query,
)
from intelligence.services.turn_controller import decide_turn


@pytest.mark.parametrize(
    "question",
    [
        "光纤光缆行情背后的产业逻辑是什么？",
        "亨通光电的核心逻辑是什么？",
        "中际旭创涨停的原因是什么",
        "液冷的投资逻辑是什么",
        "稀有金属上涨的驱动因素是什么",
        "光模块的主要风险是什么",
        "亨通光电的看点是什么",
        "储能的核心壁垒是什么",
        "算力板块今年的主线是什么",
    ],
)
def test_analysis_question_is_not_a_definition(question: str) -> None:
    assert _definition_subject(question) is None


@pytest.mark.parametrize(
    ("question", "subject"),
    [
        ("什么是液冷服务器", "液冷服务器"),
        ("融资融券是什么意思", "融资融券"),
        ("CPO是什么", "CPO"),
        ("什么是市盈率", "市盈率"),
        ("光纤光缆的技术原理", "光纤光缆"),
        ("液冷如何工作", "液冷"),
        ("CPO的产业链位置", "CPO"),
    ],
)
def test_true_definition_questions_are_unchanged(question: str, subject: str) -> None:
    assert _definition_subject(question) == subject


@pytest.mark.parametrize("question", ["亨通光电的核心逻辑是什么？", "稀有金属上涨的驱动因素是什么"])
def test_analysis_question_does_not_land_in_no_retrieval_knowledge(question: str) -> None:
    def _no_llm(*_args, **_kwargs):
        raise RuntimeError("controller LLM disabled in this test")

    decision = decide_turn(question, llm_complete=_no_llm, previous_intent=None)
    assert not (decision.lane == "knowledge" and not decision.needs_retrieval)
    assert decision.question_type != "concept_definition"


@pytest.mark.parametrize(
    ("query", "term", "expected"),
    [
        ("支撑这轮光纤光缆行情的关键证据", "光纤光缆", True),
        ("这波新能源怎么看", "新能源", True),
        ("布局光模块", "光模块", True),
        ("液冷的产业链", "液冷", True),
        # R13-A3 防线：公司名后缀嵌入仍否决
        ("立新能源怎么看", "新能源", False),
        ("国新能源怎么看", "新能源", False),
        ("华润新能源", "新能源", False),
        ("协和新能源怎么看", "新能源", False),
        ("宝新能源", "新能源", False),
    ],
)
def test_theme_left_context(query: str, term: str, expected: bool) -> None:
    assert has_clean_theme_occurrence(query, term) is expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("今天成交额多少？大盘表现怎么样？", True),
        ("今天大盘怎么样？成交额多少？", True),
        ("今天光伏涨了，A股整体如何？", True),
        ("光伏市场表现怎么样", False),
        ("今天光伏市场表现怎么样", False),
        ("大盘怎么样", False),
        ("2026-08-14 大盘表现怎么样", False),
        ("今天亨通光电走势如何", False),
    ],
)
def test_reordered_market_watch(query: str, expected: bool) -> None:
    assert is_market_watch_query(query) is expected
