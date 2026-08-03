from __future__ import annotations

import json

from intelligence.eval.normalize_harness_trace import (
    compare_sequences,
    main,
    normalize_records,
)


def test_workbench_events_keep_native_steps_and_map_control_plane() -> None:
    events = normalize_records(
        [
            {"step_id": "controller", "name": "turn_controller", "status": "completed"},
            {"step_id": "route", "name": "route_skills", "status": "completed"},
            {"step_id": "retrieve", "name": "ask_retrieve_compose", "status": "completed"},
            {"step_id": "synthesize", "name": "answer_synthesis", "status": "completed"},
            {"step_id": "budget", "name": "research_execution_budget", "status": "completed"},
        ],
        kind="workbench-trace",
    )

    assert [event.step for event in events] == [
        "intent",
        "route",
        "retrieve",
        "synthesize",
        "observe",
    ]
    assert {event.native_or_normalized for event in events} == {"native"}
    assert all("/Users/" not in event.summary for event in events)


def test_codex_and_benchmark_events_are_normalized_without_guessing_unknowns() -> None:
    events = normalize_records(
        [
            {"type": "thread.started", "thread_id": "thread-1"},
            {"type": "turn.started"},
            {"kind": "tool_request", "tool": "market_data", "query": "secret"},
            {"kind": "tool_result", "tool": "market_data", "status": "ok"},
            {"type": "turn.completed", "status": "completed"},
            {"type": "future.vendor.event", "payload": {"api_key": "sk-test"}},
        ],
        kind="codex-rollout",
    )

    assert [event.step for event in events] == [
        "configure",
        "intent",
        "retrieve",
        "retrieve",
        "stop",
        "unmapped",
    ]
    assert events[0].native_or_normalized == "normalized"
    assert events[-1].native_or_normalized == "unmapped"
    serialized = json.dumps([event.__dict__ for event in events], ensure_ascii=False)
    assert "sk-test" not in serialized
    assert "api_key" not in serialized
    assert "/Users/" not in serialized


def test_compare_sequences_reports_first_divergence_and_missing_side() -> None:
    left = normalize_records(
        [{"step_id": "controller", "name": "turn_controller"}, {"step_id": "route", "name": "route_skills"}],
        kind="workbench-trace",
    )
    right = normalize_records(
        [{"type": "thread.started"}, {"type": "turn.started"}],
        kind="codex-rollout",
    )

    result = compare_sequences(left, right)
    assert result.pre_divergence_equivalence == "not_established"
    assert result.first_divergence_step == "intent"
    assert result.evidence == ("left=intent", "right=configure", "ordinal=0")

    empty = compare_sequences(left, [])
    assert empty.pre_divergence_equivalence == "not_established"
    assert empty.first_divergence_step is None


def test_cli_writes_hashed_normalized_artifact(tmp_path) -> None:
    source = tmp_path / "sk-secret.jsonl"
    source.write_text(
        '{"step_id":"route","name":"route_skills","status":"completed"}\n',
        encoding="utf-8",
    )
    target = tmp_path / "normalized.json"

    assert main([str(source), "--kind", "workbench-trace", "--output", str(target)]) == 0
    artifact = json.loads(target.read_text(encoding="utf-8"))
    assert artifact["source_kind"] == "workbench-trace"
    assert artifact["source_file"] == "source-redacted"
    assert len(artifact["input_sha256"]) == 64
    assert artifact["events"][0]["step"] == "route"
