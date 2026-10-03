"""Synthetic evidence only. No network or production DB; all paths temporary."""
from datetime import date
import hashlib
import json

import duckdb
import pytest

from market_feature_store.db import SCHEMA_PATH
from scripts.audit_stock_daily_degraded_gap import (
    GapAuditRefused, audit_day, main, validate_joined_bar,
)

DAY = date(2026, 9, 29)
CODE = "600001.SH"


def quote(raw="10.25/100/100000", timestamp="20260929150501", rate="1.00",
          symbol="sh600001"):
    fields = [""] * 58
    values = {1: "Fixture", 2: symbol[2:], 3: "10.25", 4: "10.00", 5: "10.00",
              6: "100", 30: timestamp, 32: "2.50", 33: "11", 34: "9",
              35: raw, 38: rate, 40: "0"}
    for index, value in values.items():
        fields[index] = value
    return (f'v_{symbol}="' + '~'.join(fields) + '";\n').encode('gbk')


def capture(tmp_path, raw=None, symbol="sh600001"):
    folder = tmp_path / "capture"
    folder.mkdir(exist_ok=True)
    payload = quote(symbol=symbol) if raw is None else raw
    (folder / "batch-0001.raw").write_bytes(payload)
    receipt = {"target_date": str(DAY), "codes": [symbol[2:] + ".SH"], "captured_code_count": 1,
               "batches": [{"file": "batch-0001.raw", "codes": [symbol[2:] + ".SH"],
                            "http_status": 200, "sha256": hashlib.sha256(payload).hexdigest()}]}
    (folder / "receipt.json").write_text(json.dumps(receipt))
    return folder


def seed(con):
    schema = SCHEMA_PATH.read_text()
    for name in ("fact_stock_daily_hithink", "fact_stock_adjustment_hithink", "fact_stock_daily"):
        start = schema.index(f"CREATE TABLE IF NOT EXISTS {name} (")
        con.execute(con.extract_statements(schema[start:])[0].query)
    for day, close in (("2026-09-28", 10.0), ("2026-09-29", 10.25)):
        con.execute("INSERT INTO fact_stock_daily_hithink VALUES (?, ?, 10, 11, 9, ?, "
                    "10000, 100000, 'none', 'hithink:daily-k-10d', '2026-09-29 18:00:00')",
                    [day, CODE, close])
        con.execute("INSERT INTO fact_stock_daily "
                    "(trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount, "
                    "turnover, source, open, high, low, volume) "
                    "VALUES (?, ?, 'Fixture', ?, 10.0, 2.5, 0.001, NULL, "
                    "'hithink:daily-k-10d', 10, 11, 9, 100)", [day, CODE, close])


def test_readonly_diagnostic_always_refuses_publication(tmp_path):
    folder = capture(tmp_path)
    with duckdb.connect(":memory:") as con:
        seed(con)
        before = con.execute("SELECT count(*),sum(close) FROM fact_stock_daily").fetchone()
        report = audit_day(con, folder, DAY)
        assert before == con.execute("SELECT count(*),sum(close) FROM fact_stock_daily").fetchone()
    assert report["source_scope_count"] == report["canonical_rows_aligned"] == 1
    assert report["preview_gaps"] == []
    assert report["absent_from_vendor_previous_canonical_codes"] == []
    assert report["quote_capture"]["validated_batches"] == 1
    assert report["candidate_field38_value_count"] == 1
    assert report["production_ready"] is report["database_writes"] is False
    assert report["quote_capture"]["independent_market_universe_verified"] is False
    assert report["quote_capture"]["official_suspension_status_verified"] is False


@pytest.mark.parametrize("broken,expected", [
    ({"close": 11}, "close/amount mismatch"),
    ({"amount_yuan": 90000}, "close/amount mismatch"),
    ({"volume_shares": 9000}, "volume mismatch"),
    ({"turnover_pct": 101}, "invalid active-bar/rate"),
    ({"quote_timestamp": "20260928150501"}, "missing or wrong-date"),
])
def test_quote_mismatches_fail_closed(broken, expected):
    q = {"quote_timestamp": "20260929150501", "close": 10.25,
         "amount_yuan": 100000, "volume_shares": 10000, "turnover_pct": 1}
    with pytest.raises(GapAuditRefused, match=expected):
        validate_joined_bar((CODE, 10.25, 10000, 100000), {**q, **broken}, DAY)


