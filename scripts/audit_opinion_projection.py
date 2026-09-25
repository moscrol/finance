#!/usr/bin/env python3
"""Probe reviewed opinion consumers without certifying deployment or semantic truth.

The receipt binds source hashes, an immutable review batch, and input fingerprints.
Exit zero means the probe ran; it never means the river is ready. --out is exclusive
creation so an earlier receipt cannot be silently replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.services.catalyst_attribution import attribute_theme, build_catalyst_index  # noqa: E402
from intelligence.services.event_pricing.narrative import load_opinion_events as pricing_load  # noqa: E402
from intelligence.services.opinion_events import STORE_RELPATH, load_events, read_batches, utc_now  # noqa: E402
from intelligence.services.teaching_framework.narrative import load_opinion_events as teaching_load  # noqa: E402
from intelligence.services.workbench_overview import _load_sellside  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(wiki: Path, batch_id: str, dates: list[str]) -> dict:
    store = wiki / STORE_RELPATH
    before = sha256(store)
    batches = read_batches(store)
    batch = next(b for b in batches if b['batch_id'] == batch_id)
    ids = {c['event_id'] for c in batch['corrections']}
    results = {}
    for cutoff in dates:
        warnings: list[str] = []
        rows = load_events(wiki, as_of=cutoff, warnings=warnings)
        preview = load_events(wiki, as_of=cutoff, allow_inferred=True)
        catalyst = build_catalyst_index(wiki, cutoff, window_days=40)
        overview_warnings: list[str] = []
        winrate, flow, latest = _load_sellside(wiki, as_of=cutoff, warnings=overview_warnings)
        teaching_warnings: list[str] = []
        teaching = teaching_load(wiki, as_of=cutoff, warnings=teaching_warnings)
        pricing, gaps = pricing_load(wiki, str(STORE_RELPATH), as_of=cutoff)
        results[cutoff] = {
            'eligible_batch_ids': [r['event_id'] for r in rows if r['event_id'] in ids],
            'warnings': warnings,
            'inferred_preview': [{k: r.get(k) for k in (
                'event_id', 'revision_id', 'concept', 'date_status', 'evidence_layer', 'recorded_at',
            )} for r in preview if r['event_id'] in ids],
            'catalyst': {
                'batch_ids': [r['event_id'] for r in catalyst.opinion_events if r['event_id'] in ids],
                'warnings': catalyst.warnings,
                'diamond_status': attribute_theme(catalyst, '金刚石散热', ['九州一轨', '国机精工'])['status'],
            },
            'workbench': {'latest_date': latest, 'flow': flow, 'winrate_rows': len(winrate), 'warnings': overview_warnings},
            'teaching': {'batch_ids': [r['event_id'] for r in teaching if r['event_id'] in ids], 'warnings': teaching_warnings},
            'event_pricing': {
                'batch_ids': [r.event_id for r in pricing if r.event_id.rsplit(':', 1)[-1] in ids],
                'gaps': [{'reason': g.reason, 'detail': g.detail} for g in gaps],
            },
        }
    after = sha256(store)
    if before != after:
        raise RuntimeError('input ledger changed during probe; receipt is invalid')
    paths = [
        'intelligence/services/opinion_events.py', 'intelligence/services/catalyst_attribution.py',
        'intelligence/services/workbench_overview.py', 'intelligence/services/teaching_framework/narrative.py',
        'intelligence/services/event_pricing/narrative.py', 'intelligence/services/event_pricing/event_calendar.py',
        'scripts/teaching_framework.py', 'scripts/review_opinion_events.py', 'scripts/prepare_miracle_review.py',
        'scripts/audit_opinion_projection.py',
    ]
    return {
        'audited_at': utc_now(), 'scope': 'branch read-only consumers; not deployment or strict full-chain PIT',
        'verdict': 'REVIEW_REQUIRED', 'merge_ready': False, 'deployed': False,
        'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'code_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).splitlines(),
        'source_hashes': {p: sha256(ROOT / p) for p in paths},
        'ledger_sha256': before, 'ledger_unchanged_during_probe': before == after,
        'correction_files': {p.name: sha256(p) for p in sorted((store.parent / 'corrections').glob('*.json'))},
        'batch_id': batch_id, 'recorded_at': batch['recorded_at'],
        'actions': dict(Counter(c['action'] for c in batch['corrections'])), 'probes': results,
        'boundaries': [
            'river still consumes fact_research_report_catalog, not this projection',
            'pricing and teaching aggregates are ex-post research, not historical open-time knowledge',
            'morning briefing and opinion-cross staging/outcomes writers are outside this migration',
            'quarantine is pending review, not proof that every row is false',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wiki', required=True, type=Path)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--as-of', required=True, action='append')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    receipt = probe(args.wiki, args.batch_id, args.as_of)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({'receipt': str(args.out), 'actions': receipt['actions'], 'verdict': receipt['verdict']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
