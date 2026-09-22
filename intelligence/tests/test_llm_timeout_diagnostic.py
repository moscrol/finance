"""Probe integrity and real loopback deadline regression tests."""

from __future__ import annotations

import json
import sys
import time

import pytest

from scripts.review_probes import diagnose_llm_timeout as probe


def test_violation_uses_actual_wall_time_not_timeout_quote():
    case = {"scenario": "trickle", "wall_elapsed_seconds": 3.0,
            "timeout_input_seconds": 0.8, "attempts": [{"timeout_seconds": 0.79}]}
    assert probe.violations([case], 0.2) == ["trickle"]
    case["wall_elapsed_seconds"] = 0.9
    assert probe.violations([case], 0.2) == []


def test_real_fast_loopback_preserves_one_attempt_and_restores_transport():
    before = probe.llm_refine.llm_http_transport.urlopen
    result = probe.run_case("fast")
    assert result["content_present"] is True
    assert result["request_count"] == result["reserved_count"] == len(result["records"]) == 1
    assert len(result["attempts"]) == 1
    assert result["requests"] == [{"stream_requested": False}]
    assert 0 < result["attempts"][0]["timeout_seconds"] <= 0.8
    assert result["records"][0]["status"] == "success"
    assert probe.llm_refine.llm_http_transport.urlopen is before


def test_zero_deadline_has_no_http_or_billing_attempt():
    result = probe.run_case("zero_deadline")
    assert not result["content_present"]
    assert result["request_count"] == result["reserved_count"] == 0
    assert result["attempts"] == result["records"] == []


@pytest.mark.parametrize("scenario", [
    "header_delay", "body_stall", "headers_then_body", "body_trickle",
    "tools_stream_trickle", "tools_stream_partial_line",
    "synthesis_stream_trickle", "synthesis_stream_partial_line",
])
def test_real_slow_response_is_cancelled_without_accepting_late_payload(scenario):
    budget = 1.2 if scenario.startswith("synthesis_stream") else 0.8
    result = probe.run_case(scenario, budget)
    assert result["content_present"] is False
    assert result["request_count"] == result["reserved_count"] == len(result["records"]) == 1
    assert result["wall_elapsed_seconds"] <= budget + 0.2
    assert result["records"][0]["status"] == "failed"
    assert result["records"][0]["reason"] == "timeout"
    if scenario.endswith("partial_line"):
        assert result["emitted_chars"] == 0
    elif "stream" in scenario:
        assert result["emitted_chars"] > 0


def test_real_late_judge_report_is_rejected_at_the_transport_boundary():
    result = probe.run_judge_case("judge_late_report")
    assert result["report_received"] is False
    assert result["unavailable"] is True
    assert result["wall_elapsed_seconds"] <= 1.0
    assert result["records"][0]["status"] == "failed"
    assert result["request_count"] == len(result["records"]) == 1


def test_stalled_parent_still_stops_the_worker_at_the_deadline():
    """The worker owns the socket, so its own hard stop must not be redundant.

    Every other case ends because the parent checks the deadline between reads.
    Here the parent never reads, which is what a slow content callback looks
    like from the worker's side: only the worker-side stop can close the
    network, and it must fire long before the endpoint stops trickling.
    """
    # Budgets stay well above worker spawn cost: a deadline shorter than the
    # spawn would expire before the worker runs, which tests the machine's load
    # rather than the stop. The endpoint trickles ~10.8s, far past the deadline.
    with probe.local_endpoint("body_trickle", 3.0) as (provider, _requests, _attempts):
        request = probe.urllib.request.Request(
            provider.base_url + "/chat/completions", data=b"{}", method="POST",
        )
        started = time.monotonic()
        response = probe.llm_refine.llm_http_transport.urlopen(
            request, 1.5, loopback_only=True,
        )
        try:
            # TimeoutExpired here is the regression: a worker that outlives its
            # deadline keeps reading the socket no matter what the parent does.
            returncode = response.process.wait(timeout=4.0)
            elapsed = time.monotonic() - started
            assert elapsed < 4.0, f"worker outlived its deadline (rc={returncode})"
        finally:
            response.close()


def test_call_timeout_never_outlives_the_shared_research_deadline():
    """A per-call slice must not spend budget the shared deadline no longer has.

    Callers hand down both a slice and the research deadline. If the transport
    honoured only the slice, one late call could outlive the whole run, which is
    the failure the probe cannot see while both values agree.
    """
    transport = probe.llm_refine.llm_http_transport
    with probe.local_endpoint("body_trickle", 0.8) as (provider, _requests, _attempts):
        request = probe.urllib.request.Request(
            provider.base_url + "/chat/completions", data=b"{}", method="POST",
        )
        deadline = probe.llm_refine.Deadline.from_timeout(0.5)
        started = time.monotonic()
        with pytest.raises(transport.HTTPDeadlineExceeded):
            with transport.urlopen(
                request, 10.0, deadline=deadline, loopback_only=True,
            ) as response:
                response.read()
        # The endpoint needs ~2.9s to finish; honouring only the 10s slice would
        # read it to completion instead of raising.
        assert time.monotonic() - started < 2.0


def test_refine_wrapper_forwards_the_shared_deadline_to_the_transport():
    """`llm_refine._open_deadline_http_response` is the seam every call site uses.

    The transport test above proves the transport honours ``deadline`` when it is
    given one.  This test proves the wrapper actually gives it one: with a 10s
    slice and a 0.5s shared deadline against a trickling endpoint (~2.9s), the
    call must die at the shared deadline and surface as ``LLMDeadlineExceeded``.
    Dropping the ``deadline=`` forwarding in the wrapper keeps the probe and the
    transport test green (there slice == deadline), so only this test guards it.
    """
    llm_refine = probe.llm_refine
    with probe.local_endpoint("body_trickle", 0.8) as (provider, _requests, _attempts):
        request = probe.urllib.request.Request(
            provider.base_url + "/chat/completions", data=b"{}", method="POST",
        )
        deadline = llm_refine.Deadline.from_timeout(0.5)
        started = time.monotonic()
        with pytest.raises(llm_refine.LLMDeadlineExceeded):
            with llm_refine._open_deadline_http_response(
                request, 10.0, deadline=deadline,
            ) as response:
                response.read()
        assert time.monotonic() - started < 2.0


def test_shared_window_zero_rejection_is_not_a_third_request():
    result = probe.run_judge_case("judge_window_stalls")
    assert result["request_count"] == len(result["attempts"]) == len(result["records"]) == 2
    assert result["final_attempt_index"] == 2
    assert result["final_timeout_asked"] == 0.0
    assert result["final_exc_class"] is None
    assert result["last_dispatched_failure"]["judge_attempt_index"] == 1
    assert result["last_dispatched_failure"]["exc_class"] == "LLMDeadlineExceeded"
    assert result["final_issue"] == probe.semantic.WINDOW_EXHAUSTED_ISSUE
    assert result["remaining_root_seconds"] > 0
    assert all(row["purpose"] == "judge" for row in result["records"])
    assert all(0 < row["timeout_seconds"] <= 0.8 for row in result["attempts"])


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
    with pytest.raises(RuntimeError, match="[Nn]on-loopback"):
        probe.llm_refine.llm_http_transport.urlopen(
            probe.urllib.request.Request("https://example.invalid/v1"),
            timeout=0.8,
            loopback_only=True,
        )
