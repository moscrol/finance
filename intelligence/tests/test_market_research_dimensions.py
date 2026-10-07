"""Research lenses reach the real author contract without becoming chapters."""
from __future__ import annotations

from dataclasses import replace
import json
from uuid import uuid4

import pytest

from intelligence.runtime.turn_control_core import TurnControlCore
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import (
    EpisodeFinishRejection,
    build_episode_input,
    validate_episode_finish,
)
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import release_root_budget
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame, derive_required_outputs, rebase_task_frame


QUESTION = "2026-07-22 复盘高标连板晋级有没有断层？"
DIMENSIONS = {"market_summary", "mainline_structure", "risk_signals"}
EVIDENCE = (AgentEvidence(
    tool="market_data", title="连板梯队", detail="2026-07-22 最高板为华银电力五连板。",
    source="本地行情", source_date="2026-07-22", evidence_tier="L4", content_hash="ladder-hash",
),)
DRAFT = "7月22日最高板为华银电力五连板。单一成功者名单不能证明整体晋级没有断层，尚缺完整候选与失败名单。"


@pytest.fixture
def contexts():
    task_ids = []

    def build(frame, **kwargs):
        task_id = f"research-dimensions-{uuid4().hex}"
        task_ids.append(task_id)
        return build_episode_context(frame, task_id=task_id, today="2026-07-23", **kwargs)

    yield build
    for task_id in task_ids:
        release_root_budget(task_id)


def _frame(question=QUESTION):
    return TurnControlCore().control(
        question, llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    ).task_frame


def _payload(frame, context):
    return json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))


def _finish(*, omit=(), extra=()):
    return {
        "status": "completed", "draft": DRAFT, "gaps": [],
        "bindings": [
            {"output_id": output_id, "evidence_hashes": ["E1"], "basis": "evidence", "gap": ""}
            for output_id in ("direct_assessment", "evidence_boundary", *extra)
            if output_id not in omit
        ],
    }


@pytest.mark.parametrize("question", (
    QUESTION,
    "2026-07-22 复盘市场总览、主线和风险",
))
def test_default_lenses_reach_author_once_without_forcing_chapters(question, contexts, monkeypatch):
    monkeypatch.setenv("FINANCE_READING_BASELINE", "1")
    frame = _frame(question)
    assert frame.question_type == "dated_market_review"
    assert frame.raw_question == question
    assert frame.user_goal == question
    context = contexts(frame, perspective_context="用户选中的观点视角")
    slots = {item.output_id: item for item in context.contract.required_outputs}
    assert {key for key, item in slots.items() if item.required} == {
        "direct_assessment", "evidence_boundary",
    }
    assert DIMENSIONS.issubset(slots)
    assert all(slots[key].evidence_types for key in DIMENSIONS)

    payload = _payload(frame, context)
    contract = payload["research_contract"]
    assert {item["output_id"] for item in contract["research_dimensions"]} == DIMENSIONS
    assert DIMENSIONS.isdisjoint(item["output_id"] for item in contract["required_outputs"])
    assert "用户原问明确要求的内容仍须覆盖" in payload["research_dimensions_rule"]
    assert "FY-A09" in payload["reading_baseline"]  # existing counterpoint discipline
    assert payload["perspective_context"] == "用户选中的观点视角"
    assert "不是固定视角" in payload["reading_baseline_rule"]


def test_unfilled_lenses_do_not_reject_bounded_answer(contexts):
    context = contexts(_frame())
    finish = validate_episode_finish(_finish(), context=context, evidence=EVIDENCE)
    assert finish.status == "completed"
    assert finish.draft == DRAFT
    assert {item.output_id for item in finish.bindings} == {"direct_assessment", "evidence_boundary"}


@pytest.mark.parametrize("missing", ("direct_assessment", "evidence_boundary"))
def test_core_delivery_still_requires_evidence(missing, contexts):
    context = contexts(_frame())
    with pytest.raises(EpisodeFinishRejection, match=missing):
        validate_episode_finish(_finish(omit=(missing,)), context=context, evidence=EVIDENCE)


def test_explicit_required_dimension_is_not_demoted(contexts):
    frame = _frame()
    frame = rebase_task_frame(
        frame, question_type=frame.question_type, subject=frame.subject,
        required_outputs=("risk_signals",),
    )
    context = contexts(frame)
    payload = _payload(frame, context)["research_contract"]
    assert "risk_signals" in {item["output_id"] for item in payload["required_outputs"] if item["required"]}
    assert "risk_signals" not in {item["output_id"] for item in payload["research_dimensions"]}
    with pytest.raises(EpisodeFinishRejection, match="risk_signals"):
        validate_episode_finish(_finish(), context=context, evidence=EVIDENCE)
    assert validate_episode_finish(
        _finish(extra=("risk_signals",)), context=context, evidence=EVIDENCE,
    ).status == "completed"


