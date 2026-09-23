"""交接预算门禁的判据矩阵：``scripts/check_handoff_budget.py``。

为什么建真 git 仓而不是 mock ``git``：门禁的判据全部取自版本控制事实（暂存区 blob
大小 vs ``HEAD`` blob 大小），把 ``subprocess`` mock 掉之后测的就只剩「我写的 if 分支
会不会执行」，而真正会错的地方——``git cat-file -s`` 的取值对象、暂存区与工作区的
区别——一条都压不到。``git init`` 在 tmp_path 里约 30ms，不值得为此换成假的。

写这组用例时踩到的坑（留作后人参考）：清理用 ``git checkout -- .`` 会从**索引**恢复
工作区。如果上一条用例已经 ``git add`` 过超标内容，它"恢复"的正是那份脏数据，于是
后续用例全部假红。清理必须是 ``git reset --hard HEAD``。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parents[1] / "scripts" / "check_handoff_budget.py"
INFLIGHT = "docs/handoffs/inflight"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _write(repo: Path, rel: str, size: int) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x" * size, encoding="utf-8")


def _run_gate(repo: Path) -> int:
    return subprocess.run(
        ["python3", str(repo / "scripts" / "check_handoff_budget.py")],
        cwd=repo,
        capture_output=True,
        text=True,
    ).returncode


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """一个带存量的仓：10000 字节的超标交接 + 2000 字节的合规交接，均已进 HEAD。"""

    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "config", "user.email", "gate@test")
    _git(tmp_path, "config", "user.name", "gate")
    (tmp_path / "scripts").mkdir()
    shutil.copy(GATE, tmp_path / "scripts" / GATE.name)
    _write(tmp_path, f"{INFLIGHT}/legacy.md", 10_000)
    _write(tmp_path, f"{INFLIGHT}/small.md", 2_000)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def test_new_oversized_handoff_is_blocked(repo: Path) -> None:
    _write(repo, f"{INFLIGHT}/new-big.md", 3_500)
    _git(repo, "add", "-A")
    assert _run_gate(repo) == 1


def test_new_handoff_within_budget_passes(repo: Path) -> None:
    _write(repo, f"{INFLIGHT}/new-ok.md", 2_900)
    _git(repo, "add", "-A")
    assert _run_gate(repo) == 0


def test_legacy_oversized_may_be_edited_when_not_growing(repo: Path) -> None:
    """棘轮的核心：存量 53 份超标交接必须还能改，否则门禁会被 --no-verify 绕死。"""

    _write(repo, f"{INFLIGHT}/legacy.md", 9_999)
    _git(repo, "add", "-A")
    assert _run_gate(repo) == 0


def test_legacy_oversized_growing_is_blocked(repo: Path) -> None:
    _write(repo, f"{INFLIGHT}/legacy.md", 10_001)
    _git(repo, "add", "-A")
    assert _run_gate(repo) == 1


def test_growth_within_budget_passes(repo: Path) -> None:
    _write(repo, f"{INFLIGHT}/small.md", 2_500)
    _git(repo, "add", "-A")
    assert _run_gate(repo) == 0


def test_commit_without_inflight_changes_is_skipped(repo: Path) -> None:
    _write(repo, "docs/other/x.md", 50_000)
    _git(repo, "add", "-A")
    assert _run_gate(repo) == 0


def test_mixed_commit_blocks_on_the_offender(repo: Path) -> None:
    """一红一绿同批提交时不得被合规的那份稀释——按文件判，不按批次判。"""

    _write(repo, f"{INFLIGHT}/new-big.md", 3_500)
    _write(repo, f"{INFLIGHT}/new-ok.md", 1_000)
    _git(repo, "add", "-A")
    assert _run_gate(repo) == 1


def test_deleting_an_oversized_handoff_is_allowed(repo: Path) -> None:
    """归档已合并的交接是规约要求的动作，门禁不能拦住它。"""

    _git(repo, "rm", "-q", f"{INFLIGHT}/legacy.md")
    assert _run_gate(repo) == 0
