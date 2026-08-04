from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval.normalize_harness_trace import (
    STEPS,
    NormalizedArtifactError,
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
    assert result.evidence == ("left=intent", "right=configure", "ordinal=0")

    # A mismatch has a step on each side, so the scalar is null by contract and
    # the structured object carries both.
    assert result.first_divergence_step is None
    assert result.first_divergence is not None
    assert result.first_divergence.relation == "step_mismatch"
    assert result.first_divergence.ordinal == 0
    assert result.first_divergence.left_step == "intent"
    assert result.first_divergence.right_step == "configure"

    empty = compare_sequences(left, [])
    assert empty.pre_divergence_equivalence == "not_established"
    assert empty.first_divergence_step is None
    assert empty.first_divergence is None


def test_step_mismatch_is_symmetric_under_input_order() -> None:
    workbench = normalize_records(
        [{"step_id": "controller"}, {"step_id": "route"}],
        kind="workbench-trace",
    )
    benchmark = normalize_records(
        [{"kind": "task"}, {"kind": "tool_request"}],
        kind="runtime-benchmark",
    )

    forward = compare_sequences(workbench, benchmark)
    backward = compare_sequences(benchmark, workbench)

    # Returning only the left step made the verdict depend on argument order:
    # `route` one way, `tool` the other.  Ordinal and relation must be invariant;
    # only the two named sides swap.
    for result in (forward, backward):
        assert result.first_divergence_step is None
        assert result.first_divergence is not None
        assert result.first_divergence.relation == "step_mismatch"
        assert result.first_divergence.ordinal == 1

    assert forward.first_divergence.left_step == "route"
    assert forward.first_divergence.right_step == "tool"
    assert backward.first_divergence.left_step == "tool"
    assert backward.first_divergence.right_step == "route"


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
        # The extra step exists on one side only, so here the scalar is
        # unambiguous and is kept; the missing side is explicitly null.
        assert result.first_divergence_step == "synthesize"
        assert f"continues_on={side}" in result.evidence
        assert result.first_divergence is not None
        assert result.first_divergence.relation == f"{side}_continues"
        assert result.first_divergence.ordinal == 3
        if side == "left":
            assert result.first_divergence.left_step == "synthesize"
            assert result.first_divergence.right_step is None
        else:
            assert result.first_divergence.left_step is None
            assert result.first_divergence.right_step == "synthesize"


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


def test_runtime_benchmark_reads_safe_timestamp_from_event_payload() -> None:
    events = normalize_records(
        [
            {
                "sequence": 9,
                "kind": "finalization",
                "payload": {
                    "reason": "research_stage_closed",
                    "timestamp": "2026-08-04T12:00:00.000Z",
                },
            }
        ],
        kind="runtime-benchmark",
    )

    assert events[0].timestamp == "2026-08-04T12:00:00.000Z"


def test_raw_benchmark_schema_version_is_not_mistaken_for_normalized_artifact(
    tmp_path,
) -> None:
    source = tmp_path / "runtime-benchmark.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "case-1",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {
                                            "sequence": 1,
                                            "kind": "finish",
                                            "payload": {
                                                "status": "completed",
                                                "stop_reason": "model_finish",
                                            },
                                        }
                                    ]
                                }
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    target = tmp_path / "normalized.json"

    assert main(
        [str(source), "--kind", "runtime-benchmark", "--output", str(target)]
    ) == 0
    artifact = json.loads(target.read_text(encoding="utf-8"))
    assert artifact["source_kind"] == "runtime-benchmark"
    assert artifact["unmapped_count"] == 0
    assert artifact["events"][0]["step"] == "stop"


def test_runtime_benchmark_artifact_counts_unpaired_tool_requests(tmp_path) -> None:
    source = tmp_path / "runtime-benchmark.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "missing-response",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {"sequence": 1, "kind": "tool_request"}
                                    ]
                                }
                            }
                        ],
                    },
                    {
                        "id": "completed-response",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {"sequence": 1, "kind": "tool_request"},
                                        {"sequence": 2, "kind": "tool_result"},
                                    ]
                                }
                            }
                        ],
                    },
                    {
                        "id": "rejected-response",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {"sequence": 1, "kind": "tool_request"},
                                        {"sequence": 2, "kind": "tool_error"},
                                    ]
                                }
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    target = tmp_path / "normalized.json"

    assert main(
        [str(source), "--kind", "runtime-benchmark", "--output", str(target)]
    ) == 0
    artifact = json.loads(target.read_text(encoding="utf-8"))
    assert artifact["unpaired_tool_requests"] == 1


