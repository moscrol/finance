"""任务协议在上游就要正确：题型、时间锚、数据契约。

本文件锁两类曾经在上游就错掉的问题。共同点是**后面的门禁都在正确执行一个
错误的契约**——不是模型弱，也不是合成器故障，放宽门禁只会让无依据的结论出站。

① 预测句式：「2026-07-21 收盘了，明天怎么看」此前 envelope 认不出，
   turn_controller 按 general_finance_qa 建 TaskFrame，required_outputs 只有
   (direct_answer, evidence_boundary)——从一开始就没被要求产出 direct_assessment。

② 单指标取值：「2026-02-17 涨停家数多少」此前被 is_dated_market_review 抢进
   日报工作流；当日导出不存在时不会退到 DuckDB 直查，而是落进通用题材研究，
   甚至把问题文本当题材名。而 fact_market_daily.limit_up 一直在 METRICS 里。

两条判定链必须一致：本仓有 plan_answer_question（评分链）和 turn_controller
（任务契约链）两套，只断言一条会出现「测试绿、真实路径照旧坏」。
"""

from __future__ import annotations

import pytest

from intelligence.services.answer_orchestrator import (
    QUESTION_MARKET_FORECAST,
    plan_answer_question,
)
from intelligence.services.market_timeseries import METRICS, parse_single_metric_intent
from intelligence.services.query_understanding import (
    is_market_forecast_query,
    understand_query,
)
from intelligence.services.turn_controller import decide_turn

FORECAST_PHRASINGS = [
    "2026-07-21 收盘了，明天怎么看",
    "站在 2026-07-21 收盘，给出对 07-22 的研判",
    "明天走势怎么走",
    "明天大盘什么情况",
    "基于上周的行情，模仿你之前蒸馏的spt，写一下本周行情的展望。",
    "写一下本周行情的展望",
    "本周行情展望",
    "基于上周行情写一下本周展望",
    "展望一下本周行情",
    "展望一下A股后市",
    "模仿spt写一下本周行情的展望",
]

NOT_FORECAST = [
    "液冷服务器怎么看",
    "什么是液冷服务器",
    "2026-02-17 涨停家数多少",
    "分析有色金属板块后续走势",
]

FORECAST_REQUIRED_OUTPUTS = {
    "direct_assessment",
    "scenario_paths",
    "continuation_conditions",
    "invalidation_conditions",
}


@pytest.mark.parametrize("query", FORECAST_PHRASINGS)
def test_forecast_phrasings_agree_across_both_chains(query: str) -> None:
    """envelope / plan / turn_controller 三处必须给出同一个题型。"""
    assert is_market_forecast_query(query) is True
    assert understand_query(query).question_type == QUESTION_MARKET_FORECAST
    assert plan_answer_question(query).question_type == QUESTION_MARKET_FORECAST
    assert decide_turn(query).question_type == QUESTION_MARKET_FORECAST


@pytest.mark.parametrize("query", FORECAST_PHRASINGS)
def test_forecast_gets_the_forecast_data_contract(query: str) -> None:
    """题型对了还不够——required_outputs 必须真的要求那几段，否则合成拿不到 claim。"""
    frame = decide_turn(query).task_frame
    assert FORECAST_REQUIRED_OUTPUTS <= set(frame.required_outputs), frame.required_outputs
    assert frame.evidence_policy == "current_market_scenarios"


@pytest.mark.parametrize("query", NOT_FORECAST)
def test_non_forecast_questions_are_not_stolen(query: str) -> None:
    assert is_market_forecast_query(query) is False
    assert decide_turn(query).question_type != QUESTION_MARKET_FORECAST


def test_sector_forward_look_stays_theme_analysis() -> None:
    """带板块主语的前瞻不是全市场展望；扩它要改主语优先序，不在本单。"""
    query = "分析有色金属板块后续走势"
    assert understand_query(query).question_type == "theme_analysis"
    assert plan_answer_question(query).question_type == "theme_analysis"
    assert decide_turn(query).question_type == "theme_analysis"


@pytest.mark.parametrize(
    ("query", "metric_key"),
    [
        ("2026-02-17 涨停家数多少", "limit_up"),
        ("2026-07-23 双红板块多少个", "double_red_count"),
        ("07-21 全市成交额多少", "total_amount"),
        ("2026-02-17 连板最高多少板", "max_boards"),
    ],
)
def test_dated_single_metric_goes_to_direct_query(query: str, metric_key: str) -> None:
    """指定日期 + 单一白名单指标 = 要一个数，不该走日报工作流。"""
    spec = parse_single_metric_intent(query)
    assert spec is not None and spec.key == metric_key
    decision = decide_turn(query)
    assert decision.question_type == "quick_fact"
    assert decision.lane != "workflow"
    if query[:4].isdigit():
        assert decision.lane == "research"


@pytest.mark.parametrize(
    "query",
    ["2026-02-17 行情怎么样", "2026-02-17 复盘一下", "2026-02-17 市场结构如何"],
)
def test_review_style_questions_still_want_a_review(query: str) -> None:
    """要一份复盘的仍归复盘：只有「要一个数」才改道。"""
    assert parse_single_metric_intent(query) is None


def test_metric_vocabulary_comes_only_from_the_registry() -> None:
    """别名只能来自 METRICS：两条链各写一份词表正是上一个 bug 的成因。"""
    # 比 key 不比对象：全量跑里模块可能被重新导入，同一性会失败而值仍相同。
    hit = parse_single_metric_intent("2026-02-17 涨停家数多少")
    assert hit is not None and hit.key == METRICS["limit_up"].key
    # 没登记的指标不得被瞎认
    assert parse_single_metric_intent("2026-02-17 北向净流入多少") is None
    # 命中多个指标时不算单指标取值——那是一份小复盘
    assert parse_single_metric_intent("2026-02-17 涨停家数和跌停家数各多少") is None
    # 没有日期锚点时不抢（由上层的日期解析把关）
    assert decide_turn("涨停家数多少").lane != "knowledge"
