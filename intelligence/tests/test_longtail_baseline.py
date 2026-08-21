from __future__ import annotations

import json

from intelligence.services.episode_protocol import (
    build_episode_input,
    build_episode_instructions,
)
from intelligence.services.episode_semantic_verifier import _JUDGE_SYSTEM_PROMPT
from intelligence.services.lane_generation import _system_prompt
from intelligence.services.longtail_baseline import (
    ANALYTICAL_MARKERS,
    ENV_NAME,
    HEADING,
    assert_skill_contract,
    enabled,
    episode_rule,
    should_inject_decision,
    should_inject_frame,
    skill_body,
    skill_body_is_clean,
)
from intelligence.services.research_contract import TurnIntent
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import TurnDecision
from intelligence.tests.test_episode_protocol import _context, _frame, _registry


def _general_frame(*, confidence: float = 0.4) -> TaskFrame:
    return TaskFrame(
        raw_question="基于行情现状你认为周一的机会在哪",
        user_goal="形成条件化判断",
        question_type="general_finance_qa",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_answer",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="general_finance_evidence",
        confidence=confidence,
    )


def _decision(
    *,
    lane: str = "chat",
    question_type: str | None = "general_finance_qa",
    confidence: float = 0.45,
    reason: str = "",
    llm_failure_reason: str = "",
    owner: str | None = None,
) -> TurnDecision:
    intent = None
    if owner is not None:
        intent = TurnIntent(
            primary_subject=None,
            secondary_topics=(),
            question_type=question_type or "general_finance_qa",
            answer_owner=owner,
            comparison_entities=(),
            inherited_from_turn=None,
        )
    return TurnDecision(
        lane=lane,
        needs_retrieval=False,
        needs_memory=False,
        needs_template=False,
        question_type=question_type,
        confidence=confidence,
        reason=reason,
        llm_failure_reason=llm_failure_reason,
        turn_intent=intent,
    )


def test_flag_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NAME, raising=False)
    assert enabled() is False
    assert should_inject_frame(_general_frame()) is False
    assert should_inject_decision(_decision(llm_failure_reason="timeout")) is False


def test_trigger_low_confidence_general_qa(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    assert should_inject_frame(_general_frame(confidence=0.4)) is True
    assert should_inject_frame(_general_frame(confidence=0.6)) is False
    assert should_inject_frame(_frame()) is False


def test_trigger_safe_fallback(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    assert should_inject_decision(_decision(llm_failure_reason="timeout")) is True
    assert should_inject_decision(
        _decision(reason="Controller 不可用；安全降级为不检索的普通对话")
    ) is True
    assert should_inject_decision(_decision(reason="明确寒暄", question_type=None)) is False


def test_owner_yields(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    assert (
        should_inject_decision(
            _decision(llm_failure_reason="timeout", owner="stock-deep-dive")
        )
        is False
    )


def test_skill_file_matches_judge_markers() -> None:
    assert_skill_contract()
    body = skill_body()
    for marker in ANALYTICAL_MARKERS:
        assert marker in _JUDGE_SYSTEM_PROMPT
        assert marker in body


def test_redline_rejects_smuggled_market_numbers() -> None:
    fake = skill_body() + "\n放量超过二点五倍的半导体。"
    # 中文数字不够，必须挡住阿拉伯数字走私
    assert skill_body_is_clean(skill_body()) is True
    assert skill_body_is_clean(skill_body() + "\n放量 2.5 倍。") is False
    assert skill_body_is_clean(fake) is False


def test_episode_instructions_unchanged_when_off(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NAME, raising=False)
    frame = _frame()
    off_text = build_episode_instructions(frame, _context(frame), _registry())
    payload = json.loads(build_episode_input(frame, _context(frame), _registry()))
    assert HEADING not in off_text
    assert HEADING not in payload["question_type_rules"]
    assert episode_rule(frame) == ""


def test_episode_instructions_inject_when_on(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    frame = _general_frame()
    text = build_episode_instructions(frame, _context(frame), _registry())
    payload = json.loads(build_episode_input(frame, _context(frame), _registry()))
    assert HEADING not in text
    assert HEADING in payload["question_type_rules"]
    for marker in ANALYTICAL_MARKERS:
        assert marker in payload["question_type_rules"]


def test_lane_prompt_unchanged_when_off(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NAME, raising=False)
    decision = _decision(llm_failure_reason="timeout")
    prompt = _system_prompt(decision, False)
    assert HEADING not in prompt
    assert "不要套金融研究模板" in prompt


def test_lane_prompt_injects_on_safe_fallback(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    prompt = _system_prompt(_decision(llm_failure_reason="timeout"), False)
    assert HEADING in prompt
    assert "据此判断" in prompt
