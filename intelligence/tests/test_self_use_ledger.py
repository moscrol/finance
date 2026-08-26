"""自用摩擦台账 CLI 的行为合同。

钉三件事：写入前 schema 校验（failed/rescued 必须带摩擦）、追加不覆盖、
summary 的口径行（ok 率 / ok+降级可用率 / 救场单列）算得对。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "self_use_ledger",
    Path(__file__).resolve().parents[2] / "scripts" / "self_use_ledger.py",
)
sul = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(sul)


@pytest.fixture()
def ledger_dir(tmp_path, monkeypatch):
    target = tmp_path / "self-use-ledger"
    monkeypatch.setattr(sul, "LEDGER_DIR", target)
    monkeypatch.setattr(sul, "REPO_ROOT", tmp_path)
    return target


def _add(argv):
    return sul.main(["add", *argv])


def test_add_appends_valid_entry(ledger_dir):
    assert _add([
        "--date", "2026-08-26", "--task-type", "stock",
        "--question", "长电科技怎么看", "--outcome", "ok",
        "--minutes-saved", "15",
    ]) == 0
    assert _add([
        "--date", "2026-08-26", "--task-type", "market",
        "--question", "今天市场怎么样", "--outcome", "degraded",
        "--friction", "板块行缺当日边际量",
    ]) == 0
    lines = (ledger_dir / "2026-08-26.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "追加写入，不得覆盖"
    first = json.loads(lines[0])
    assert first["task_type"] == "stock"
    assert first["outcome"] == "ok"
    assert first["minutes_saved"] == 15
    assert first["run_id"] is None


def test_failed_without_friction_is_rejected(ledger_dir):
    with pytest.raises(SystemExit):
        _add([
            "--date", "2026-08-26", "--task-type", "news",
            "--question", "这条公告怎么看", "--outcome", "failed",
        ])
    assert not (ledger_dir / "2026-08-26.jsonl").exists(), "校验失败不得落盘"


def test_bad_date_rejected(ledger_dir):
    with pytest.raises(SystemExit):
        _add([
            "--date", "2026-13-01", "--task-type", "theme",
            "--question", "固态电池", "--outcome", "ok",
        ])


def test_summary_rates_and_rescue_bucket(ledger_dir, capsys):
    _add(["--date", "2026-08-25", "--task-type", "market",
          "--question", "复盘", "--outcome", "ok"])
    _add(["--date", "2026-08-25", "--task-type", "theme",
          "--question", "光刻胶", "--outcome", "degraded",
          "--friction", "缺 L3"])
    _add(["--date", "2026-08-26", "--task-type", "stock",
          "--question", "深挖", "--outcome", "rescued",
          "--friction", "手工重启 sidecar"])
    _add(["--date", "2026-08-26", "--task-type", "watchlist",
          "--question", "自选异动", "--outcome", "failed",
          "--friction", "接口超时且无降级提示"])
    capsys.readouterr()

    assert sul.main(["summary"]) == 0
    out = capsys.readouterr().out
    assert "1/4 = 25.0%" in out            # ok 率
    assert "2/4 = 50.0%" in out            # ok+降级可用率
    assert "手工重启 sidecar" in out        # 救场明细带摩擦原文
    assert "缺 ['news']" in out            # 五类覆盖缺口点名

    assert sul.main(["summary", "--days", "1"]) == 0
    out = capsys.readouterr().out
    assert "2026-08-25" not in out, "--days 只看最近 N 个有记录日"
