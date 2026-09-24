"""reconcile_hithink_gate 的故障回归（十三轮 P1）：异常路径必须 fail-closed 且留结构化证据。

两处被审查真实复现过的洞：
- git status 失败（rc=128、stdout 为空，如索引损坏）曾被误读成「工作树干净」
  而整体放行；
- --output-base 指向普通文件时，报告兜底写回同一失败路径，最终只有
  traceback、没有结构化 FAIL 报告。
"""
from __future__ import annotations

import importlib
import json
import sys

import pytest

from scripts import reconcile_hithink_gate as gate


@pytest.fixture()
def mod():
    """每例重载模块，隔离 checks/inputs/RUN/OUT_BASE 全局状态。"""
    return importlib.reload(gate)


def test_git_status_failure_is_fail_closed_not_clean(mod, monkeypatch, tmp_path):
    out_base = tmp_path / "out"
    out_base.mkdir()
    real_run = mod.subprocess.run

    def fake_run(cmd, **kwargs):
        if list(cmd)[:2] == ["git", "status"]:
            return mod.subprocess.CompletedProcess(cmd, 128, "", "fatal: index file corrupt")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys, "argv",
        ["gate", "--expect-revision", "0" * 40, "--output-base", str(out_base)],
    )
    with pytest.raises(SystemExit) as exc:
        mod.run_gate()
    assert exc.value.code == 1
    git_checks = [c for c in mod.checks if c["name"] == "git_invocation"]
    assert len(git_checks) == 1 and git_checks[0]["ok"] is False
    assert git_checks[0]["detail"]["rc"] == 128
    assert "git" in git_checks[0]["detail"]["command"][0]
    assert not any(c["name"] == "tree_clean" and c["ok"] for c in mod.checks)
    reports = list(out_base.glob("gate-FAIL-*.json"))
    assert len(reports) == 1
    doc = json.loads(reports[0].read_text(encoding="utf-8"))
    assert doc["verdict"] == "FAIL" and doc["failed"] == ["git_invocation"]


def test_output_base_collision_still_leaves_structured_fail(mod, monkeypatch, tmp_path):
    collision = tmp_path / "plain-file"
    collision.write_text("review fixture", encoding="utf-8")
    fallback_dir = tmp_path / "independent-temp"
    fallback_dir.mkdir()
    monkeypatch.setattr(mod.tempfile, "mkdtemp", lambda **_kw: str(fallback_dir))
    monkeypatch.setattr(
        sys, "argv",
        ["gate", "--expect-revision", "0" * 40, "--output-base", str(collision)],
    )
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    assert any(c["name"] == "unhandled_exception" and c["ok"] is False
               for c in mod.checks)
    doc = json.loads((fallback_dir / "gate-report.json").read_text(encoding="utf-8"))
    assert doc["verdict"] == "FAIL" and "unhandled_exception" in doc["failed"]


def test_finalize_fallback_chain_skips_broken_targets(mod, monkeypatch, tmp_path):
    mod.OUT_BASE = tmp_path / "not-a-directory"
    mod.OUT_BASE.write_text("x", encoding="utf-8")
    mod.RUN = None
    mod.check("forced_failure", False, "injected")
    fallback_dir = tmp_path / "fb"
    fallback_dir.mkdir()
    monkeypatch.setattr(mod.tempfile, "mkdtemp", lambda **_kw: str(fallback_dir))
    with pytest.raises(SystemExit) as exc:
        mod.finalize(1)
    assert exc.value.code == 1
    doc = json.loads((fallback_dir / "gate-report.json").read_text(encoding="utf-8"))
    assert doc["verdict"] == "FAIL" and doc["failed"] == ["forced_failure"]


def test_finalize_writes_into_run_dir_on_success(mod, tmp_path):
    mod.RUN = tmp_path
    mod.OUT_BASE = None
    mod.inputs.update({"trade_date": "2026-09-11"})
    mod.check("ok_check", True, "fine")
    with pytest.raises(SystemExit) as exc:
        mod.finalize(0)
    assert exc.value.code == 0
    doc = json.loads((tmp_path / "gate-report.json").read_text(encoding="utf-8"))
    assert doc["verdict"] == "PASS" and doc["failed"] == []
