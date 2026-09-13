"""Safety assertions against public outputs; controls distinguish fail-closed from overblocking."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def results():
    return {t: json.loads(subprocess.check_output([sys.executable, str(Path(__file__).with_name("probe_round7.py")), t], text=True))["probes"] for t in ("01", "05")}


def _valid(result):
    assert result["receipt"]["invalid_reasons"] == []
    assert result["receipt"]["event_accounting"]["rejected"] == []
    assert result["summary_errors"] == []
    assert all(a["evidence_status"] == "ok" for a in result["receipt"]["tasks"]["assisted"]["attempts"])


def test_j12_repeated_occurrences_and_scan_stability(results):
    reports = results["01"]["repeat_and_scan_stability"]
    for r in reports.values():
        by_id = {i["id"]: i for i in r["items"]}
        assert r["counts"]["items_open"] == 1
        assert len(by_id) == len(r["items"])
        for item in r["items"]:
            seen = set()
            p = item["id"]
            while p:
                assert p in by_id and p not in seen
                seen.add(p)
                prev = by_id[p]["supersedes"]
                if prev:
                    assert by_id[prev]["day"] < by_id[p]["day"]
                p = prev
    assert reports["2026-09-14"]["items"] == reports["2026-09-15"]["items"]
    assert len(reports["2026-09-14"]["items"]) == 5


def test_j12_new_occurrence_action_survives_next_scan(results):
    r = results["01"]["new_action_next_scan"]
    assert r["management_log"]["applied"] == 1
    assert r["management_log"]["rejected"] == 0
    assert len([i for i in r["items"] if i["status"] == "snoozed"]) == 1


@pytest.mark.parametrize("case", ["second_tool_only", "second_writer_tool"])
def test_pv11_one_attempt_cannot_cover_another_attempt_models(results, case):
    r = results["05"]["two_successful_attempts"][case]
    _valid(r)
    assert len(r["receipt"]["tasks"]["assisted"]["attempts"]) == 2
    assert r["cost"]["detail"]["full_cost_status"] == "unknown", r["cost"]


def test_pv11_multi_attempt_controls(results):
    p = results["05"]["two_successful_attempts"]
    for r in p.values():
        _valid(r)
    assert p["second_no_fees"]["cost"]["detail"]["full_cost_status"] == "unknown"
    assert p["both_complete"]["cost"]["detail"]["full_cost_status"] == "known"
    assert p["both_complete"]["cost"]["detail"]["known_cost_by_currency"] == {"CNY": 1.39}


def test_pv12_failed_tool_fee_cannot_erase_retry_model_gap(results):
    r = results["05"]["all_failed_attempts"]["tool_only"]
    _valid(r)
    assert all(a["failed"] for a in r["receipt"]["tasks"]["assisted"]["attempts"])
    assert "retry" not in r["cost"]["detail"]["not_applicable_components"]
    assert r["cost"]["detail"]["full_cost_status"] == "unknown", r["cost"]


def test_pv12_failed_attempt_controls(results):
    p = results["05"]["all_failed_attempts"]
    for r in p.values():
        _valid(r)
    assert p["no_fees"]["cost"]["detail"]["full_cost_status"] == "unknown"
    assert p["model_and_tool"]["cost"]["detail"]["full_cost_status"] == "known"


def test_pv13_uncovered_components_reach_public_summary(results):
    r = results["05"]["missing_component_detail"]
    _valid(r)
    assert r["cost"]["detail"]["full_cost_status"] == "unknown"
    # Both the missing task id and actual missing component must survive projection.
    serialized = json.dumps(r["cost"], ensure_ascii=False)
    assert "uncovered_components" in serialized, r["cost"]
    assert "review_model" in serialized, r["cost"]
