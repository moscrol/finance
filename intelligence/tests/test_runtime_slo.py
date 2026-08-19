"""P4: SLO projection never fills missing measurements with zero."""

from __future__ import annotations

from pathlib import Path

from intelligence.services.gate_receipt import RECEIPT_KEYS
from intelligence.services.runtime_slo import (
    NOT_EVALUATED,
    RATE_FIELDS,
    UNKNOWN,
    RuntimeObservation,
    evaluate_release_gate,
    observation_from_artifacts,
    project_slo,
)


def test_empty_cohort_rates_are_not_evaluated_not_zero() -> None:
    slo = project_slo(())
    assert slo["n"] == 0
    for field in RATE_FIELDS:
        assert slo[field] == NOT_EVALUATED
    assert slo["p50_latency"] == NOT_EVALUATED
    assert slo["p50_time_to_first_tool"] == NOT_EVALUATED
    assert slo["average_llm_calls"] == NOT_EVALUATED
    assert slo["dimensions"]["status"] == [UNKNOWN]


def test_evaluated_zero_completion_is_numeric_zero() -> None:
    slo = project_slo(
        (
            RuntimeObservation(
                status="failed",
                stop_reason="cancelled",
                budget_exhausted=False,
            ),
            RuntimeObservation(
                status="failed",
                stop_reason="deadline_exhausted",
                budget_exhausted=True,
            ),
        )
    )
    assert slo["completion_rate"] == 0.0
    assert slo["failed_rate"] == 1.0
    assert slo["cancelled_rate"] == 0.5
    assert slo["budget_exhaustion_rate"] == 0.5


def test_missing_time_to_first_tool_stays_unevaluated_when_latency_exists() -> None:
    slo = project_slo(
        (
            RuntimeObservation(
                status="completed",
                latency_seconds=10.0,
                time_to_first_tool=None,
            ),
        )
    )
    assert slo["p50_latency"] == 10.0
    assert slo["p50_time_to_first_tool"] == NOT_EVALUATED


def test_observation_extracts_receipt_without_inventing_tool_timing() -> None:
    row = observation_from_artifacts(
        run={"status": "completed"},
        report={
            "gate_receipt": {
                "rev": "abc123",
                "judge_status": "passed",
                "timings": {"elapsed_seconds": 12.0},
            },
            "query_ledger": {"late_result_discarded_count": 0},
        },
        private_artifact={
            "runtime_backend": "continuous",
            "contract": {
                "question_type": "market_forecast",
                "research_tier": "standard",
            },
            "outcome": {
                "status": "completed",
                "stop_reason": "completed",
                "usage": {"llm_calls": 3, "tool_calls": 2},
            },
            "repair_attempts": 1,
            "cold_restart": False,
            "events": [
                {"kind": "task", "payload": {}},
                {
                    "kind": "model_turn",
                    "payload": {"provider_name": "zhipu", "model": "glm-4"},
                },
                {"kind": "tool_request", "payload": {"call_id": "c1"}},
                {"kind": "tool_result", "payload": {"call_id": "c1"}},
            ],
        },
    )
    assert row.source_revision == "abc123"
    assert row.runtime_backend == "continuous"
    assert row.provider == "zhipu"
    assert row.model == "glm-4"
    assert row.repaired is True
    assert row.cold_restart is False
    assert row.late_result_count == 0
    assert row.tools_paired is True
    assert row.time_to_first_tool is None
    assert row.semantic_verifier_unavailable is False


def test_unpaired_tool_request_is_observable() -> None:
    row = observation_from_artifacts(
        private_artifact={
            "events": [
                {"kind": "tool_request", "payload": {}},
                {"kind": "tool_request", "payload": {}},
                {"kind": "tool_result", "payload": {}},
            ]
        }
    )
    assert row.tools_paired is False


def test_release_gate_fails_closed_when_canary_field_is_unevaluated() -> None:
    verdict = evaluate_release_gate(
        (
            RuntimeObservation(
                source_revision="rev-1",
                runtime_backend="continuous",
                provider="zhipu",
                model="glm-4",
                status="completed",
                stop_reason="completed",
                tools_paired=True,
                terminal_claim_conflict=False,
                budget_exhausted=False,
                late_result_count=None,
                provider_error=False,
            ),
        ),
        expected_revision="rev-1",
        regression_green=True,
    )
    assert verdict["rollback"] == "manual"
    assert verdict["passed"] is False
    canary = next(
        item
        for item in verdict["checks"]
        if item["name"] == "canary_late_result_rate"
    )
    assert canary["status"] == NOT_EVALUATED


def test_release_gate_passes_when_every_check_is_evaluated_and_green() -> None:
    verdict = evaluate_release_gate(
        (
            RuntimeObservation(
                source_revision="rev-1",
                runtime_backend="continuous",
                provider="zhipu",
                model="glm-4",
                status="completed",
                stop_reason="completed",
                latency_seconds=8.0,
                repaired=False,
                cold_restart=False,
                late_result_count=0,
                provider_error=False,
                tool_error=False,
                semantic_verifier_unavailable=False,
                llm_calls=2,
                tool_calls=1,
                budget_exhausted=False,
                tools_paired=True,
                terminal_claim_conflict=False,
            ),
            RuntimeObservation(
                source_revision="rev-1",
                runtime_backend="continuous",
                provider="zhipu",
                model="glm-4",
                status="partial",
                stop_reason="deadline_exhausted",
                latency_seconds=20.0,
                repaired=True,
                cold_restart=False,
                late_result_count=0,
                provider_error=False,
                tool_error=True,
                semantic_verifier_unavailable=False,
                llm_calls=4,
                tool_calls=3,
                budget_exhausted=True,
                tools_paired=True,
                terminal_claim_conflict=False,
            ),
        ),
        expected_revision="rev-1",
        regression_green=True,
    )
    assert verdict["passed"] is True
    assert verdict["slo"]["completion_rate"] == 0.5
    assert verdict["slo"]["late_result_rate"] == 0.0
    assert all(item["status"] == "pass" for item in verdict["checks"])


def test_slo_module_stays_in_services_and_does_not_import_runtime() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "services" / "runtime_slo.py"
    ).read_text(encoding="utf-8")
    assert "intelligence.runtime" not in source
    assert "from intelligence.runtime" not in source


def test_gate_receipt_keyset_is_frozen_against_slo_projection() -> None:
    """P4 aggregates receipts; it must not grow the ask/episode dict-diff contract."""

    assert RECEIPT_KEYS == (
        "schema_version",
        "engine",
        "rev",
        "verified_status",
        "judge_status",
        "issues",
        "judge_unavailable_count",
        "content_degraded_count",
        "timings",
    )
