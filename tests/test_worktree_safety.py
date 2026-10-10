from __future__ import annotations

import json
import os
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


def test_regenerable_caches_do_not_block_but_other_ignored_content_does():
    state = {'paths': [], 'unknown_reason': '', 'ignored': [
        '__pycache__/', 'intelligence/__pycache__/x.cpython-312.pyc', '.pytest_cache/', '.ruff_cache/',
        'intelligence/webapp/node_modules/', '.venv-workbench/', '.venv/', '.DS_Store',
        'tmp/recovery-20260921/market.duckdb', 'intelligence/users/default/workbench.sqlite3', 'evidence/',
    ]}
    blockers = safety.file_blockers(state)
    assert blockers == [
        'ignored 内容: tmp/recovery-20260921/market.duckdb',
        'ignored 内容: intelligence/users/default/workbench.sqlite3',
        'ignored 内容: evidence/',
    ]
    # 2026-09-24 dry-run 报 0 棵可删：125 棵被 __pycache__/.pytest_cache 挡住。缓存不是内容。
    assert safety.is_cache_path('a/b/__pycache__/c.pyc') and not safety.is_cache_path('a/b/cache_notes.md')


def test_launcher_pointing_at_home_itself_does_not_block_every_tree(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    tree = home / 'fwp-wt-x'
    tree.mkdir(parents=True)
    launch = home / 'Library/LaunchAgents/exec-server.plist'
    launch.parent.mkdir(parents=True)
    monkeypatch.setattr(safety.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, '', ''))
    # 2026-09-25：一份 WorkingDirectory=$HOME 的 plist 把家目录下 37 棵树全判成「被 launchd 引用」。
    # $HOME（以及 / 、/Users）不是任何一棵树的代码根。
    launch.write_bytes(plistlib.dumps({'WorkingDirectory': str(home), 'ProgramArguments': ['/bin/echo']}))
    context = safety.sample_context(timeout=1, home=home)
    assert not context['errors']
    assert not safety.context_blockers(str(tree), context)
    # 指到树本身（或树里的文件）的引用仍然算。
    launch.write_bytes(plistlib.dumps({'WorkingDirectory': str(tree)}))
    context = safety.sample_context(timeout=1, home=home)
    assert any('exec-server.plist' in b for b in safety.context_blockers(str(tree), context))


def test_reference_to_an_ancestor_does_not_block_trees_nested_below_it(tmp_path, monkeypatch):
    # 2026-10-05 dry-20261005T040409：约 40 个启动器点名主检出根（WorkingDirectory / FINANCE_WS），
    # 29 份 com.a77.ima-* 的 WorkingDirectory=/tmp（解析成 /private/tmp）；嵌在主检出 .claude/worktrees、
    # .worktrees 下和 /private/tmp 下的树因此全被判「被 launchd/启动器引用」。祖先目录不是这棵树。
    home = tmp_path / 'home'
    main = home / 'finance-workspace-private'
    private_tmp = tmp_path / 'private/tmp'
    nested = [main / '.claude/worktrees/hungry-x', main / '.worktrees/capture-quotes-0929',
              private_tmp / 'harness-opt', private_tmp / 'harness-opt/tmp/pr10-gates-1002']
    for tree in nested:
        tree.mkdir(parents=True)
    tmp_alias = tmp_path / 'tmp'
    tmp_alias.symlink_to(private_tmp, target_is_directory=True)  # 同 /tmp -> /private/tmp
    agents = home / 'Library/LaunchAgents'
    agents.mkdir(parents=True)
    (agents / 'com.financeworkspace.daily-full-review-sync.plist').write_bytes(plistlib.dumps({
        'WorkingDirectory': str(main), 'EnvironmentVariables': {'FINANCE_WS': str(main)},
        'ProgramArguments': ['/bin/sh', 'scripts/run.sh'],
    }))
    (agents / 'com.a77.ima-stock-queue-0827.plist').write_bytes(plistlib.dumps({
        'WorkingDirectory': str(tmp_alias), 'ProgramArguments': ['/bin/echo'],
    }))
    launcher = home / '.local/bin/start-finance-workbench'
    launcher.parent.mkdir(parents=True)
    launcher.write_text('#!/bin/sh\ncd "$HOME/finance-workspace-private" && exec ./serve\n')
    monkeypatch.setattr(safety.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, '', ''))
    context = safety.sample_context(timeout=1, home=home)
    assert not context['errors']
    blocked = {tree.name: safety.context_blockers(str(tree), context) for tree in nested}
    assert blocked == {tree.name: [] for tree in nested}
    # 同一批引用对它们点名的那个目录照样算：主检出根本身被 plist 和启动器挡住。
    blockers = ' | '.join(safety.context_blockers(str(main), context))
    assert 'daily-full-review-sync.plist' in blockers and 'start-finance-workbench' in blockers


