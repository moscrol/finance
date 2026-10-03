"""CLI negative controls finish before importing any product/model runtime."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/preflight_model_harness_conversation.py'


def invoke(tmp_path, *, db_state='missing', question='offline fixture', model='glm-5.3-flash', existing=False):
    data = tmp_path / 'data'
    db = data / 'db/market_feature_store.duckdb'
    if db_state != 'missing':
        db.parent.mkdir(parents=True)
        # The command must reject these inputs before it tries to open this non-database.
        db.write_bytes(b'not a real database')
        db.chmod(0o444 if db_state == 'readonly' else 0o644)
    case = tmp_path / 'case.json'
    case.write_text(json.dumps({'question': question}))
    output = tmp_path / 'output'
    if existing:
        output.mkdir()
        (output / 'sentinel').write_text('do not overwrite')
    proc = subprocess.run([sys.executable, str(SCRIPT), '--output', str(output),
                           '--data-root', str(data), '--case-json', str(case), '--model', model],
                          capture_output=True, text=True, timeout=10)
    return proc, output


@pytest.mark.parametrize('db_state', ['missing', 'writable'])
def test_requires_readonly_snapshot_before_any_runtime(tmp_path, db_state):
    proc, output = invoke(tmp_path, db_state=db_state)
    assert proc.returncode != 0
    assert 'read-only frozen market database' in proc.stderr
    assert not output.exists()


@pytest.mark.parametrize('question', ['', '   ', None])
def test_empty_case_cannot_start_runtime(tmp_path, question):
    proc, output = invoke(tmp_path, db_state='readonly', question=question)
    assert proc.returncode != 0
    assert 'question missing' in proc.stderr
    assert not output.exists()


def test_unknown_model_not_silently_replaced(tmp_path):
    proc, output = invoke(tmp_path, model='unregistered-model')
    assert proc.returncode == 2
    assert not output.exists()


def test_previous_probe_is_never_overwritten(tmp_path):
    proc, output = invoke(tmp_path, db_state='readonly', existing=True)
    assert proc.returncode != 0
    assert 'FileExistsError' in proc.stderr
    assert (output / 'sentinel').read_text() == 'do not overwrite'
    assert sorted(p.name for p in output.iterdir()) == ['sentinel']


@pytest.mark.parametrize('command', [
    ['git', 'checkout', '--', 'status'],
    ['git', 'reset', '--hard', 'log'],
    ['git', 'log', '--output=/tmp/preflight-output'],
    ['git', '-c', 'core.pager=touch /tmp/preflight-output', 'status'],
    ['git', 'diff', '--ext-diff'],
    ['/tmp/git', 'status', '--porcelain'],
    'git status --porcelain',
])
def test_git_guard_rejects_safe_words_inside_unsafe_commands(command):
    from scripts.preflight_model_harness_conversation import read_only_git_command
    assert not read_only_git_command(command)


def test_git_guard_only_allows_exact_provenance_reads():
    from scripts.preflight_model_harness_conversation import read_only_git_command
    assert read_only_git_command(['git', '-C', '/repo', 'rev-parse', 'HEAD'])
    assert read_only_git_command(['git', 'status', '--porcelain'])
    assert not read_only_git_command(['git', 'status', '--porcelain'], shell=True)
