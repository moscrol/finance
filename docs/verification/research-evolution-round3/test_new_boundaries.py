"""Expected safety properties; these five tests intentionally expose unresolved defects."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent

@pytest.fixture(scope="module")
def results():
    return {track: json.loads(subprocess.check_output([sys.executable, str(BASE / "probe_new_boundaries.py"), track], text=True))['probes'] for track in ('01', '04', '05')}


def test_j4_same_instant_offset_cannot_change_retirement(results):
    data = results['01']['mixed_offset_correction']
    assert data['actual'] == data['same_instant_normalized'], data


def test_j5_equal_timestamps_preserve_ambiguous_version_gap(results):
    actual = results['01']['equal_time_distinct_hash']['actual']
    assert 'ambiguous_version_order' in actual['gaps'], actual


def test_d5_later_current_hash_does_not_discharge_unknown_time(results):
    data = results['04']['later_reinstatement_masks_missing_time']
    assert data['fill_early']['classification'] == 'issue'
    assert data['fill_late']['classification'] == 'context'
    assert data['actual']['classification'] == 'unknown', data['actual']


def test_pv6_abandonment_is_not_cost_coverage(results):
    data = results['05']['terminal_without_cost_evidence']
    for source, variant in data.items():
        assert variant['receipt_status'] == 'incomplete'
        assert variant['receipt_cost_items'] == []
        assert variant['receipt_unknown'] == []
        actual = variant['with_receipt']['detail']
        assert actual['full_cost_status'] == 'unknown', (source, actual)


def test_pv7_future_window_preserves_activated_mature_denominator(results):
    data = results['05']['future_window_removes_task_started_cohort']
    assert data['before']['metric']['denominator_ids'] == [f'q{i}' for i in range(1, 7)]
    assert data['after']['metric']['denominator_ids'] == data['before']['metric']['denominator_ids'], data['after']
    assert data['after']['criterion']['verdict'] == 'unknown'
