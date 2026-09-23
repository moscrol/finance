from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import duckdb
import pytest

from scripts.verify_briefing_consumption import main


@pytest.fixture
def inputs(tmp_path: Path, monkeypatch) -> Namespace:
    db = tmp_path / "market.duckdb"
    labels = tmp_path / "labels.duckdb"
    wiki = tmp_path / "wiki"
    projection = wiki / "raw/theme-radar/opinion-store/briefing-tier-events.jsonl"
    projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"briefing_date": "2026-09-18", "available_from": "2026-09-19",
                                      "recorded_at": "2026-09-21", "tier": 2, "dimensions": 2}) + "\n")
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
        con.execute("INSERT INTO fact_market_daily VALUES ('2026-09-18')")
    with duckdb.connect(str(labels)) as con:
        con.execute(
            "CREATE TABLE history_teaching_labels ("
            "trade_date DATE, entity_type VARCHAR, entity_id VARCHAR, label VARCHAR, value_num DOUBLE, "
            "framework_version VARCHAR, status VARCHAR, computed_at TIMESTAMP)"
        )
    monkeypatch.setattr("sys.argv", ["verify", "--db-path", str(db), "--labels-db", str(labels),
                                    "--kb-wiki", str(wiki), "--briefing-date", "2026-09-18", "--entity", "test"])
    return Namespace(db=db, labels=labels, projection=projection)


def _add_landing_day(inputs: Namespace) -> None:
    with duckdb.connect(str(inputs.db)) as con:
        con.execute("INSERT INTO fact_market_daily VALUES ('2026-09-19')")


def _add_briefing_labels(
    inputs: Namespace, *, hit_value: float | None = None, early_label: str | None = None,
) -> None:
    values = {
        "tf.briefing_tier1_items": 0.0,
        "tf.briefing_tier2_items": 1.0,
        "tf.briefing_tier3_items": 0.0,
        "tf.briefing_market_confirmed": None,
        "tf.briefing_dimensions": 2.0,
        "tf.briefing_hit_rps5_pct": hit_value,
        "tf.briefing_lag_days": 2.0,
    }
    rows = [
        (label, value, "2026-09-20 08:00:00" if label == early_label else "2026-09-22 08:00:00")
        for label, value in values.items()
    ]
    with duckdb.connect(str(inputs.labels)) as con:
        con.executemany(
            "INSERT INTO history_teaching_labels "
            "(trade_date, entity_type, entity_id, label, value_num, framework_version, status, computed_at) "
            "VALUES ('2026-09-19', 'market', 'market', ?, ?, 'tf-test', 'ok', ?)",
            rows,
        )


@pytest.mark.parametrize("case", ["missing_file", "empty_projection", "invalid_projection", "empty_market", "missing_labels"])
def test_invalid_inputs_never_report_success(inputs, case, capsys):
    if case == "missing_file":
        inputs.projection.unlink()
    elif case == "empty_projection":
        inputs.projection.write_text("")
    elif case == "invalid_projection":
        inputs.projection.write_text("{\n")
    elif case == "empty_market":
        with duckdb.connect(str(inputs.db)) as con:
            con.execute("DELETE FROM fact_market_daily")
    else:
        with duckdb.connect(str(inputs.db)) as con:
            con.execute("INSERT INTO fact_market_daily VALUES ('2026-09-21')")
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "FAIL"


def test_market_not_yet_available_is_blocked_with_nonzero_exit(inputs, capsys):
    assert main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert result["market_latest"] == "2026-09-18"
    assert result["briefings"][0]["source_rows"] == 1
    assert result["briefings"][0]["reason"] == "market_calendar_ends_before_availability"


def test_null_source_field_cannot_be_replaced_by_zero(inputs, capsys):
    _add_landing_day(inputs)
    _add_briefing_labels(inputs, hit_value=0.0)
    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "FAIL"
    assert "Label mismatch: 2026-09-19 briefing_hit_rps5_pct" in result["error"]


def test_one_backdated_label_cannot_be_hidden_by_later_labels(inputs, capsys):
    _add_landing_day(inputs)
    _add_briefing_labels(inputs, early_label="tf.briefing_tier1_items")
    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "FAIL"
    assert "Label computed_at before source recorded_at: 2026-09-19 tf.briefing_tier1_items" in result["error"]
