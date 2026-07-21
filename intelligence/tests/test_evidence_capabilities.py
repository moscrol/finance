from intelligence.services.evidence_capabilities import (
    is_current_market_query,
    resolve_evidence_plan,
)


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


def test_methodology_query_does_not_inherit_market_capabilities():
    plan = resolve_evidence_plan(
        "市场主线判断的 agent 架构怎么实现？",
        question_type="methodology_discussion",
    )
    assert plan.profile == "general"
    assert plan.requirements == ()
