import inspect

import pytest

from intelligence.services import evidence_capabilities as evidence_capabilities_mod
from intelligence.services.evidence_capabilities import (
    _OVERLAY_REQUIREMENT_TEMPLATE,
    _has_overnight_external_premise,
    is_current_market_query,
    resolve_evidence_plan,
)
from intelligence.services.route_table import LANE_COMPOSITION_RULES

# 一道盘面题拿不到行情数据时，答案看起来仍然是完整的——所以这类漏判不会自己
# 暴露，只能靠一张固定的自然问法表守。表里每条都写明「为什么它曾经漏/曾经误
# 触发」，新增说法时照抄格式即可。
#
# 初版判定是单条 `has_time and has_subject` AND，实测这 18 条只对 10 条：
# 时间词表缺「今天」、显式日期一个时间词都不命中、无时间词的度量提问
#（「涨停家数多少」）全漏；而「主线/盘面/成交/涨停」当时同时在时间词表和主体
# 词表里，AND 对它们退化成单词命中，把「如何判断主线候选和噪音」这种纯方法题
# 拖进了行情数据。
_CURRENT_MARKET_CASES: tuple[tuple[str, bool, str], ...] = (
    # 显式日期是最强时效信号，但纯词表下它一个时间词都命中不了
    ("以 2026-08-07 收盘为准，A股整体市场处于什么状态", True, "显式日期+主体"),
    ("以 2026-08-07 收盘为准，明天大盘怎么看", True, "显式日期+前瞻"),
    ("现在大盘怎么看", True, "时间词+主体"),
    # 「今天」曾缺席时间词表——而它是最常用的那个
    ("今天板块表现如何", True, "时间词+主体"),
    ("这两天市场情绪怎么样", True, "口语时间词+主体"),
    ("市场处于什么阶段", True, "无时间词，靠现状判断词"),
    ("A股强不强", True, "无时间词无度量词，靠现状判断词"),
    # 度量词自带「要看数据」语义，不该要求同时出现时间词
    ("涨停家数多少", True, "度量词独立成立"),
    ("大盘现在在什么位置", True, "时间词+主体"),
    ("当前主线是什么", True, "时间词+主体"),
    ("茅台现在多少钱", True, "个股价格走度量词（多少钱）"),
    # 个股估值问题（贵不贵）不靠 is_current_market_query 拿到 market_data；
    # 它由 question_type=valuation_estimate → policy floor=company_valuation_evidence
    # 这条路径覆盖，is_current_market_query 不参与，此处正确值是 False。
    ("宁德时代估值贵不贵", False, "个股估值走 valuation_estimate policy，不走关键词路径"),
    # 今昔对比同时要当日盘面和历史区间；初版对历史词无条件 return False
    ("最近行情和2024年哪段像", True, "今昔对比，历史词不应整条否掉"),
    # 以下必须保持 False：把知识题拖进行情数据会污染答案
    ("什么是PE", False, "纯概念"),
    ("市盈率怎么计算", False, "纯概念，含「怎么」但非盘面"),
    ("你的检索硬触发是怎么设计的", False, "方法论提问"),
    ("如何判断主线候选和噪音", False, "方法论提问，曾因词表重叠误触发"),
    ("复盘2025年A股市场主线", False, "纯历史复盘，无当期时间信号"),
)


@pytest.mark.parametrize(
    ("query", "expected", "reason"),
    _CURRENT_MARKET_CASES,
    ids=[case[0] for case in _CURRENT_MARKET_CASES],
)
def test_current_market_detection_covers_natural_phrasings(
    query: str,
    expected: bool,
    reason: str,
) -> None:
    assert is_current_market_query(query) is expected, reason


def test_current_market_mainline_variants_share_one_evidence_profile():
    queries = (
        "目前市场的主线是什么",
        "你觉得目前市场的主线是什么，给我你的判断依据",
        "当前盘面怎么看",
        "最新市场结构有哪些变化",
    )
    assert all(is_current_market_query(query) for query in queries)
    plans = [
        resolve_evidence_plan(query, question_type="general_finance_qa")
        for query in queries
    ]
    assert {plan.profile for plan in plans} == {"mainline_current"}
    assert all(
        plan.mandatory_provider_names == ("MARKET_DAILY", "D4")
        for plan in plans
    )


def test_historical_market_question_does_not_force_current_data():
    plan = resolve_evidence_plan(
        "复盘2025年A股市场主线",
        question_type="general_finance_qa",
    )
    assert plan.profile == "general"
    assert plan.mandatory_provider_names == ()


def test_market_forecast_has_current_market_requirement():
    plan = resolve_evidence_plan(
        "明天市场是反弹还是继续下跌",
        question_type="market_forecast",
    )
    assert plan.profile == "market_forecast"
    assert plan.mandatory_provider_names == ("MARKET_DAILY",)


_FIFTH_ROUND_OVERNIGHT = (
    "基于周二的盘面数据，你认为主线是什么。"
    "今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会"
)


def test_overnight_hybrid_forecast_adds_news_and_web_requirements():
    plan = resolve_evidence_plan(
        _FIFTH_ROUND_OVERNIGHT,
        question_type="market_forecast",
    )
    capabilities = {item.capability for item in plan.requirements}
    assert plan.profile == "market_forecast"
    assert plan.mandatory_provider_names == ("MARKET_DAILY",)
    assert capabilities >= {"market_data", "mainline_context", "news_search", "web_search"}


