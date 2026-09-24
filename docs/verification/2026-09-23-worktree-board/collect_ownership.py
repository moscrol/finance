#!/usr/bin/env python3
"""Read-only inventory of the twelve preserved ownership review trees."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.worktree_board import parse_worktree_porcelain  # noqa: E402

# Provenance pointers, not deletion permits; arena identities are in evidence/README.md.
EVIDENCE = {
    'arena-gates': 'arena-main-ready-20260921',
    'arena-gates-v2': 'arena-main-ready-v2-20260921',
    'closeout': 'ownership-closeout-20260921',
    'gates': 'ownership-followup-20260921',
    'gates-v2': 'ownership-followup-recheck-20260921',
    'gates-v3': 'ownership-resume-20260921',
    'gates-v4': 'ownership-integration-v4-20260921',
    'quality-v3': 'ownership-k3-v3-20260921/quality-k3',
    'quality-v4': 'ownership-k3-v4-20260921/quality-k3',
    'resume-review': 'ownership-resume-20260921',
    'spec-v3': 'ownership-k3-v3-20260921/spec-k3',
    'spec-v4': 'ownership-k3-v4-20260921/spec-k3',
}


def git(*args, cwd=ROOT):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True,
                          text=True, timeout=30, check=True).stdout.rstrip('\n')


def main():
    base = git('rev-parse', 'gitea/main')
    rows = []
    for spec in parse_worktree_porcelain(git('worktree', 'list', '--porcelain')):
        name = Path(spec['path']).name
        if not (name.startswith('fwp-wt-ownership-') and name.endswith('-0921')):
            continue
        key = name.removeprefix('fwp-wt-ownership-').removesuffix('-0921')
        status = git('status', '--porcelain=v1', '--untracked-files=all', cwd=spec['path'])
        head = git('rev-parse', 'HEAD', cwd=spec['path'])
        anchors = git('for-each-ref', '--format=%(refname:short)', '--points-at', head,
                      'refs/heads/baseline/ownership-*').splitlines()
        evidence = EVIDENCE.get(key)
        evidence_path = str(Path.home() / '.finance-runtime/reviews' / evidence) if evidence else None
        ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', head, base],
                                  cwd=ROOT, timeout=30, check=False).returncode
        rows.append({**spec, 'observed_head': head, 'head_matches_registration': head == spec['head'],
                     'status': status.splitlines(), 'baseline_anchors_at_head': anchors,
                     'ancestor_exit': ancestor, 'evidence_directory': evidence_path,
                     'evidence_exists': Path(evidence_path).is_dir() if evidence_path else None,
                     'disposition': 'KEEP: dirty review tree; #64 authorization required',
                     'evidence_note': '' if evidence else 'Arena evidence directory not established; retain tree'})
    print(json.dumps({'sampled_at': datetime.now(timezone.utc).isoformat(),
                      'base_sha': base, 'trees': rows}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
