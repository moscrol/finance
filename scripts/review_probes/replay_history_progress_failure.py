"""Replay archived history-query rejection through the real progress accumulator.

Prevents blaming model credentials or the last dispatched tool for a local
mappingproxy JSON failure. Reads the original task/call/evidence, runs the real
registry parser and rejected-result consumer, and records the exception stack
or feedback. No model, database, provider, or finish admission is executed.

Use --code-root to compare a frozen candidate and an already committed repair;
--expect crash/feedback makes the claimed seam result executable. Output is
exclusive and cannot overwrite the event source. This is not a live rerun or
proof of end-to-end answer preservation.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
from datetime import date
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import traceback


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--expect", choices=("crash", "feedback"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    code = args.code_root.resolve()
    source = args.events.resolve()
    output = args.output.resolve()
    if output == source or output.exists():
        parser.error("output must be a new file, not the archived source")
    sys.path.insert(0, str(code))
    attempts: list[str] = []

    def denied(*_args, **_kwargs):
        attempts.append("connect")
        raise AssertionError("offline replay must not connect")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied

    from intelligence.runtime.agent_episode import _EpisodeLedger, _EpisodeToolAccumulator
    from intelligence.runtime.episode_tool_batch import ToolBatchResult, ToolCallResult
    from intelligence.services.agent_research import AgentEvidence
    from intelligence.services.agent_runtime import ModelToolCall
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.services.historical_research.episode import history_tool_specs
    from intelligence.services.research_contract import (
        InformationCutoff,
        RequiredOutput,
        ResearchDeadline,
        ResearchPolicy,
        ResearchRunContext,
        ResearchTaskContract,
    )
    from intelligence.services.research_tool_registry import (
        InvalidResearchToolArguments,
        ResearchToolRegistry,
    )
    from intelligence.services.task_frame import TaskFrame

    original = source.read_bytes()
    events = [json.loads(row) for row in original.decode().splitlines() if row.strip()]
    task = next(event["payload"] for event in events if event["kind"] == "task")
    frame = TaskFrame.from_dict(task["task_frame"])
    assert frame is not None and frame.history_intent is not None
    request_index, request = next(
        (index, event["payload"])
        for index, event in reversed(list(enumerate(events)))
        if event["kind"] == "tool_request" and event["payload"]["name"] == "history_query"
    )
    call = ModelToolCall(request["call_id"], request["name"], request["arguments"])
    assert "end" not in call.arguments and call.arguments["operation"] == "find_analogues"
    assert any(
        item["call_id"] == call.call_id
        for event in events if event["kind"] == "model_turn"
        for item in event["payload"].get("tool_calls", ())
    ), "the archived model must have requested this call"
    before_call = call.to_dict()
    cutoff = date.fromisoformat(str(request["at"])[:10])
    context = ResearchRunContext(
        contract=ResearchTaskContract(
            task_id="offline-history-progress", question=frame.raw_question,
            subject=frame.subject, subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=tuple(
                RequiredOutput(name, name, ("finance_query",), True)
                for name in frame.required_outputs
            ),
            allowed_capabilities=("finance_query",), task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy("standard", 6, 60, 0),
        trace_parent_id="offline-history-progress",
        information_cutoff=InformationCutoff(cutoff, "runtime_default"),
        history_intent=frame.history_intent,
    )
    # No runner is invoked: the real parser rejects the missing end first.
    registry = ResearchToolRegistry(history_tool_specs(
        frame, context, code / "offline-database-must-not-be-opened.duckdb", None,
    ))
    try:
        registry.prepare(call.name, call.arguments)
    except InvalidResearchToolArguments as exc:
        rejection = {"code": exc.code, "detail": str(exc)}
    else:
        raise AssertionError("the missing end must remain invalid")
    assert rejection["detail"] == "end requires ISO date"

    evidence_fields = {field.name for field in fields(AgentEvidence)}
    prior: dict[str, AgentEvidence] = {}
    for event in events[:request_index]:
        if event["kind"] != "tool_result":
            continue
        for raw in event["payload"].get("evidence", ()):
            values = {key: value for key, value in raw.items() if key in evidence_fields}
            for name in ("supports", "contradicts", "observations", "derived_from"):
                if name in values:
                    values[name] = tuple(values[name])
            item = AgentEvidence(**values)
            prior.setdefault(item.content_hash, item)
    assert prior, "replay requires the earlier successful evidence"
    evidence_ledger = EvidenceLedger(information_cutoff=cutoff)
    evidence_ledger.append(tuple(prior.values()))
    evidence_snapshot = evidence_ledger.snapshot()
    ledger = _EpisodeLedger(frame)
    accumulator = _EpisodeToolAccumulator(
        messages=[], ledger=ledger, evidence_ledger=evidence_ledger,
        evidence=list(prior.values()), evidence_hashes=set(prior),
    )
    batch = ToolBatchResult(
        (ToolCallResult(call, "rejected", error=rejection["code"], detail=rejection["detail"]),),
        executed_count=0, normalized_queries=(),
    )
    failure = None
    feedback = None
    try:
        invalid = accumulator.consume(batch, context)
    except TypeError as exc:
        failure = {"type": type(exc).__name__, "message": str(exc), "stack": traceback.format_exc()}
    else:
        assert invalid == 1
        errors = [event for event in ledger.events if event.kind == "tool_error"]
        assert len(errors) == 1
        assert len(accumulator.messages) == 1
        feedback = json.loads(accumulator.messages[0].content)
        assert feedback["ok"] is False
        assert feedback["error"] == rejection["code"]
        assert feedback["detail"] == rejection["detail"]
        assert accumulator.messages[0].tool_call_id == call.call_id

    assert tuple(accumulator.evidence) == tuple(prior.values())
    assert evidence_ledger.snapshot() == evidence_snapshot
    assert call.to_dict() == before_call
    assert not attempts and source.read_bytes() == original
    actual = "crash" if failure else "feedback"
    if failure:
        assert failure["message"] == "Object of type mappingproxy is not JSON serializable"
        assert "normalize_query" in failure["stack"]
    revision = subprocess.check_output(["git", "-C", str(code), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(code), "status", "--porcelain"], text=True).splitlines()
    report = {
        "scope": "original-input parser -> rejected result -> progress accumulator only",
        "code_revision": revision, "code_dirty_paths": dirty,
        "source": str(source), "source_sha256": hashlib.sha256(original).hexdigest(),
        "task_frame_hash": frame.task_frame_hash, "call_id": call.call_id,
        "rejection": rejection, "result": actual, "expected": args.expect,
        "failure": failure, "feedback": feedback,
        "prior_unique_evidence_count": len(prior), "prior_evidence_unchanged": True,
        "call_arguments_unchanged": True, "source_unchanged": True,
        "network_connect_attempts": len(attempts), "model_calls": 0,
        "database_queries": 0, "live_resubmissions": 0,
        "live_acceptance_changed": False, "finish_preservation_exercised": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    assert actual == args.expect, f"expected {args.expect}, got {actual}"


if __name__ == "__main__":
    main()