def test_reference_at_or_inside_a_tree_still_blocks_it(tmp_path, monkeypatch):
    # 只放掉「祖先」这一个方向：点名树本身、指到树里的文件、经软链落到树上的引用都照挡。
    home = tmp_path / 'home'
    runtime = home / '.finance-runtime'
    sync_root, s7_root = runtime / 'finance-sync-7eec31b04b4b', runtime / 'finance-s7-sync'
    snapshot = runtime / 'finance-workspace-58d04e3780f4'
    main = home / 'finance-workspace-private'
    nested = main / '.worktrees/capture-quotes-0929'
    for tree in (sync_root, s7_root, snapshot, nested):
        tree.mkdir(parents=True)
    alias = home / 'finance-workspace-runtime'
    alias.symlink_to(snapshot, target_is_directory=True)
    agents = home / 'Library/LaunchAgents'
    agents.mkdir(parents=True)
    (agents / 'com.financeworkspace.daily-full-review-sync.plist').write_bytes(plistlib.dumps({
        'WorkingDirectory': str(sync_root)}))
    (agents / 'com.financeworkspace.nested-job.plist').write_bytes(plistlib.dumps({
        'ProgramArguments': ['/usr/bin/python3', str(nested / 'scripts/job.py')]}))
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True)
    (bin_dir / 'nightly-review-sync-staged.py').write_text(f'SCRIPT = "{s7_root}/scripts/run_review_sync.py"\n')
    (bin_dir / 'start-finance-workbench').write_text('exec "$HOME/finance-workspace-runtime/scripts/serve.sh"\n')
    monkeypatch.setattr(safety.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, '', ''))
    context = safety.sample_context(timeout=1, home=home)
    assert not context['errors']

    def blocked_by(tree):
        return ' | '.join(safety.context_blockers(str(tree), context))

    assert 'daily-full-review-sync.plist' in blocked_by(sync_root)  # 树本身
    assert 'nightly-review-sync-staged.py' in blocked_by(s7_root)  # 树里的文件
    assert 'start-finance-workbench' in blocked_by(snapshot)  # 经软链落到树里的文件
    assert str(alias) in blocked_by(snapshot)  # 软链本身指到树
    # 指进嵌套树的引用挡这棵树，也挡把它装在里面的主检出：外层目录包含它。
    assert 'nested-job.plist' in blocked_by(nested) and 'nested-job.plist' in blocked_by(main)


def test_directory_watch_handles_are_not_process_usage(tmp_path, monkeypatch):
    root = tmp_path / 'tree'
    root.mkdir()
    (root / 'sub').mkdir()
    other = tmp_path / 'other'
    other.mkdir()
    # 一个 Claude Code 会话在 ~210 棵树里持有 3000+ 个目录句柄（kqueue 文件监视器）：
    # fd 是数字、类型 DIR，不算「在用」；cwd / 普通文件句柄仍算。
    output = (
        f'p7\ncclaude\nf5\ntDIR\nn{root / "sub"}\n'
        f'p8\ncpytest\nfcwd\ntDIR\nn{other}\n'
        f'p9\ncpython\nf3\ntREG\nn{other / "x.py"}\n'
    )
    monkeypatch.setattr(safety.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, output, ''))
    context = safety.sample_context(timeout=1, home=tmp_path / 'home')
    assert not context['errors']
    assert not safety.context_blockers(str(root), context)
    blockers = safety.context_blockers(str(other), context)
    assert any('pid=8 pytest fd=cwd' in b for b in blockers)
    assert any('pid=9 python fd=3' in b for b in blockers)


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


@pytest.mark.parametrize(('text', 'expected'), [
    # 路径在闭合它所在 ${...} 的那个 } 处结束；} 后面的部分不拼回去。
    ('exec "${FINANCE_CODE_ROOT:-$HOME/finance-workspace-runtime}/scripts/serve.sh"', 'finance-workspace-runtime'),
    ('FINANCE_S7_ROOT="${FINANCE_S7_ROOT:-$HOME/.finance-runtime/finance-s7-sync}"', '.finance-runtime/finance-s7-sync'),
    ('FINANCE_WS="${FINANCE_WS:-<home>/finance-workspace-private}"', 'finance-workspace-private'),
    ('KB="${PIT_KNOWLEDGE_ROOT:-${KNOWLEDGE_WIKI:-${HOME}/knowledge-base-private}}"', 'knowledge-base-private'),
    # 后面紧跟另一个 ${...}：路径停在它前面，引号里外一样，引号里的空格照留。
    ('export PYTHONPATH="$HOME/finance-workspace-runtime${PYTHONPATH:+:$PYTHONPATH}"', 'finance-workspace-runtime'),
    ('PYTHONPATH=$HOME/finance-workspace-runtime${PYTHONPATH:+:$PYTHONPATH} exec serve', 'finance-workspace-runtime'),
    ('exec "$HOME/tree with spaces${RUN_SUFFIX:-}/bin/start"', 'tree with spaces'),
], ids=['default-then-suffix', 'default-assignment', 'absolute-home-default', 'nested-defaults',
        'quoted-then-expansion', 'bare-then-expansion', 'quoted-spaces-then-expansion'])
