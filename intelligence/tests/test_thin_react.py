"""Evaluation driver boundaries; synthetic data only, no live provider calls."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from intelligence.eval.thin_react import run_thin_react
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn

TOOLS = [{"type": "function", "function": {
    "name": "read_number", "description": "Read the fixture integer.",
    "parameters": {"type": "object", "properties": {}},
}}]
CALL = ModelToolCall("call-1", "read_number", {})


class Model:
    def __init__(self, turns):
        self.turns = iter(turns)
        self.inputs = []

    def complete(self, **kwargs):
        self.inputs.append(kwargs)
        value = next(self.turns)
        if isinstance(value, Exception):
            raise value
        return value


def run(tmp_path, turns, **kwargs):
    model = Model(turns)
    dispatched = []

    def execute(name, args, remaining):
        dispatched.append((name, args, remaining))
        return {"value": 17, "source": "synthetic"}

    result = run_thin_react(
        model, question="Read the fixture number.", expected_model="model-g",
        tools=TOOLS, execute_tool=kwargs.pop("execute_tool", execute),
        artifact=tmp_path / "episode.json", **kwargs,
    )
    assert json.loads((tmp_path / "episode.json").read_text()) == result
    return result, dispatched, model


def test_live_shaped_tool_turn_round_trip_is_automatically_admitted(tmp_path):
    result, calls, model = run(tmp_path, [
        ModelTurn("", (CALL,), served_model="model-g", provider_attempts=2),
        ModelTurn("17", (), served_model="model-g"),
    ])
    assert result["status"] == "completed"
    assert result["admission_exit"] == 0
    assert result["answer"] == "17"
    assert len(calls) == result["tool_calls"] == 1
    assert 0 < calls[0][2] <= 90
    assert result["events"][0]["payload"]["provider_attempts"] == 2
    tool_message = next(m for m in model.inputs[1]["messages"] if m["role"] == "tool")
    assert tool_message["tool_call_id"] == "call-1"
    assert json.loads(tool_message["content"])["value"] == 17


@pytest.mark.parametrize("served,exit_code", [("wrong-model", 1), (None, 2), ("", 2)])
def test_identity_failure_stops_before_tool_dispatch(tmp_path, served, exit_code):
    result, calls, _ = run(tmp_path, [ModelTurn("", (CALL,), served_model=served)])
    assert result["status"] == "failed"
    assert result["failure"] == "model_admission_rejected"
    assert result["admission_exit"] == exit_code
    assert not calls


def test_later_wrong_model_invalidates_whole_episode(tmp_path):
    result, calls, _ = run(tmp_path, [
        ModelTurn("", (CALL,), served_model="model-g"),
        ModelTurn("17", (), served_model="wrong-model"),
    ])
    assert result["admission_exit"] == 1
    assert result["answer"] == ""
    assert len(calls) == 1
    assert len([e for e in result["events"] if e["kind"] == "model_turn"]) == 2


def test_invented_tool_rejects_whole_batch(tmp_path):
    result, calls, _ = run(tmp_path, [ModelTurn("", (
        CALL, ModelToolCall("bad", "write_production", {}),
    ), served_model="model-g")])
    assert result["failure"] == "tool_not_allowed"
    assert not calls


def test_tool_budget_rejects_whole_batch(tmp_path):
    result, calls, _ = run(tmp_path, [ModelTurn("", (CALL, CALL), served_model="model-g")], max_tool_calls=1)
    assert result["failure"] == "tool_budget_exhausted"
    assert not calls


def test_last_model_turn_cannot_start_more_tools(tmp_path):
    result, calls, _ = run(tmp_path, [ModelTurn("", (CALL,), served_model="model-g")], max_turns=1)
    assert result["failure"] == "model_turn_budget_exhausted"
    assert not calls


def test_tool_exception_retains_identity_and_request(tmp_path):
    def broken(*_):
        raise RuntimeError("do not copy arbitrary private exception text")

    result, _, _ = run(tmp_path, [ModelTurn("", (CALL,), served_model="model-g")], execute_tool=broken)
    assert result["failure"] == "tool_execution_failed"
    assert result["admission_exit"] == 0  # identity is not answer success
    assert result["status"] == "failed"
    assert result["events"][-1]["kind"] == "tool_error"
    assert "private exception text" not in json.dumps(result)


def test_adapter_exception_is_not_completed_or_admitted(tmp_path):
    result, calls, _ = run(tmp_path, [RuntimeError("private")])
    assert result["failure"] == "model_exception:RuntimeError"
    assert result["admission_exit"] == 2
    assert not calls


def test_incomplete_response_cannot_become_an_answer(tmp_path):
    result, calls, _ = run(tmp_path, [ModelTurn("17", (), served_model="model-g", finish_reason="length")])
    assert result["failure"] == "model_reported_error"
    assert result["answer"] == ""
    assert not calls


def test_late_response_cannot_dispatch_tool(tmp_path):
    ticks = iter([0, 0, 0, 100, 100])
    result, calls, _ = run(tmp_path, [ModelTurn("", (CALL,), served_model="model-g")], clock=lambda: next(ticks))
    assert result["failure"] == "deadline_exhausted_local"
    assert not calls


def test_existing_artifact_is_not_reused(tmp_path):
    artifact = tmp_path / "episode.json"
    artifact.write_text("original")
    with pytest.raises(FileExistsError):
        run(tmp_path, [])
    assert artifact.read_text() == "original"


@pytest.mark.parametrize("kwargs", [{"max_turns": 0}, {"max_tool_calls": True}, {"timeout": float("nan")}])
def test_invalid_limits_do_not_create_artifact(tmp_path, kwargs):
    with pytest.raises(ValueError):
        run(tmp_path, [], **kwargs)
    assert not (tmp_path / "episode.json").exists()


@pytest.mark.parametrize("served", [None, ""])
def test_later_missing_identity_cannot_hide_behind_first_good_turn(tmp_path, served):
    result, calls, _ = run(tmp_path, [
        ModelTurn("", (CALL,), served_model="model-g"),
        ModelTurn("17", (), served_model=served),
    ])
    assert result["admission_exit"] == 2
    assert result["status"] == "failed"
    assert result["answer"] == ""
    assert len(calls) == 1


class MenuFollowingModel:
    """Synthetic model: query while a menu is offered, otherwise use evidence."""

    def __init__(self):
        self.inputs = []

    def complete(self, **kwargs):
        self.inputs.append(deepcopy(kwargs))
        if kwargs["tools"]:
            return ModelTurn("", (CALL,), served_model="model-g")
        evidence = [json.loads(m["content"]) for m in kwargs["messages"] if m["role"] == "tool"]
        answer = str(evidence[-1]["value"]) if evidence else "No evidence available."
        return ModelTurn(answer, (), served_model="model-g")


@pytest.mark.parametrize("limits", [
    {"max_tool_calls": 1, "max_turns": 4},
    {"max_tool_calls": 4, "max_turns": 2},
])
def test_menu_closes_for_budgeted_final_answer_without_extra_turns(tmp_path, limits):
    model = MenuFollowingModel()
    dispatched = []

    def execute(*args):
        dispatched.append(args)
        return {"value": 17, "source": "synthetic"}

    result = run_thin_react(
        model, question="Read the fixture number.", expected_model="model-g",
        tools=TOOLS, execute_tool=execute, artifact=tmp_path / "episode.json", **limits,
    )
    assert result["status"] == "completed", result["failure"]
    assert result["answer"] == "17"
    assert result["admission_exit"] == 0
    assert len(dispatched) == result["tool_calls"] == 1
    assert len(model.inputs) == 2
    assert model.inputs[0]["tools"] == TOOLS
    assert model.inputs[1]["tools"] == []
    assert json.loads((tmp_path / "episode.json").read_text()) == result


def test_single_turn_uses_existing_budget_to_report_evidence_gap(tmp_path):
    model = MenuFollowingModel()

    def forbidden_dispatch(*args):
        pytest.fail("last model turn cannot dispatch a tool")

    result = run_thin_react(
        model, question="Read the fixture number.", expected_model="model-g",
        tools=TOOLS, execute_tool=forbidden_dispatch,
        artifact=tmp_path / "episode.json", max_turns=1,
    )
    assert result["status"] == "completed"
    assert result["answer"] == "No evidence available."
    assert len(model.inputs) == 1
    assert model.inputs[0]["tools"] == []


def test_resource_message_and_receipt_follow_actual_remaining_budget(tmp_path):
    now = [0.0]

    def execute(*args):
        now[0] += 7.0
        return {"value": 17}

    result, _, model = run(tmp_path, [
        ModelTurn("", (CALL,), served_model="model-g"),
        ModelTurn("", (CALL,), served_model="model-g"),
        ModelTurn("17", (), served_model="model-g"),
    ], max_turns=3, max_tool_calls=2, clock=lambda: now[0], execute_tool=execute)
    turns = [e for e in result["events"] if e["kind"] == "model_turn"]
    for index, (request, event) in enumerate(zip(model.inputs, turns, strict=True)):
        budget = event["request_budget"]
        assert budget["model_turns_remaining"] == 3 - index
        assert budget["tool_calls_remaining"] == 2 - index
        assert budget["wall_seconds_remaining"] == 90 - 7 * index
        assert request["messages"][-1]["role"] == "user"
        assert json.dumps(budget, ensure_ascii=False) in request["messages"][-1]["content"]
        assert request["tools"] == (TOOLS if index < 2 else [])
        # Resource messages describe only this request; stale budgets do not
        # accumulate in the conversation seen by a later model turn.
        assert sum("本轮资源" in (m.get("content") or "") for m in request["messages"]) == 1
    assert result["status"] == "completed"
    assert result["limits"]["max_turns"] == 3
    assert result["limits"]["max_tool_calls"] == result["tool_calls"] == 2


def test_closed_menu_does_not_let_model_exceed_tool_budget(tmp_path):
    result, calls, model = run(tmp_path, [
        ModelTurn("", (CALL,), served_model="model-g"),
        ModelTurn("", (CALL,), served_model="model-g"),
    ], max_tool_calls=1)
    assert model.inputs[1]["tools"] == []
    assert len(model.inputs) == 2
    assert len(calls) == 1
    assert result["status"] == "failed"
    assert result["failure"] == "tool_budget_exhausted"
    assert result["answer"] == ""


def test_deadline_expiring_during_request_preparation_starts_no_model(tmp_path):
    ticks = iter([0.0, 0.0, 100.0, 100.0])
    result, calls, model = run(tmp_path, [], clock=lambda: next(ticks))
    assert result["failure"] == "deadline_exhausted_local"
    assert result["answer"] == ""
    assert not calls
    assert not model.inputs
