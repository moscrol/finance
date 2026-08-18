"""取值查询必须走 quick_fact，而且两条并行判定链要给出同一个答案。

坏掉的形态：「宁德时代今天收盘多少」这种问过去数字的问题被判成 market_forecast
——因为 answer_orchestrator 的前瞻兜底把「收盘」列成了触发词，而 turn_controller
的 quick_fact 词面只认「股价/市盈率/市净率/股票代码」。后果是两头判失败：
task_frame 要它给出情景路径与失效条件，rubric 追加四源合议等 5 个前瞻维度。

同一道 counterpoint 门禁已经因为路由送错 frame 修过三次（07-31 两次 + C5），
每次修的都是门禁的判定条件。真正的杠杆在分类器。
"""

from __future__ import annotations

import pytest

from intelligence.eval.finance_answer_rubric import score_answer
from intelligence.services.answer_orchestrator import (
    QUESTION_MARKET_FORECAST,
    QUESTION_QUICK_FACT,
    plan_answer_question,
)
from intelligence.services.route_table import is_quick_fact_query
from intelligence.services.turn_controller import _fine_grained_route_row, decide_turn

QUICK_FACT_QUERIES = [
    "立新能源 2026-07-20 和 07-21 分别涨了多少、收盘价多少",
    "宁德时代今天收盘多少",
    "茅台现在股价多少",
    "英伟达市盈率多少倍",
    "300750是哪家公司",
    "光刻胶板块今天成交额多少",
]

# 这些必须留给原来的题型：前瞻问的是判断，不是取值。
NOT_QUICK_FACT_QUERIES = [
    "2026-07-21 收盘了，明天怎么看",
    "明天收盘多少",
    "明天大盘怎么看",
    "液冷服务器怎么看",
    "后市怎么演绎",
]


@pytest.mark.parametrize("query", QUICK_FACT_QUERIES)
def test_quick_fact_recognised_by_both_chains(query: str) -> None:
    """词面判定、路由表、题型分类三处必须一致——各写一份词表就会漂移。"""
    assert is_quick_fact_query(query) is True
    row = _fine_grained_route_row(query)
    assert row is not None and row.route_id == "quick_fact"
    assert plan_answer_question(query).question_type == QUESTION_QUICK_FACT


@pytest.mark.parametrize("query", NOT_QUICK_FACT_QUERIES)
def test_forward_looking_questions_are_not_stolen(query: str) -> None:
    assert is_quick_fact_query(query) is False
    row = _fine_grained_route_row(query)
    assert row is None or row.route_id != "quick_fact"


def test_closing_price_lookup_no_longer_routes_to_forecast() -> None:
    """锁住这次修复的核心：查收盘价不再被判成前瞻研判。"""
    plan = plan_answer_question("宁德时代今天收盘多少")
    assert plan.question_type != QUESTION_MARKET_FORECAST
    assert plan.question_type == QUESTION_QUICK_FACT


def test_next_day_call_stays_forecast() -> None:
    """反向护栏：真正的前瞻题不能被 quick_fact 抢走（A2 验收题的形态）。"""
    assert plan_answer_question("2026-07-21 收盘了，明天怎么看").question_type == (
        QUESTION_MARKET_FORECAST
    )


def test_quick_fact_is_not_scored_on_inapplicable_dimensions() -> None:
    """取值回答不该被盘面阶段、产业推导、反方审稿扣分——那是范畴错误。"""
    answer = (
        "立新能源（001258）2026-07-20 收盘 8.42 元、涨 3.1%；2026-07-21 收盘 8.15 元、"
        "跌 3.2% [S1]。数据来自本地 market_feature_store 的 fact_stock_daily。"
        "证据边界：仅覆盖这两个交易日的日线收盘。"
    )
    scored = score_answer("立新能源收盘价多少", answer, question_type=QUESTION_QUICK_FACT)
    keys = {d.key for d in scored.dimensions}
    for absent in (
        "market_stage",
        "industry_reasoning",
        "critic_review",
        "actionability",
        "personal_methodology",
        "evidence_layering",
    ):
        assert absent not in keys, absent
    assert scored.max_score == 15

    vague = score_answer("立新能源收盘价多少", "走势不错，可以关注。", question_type=QUESTION_QUICK_FACT)
    assert vague.total_score < scored.total_score


@pytest.mark.parametrize(
    "query",
    (
        "2026-07-21 MLCC 板块成交额多少",
        "立新能源 2026-07-20 和 07-21 分别涨了多少、收盘价多少",
    ),
)
def test_dated_metric_quick_fact_uses_research_lane(query: str) -> None:
    """C4/C5：取值题仍是 quick_fact，但不得落 knowledge_lane_answer。"""

    assert is_quick_fact_query(query) is True
    row = _fine_grained_route_row(query)
    assert row is not None
    assert row.route_id == "quick_fact"
    assert row.lane == "research"
    decision = decide_turn(query)
    assert decision.question_type == "quick_fact"
    assert decision.lane == "research"


def test_undated_quick_fact_stays_on_knowledge_lane() -> None:
    for query in ("茅台现在股价多少", "300750是哪家公司"):
        row = _fine_grained_route_row(query)
        assert row is not None
        assert row.route_id == "quick_fact"
        assert row.lane == "knowledge"
