from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worktree_board.py"
_spec = importlib.util.spec_from_file_location("worktree_board_under_test", _SCRIPT)
assert _spec and _spec.loader
board = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = board
_spec.loader.exec_module(board)


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _init_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "board@example.test")
    _git(repo, "config", "user.name", "board")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "base")
    return repo


def test_parse_worktree_porcelain() -> None:
    text = (
        "worktree /tmp/a\nHEAD abc\nbranch refs/heads/feat/x\n\n"
        "worktree /tmp/b\nHEAD def\ndetached\n"
    )
    rows = board.parse_worktree_porcelain(text)
    assert rows[0]["branch"] == "feat/x"
    assert rows[1]["branch"] == "(detached)"


def test_code_dirty_skips_exports() -> None:
    assert board.is_code_dirty(["market_feature_store/exports/x.json"]) is False
    assert board.is_code_dirty(["intelligence/services/foo.py"]) is True


def test_tree_kind_uses_path_shape_not_home_literal(tmp_path: Path) -> None:
    main = str(tmp_path / "main")
    assert (
        board.tree_kind(
            str(tmp_path / ".finance-runtime" / "finance-workspace-deadbeef"),
            main,
        )
        == "prod-snapshot"
    )
    assert board.tree_kind(str(tmp_path / "fwp-wt-topic"), main) == "dev-wt"


def test_cherry_equivalent_patch_is_in_main(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "topic")
    (repo / "feature.txt").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "feature.txt")
    _git(repo, "commit", "-m", "feature")
    _git(repo, "checkout", "main")
    (repo / "other.txt").write_text("unrelated\n", encoding="utf-8")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-m", "unrelated")
    _git(repo, "cherry-pick", "topic")
    plus, minus, in_main = board.cherry_counts(
        _git(repo, "rev-parse", "topic"),
        "main",
        cwd=str(repo),
        timeout=10,
    )
    assert plus == 0
    assert minus == 1
    assert in_main is True


def test_unique_commit_is_cherry_plus(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "topic")
    (repo / "feature.txt").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "feature.txt")
    _git(repo, "commit", "-m", "feature")
    plus, minus, in_main = board.cherry_counts(
        _git(repo, "rev-parse", "HEAD"),
        "main",
        cwd=str(repo),
        timeout=10,
    )
    assert plus == 1
    assert minus == 0
    assert in_main is False


def test_ledger_falls_back_to_git_common_dir_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main = tmp_path / "main"
    worktree = tmp_path / "wt"
    (main / "state").mkdir(parents=True)
    worktree.mkdir()
    ledger = main / "state" / "deploy-ledger.jsonl"
    ledger.write_text(
        json.dumps({"action": "switch", "rev": "dddddddddddd", "port": 8792}) + "\n",
        encoding="utf-8",
    )

    def fake_git(args: list[str], *, cwd: str | None, timeout: float) -> tuple[int, str]:
        if args[:1] == ["rev-parse"] and "--git-common-dir" in args:
            return 0, str(main / ".git")
        return 1, ""

    monkeypatch.delenv("FINANCE_DEPLOY_LEDGER", raising=False)
    monkeypatch.delenv("FINANCE_WS", raising=False)
    monkeypatch.setattr(board, "_git", fake_git)
    # 密封：宿主 ~/.finance-runtime 真账本有带 unix 的 8792 切换，会盖过这份夹具
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    assert board.resolve_ledger_path(worktree) == ledger


