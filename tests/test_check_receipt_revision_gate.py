"""收据只自证「跑在哪棵树」，不自证「那棵树是不是要合的树」——这两个门补后半句。

失败形状（2026-08-27 工单 §P1-a，#444 实测）：分支收据 6579 passed 是真的，
但基座落后 main 27 张 PR；合并后的 main tip 上没有任何收据，批次门禁那一格是空的，
而「收据树 SHA == main tip」只是规程文字，没人执行它。

- ``--expect-revision``：收据 revision 与期望 SHA **全等**（rev-parse 展开后比较，
  防 startswith 削弱——变异测试就打这里）。
- ``--base-drift-max``：收据 revision 的合并基座落后主干超过 N 张合并即拒绝，
  分支尖收据不得冒充批次门禁。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_test_receipt.py"
_spec = importlib.util.spec_from_file_location("check_test_receipt", _SCRIPT)
ctr = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("check_test_receipt", ctr)
_spec.loader.exec_module(ctr)


def _run(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _run(tmp_path, "init", "-q", "-b", "main")
    _run(tmp_path, "config", "user.email", "t@example.com")
    _run(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.txt").write_text("1\n", encoding="utf-8")
    _run(tmp_path, "add", "-A")
    _run(tmp_path, "commit", "-qm", "c1")
    return tmp_path


def _add_merges(repo: Path, n: int) -> None:
    """在 main 上追加 n 个 merge commit（模拟 n 张 PR 合并）。"""
    for i in range(n):
        _run(repo, "checkout", "-q", "-b", f"side{i}")
        (repo / f"s{i}.txt").write_text(f"{i}\n", encoding="utf-8")
        _run(repo, "add", "-A")
        _run(repo, "commit", "-qm", f"side {i}")
        _run(repo, "checkout", "-q", "main")
        _run(repo, "merge", "--no-ff", "-q", "-m", f"merge pr {i}", f"side{i}")


def test_expect_revision_exact_match_passes(repo, monkeypatch):
    monkeypatch.setattr(ctr, "REPO", repo)
    head = _run(repo, "rev-parse", "HEAD")
    ok, _ = ctr.check_expected_revision(head, head)
    assert ok


def test_expect_revision_resolves_short_sha(repo, monkeypatch):
    """短 SHA / 引用名经 rev-parse 展开后全等比较，不是字符串前缀比较。"""
    monkeypatch.setattr(ctr, "REPO", repo)
    head = _run(repo, "rev-parse", "HEAD")
    ok, _ = ctr.check_expected_revision(head, head[:12])
    assert ok


def test_expect_revision_mismatch_reports_lag(repo, monkeypatch):
    monkeypatch.setattr(ctr, "REPO", repo)
    old = _run(repo, "rev-parse", "HEAD")
    _add_merges(repo, 3)
    new = _run(repo, "rev-parse", "HEAD")
    ok, message = ctr.check_expected_revision(old, new)
    assert not ok
    assert "3" in message  # 差额（落后 3 张合并）必须打进错误正文


def test_expect_revision_same_prefix_is_not_enough(repo, monkeypatch):
    """变异防线：比较被削成 startswith（只比前 4 位）时本用例必红。

    两个假 SHA 前 4 位相同、其余不同；rev-parse 解析不了它们，走字符串
    全等 fallback——全等语义下不通过，startswith(前4位) 语义下会误通过。
    """
    monkeypatch.setattr(ctr, "REPO", repo)
    ok, _ = ctr.check_expected_revision("abcd" + "1" * 36, "abcd" + "2" * 36)
    assert not ok


def test_base_drift_within_limit_passes(repo, monkeypatch):
    monkeypatch.setattr(ctr, "REPO", repo)
    _run(repo, "checkout", "-q", "-b", "feature")
    (repo / "f.txt").write_text("f\n", encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "feature work")
    feature = _run(repo, "rev-parse", "HEAD")
    _run(repo, "checkout", "-q", "main")
    _add_merges(repo, 2)
    ok, _ = ctr.check_base_drift(feature, "main", max_merges=5)
    assert ok


def test_base_drift_beyond_limit_fails_with_count(repo, monkeypatch):
    monkeypatch.setattr(ctr, "REPO", repo)
    _run(repo, "checkout", "-q", "-b", "feature")
    (repo / "f.txt").write_text("f\n", encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "feature work")
    feature = _run(repo, "rev-parse", "HEAD")
    _run(repo, "checkout", "-q", "main")
    _add_merges(repo, 6)
    ok, message = ctr.check_base_drift(feature, "main", max_merges=5)
    assert not ok
    assert "6" in message  # 实际漂移数必须可见


def test_base_drift_unresolvable_ref_fails_closed(repo, monkeypatch):
    """main 引用解析不了时 fail-closed（认不出来就拒绝，不降级放行）。"""
    monkeypatch.setattr(ctr, "REPO", repo)
    head = _run(repo, "rev-parse", "HEAD")
    ok, _ = ctr.check_base_drift(head, "no-such-ref", max_merges=5)
    assert not ok
