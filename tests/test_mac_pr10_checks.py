"""Mac 侧核验串联脚本：各步独立、坏一步不拖累后面，摘要只有计数和判定、不带台账正文。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import duckdb
import pytest

from market_feature_store import db as mfs_db

from tests.test_numeric_gate_label_ab import OLD_ROW, RESTATEMENT, _write_receipt

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("mac_pr10_checks", REPO / "scripts" / "mac_pr10_checks.py")
runbook = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("mac_pr10_checks", runbook)
_SPEC.loader.exec_module(runbook)

SECRET = "这条纠偏正文不许出现在摘要里"


def _users(tmp_path: Path) -> Path:
    root = tmp_path / "users"
    _write_receipt(root, RESTATEMENT, OLD_ROW, user="linxiaoqi5111", run="run_20260920_100000_000001")
    (root / "linxiaoqi5111" / "corrections.jsonl").write_text(
        json.dumps({"ts": "2026-06-29T09:43:06+00:00", "correction": SECRET, "themes": ["裕太微"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    return root


def test_runbook_writes_a_shareable_summary_without_private_text(tmp_path, monkeypatch, capsys):
    users = _users(tmp_path)
    db = tmp_path / "mfs.duckdb"
    duckdb.connect(str(db)).close()
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users))
    out = tmp_path / "out"
    assert runbook.main(["--db", str(db), "--out", str(out)]) == 0
    summary = (out / "summary.md").read_text(encoding="utf-8")
    for title in ("换库锁平台自检", "百分数字段量纲", "标签 A/B 回放", "生效模型准入抽查", "记忆召回分档", "工具调用按数据集", "台账体检"):
        assert f"## {title}" in summary, title
    assert "消失 1 处，新增 0 处" in summary
    assert "未出分：记忆标注不可用" in summary
    assert "| T1 |" not in summary  # 缺失标注不能冒充召回分数
    assert "各按自己 configure 里配置的模型" in summary
    assert SECRET not in summary
    assert "若强势股成交占比回到" not in summary, "回答原句只进本机日志"
    assert "若强势股成交占比回到" in (out / "logs" / "03-replay.txt").read_text(encoding="utf-8")
    assert "可以贴回来" in capsys.readouterr().out


def test_recall_summary_keeps_table_for_complete_labels(tmp_path):
    from intelligence.eval.retrieval_recall import load_cases

    cases = load_cases(REPO / "intelligence/eval/cases/retrieval_recall_v1.jsonl", channel="user_memory")
    user = tmp_path / "users" / "fixture"
    user.mkdir(parents=True)
    labels = sorted({identity for case in cases for identity in case["relevant"]})
    (user / "corrections.jsonl").write_text("\n".join(
        json.dumps({"ts": ts, "correction": SECRET, "themes": ["裕太微"]}, ensure_ascii=False)
        for ts in labels
    ), encoding="utf-8")
    (tmp_path / "out" / "logs").mkdir(parents=True)
    result, lines = runbook.step_recall(tmp_path / "out", user.parent, user.name, [])
    assert result["exit"] == 0
    assert "| T1 |" in "\n".join(lines)
    assert SECRET not in "\n".join(lines)


@pytest.mark.parametrize("stdout", [
    json.dumps({"status": "memory_retrieval_unavailable", "error": SECRET}),
    SECRET,
    json.dumps([SECRET]),
])
def test_recall_failure_summary_never_exposes_private_diagnostics(tmp_path, monkeypatch, stdout):
    monkeypatch.setattr(runbook, "_run", lambda *a: {"exit": 2, "stdout": stdout})
    result, lines = runbook.step_recall(tmp_path, tmp_path / "users", "fixture", [])
    assert result["exit"] == 2
    assert "未出分" in "\n".join(lines)
    assert SECRET not in "\n".join(lines)


def test_runbook_refuses_without_users_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("FORESIGHT_USERS_DIR", raising=False)
    assert runbook.main(["--out", str(tmp_path / "out")]) == 2


def test_a_failing_step_does_not_stop_the_rest(tmp_path, monkeypatch):
    users = _users(tmp_path)
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users))

    def boom(out):
        raise RuntimeError("probe crashed")

    monkeypatch.setattr(runbook, "step_swap_lock", boom)
    out = tmp_path / "out"
    assert runbook.main(["--out", str(out)]) == 0
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "RuntimeError: probe crashed" in summary
    assert "## 台账体检" in summary
    assert "跳过：库不存在" in summary


def test_units_snapshot_keeps_committed_rows_in_wal(tmp_path, monkeypatch):
    source = tmp_path / "source.duckdb"
    snapshots = []

    def inspect_snapshot(name, argv, out, timeout):
        snapshot = Path(argv[-1])
        snapshots.append(snapshot)
        assert snapshot != source
        with duckdb.connect(str(snapshot), read_only=True) as con:
            assert con.execute("SELECT value FROM sample").fetchall() == [(42,)]
        return {"name": name, "exit": 0, "stdout": "", "seconds": 0}

    monkeypatch.setattr(runbook, "_run", inspect_snapshot)
    with duckdb.connect(str(source)) as con:
        con.execute("CREATE TABLE sample(value INTEGER)")
        con.execute("CHECKPOINT")
        con.execute("INSERT INTO sample VALUES (42)")
        assert mfs_db.wal_path(source).is_file()
        result, _ = runbook.step_units(tmp_path, source)
        assert result["exit"] == 0
        assert con.execute("SELECT value FROM sample").fetchall() == [(42,)]
    assert snapshots and not snapshots[0].parent.exists()


def test_units_snapshot_failure_never_falls_back_to_live_database(tmp_path, monkeypatch):
    source = tmp_path / "source.duckdb"
    duckdb.connect(str(source)).close()
    snapshots = []

    def failed_clone(source, staging):
        snapshots.append(staging)
        raise OSError("snapshot unavailable")

    monkeypatch.setattr(mfs_db, "clone_to_staging", failed_clone)
    monkeypatch.setattr(runbook, "_run", lambda *args: pytest.fail("must not check the live database"))
    with pytest.raises(OSError, match="snapshot unavailable"):
        runbook.step_units(tmp_path, source)
    assert snapshots and not snapshots[0].parent.exists()


@pytest.mark.parametrize(("lint_exit", "test_exit"), [(1, 0), (None, 0), (0, 1), (0, None), (0, 0)])
def test_full_tests_cannot_hide_lint_failure_or_timeout(tmp_path, monkeypatch, lint_exit, test_exit):
    results = iter([
        {"name": "ruff", "exit": lint_exit, "stdout": "lint result", "seconds": 1, "log": "ruff.txt"},
        {"name": "pytest", "exit": test_exit, "stdout": "test result", "seconds": 2, "log": "pytest.txt"},
    ])
    monkeypatch.setattr(runbook, "_run", lambda *args: next(results))
    result, summary = runbook.step_full_tests(tmp_path)
    assert (result["exit"] == 0) == (lint_exit == 0 and test_exit == 0)
    assert "lint result" in "\n".join(summary)
    assert "test result" in "\n".join(summary)
