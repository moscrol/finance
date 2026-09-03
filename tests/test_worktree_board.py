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
    assert board.resolve_ledger_path(worktree) == ledger


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
    assert lines[-1].startswith("看板:")


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
    assert "树可拆" in text
    assert "本脚本不拆" in text
