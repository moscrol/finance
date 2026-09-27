from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from intelligence.services import ask_synthesis
from intelligence.services.ask_types import AskOptions, AskResult
from intelligence.services.answer_orchestrator import plan_answer_question
from intelligence.services.answer_quality import AnswerQualityContext
from intelligence.services.episode_protocol import build_episode_input, build_episode_instructions
from intelligence.services.research_workflow_guidance import ENV_FLAG, HEADING, workflow_guidance
from intelligence.services.research_tool_registry import default_registry
from intelligence.tests.test_episode_protocol import _context, _frame, _registry


CASES = (
    ("financial_analysis", "分析公司中报业绩", "未取得可比的一致预期"),
    ("event_forecast", "推演政策落地的情景", "事件发生概率"),
    ("kol_review", "这段研报观点站得住吗", "不自动扩写成作者的长期画像"),
    ("fact_check", "核对这份报告中的事实", "未查到不等于正确"),
    ("news_impact", "这条消息有什么影响", "主张身份的区分"),
    ("comparison_analog", "和历史上那轮行情有何异同", "案例不能代替完整样本"),
)


@pytest.mark.parametrize("question_type,question,marker", CASES)
def test_episode_receives_only_its_workflow_in_dynamic_input(
    monkeypatch, question_type, question, marker
):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    frame = replace(_frame(), question_type=question_type, raw_question=question)
    context = _context(frame)
    registry = _registry()
    payload = json.loads(build_episode_input(frame, context, registry))
    rules = payload["question_type_rules"]
    assert HEADING in rules
    assert marker in rules
    assert "不能扩大读取权限" in rules
    assert HEADING not in build_episode_instructions(frame, context, registry)
    assert context.contract.allowed_capabilities == ("market_data",)
    for other_type, _, other_marker in CASES:
        if other_type != question_type and not (
            question_type == "fact_check" and other_type == "news_impact"
        ):
            assert other_marker not in rules

    monkeypatch.setenv(ENV_FLAG, "off")
    disabled = json.loads(build_episode_input(frame, context, registry))
    assert HEADING not in disabled["question_type_rules"]
    # The switch changes guidance only, not evidence, tool grants, or output slots.
    payload.pop("question_type_rules")
    disabled.pop("question_type_rules")
    assert payload == disabled


def _ask_messages(monkeypatch, tmp_path, question_type, question, *, plan=None, override=None):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path))
    monkeypatch.setattr(
        ask_synthesis.perspective_lab,
        "build_runtime_context",
        lambda *_args, **_kwargs: SimpleNamespace(prompt="test perspective"),
    )
    monkeypatch.setattr(ask_synthesis.evidence_registry, "provider_enabled", lambda *_: False)
    result = AskResult(question, None, None, None, None)
    result.answer_spec = SimpleNamespace(to_prompt_block=lambda: "test evidence boundary")
    if plan is None:
        plan = SimpleNamespace(
            question_type=question_type,
            query_envelope=SimpleNamespace(question_type=question_type),
        )
    return ask_synthesis._prepare_answer_spec_synthesis(
        options=AskOptions(query=question, question_type_override=override),
        result=result,
        question_plan=plan,
        theme="",
        citations=[],
        quality_context=AnswerQualityContext(stage="test", layers=[]),
        is_market_review=False,
    )


@pytest.mark.parametrize("question_type,question,marker", CASES)
def test_ask_synthesis_gets_same_discipline(monkeypatch, tmp_path, question_type, question, marker):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    messages = _ask_messages(monkeypatch, tmp_path, question_type, question)
    body = "\n".join(message["content"] for message in messages)
    assert workflow_guidance(question_type) in body
    assert marker in body
    monkeypatch.setenv(ENV_FLAG, "0")
    disabled = _ask_messages(monkeypatch, tmp_path, question_type, question)
    assert HEADING not in "\n".join(message["content"] for message in disabled)


@pytest.mark.parametrize(
    "question_type",
    ("market_watch", "market_forecast", "quick_fact", "concept_definition",
     "methodology_discussion", "theme_track", "stock_deep_dive", "", "unknown"),
)
def test_unrelated_questions_stay_unchanged(monkeypatch, tmp_path, question_type):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    assert workflow_guidance(question_type) == ""
    frame = replace(_frame(), question_type=question_type)
    assert HEADING not in json.loads(build_episode_input(frame, _context(frame), _registry()))[
        "question_type_rules"
    ]
    assert HEADING not in "\n".join(
        message["content"] for message in _ask_messages(
            monkeypatch, tmp_path, question_type, "财报这个词不应绕过既有路由"
        )
    )


@pytest.mark.parametrize("value", ("0", "off", "false", "no", " OFF "))
def test_explicit_rollback(monkeypatch, value):
    monkeypatch.setenv(ENV_FLAG, value)
    assert workflow_guidance("financial_analysis") == ""