def _write_ledger(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _no_common_dir(args: list[str], *, cwd: str | None, timeout: float) -> tuple[int, str]:
    return 1, ""


def test_ledger_picks_the_home_with_the_freshest_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """两份账本都在：主树 state/ 停在一天前的切换，~/.finance-runtime 记着之后两次。

    2026-09-08 实测形状：按覆盖序取第一份会把 8792 报成 b594a5e7，生产其实已是
    0060da5c。读取侧要在存在的候选里取该 port 末次 switch 最新的那份。
    """

    repo = tmp_path / "repo"
    home = tmp_path / "home"
    stale = _write_ledger(
        repo / "state" / "deploy-ledger.jsonl",
        [
            {"action": "switch", "rev": "b594a5e7f8ae", "port": 8792, "unix": 1788770530.6},
            # 更晚的行，但不是 8792 的 switch：不能让它把这份账本抬成「最新」
            {"action": "startup", "rev": "2431da494ad4", "port": 8799, "unix": 1788805233.7},
        ],
    )
    fresh = _write_ledger(
        home / ".finance-runtime" / "deploy-ledger.jsonl",
        [
            {"action": "switch", "rev": "b594a5e7f8ae", "port": 8792, "unix": 1788770530.6},
            {"action": "switch", "rev": "af370f529681", "port": 8792, "unix": 1788798729.5},
            {"action": "switch", "rev": "0060da5c1a08", "port": 8792, "unix": 1788804095.0},
        ],
    )
    monkeypatch.delenv("FINANCE_DEPLOY_LEDGER", raising=False)
    monkeypatch.delenv("FINANCE_WS", raising=False)
    monkeypatch.setattr(board, "_git", _no_common_dir)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert board.resolve_ledger_path(repo) == fresh
    assert board.last_switch_for_port(fresh, port=8792)[0]["rev"] == "0060da5c1a08"
    # 反向：主树那份更新时仍取主树，说明是按时刻不是按位置
    _write_ledger(
        stale,
        [{"action": "switch", "rev": "eeeeeeeeeeee", "port": 8792, "unix": 1788900000.0}],
    )
    assert board.resolve_ledger_path(repo) == stale


def test_ledger_prefers_the_single_home_when_no_switch_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """都没有该 port 的 switch 行（或旧格式没写 unix）时，唯一家 ``~/.finance-runtime`` 优先——
    它是写入侧唯一的目标（工单 #44）；旧家 ``<repo>/state`` 只在它有更新的 8792 切换时才赢。"""

    repo = tmp_path / "repo"
    home = tmp_path / "home"
    legacy = _write_ledger(
        repo / "state" / "deploy-ledger.jsonl",
        [{"action": "startup", "rev": "aaaaaaaaaaaa", "port": 8792}],
    )
    single_home = _write_ledger(
        home / ".finance-runtime" / "deploy-ledger.jsonl",
        [{"action": "switch", "rev": "cccccccccccc", "port": 8796, "unix": 1788900000.0}],
    )
    monkeypatch.delenv("FINANCE_DEPLOY_LEDGER", raising=False)
    monkeypatch.delenv("FINANCE_WS", raising=False)
    monkeypatch.setattr(board, "_git", _no_common_dir)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert board.resolve_ledger_path(repo) == single_home
    # FINANCE_WS 指向的 state/ 只是旧家之一：没有更新的 8792 切换就不抢
    monkeypatch.setenv("FINANCE_WS", str(repo))
    assert board.resolve_ledger_path(repo) == single_home
    # 旧家有更新的 8792 切换时仍按时刻取它（#675 的读法不退）
    _write_ledger(
        legacy,
        [{"action": "switch", "rev": "eeeeeeeeeeee", "port": 8792, "unix": 1788900001.0}],
    )
    assert board.resolve_ledger_path(repo) == legacy
    # 什么都没有时也回唯一家（写入侧会建它）
    legacy.unlink()
    single_home.unlink()
    assert board.resolve_ledger_path(repo) == single_home


def test_last_switch_prefers_port_8792(tmp_path: Path) -> None:
    ledger = tmp_path / "deploy-ledger.jsonl"
    rows = [
        {"action": "switch", "rev": "aaaaaaa1", "port": 8796},
        {"action": "startup", "rev": "bbbbbbbb", "port": 8792},
        {"action": "switch", "rev": "ccccccc3", "port": 8792},
    ]
    ledger.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    found, unattributed = board.last_switch_for_port(ledger, port=8792)
    assert found is not None
    assert found["rev"] == "ccccccc3"
    assert unattributed is None


def test_newer_switch_without_port_is_not_masked_by_older_matched_row(
    tmp_path: Path,
) -> None:
    """现场形状：09-03 那次切换按规程跑、规程没带 --port，账本落了无 port 的行。

    旧实现返回更旧的 c88c81da（末次带 port 的行），看板每个会话都把它当作
    8792 现状报出来。判据是「不许把旧 rev 当真值报」，不是「必须报新 rev」——
    账本确实无从归属。
    """

    ledger = tmp_path / "deploy-ledger.jsonl"
    rows = [
        {"action": "switch", "rev": "c88c81da5120", "port": 8792},
        {"action": "switch", "rev": "f4c03b9ae610"},  # 规程漏了 --port
    ]
    ledger.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    found, unattributed = board.last_switch_for_port(ledger, port=8792)
    assert unattributed is not None
    assert unattributed["rev"] == "f4c03b9ae610"
    assert found is not None and found["rev"] == "c88c81da5120"


def test_unattributed_switch_is_not_credited_to_another_port(tmp_path: Path) -> None:
    """未归属行不许被「取最新」归给随便哪个 port。

    真账本里 8796 末次 switch 之后同样跟着未归属行；把「最新那条」直接当答案，
    会把 8792 的 rev 报成 8796 的现状。
    """

    ledger = tmp_path / "deploy-ledger.jsonl"
    rows = [
        {"action": "switch", "rev": "76ee1e89ed8a", "port": 8796},
        {"action": "switch", "rev": "f4c03b9ae610"},
    ]
    ledger.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    found, unattributed = board.last_switch_for_port(ledger, port=8796)
    assert found is not None and found["rev"] == "76ee1e89ed8a"
    assert unattributed is not None and unattributed["rev"] == "f4c03b9ae610"


def test_board_line_declines_to_assert_when_newest_switch_lacks_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init_repo(tmp_path)
    ledger = repo / "state" / "deploy-ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "".join(
            json.dumps(row) + "\n"
            for row in (
                {"action": "switch", "rev": "c88c81da5120", "port": 8792},
                {"action": "switch", "rev": "f4c03b9ae610"},
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    sha = _git(repo, "rev-parse", "HEAD")
    lines = board.this_tree_lines(
        cwd=str(repo), base="main", base_sha=sha, timeout=10, repo_root=repo
    )
    port_line = next(line for line in lines if line.startswith("8792:"))
    assert "判不出" in port_line
    assert "f4c03b9ae610" in port_line
    # 关键：不能把更旧的 rev 摆成 8792 的现状读数
    assert not port_line.startswith("8792: c88c81da5120")


def test_this_tree_lines_when_already_on_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.delenv("FINANCE_DEPLOY_LEDGER", raising=False)
    monkeypatch.delenv("FINANCE_WS", raising=False)
    sha = _git(repo, "rev-parse", "HEAD")
    lines = board.this_tree_lines(
        cwd=str(repo),
        base="main",
        base_sha=sha,
        timeout=10,
        repo_root=repo,
    )
    assert lines[0].startswith("合入: 本枝补丁已在 main=")
    assert "落后" not in lines[0]
    assert lines[-1].startswith("看板:")


def _behind_repo(tmp_path: Path, n: int) -> Path:
    """建一棵「补丁都在 main、但底落后 n 提交」的树。

    这是本修复唯一要拦的形状：``cherry+0`` 与 ``behind>0`` 同时成立。拿生产
    快照复制一棵证明不了任何事 —— 必须专门造出只有这条分支会拒的那一棵。
    """

    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "topic")
    for i in range(n):
        (repo / f"m{i}.txt").write_text(f"{i}\n", encoding="utf-8")
        _git(repo, "add", f"m{i}.txt")
        _git(repo, "commit", "-m", f"main-only {i}")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--ff-only", "topic")
    # 回到落后的那棵：HEAD 停在 base，main 已前进 n 笔，且 HEAD 无独有补丁。
    _git(repo, "checkout", "-B", "stale", "HEAD~" + str(n) if n else "HEAD")
    return repo


def _this_lines(repo: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.chdir(repo)
    monkeypatch.delenv("FINANCE_DEPLOY_LEDGER", raising=False)
    monkeypatch.delenv("FINANCE_WS", raising=False)
    return board.this_tree_lines(
        cwd=str(repo),
        base="main",
        base_sha=_git(repo, "rev-parse", "main"),
        timeout=10,
        repo_root=repo,
    )


def test_this_tree_lines_reports_behind_even_when_cherry_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cherry+0 不等于「一切正常」：底旧必须同时报出来。"""

    repo = _behind_repo(tmp_path, 3)
    monkeypatch.setattr(board, "STALE_BASE_WARN", 50)
    lines = _this_lines(repo, monkeypatch)
    assert "cherry+0" in lines[0], lines[0]
    assert "底落后 3 提交" in lines[0], lines[0]
    # 没过阈值：报数字，不喊。喊多了 agent 会学会忽略。
    assert "⚠" not in lines[0], lines[0]


def test_this_tree_lines_warns_once_base_drift_passes_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _behind_repo(tmp_path, 3)
    monkeypatch.setattr(board, "STALE_BASE_WARN", 3)
    lines = _this_lines(repo, monkeypatch)
    assert "底落后 3 提交" in lines[0], lines[0]
    assert "⚠" in lines[0], lines[0]
    # 后果要写出来，否则读的人不知道这条事实该改变什么行为。
    assert "我们没有" in lines[0], lines[0]


def test_stale_base_warn_is_a_usable_threshold() -> None:
    """取 0 会每次会话都喊（工作树按构造天天落后），取太大等于没装。"""

    assert 10 <= board.STALE_BASE_WARN <= 200


def test_count_treats_non_numeric_output_as_unknown(tmp_path: Path) -> None:
    """git 把话写到 stdout 时不能抛；失败必须保留为未知，不能冒充 0。"""

    repo = _init_repo(tmp_path)
    assert (
        board.behind_count("HEAD", "no/such/ref", cwd=str(repo), timeout=10) == -1
    )
    assert board._count(["rev-parse", "HEAD"], cwd=str(repo), timeout=10) == -1


def test_format_board_splits_unique_and_prunable() -> None:
    unique = board.TreeRow(
        path="/tmp/fwp-wt-open",
        head="aaaaaaaaaaaa",
        branch="feat/open",
        cherry_plus=2,
        cherry_minus=0,
        ahead=2,
        behind=3,
        in_main=False,
        dirty=False,
        code_dirty=False,
        dirty_n=0,
        kind="dev-wt",
        subjects=("deadbeef feat: leftover",),
    )
    done = board.TreeRow(
        path="/tmp/fwp-wt-done",
        head="bbbbbbbbbbbb",
        branch="feat/done",
        cherry_plus=0,
        cherry_minus=1,
        ahead=1,
        behind=0,
        in_main=True,
        dirty=False,
        code_dirty=False,
        dirty_n=0,
        kind="dev-wt",
        subjects=(),
    )
    text = board.format_board([unique, done], base="gitea/main", base_sha="c" * 40)
    assert "feat/open" in text
    assert "feat/done" in text
    assert "还有补丁" in text
    assert "不是删除许可" in text
    assert "cleanup_gate_trees.sh" in text
    assert "树可拆" not in text


def _classify(repo: Path, **metadata: str):
    return board.classify_worktree(
        {"path": str(repo), "head": _git(repo, "rev-parse", "HEAD"),
         "branch": "main", **metadata},
        base="main", main_checkout=str(repo.parent / "other"), timeout=10,
    )


def test_missing_worktree_is_visible_as_unknown(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    row = board.classify_worktree(
        {"path": str(tmp_path / "fwp-wt-missing"),
         "head": _git(repo, "rev-parse", "HEAD"), "branch": "topic"},
        base="main", main_checkout=str(repo), timeout=10,
    )
    assert row is not None
    assert row.error and row.unknown_reason
    assert row.cherry_plus == -1
    text = board.format_board([row], base="main", base_sha="a" * 40)
    assert "待核实 1" in text
    assert "fwp-wt-missing" in text
    assert "干净 dev 树 0" in text


def test_parent_repository_is_not_mistaken_for_missing_worktree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    nested = repo / "fwp-wt-nested"
    nested.mkdir()
    row = board.classify_worktree(
        {"path": str(nested), "head": _git(repo, "rev-parse", "HEAD"), "branch": "topic"},
        base="main", main_checkout=str(repo), timeout=10,
    )
    assert row is not None
    assert "root mismatch" in row.error
    assert row.cherry_plus == -1 and not row.in_main
    assert row.ahead == row.behind == -1


def test_collect_rows_pins_baseline_for_entire_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _init_repo(tmp_path)
    expected = _git(repo, "rev-parse", "main")
    seen: list[str] = []

    def classify(spec, **kwargs):
        seen.append(kwargs["base"])
        return None

    monkeypatch.setattr(board, "classify_worktree", classify)
    monkeypatch.setattr(board.safety, "sample_context", lambda **kw: {"references": [], "errors": []})
    base, sha, _, rows = board.collect_rows(cwd=str(repo), timeout=10)
    assert base == "main" and sha == expected
    assert seen == [expected] and rows == []


def test_status_failure_never_becomes_prunable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _init_repo(tmp_path)
    original_git = board._git

    def fail_status(args, **kwargs):
        return (1, "") if args[0] == "status" else original_git(args, **kwargs)

    monkeypatch.setattr(board, "_git", fail_status)
    row = _classify(repo)
    assert "dirty state unknown" in row.error
    assert "待核实 1" in board.format_board([row], base="main", base_sha="a" * 40)


def test_failed_cherry_is_unknown_in_session_start(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert board.cherry_counts("HEAD", "missing", cwd=str(repo), timeout=10) == (-1, -1, False)
    lines = board.this_tree_lines(
        cwd=str(repo), base="missing", base_sha="", timeout=10, repo_root=repo,
    )
    assert "未知" in lines[0]
    assert "cherry+0" not in lines[0]


@pytest.mark.parametrize("metadata", [{"locked": "review"}, {"prunable": "missing gitdir"}])
def test_worktree_metadata_prevents_cleanup_suggestion(tmp_path: Path, metadata) -> None:
    repo = _init_repo(tmp_path)
    text = "worktree " + str(repo) + "\nHEAD abc\n"
    text += "\n".join(f"{key} {value}" for key, value in metadata.items())
    spec = board.parse_worktree_porcelain(text)[0]
    for key, value in metadata.items():
        assert spec[key] == value
    row = _classify(repo, **metadata)
    text = board.format_board([row], base="main", base_sha="a" * 40)
    assert "待核实 1" in text
    assert row.blockers


def test_tracked_single_character_file_keeps_porcelain_status_columns(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "x").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "x")
    _git(repo, "commit", "-m", "short filename")
    (repo / "x").write_text("uncommitted original\n", encoding="utf-8")
    code, status = board._git(["status", "--porcelain"], cwd=str(repo), timeout=10)
    assert code == 0 and status == " M x"
    row = _classify(repo)
    assert row.dirty and row.dirty_n == 1
    assert "未提交: x" in row.blockers


def test_document_only_dirt_is_not_safe_to_remove(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    wt = tmp_path / "fwp-wt-docs"
    _git(repo, "worktree", "add", "-b", "docs", str(wt))
    (wt / "notes.md").write_text("uncommitted original\n", encoding="utf-8")
    row = _classify(wt)
    assert row.in_main and row.dirty and not row.code_dirty
    text = board.format_board([row], base="main", base_sha="a" * 40)
    assert "干净 dev 树 0" in text
    assert "还有未提交文件" in text
    assert str(wt) not in text.split("【补丁已在基线且 Git 干净")[1].split("【")[0]


def test_ahead_query_failure_remains_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path)
    original_git = board._git

    def fail_count(args, **kwargs):
        return (1, "") if args[0] == "rev-list" else original_git(args, **kwargs)

    monkeypatch.setattr(board, "_git", fail_count)
    row = _classify(repo)
    assert row.ahead == row.behind == -1
    assert row.error
    assert "待核实 1" in board.format_board([row], base="main", base_sha="a" * 40)
    assert "底落后量未知" in board.this_tree_lines(
        cwd=str(repo), base="main", base_sha=_git(repo, "rev-parse", "main"),
        timeout=10, repo_root=repo,
    )[0]


def test_session_start_pins_baseline_sha(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    sha = _git(repo, "rev-parse", "HEAD")
    lines = board.this_tree_lines(
        cwd=str(repo), base="moved/ref", base_sha=sha,
        timeout=10, repo_root=repo,
    )
    assert "cherry+0" in lines[0]
    assert "未知" not in lines[0]


@pytest.mark.parametrize("mode", ["no-main", "base-failed", "list-failed", "common-failed"])
def test_global_scan_failure_is_not_empty_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str,
) -> None:
    repo = _init_repo(tmp_path)
    monkeypatch.chdir(repo)
    original_git = board._git
    if mode == "no-main":
        _git(repo, "branch", "-m", "topic")
    else:
        monkeypatch.setattr(board, "resolve_base", lambda cwd, timeout: "main")

    def fail(args, **kwargs):
        if mode == "base-failed" and args == ["rev-parse", "main"]:
            return 1, ""
        if mode == "list-failed" and args[:2] == ["worktree", "list"]:
            return 1, ""
        if mode == "common-failed" and "--git-common-dir" in args:
            return 1, ""
        return original_git(args, **kwargs)

    monkeypatch.setattr(board, "_git", fail)
    assert board.main(["--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["error"] and data["trees"] is None
    if mode == "no-main":
        assert board.main(["--this"]) == 1
        assert "不回退 HEAD" in capsys.readouterr().out


def test_json_includes_concrete_blockers(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path)
    (repo / "notes.md").write_text("preserve")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(board.safety, "sample_context", lambda **kw: {
        "references": [{"kind": "process", "path": str(repo.resolve()), "source": "pid=42 fd=cwd"}],
        "errors": [],
    })
    assert board.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["base_sha"] == _git(repo, "rev-parse", "HEAD")
    assert len(payload["trees"]) == 1
    row = payload["trees"][0]
    assert row["unknown_reason"] == ""
    assert isinstance(row["blockers"], list)
    assert "未提交: notes.md" in row["blockers"]
    assert any("pid=42" in blocker for blocker in row["blockers"])


# ---- 内容落地比例（--landed） ------------------------------------------------

_LANDED_LINES = [
    "def settle(order):",
    "    total = sum(item.price for item in order.items)",
    "    return round(total * (1 - order.discount), 2)",
    "LIMIT_PER_ORDER = 5000",
]


def _commit_files(repo: Path, message: str, files: dict[str, str]) -> str:
    for rel, text in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    _git(repo, "add", "--", *files)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _topic_with_code(repo: Path) -> str:
    _commit_files(repo, "app", {"app.py": "import os\n"})
    _git(repo, "checkout", "-q", "-b", "topic")
    topic = _commit_files(repo, "topic", {
        # 短行（<=12 字符）与注释行不计；docs/ 与 .md 整个文件不计。
        "app.py": "import os\n" + "\n".join(_LANDED_LINES) + "\nx = 1\n# a comment that is long enough\n",
        "docs/notes.md": "a long documentation line that never counts\n",
    })
    _git(repo, "checkout", "-q", "main")
    return topic


def test_landed_ratio_sees_a_squashed_successor_that_cherry_misses(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    topic = _topic_with_code(repo)
    # 接替 PR：同样的代码换了上下文、夹着别的改动 squash 成一个提交，patch-id 全变。
    _commit_files(repo, "successor", {
        "app.py": "import os\nimport sys\n\n" + "\n".join(_LANDED_LINES) + "\n\nprint(sys.argv)\n",
        "other.py": "VALUE = 'unrelated change in the same squash'\n",
    })
    plus, _minus, in_main = board.cherry_counts(topic, "main", cwd=str(repo), timeout=10)
    assert plus == 1 and in_main is False
    landed = board.landed_ratio(topic, "main", cwd=str(repo), timeout=10)
    assert (landed.added, landed.found, landed.pct, landed.files, landed.error) == (4, 4, 100, 1, "")
    assert board.format_landed(landed) == "100%(4/4)"


def test_landed_ratio_counts_partial_landing_per_file(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    topic = _topic_with_code(repo)
    _commit_files(repo, "half", {
        "app.py": "import os\n" + "\n".join(_LANDED_LINES[:2]) + "\n",
        # 同一行落在别的文件里不算：逐文件比，样板行才不会把比例抬虚。
        "elsewhere.py": "\n".join(_LANDED_LINES[2:]) + "\n",
    })
    landed = board.landed_ratio(topic, "main", cwd=str(repo), timeout=10)
    assert (landed.added, landed.found, landed.pct) == (4, 2, 50)


def test_landed_ratio_of_a_docs_only_branch_is_not_zero_percent(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "docs")
    head = _commit_files(repo, "docs", {"docs/plan.md": "a plan that is long enough\n",
                                        "data/table.csv": "a,b,c,d,e,f,g,h\n"})
    landed = board.landed_ratio(head, "main", cwd=str(repo), timeout=10)
    assert (landed.added, landed.pct, landed.files) == (0, -1, 0)
    assert board.format_landed(landed).startswith("-")


def test_landed_ratio_failure_is_unknown_not_zero(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    landed = board.landed_ratio("f" * 40, "main", cwd=str(repo), timeout=10)
    assert landed.error and landed.pct == -1
    assert board.format_landed(landed).startswith("?")


def test_added_code_lines_skips_headers_comments_and_short_lines() -> None:
    diff = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,0 +2,4 @@\n"
        "+    value = compute_the_total(order)\n+x = 1\n+  // a long js comment line\n"
        '+    """docstring opener line"""\n+* bullet continuation line\n'
    )
    assert board.added_code_lines(diff) == ["value = compute_the_total(order)"]


def test_board_prints_landed_ratio_only_when_measured() -> None:
    row = board.TreeRow(
        path="/tmp/fwp-wt-open", head="a" * 12, branch="feat/open", cherry_plus=2, cherry_minus=0,
        ahead=2, behind=0, in_main=False, dirty=False, code_dirty=False, dirty_n=0, kind="dev-wt",
        landed=board.Landed(added=34, found=33, pct=97, files=3),
    )
    text = board.format_board([row], base="gitea/main", base_sha="c" * 40)
    assert "landed:97%(33/34)" in text
    assert "≥90% 1 条" in text and "不是删除许可" in text
    plain = board.format_board([board.TreeRow(**{**row.__dict__, "landed": None})],
                               base="gitea/main", base_sha="c" * 40)
    assert "landed:" not in plain and "内容落地" not in plain
    assert "worktree_closeout.py" in plain


def test_json_row_carries_landed_fields() -> None:
    from dataclasses import asdict

    row = board.TreeRow(
        path="/tmp/x", head="a" * 12, branch="b", cherry_plus=1, cherry_minus=0, ahead=1, behind=0,
        in_main=False, dirty=False, code_dirty=False, dirty_n=0, kind="dev-wt",
        landed=board.Landed(added=2, found=1, pct=50, files=1),
    )
    assert asdict(row)["landed"] == {"added": 2, "found": 1, "pct": 50, "files": 1, "error": ""}


# ---- 锁理由的 C 风格引号 ------------------------------------------------------


def test_chinese_lock_reason_is_unquoted(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    tree = tmp_path / "rehearsal"
    _git(repo, "worktree", "add", "-q", "--detach", str(tree), "HEAD")
    _git(repo, "worktree", "lock", "--reason", "留待授权部署 \"retain\"", str(tree))
    porcelain = _git(repo, "-c", "core.quotePath=true", "worktree", "list", "--porcelain")
    assert "\\347" in porcelain  # 默认设置下 git 真的把它写成了八进制
    [_main, locked] = board.parse_worktree_porcelain(porcelain)
    assert locked["locked"] == '留待授权部署 "retain"'


def test_unquote_c_leaves_plain_values_alone() -> None:
    assert board.unquote_c("retain for deployment") == "retain for deployment"
    assert board.unquote_c('"a\\tb\\\\c"') == "a\tb\\c"
    assert board.unquote_c('"') == '"'