def test_missing_capture_quote_and_missing_canonical_are_not_silent(tmp_path):
    folder = capture(tmp_path)
    with duckdb.connect(":memory:") as con:
        seed(con)
        con.execute("DELETE FROM fact_stock_daily WHERE trade_date=?", [DAY])
        with pytest.raises(GapAuditRefused, match="identity differs"):
            audit_day(con, folder, DAY)
    with duckdb.connect(":memory:") as con:
        seed(con)
        (folder / "batch-0001.raw").write_bytes(b"tampered")
        with pytest.raises(ValueError, match="hash changed"):
            audit_day(con, folder, DAY)


def test_cli_never_overwrites_diagnostic_or_writes_db(tmp_path, capsys):
    folder = capture(tmp_path)
    db = tmp_path / "fixture.duckdb"
    with duckdb.connect(str(db)) as con:
        seed(con)
    path = tmp_path / "report.json"
    args = ["--db", str(db), "--capture-dir", str(folder),
            "--trade-date", str(DAY), "--json", str(path)]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["production_ready"] is False
    first = path.read_bytes()
    assert main(args) == 2
    assert path.read_bytes() == first
    assert json.loads(capsys.readouterr().out)["diagnostic_complete"] is False
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM fact_stock_daily").fetchone()[0] == 2


def test_missing_previous_bar_remains_gap_not_silent_reference(tmp_path):
    folder = capture(tmp_path)
    with duckdb.connect(":memory:") as con:
        seed(con)
        con.execute("DELETE FROM fact_stock_daily_hithink WHERE trade_date=?", ["2026-09-28"])
        # Can't keep a canonical row that failed the preview. The tool refuses,
        # rather than filling a previous close from yesterday's canonical table.
        with pytest.raises(GapAuditRefused, match="unrecognized exceptional row source"):
            audit_day(con, folder, DAY)


def test_already_filled_gap_is_a_diagnostic_not_a_release(tmp_path):
    folder = capture(tmp_path)
    with duckdb.connect(":memory:") as con:
        seed(con)
        con.execute("DELETE FROM fact_stock_daily_hithink WHERE trade_date=?", ["2026-09-28"])
        con.execute("UPDATE fact_stock_daily SET source=? WHERE trade_date=?", [
            "hithink:daily-k-10d:gapfill-two-source", DAY])
        report = audit_day(con, folder, DAY)
    assert report["preview_calculated_count"] == 0
    assert report["canonical_total_rows"] == 1
    assert report["canonical_gapfill_exception_count"] == 1
    assert report["preview_gaps"][0]["reasons"] == ["missing-previous-bar"]
    assert report["canonical_gapfill_exceptions"][0]["reference_check"] == (
        "quote_reference_matched_not_official_event")
    assert report["candidate_field38_value_count"] == 0
    assert report["production_ready"] is False


def test_already_filled_gap_without_quote_keeps_reference_unverified(tmp_path):
    folder = capture(tmp_path, symbol="sh600002")
    with duckdb.connect(":memory:") as con:
        seed(con)
        con.execute("DELETE FROM fact_stock_daily_hithink WHERE trade_date=?", ["2026-09-28"])
        con.execute("UPDATE fact_stock_daily SET source=? WHERE trade_date=?", [
            "hithink:daily-k-10d:gapfill-two-source", DAY])
        report = audit_day(con, folder, DAY)
    assert report["gapfill_reference_unavailable_count"] == 1
    assert report["canonical_gapfill_exceptions"][0]["reference_check"] == (
        "quote_reference_unavailable")
    assert report["production_ready"] is False


@pytest.mark.parametrize("mutate", ["source", "open", "pct_chg", "volume"])
def test_already_filled_gap_drift_is_refused(tmp_path, mutate):
    folder = capture(tmp_path)
    with duckdb.connect(":memory:") as con:
        seed(con)
        con.execute("DELETE FROM fact_stock_daily_hithink WHERE trade_date=?", ["2026-09-28"])
        con.execute("UPDATE fact_stock_daily SET source=? WHERE trade_date=?", [
            "hithink:daily-k-10d:gapfill-two-source", DAY])
        values = {"source": "unreviewed", "open": 9.9, "pct_chg": 3.0, "volume": 101.0}
        con.execute(f"UPDATE fact_stock_daily SET {mutate}=? WHERE trade_date=?", [values[mutate], DAY])
        with pytest.raises(GapAuditRefused):
            audit_day(con, folder, DAY)
