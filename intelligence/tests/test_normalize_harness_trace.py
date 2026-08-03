from __future__ import annotations

import json

from intelligence.eval.normalize_harness_trace import (
    STEPS,
    compare_sequences,
    main,
    normalize_records,
)


def test_workbench_configure_and_plan_are_not_swallowed_by_generic_branches() -> None:
    events = normalize_records(
        [
            {"step_id": "configure", "name": "turn_assembly", "status": "completed"},
            {"step_id": "plan", "name": "research_plan", "status": "completed"},
        ],
        kind="workbench-trace",
    )

    # `turn_assembly` has no keyword in the legacy branches and fell through to
    # `unmapped`; `research_plan` contains "research" and was captured by
    # `retrieve`.  Both must resolve to their own L1 step.
    assert [event.step for event in events] == ["configure", "plan"]
    assert {event.native_or_normalized for event in events} == {"native"}


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
        "tool",
        "observe",
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


def test_compare_sequences_survives_prefix_on_either_side() -> None:
    short = normalize_records(
        [{"step_id": "controller"}, {"step_id": "route"}, {"step_id": "retrieve"}],
        kind="workbench-trace",
    )
    long = normalize_records(
        [
            {"step_id": "controller"},
            {"step_id": "route"},
            {"step_id": "retrieve"},
            {"step_id": "synthesize"},
        ],
        kind="workbench-trace",
    )

    # The shorter side used to be indexed past its end and raise IndexError.
    for left, right, side in ((short, long, "right"), (long, short, "left")):
        result = compare_sequences(left, right)
        assert result.pre_divergence_equivalence == "equivalent_before_divergence"
        assert result.first_divergence_step == "synthesize"
        assert f"continues_on={side}" in result.evidence


def test_tool_results_map_to_observe_across_both_harness_mappers() -> None:
    rollout = normalize_records(
        [
            {"type": "item.completed", "item": {"type": "function_call"}},
            {"type": "item.completed", "item": {"type": "function_call_output"}},
            {"type": "item.completed", "item": {"type": "mcp_tool_call_output"}},
            {"type": "item.completed", "item": {"type": "output_text"}},
        ],
        kind="codex-rollout",
    )
    benchmark = normalize_records(
        [{"kind": "tool_request"}, {"kind": "tool_result"}],
        kind="runtime-benchmark",
    )

    # A tool result must not collapse into `retrieve` just because its item type
    # also contains `function_call`; otherwise every paired comparison against a
    # workbench trace diverges at the first tool result for vocabulary reasons.
    assert [event.step for event in rollout] == [
        "tool",
        "observe",
        "observe",
        "synthesize",
    ]
    assert [event.step for event in benchmark] == ["tool", "observe"]


def test_terminal_state_survives_payload_nesting() -> None:
    events = normalize_records(
        [
            {
                "sequence": 9,
                "kind": "finish",
                "payload": {"status": "partial", "stop_reason": "headless_timeout"},
            },
            {"kind": "finish", "status": "completed", "stop_reason": "model_finish"},
        ],
        kind="runtime-benchmark",
    )

    assert "status=partial" in events[0].summary
    assert "stop_reason=headless_timeout" in events[0].summary
    assert "status=completed" in events[1].summary
    assert "stop_reason=model_finish" in events[1].summary


def test_every_persisted_benchmark_kind_has_a_normalized_step() -> None:
    from intelligence.eval.normalize_harness_trace import _BENCHMARK_STEPS
    from intelligence.eval.runtime_backend_benchmark import _DIAGNOSTIC_EVENT_KINDS

    # A kind the benchmark is allowed to persist but the normalizer cannot map
    # drops silently out of every comparison.  This is the projection contract:
    # whatever survives serialization must survive normalization.
    missing = sorted(_DIAGNOSTIC_EVENT_KINDS - set(_BENCHMARK_STEPS))
    assert missing == [], f"unmapped persisted kinds: {missing}"

    unknown_steps = {
        step for step, _role in _BENCHMARK_STEPS.values() if step not in STEPS
    }
    assert unknown_steps == set()


def test_step_vocabulary_matches_the_triage_skill_l1_pipeline() -> None:
    from intelligence.eval.normalize_harness_trace import VOCABULARY

    # `agent-run-triage` references/taxonomy.md fixes L1 to these nine steps.
    # Keeping them identical is what lets a triage report's `first_bad_step` and
    # this module's `first_divergence_step` be compared at all.
    assert STEPS == (
        "configure",
        "intent",
        "plan",
        "route",
        "retrieve",
        "tool",
        "observe",
        "synthesize",
        "stop",
    )
    assert VOCABULARY == "triage-l1-9"


def test_tool_invocation_and_planning_are_not_collapsed() -> None:
    events = normalize_records(
        [
            {"kind": "mode_decision"},
            {"kind": "branch_started"},
            {"kind": "tool_request"},
            {"kind": "tool_result"},
        ],
        kind="runtime-benchmark",
    )
    rollout = normalize_records(
        [{"type": "item.completed", "item": {"type": "function_call"}}],
        kind="codex-rollout",
    )

    # `plan` (how deep to research) and `tool` (invoking one) are distinct L1
    # boundaries; v1 folded them into `route`/`retrieve` and made an L1=`tool`
    # finding inexpressible.
    assert [event.step for event in events] == ["plan", "retrieve", "tool", "observe"]
    assert rollout[0].step == "tool"


def test_control_plane_kinds_map_to_their_runtime_semantics() -> None:
    events = normalize_records(
        [
            {"kind": "task", "payload": {"task_frame_hash": "abc"}},
            {"kind": "mode_decision"},
            {"kind": "tool_request"},
            {"kind": "tool_error", "payload": {"error": "research_stage_closed"}},
            {"kind": "invalid_action", "payload": {"reason": "bad plan"}},
            {"kind": "repair_goal"},
            {"kind": "finalization"},
            {"kind": "finish", "payload": {"status": "partial"}},
        ],
        kind="runtime-benchmark",
    )

    assert [event.step for event in events] == [
        "intent",
        "plan",
        "tool",
        "observe",
        "observe",
        "plan",
        "synthesize",
        "stop",
    ]
    assert all(event.step != "unmapped" for event in events)


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