def test_pairing_metric_is_kind_aware(tmp_path) -> None:
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {"type": "function_call", "id": "c1"},
                {"type": "function_call_output", "id": "c1o"},
                {"type": "function_call", "id": "c2"},
                {"type": "turn.failed"},
            )
        ),
        encoding="utf-8",
    )
    codex_target = tmp_path / "codex-normalized.json"
    assert main(
        [
            str(rollout),
            "--kind",
            "codex-rollout",
            "--output",
            str(codex_target),
        ]
    ) == 0

    workbench = tmp_path / "workbench.jsonl"
    workbench.write_text(
        '{"step_id":"route","name":"route_skills"}\n',
        encoding="utf-8",
    )
    workbench_target = tmp_path / "workbench-normalized.json"
    assert main(
        [
            str(workbench),
            "--kind",
            "workbench-trace",
            "--output",
            str(workbench_target),
        ]
    ) == 0

    codex_artifact = json.loads(codex_target.read_text(encoding="utf-8"))
    workbench_artifact = json.loads(
        workbench_target.read_text(encoding="utf-8")
    )
    assert codex_artifact["unpaired_tool_requests"] == 1
    assert workbench_artifact["unpaired_tool_requests"] is None


def test_runtime_benchmark_pairs_only_matching_request_ids(tmp_path) -> None:
    matched_id = "a" * 32
    pending_id = "b" * 32
    unrelated_id = "c" * 32
    source = tmp_path / "benchmark.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "matched",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {
                                            "kind": "tool_request",
                                            "payload": {"request_id": matched_id},
                                        },
                                        {
                                            "kind": "tool_result",
                                            "payload": {"request_id": matched_id},
                                        },
                                    ]
                                }
                            }
                        ],
                    },
                    {
                        "id": "mismatched",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {
                                            "kind": "tool_request",
                                            "payload": {"request_id": pending_id},
                                        },
                                        {
                                            "kind": "tool_result",
                                            "payload": {"request_id": unrelated_id},
                                        },
                                    ]
                                }
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    target = tmp_path / "normalized.json"

    assert main(
        [str(source), "--kind", "runtime-benchmark", "--output", str(target)]
    ) == 0
    artifact = json.loads(target.read_text(encoding="utf-8"))
    assert artifact["unpaired_tool_requests"] == 1
    assert [event["correlation_id"] for event in artifact["events"]] == [
        matched_id,
        matched_id,
        pending_id,
        unrelated_id,
    ]


def test_codex_nested_call_ids_survive_normalization(tmp_path) -> None:
    source = tmp_path / "rollout.jsonl"
    source.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {
                    "type": "item.completed",
                    "item": {"type": "function_call", "call_id": "call-1"},
                },
                {
                    "type": "item.completed",
                    "item": {
                        "type": "function_call_output",
                        "call_id": "call-1",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {"type": "function_call", "call_id": "call-2"},
                },
            )
        ),
        encoding="utf-8",
    )
    target = tmp_path / "normalized.json"

    assert main(
        [str(source), "--kind", "codex-rollout", "--output", str(target)]
    ) == 0
    artifact = json.loads(target.read_text(encoding="utf-8"))
    assert artifact["unpaired_tool_requests"] == 1
    assert [event["correlation_id"] for event in artifact["events"]] == [
        "call-1",
        "call-1",
        "call-2",
    ]


