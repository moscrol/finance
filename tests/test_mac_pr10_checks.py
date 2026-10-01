"""Mac 侧核验串联脚本：各步独立、坏一步不拖累后面，摘要只有计数和判定、不带台账正文。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import duckdb

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
    assert "| T1 |" in summary  # 召回分档表进摘要
    assert SECRET not in summary
    assert "若强势股成交占比回到" not in summary, "回答原句只进本机日志"
    assert "若强势股成交占比回到" in (out / "logs" / "03-replay.txt").read_text(encoding="utf-8")
    assert "可以贴回来" in capsys.readouterr().out


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
