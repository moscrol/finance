"""收据的脏判定必须看见 porcelain 的**第一行**。

失败形状（2026-08-26 实测）：``_git`` 对 ``git status --porcelain`` 的整段输出做了
``.strip()``。未暂存改动行形如 ``" M path"``，整段 strip 吃掉首行那个前导空格，
随后 ``line[3:]`` 多切一个字符 → ``"ntelligence/services/…"`` → 前缀匹配失败 →
被静默丢弃。

当它是**唯一**的脏代码文件时，``dirty`` 记成 False，收据自称干净树，
``check_test_receipt.py`` 判「可采信」——正是这套收据要防的那件事。现场：judge 修复
树只改了 ``intelligence/services/llm_refine.py``，``_code_dirt()`` 返回 ``[]``。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import conftest as root_conftest


def _run(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _run(tmp_path, "init", "-q")
    _run(tmp_path, "config", "user.email", "t@example.com")
    _run(tmp_path, "config", "user.name", "t")
    (tmp_path / "intelligence" / "services").mkdir(parents=True)
    (tmp_path / "intelligence" / "services" / "alpha.py").write_text(
        "x = 1\n", encoding="utf-8"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("hi\n", encoding="utf-8")
    _run(tmp_path, "add", "-A")
    _run(tmp_path, "commit", "-qm", "init")
    return tmp_path


def test_the_only_dirty_code_file_is_not_swallowed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """唯一脏文件 = porcelain 首行 = 老实现丢掉它、dirty 变 False。"""
    (repo / "intelligence" / "services" / "alpha.py").write_text(
        "x = 2\n", encoding="utf-8"
    )
    monkeypatch.setattr(root_conftest, "REPO", repo)

    assert root_conftest._code_dirt() == ["intelligence/services/alpha.py"]
    assert bool(root_conftest._code_dirt()) is True


def test_status_lines_keep_the_leading_status_column(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """首行必须仍是 ``" M "`` 三字符前缀——这是 line[3:] 成立的前提。"""
    (repo / "intelligence" / "services" / "alpha.py").write_text(
        "x = 3\n", encoding="utf-8"
    )
    monkeypatch.setattr(root_conftest, "REPO", repo)

    lines = root_conftest._git_status_lines()

    assert lines and lines[0].startswith(" M ")
    assert lines[0][3:] == "intelligence/services/alpha.py"


def test_non_code_first_line_still_hides_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/ 排在首行时（老实现下这个洞被掩盖），代码文件照样要被列出。"""
    (repo / "docs" / "note.md").write_text("changed\n", encoding="utf-8")
    (repo / "intelligence" / "services" / "alpha.py").write_text(
        "x = 4\n", encoding="utf-8"
    )
    monkeypatch.setattr(root_conftest, "REPO", repo)

    assert root_conftest._code_dirt() == ["intelligence/services/alpha.py"]


def test_worktree_dirty_total_counts_every_line(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "docs" / "note.md").write_text("changed\n", encoding="utf-8")
    (repo / "intelligence" / "services" / "alpha.py").write_text(
        "x = 5\n", encoding="utf-8"
    )
    monkeypatch.setattr(root_conftest, "REPO", repo)

    assert len(root_conftest._git_status_lines()) == 2


def test_a_clean_tree_reports_clean(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(root_conftest, "REPO", repo)

    assert root_conftest._code_dirt() == []
    assert root_conftest._git_status_lines() == []
