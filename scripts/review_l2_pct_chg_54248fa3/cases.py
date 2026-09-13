"""Independent review probes for 54248fa3; only disposable DuckDB files are written.

Run with the repository as cwd using the workbench interpreter. Three regression
assertions intentionally fail on the reviewed revision; do not treat them as
production-suite failures. Remaining cases verify narrow successful contracts.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

ROOT = Path(os.environ.get("L2_QC_REPO", Path.cwd()))
DATE = "2026-07-15"
CAP = "feature_l2_capital_flow_daily"
QUANT = "feature_l2_quant_orders_daily"


@pytest.fixture
def setup_db(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    import market_feature_store.db as db

    path = tmp_path / "fixture.duckdb"
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.syspath_prepend(str(ROOT / "scripts/moneyflow"))
    monkeypatch.delitem(sys.modules, "config", raising=False)
    spec = importlib.util.spec_from_file_location(
        "l2_writer_qc", ROOT / "scripts/moneyflow/write_to_duckdb.py"
    )
    writer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(writer)
    with duckdb.connect(str(path)) as con:
        writer.init_db(con)
    return writer, path


def seed(path, codes=("000001",), daily=True, scans=("top100",), date=DATE):
    with duckdb.connect(str(path)) as con:
        for code in codes:
            if daily:
                con.execute(
                    "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, pct_chg) "
                    "VALUES (?, ?, 1.5)", [date, code + ".SZ"],
                )
            for scan in scans:
                con.execute(
                    f"INSERT INTO {CAP} "
                    "(trade_date, scan_type, stock_code, stock_ts_code, pct_change, "
                    "main_buy_net_wan, score, big_order_threshold_wan, calculated_at) "
                    "VALUES (?, ?, ?, ?, 9.99, 42, 0.125, 50, '2026-07-15 16:00:00')",
                    [date, scan, code, code + ".SZ"],
                )
            con.execute(
                f"INSERT INTO {QUANT} "
                "(trade_date, stock_code, stock_ts_code, pct_change, quant_amount_wan, "
                "quant_threshold_wan, calculated_at) "
                "VALUES (?, ?, ?, 9.99, 100, 200, '2026-07-15 16:00:00')",
                [date, code, code + ".SZ"],
            )


def snapshot(path):
    with duckdb.connect(str(path), read_only=True) as con:
        return {
            table: con.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in (CAP, QUANT, "ops_pipeline_run_daily")
        }


def test_cli_refuses_nonexistent_database(tmp_path):
    path = tmp_path / "typo" / "missing.duckdb"
    env = {**os.environ, "MARKET_FEATURE_STORE_DB": str(path)}
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/moneyflow/write_to_duckdb.py"),
         "--repair-pct-chg", DATE],
        env=env, cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode != 0 and not path.exists(), (
        f"exit={completed.returncode}, created_database={path.exists()}, "
        f"stdout={completed.stdout!r}"
    )


def test_audit_counts_target_rows_not_distinct_symbols(setup_db):
    writer, path = setup_db
    seed(path, codes=("000001",), scans=("top100", "limitup"))
    seed(path, codes=("000002",), daily=False, scans=("top100", "limitup"))
    message = writer.repair_pct_chg(DATE)
    with duckdb.connect(str(path), read_only=True) as con:
        actual = con.execute(
            f"SELECT count(pct_change), count(*) - count(pct_change) FROM {CAP}"
        ).fetchone()
    assert actual == (2, 2)
    assert "capital updated=2 null=2" in message, message


def test_all_missing_symbols_are_registered(setup_db):
    writer, path = setup_db
    codes = tuple(f"{i:06d}" for i in range(1, 22))
    seed(path, codes=codes, daily=False)
    writer.repair_pct_chg(DATE)
    with duckdb.connect(str(path), read_only=True) as con:
        message = con.execute(
            "SELECT message FROM ops_pipeline_run_daily WHERE step='repair_pct_chg'"
        ).fetchone()[0]
    assert all(code in message for code in codes), message


def test_two_tables_and_ledger_rollback_together(setup_db, monkeypatch):
    writer, path = setup_db
    seed(path)
    before = snapshot(path)
    original = writer._mark_status

    def fail_after_ledger(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected failure after both tables and ledger")

    monkeypatch.setattr(writer, "_mark_status", fail_after_ledger)
    with pytest.raises(RuntimeError, match="injected failure"):
        writer.repair_pct_chg(DATE)
    assert snapshot(path) == before


def test_only_pct_column_changes_and_values_are_idempotent(setup_db):
    writer, path = setup_db
    seed(path, scans=("top100", "limitup"))
    seed(path, codes=("000002",), daily=False)
    seed(path, date="2026-07-14")
    with duckdb.connect(str(path), read_only=True) as con:
        before = {
            table: con.execute(f"SELECT * EXCLUDE(pct_change) FROM {table} ORDER BY ALL").fetchall()
            for table in (CAP, QUANT)
        }
    writer.repair_pct_chg(DATE)
    first = snapshot(path)
    writer.repair_pct_chg(DATE)
    second = snapshot(path)
    for table in (CAP, QUANT):
        assert first[table] == second[table]
    with duckdb.connect(str(path), read_only=True) as con:
        for table in (CAP, QUANT):
            assert con.execute(
                f"SELECT * EXCLUDE(pct_change) FROM {table} ORDER BY ALL"
            ).fetchall() == before[table]
            assert con.execute(
                f"SELECT DISTINCT pct_change FROM {table} WHERE trade_date='2026-07-14'"
            ).fetchall() == [(9.99,)]
            assert con.execute(
                f"SELECT DISTINCT stock_code, pct_change FROM {table} "
                "WHERE trade_date=? ORDER BY stock_code", [DATE]
            ).fetchall() == [("000001", 1.5), ("000002", None)]


def test_source_null_is_preserved_as_null(setup_db):
    writer, path = setup_db
    seed(path)
    with duckdb.connect(str(path)) as con:
        con.execute("UPDATE fact_stock_daily SET pct_chg=NULL")
    writer.repair_pct_chg(DATE)
    with duckdb.connect(str(path), read_only=True) as con:
        for table in (CAP, QUANT):
            assert con.execute(f"SELECT pct_change FROM {table}").fetchall() == [(None,)]
