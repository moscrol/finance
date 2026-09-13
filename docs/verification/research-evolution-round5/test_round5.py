"""Safety assertions for round-5 independent QC; four are red on the pinned candidates."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent


@pytest.fixture(scope="module")
def results():
    return {track: json.loads(subprocess.check_output([sys.executable, str(BASE / "probe_round5.py"), track], text=True))["probes"] for track in ("01", "05")}


def test_j8_condition_observation_cannot_cross_cutoff_by_offset_spelling(results):
    p = results["01"]["condition_known_market_day"]
    assert p["known_control"]["items"][0]["condition"] == "true"
    assert p["market"]["items"][0]["condition"] == "unknown"
    assert p["utc"]["items"][0]["condition"] == "unknown", p


def test_j9_binding_cannot_be_effective_before_market_created_day(results):
    p = results["01"]["binding_created_market_day"]
    assert p["market"]["counts"]["objects_bound"] == 0
    assert p["utc"]["counts"]["objects_bound"] == 0, p


def test_j10_ambiguity_transition_must_survive_report_item_dedup(results):
    p = results["01"]["ambiguity_transition_item_identity"]
    assert p["before"]["counts"]["items_open"] == 1
    assert p["after"]["counts"]["items_open"] == 1, p
    assert "ambiguous_version_order" in p["after"]["gaps"], p


def test_pv9_other_component_fee_does_not_cover_missing_model_fees(results):
    p = results["05"]["unrelated_task_fee_covers_models"]
    for v in p.values():
        assert v["receipt"]["invalid_reasons"] == []
        assert v["receipt"]["event_accounting"]["rejected"] == []
        assert v["receipt"]["tasks"]["assisted"]["attempts"] == []
    assert p["before"]["cost"]["detail"]["full_cost_status"] == "unknown"
    assert p["all_components_control"]["cost"]["detail"]["full_cost_status"] == "known"
    assert p["tool_only"]["cost"]["detail"]["full_cost_status"] == "unknown", p["tool_only"]["cost"]
    assert p["writer_and_tool_only"]["cost"]["detail"]["full_cost_status"] == "unknown", p["writer_and_tool_only"]["cost"]


def test_pv9_complete_task_costs_remain_legal(results):
    p = results["05"]["unrelated_task_fee_covers_models"]["all_components_control"]
    assert p["receipt"]["event_accounting"]["rejected"] == []
    assert p["cost"]["detail"]["full_cost_status"] == "known"
    assert p["cost"]["detail"]["known_cost_by_currency"] == {"CNY": 0.93}
