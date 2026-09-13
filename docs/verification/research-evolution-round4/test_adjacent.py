"""Safety properties for the round-4 review; intentionally red on candidates."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent

@pytest.fixture(scope="module")
def results():
    return {t: json.loads(subprocess.check_output([sys.executable, str(BASE / "probe_adjacent.py"), t], text=True))["probes"] for t in ("01", "05")}


def test_j6_cross_midnight_representation_cannot_change_cutoff(results):
    probe = results["01"]["cross_midnight_representation"]
    assert probe["actual"] == probe["same_instant_normalized"], probe


def test_j7_incomparable_times_must_keep_ambiguity(results):
    probe = results["01"]["incomparable_precision"]
    assert probe["fill_early"]["counts"]["items_open"] == 1
    assert probe["fill_late"]["counts"]["items_open"] == 0
    assert "ambiguous_version_order" in probe["actual"]["gaps"], probe


def test_j5_baseline_sorting_last_must_not_hide_equal_time_gap(results):
    probe = results["01"]["tie_baseline_sorts_last"]
    assert "ambiguous_version_order" in probe["other_hash_sorts_last"]["gaps"]
    assert "ambiguous_version_order" in probe["actual"]["gaps"], probe


def test_pv8_elapsed_time_is_not_assisted_cost_coverage(results):
    probe = results["05"]["timed_assisted_without_usage"]
    assert probe["assisted_task"]["attempts"] == []
    assert probe["assisted_task"]["timing"]["end_to_end_minutes"] == 20
    assert probe["cost_items"] == []
    assert probe["before"]["detail"]["full_cost_status"] == "unknown"
    assert probe["after"]["detail"]["known_cost_by_currency"] == {"CNY": 0.46}
    assert probe["after"]["detail"]["full_cost_status"] == "unknown", probe["after"]
