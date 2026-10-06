"""Answer uncertainty is not an absent input; actual referents still block."""

from __future__ import annotations

import json

import pytest

from intelligence.services.query_understanding import understand_query
from intelligence.services.task_frame import (
    CLARIFICATION_INPUT_RULE, align_task_frame, build_task_frame,
)
from intelligence.services.turn_controller import decide_turn


QUESTION = "2026-07-22 高标股的晋级情况如何，有没有出现空档"
# Captured from the failed first response, not a model-generated test oracle.
D6_AMBIGUITIES = [
    "'高标'的板数阈值未明确（是≥5板、≥6板还是仅看最高板），不同口径下晋级与空档结论可能不同",
    "用户只关心高标段的梯队结构，还是需要完整涨停梯队及晋级率全景，未明确",
    "'空档'是仅指板位断层，还是包含'最高板清零（无高标）'的情形，口径未明确",
]


def _reply(ambiguities):
    return json.dumps({
        "route_id": "market_watch", "confidence": 0.8, "reason": "复盘当日梯队",
        "user_goal": "查看完整连板梯队，区分板位空档与候选晋级失败",
        "assumptions": ["按当日收盘的完整连板梯队呈现，并说明高标口径"],
        "ambiguities": ambiguities,
    }, ensure_ascii=False)


def test_frozen_d6_alignment_does_not_replace_answer_with_subject_question():
    frame = build_task_frame(QUESTION, understand_query(QUESTION))
    aligned = align_task_frame(frame, _reply(D6_AMBIGUITIES))
    assert aligned.clarification_question is None
    assert aligned.ambiguities == tuple(D6_AMBIGUITIES)
    assert aligned.subject == frame.subject
    assert aligned.required_outputs == frame.required_outputs


def test_alignment_call_receives_same_input_gap_rule():
    calls = []

    def complete(messages):
        calls.append(messages)
        return _reply(D6_AMBIGUITIES), object(), ""

    frame = build_task_frame(QUESTION, understand_query(QUESTION), llm_complete=complete)
    assert frame.clarification_question is None
    assert CLARIFICATION_INPUT_RULE in calls[0][0]["content"]


def test_frozen_d6_controller_reaches_research_and_receives_input_gap_guidance():
    calls = []

    def complete(messages):
        calls.append(messages)
        return _reply(D6_AMBIGUITIES), object(), ""

    decision = decide_turn(QUESTION, llm_complete=complete)
    assert decision.lane in {"research", "workflow"}
    assert decision.needs_retrieval
    assert decision.clarification_questions == ()
    assert len(calls) == 1
    assert CLARIFICATION_INPUT_RULE in calls[0][0]["content"]


@pytest.mark.parametrize("ambiguity", [
    "市场强弱结论可能不同，需要比较量价与广度",
    "量能指标可能改变结论，需要核对同口径数据",
    "统计对象包含全部连板股，晋级结论可能有分歧",
    "主体已明确为电力，后续结论可能改变",
    "研究结论不明，需检索后再判断",
    "市场可能是良性轮动，也可能是退潮，需要比较后续证据",
    "结论的边界仍不明确，需要结合样本量讨论",
    "风险边界不明，需比较波动和回撤，而非向用户索要数据权限",
    "题材边界有歧义，可完整呈现重叠成分股并按代码去重",
    "研究边界未明确，先呈现全样本并说明统计口径",
    "工具权限已明确，但推断边界还不明确",
    "不是读取边界不明确，而是结论边界不明确",
    "并非工具权限冲突，研究判断仍需比较样本",
    "不存在访问范围缺失的问题，只是统计结论不确定",
    "工具可用但推断范围不明，应继续研究",
    "数据源已选但统计范围不明，应说明分母",
    "研究范围不明，需读取全样本进行比较",
    "风险边界不明，读取公开材料能帮助判断",
    "研究边界不明，不是读取权限不明",
], ids=["conclusion", "quantity", "population", "known-subject", "research", "alternatives",
        "conclusion-boundary", "risk-boundary", "theme-boundary", "research-boundary",
        "known-permission", "denied-read", "denied-tool", "denied-existence", "nearby-tool",
        "nearby-source", "later-read", "later-public-read", "denied-later"])
def test_research_uncertainty_is_retained_without_subject_clarification(ambiguity):
    frame = build_task_frame(QUESTION, understand_query(QUESTION))
    aligned = align_task_frame(frame, _reply([ambiguity]))
    assert ambiguity in aligned.ambiguities
    assert aligned.clarification_question is None


@pytest.mark.parametrize("ambiguity,expected", [
    ("市场不明可能改变结论", "A 股、美股"),
    ("主体不明，可能改变工具和结论", "哪个明确主体"),
    ("“这条线”缺少可唯一绑定的主体（哪个板块或题材），可能改变工具和结论", "哪个明确主体"),
    ("分析对象存在冲突，可能指公司也可能指题材", "哪个明确主体"),
    ("主体不明，默认按电力研究，但材料原文缺失，需用户提供", "材料"),
    ("市场范围仍不明确，需用户选择", "A 股、美股"),
    ("不明的分析主体会改变结论", "哪个明确主体"),
    ("工具权限边界冲突，无法继续读取", "哪个数据源或工具"),
    ("主体还不明确，需用户确认", "哪个明确主体"),
    ("读取边界未给出，需用户授权", "哪个数据源或工具"),
    ("访问边界尚不明确，不可自行扩大访问范围", "哪个数据源或工具"),
    ("工具使用权限未指定，无法读取私有材料", "哪个数据源或工具"),
    ("未明确的数据源，需要用户选择账户", "哪个数据源或工具"),
], ids=["market", "subject", "unbound-reference", "conflict", "missing-material", "market-scope",
        "subject-before", "permission", "subject-still", "read-scope", "access-scope",
        "tool-use-permission", "source-before"])
def test_actual_missing_inputs_are_not_waived(ambiguity, expected):
    frame = build_task_frame(QUESTION, understand_query(QUESTION))
    aligned = align_task_frame(frame, _reply([ambiguity]))
    assert expected in (aligned.clarification_question or "")


@pytest.mark.parametrize("ambiguity", [
    "未明确的读取范围需要用户确认",
    "权限尚不明确，需用户授权读取",
    "不是研究边界不明，而是读取权限未给出",
    "不需要访问外部工具，但读取权限仍不明确",
    "无需索要外部工具权限；权限不明，需确认私有账户授权",
    "研究边界已明确，默认按全市场分析，但私有材料的读取范围缺失",
    "工具已选定，权限未明确，暂不能取数",
    "权限边界冲突，不可自行扩大读取范围",
], ids=["scope-before", "permission-before", "contrast", "separate-negation",
        "reverse-after-negation", "default-other-clause", "selected-tool", "permission-boundary"])
def test_explicit_access_gaps_survive_unrelated_negation_and_defaults(ambiguity):
    frame = build_task_frame(QUESTION, understand_query(QUESTION))
    aligned = align_task_frame(frame, _reply([ambiguity]))
    assert "允许的读取范围" in (aligned.clarification_question or "")
