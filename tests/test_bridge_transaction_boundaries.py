"""Real DuckDB writes and controlled interleavings, never a production database."""
from __future__ import annotations

from datetime import datetime

import duckdb
import pytest

from market_feature_store.sync import bridge_hithink_stock_daily as bridge
from tests import test_bridge_hithink_stock_daily as seed


def _rows(con):
    return con.execute("SELECT * FROM fact_stock_daily ORDER BY ALL").fetchall()


class _ObservedConnection(seed._KeepOpen):
    def __init__(self, con, *, after_insert=None, before_delete=None):
        super().__init__(con)
        self.events = []
        self.after_insert = after_insert
        self.before_delete = before_delete

    def execute(self, sql, *args):
        self.events.append(sql.split()[0].upper())
        if sql.startswith("DELETE") and self.before_delete:
            self.before_delete()
        return self._con.execute(sql, *args)

    def executemany(self, sql, rows):
        self.events.append("INSERT")
        result = self._con.executemany(sql, rows)
        if self.after_insert:
            self.after_insert()
        return result


@pytest.mark.parametrize("column,value", [
    ("stock_name", "changed"), ("pct_chg", 88.0), ("turnover", 88.0),
    ("source", "changed"), ("updated_at", datetime(2026, 9, 19)),
    ("open", 88.0), ("high", 88.0), ("low", 88.0), ("volume", 88.0),
    ("close", None), ("pre_close", None), ("amount", None),
])
def test_every_other_day_column_is_guarded_and_rolled_back(column, value):
    with seed._con(seed._codes(3)) as con:
        seed._seed_canonical(con, seed._codes(3), seed.PREV)
        before = _rows(con)
        plan = bridge.build_bridge_day(con, seed.TD)

        def corrupt():
            assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date=?",
                               [seed.TD]).fetchone()[0] == 3
            con.execute(f"UPDATE fact_stock_daily SET {column}=? WHERE trade_date=?",
                        [value, seed.PREV])

        observed = _ObservedConnection(con, after_insert=corrupt)
        with pytest.raises(bridge.BridgeRefused, match="写入越界"):
            bridge.apply_bridge_day(observed, plan)
        assert observed.events[0] == "BEGIN"
        assert observed.events[-1] == "ROLLBACK"
        assert "COMMIT" not in observed.events
        assert _rows(con) == before


def test_insertion_into_previously_absent_other_day_rolls_back():
    with seed._con(seed._codes(3)) as con:
        plan = bridge.build_bridge_day(con, seed.TD)
        observed = _ObservedConnection(con, after_insert=lambda: seed._seed_canonical(
            con, seed._codes(1), "2026-09-16"))
        with pytest.raises(bridge.BridgeRefused, match="写入越界"):
            bridge.apply_bridge_day(observed, plan)
        assert _rows(con) == []
        assert observed.events[-1] == "ROLLBACK"


def test_null_and_negative_one_are_distinct_fingerprints():
    with seed._con(seed._codes(1)) as con:
        seed._seed_canonical(con, seed._codes(1), seed.PREV)
        con.execute("UPDATE fact_stock_daily SET close=NULL")
        null = bridge._day_fingerprints(con)
        con.execute("UPDATE fact_stock_daily SET close=-1")
        assert bridge._day_fingerprints(con) != null


@pytest.mark.parametrize("replace", [False, True])
def test_failure_after_first_actual_insert_restores_all_columns(replace):
    with seed._con(seed._codes(3)) as con:
        seed._seed_canonical(con, seed._codes(3), seed.PREV)
        if replace:
            seed._seed_canonical(con, seed._codes(3), seed.TD, close=99.0)
        before = _rows(con)
        plan = bridge.build_bridge_day(con, seed.TD,
                                       policy=bridge.BridgePolicy(allow_replace_existing=replace))

        class PartialInsert(_ObservedConnection):
            def executemany(self, sql, rows):
                self._con.execute(sql, rows[0])
                assert self._con.execute(
                    "SELECT close FROM fact_stock_daily WHERE trade_date=?", [seed.TD],
                ).fetchall() == [(10.0,)]
                raise RuntimeError("injected after first insert")

        observed = PartialInsert(con)
        with pytest.raises(RuntimeError, match="injected after first insert"):
            bridge.apply_bridge_day(observed, plan)
        assert observed.events[-1] == "ROLLBACK"
        assert "COMMIT" not in observed.events
        assert _rows(con) == before


def test_actual_build_then_stale_refuses_before_delete():
    with seed._con(seed._codes(3)) as con:
        plan = bridge.build_bridge_day(con, seed.TD)
        seed._seed_canonical(con, seed._codes(3), seed.TD, close=99.0)
        before = _rows(con)
        observed = _ObservedConnection(con)
        with pytest.raises(bridge.BridgeRefused):
            bridge.apply_bridge_day(observed, plan)
        assert observed.events[0] == "BEGIN"
        assert observed.events[-1] == "ROLLBACK"
        assert not {"DELETE", "INSERT", "COMMIT"} & set(observed.events)
        assert _rows(con) == before


def test_two_connections_cannot_silently_replace_winning_writer(tmp_path):
    path = tmp_path / "concurrent.duckdb"
    with duckdb.connect(str(path)) as con, seed._con(seed._codes(3)) as vendor:
        con.execute(seed._SCHEMA)
        # Match the canonical primary-key constraint, absent in the minimal fixture.
        con.execute("CREATE UNIQUE INDEX daily_pk ON fact_stock_daily(trade_date, stock_ts_code)")
        bars = vendor.execute("SELECT * FROM fact_stock_daily_hithink").fetchall()
        con.executemany("INSERT INTO fact_stock_daily_hithink VALUES (?,?,?,?,?,?,?,?,?,?,?)", bars)
        plan = bridge.build_bridge_day(con, seed.TD)
        with duckdb.connect(str(path)) as rival:
            def competing_write():
                seed._seed_canonical(rival, seed._codes(3), seed.TD, close=99.0)

            observed = _ObservedConnection(con, before_delete=competing_write)
            with pytest.raises(duckdb.Error):
                bridge.apply_bridge_day(observed, plan)
            assert observed.events[-1] == "ROLLBACK"
            assert con.execute("SELECT close FROM fact_stock_daily ORDER BY 1").fetchall() == [(99.0,)] * 3