def test_tonight_review_without_external_marker_stays_local_forecast():
    plan = resolve_evidence_plan(
        "今晚复盘，你认为明天盘面会怎么走",
        question_type="market_forecast",
    )
    assert {item.capability for item in plan.requirements} == {
        "market_data",
        "mainline_context",
    }


_FED_MACRO_LOCAL = "美联储决议后 A 股半导体板块怎么推演"

# 每条组合规则至少一条问法。新增规则必须在此登记，否则穷尽测试红。
_COMPOSITION_RULE_QUERIES: dict[str, str] = {
    "overnight_external_premise": _FIFTH_ROUND_OVERNIGHT,
    "external_macro_event_local_inference": _FED_MACRO_LOCAL,
}


def test_every_lane_composition_rule_has_a_forecast_overlay_case():
    assert {rule.rule_name for rule in LANE_COMPOSITION_RULES} == set(
        _COMPOSITION_RULE_QUERIES
    )
    for rule in LANE_COMPOSITION_RULES:
        query = _COMPOSITION_RULE_QUERIES[rule.rule_name]
        assert rule.predicate(query), rule.rule_name
        plan = resolve_evidence_plan(query, question_type="market_forecast")
        capabilities = {item.capability for item in plan.requirements}
        assert plan.profile == "market_forecast"
        assert plan.mandatory_provider_names == ("MARKET_DAILY",)
        assert capabilities.issuperset(rule.extra_capabilities)


def test_overnight_is_first_composition_rule_and_same_predicate():
    first = LANE_COMPOSITION_RULES[0]
    assert first.rule_name == "overnight_external_premise"
    assert first.predicate is _has_overnight_external_premise


def test_resolve_evidence_plan_has_no_overnight_special_case_if():
    source = inspect.getsource(evidence_capabilities_mod.resolve_evidence_plan)
    assert "if _has_overnight_external_premise" not in source
    assert "_apply_lane_composition" in source
    module_source = inspect.getsource(evidence_capabilities_mod)
    assert "if _has_overnight_external_premise" not in module_source


def test_fed_event_local_inference_overlays_news_and_web_only():
    plan = resolve_evidence_plan(
        _FED_MACRO_LOCAL,
        question_type="market_forecast",
    )
    capabilities = {item.capability for item in plan.requirements}
    assert plan.profile == "market_forecast"
    assert plan.mandatory_provider_names == ("MARKET_DAILY",)
    assert capabilities == {
        "market_data",
        "mainline_context",
        "news_search",
        "web_search",
    }
    overlay = [
        item
        for item in plan.requirements
        if item.capability in {"news_search", "web_search"}
    ]
    assert overlay and all(item.mandatory is False for item in overlay)


def test_fomc_and_nfp_local_inference_also_overlay():
    queries = (
        "FOMC 决议后对 A 股半导体怎么推演",
        "非农公布后 A 股怎么走",
        "CPI 同比公布后 A 股银行板块怎么看",
    )
    for query in queries:
        plan = resolve_evidence_plan(query, question_type="market_forecast")
        capabilities = {item.capability for item in plan.requirements}
        assert capabilities >= {"news_search", "web_search"}, query


def test_macro_event_without_local_inference_does_not_overlay():
    plan = resolve_evidence_plan(
        "美联储今晚会不会降息",
        question_type="market_forecast",
    )
    assert {item.capability for item in plan.requirements} == {
        "market_data",
        "mainline_context",
    }


def test_cpi_without_yoy_does_not_overlay_even_with_a_share():
    plan = resolve_evidence_plan(
        "CPI公布后A股银行板块怎么走",
        question_type="market_forecast",
    )
    assert {item.capability for item in plan.requirements} == {
        "market_data",
        "mainline_context",
    }


def test_plain_news_forecast_does_not_overlay_macro_rule():
    plan = resolve_evidence_plan(
        "今天有什么财经新闻，明天盘面会怎么走",
        question_type="market_forecast",
    )
    assert {item.capability for item in plan.requirements} == {
        "market_data",
        "mainline_context",
    }


def test_composition_overlay_does_not_duplicate_or_remove_base_caps():
    query = "隔夜美股因美联储决议大跌，明天A股板块怎么推演"
    plan = resolve_evidence_plan(query, question_type="market_forecast")
    capabilities = [item.capability for item in plan.requirements]
    assert capabilities[:2] == ["market_data", "mainline_context"]
    assert capabilities.count("news_search") == 1
    assert capabilities.count("web_search") == 1


def test_every_composition_extra_capability_has_overlay_template():
    for rule in LANE_COMPOSITION_RULES:
        for capability in rule.extra_capabilities:
            assert capability in _OVERLAY_REQUIREMENT_TEMPLATE, (
                rule.rule_name,
                capability,
            )


def test_methodology_query_does_not_inherit_market_capabilities():
    plan = resolve_evidence_plan(
        "市场主线判断的 agent 架构怎么实现？",
        question_type="methodology_discussion",
    )
    assert plan.profile == "general"
    assert plan.requirements == ()


def test_definition_plus_current_market_fact_gets_structured_evidence_plan():
    plan = resolve_evidence_plan(
        "什么是双红，现在哪些板块双红",
        question_type="concept_definition",
    )
    assert plan.profile == "current_market_fact"
    assert plan.mandatory_provider_names == ("D4",)
    assert plan.mandatory_capabilities == ("mainline_context",)


def test_pure_definition_does_not_get_current_market_data():
    plan = resolve_evidence_plan(
        "什么是双红",
        question_type="concept_definition",
    )
    assert plan.profile == "general"
    assert plan.requirements == ()
