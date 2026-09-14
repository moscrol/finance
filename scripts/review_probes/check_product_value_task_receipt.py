"""QC checks; explicit invocation, not default pytest collection.

QC_TREE=<target-worktree> python -m pytest -q <this-file>
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    output = tmp_path_factory.mktemp("task-receipt") / "result.json"
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("product_value_task_receipt.py")), os.environ["QC_TREE"], str(output)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(output.read_text())


def test_inputs_are_accepted(results):
    for result in results.values():
        receipt = result["receipt"]
        assert receipt["invalid_reasons"] == []
        assert receipt["event_accounting"]["rejected"] == []
        assert result["summary_errors"] == []
        # Legitimate original human timing is not lost or blocked.
        original = receipt["tasks"]["original"]
        assert original["attempts"] == []
        assert original["timing"]["reason"] is None
        assert original["timing"]["end_to_end_minutes"] > 0


@pytest.mark.parametrize("case,missing", [
    ("task_no_fees", {"writer_model", "review_model"}),
    ("task_tool_only", {"writer_model", "review_model"}),
    ("task_writer_tool", {"review_model"}),
])
def test_no_run_task_component_gaps_reach_receipt(results, case, missing):
    result = results[case]
    receipt = result["receipt"]
    assert receipt["tasks"]["assisted"]["attempts"] == []
    assert receipt["tasks"]["assisted"]["timing"]["reason"] is None
    assert result["cost"]["detail"]["full_cost_status"] == "unknown"
    assert receipt["status"] == "incomplete"
    serialized = json.dumps(receipt["unknown_cost_components"])
    assert all(component in serialized for component in missing)


@pytest.mark.parametrize("case,amount", [("task_complete", .93), ("protocol_review_exempt", .83)])
def test_complete_and_protocol_exemption_controls(results, case, amount):
    result = results[case]
    assert result["receipt"]["status"] == "valid"
    assert result["receipt"]["unknown_cost_components"] == []
    assert result["cost"]["detail"]["full_cost_status"] == "known"
    assert result["cost"]["detail"]["known_cost_by_currency"] == {"CNY": amount}


def test_attempt_component_identity_survives_summary_projection(results):
    result = results["attempt_no_fees"]
    gaps = [g for g in result["cost"]["unknown"] if g["reason"] == "no_usage_evidence_for_attempt"]
    # A list per attempt or one row per component are both acceptable. Each
    # execution-level row must expose which model bill is actually missing.
    assert gaps
    assert all("component" in g or g.get("uncovered_components") for g in gaps), gaps
    serialized = json.dumps(gaps)
    assert "writer_model" in serialized and "review_model" in serialized


def test_distinct_attempt_repair_actions_do_not_collapse(results):
    first, second = results["split_gaps_a"], results["split_gaps_b"]
    assert first["receipt"]["unknown_cost_components"] != second["receipt"]["unknown_cost_components"]
    assert first["cost"]["detail"]["known_cost_by_currency"] == second["cost"]["detail"]["known_cost_by_currency"]
    assert first["cost"]["unknown"] != second["cost"]["unknown"]
