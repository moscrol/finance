"""canonical DuckDB 到板块分析消费者的只读适配器测试。"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from market_feature_store.analysis.sector_data import SectorDataProvider


def _make_fixture(path: Path) -> None:
    con = duckdb.connect(str(path))
    con.execute(
        """
        CREATE TABLE fact_market_daily (
            trade_date DATE,
            total_amount DOUBLE,
            amount_vs_yesterday_pct DOUBLE,
            limit_up INTEGER,
            limit_down INTEGER,
            sh_week_ma DOUBLE,
            sh_deviation_pct DOUBLE,
            advancers INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE fact_sector_daily (
            trade_date DATE,
            sector_ts_code TEXT,
            sector_name TEXT,
            diff_ratio DOUBLE,
            pct_chg DOUBLE,
            amount DOUBLE
        )
        """
    )
    con.executemany(
        "INSERT INTO fact_market_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("2026-01-01", 100.0, None, 10, 1, 3000.0, 0.1, 1000),
            ("2026-01-02", 120.0, 20.0, 12, 2, 3010.0, 0.2, 2000),
            ("2026-01-03", 110.0, -8.333, 11, 3, 3020.0, -0.1, 3000),
        ],
    )
    con.executemany(
        "INSERT INTO fact_sector_daily VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("2026-01-01", "S1", "测试板块", 12.0, 1.5, 600.0),
            ("2026-01-01", "S2", "空涨幅", 8.0, None, 400.0),
            ("2026-01-02", "S1", "测试板块", 20.0, 2.5, 700.0),
            ("2026-01-03", "S1", "测试板块", -2.0, -1.0, 500.0),
        ],
    )
    con.close()


def test_provider_maps_canonical_sector_and_market_fields(tmp_path):
    db_path = tmp_path / "market_feature_store.duckdb"
    _make_fixture(db_path)
    provider = SectorDataProvider(db_path)

    try:
        assert provider.get_sector_price_matrix("2026-01-01", "2026-01-03") == {
            "2026-01-01": {"S1": 1.5},
            "2026-01-02": {"S1": 2.5},
            "2026-01-03": {"S1": -1.0},
        }
        assert provider.get_sector_marginal("2026-01-02") == {
            "S1": {
                "sector": "测试板块",
                "diff_ratio": 20.0,
                "pct_chg": 2.5,
                "amount": 700.0,
            }
        }
        assert provider.get_market_data("2026-01-01", "2026-01-03") == [
            {
                "date": "2026-01-01",
                "volume": 100.0,
                "volume_change": None,
                "limit_up": 10,
                "limit_down": 1,
                "week_ma": 3000.0,
                "deviation": 0.1,
            },
            {
                "date": "2026-01-02",
                "volume": 120.0,
                "volume_change": 20.0,
                "limit_up": 12,
                "limit_down": 2,
                "week_ma": 3010.0,
                "deviation": 0.2,
            },
            {
                "date": "2026-01-03",
                "volume": 110.0,
                "volume_change": -8.333,
                "limit_up": 11,
                "limit_down": 3,
                "week_ma": 3020.0,
                "deviation": -0.1,
            },
        ]
        advancers = provider.get_advancers("2026-01-01", "2026-01-03")
        assert [row["count"] for row in advancers] == [1000, 2000, 3000]
        assert [row["ma5"] for row in advancers] == [1000.0, 1500.0, 2000.0]
        assert provider.get_trading_dates("2026-01-01", "2026-01-03") == [
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
        ]
    finally:
        provider.close()


def test_provider_rejects_missing_database_without_creating_it(tmp_path):
    db_path = tmp_path / "missing.duckdb"

    with pytest.raises(FileNotFoundError, match="canonical DuckDB"):
        SectorDataProvider(db_path)

    assert not db_path.exists()


def test_provider_rejects_missing_canonical_relation(tmp_path):
    db_path = tmp_path / "incomplete.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
    con.close()

    with pytest.raises(RuntimeError, match="fact_sector_daily"):
        SectorDataProvider(db_path)
