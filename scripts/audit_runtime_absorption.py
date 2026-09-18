"""Observe three runtime absorption boundaries with fake models and tools.

This is a read-only audit probe, not a regression gate: it prints observations
rather than treating today's problematic behavior as the desired contract.
It uses existing test fixtures; no paid model, network, production data, or
production episode store is used. All stores are in memory.

Audited baseline: finance bf662e9310ff (2026-09-18). The probe intentionally
covers store-failure completion, recall after compaction, and length-truncated
tool calls. A changed implementation may legitimately change the output.

Run from the repository root with the workbench interpreter:
    PYTHONPATH=. .venv-workbench/bin/python scripts/audit_runtime_absorption.py
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.glm_agent_runtime import _turn_from_message
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.tests.conformance.races.test_race_store_failure_vs_memory_ledger import (
    _run,
)
from intelligence.tests.test_agent_episode import (
    ScriptedModel,
    _context,
    _frame,
    _market_registry,
)
from intelligence.tests.test_episode_history_compaction_loop import (
    _finish_binding,
    _runner,
    _tool_turn,
)


def store_probe() -> dict[str, object]:
    rig, store, outcome = _run("audit-store-probe", fail_on="model_turn")
    restored = ContinuousAgentEpisode.restore(rig.task_id, store)
    finish = next(event for event in outcome.events if event.kind == "finish")
    state = rig.stored_state()
    return {
        "outcome_status": outcome.status,
        "durable_phase": state.phase if state is not None else None,
        "restore_action": restored.plan.action if restored.plan is not None else None,
        "store_failures": list(finish.payload["store_failures"]),
    }


def compaction_probe() -> dict[str, object]:
    executed: list[str] = []

    def runner(query, context):
        executed.append(query)
        return _runner(query, context)

    model = ScriptedModel([
        _tool_turn(1),
        _tool_turn(2),
        _tool_turn(3),
        ModelTurn(
            "",
            (ModelToolCall("recall-1", "market_data", {"query": "查询1"}),),
            "scripted",
            "",
        ),
        _finish_binding("E1"),
    ])
    frame = _frame()
    with patch.dict(os.environ, {
        "ASK_EPISODE_HISTORY_COMPACTION": "on",
        "ASK_EPISODE_HISTORY_KEEP_BATCHES": "2",
    }):
        outcome = ContinuousAgentEpisode(model).run(
            task_frame=frame,
            context=_context(frame, max_steps=8),
            registry=_market_registry(runner),
        )
    fourth_input = [
        json.loads(message["content"])
        for message in model.calls[3]["messages"]
        if message["role"] == "tool"
    ]
    recall_errors = [
        event.payload["error"]
        for event in outcome.events
        if event.kind == "tool_error" and event.payload.get("call_id") == "recall-1"
    ]
    return {
        "folded_before_recall": fourth_input[0].get("compacted", False),
        "note": fourth_input[0].get("note"),
        "executed_queries": executed,
        "recall_errors": recall_errors,
        "outcome_status": outcome.status,
    }


def truncation_probe() -> dict[str, object]:
    message = {
        "content": "",
        "tool_calls": [{
            "id": "truncated-call",
            "type": "function",
            "function": {"name": "market_data", "arguments": '{"query":"查询1"}'},
        }],
        "_finish_reason": "length",
    }
    turn, error = _turn_from_message(message, "scripted-provider", 1)
    executed: list[str] = []

    def runner(query, context):
        executed.append(query)
        return _runner(query, context)

    model = ScriptedModel([turn, _finish_binding("E1")])
    frame = _frame()
    with patch.dict(os.environ, {"ASK_EPISODE_HISTORY_COMPACTION": "off"}):
        outcome = ContinuousAgentEpisode(model).run(
            task_frame=frame,
            context=_context(frame, max_steps=8),
            registry=_market_registry(runner),
        )
    return {
        "provider_finish_reason": message["_finish_reason"],
        "adapter_error": error,
        "model_turn_error": turn.error,
        "tool_calls_released": len(turn.tool_calls),
        "executed_queries": executed,
        "outcome_status": outcome.status,
    }


def main() -> None:
    observations = {
        "store": store_probe(),
        "compaction": compaction_probe(),
        "truncation": truncation_probe(),
    }
    print(json.dumps(observations, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
