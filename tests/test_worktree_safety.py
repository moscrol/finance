from __future__ import annotations

import json
import plistlib
import subprocess
import sys

import pytest

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


def _native_plist_fixture(root):
    data = {'WorkingDirectory': str(root), 'ProgramArguments': ['/bin/echo', 'x & y']}
    # Native macOS accepts this comment; Expat rejects its double hyphen.
    return data, plistlib.dumps(data).replace(b'<dict>', b'<!-- git checkout --detach -->\n<dict>', 1)


@pytest.mark.parametrize('fmt', [plistlib.FMT_XML, plistlib.FMT_BINARY])
def test_standard_plist_needs_no_native_process(fmt, tmp_path, monkeypatch):
    value = {'WorkingDirectory': str(tmp_path)}
    monkeypatch.setattr(safety.subprocess, 'run', lambda *a, **kw: pytest.fail('unexpected process'))
    assert safety._load_launchd_plist(plistlib.dumps(value, fmt=fmt), timeout=1) == value


def test_native_fallback_preserves_launcher_blocker(tmp_path, monkeypatch):
    root = tmp_path / 'tree with spaces'
    launch = tmp_path / 'Library/LaunchAgents/native.plist'
    launch.parent.mkdir(parents=True)
    value, original = _native_plist_fixture(root)
    launch.write_bytes(original)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command[0] == 'lsof':
            return subprocess.CompletedProcess(command, 0, '', '')
        assert command == ['/usr/bin/plutil', '-convert', 'binary1', '-o', '-', '--', '-']
        assert kwargs['input'] == original and kwargs['timeout'] == 1
        assert kwargs['capture_output'] is True
        launch.write_bytes(b'changed after the read')
        return subprocess.CompletedProcess(command, 0, plistlib.dumps(value, fmt=plistlib.FMT_BINARY), b'')

    monkeypatch.setattr(safety.sys, 'platform', 'darwin')
    monkeypatch.setattr(safety.subprocess, 'run', run)
    context = safety.sample_context(timeout=1, home=tmp_path)
    assert not context['errors']
    assert any(str(launch) in item for item in safety.context_blockers(str(root), context))
    assert len(commands) == 2


@pytest.mark.parametrize('failure', ['exit', 'timeout', 'missing', 'invalid-output', 'wrong-root'])
def test_failed_native_conversion_stays_unknown(failure, tmp_path, monkeypatch):
    launch = tmp_path / 'Library/LaunchAgents/native.plist'
    launch.parent.mkdir(parents=True)
    launch.write_bytes(_native_plist_fixture(tmp_path)[1])

    def run(command, **kwargs):
        if command[0] == 'lsof':
            return subprocess.CompletedProcess(command, 0, '', '')
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        if failure == 'missing':
            raise FileNotFoundError(command[0])
        output = plistlib.dumps(['not a launchd dictionary']) if failure == 'wrong-root' else b'broken'
        return subprocess.CompletedProcess(command, int(failure == 'exit'), output, b'error')

    monkeypatch.setattr(safety.sys, 'platform', 'darwin')
    monkeypatch.setattr(safety.subprocess, 'run', run)
    context = safety.sample_context(timeout=1, home=tmp_path)
    assert len(context['errors']) == 1 and str(launch) in context['errors'][0]
    assert not context['references']


def test_invalid_plist_on_other_platform_does_not_invoke_native(tmp_path, monkeypatch):
    monkeypatch.setattr(safety.sys, 'platform', 'linux')
    monkeypatch.setattr(safety.subprocess, 'run', lambda *a, **kw: pytest.fail('unexpected process'))
    with pytest.raises(ValueError):
        safety._load_launchd_plist(b'not a plist', timeout=1)


def test_plist_root_must_be_launchd_dictionary():
    with pytest.raises(ValueError, match='dictionary'):
        safety._load_launchd_plist(plistlib.dumps(['not a launcher']), timeout=1)


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS native plist compatibility')
def test_real_native_parser_accepts_macos_plist_and_rejects_garbage(tmp_path):
    value, original = _native_plist_fixture(tmp_path)
    assert safety._load_launchd_plist(original, timeout=5) == value
    with pytest.raises(subprocess.CalledProcessError):
        safety._load_launchd_plist(b'not a plist', timeout=5)


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
