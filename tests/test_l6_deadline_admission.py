"""The live controller must not admit incomplete or cross-candidate probes."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.review_probes import diagnose_llm_timeout as probe
from scripts.review_probes.prepare_adaptive_l6_runner import validate_deadline_admission


@pytest.fixture
def strict_receipt(monkeypatch):
    identity = {"revision": "a" * 40, "working_tree_status": "", "source_sha256": {"fixture": "b" * 64}}
    monkeypatch.setattr(probe, "source_identity", lambda: identity)
    cases = []
    for name in probe.SCENARIOS + probe.JUDGE_SCENARIOS:
        zero = name in {"zero_deadline", "judge_root_expired"}
        count = 0 if zero else 2 if name == "judge_window_stalls" else 1
        budget = 0.0 if zero else 1.2 if name.startswith("synthesis_stream") else 0.8
        cases.append({
            "scenario": name, "request_count": count,
            "attempts": [{"headers_ms": 1}] * count, "records": [{}] * count,
            "content_present": name == "fast", "emitted_chars": int("stream" in name),
            "timeout_input_seconds": budget, "wall_elapsed_seconds": budget,
        })
    return {
        "schema_version": 3, "source_before": deepcopy(identity), "source_after": deepcopy(identity),
        "scheduling_tolerance_seconds": 0.2, "deadline_violations": [], "coverage_gaps": [], "cases": cases,
    }


def test_complete_current_receipt_can_admit(strict_receipt):
    validate_deadline_admission(strict_receipt, "a" * 40)


@pytest.mark.parametrize("fault", [
    "reported_gap", "hidden_gap", "missing_gap_field", "reported_overrun", "hidden_overrun",
    "missing_case", "duplicate_case", "unknown_case", "bad_case", "unhashable_name",
    "expanded_timeout", "expanded_tolerance", "missing_tolerance", "nan_elapsed", "negative_elapsed",
    "infinite_elapsed", "bool_elapsed", "bool_timeout", "old_revision", "dirty_receipt",
    "changed_sources", "moved_candidate", "old_schema",
])
def test_incomplete_or_forged_receipt_cannot_admit(strict_receipt, fault):
    receipt = strict_receipt
    case = next(c for c in receipt["cases"] if c["scenario"] == "body_stall")
    revision = "a" * 40
    if fault == "reported_gap":
        receipt["coverage_gaps"] = [{"scenario": "body_stall"}]
    elif fault == "hidden_gap":
        case["request_count"] = 0
    elif fault == "missing_gap_field":
        del receipt["coverage_gaps"]
    elif fault == "reported_overrun":
        receipt["deadline_violations"] = ["body_stall"]
    elif fault == "hidden_overrun":
        case["wall_elapsed_seconds"] = 1.01
    elif fault == "missing_case":
        receipt["cases"].pop()
    elif fault == "duplicate_case":
        receipt["cases"][-1] = deepcopy(receipt["cases"][0])
    elif fault == "unknown_case":
        case["scenario"] = "not_a_scenario"
    elif fault == "bad_case":
        receipt["cases"][0] = None
    elif fault == "unhashable_name":
        case["scenario"] = []
    elif fault == "expanded_timeout":
        case["timeout_input_seconds"] = 3.0
    elif fault == "expanded_tolerance":
        receipt["scheduling_tolerance_seconds"] = 0.3
    elif fault == "missing_tolerance":
        del receipt["scheduling_tolerance_seconds"]
    elif fault == "nan_elapsed":
        case["wall_elapsed_seconds"] = float("nan")
    elif fault == "negative_elapsed":
        case["wall_elapsed_seconds"] = -1
    elif fault == "infinite_elapsed":
        case["wall_elapsed_seconds"] = float("inf")
    elif fault == "bool_elapsed":
        case["wall_elapsed_seconds"] = False
    elif fault == "bool_timeout":
        receipt["cases"][-1]["timeout_input_seconds"] = False
    elif fault == "old_revision":
        receipt["source_before"]["revision"] = "b" * 40
    elif fault == "dirty_receipt":
        receipt["source_before"]["working_tree_status"] = " M changed.py"
    elif fault == "changed_sources":
        receipt["source_after"]["source_sha256"] = {"fixture": "c" * 64}
    elif fault == "moved_candidate":
        revision = "b" * 40
    elif fault == "old_schema":
        receipt["schema_version"] = 2
    with pytest.raises(ValueError):
        validate_deadline_admission(receipt, revision)
