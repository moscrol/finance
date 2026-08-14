"""方案 2：LLM 检索 planner（计划钳制 + 模式灰度 + 失败回退）。"""

from unittest import mock

from intelligence.services import retrieval_planner


def test_planner_mode_defaults_to_rules(monkeypatch):
    monkeypatch.delenv(retrieval_planner.ENV_MODE, raising=False)
    assert retrieval_planner.planner_mode() == "rules"
    monkeypatch.setenv(retrieval_planner.ENV_MODE, "SHADOW")
    assert retrieval_planner.planner_mode() == "shadow"
    monkeypatch.setenv(retrieval_planner.ENV_MODE, "bogus")
    assert retrieval_planner.planner_mode() == "rules"


def test_clamp_plan_intersects_whitelist_and_unions_mandatory():
    providers = retrieval_planner.clamp_plan(
        ["d9", "D5", "NOT_A_BLOCK", 42], "theme_analysis",
    )
    # ∩ 白名单去掉非法名，∪ 默认必选块 M/V，按注册顺序输出
    assert providers == ("D9", "M", "V", "D5")


def test_clamp_plan_perspective_unions_market_blocks():
    providers = retrieval_planner.clamp_plan([], "general", perspective_active=True)
    for name in retrieval_planner.PERSPECTIVE_MANDATORY:
        assert name in providers
    # 非视角模式不受影响
    baseline = retrieval_planner.clamp_plan([], "general")
    assert "MARKET_DAILY" not in baseline
    assert "D6" not in baseline


def test_mandatory_for_perspective_keeps_question_type_blocks():
    providers = retrieval_planner.mandatory_for(
        "valuation", perspective_active=True
    )
    assert "D5" in providers  # 问题类型必选块不丢
    assert "MARKET_DAILY" in providers and "D4" in providers and "D6" in providers


def test_clamp_plan_market_review_mandatory():
    providers = retrieval_planner.clamp_plan([], "market_review")
    assert providers == ("M", "V", "D4")


def test_plan_retrieval_success_parses_json():
    content = (
        '```json\n{"providers": ["D6", "W7"], '
        '"queries": {"w7": " 固态电池 中试线 "}, "reason": "中期趋势+事件"}\n```'
    )
    with mock.patch.object(
        retrieval_planner.llm_refine, "complete", return_value=(content, None, ""),
    ):
        plan = retrieval_planner.plan_retrieval("固态电池中期怎么看", "theme_analysis")
    assert plan.source == "llm"
    assert plan.providers == ("D6", "W7", "M", "V")
    assert plan.queries == {"W7": "固态电池 中试线"}
    assert plan.reason == "中期趋势+事件"


def test_plan_retrieval_falls_back_on_llm_failure():
    with mock.patch.object(
        retrieval_planner.llm_refine, "complete", return_value=(None, None, "未配置 LLM key"),
    ):
        plan = retrieval_planner.plan_retrieval("q", "general")
    assert plan.providers == ()
    assert plan.source.startswith("llm_fallback:")


def test_plan_retrieval_falls_back_on_invalid_json():
    with mock.patch.object(
        retrieval_planner.llm_refine, "complete", return_value=("不是 JSON", None, ""),
    ):
        plan = retrieval_planner.plan_retrieval("q", "general")
    assert plan.providers == ()
    assert plan.source == "llm_fallback:非法 JSON 输出"


def test_rules_mode_never_calls_llm(monkeypatch):
    """默认 rules 模式下 answer_query 不应触碰 planner LLM。"""
    monkeypatch.delenv(retrieval_planner.ENV_MODE, raising=False)
    from intelligence.services.ask import AskOptions, answer_query

    with mock.patch.object(retrieval_planner, "plan_retrieval") as plan:
        answer_query(AskOptions(query="帮我看看", use_modules=False, use_wiki_rag=False))
    plan.assert_not_called()