def test_reused_v2_artifact_accepts_missing_optional_correlation_id(
    tmp_path,
) -> None:
    source = tmp_path / "benchmark.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "case-1",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {
                                            "kind": "tool_request",
                                            "payload": {"request_id": "d" * 32},
                                        }
                                    ]
                                }
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    artifact_path = tmp_path / "normalized.json"
    assert main(
        [
            str(source),
            "--kind",
            "runtime-benchmark",
            "--output",
            str(artifact_path),
        ]
    ) == 0
    legacy = json.loads(artifact_path.read_text(encoding="utf-8"))
    for event in legacy["events"]:
        event.pop("correlation_id", None)
    legacy_path = tmp_path / "legacy-v2.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    compared = tmp_path / "compared.json"

    assert main(
        [
            str(legacy_path),
            "--compare",
            str(legacy_path),
            "--output",
            str(compared),
        ]
    ) == 0
    reused = json.loads(compared.read_text(encoding="utf-8"))["left"]
    assert reused["unpaired_tool_requests"] == 1
    assert reused["events"][0]["correlation_id"] is None


def test_reused_artifact_recomputes_or_validates_tool_pairing_count(tmp_path) -> None:
    source = tmp_path / "benchmark.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "case-1",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {"sequence": 1, "kind": "tool_request"}
                                    ]
                                }
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    artifact_path = tmp_path / "normalized.json"
    assert main(
        [
            str(source),
            "--kind",
            "runtime-benchmark",
            "--output",
            str(artifact_path),
        ]
    ) == 0
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    legacy = dict(artifact)
    legacy.pop("unpaired_tool_requests")
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    compared = tmp_path / "compared.json"
    assert main(
        [
            str(legacy_path),
            "--compare",
            str(legacy_path),
            "--output",
            str(compared),
        ]
    ) == 0
    output = json.loads(compared.read_text(encoding="utf-8"))
    assert output["left"]["unpaired_tool_requests"] == 1

    tampered = dict(artifact, unpaired_tool_requests=0)
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(NormalizedArtifactError) as raised:
        main([str(tampered_path), "--compare", str(artifact_path)])
    message = str(raised.value)
    assert "unpaired_tool_requests=0" in message
    assert "recomputed 1" in message


def test_frozen_finalization_artifacts_expose_the_pairing_gap(tmp_path) -> None:
    measurements = (
        Path(__file__).resolve().parents[1]
        / "eval"
        / "measurements"
        / "2026-08-04b-finalization"
    )
    counts: list[int] = []
    for filename in ("c-long-capped-t1.json", "c-long-capped-t2.json"):
        output_path = tmp_path / f"{filename}.normalized.json"
        assert main(
            [
                str(measurements / filename),
                "--kind",
                "runtime-benchmark",
                "--output",
                str(output_path),
            ]
        ) == 0
        artifact = json.loads(output_path.read_text(encoding="utf-8"))
        counts.append(artifact["unpaired_tool_requests"])

    assert counts == [0, 1]


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


def test_root_budget_overdraft_is_mapped_not_left_unmapped() -> None:
    """A new event kind must reach the normalizer, or R-20260804-06 silently regresses.

    `root_budget_overdraft` is emitted when a finished tool call is settled for
    less than it actually spent. Unknown kinds fall back to
    ("unmapped", "unmapped", "unknown"), which would break the already-confirmed
    prediction that normalization leaves `unmapped_count == 0`.
    """

    events = normalize_records(
        [
            {"kind": "tool_request"},
            {"kind": "tool_result"},
            {
                "kind": "root_budget_overdraft",
                "payload": {
                    "requested_seconds": 0.9,
                    "settled_seconds": 0.1,
                    "overdraft_seconds": 0.8,
                },
            },
            {"kind": "finalization"},
        ],
        kind="runtime-benchmark",
    )

    assert [event.step for event in events] == [
        "tool",
        "observe",
        "observe",
        "synthesize",
    ]
    overdraft = events[2]
    assert overdraft.step == "observe"
    assert overdraft.event_role == "control"
    assert overdraft.native_or_normalized == "normalized"
    # The point of the test: zero unmapped events.
    assert sum(1 for event in events if event.step == "unmapped") == 0


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

    # The single-input artifact must NOT be documented as carrying the
    # divergence verdict: those two values only exist in `compare_sequences`,
    # and a caller told to read them here finds nothing and invents a value.
    assert "first_divergence_step" not in artifact
    assert "pre_divergence_equivalence" not in artifact
    assert "comparison" not in artifact


