"""Explicit QC checks; known defects are not in default pytest collection.

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
    output = tmp_path_factory.mktemp("selection") / "result.json"
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("product_value_selection.py")), os.environ["QC_TREE"], str(output)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(output.read_text())


def assert_accepted(result):
    assert result["receipt"]["invalid_reasons"] == []
    assert result["receipt"]["event_accounting"]["rejected"] == []
    assert result["summary_errors"] == []


@pytest.mark.parametrize("case", ["consistent_coarse_with_fine", "fine_only_control", "all_components_control"])
def test_legitimate_cost_controls(results, case):
    result = results[case]
    assert_accepted(result)
    assert result["receipt"]["status"] == "valid"
    assert result["receipt"]["unknown_cost_components"] == []
    assert result["cost"]["detail"]["full_cost_status"] == "known"
    assert result["cost"]["detail"]["known_cost_by_currency"] == {"CNY": 1.39}


def test_original_joint_identity_fix_remains_effective(results):
    result = results["mismatch_without_fine"]
    assert_accepted(result)
    assert result["receipt"]["status"] == "incomplete"
    assert any(g["reason"] == "no_usage_evidence_for_attempt" for g in result["receipt"]["unknown_cost_components"])


def test_unselected_fine_bills_cannot_clear_receipt_gap(results):
    result = results["mismatch_with_unselected_fine"]
    assert_accepted(result)
    assert result["cost"]["detail"]["full_cost_status"] == "unknown"
    assert any(i["selected"] is False and i["attempt_id"] == "qc-selection-attempt2"
               for i in result["receipt"]["cost_items"])
    assert result["receipt"]["status"] == "incomplete"
    assert any(g["reason"] == "no_usage_evidence_for_attempt" for g in result["receipt"]["unknown_cost_components"])


@pytest.mark.parametrize("case", ["second_tool_only", "second_writer_tool"])
def test_component_gaps_are_visible_in_receipt_not_only_summary(results, case):
    result = results[case]
    assert_accepted(result)
    assert result["cost"]["detail"]["full_cost_status"] == "unknown"
    assert result["receipt"]["status"] == "incomplete"
    gaps = result["receipt"]["unknown_cost_components"]
    assert gaps
    serialized = json.dumps(gaps)
    assert "review_model" in serialized
    if case == "second_tool_only":
        assert "writer_model" in serialized
