"""Safety assertions over real public pure-function outputs, with legal controls."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent


@pytest.fixture(scope="module")
def results():
    return {
        track: json.loads(subprocess.check_output([sys.executable, str(BASE / "probe_round6.py"), track], text=True))["probes"]
        for track in ("01", "05")
    }


def test_j11_market_day_baseline_must_accept_equivalent_utc_stamp(results):
    p = results["01"]["binding_validation_market_day"]
    assert p["2026-09-12T00:30:00+08:00"]["accepted"]
    assert p["2026-09-11T16:30:00Z"]["accepted"], p


def test_j11_future_baseline_must_reject_even_if_offset_prefix_matches(results):
    p = results["01"]["binding_validation_market_day"]
    assert not p["2026-09-11T18:30:00+08:00"]["accepted"]
    assert not p["2026-09-12T00:30:00+14:00"]["accepted"], p


def test_j12_resolution_preserves_an_acyclic_supersedes_chain(results):
    p = results["01"]["resolution_supersedes_cycle"]
    assert p["report"]["counts"]["items_open"] == 1
    assert "ambiguous_version_order" in p["report"]["gaps"]
    assert p["cycles"] == [], p


def test_pv10_run_tool_fee_cannot_cover_writer_and_review(results):
    p = results["05"]["run_component_coverage"]["tool_only"]
    assert p["receipt"]["invalid_reasons"] == []
    assert p["receipt"]["event_accounting"]["rejected"] == []
    assert p["receipt"]["tasks"]["assisted"]["attempts"][0]["evidence_status"] == "ok"
    assert p["cost"]["detail"]["full_cost_status"] == "unknown", p["cost"]


def test_pv10_run_writer_fee_cannot_cover_review(results):
    p = results["05"]["run_component_coverage"]["writer_tool"]
    assert p["receipt"]["invalid_reasons"] == []
    assert p["receipt"]["event_accounting"]["rejected"] == []
    assert p["cost"]["detail"]["full_cost_status"] == "unknown", p["cost"]


def test_pv10_complete_run_bills_and_no_fee_controls(results):
    p = results["05"]["run_component_coverage"]
    assert p["no_fees"]["cost"]["detail"]["full_cost_status"] == "unknown"
    assert p["all_components"]["cost"]["detail"]["full_cost_status"] == "known"
    assert p["all_components"]["cost"]["detail"]["known_cost_by_currency"] == {"CNY": 0.93}