def test_compare_cli_exposes_the_divergence_verdict_with_caveats(tmp_path) -> None:
    left = tmp_path / "left.jsonl"
    left.write_text(
        '{"step_id":"controller","name":"turn_controller"}\n'
        '{"step_id":"route","name":"route_skills"}\n',
        encoding="utf-8",
    )
    right = tmp_path / "right.jsonl"
    right.write_text(
        '{"type":"thread.started"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"future.vendor.event"}\n',
        encoding="utf-8",
    )
    target = tmp_path / "compared.json"

    assert (
        main(
            [
                str(left),
                "--kind",
                "workbench-trace",
                "--compare",
                str(right),
                "--compare-kind",
                "codex-rollout",
                "--output",
                str(target),
            ]
        )
        == 0
    )
    artifact = json.loads(target.read_text(encoding="utf-8"))
    comparison = artifact["comparison"]

    # Lock the *whole* key set, not a subset: asserting only the keys we happen
    # to read lets a field be dropped while the test stays green, which is the
    # same class of gap as documenting a field the artifact never carried.
    assert set(comparison) == {
        "pre_divergence_equivalence",
        "first_divergence_step",
        "first_divergence",
        "evidence",
        "mapped_event_counts",
        "unmapped_counts",
        "interpretation_caveats",
    }
    assert isinstance(comparison["pre_divergence_equivalence"], str)
    assert isinstance(comparison["evidence"], list)
    assert all(isinstance(item, str) for item in comparison["evidence"])
    assert isinstance(comparison["interpretation_caveats"], list)
    assert all(isinstance(item, str) for item in comparison["interpretation_caveats"])

    assert comparison["pre_divergence_equivalence"] == "not_established"
    assert comparison["evidence"] == ["left=intent", "right=configure", "ordinal=0"]
    assert comparison["mapped_event_counts"] == {"left": 2, "right": 2}
    assert comparison["unmapped_counts"] == {"left": 0, "right": 1}
    assert artifact["left"]["source_kind"] == "workbench-trace"
    assert artifact["right"]["source_kind"] == "codex-rollout"

    # A mismatch is two steps at one ordinal: scalar null, structured object read.
    assert comparison["first_divergence_step"] is None
    assert comparison["first_divergence"] == {
        "ordinal": 0,
        "relation": "step_mismatch",
        "left_step": "intent",
        "right_step": "configure",
    }

    # Three misreadings the caveats exist to block: a vocabulary gap read as a
    # behavioural difference, `not_established` read as "no divergence", and a
    # two-sided mismatch collapsed into one L1 value.
    caveats = " ".join(comparison["interpretation_caveats"])
    assert "vocabulary gap" in caveats
    assert "insufficient trace" in caveats
    assert "step_mismatch" in caveats


def _write_pair(tmp_path) -> tuple[Path, Path]:
    left = tmp_path / "left.jsonl"
    left.write_text(
        '{"step_id":"controller"}\n{"step_id":"route"}\n',
        encoding="utf-8",
    )
    right = tmp_path / "right.jsonl"
    right.write_text(
        '{"type":"thread.started"}\n{"type":"turn.started"}\n',
        encoding="utf-8",
    )
    return left, right


def test_compare_accepts_our_own_single_input_artifacts_round_trip(tmp_path) -> None:
    left, right = _write_pair(tmp_path)

    direct = tmp_path / "direct.json"
    assert (
        main(
            [
                str(left),
                "--kind",
                "workbench-trace",
                "--compare",
                str(right),
                "--compare-kind",
                "codex-rollout",
                "--output",
                str(direct),
            ]
        )
        == 0
    )

    left_artifact = tmp_path / "left-normalized.json"
    right_artifact = tmp_path / "right-normalized.json"
    assert main([str(left), "--kind", "workbench-trace", "--output", str(left_artifact)]) == 0
    assert main([str(right), "--kind", "codex-rollout", "--output", str(right_artifact)]) == 0

    round_tripped = tmp_path / "round-tripped.json"
    assert (
        main([str(left_artifact), "--compare", str(right_artifact), "--output", str(round_tripped)])
        == 0
    )

    # The adapter tells triage to "consume the existing normalized artifacts".
    # Feeding them back used to re-run the raw mapper over normalized events,
    # which reads `type`/`kind`, not `step`, so both sides mapped to 0 events and
    # the verdict came back null -- indistinguishable from "no divergence".
    direct_comparison = json.loads(direct.read_text(encoding="utf-8"))["comparison"]
    reused = json.loads(round_tripped.read_text(encoding="utf-8"))
    assert reused["comparison"] == direct_comparison
    assert reused["comparison"]["mapped_event_counts"] == {"left": 2, "right": 2}

    # Provenance survives reuse: the hash still names the original trace.
    assert reused["left"]["reused_normalized_artifact"] is True
    assert (
        reused["left"]["input_sha256"]
        == json.loads(left_artifact.read_text(encoding="utf-8"))["input_sha256"]
    )
    assert reused["left"]["source_kind"] == "workbench-trace"
    assert reused["right"]["source_kind"] == "codex-rollout"


