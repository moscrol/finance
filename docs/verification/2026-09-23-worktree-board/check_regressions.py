#!/usr/bin/env python3
"""Run the nine legacy counterexamples, or remove the dirty guard in memory.

No production source/worktree is modified. Exit 0 means the expected failures
were observed, not that the intentionally broken implementation passed tests.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TESTS = [
    'test_missing_worktree_is_visible_as_unknown',
    'test_parent_repository_is_not_mistaken_for_missing_worktree',
    'test_collect_rows_pins_baseline_for_entire_scan',
    'test_status_failure_never_becomes_prunable',
    'test_failed_cherry_is_unknown_in_session_start',
    'test_worktree_metadata_prevents_cleanup_suggestion',
    'test_tracked_single_character_file_keeps_porcelain_status_columns',
    'test_document_only_dirt_is_not_safe_to_remove',
]


class Probe:
    def __init__(self, source):
        self.source = source
        self.failures = 0

    def pytest_collection_modifyitems(self, items):
        module = items[0].module.board
        exec(compile(self.source, module.__file__, 'exec'), module.__dict__)

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' and report.failed:
            self.failures += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['old', 'mutation'])
    args = parser.parse_args()
    if args.mode == 'old':
        source = subprocess.check_output(
            ['git', 'show', '626d8a508:scripts/worktree_board.py'], cwd=ROOT, text=True,
        )
        tests, expected = TESTS, 9
    else:
        source = (ROOT / 'scripts/worktree_board.py').read_text()
        original = 'clean_merged_dev = [row for row in merged_dev if not row.dirty]'
        assert original in source
        source = source.replace(original, original.replace('row.dirty', 'row.code_dirty'))
        tests, expected = ['test_document_only_dirt_is_not_safe_to_remove'], 1
    probe = Probe(source)
    result = pytest.main(['-q', '-p', 'no:cacheprovider', *[
        str(ROOT / 'tests/test_worktree_board.py') + '::' + test for test in tests
    ]], plugins=[probe])
    print(f'expected_failures={expected} observed_call_failures={probe.failures} pytest_exit={result}')
    return 0 if result == 1 and probe.failures == expected else 1


if __name__ == '__main__':
    raise SystemExit(main())
