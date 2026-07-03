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