def test_incomparable_artifacts_fail_loudly_instead_of_mapping_to_nothing(tmp_path) -> None:
    left, _right = _write_pair(tmp_path)
    left_artifact = tmp_path / "left-normalized.json"
    assert main([str(left), "--kind", "workbench-trace", "--output", str(left_artifact)]) == 0
    good = json.loads(left_artifact.read_text(encoding="utf-8"))

    # v1 artifacts predate `plan`/`tool`; comparing them against v2 silently
    # compares two different vocabularies.
    v1 = dict(good, schema_version="normalized-harness-trace-1")
    v1.pop("vocabulary", None)
    foreign = dict(good, vocabulary="some-other-vocab")
    malformed = dict(good, events=[{"step": "route"}])
    outside = dict(
        good, events=[dict(good["events"][0], step="not-an-l1-step")]
    )
    verdict = dict(good, comparison={"first_divergence_step": None})

    for name, payload in (
        ("v1.json", v1),
        ("foreign.json", foreign),
        ("malformed.json", malformed),
        ("outside.json", outside),
        ("verdict.json", verdict),
    ):
        path = tmp_path / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NormalizedArtifactError):
            main([str(path), "--compare", str(left_artifact)])


_SECRET_SUMMARY = "authorization: super-secret /Users/alice/private.txt"


def _good_artifact(tmp_path) -> tuple[dict, Path]:
    left, _right = _write_pair(tmp_path)
    artifact = tmp_path / "good-normalized.json"
    assert main([str(left), "--kind", "workbench-trace", "--output", str(artifact)]) == 0
    return json.loads(artifact.read_text(encoding="utf-8")), artifact


def _with_event(good: dict, **overrides) -> dict:
    events = [dict(event) for event in good["events"]]
    events[0].update(overrides)
    return dict(good, events=events)


