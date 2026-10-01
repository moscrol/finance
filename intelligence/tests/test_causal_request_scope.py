"""Synthetic scope regressions from the GLM pilot; no provider calls."""
import itertools
import json
import uuid
from pathlib import Path

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.query_understanding import (
    is_market_cause_query,
    understand_query,
)

FIXTURE = Path(__file__).resolve().parents[2] / "docs/verification/fixtures/2026-10-01-glm-intent-negation.json"
CAUSAL_OUTPUTS = {"causal_chain", "counterpoint", "cause_attribution"}


def assert_scope(question, expected):
    envelope = understand_query(question)
    frame = envelope.task_frame
    context = build_episode_context(
        frame, task_id="scope-" + uuid.uuid4().hex, capabilities=("finance_query", "memory_lookup"),
        today="2026-10-01", latest_data_date="2026-09-30", timeout=30,
    )
    required = {o.output_id for o in context.contract.required_outputs if o.required}
    assert is_market_cause_query(question) is expected
    assert (envelope.question_type == "market_cause") is expected
    assert ("cause_attribution" in envelope.operators) is expected
    if expected:
        assert CAUSAL_OUTPUTS <= required
    else:
        assert not (CAUSAL_OUTPUTS & required)
    assert frame.raw_question == question
    assert context.contract.question == question


@pytest.mark.parametrize("case", json.loads(FIXTURE.read_text())["cases"], ids=lambda c: c["id"])
def test_frozen_pilot_reaches_the_right_contract(case):
    assert_scope(case["question"], case["expected_causal_task"])


@pytest.mark.parametrize("negation,verb,subject", list(itertools.product(
    ("不要", "不必", "无需", "不用", "别", "请勿"),
    ("解释", "分析", "推测"),
    ("市场上涨", "指数下跌"),
)))
def test_negated_task_does_not_become_a_required_output(negation, verb, subject):
    assert_scope(f"只查询两日成交额。{negation}{verb}{subject}的原因。", False)


@pytest.mark.parametrize("question", [
    "只给成交额，不解释市场涨跌原因。",
    "我不是要你解释市场涨跌原因，只比较两日成交额。",
    "无需对市场上涨的原因进行分析，只查询成交额。",
    "不要解释市场涨跌原因而是比较两日成交额。",
    "不要分析、推测或解释市场上涨原因，只给成交额。",
    "不要分析，推测或解释市场上涨原因，只给成交额。",
    "不要解释‘市场为什么上涨’，只比较两日成交额。",
    "报告写道“市场为什么上涨”，我只需要成交额对比。",
    "报告提到\"市场上涨的原因\"，只查询两日成交额。",
    "‘市场为什么上涨’不是我的问题，只比较成交额。",
])
def test_scope_and_reported_questions_are_not_new_tasks(question):
    assert_scope(question, False)


@pytest.mark.parametrize("question", [
    "请解释市场为什么没有上涨。",
    "请解释市场为什么不能上涨。",
    "市场上涨的原因不明，帮我分析。",
    "不要忽略市场上涨的原因。",
    "不要回避市场下跌的原因。",
    "不能不解释市场下跌的原因。",
    "不得不解释市场下跌的原因。",
    "不是不需要解释市场上涨原因。",
    "并非不需要解释市场上涨原因。",
    "不仅分析市场上涨原因，还要给出证据。",
    "不要只解释市场上涨原因，还要给出证据。",
    "能不能解释市场上涨的原因？",
    "可不可以解释市场下跌的原因？",
    "需不需要解释市场上涨的原因？",
    "不要解释市场下跌原因，但请解释市场上涨原因。",
    "不必比较两日成交额，请解释市场上涨原因。",
    "请解释市场上涨原因，但不要预测明天的成交额。",
    "不要解释个股上涨原因，而是请解释大盘上涨的原因。",
    "请回答‘市场为什么上涨’。",
    "请解释报告中提到的‘市场为什么上涨’。",
    "“半导体”板块为什么上涨？",
    "市场上涨。不要归因于降息，请分析真正原因。",
])
def test_positive_double_negative_and_mixed_tasks_survive(question):
    assert_scope(question, True)


def test_local_data_constraint_and_comparison_are_not_lost():
    case = json.loads(FIXTURE.read_text())["cases"][0]
    envelope = understand_query(case["question"])
    assert "comparison" in envelope.operators
    assert envelope.task_frame.material_contract.data_scope == "local_only"
    assert_scope(case["question"], False)
