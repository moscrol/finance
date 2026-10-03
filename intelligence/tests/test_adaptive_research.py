"""Perspective protocol and real-loop transport, not a semantic quality score."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.research_progress import ResearchProgressTracker, ToolCallDigest
from intelligence.services.adaptive_research import (
    adaptive_research_enabled,
    perspective_checkpoint_message,
    perspective_diagnostics,
    perspective_progress,
)
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.episode_protocol import build_episode_input, build_episode_instructions
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_plan import parse_research_plan, plan_to_public_dict, validate_plan_revision
from intelligence.tests.test_agent_episode_progress import (
    ScriptedModel, _budget_blocks, _context, _evidence_for, _finish_turn, _frame, _registry, _run, _runner, _tool_turn,
)
from intelligence.tests.test_research_plan import _plan_json


def _perspective(**overrides):
    return {
        "perspective_id": "sustainability",
        "question": "What evidence would overturn the initial explanation?",
        "status": "open",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "assessment": "Not yet investigated",
        "next_check": "Independent evidence beyond the first source",
        **overrides,
    }


def _plan(*perspectives, revision=1):
    return parse_research_plan(_plan_json(perspectives=list(perspectives), revision=revision))


@pytest.mark.parametrize("raw,expected", [(None, False), ("off", False), ("on", True), ("1", True), ("invalid", False)])
def test_candidate_is_explicit_opt_in(monkeypatch, raw, expected):
    monkeypatch.delenv("WORKBENCH_ADAPTIVE_RESEARCH", raising=False)
    if raw is not None:
        monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", raw)
    assert adaptive_research_enabled() is expected


def test_old_plan_wire_format_unchanged():
    plan = parse_research_plan(_plan_json())
    assert plan.perspectives == ()
    assert "perspectives" not in plan_to_public_dict(plan)


def test_perspectives_round_trip_and_retain_counterevidence():
    plan = _plan(_perspective(status="contested", supporting_evidence=["E1"], contradicting_evidence=["E2"]))
    payload = plan_to_public_dict(plan)
    assert parse_research_plan(json.dumps({"kind": "PLAN", **payload})) == plan
    assert perspective_diagnostics(plan, evidence=[_evidence_for("first"), _evidence_for("second")]) == ()
    assert perspective_diagnostics(plan, evidence=[_evidence_for("first")]) == ("E2",)


@pytest.mark.parametrize("value", [
    None, {}, [_perspective()] * 2,
    [_perspective(perspective_id=str(i)) for i in range(9)],
    [_perspective(status="done")],
    [_perspective(status=[])],
    [_perspective(status="supported")],
    [_perspective(status="contested")],
    [_perspective(status="blocked", assessment="")],
    [_perspective(status="not_relevant", assessment="")],
    [_perspective(supporting_evidence=["made-up-hash"])],
    [_perspective(supporting_evidence=["E0"])],
    [_perspective(supporting_evidence=["E01"])],
    [_perspective(supporting_evidence=["E\u00b2"])],
    [_perspective(supporting_evidence=[f"E{i}" for i in range(1, 10)])],
    [_perspective(question="x" * 301)],
    [_perspective(assessment="x" * 301)],
    [_perspective(next_check=None)],
    [_perspective(budget=999)],
])
def test_malformed_perspectives_cannot_grant_authority(value):
    with pytest.raises(ValueError):
        parse_research_plan(_plan_json(perspectives=value))


def test_revision_adds_viewpoints_but_cannot_silently_drop_them():
    initial = _plan(_perspective())
    expanded = _plan(_perspective(), _perspective(perspective_id="alternative"), revision=2)
    validate_plan_revision(initial, expanded, original_task_id="t", current_task_id="t")
    with pytest.raises(ValueError, match="cannot remove perspectives"):
        validate_plan_revision(expanded, _plan(_perspective(), revision=3), original_task_id="t", current_task_id="t")
    resolved = _plan(_perspective(), _perspective(perspective_id="alternative", status="not_relevant", assessment="Outside the question's horizon"), revision=3)
    validate_plan_revision(expanded, resolved, original_task_id="t", current_task_id="t")


def test_reference_validity_is_frozen_at_submission_not_laundered_by_later_evidence(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    tracker = ResearchProgressTracker()
    tracker.record_plan(_plan(_perspective(status="supported", supporting_evidence=["E1"])), evidence=[])
    tracker.record_call(ToolCallDigest("market_data", "fresh", "new", new_evidence=1))
    tracker.close_batch()
    view = tracker.model_view()["adaptive_research"]
    assert view["unknown_evidence_ids_at_submission"] == ["E1"]
    assert view["batches_since_plan"] == 1
    assert view["plan_recorded_after_batch"] == 0
    # A genuine new revision may use the now-observed E1. It still is only a model claim.
    tracker.record_plan(_plan(_perspective(status="supported", supporting_evidence=["E1"]), revision=2), evidence=[_evidence_for("first")])
    updated = tracker.model_view()["adaptive_research"]
    assert updated["unknown_evidence_ids_at_submission"] == []
    assert updated["plan_recorded_after_batch"] == 1
    assert "不是覆盖率评分" in updated["instruction"]
    assert not tracker.should_finalize()


def test_prompt_switch_changes_dynamic_input_only(monkeypatch):
    frame = _frame()
    context = _context(frame)
    registry = _registry(_runner)
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "off")
    original = json.loads(build_episode_input(frame, context, registry))
    constitution = build_episode_instructions(frame, context, registry)
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    candidate = json.loads(build_episode_input(frame, context, registry))
    assert "不套固定股票池" in candidate.pop("adaptive_research")
    assert candidate == original
    assert build_episode_instructions(frame, context, registry) == constitution


def _planned_tool_turn(query, call_id, *perspectives, revision=1):
    return replace(_tool_turn(query, call_id), content=_plan_json(perspectives=list(perspectives), revision=revision))


def test_real_loop_updates_perspectives_in_the_same_tool_round(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    monkeypatch.setenv("WORKBENCH_RESEARCH_PROGRESS", "on")
    monkeypatch.setenv("FORESIGHT_STRICT_DERIVATION", "1")
    model = ScriptedModel([
        _planned_tool_turn("first", "c1", _perspective()),
        _planned_tool_turn("alternative", "c2", _perspective(status="supported", supporting_evidence=["E1"]), _perspective(perspective_id="alternative"), revision=2),
        _finish_turn(("hash-first", "hash-alternative")),
    ])
    outcome = _run(model)
    assert outcome.status == "completed"
    assert len(model.calls) == 3
    assert len([event for event in outcome.events if event.kind == "tool_request"]) == 2
    assert len(outcome.plan.perspectives) == 2
    blocks = _budget_blocks(model)
    first = blocks[0]["research_progress"]["adaptive_research"]
    second = blocks[1]["research_progress"]["adaptive_research"]
    assert first["plan_revision"] == 1 and first["unresolved_perspective_ids"] == ["sustainability"]
    assert first["plan_revision_constraints"]["preserve_perspective_ids"] == ["sustainability"]
    assert second["plan_revision_constraints"]["preserve_perspective_ids"] == ["sustainability", "alternative"]
    assert second["plan_revision"] == 2 and second["plan_recorded_after_batch"] == 1
    assert second["unknown_evidence_ids_at_submission"] == []
    assert second["unresolved_perspective_ids"] == ["alternative"]
    states = [event.payload for event in outcome.events if event.kind == "tool_budget_state"]
    assert json.loads(states[-1]["model_content"])["runtime_budget"] == blocks[-1]
    assert "perspectives" in [event.payload for event in outcome.events if event.kind == "plan"][-1]


def test_based_revision_feedback_allows_retraction_and_real_loop_consumes_it(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    monkeypatch.setenv("WORKBENCH_RESEARCH_PROGRESS", "on")
    monkeypatch.setenv("FORESIGHT_STRICT_DERIVATION", "1")
    first = parse_research_plan(_plan_json(
        base_revision=0, perspectives=[_perspective()], branch_goals=["Self-proposed extension"],
    ))
    second = replace(
        first, revision=2, base_revision=1, revision_reason="This self-proposed angle is irrelevant.",
        answer_elements=("Direct answer",), branch_goals=(), perspectives=(),
    )
    model = ScriptedModel([
        replace(_tool_turn("first", "c1"), content=json.dumps({"kind": "PLAN", **plan_to_public_dict(first)})),
        replace(_tool_turn("alternative", "c2"), content=json.dumps({"kind": "PLAN", **plan_to_public_dict(second)})),
        _finish_turn(("hash-first", "hash-alternative")),
    ])
    outcome = _run(model)
    assert outcome.status == "completed" and outcome.plan == second
    assert outcome.usage.llm_calls == 3 and outcome.usage.tool_calls == 2
    assert outcome.usage.invalid_actions == 0
    blocks = _budget_blocks(model)
    for index, plan in enumerate((first, second)):
        view = blocks[index]["research_progress"]["adaptive_research"]
        constraint = json.loads(perspective_checkpoint_message(plan))["plan_revision_constraints"]
        assert view["plan_revision_constraints"] == constraint == {
            "minimum_revision": plan.revision + 1,
            "base_revision": plan.revision,
            "retraction_requires_revision_reason": True,
        }
    assert blocks[0]["research_progress"]["adaptive_research"]["unresolved_perspective_ids"] == ["sustainability"]
    assert blocks[1]["research_progress"]["adaptive_research"]["model_reported_perspectives"] == []
    assert blocks[1]["research_progress"]["adaptive_research"]["unresolved_perspective_ids"] == []
    assert len(outcome.evidence) == 2  # Retraction does not erase the previous observation.


def test_plan_only_submission_uses_the_same_progress_channel(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    model = ScriptedModel([
        ModelTurn(_plan_json(perspectives=[_perspective()]), (), "scripted", ""),
        _tool_turn("first", "c1"),
        _finish_turn(("hash-first",)),
    ])
    outcome = _run(model)
    assert outcome.status == "completed"
    assert _budget_blocks(model)[-1]["research_progress"]["adaptive_research"]["plan_revision"] == 1


def test_no_plan_is_visible_as_missing_not_complete_and_budget_still_closes(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    model = ScriptedModel([_tool_turn("first", "c1"), _finish_turn(("hash-first",))])
    outcome = _run(model, max_steps=1)
    view = _budget_blocks(model)[0]["research_progress"]["adaptive_research"]
    assert view["plan_revision"] is None
    assert view["model_reported_perspectives"] == []
    assert model.calls[-1]["tools"] == []
    assert outcome.status == "completed"
    assert [event.payload["reason"] for event in outcome.events if event.kind == "finalization"] == ["tool_budget_exhausted"]


def _run_deep(model, *, max_steps=8, runner=None):
    frame = _frame()
    context = _context(frame, max_steps=max_steps)
    context = replace(
        context,
        contract=replace(context.contract, research_tier="deep"),
        policy=replace(context.policy, tier="deep"),
    )
    return ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=_registry(_runner if runner is None else runner))


def test_deep_research_gets_one_checkpoint_after_first_observation(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    monkeypatch.setenv("FORESIGHT_STRICT_DERIVATION", "1")
    model = ScriptedModel([
        _tool_turn("first", "c1"),
        ModelTurn("```json\n" + _plan_json(perspectives=[_perspective(supporting_evidence=["E1"])]) + "\n```", (), "scripted", ""),
        _tool_turn("counter", "c2"),
        _finish_turn(("hash-first", "hash-counter")),
    ])
    outcome = _run_deep(model)
    assert outcome.status == "completed"
    assert outcome.usage.tool_calls == 2 and outcome.usage.llm_calls == 4
    assert [bool(call["tools"]) for call in model.calls] == [True, False, True, True]
    assert "首批取证后的研究复核" in model.calls[1]["messages"][-1]["content"]
    assert outcome.plan.perspectives[0].supporting_evidence == ("E1",)
    assert _budget_blocks(model)[-1]["research_progress"]["adaptive_research"]["plan_revision"] == 1


def test_checkpoint_does_not_repeat_after_malformed_plan(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    monkeypatch.setenv("FORESIGHT_STRICT_DERIVATION", "1")
    model = ScriptedModel([
        _tool_turn("first", "c1"),
        ModelTurn('{"kind":"PLAN"}', (), "scripted", ""),
        _tool_turn("counter", "c2"),
        _finish_turn(("hash-first", "hash-counter")),
    ])
    outcome = _run_deep(model)
    assert outcome.status == "completed"
    assert [bool(call["tools"]) for call in model.calls] == [True, False, True, True]
    assert outcome.usage.invalid_actions == 1


def test_checkpoint_cannot_reopen_exhausted_tool_budget(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    model = ScriptedModel([_tool_turn("first", "c1"), _finish_turn(("hash-first",))])
    outcome = _run_deep(model, max_steps=1)
    assert outcome.status == "completed"
    assert len(model.calls) == 2 and not model.calls[-1]["tools"]
    assert "首批取证后的研究复核" not in model.calls[-1]["messages"][-1]["content"]


def test_existing_perspectives_skip_the_deep_checkpoint(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    model = ScriptedModel([
        _planned_tool_turn("first", "c1", _perspective()),
        _finish_turn(("hash-first",)),
    ])
    outcome = _run_deep(model)
    assert outcome.status == "completed"
    assert len(model.calls) == 2 and model.calls[-1]["tools"]


def test_disabled_feedback_is_byte_compatible(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "off")
    tracker = ResearchProgressTracker()
    tracker.record_call(ToolCallDigest("market_data", "first", "new", new_evidence=1))
    tracker.close_batch()
    before = tracker.model_view()
    tracker.record_plan(_plan(_perspective()), evidence=[])
    assert tracker.model_view() == before
    assert "adaptive_research" not in before


def _revision_contract_plan(*, revision=4, perspectives=()):
    return parse_research_plan(_plan_json(
        answer_elements=["Comparison", "Counterevidence", "Unknowns"],
        branch_goals=["Verify first alternative", "Verify second alternative"],
        perspectives=list(perspectives),
        revision=revision,
    ))


def test_checkpoint_exposes_the_actual_accepted_plan_constraints():
    # Existing perspectives skip the checkpoint; only regular feedback retains their IDs.
    plan = _revision_contract_plan()
    message = json.loads(perspective_checkpoint_message(plan))
    assert message["plan_revision_constraints"] == {
        "minimum_revision": 5,
        "preserve_answer_elements": list(plan.answer_elements),
        "preserve_branch_goals": list(plan.branch_goals),
        "preserve_perspective_ids": [],
    }
    assert "branch_goals" in message["instruction"]
    assert "answer_elements" in message["instruction"]


def test_regular_feedback_exposes_the_same_detached_revision_constraints():
    plan = _revision_contract_plan(perspectives=[_perspective()])
    view = perspective_progress(plan, batch=3, plan_batch=1, unknown_evidence_ids=())
    contract = json.loads(perspective_checkpoint_message(plan))["plan_revision_constraints"]
    assert view["plan_revision_constraints"] == contract
    view["plan_revision_constraints"]["preserve_answer_elements"].append("Not committed")
    assert "Not committed" not in plan.answer_elements
    updated = _revision_contract_plan(revision=5)
    assert perspective_progress(updated, batch=3, plan_batch=3, unknown_evidence_ids=())["plan_revision_constraints"]["minimum_revision"] == 6


def test_sufficient_single_fact_checkpoint_allows_finish_without_a_plan():
    message = json.loads(perspective_checkpoint_message())
    assert "直接 FINAL_JSON" in message["instruction"]
    assert "不必提交 PLAN" in message["instruction"]
    assert message["plan_revision_constraints"] is None


def test_real_checkpoint_carries_the_accepted_plan_and_keeps_revision_admission(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    monkeypatch.setenv("FORESIGHT_STRICT_DERIVATION", "1")
    first = _revision_contract_plan(revision=1)
    second = _revision_contract_plan(revision=2, perspectives=[_perspective(supporting_evidence=["E1"])])
    model = ScriptedModel([
        replace(_tool_turn("first", "c1"), content=json.dumps({"kind": "PLAN", **plan_to_public_dict(first)})),
        ModelTurn(json.dumps({"kind": "PLAN", **plan_to_public_dict(second)}), (), "scripted", ""),
        _finish_turn(("hash-first",)),
    ])
    outcome = _run_deep(model)
    checkpoint = json.loads(model.calls[1]["messages"][-1]["content"])
    assert checkpoint["plan_revision_constraints"]["preserve_answer_elements"] == list(first.answer_elements)
    assert checkpoint["plan_revision_constraints"]["preserve_branch_goals"] == list(first.branch_goals)
    assert checkpoint["plan_revision_constraints"]["minimum_revision"] == 2
    assert checkpoint["plan_revision_constraints"]["preserve_perspective_ids"] == []
    assert outcome.plan == second
    assert outcome.usage.invalid_actions == 0
    assert outcome.usage.llm_calls == 3 and outcome.usage.tool_calls == 1
    assert [bool(call["tools"]) for call in model.calls] == [True, False, True]


def test_single_fact_can_finish_in_the_checkpoint_without_an_extra_round(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    monkeypatch.setenv("FORESIGHT_STRICT_DERIVATION", "1")
    model = ScriptedModel([_tool_turn("first", "c1"), _finish_turn(("hash-first",))])
    outcome = _run_deep(model)
    assert outcome.status == "completed" and outcome.plan is None
    assert outcome.usage.invalid_actions == 0
    assert outcome.usage.llm_calls == 2 and outcome.usage.tool_calls == 1
    assert model.calls[1]["tools"] == []


@pytest.mark.parametrize("changed,reason", [
    ({"answer_elements": ["Comparison"]}, "cannot remove answer elements"),
    ({"branch_goals": ["Verify first alternative"]}, "cannot remove branch goals"),
    ({"revision": 1}, "revision"),
])
def test_checkpoint_still_rejects_invalid_revisions(monkeypatch, changed, reason):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    monkeypatch.setenv("FORESIGHT_STRICT_DERIVATION", "1")
    first = _revision_contract_plan(revision=1)
    payload = {"kind": "PLAN", **plan_to_public_dict(first), "revision": 2, **changed}
    model = ScriptedModel([
        replace(_tool_turn("first", "c1"), content=json.dumps({"kind": "PLAN", **plan_to_public_dict(first)})),
        ModelTurn(json.dumps(payload), (), "scripted", ""),
        _finish_turn(("hash-first",)),
    ])
    outcome = _run_deep(model)
    assert outcome.plan == first
    assert outcome.usage.invalid_actions == 1
    assert any(reason in str(event.payload.get("reason")) for event in outcome.events if event.kind == "invalid_action")
    assert outcome.usage.tool_calls == 1 and outcome.usage.llm_calls == 3
    assert model.calls[1]["tools"] == []


def test_checkpoint_accepts_reordering_preserved_items(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    first = _revision_contract_plan(revision=1)
    second = replace(first, revision=2, answer_elements=first.answer_elements[::-1], branch_goals=first.branch_goals[::-1])
    model = ScriptedModel([
        replace(_tool_turn("first", "c1"), content=json.dumps({"kind": "PLAN", **plan_to_public_dict(first)})),
        ModelTurn(json.dumps({"kind": "PLAN", **plan_to_public_dict(second)}), (), "scripted", ""),
        _finish_turn(("hash-first",)),
    ])
    outcome = _run_deep(model)
    assert outcome.plan == second and outcome.usage.invalid_actions == 0


def test_empty_evidence_checkpoint_cannot_claim_completed(monkeypatch):
    monkeypatch.setenv("WORKBENCH_ADAPTIVE_RESEARCH", "on")
    monkeypatch.setenv("FORESIGHT_STRICT_DERIVATION", "1")

    def empty_runner(query, context):
        return [], "No local evidence", ProviderTrace(provider="test:empty", capability="market_data", status="success", result_count=0)

    partial = ModelTurn(json.dumps({
        "status": "partial", "draft": "Insufficient evidence to assess.",
        "gaps": ["No local evidence"],
        "bindings": [{"output_id": "direct_assessment", "evidence_hashes": [], "gap": "No local evidence"}],
    }), (), "scripted", "")
    model = ScriptedModel([_tool_turn("first", "c1"), _finish_turn(()), partial])
    outcome = _run_deep(model, runner=empty_runner)
    assert outcome.status == "partial"
    assert outcome.usage.invalid_actions == 1
    assert model.calls[1]["tools"] == []
    assert outcome.usage.tool_calls == 1 and outcome.usage.llm_calls == 3