def test_reused_artifact_is_validated_field_by_field_not_just_step_enum(tmp_path) -> None:
    good, reference = _good_artifact(tmp_path)

    # Reuse skips the mapper, so it also skips the mapper's type coercion and
    # sanitizers.  Checking only presence + the `step` enum accepted every one of
    # these, including a summary carrying a credential and an absolute path --
    # a hole in the redaction guarantee that `trace-profile.md` §6 states.
    cases = {
        # types
        "sequence_type": _with_event(good, sequence="not-an-int"),
        "sequence_bool": _with_event(good, sequence=True),
        "sequence_position": _with_event(good, sequence=7),
        "timestamp_nested": _with_event(good, timestamp={"nested": "not-a-timestamp"}),
        "timestamp_text": _with_event(good, timestamp="last tuesday"),
        "summary_type": _with_event(good, summary=["not", "a", "string"]),
        # redaction
        "summary_secret": _with_event(good, summary=_SECRET_SUMMARY),
        "summary_path": _with_event(good, summary="source=x /Users/alice/notes.md"),
        "summary_长度": _with_event(good, summary="x" * 241),
        # Path *shape*, not character set: every one of these satisfies
        # `_SAFE_TOKEN` in full, which is why a character whitelist cannot answer
        # the question.  The id is concatenated into `source_event_id`, so a
        # traversal shape would travel with it into logs and path-like storage.
        "case_id_traversal": _with_event(good, case_id="../../etc/passwd"),
        "case_id_absolute": _with_event(good, case_id="/etc/passwd"),
        "case_id_dot": _with_event(good, case_id="suite/./case-01"),
        "case_id_dotdot": _with_event(good, case_id="suite/../case-01"),
        "case_id_empty_segment": _with_event(good, case_id="suite//case-01"),
        "case_id_windows_drive": _with_event(good, case_id="C:/cases/case-01"),
        "case_id_type": _with_event(good, case_id=7),
        "source_id_secret": _with_event(good, source_event_id="sk-live-deadbeef"),
        "source_type_unsafe": _with_event(good, source_event_type="has spaces"),
        # enums, and the unmapped pairing
        "provenance_enum": _with_event(good, native_or_normalized="made-up"),
        "provenance_pairing": _with_event(good, native_or_normalized="unmapped"),
        "role_enum": _with_event(good, event_role="wat"),
        # foreign schema masquerading as a newer one
        "extra_key": _with_event(good, note="added by hand"),
        # provenance of the verdict
        "hash_shape": dict(good, input_sha256="nope"),
        "hash_type": dict(good, input_sha256=None),
        "source_kind_enum": dict(good, source_kind="some-other-harness"),
        "source_kind_auto": dict(good, source_kind="auto"),
        "source_file_unsafe": dict(good, source_file="/Users/alice/trace.jsonl"),
        # derived counts disagreeing means the events were edited afterwards
        "event_count": dict(good, event_count=99),
        "unmapped_count": dict(good, unmapped_count=5),
    }

    for name, payload in cases.items():
        path = tmp_path / f"bad-{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NormalizedArtifactError):
            main([str(path), "--compare", str(reference)])

    # The unmodified artifact still round-trips: these checks reject tampering,
    # they do not reject our own output.
    assert main([str(reference), "--compare", str(reference)]) == 0


def test_case_id_contract_rejects_path_shape_but_keeps_hierarchical_ids(tmp_path) -> None:
    good, reference = _good_artifact(tmp_path)

    # The check is structural, so it must not become "no slashes allowed":
    # `suite/case-01` is an ordinary hierarchical id and stays valid.
    legal = tmp_path / "hierarchical.json"
    legal.write_text(
        json.dumps(_with_event(good, case_id="suite/case-01")), encoding="utf-8"
    )
    assert main([str(legal), "--compare", str(reference)]) == 0

    # Raw input takes the tolerant path: the same shape degrades to None and,
    # crucially, is not concatenated into `source_event_id`.
    events = normalize_records(
        [
            {"case_id": "../../etc/passwd", "kind": "task"},
            {"case_id": "suite/case-01", "kind": "task"},
        ],
        kind="runtime-benchmark",
    )
    assert events[0].case_id is None
    assert "etc/passwd" not in events[0].source_event_id
    # The legal id still travels into the composite id, as benchmark events rely on.
    assert events[1].case_id == "suite/case-01"
    assert events[1].source_event_id.startswith("suite/case-01:")


def test_rejection_message_describes_the_bad_value_without_echoing_it(tmp_path) -> None:
    good, reference = _good_artifact(tmp_path)
    path = tmp_path / "leaky.json"
    path.write_text(json.dumps(_with_event(good, summary=_SECRET_SUMMARY)), encoding="utf-8")

    with pytest.raises(NormalizedArtifactError) as raised:
        main([str(path), "--compare", str(reference)])

    message = str(raised.value)
    # A validator that echoes the offending value to explain itself copies the
    # credential into logs and CI output -- the exact thing the check exists to
    # prevent.  Name the field and the shape instead.
    assert "super-secret" not in message
    assert "/Users/alice" not in message
    assert "summary" in message
    assert "len=" in message


def test_derived_count_rejection_does_not_echo_invalid_text(tmp_path) -> None:
    good, reference = _good_artifact(tmp_path)
    path = tmp_path / "leaky-count.json"
    path.write_text(
        json.dumps(dict(good, event_count=_SECRET_SUMMARY)),
        encoding="utf-8",
    )

    with pytest.raises(NormalizedArtifactError) as raised:
        main([str(path), "--compare", str(reference)])

    message = str(raised.value)
    assert "super-secret" not in message
    assert "/Users/alice" not in message
    assert "event_count=<str>" in message
    assert "recomputed" in message
