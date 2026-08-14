from __future__ import annotations

import json
from pathlib import Path

from intelligence.services.workbench_overview import _load_forecast_performance


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_direction_verdict_projection_uses_25_sample_gate(tmp_path: Path) -> None:
    ledger = tmp_path / "docs" / "learning" / "forecast-review-ledger"
    _write(
        ledger / "2026-07-01.answer.codex.json",
        {
            "date": "2026-07-01",
            "agent": "codex",
            "source": "duckdb",
            "hypotheses": [
                {"id": "direction", "category": "direction", "confidence": "high"}
            ],
        },
    )
    verdicts = [
        {
            "id": "direction",
            "agent": "codex",
            "stream": "盘面",
            "horizon": "T+1",
            "verdict": value,
        }
        for value in (["hit"] * 10 + ["partial"] * 5 + ["miss"] * 10)
    ]
    _write(
        ledger / "2026-07-01.verdict.json",
        {"date": "2026-07-01", "verdicts": verdicts},
    )

    result = _load_forecast_performance(tmp_path)

    assert result["total_judged"] == 25
    assert result["decision_eligible"] is True
    row = result["rows"][0]
    assert row["sample_count"] == 25
    assert row["hit_rate"] == 0.4
    assert row["weighted_rate"] == 0.5
    assert row["decision_eligible"] is True


def test_direction_projection_is_empty_when_ledger_is_missing(tmp_path: Path) -> None:
    assert _load_forecast_performance(tmp_path) == {
        "sample_goal": 25,
        "total_judged": 0,
        "decision_eligible": False,
        "rows": [],
    }