def test_shell_path_ends_where_its_brace_expansion_closes(text, expected, tmp_path):
    # 2026-10-05：本机 63 条启动器引用以 } 结尾（${FINANCE_RUNTIME:-$HOME/finance-workspace-runtime}
    # 采成 …/finance-workspace-runtime}），realpath 过不了软链，对不上启动器真正点名的树。
    text = text.replace('<home>', str(tmp_path))
    assert list(safety._shell_paths(text, tmp_path)) == [str(tmp_path / expected)]


def test_launcher_naming_a_tree_through_a_brace_default_blocks_it(tmp_path, monkeypatch):
    # ${VAR:-默认值} 的默认值就是变量没设时真正跑的树；夜跑与 Workbench 启动器都这么写代码根。
    home = tmp_path / 'home'
    runtime = home / '.finance-runtime'
    snapshot, s7_root = runtime / 'finance-workspace-765ecbac9ad3', runtime / 'finance-s7-sync'
    sync_root = runtime / 'finance-sync-7eec31b04b4b'
    for tree in (snapshot, s7_root, sync_root):
        tree.mkdir(parents=True)
    (home / 'finance-workspace-runtime').symlink_to(snapshot, target_is_directory=True)
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True)
    launchers = {
        'start-finance-workbench': 'exec "${FINANCE_CODE_ROOT:-$HOME/finance-workspace-runtime}/scripts/serve.sh"\n',
        'perspective-workbench': 'export PYTHONPATH="$HOME/finance-workspace-runtime${PYTHONPATH:+:$PYTHONPATH}"\n',
        'nightly-full-review-s7.sh': f'FINANCE_S7_ROOT="${{FINANCE_S7_ROOT:-{s7_root}}}"\n',
        'nightly-review-sync.sh': 'ROOT="${FINANCE_SYNC_CODE_ROOT:-${FINANCE_CODE_ROOT:-${HOME}/.finance-runtime/'
                                  'finance-sync-7eec31b04b4b}}"\n',
    }
    for name, text in launchers.items():
        (bin_dir / name).write_text(text)
    monkeypatch.setattr(safety.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, '', ''))
    context = safety.sample_context(timeout=1, home=home)
    assert not context['errors']
    assert [ref['path'] for ref in context['references'] if '{' in ref['path'] or '}' in ref['path']] == []

    def blocked_by(tree):
        return ' | '.join(safety.context_blockers(str(tree), context))

    # 运行时软链本身也挡快照，所以这里点名的是启动器，不是「有没有被挡」。
    assert 'start-finance-workbench' in blocked_by(snapshot)
    assert 'perspective-workbench' in blocked_by(snapshot)
    assert 'nightly-full-review-s7.sh' in blocked_by(s7_root)
    assert 'nightly-review-sync.sh' in blocked_by(sync_root)


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


# ---- 收口复用的只读原语（worktree_closeout.py） --------------------------------


def _repo(tmp_path, name='repo'):
    repo = tmp_path / name
    repo.mkdir()
    for args in (['init', '-q', '-b', 'main'], ['config', 'user.name', 't'],
                 ['config', 'user.email', 't@example.test'], ['config', 'commit.gpgsign', 'false']):
        subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
    return repo


def _run(repo, *args, stdin=None):
    return subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True, text=True,
                          input=stdin).stdout.strip()


def _commit(repo, name, text):
    (repo / name).write_text(text)
    _run(repo, 'add', '--', name)
    _run(repo, 'commit', '-qm', name)
    return _run(repo, 'rev-parse', 'HEAD')


