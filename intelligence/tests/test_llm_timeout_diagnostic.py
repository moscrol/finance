"""Probe integrity tests; actual deadline failures live in its strict receipt."""

from __future__ import annotations

import json
import sys

import pytest

from scripts.review_probes import diagnose_llm_timeout as probe


def test_violation_uses_actual_wall_time_not_timeout_quote():
    case = {"scenario": "trickle", "wall_elapsed_seconds": 3.0,
            "timeout_input_seconds": 0.8, "attempts": [{"timeout_seconds": 0.79}]}
    assert probe.violations([case], 0.2) == ["trickle"]
    case["wall_elapsed_seconds"] = 0.9
    assert probe.violations([case], 0.2) == []


def test_real_fast_loopback_preserves_one_attempt_and_restores_urlopen():
    before = probe.llm_refine.urllib.request.urlopen
    result = probe.run_case("fast")
    assert result["content_present"] is True
    assert result["request_count"] == result["reserved_count"] == len(result["records"]) == 1
    assert len(result["attempts"]) == 1
    assert result["requests"] == [{"stream_requested": False}]
    assert 0 < result["attempts"][0]["timeout_seconds"] <= 0.8
    assert result["records"][0]["status"] == "success"
    assert probe.llm_refine.urllib.request.urlopen is before


def test_zero_deadline_has_no_http_or_billing_attempt():
    result = probe.run_case("zero_deadline")
    assert not result["content_present"]
    assert result["request_count"] == result["reserved_count"] == 0
    assert result["attempts"] == result["records"] == []


def test_shared_window_zero_rejection_is_not_a_third_request():
    result = probe.run_judge_case("judge_window_stalls")
    assert result["request_count"] == len(result["attempts"]) == len(result["records"]) == 2
    assert result["final_attempt_index"] == 2
    assert result["final_timeout_asked"] == 0.0
    assert result["final_exc_class"] is None
    assert result["last_dispatched_failure"]["judge_attempt_index"] == 1
    assert result["last_dispatched_failure"]["exc_class"] == "TimeoutError"
    assert result["final_issue"] == probe.semantic.WINDOW_EXHAUSTED_ISSUE
    assert result["remaining_root_seconds"] > 0
    assert all(row["purpose"] == "judge" for row in result["records"])


def test_expired_root_is_distinct_from_exhausted_judge_window():
    result = probe.run_judge_case("judge_root_expired")
    assert result["request_count"] == 0
    assert result["records"] == result["attempts"] == []
    assert result["last_dispatched_failure"] is None
    assert result["final_issue"] == probe.semantic.ROOT_DEADLINE_EXHAUSTED_ISSUE


@pytest.mark.parametrize("strict,elapsed,expected", [(False, 3.0, 0), (True, 3.0, 1), (True, 0.2, 0)])
def test_cli_strict_mode_is_a_real_wall_clock_gate(monkeypatch, tmp_path, strict, elapsed, expected):
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(probe, "SCENARIOS", ("fast",))
    monkeypatch.setattr(probe, "JUDGE_SCENARIOS", ())
    monkeypatch.setattr(probe, "source_identity", lambda: {"revision": "fixed"})
    monkeypatch.setattr(probe, "run_case", lambda name, budget: {
        "scenario": name, "timeout_input_seconds": budget, "wall_elapsed_seconds": elapsed,
    })
    monkeypatch.setattr(sys, "argv", ["probe", "--output", str(output), *(["--assert-deadline"] if strict else [])])
    assert probe.main() == expected
    receipt = json.loads(output.read_text())
    assert receipt["deadline_violations"] == (["fast"] if elapsed > 1 else [])
    assert receipt["source_before"] == receipt["source_after"]


def test_existing_receipt_is_never_overwritten(monkeypatch, tmp_path):
    output = tmp_path / "receipt.json"
    output.write_text("sealed")
    monkeypatch.setattr(sys, "argv", ["probe", "--output", str(output)])
    with pytest.raises(FileExistsError):
        probe.main()
    assert output.read_text() == "sealed"


@pytest.mark.parametrize("value", ["nan", "inf", "0", "30"])
def test_probe_rejects_unbounded_or_nonfinite_waits(monkeypatch, tmp_path, value):
    monkeypatch.setattr(sys, "argv", ["probe", "--timeout", value, "--output", str(tmp_path / "receipt.json")])
    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 2


def test_endpoint_guard_rejects_external_hosts_before_network():
    with probe.local_endpoint("fast", 0.8):
        with pytest.raises(RuntimeError, match="non-loopback"):
            probe.llm_refine.urllib.request.urlopen(
                probe.urllib.request.Request("https://example.invalid/v1"), timeout=0.8,
            )
