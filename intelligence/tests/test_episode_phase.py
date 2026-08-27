"""Episode 审计用 phase 投影：sidecar，不进 durable 事件日志。"""

from __future__ import annotations

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_phase import (
    PhaseHints,
    PhaseRecorder,
    project_phase_transitions,
)


def _event(seq: int, kind: str, **payload: object) -> EpisodeEvent:
    return EpisodeEvent(seq, kind, payload)


def test_simple_path_has_exactly_one_public_terminal() -> None:
    events = (
        _event(1, "task", question="目前市场结构如何"),
        _event(2, "plan", steps=["查盘面"]),
        _event(3, "tool_request", name="market_data"),
        _event(4, "tool_result", name="market_data"),
        _event(5, "finalization", reason="surface_satisfied"),
        _event(6, "finish", status="completed", stop_reason="model_finish"),
    )

    trace = project_phase_transitions(
        events,
        hints=PhaseHints(
            structural_verify=True,
            semantic_verify=True,
            public_status="completed",
            evidence_count=1,
            remaining_calls=3,
            remaining_seconds=12.0,
        ),
    )

    phases = tuple(item.to_phase for item in trace.transitions)
    assert phases == (
        "planning",
        "research",
        "finalizing",
        "structural_verify",
        "semantic_verify",
        "completed",
    )
    assert trace.terminal_phases == ("completed",)
    assert not trace.has_anomalies
    payload = trace.to_dict()
    assert payload["transitions"][-1]["terminal_claimed"] is True
    assert payload["transitions"][-1]["remaining_calls"] == 3
    assert "unregistered_kinds" not in payload.get("anomalies", {})


def test_intermediate_finish_is_not_a_public_terminal() -> None:
    """resume 会在同一 ledger 上再写一条 finish。中间那条仍是 finalizing。"""

    events = (
        _event(1, "task"),
        _event(2, "tool_result"),
        _event(3, "finalization", reason="close_tools"),
        _event(4, "finish", status="partial", stop_reason="model_finish"),
        _event(5, "repair_goal", repair_goal_id="g1"),
        _event(6, "tool_result"),
        _event(7, "finish", status="completed", stop_reason="repair_model_finish"),
    )

    trace = project_phase_transitions(
        events,
        hints=PhaseHints(
            structural_verify=True,
            semantic_verify=True,
            public_status="completed",
            repair_attempts=1,
        ),
    )

    assert trace.terminal_phases == ("completed",)
    assert all(
        item.trigger == "public_outcome"
        for item in trace.transitions
        if item.to_phase in {"completed", "partial", "degraded", "failed", "cancelled"}
    )
    assert not trace.has_anomalies


def test_recorder_interleaves_verify_and_repair() -> None:
    recorder = PhaseRecorder()
    recorder.ingest_events(
        (
            _event(1, "task"),
            _event(2, "tool_result"),
            _event(3, "finalization", reason="close_tools"),
            _event(4, "finish", status="partial", stop_reason="model_finish"),
        )
    )
    recorder.record("structural_verify", trigger="structural_verifier", reason_code="missing_outputs")
    recorder.record("repair", trigger="resume", reason_code="repair_goal")
    recorder.ingest_events(
        (
            _event(4, "finish", status="partial", stop_reason="model_finish"),
            _event(5, "repair_goal"),
            _event(6, "finish", status="completed", stop_reason="repair_model_finish"),
        )
    )
    recorder.record("structural_verify", trigger="structural_verifier", reason_code="recheck")
    recorder.record("semantic_verify", trigger="semantic_verifier", reason_code="passed")
    recorder.record(
        "completed",
        trigger="public_outcome",
        reason_code="completed",
        remaining_calls=1,
        evidence_count=2,
        repair_attempts=1,
    )

    trace = recorder.trace()
    assert tuple(item.to_phase for item in trace.transitions) == (
        "planning",
        "research",
        "finalizing",
        "structural_verify",
        "repair",
        "finalizing",
        "structural_verify",
        "semantic_verify",
        "completed",
    )
    assert trace.terminal_phases == ("completed",)
    assert not trace.has_anomalies


def test_undefined_transition_is_kept_and_flagged() -> None:
    recorder = PhaseRecorder()
    recorder.record("planning", trigger="task", reason_code="task")
    recorder.record("semantic_verify", trigger="skip", reason_code="illegal_skip")

    trace = recorder.trace()
    assert trace.has_anomalies
    assert trace.anomalies_to_dict()["illegal_transitions"] == [
        "planning -> semantic_verify (skip)",
    ]
    assert tuple(item.to_phase for item in trace.transitions) == (
        "planning",
        "semantic_verify",
    )


def test_post_terminal_records_do_not_change_public_outcome() -> None:
    recorder = PhaseRecorder()
    recorder.record("planning", trigger="task", reason_code="task")
    recorder.record("failed", trigger="public_outcome", reason_code="cancelled")
    recorder.record("completed", trigger="late_result", reason_code="should_not_win")

    trace = recorder.trace()
    assert trace.terminal_phases == ("failed",)
    assert trace.has_anomalies
    assert "late_result" in trace.anomalies_to_dict()["post_terminal_triggers"]
    assert trace.transitions[-1].to_phase == "failed"


def test_cancelled_from_research_is_a_legal_terminal() -> None:
    trace = project_phase_transitions(
        (
            _event(1, "task"),
            _event(2, "tool_request"),
        ),
        hints=PhaseHints(public_status="cancelled", reason_code="cancelled"),
    )
    assert trace.terminal_phases == ("cancelled",)
    assert not trace.has_anomalies


def test_phase_trace_does_not_invent_durable_event_kinds() -> None:
    from intelligence.services.episode_event_lanes import DURABLE_EVENT_KINDS

    assert "phase_transition" not in DURABLE_EVENT_KINDS
    assert "structural_verify" not in DURABLE_EVENT_KINDS
    assert "semantic_verify" not in DURABLE_EVENT_KINDS