def test_real_legacy_material_route_keeps_critique_instead_of_financial_workflow(monkeypatch, tmp_path):
    from intelligence.tests.test_query_understanding import _REPORT_TEXT

    question = _REPORT_TEXT + "\n\n这篇研报的核心逻辑站得住吗？帮我分开哪些是硬事实、哪些只是推测"
    plan = plan_answer_question(question)
    assert plan.query_envelope.question_type == "kol_review"
    assert plan.question_type != "kol_review"
    messages = _ask_messages(monkeypatch, tmp_path, plan.question_type, question, plan=plan)
    text = "\n".join(message["content"] for message in messages)
    assert workflow_guidance("kol_review") in text
    assert workflow_guidance("financial_analysis") not in text


def test_legacy_classifier_financial_route_is_not_lost_to_generic_envelope(monkeypatch, tmp_path):
    question = "宁德时代财报怎么看"
    plan = plan_answer_question(question)
    assert plan.question_type == "financial_analysis"
    messages = _ask_messages(monkeypatch, tmp_path, plan.question_type, question, plan=plan)
    assert workflow_guidance("financial_analysis") in "\n".join(m["content"] for m in messages)


def test_ask_news_query_reaches_q14_layers_without_type_override(monkeypatch, tmp_path):
    from intelligence.eval.knevo_regression import DEFAULT_SUITE, select_case

    question = select_case(DEFAULT_SUITE, "Q14-news-layers").question
    plan = plan_answer_question(question)
    assert plan.question_type == "news_impact"
    messages = _ask_messages(monkeypatch, tmp_path, plan.question_type, question, plan=plan)
    assert "主张身份的区分" in "\n".join(m["content"] for m in messages)


def test_episode_natural_news_route_receives_q14_without_type_override(monkeypatch):
    from intelligence.services.query_understanding import understand_query

    monkeypatch.delenv(ENV_FLAG, raising=False)
    # The material-proxy query takes a different real route; this checks the
    # existing news door, not a claim that every news-like material reaches it.
    frame = understand_query("这条消息对液冷有什么影响？").task_frame
    assert frame.question_type == "news_impact"
    payload = json.loads(build_episode_input(frame, _context(frame), _registry()))
    assert "主张身份的区分" in payload["question_type_rules"]


def test_q14_layers_keep_fact_inference_and_price_boundaries(monkeypatch):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    for question_type in ("news_impact", "fact_check"):
        text = workflow_guidance(question_type)
        assert "事实、解读与情绪表达" in text
        assert "来源、对象、时间和确认阶段" in text
        assert "传播次数与独立来源数分开" in text
        assert "已证实事实也不自动成为交易指令" in text
        assert "不用实际涨幅减一个猜测的合理涨幅" in text
        assert "摘要保留原有条件" in text
    monkeypatch.setenv(ENV_FLAG, "0")
    assert workflow_guidance("news_impact") == workflow_guidance("fact_check") == ""


def test_explicit_route_override_does_not_inherit_envelope_workflow(monkeypatch, tmp_path):
    plan = SimpleNamespace(
        question_type="quick_fact", query_envelope=SimpleNamespace(question_type="kol_review")
    )
    messages = _ask_messages(
        monkeypatch, tmp_path, "quick_fact", "这个数字是多少", plan=plan, override="quick_fact"
    )
    assert HEADING not in "\n".join(m["content"] for m in messages)


@pytest.mark.parametrize("question_type,question,marker", CASES)
def test_material_only_cannot_get_tools_from_guidance(monkeypatch, question_type, question, marker):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    frame = replace(_frame(), question_type=question_type, raw_question=question)
    registry = _registry().with_read_scope("material_only")
    payload = json.loads(build_episode_input(frame, _context(frame), registry))
    assert marker in payload["question_type_rules"]
    assert registry.tool_definitions() == []
    assert "market_data" not in payload["available_tools"]


def test_tool_limitations_reach_model_definitions_without_granting_tools():
    def never_run(*_args, **_kwargs):
        raise AssertionError("metadata projection must not perform IO")

    registry = default_registry({name: never_run for name in ("web_search", "graph_lookup", "financial_data")})
    definitions = {
        item["function"]["name"]: item["function"]["description"]
        for item in registry.tool_definitions()
    }
    assert "缺值不是零" in definitions["financial_data"]
    assert "不自动证明因果" in definitions["graph_lookup"]
    assert "摘要是线索" in definitions["web_search"]
    assert registry.tool_definitions(()) == []
    assert [item["function"]["name"] for item in registry.tool_definitions(("financial_data",))] == [
        "financial_data"
    ]


def test_source_rules_are_adapted_not_copied_as_new_permissions(monkeypatch):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    text = "\n".join(workflow_guidance(case[0]) for case in CASES)
    for foreign_api in ("finance_memory_write", "finance_provider_status", "run_sandbox", "terminal emit"):
        assert foreign_api not in text
    for fixed_threshold in ("0.5%", "40%", "60%", "1-2个季度"):
        assert fixed_threshold not in text
    assert "不硬编概率数字" in text
    assert "不宣称审查通过" in text
    assert "不自动升为投资结论" in text