def test_status_records_keep_the_leading_status_column_from_real_git(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, 'src.py', 'a\n')
    _commit(repo, 'old name.txt', 'b\n')
    (repo / 'src.py').write_text('changed\n')
    _run(repo, 'mv', 'old name.txt', 'new name.txt')
    code, raw = safety.git(['status', '--porcelain=v1', '-z'], cwd=str(repo), timeout=10)
    assert code == 0 and raw.startswith('R  new name.txt\0old name.txt\0') or ' M src.py' in raw
    records = safety.status_records(raw)
    assert ('R ', 'new name.txt', 'old name.txt') in records
    assert (' M', 'src.py', '') in records
    # 反例：strip 后首条变成 "M src.py"，一次性脚本的 rec[3:] 会静默读成 "rc.py"（两轮都踩过）；
    # 这里列位对不上就拒绝解析，不猜。
    stripped = ' M src.py\0'.strip()
    assert stripped.split('\0')[0][3:] == 'rc.py'
    with pytest.raises(ValueError):
        safety.status_records(stripped)


def test_unpushed_commits_feeds_negations_through_stdin(tmp_path):
    repo = _repo(tmp_path)
    pushed = _commit(repo, 'a.txt', 'a\n')
    head = _commit(repo, 'b.txt', 'b\n')
    assert safety.unpushed_commits(head, [pushed], cwd=str(repo), timeout=10) == 1
    assert safety.unpushed_commits(head, [head], cwd=str(repo), timeout=10) == 0
    assert safety.unpushed_commits(head, [], cwd=str(repo), timeout=10) == 2
    assert safety.unpushed_commits('f' * 40, [pushed], cwd=str(repo), timeout=10) == -1
    # 看起来等价的写法：命令行上的 --not 不否定 stdin 读进来的 sha，于是「全都没推」。
    naive = _run(repo, 'rev-list', '--count', head, '--not', '--stdin', stdin=pushed + '\n')
    assert int(naive) > 1


def test_remote_tips_counts_advertised_but_unfetched_ids(tmp_path):
    upstream = _repo(tmp_path, 'upstream')
    base = _commit(upstream, 'a.txt', 'a\n')
    clone = tmp_path / 'clone'
    subprocess.run(['git', 'clone', '-q', str(upstream), str(clone)], check=True, capture_output=True)
    _commit(upstream, 'b.txt', 'b\n')  # 远端前进了，本机没 fetch
    tips = safety.remote_tips(str(clone), 'origin', timeout=10)
    assert tips == {'shas': [], 'unknown': 1, 'error': ''}
    # base 其实在远端（是新 tip 的祖先），但本机走不到新 tip，证明不了：按「没推」算，先 fetch。
    assert safety.unpushed_commits(base, tips['shas'], cwd=str(clone), timeout=10) == 1
    _run(clone, 'fetch', '-q', 'origin')
    tips = safety.remote_tips(str(clone), 'origin', timeout=10)
    assert tips['unknown'] == 0 and safety.unpushed_commits(base, tips['shas'], cwd=str(clone), timeout=10) == 0
    assert safety.remote_tips(str(clone), 'no-such-remote', timeout=10)['error']


def test_unnamed_commits_ignore_worktree_heads(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, 'a.txt', 'a\n')
    tree = tmp_path / 'scratch'
    _run(repo, 'worktree', 'add', '-q', '--detach', str(tree), 'HEAD')
    head = _commit(tree, 'fix.txt', 'fix\n')
    assert safety.unnamed_commits(head, cwd=str(repo), timeout=10) == 1
    _run(repo, 'update-ref', 'refs/archive/wt-20260928/scratch', head)
    assert safety.unnamed_commits(head, cwd=str(repo), timeout=10) == 0
    assert safety.main(['unnamed', '--path', str(repo), '--head', head]) == 0


def test_newest_activity_names_the_file_not_its_directory(tmp_path):
    root = tmp_path / 'tree'
    (root / 'sub').mkdir(parents=True)
    (root / 'sub' / 'old.txt').write_text('old')
    (root / 'node_modules').mkdir()
    old = 946684800
    for path in (root / 'sub' / 'old.txt', root / 'sub', root / 'node_modules', root):
        os.utime(path, (old, old))
    assert safety.newest_activity(str(root), since=old + 10)[0] <= old + 10
    (root / 'node_modules' / 'cache.js').write_text('cache writes are not activity')
    os.utime(root / 'node_modules', (old, old))
    assert safety.newest_activity(str(root), since=old + 10)[0] <= old + 10
    (root / 'sub' / 'new.txt').write_text('new')
    assert safety.newest_activity(str(root), since=old + 10)[1] == 'sub/new.txt'
    (root / 'sub' / 'new.txt').unlink()
    (root / 'sub' / 'old.txt').unlink()
    assert safety.newest_activity(str(root), since=old + 10)[1] == 'sub/'


def test_code_review_graph_is_a_regenerable_cache():
    assert safety.is_cache_path('.code-review-graph/graph.db')
    assert safety.file_blockers({'paths': [], 'ignored': ['.code-review-graph/wiki/'], 'unknown_reason': ''}) == []
