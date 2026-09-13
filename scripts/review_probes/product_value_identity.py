"""Offline probes for identity loss before/after cost coverage (round-8 QC).

Usage: python product_value_identity.py <target-worktree> <output.json>
Synthetic inputs only, no provider/production writes; measurement uses public
measure_pair -> summarize, never patched receipts. Fixture helpers build inputs.
"""
# ruff: noqa: E402 -- target checkout must precede all project imports
import copy
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from intelligence.tests.test_product_value_summarize import _r7_setup, _r7_fee
from intelligence.services.product_value.evidence import InMemoryEvidenceReader
from intelligence.services.product_value.measure import measure_pair
from intelligence.services.product_value.summarize import summarize

proto, complete, ev1, _, ev2, writer, review, base = _r7_setup()
r1 = writer['payload']['cost_item']['run_id']
a1 = writer['payload']['cost_item']['attempt_id']
r2, a2 = 'qc-extra-r2', 'qc-extra-a2'
extra = []
for e in base:
    if e['event_type'] in {'run_started', 'run_finished'}:
        e = copy.deepcopy(e)
        e['event_id'] += '-second'
        e['run_ids'] = [r2]
        e['payload'].update(run_id=r2, attempt_id=a2)
        for k in ('event_at', 'recorded_at'):
            e[k] = (datetime.fromisoformat(e[k]) + timedelta(minutes=8)).isoformat()
        extra.append(e)
run = copy.deepcopy(ev2['runs'][0])
run.update(run_id=r2, artifacts={})
for k in ('created_at', 'finished_at'):
    run[k] = (datetime.fromisoformat(run[k]) + timedelta(minutes=8)).isoformat()
runs = ev2['runs'] + [run]

def fees(rid, aid, suffix):
    return [_r7_fee(writer, c, amount, run_id=rid, attempt_id=aid, suffix=suffix)
            for c, amount in [('tool', .01), ('writer_model', .36), ('review_model', .10)]]

def report(events, supplied_runs=runs):
    reader = InMemoryEvidenceReader.from_json({'runs': ev1['runs'] + supplied_runs})
    reference = measure_pair(complete, proto, reader)
    receipt = measure_pair(events, proto, reader)
    summary = summarize([reference, receipt],
        [e for e in complete + events if e['event_type'] == 'assignment_created'],
        proto, cohort_events=complete + events, due_rechecks=[])
    metric = next(m for m in summary['metrics'] if m['metric_id'] == 'cost_full_status')
    return {'receipt': receipt, 'cost': metric, 'summary_errors': summary['input_errors']}

out = {}
out['consistent_control'] = report(base + extra + [writer, review] + fees(r2, a2, '-ok'))
out['mismatch_only_second'] = report(base + extra + [writer, review] + fees(r1, a2, '-wrong'))
# No tests or private helpers decide coverage; all variants change only input events.
out['run_only_control'] = report(base + extra + [writer, review] + [
    {**e, 'payload': {**e['payload'], 'cost_item': {**e['payload']['cost_item'], 'attempt_id': None}}}
    for e in fees(r2, a2, '-run-only')])
out['attempt_only_control'] = report(base + extra + [writer, review] + [
    {**e, 'run_ids': [], 'payload': {**e['payload'], 'cost_item': {**e['payload']['cost_item'], 'run_id': None, 'coverage_scope': 'attempt'}}}
    for e in fees(r2, a2, '-attempt-only')])
# Conflicting lifecycle identity: distinct real runs have one reused attempt id.
collapsed = copy.deepcopy(extra)
for e in collapsed:
    e['payload']['attempt_id'] = a1
out['reused_attempt_for_second_run'] = report(base + collapsed + [writer, review, _r7_fee(writer, 'tool', .01)])
# Same mistake, opposite direction: run_started claims r1, run_finished claims r2.
changed_finish = copy.deepcopy(base)
for e in changed_finish:
    if e['event_type'] == 'run_finished':
        e['payload']['run_id'] = r2
        e['run_ids'] = [r2]
out['started_finished_run_mismatch'] = report(changed_finish + [writer, review, _r7_fee(writer, 'tool', .01)])

Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=2))
for label, result in out.items():
    receipt = result['receipt']
    print(json.dumps({'case': label, 'receipt_status': receipt['status'],
        'attempts': [(a['attempt_id'], a['run_id'], a['evidence_status']) for a in receipt['tasks']['assisted']['attempts']],
        'receipt_unknown': receipt['unknown_cost_components'], 'receipt_known': receipt['known_cost_by_currency'],
        'invalid': receipt['invalid_reasons'], 'rejected': receipt['event_accounting']['rejected'],
        'full_cost_status': result['cost']['detail']['full_cost_status'],
        'summary_known': result['cost']['detail']['known_cost_by_currency'], 'summary_unknown': result['cost']['unknown']}, ensure_ascii=False))
