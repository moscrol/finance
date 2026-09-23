from __future__ import annotations

import json
import plistlib
import subprocess

from scripts import worktree_safety as safety


def test_read_only_git_disables_optional_index_locks(tmp_path, monkeypatch):
    from scripts import worktree_board as board

    environments = []

    def run(*args, **kwargs):
        environments.append(kwargs['env'])
        return subprocess.CompletedProcess([], 0, ' M x\n', '')

    monkeypatch.setattr(subprocess, 'run', run)
    for runner in (safety.git, board._git):
        assert runner(['status', '--porcelain'], cwd=str(tmp_path), timeout=1) == (0, ' M x')
    assert all(env['GIT_OPTIONAL_LOCKS'] == '0' for env in environments)


def test_status_paths_preserve_rename_and_unusual_names():
    dirty, ignored = safety.status_paths(' M x\0?? dir/a -> b\0R  new name\0old name\0!! evidence/\0')
    assert dirty == ['x', 'dir/a -> b', 'new name']
    assert ignored == ['evidence/']


def test_context_retains_pid_plist_and_runtime_link(tmp_path, monkeypatch):
    root = tmp_path / 'tree with spaces'
    root.mkdir()
    home = tmp_path / 'home'
    launch = home / 'Library/LaunchAgents/job.plist'
    launch.parent.mkdir(parents=True)
    alias = home / 'finance-workspace-runtime'
    alias.symlink_to(root, target_is_directory=True)
    launch.write_bytes(plistlib.dumps({'WorkingDirectory': str(alias)}, fmt=plistlib.FMT_BINARY))
    monkeypatch.setattr(safety.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
        [], 0, f'p42\nctest\nfcwd\nn{root}\n', '',
    ))
    context = safety.sample_context(timeout=1, home=home)
    assert not context['errors']
    blockers = safety.context_blockers(str(root), context)
    assert any('pid=42 test fd=cwd' in b for b in blockers)
    assert any(str(launch) in b for b in blockers)
    assert any(str(alias) in b for b in blockers)
    assert not safety.context_blockers(str(tmp_path / 'tree with spaces-other'), context)


def test_malformed_xml_and_lsof_timeout_are_unknown(tmp_path, monkeypatch):
    launch = tmp_path / 'Library/LaunchAgents/broken.plist'
    launch.parent.mkdir(parents=True)
    launch.write_text('<?xml version="1.0"?><plist><string>x & y</string></plist>')

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('lsof', 1)

    monkeypatch.setattr(safety.subprocess, 'run', timeout)
    context = safety.sample_context(timeout=1, home=tmp_path)
    assert any('lsof' in error for error in context['errors'])
    assert any(str(launch) in error for error in context['errors'])


def test_shell_reference_with_spaces_and_home_expansion(tmp_path):
    text = 'exec "$HOME/tree with spaces/bin/start" ${HOME}/other/bin/start'
    assert list(safety._shell_paths(text, tmp_path)) == [
        str(tmp_path / 'tree with spaces/bin/start'), str(tmp_path / 'other/bin/start'),
    ]


def test_cli_and_board_consume_same_blockers(tmp_path, monkeypatch, capsys):
    from scripts import worktree_board as board

    path = str(tmp_path)
    state = {'paths': ['notes.md'], 'ignored': ['evidence/'], 'unknown_reason': ''}
    context = {'references': [
        {'kind': 'process', 'path': path, 'source': 'pid=42 worker fd=cwd'},
        {'kind': 'launcher', 'path': path, 'source': str(tmp_path / 'Library/LaunchAgents/job.plist')},
    ], 'errors': []}
    snapshot = tmp_path / 'context.json'
    snapshot.write_text(json.dumps(context))
    monkeypatch.setattr(safety, 'inspect_tree', lambda *a, **kw: state)
    monkeypatch.setattr(board, 'cherry_counts', lambda *a, **kw: (0, 0, True))
    monkeypatch.setattr(board, '_count', lambda *a, **kw: 0)
    row = board.classify_worktree({'path': path, 'head': 'a'*40}, base='main',
                                  main_checkout=path, timeout=1, context=context)
    assert safety.main(['check', '--path', path, '--context', str(snapshot)]) == 0
    cleanup_blockers = capsys.readouterr().out
    assert all(blocker in cleanup_blockers for blocker in row.blockers)
    assert 'notes.md' in cleanup_blockers and 'pid=42' in cleanup_blockers
    text = board.format_board([row], base='main', base_sha='a'*40)
    assert 'job.plist' in text


def test_failed_cherry_still_reports_dirty_files(tmp_path, monkeypatch):
    from scripts import worktree_board as board

    monkeypatch.setattr(safety, 'inspect_tree', lambda *a, **kw: {
        'paths': ['notes.md'], 'ignored': [], 'unknown_reason': '',
    })
    monkeypatch.setattr(board, 'cherry_counts', lambda *a, **kw: (-1, -1, False))
    monkeypatch.setattr(board, '_count', lambda *a, **kw: -1)
    row = board.classify_worktree({'path': str(tmp_path), 'head': 'a'*40}, base='main',
                                  main_checkout=str(tmp_path), timeout=1,
                                  context={'references': [], 'errors': []})
    assert row.unknown_reason and row.dirty
    assert '未提交: notes.md' in row.blockers
    assert 'unknown_reason:' in board.format_board([row], base='main', base_sha='a'*40)
