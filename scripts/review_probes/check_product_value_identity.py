"""Explicit QC safety assertions; not part of default pytest collection.

QC_TREE=<target-worktree> python -m pytest -q <this-file>
3 failures on f8540a53 are expected defects, not xfail/acceptance allowances.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent

@pytest.fixture(scope='module')
def results(tmp_path_factory):
    output = tmp_path_factory.mktemp('identity') / 'result.json'
    subprocess.run([sys.executable, str(BASE / 'product_value_identity.py'), os.environ['QC_TREE'], str(output)], check=True, capture_output=True, text=True)
    return json.loads(output.read_text())

@pytest.mark.parametrize('case', ['consistent_control', 'run_only_control', 'attempt_only_control'])
def test_legal_identities_remain_known(results, case):
    r = results[case]
    assert r['receipt']['invalid_reasons'] == []
    assert r['receipt']['event_accounting']['rejected'] == []
    assert r['summary_errors'] == []
    assert len(r['receipt']['tasks']['assisted']['attempts']) == 2
    assert r['cost']['detail']['full_cost_status'] == 'known'
    assert r['cost']['detail']['known_cost_by_currency'] == {'CNY': 1.39}

def test_original_round8_summary_fix(results):
    r = results['mismatch_only_second']
    assert r['cost']['detail']['full_cost_status'] == 'unknown'
    gap = next(g for g in r['cost']['unknown'] if g['id'].startswith('unmeasured_task:'))
    assert gap['uncovered_components'] == ['review_model', 'writer_model']

def test_receipt_cannot_claim_complete_billing_for_mismatched_identity(results):
    r = results['mismatch_only_second']['receipt']
    assert r['status'] != 'valid', r
    assert r['unknown_cost_components'] or r['invalid_reasons']

@pytest.mark.parametrize('case', ['reused_attempt_for_second_run', 'started_finished_run_mismatch'])
def test_conflicting_attempt_run_identity_cannot_silently_drop_a_run(results, case):
    r = results[case]
    assert r['cost']['detail']['full_cost_status'] == 'unknown', r['cost']
    receipt = r['receipt']
    assert (receipt['invalid_reasons'] or receipt['event_accounting']['rejected']
            or receipt['limitations'] or len(receipt['tasks']['assisted']['attempts']) == 2)
