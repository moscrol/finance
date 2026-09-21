"""一张 0 passed / 0 failed / exit 0 的收据不是读数，不能被采信。

失败形状（2026-09-19 实测）：`~/.finance-runtime/test-receipts/20260919T105310Z-d46c2c3b.json`
counts 全为 0、exit_status 0、干净树、revision 全等——每一项既有门都过，`check_test_receipt.py`
会打印「✅ 可采信」。它多半来自 collect-only 或一次什么都没选中的 `-k`，签的是「什么都没跑」。

- ``check_executed_counts``：passed+failed+error 为 0 即拒绝；有 failed 的红读数仍是读数。
- ``main`` 端到端：零计数收据的 blockers 里必须出现「零执行读数」，exit 1。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_test_receipt.py"
_spec = importlib.util.spec_from_file_location("check_test_receipt_zero", _SCRIPT)
ctr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctr)


@pytest.mark.parametrize(
    "counts",
    [
        {"passed": 0, "failed": 0, "error": 0, "skipped": 0},
        {"passed": 0, "failed": 0, "error": 0, "skipped": 87},  # skips alone execute nothing
        {},
        None,
    ],
)
def test_zero_executed_counts_are_not_a_reading(counts):
    ok, message = ctr.check_executed_counts(counts)
    assert not ok
    assert "零执行读数" in message


@pytest.mark.parametrize(
    "counts",
    [
        {"passed": 1, "failed": 0, "error": 0, "skipped": 0},
        {"passed": 0, "failed": 2, "error": 0, "skipped": 0},  # a red reading is still a reading
        {"passed": 0, "failed": 0, "error": 1, "skipped": 0},
        {"passed": 12259, "failed": 0, "error": 0, "skipped": 87},
    ],
)
def test_executed_counts_pass_the_gate(counts):
    ok, message = ctr.check_executed_counts(counts)
    assert ok
    assert "执行读数" in message


def test_main_blocks_zero_count_receipt_even_when_everything_else_matches(tmp_path, monkeypatch, capsys):
    receipt = {
        "revision": ctr._git("rev-parse", "HEAD") or "(unknown)",
        "interpreter": sys.executable,
        "python_version": ctr.platform.python_version(),
        "dependency_fingerprint": ctr._fingerprint(),
        "dirty": False,
        "worktree_dirty_total": 0,
        "dependency_gate_bypassed": False,
        "target": "",
        "counts": {"passed": 0, "failed": 0, "error": 0, "skipped": 0},
        "failed_ids": [],
        "exit_status": 0,
        "finished_at": "2026-09-19T10:53:10+00:00",
    }
    path = tmp_path / "20260919T105310Z-empty.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_test_receipt.py", str(path)])
    assert ctr.main() == 1
    out = capsys.readouterr().out
    assert "零执行读数" in out
    assert "✅ 可采信" not in out
