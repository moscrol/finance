"""Invalid historical identity must remain unknown until its streak is consumed."""
from datetime import date, datetime, timedelta, timezone

import pytest

from market_feature_store.sector_universe import SectorDescriptor, SectorUniverseStore
from market_feature_store.sync import compute_local_stats as cls
from tests.test_compute_local_stats import _db, _stock

TABLES = ("fact_theme_limit_heat_daily", "fact_theme_limit_stock_daily",
          "fact_limit_advance_daily", "fact_leader_height_daily", "fact_stock_high_daily")


def seed(con):
    for offset in range(2, 27):
        _stock(con, str(date(2026, 9, 23) - timedelta(days=offset)),
               "600001.SH", "ordinary", 10.0, 10.0)
    _stock(con, "2026-09-22", "600001.SH", "ordinary", 11.0, 10.0)
    _stock(con, "2026-09-23", "600001.SH", "ordinary", 12.1, 11.0)
    con.execute("UPDATE fact_stock_daily SET high=close")
    con.execute("INSERT INTO dim_sector (sector_ts_code,sector_name) VALUES ('990001.FP','sample')")
    snapshot = SectorUniverseStore(con).publish_snapshot(
        trade_date="2026-09-23", provider_source="fupanhui",
        sectors=[SectorDescriptor("990001.FP", "sample", 1)],
        captured_at=datetime(2026, 9, 23, 18, tzinfo=timezone.utc))
    con.execute("INSERT INTO fact_sector_stock_daily_generation "
                "(trade_date,sector_universe_snapshot_id,sector_ts_code,sector_name,stock_ts_code,"
                "stock_name,price,pct_chg,amount,source,updated_at) "
                "VALUES ('2026-09-23',?,'990001.FP','sample','600001.SH','ordinary',12.1,10.,1.,'local:test',now())",
                [snapshot.snapshot_id])


def compute(con, consumer):
    if consumer == "high":
        return cls.compute_stock_high_local("2026-09-23", con=con)
    kwargs = {"recovery_members": {"990001.FP": ["600001.SH"]}} if consumer == "recovery" else {}
    return cls.compute_limit_stats_local("2026-09-23", con=con, **kwargs)


@pytest.mark.parametrize("prior_name", [None, "", "   ", "\u3000", "bad\x00name", "bad\tname", "bad\x7fname"],
                         ids=["null", "empty", "spaces", "wide-space", "nul", "tab", "del"])
@pytest.mark.parametrize("consumer", ["daily", "recovery", "high"])
def test_consumed_unknown_historical_name_refuses_before_replacing_stats(prior_name, consumer):
    with _db() as con:
        seed(con)
        compute(con, consumer)
        before = {table: con.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall() for table in TABLES}
        con.execute("UPDATE fact_stock_daily SET stock_name=? WHERE trade_date='2026-09-22'", [prior_name])
        with pytest.raises(cls.InvalidStockName, match="consumed history: 600001.SH @ 2026-09-22"):
            compute(con, consumer)
        assert {table: con.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall() for table in TABLES} == before


def test_overview_does_not_consume_prior_streak_identity():
    with _db() as con:
        seed(con)
        con.execute("UPDATE fact_stock_daily SET stock_name=NULL WHERE trade_date='2026-09-22'")
        assert cls.compute_market_overview_local("2026-09-23", con=con)["limit_up"] == 1


def test_current_non_limit_stock_does_not_consume_prior_streak_identity():
    with _db() as con:
        seed(con)
        con.execute("UPDATE fact_stock_daily SET stock_name=NULL WHERE trade_date='2026-09-22'")
        con.execute("UPDATE fact_stock_daily SET close=pre_close WHERE trade_date='2026-09-23'")
        assert compute(con, "daily")["market_limit_up"] == 0


def test_valid_break_keeps_older_unknown_name_out_of_streak():
    with _db() as con:
        seed(con)
        con.execute("UPDATE fact_stock_daily SET stock_name=NULL WHERE trade_date='2026-09-21'")
        con.execute("UPDATE fact_stock_daily SET close=pre_close WHERE trade_date='2026-09-22'")
        assert compute(con, "daily")["leader_height"] == 1
