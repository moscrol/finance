"""Delivery and rollback tests, not proof of improved model reasoning."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from intelligence.services import knowledge_injection_policy, research_reasoning
from intelligence.services.episode_protocol import build_episode_input, build_episode_instructions
from intelligence.tests.test_episode_protocol import _context, _frame, _registry
from intelligence.tests.test_research_workflow_guidance import _ask_messages


@pytest.mark.parametrize("setting", [None, "off", "0", "false", "no", "", "typo"])
def test_defaults_and_invalid_values_fail_closed(monkeypatch, setting):
    if setting is None:
        monkeypatch.delenv(research_reasoning.ENV_FLAG, raising=False)
    else:
        monkeypatch.setenv(research_reasoning.ENV_FLAG, setting)
    assert research_reasoning.guidance("market_forecast") == ""
    assert research_reasoning.observation_guidance("market_forecast") == ""


@pytest.mark.parametrize("setting", ["on", "1", "true", "yes", " ON "])
def test_explicit_enable(monkeypatch, setting):
    monkeypatch.setenv(research_reasoning.ENV_FLAG, setting)
    assert research_reasoning.HEADING in research_reasoning.guidance("market_cause")


@pytest.mark.parametrize("kind", [
    "market_watch", "market_review", "dated_market_review", "market_forecast",
    "market_cause", "stock_deep_dive", "valuation_estimate", "theme_analysis",
    "financial_analysis", "fact_check", "methodology_discussion", "general_finance_qa",
])
def test_dynamic_delivery_does_not_change_contract_or_static_system(monkeypatch, kind):
    frame = replace(_frame(), question_type=kind)
    context, registry = _context(frame), _registry()
    monkeypatch.setenv(research_reasoning.ENV_FLAG, "off")
    before = json.loads(build_episode_input(frame, context, registry))
    system = build_episode_instructions(frame, context, registry)
    monkeypatch.setenv(research_reasoning.ENV_FLAG, "on")
    after = json.loads(build_episode_input(frame, context, registry))
    assert research_reasoning.guidance(kind) in after["question_type_rules"]
    assert after["question_type_rules"].replace(research_reasoning.guidance(kind), "") == before["question_type_rules"]
    after.pop("question_type_rules")
    before.pop("question_type_rules")
    assert after == before
    assert build_episode_instructions(frame, context, registry) == system
    assert research_reasoning.HEADING not in system
    assert context.contract.allowed_capabilities == ("market_data",)


@pytest.mark.parametrize("kind", [
    "quick_fact", "concept_definition", "market_technical", "external_market",
    "disclosure_scan", "watchlist_digest", "general_knowledge", "", "future_unknown_kind",
])
def test_non_research_questions_have_no_extra_guidance(monkeypatch, tmp_path, kind):
    monkeypatch.setenv(research_reasoning.ENV_FLAG, "on")
    assert research_reasoning.guidance(kind) == ""
    assert research_reasoning.observation_guidance(kind) == ""
    frame = replace(_frame(), question_type=kind)
    payload = build_episode_input(frame, _context(frame), _registry())
    assert research_reasoning.HEADING not in payload
    messages = _ask_messages(monkeypatch, tmp_path, kind, "只告诉我这个数字")
    assert research_reasoning.HEADING not in "\n".join(m["content"] for m in messages)


def test_market_knowledge_gate_remains_closed(monkeypatch, tmp_path):
    monkeypatch.setenv(research_reasoning.ENV_FLAG, "on")
    monkeypatch.delenv(knowledge_injection_policy.ENV_FLAG, raising=False)
    assert not knowledge_injection_policy.inject_knowledge("market_watch")
    assert knowledge_injection_policy.reading_guidance_for("market_watch") == ""
    messages = _ask_messages(monkeypatch, tmp_path, "market_watch", "为什么放量却下跌")
    assert research_reasoning.guidance("market_watch") in "\n".join(m["content"] for m in messages)


def test_explicit_factual_override_wins_over_research_envelope(monkeypatch, tmp_path):
    monkeypatch.setenv(research_reasoning.ENV_FLAG, "on")
    plan = SimpleNamespace(
        question_type="quick_fact", query_envelope=SimpleNamespace(question_type="market_watch")
    )
    messages = _ask_messages(
        monkeypatch, tmp_path, "quick_fact", "只报成交额", plan=plan, override="quick_fact"
    )
    assert research_reasoning.HEADING not in "\n".join(m["content"] for m in messages)


def test_material_only_gets_no_tool_grants(monkeypatch):
    monkeypatch.setenv(research_reasoning.ENV_FLAG, "on")
    frame = _frame()
    registry = _registry().with_read_scope("material_only")
    payload = json.loads(build_episode_input(frame, _context(frame), registry))
    assert research_reasoning.HEADING in payload["question_type_rules"]
    assert registry.tool_definitions() == []
    assert "market_data" not in payload["available_tools"]


@pytest.mark.parametrize("progress", ["on", "off"])
@pytest.mark.parametrize("setting,kind,expected", [
    ("on", "market_forecast", True), ("off", "market_forecast", False),
    ("on", "quick_fact", False),
])
def test_real_loop_delivers_observation_hint_without_extra_calls(
    monkeypatch, progress, setting, kind, expected
):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.tests import test_agent_episode_progress as fixtures

    monkeypatch.setenv(research_reasoning.ENV_FLAG, setting)
    monkeypatch.setenv("WORKBENCH_RESEARCH_PROGRESS", progress)
    frame = replace(fixtures._frame(), question_type=kind)
    context = fixtures._context(frame, max_steps=3)
    model = fixtures.ScriptedModel([
        fixtures._tool_turn("q1", "c1"), fixtures._finish_turn(("hash-q1",))
    ])
    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame, context=context, registry=fixtures._registry(fixtures._runner)
    )
    assert outcome.status == "completed"
    assert len(model.calls) == 2
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0].content_hash == "hash-q1"
    blocks = fixtures._budget_blocks(model)
    assert len(blocks) == 1
    assert ("research_reasoning" in blocks[0]) == expected
    assert blocks[0]["remaining_tool_calls"] == 2
    states = [event for event in outcome.events if event.kind == "tool_budget_state"]
    assert len(states) == 1
    assert json.loads(states[0].payload["model_content"])["runtime_budget"] == blocks[0]
    if expected:
        assert blocks[0]["research_reasoning"] == research_reasoning.observation_guidance(kind)


def test_synthesis_fallback_injects_only_when_no_prepared_messages(monkeypatch, tmp_path):
    from intelligence.services.ask import prepare_existing_answer
    from intelligence.services.ask_types import AskOptions, AskResult

    monkeypatch.setenv(research_reasoning.ENV_FLAG, "on")
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path))
    result = AskResult("为什么放量下跌", None, None, None, None)
    result.answer_spec = SimpleNamespace(
        presentation_kind="general", presentation_title="市场", to_prompt_block=lambda: "已有证据"
    )
    result.question_plan = SimpleNamespace(question_type="market_review")
    options = AskOptions(query=result.query)
    prepared = prepare_existing_answer(options, result)
    messages = prepared.result.prepared_synthesis_messages
    assert research_reasoning.HEADING in "\n".join(m["content"] for m in messages)
    assert prepare_existing_answer(options, result).result.prepared_synthesis_messages is messages


def test_guidance_does_not_define_lenses_or_mandatory_reflection(monkeypatch):
    monkeypatch.setenv(research_reasoning.ENV_FLAG, "on")
    text = research_reasoning.guidance("market_watch")
    for boundary in (
        "单纯查数", "没有封闭视角菜单", "不默认从宏观或流动性开始",
        "不能单独证明因果", "不为凑数量编反方", "当时可知时间",
        "放弃解释", "保留未知", "合成阶段仅使用已提供材料", "不新增权限",
        "统计对象、分组口径、分母、时间窗", "当前占比不能直接说明增量分布",
        "行业分组不能替代市值分组", "不能唯一识别资金来源与买卖动机",
        "订单不等于交付", "不把不确定扩大为全盘拒答",
    ):
        assert boundary in text


def _behavior_cases():
    path = Path(__file__).parents[1] / "eval/fixtures/research-reasoning-awareness.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["turns"] and case["criteria"] for case in cases)
    return {case["id"]: case for case in cases}


@pytest.mark.parametrize("case_id,shares,increment,contribution", [
    ("share-up-amount-down", (Fraction(1, 5), Fraction(3, 10)), -20, Fraction(1, 20)),
    ("increment-with-denominator", (Fraction(1, 10), Fraction(3, 20)), 80, Fraction(2, 5)),
])
def test_counterexample_fixture_arithmetic(case_id, shares, increment, contribution):
    # Fixture consistency only, not an assertion about model behavior. A ratio
    # of two negative changes is not a contribution to positive new turnover.
    data = _behavior_cases()[case_id]["numbers"]
    assert tuple(Fraction(data[f"sector_{period}"], data[f"market_{period}"]) for period in ("before", "after")) == shares
    sector_change = data["sector_after"] - data["sector_before"]
    market_change = data["market_after"] - data["market_before"]
    assert sector_change == increment
    assert Fraction(sector_change, market_change) == contribution


def test_margin_counterexample_does_not_confuse_ratio_and_amount():
    data = _behavior_cases()["margin-is-not-profit"]["numbers"]
    gross_profits = []
    margins = []
    for period in ("before", "after"):
        unit_profit = data[f"price_{period}"] - data[f"cost_{period}"]
        gross_profits.append(data[f"quantity_{period}"] * unit_profit)
        margins.append(Fraction(unit_profit, data[f"price_{period}"]))
    assert gross_profits == [24, 24]
    assert margins == [Fraction(1, 5), Fraction(3, 11)]
