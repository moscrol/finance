"""Prompt ownership, not semantic acceptance of any generated answer."""
from dataclasses import replace
import json
from uuid import uuid4

import pytest

from intelligence.eval.knevo_regression import load_suite
from intelligence.services.conversation_materials import ConversationMaterials
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import _question_type_rules, build_episode_input
from intelligence.services.material_grounding import material_grounding_payload
from intelligence.services.research_reasoning import guidance as reasoning_guidance
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.research_workflow_guidance import workflow_guidance
from intelligence.services.turn_controller import decide_turn

PACKS = tuple(case for case in load_suite() if case.case_id.startswith("K260917-pack"))
LEGACY_HEADINGS = ("跟踪表达契约", "情景树表达契约", "排序与情景表达契约")


def context_for(case):
    frame = decide_turn(case.question, conversation_materials=ConversationMaterials()).task_frame
    return frame, build_episode_context(frame, task_id=f"material-prompt-{uuid4().hex}")


@pytest.mark.parametrize("case", PACKS, ids=lambda case: case.case_id)
def test_numbered_material_contract_owns_prompt_without_dropping_questions(case, monkeypatch):
    monkeypatch.setenv("FINANCE_RESEARCH_REASONING", "off")
    frame, context = context_for(case)
    original_contract = context.contract.to_dict()
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    rules = payload["question_type_rules"]
    assert all(heading not in rules for heading in LEGACY_HEADINGS)
    assert "financial_data" not in rules
    assert "memory_lookup" not in rules
    assert "E1、E2" not in rules
    assert rules == workflow_guidance(frame.question_type)
    assert context.contract.to_dict() == original_contract
    assert payload["task_frame"]["raw_question"] == frame.raw_question == case.question.strip()
    assert payload["research_contract"] == json.loads(json.dumps({
        key: value for key, value in original_contract.items() if key != "task_id"
    }))
    assert payload["material_grounding"] == json.loads(json.dumps(material_grounding_payload(context.contract)))
    assert payload["material_grounding"]["finish_format"]["render_from_claims"] is True
    assert [(q["question_id"], q["text"]) for q in payload["material_delivery"]["questions"]] == [
        (q.question_id, q.text) for q in context.contract.material_contract.questions
    ]
    assert len(payload["material_delivery"]["questions"]) == 8
    assert payload["available_tools"] == ""
    assert context.contract.allowed_capabilities == ()


@pytest.mark.parametrize("scope,clarify", [
    ("full", False), ("local_only", False), (None, True), ("material_only", True),
])
def test_unsettled_or_non_material_scope_keeps_legacy_prompt(scope, clarify):
    frame, context = context_for(PACKS[0])
    ordinary = replace(context, contract=replace(context.contract, material_contract=None))
    expected = _question_type_rules(frame, ordinary)
    assert all(heading in expected for heading in LEGACY_HEADINGS)
    changed = replace(context, contract=replace(context.contract, material_contract=replace(
        context.contract.material_contract, data_scope=scope,
        classification="boundary_uncertain" if clarify else "constraint_confirmed",
    )))
    assert _question_type_rules(frame, changed) == expected


def test_material_prompt_preserves_typed_discipline_and_opt_in_reasoning(monkeypatch):
    monkeypatch.setenv("FINANCE_RESEARCH_WORKFLOW_GUIDANCE", "1")
    monkeypatch.setenv("FINANCE_RESEARCH_REASONING", "on")
    frame, context = context_for(PACKS[0])
    frame = replace(frame, question_type="news_impact")
    context = replace(context, contract=replace(context.contract, question_type=frame.question_type))
    rules = _question_type_rules(frame, context)
    assert "消息逐项拆为事实、解读与情绪表达" in rules
    assert "研究求证意识" in rules
    assert rules == workflow_guidance(frame.question_type) + reasoning_guidance(frame.question_type)
    monkeypatch.setenv("FINANCE_RESEARCH_REASONING", "off")
    assert _question_type_rules(frame, context) == workflow_guidance(frame.question_type)


def test_unnumbered_material_prompt_is_unchanged():
    frame, context = context_for(PACKS[0])
    context = replace(context, contract=replace(context.contract, material_contract=replace(
        context.contract.material_contract, questions=(),
    )))
    ordinary = replace(context, contract=replace(context.contract, material_contract=None))
    rules = _question_type_rules(frame, context)
    assert all(heading in rules for heading in LEGACY_HEADINGS)
    assert rules == _question_type_rules(frame, ordinary)