def test_explicit_requirement_survives_default_collision_restore_and_type_rebase(contexts):
    frame = _frame("目前市场的主线是什么")
    assert "risk_signals" in frame.required_outputs
    frame = rebase_task_frame(
        frame, question_type=frame.question_type, subject=frame.subject,
        required_outputs=("risk_signals",),
    )
    restored = TaskFrame.from_dict(frame.to_dict())
    assert restored is not None
    assert restored.required_output_additions == ("risk_signals",)
    rebased = rebase_task_frame(
        restored, question_type="dated_market_review", subject=restored.subject,
    )
    context = contexts(rebased)
    assert "risk_signals" in {item.output_id for item in context.contract.required_outputs if item.required}
    with pytest.raises(EpisodeFinishRejection, match="risk_signals"):
        validate_episode_finish(_finish(), context=context, evidence=EVIDENCE)


@pytest.mark.parametrize("additions", ("risk_signals", [1], ["not-in-required-outputs"]))
def test_malformed_restored_additions_are_rejected(additions):
    payload = _frame().to_dict()
    payload["required_output_additions"] = additions
    assert TaskFrame.from_dict(payload) is None


def test_empty_additions_do_not_change_legacy_frame_shape():
    frame = _frame()
    assert "required_output_additions" not in frame.to_dict()
    restored = TaskFrame.from_dict(frame.to_dict())
    assert restored == frame
    assert restored.task_frame_hash == frame.task_frame_hash


def test_multiday_comparison_requirements_keep_priority(contexts):
    question = "2026-07-16 到 07-22 这几天，成交量和涨停家数的变化说明了什么"
    required = derive_required_outputs("dated_market_review", question)
    assert required == ("change_summary", "direct_assessment", "supporting_evidence", "risk_signals")
    frame = replace(_frame(), raw_question=question, required_outputs=required)
    context = contexts(frame)
    assert {item.output_id for item in context.contract.required_outputs if item.required} == set(required)
    with pytest.raises(EpisodeFinishRejection):
        validate_episode_finish(_finish(), context=context, evidence=EVIDENCE)


def test_optional_dimension_cannot_borrow_unknown_source(contexts):
    context = contexts(_frame())
    finish = _finish(extra=("mainline_structure",))
    finish["bindings"][-1]["evidence_hashes"] = ["forged-source"]
    with pytest.raises(EpisodeFinishRejection) as rejected:
        validate_episode_finish(finish, context=context, evidence=EVIDENCE)
    assert rejected.value.code == "forged_hash"


def test_dimension_split_preserves_research_plan_permissions_time_and_budget(contexts, monkeypatch):
    monkeypatch.setattr("intelligence.services.research_contract.time.monotonic", lambda: 1000.0)
    frame = _frame()
    current = contexts(frame, timeout=40.0, synthesis_reserve=6.0)
    previous = contexts(replace(frame, required_outputs=(
        "direct_assessment", "market_summary", "mainline_structure", "risk_signals",
    )), timeout=40.0, synthesis_reserve=6.0)
    assert current.contract.allowed_capabilities == previous.contract.allowed_capabilities
    assert current.contract.evidence_plan == previous.contract.evidence_plan
    assert current.contract.timeframe == previous.contract.timeframe
    assert current.information_cutoff == previous.information_cutoff
    assert current.policy == previous.policy
    assert current.deadline == previous.deadline


def test_rebase_supplies_new_delivery_requirements_without_losing_explicit_extra(contexts):
    frame = _frame("固态电池产业链怎么分")
    frame = replace(frame, required_outputs=(*frame.required_outputs, "invalidation_conditions"))
    rebased = rebase_task_frame(
        frame, question_type="dated_market_review", subject=frame.subject,
    )
    context = contexts(rebased)
    assert {"direct_assessment", "evidence_boundary", "invalidation_conditions"}.issubset(
        item.output_id for item in context.contract.required_outputs if item.required
    )
    assert all(not item.required for item in context.contract.required_outputs if item.output_id in DIMENSIONS)


def test_numbered_local_material_delivery_keeps_each_required_question(contexts):
    frame = understand_query(
        "只用本地数据。\n1. 2026-07-22 最高连板是谁？\n2. 2026-07-22 市场主线和风险是什么？"
    ).task_frame
    frame = replace(frame, question_type="dated_market_review", evidence_policy="dated_a_share_market")
    context = contexts(frame)
    slots = {item.output_id for item in context.contract.required_outputs if item.required}
    assert {"answer_q1", "answer_q2", "evidence_boundary"} == slots
    payload = _payload(frame, context)
    assert "research_dimensions" not in payload["research_contract"]
    assert "research_dimensions_rule" not in payload
    with pytest.raises(EpisodeFinishRejection):
        validate_episode_finish(_finish(), context=context, evidence=EVIDENCE)


def test_other_question_types_do_not_gain_dimension_projection(contexts):
    frame = _frame("目前市场的主线是什么")
    assert frame.question_type == "market_watch"
    payload = _payload(frame, contexts(frame))
    assert "research_dimensions" not in payload["research_contract"]
    assert "research_dimensions_rule" not in payload
    assert "risk_signals" in {item["output_id"] for item in payload["research_contract"]["required_outputs"]}
