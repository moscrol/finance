"""当日盘面题的口语谓词（2026-10-01 路由改写探针）。"""

from __future__ import annotations

import pytest

from intelligence.services.query_understanding import understand_query


@pytest.mark.parametrize(
    "query",
    ["今天大盘咋样啊？成交了多少？", "今天行情怎样", "今日大盘走势如何", "今天大盘表现怎么样", "今天大盘怎么样？成交额多少？"],
)
def test_colloquial_market_watch(query: str) -> None:
    assert understand_query(query).question_type == "market_watch"


@pytest.mark.parametrize("query", ["今天固态电池怎么样", "今天光伏板块咋样"])
def test_theme_questions_are_not_swallowed(query: str) -> None:
    assert understand_query(query).question_type != "market_watch"
