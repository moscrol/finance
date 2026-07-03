"""dual_blind_forecast 的 verdict 校验与 md 回检表渲染测试。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "dual_blind_forecast", Path(__file__).resolve().parents[1] / "scripts" / "dual_blind_forecast.py"
)
d = importlib.util.module_from_spec(_SPEC)
sys.modules["dual_blind_forecast"] = d
_SPEC.loader.exec_module(d)

DATE = "2026-07-02"


@pytest.fixture()
def ledger(tmp_path: Path) -> Path:
    answer = {"picks": [{"code": "600000", "name": "x", "strategy": "s", "reason": "r"}]}
    (tmp_path / f"{DATE}.answer.codex.json").write_text(json.dumps(answer), encoding="utf-8")
    return tmp_path


def _draft(verdicts: list[dict]) -> dict:
    return {"date": DATE, "verdicts": verdicts}


def test_validate_verdict_ok(ledger: Path) -> None:
    draft = _draft([
        {"id": "market", "agent": "codex", "verdict": "hit", "actual": "上证+1%"},
        {"id": "target:600000", "agent": "codex", "verdict": "miss", "actual": "-2%"},
    ])
    assert d.validate_verdict(draft, ledger_dir=ledger) == []


def test_validate_verdict_catches_errors(ledger: Path) -> None:
    draft = _draft([
        {"id": "bogus", "agent": "codex", "verdict": "hit", "actual": "x"},
        {"id": "direction", "agent": "claude", "verdict": "hit", "actual": "x"},
        {"id": "falsify", "agent": "codex", "verdict": "hit"},
        {"id": "market", "agent": "codex", "verdict": "great", "actual": "x"},
    ])
    errors = d.validate_verdict(draft, ledger_dir=ledger)
    assert any("不在 codex 答卷假设集" in e for e in errors)
    assert any("无对应答卷" in e for e in errors)
    assert any("必须填 actual" in e for e in errors)
    assert any("verdict 应为" in e for e in errors)


def test_render_verdict_md_inserts_and_replaces(ledger: Path) -> None:
    md_path = ledger / f"{DATE}.md"
    md_path.write_text("# 复盘\n\n正文保留\n", encoding="utf-8")
    verdict = {
        "date": DATE,
        "verdicts": [{"id": "market", "agent": "codex", "verdict": "hit", "actual": "上证+1%"}],
    }
    assert d.render_verdict_md(verdict, ledger_dir=ledger) == md_path
    text = md_path.read_text(encoding="utf-8")
    assert "正文保留" in text
    assert d.VERDICT_BEGIN in text and d.VERDICT_END in text
    assert "codex 1/1" in text

    verdict["verdicts"][0]["verdict"] = "miss"
    verdict["verdicts"][0]["actual"] = "-1%"
    d.render_verdict_md(verdict, ledger_dir=ledger)
    text = md_path.read_text(encoding="utf-8")
    assert text.count(d.VERDICT_BEGIN) == 1
    assert "codex 0/1" in text
    assert "✅ hit" not in text


def test_render_verdict_md_missing_md(ledger: Path) -> None:
    assert d.render_verdict_md({"date": "1999-01-01", "verdicts": []}, ledger_dir=ledger) is None


def test_build_index_html(ledger: Path) -> None:
    answer = json.loads((ledger / f"{DATE}.answer.codex.json").read_text(encoding="utf-8"))
    answer.update({"main_judgment": "缩量分歧日", "thresholds": {"market": "涨家数>3500", "direction": "储能 diff>0", "targets": "t", "falsify": "大金融大跌"}})
    (ledger / f"{DATE}.answer.codex.json").write_text(json.dumps(answer), encoding="utf-8")
    (ledger / f"{DATE}.verdict.json").write_text(json.dumps({
        "date": DATE,
        "verdicts": [{"id": "market", "agent": "codex", "verdict": "hit", "actual": "3600"}],
    }), encoding="utf-8")
    (ledger / f"{DATE}.md").write_text("# 复盘\n\n§2 主判断原文……\n", encoding="utf-8")
    html = d.build_index_html(ledger)
    assert "缩量分歧日" in html
    assert "当日原文" in html and "§2 主判断原文……" in html
    assert "涨家数&gt;3500" in html
    assert "target:600000" in html
    assert "✅ hit" in html and "3600" in html
    assert "待验证" in html  # 未裁定的假设


def test_build_index_html_empty(tmp_path: Path) -> None:
    assert "暂无机器可读台账文件" in d.build_index_html(tmp_path)


def test_validate_verdict_stream_horizon(ledger: Path) -> None:
    draft = _draft([
        {"id": "market", "agent": "codex", "verdict": "hit", "actual": "x", "stream": "卖方", "horizon": "T+3"},
        {"id": "market", "agent": "codex", "verdict": "miss", "actual": "x", "stream": "别的", "horizon": "T+9"},
    ])
    errors = d.validate_verdict(draft, ledger_dir=ledger)
    assert any("stream 应为" in e for e in errors)
    assert any("horizon 应为" in e for e in errors)
    assert len(errors) == 2


def test_verdict_table_shows_stream_horizon_failure_mode(ledger: Path) -> None:
    table = d.build_verdict_table({
        "date": DATE,
        "verdicts": [
            {"id": "market", "agent": "codex", "verdict": "miss", "actual": "x",
             "stream": "卖方", "horizon": "T+3", "failure_mode": "阈值定早"},
            {"id": "target:600000", "agent": "codex", "verdict": "hit", "actual": "+5%"},
        ],
    })
    assert "| 卖方 | T+3 |" in table and "阈值定早" in table
    assert "| 盘面 | T+1 |" in table  # 缺省值


def test_aggregate_verdicts_by_stream_horizon(ledger: Path) -> None:
    answer = {
        "schema_version": "1.0", "date": DATE, "agent": "codex", "manifest_sha": "x",
        "stage": "s", "main_judgment": "m", "direction_ranking": ["d"],
        "picks": [{"code": "600000", "name": "x", "strategy": "s", "reason": "r"}],
        "thresholds": {"market": "m", "direction": "d", "targets": "t", "falsify": "f"},
        "recheck": {},
    }
    (ledger / f"{DATE}.answer.codex.json").write_text(json.dumps(answer), encoding="utf-8")
    (ledger / f"{DATE}.verdict.json").write_text(json.dumps({
        "date": DATE,
        "verdicts": [
            {"id": "market", "agent": "codex", "verdict": "hit", "actual": "x"},
            {"id": "market", "agent": "codex", "verdict": "miss", "actual": "x",
             "stream": "卖方", "horizon": "T+3", "failure_mode": "阈值定早"},
        ],
    }), encoding="utf-8")
    report = d.aggregate(ledger)
    stats = report["agents"]["codex"]["verdicts_by_stream_horizon"]
    assert stats["盘面/T+1"]["hit"] == 1
    assert stats["卖方/T+3"]["miss"] == 1
    assert report["agents"]["codex"]["failure_modes"] == {"阈值定早": 1}
    md = d._render_aggregate_md(report)
    assert "盘后验证按流×时点" in md and "阈值定早×1" in md
