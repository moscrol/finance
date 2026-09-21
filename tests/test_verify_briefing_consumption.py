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
        con.execute("CREATE TABLE history_teaching_labels (trade_date DATE, entity_type VARCHAR, entity_id VARCHAR, label VARCHAR, value_num DOUBLE)")
    monkeypatch.setattr("sys.argv", ["verify", "--db-path", str(db), "--labels-db", str(labels),
                                    "--kb-wiki", str(wiki), "--briefing-date", "2026-09-18", "--entity", "test"])
    return Namespace(db=db, labels=labels, projection=projection)


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
