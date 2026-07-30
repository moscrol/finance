"""当日盘面提问必须在「信封」这一层就被认出来。

market_watch 是路由表里已有的一行（lane=workflow，描述「询问当日盘面的关注点、
看点或整体情况」）。整条会话链路都读信封的判断：TaskFrame 拿它选证据策略、
turn_intent 拿它决定要不要跑 daily-review skill、ask 再把它映射成
market_review 走 _answer_market_review。

所以信封漏判一句，下游全漏：「今天大盘处于什么阶段？当前主线是哪几个方向？」
原先退到 general_finance_qa，日报 skill 不跑、主线数据块不构建，答案只能写
「主线未知」——而 DuckDB 里半导体近 20 日出现 15 天的结构一直都在。

在信封层修而不是逐个下游打补丁：漏判的原因只有一个，修一处就够。
"""
from __future__ import annotations

import pytest

from intelligence.services.query_understanding import (
    is_market_watch_query,
    understand_query,
)

# 原先漏判的说法。market_stage 本身就是 fact_market_daily 的字段。
NEWLY_RECOGNISED = [
    "今天大盘处于什么阶段？当前主线是哪几个方向？",
    "今天大盘处于什么阶段",
    "今天市场处于什么阶段",
    "行情现在处于什么阶段",
    "大盘目前在哪个阶段",
    "当前主线是哪几个方向",
    "当前主线是什么",
    "现在主线有哪些",
]

# 原先就认得的，不能回退。
ALREADY_RECOGNISED = [
    "今天有什么值得关注的",
    "今日盘面有哪些看点",
    "今天市场怎么样",
    "当前市场的主线是什么",
    "今天复盘",
]

# 必须守住的反例：题材/个股问「阶段」和「主线」的说法很像，不能被当成大盘提问。
MUST_NOT_MATCH = [
    "固态电池现在处于什么阶段",
    "宁德时代现在处于什么阶段",
    "半导体板块现在处于什么阶段",
    "光模块题材现在什么阶段",
    "固态电池当前主线逻辑是什么",
    "半导体设备板块的产业链",
    "天赐材料这只股票怎么看",
    "明天大盘怎么看",
    "后市如何演绎",
    "这个反弹能持续多久",
    "给我讲个笑话",
]


@pytest.mark.parametrize("query", NEWLY_RECOGNISED + ALREADY_RECOGNISED)
def test_daily_market_questions_are_market_watch(query: str) -> None:
    assert is_market_watch_query(query)
    assert understand_query(query, matched_theme=None).question_type == "market_watch"


@pytest.mark.parametrize("query", MUST_NOT_MATCH)
def test_theme_and_stock_questions_are_not_swallowed(query: str) -> None:
    assert not is_market_watch_query(query), (
        f"「{query}」被当成大盘提问，会去跑 daily-review 而不是它该走的路径"
    )


def test_mainline_needs_a_clause_boundary_not_just_the_word() -> None:
    """主线在本项目里专指全市场主线，所以前面不需要主语——但必须在句首或分句首。

    「固态电池当前主线逻辑是什么」里的 当前主线 紧跟着题材名，不是大盘提问。
    """
    assert is_market_watch_query("今天大盘处于什么阶段？当前主线是哪几个方向？")
    assert not is_market_watch_query("固态电池当前主线逻辑是什么")
