from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pytest

from intelligence.services.duckdb_market_snapshot import (
    DuckDbSnapshotUnavailable,
    build_duckdb_snapshot_candidate,
)


BEIJING = ZoneInfo("Asia/Shanghai")


def _build_db(
    path: Path,
    *,
    trade_date: str = "2026-07-16",
    stock_rows: int = 4000,
    include_mainline: bool = True,
) -> Path:
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE fact_market_daily (
            trade_date DATE,
            market_stage VARCHAR,
            total_amount DOUBLE,
            volume_ratio DOUBLE,
            advancers INTEGER,
            limit_up INTEGER,
            limit_down INTEGER,
            industry_1 VARCHAR,
            industry_1_ratio DOUBLE,
            industry_2 VARCHAR,
            industry_2_ratio DOUBLE,
            industry_3 VARCHAR,
            industry_3_ratio DOUBLE,
            source VARCHAR,
            updated_at TIMESTAMP
        );
        CREATE TABLE fact_stock_daily (
            trade_date DATE,
            stock_ts_code VARCHAR,
            stock_name VARCHAR,
            pct_chg DOUBLE,
            amount DOUBLE,
            source VARCHAR,
            updated_at TIMESTAMP
        );
        CREATE TABLE fact_sector_daily (
            trade_date DATE,
            sector_name VARCHAR,
            pct_chg DOUBLE,
            amount DOUBLE,
            diff_ratio DOUBLE,
            strength DOUBLE,
            source VARCHAR,
            updated_at TIMESTAMP
        );
        CREATE TABLE fact_mainline_sector_daily (
            trade_date DATE,
            theme_name VARCHAR,
            sector_name VARCHAR,
            limit_up_count INTEGER,
            strength DOUBLE,
            cycle_status VARCHAR,
            source VARCHAR,
            updated_at TIMESTAMP
        );
        """
    )
    connection.execute(
        """
        INSERT INTO fact_market_daily VALUES (
            ?::DATE, '上涨阶段', 25000.0, 105.0, 2500, 80, 8,
            '电子', 32.0, '通信', 18.0, '医药', 12.0,
            'fixture:market', '2026-07-16 18:00:00'
        )
        """,
        [trade_date],
    )
    connection.execute(
        """
        INSERT INTO fact_stock_daily
        SELECT
            ?::DATE,
            printf('%06d.SZ', i),
            printf('测试股票%d', i),
            CASE WHEN i < 2500 THEN 8.0 + (i % 20) / 100.0 ELSE -1.0 END,
            1.0 + i / 10.0,
            'fixture:stock',
            '2026-07-16 18:01:00'::TIMESTAMP
        FROM range(?) AS rows(i)
        """,
        [trade_date, stock_rows],
    )
    connection.execute(
        """
        INSERT INTO fact_sector_daily VALUES
        (?::DATE, '光模块', 3.2, 1500.0, 12.0, 88.0, 'fixture:sector', '2026-07-16 18:02:00'),
        (?::DATE, '创新药', 2.1, 900.0, 8.0, 70.0, 'fixture:sector', '2026-07-16 18:02:00')
        """,
        [trade_date, trade_date],
    )
    if include_mainline:
        connection.execute(
            """
            INSERT INTO fact_mainline_sector_daily VALUES
            (?::DATE, 'AI算力', '光模块', 6, 90.0, '顺势', 'fixture:mainline', '2026-07-16 18:03:00'),
            (?::DATE, 'AI算力', '液冷', 2, 75.0, '启动', 'fixture:mainline', '2026-07-16 18:03:00')
            """,
            [trade_date, trade_date],
        )
    connection.close()
    return path


def test_builds_complete_exact_date_snapshot(tmp_path: Path) -> None:
    db_path = _build_db(tmp_path / "market.duckdb")

    candidate = build_duckdb_snapshot_candidate(
        db_path,
        target_date="2026-07-16",
        now=datetime(2026, 7, 16, 18, 30, tzinfo=BEIJING),
    )

    daily = candidate.document
    assert candidate.trade_date == "2026-07-16"
    assert daily["quality"] == "complete"
    assert daily["freshness"] == "fresh"
    assert daily["source"] == "duckdb:market_feature_store"
    assert daily["market"]["advancers"] == 2500
    assert daily["market"]["decliners"] == 1500
    assert daily["market"]["capacity_top3"][0] == {
        "industry": "电子",
        "ratio": 32.0,
    }
    assert daily["themes"][0]["concept"] == "AI算力"
    assert daily["themes"][0]["trigger_types"] == ["duckdb_mainline"]
    assert len(daily["strong_stocks"]) == 80
    assert candidate.source_tables == (
        "fact_market_daily",
        "fact_stock_daily",
        "fact_mainline_sector_daily",
    )


def test_uses_latest_prior_date_only_when_allowed(tmp_path: Path) -> None:
    db_path = _build_db(
        tmp_path / "market.duckdb",
        trade_date="2026-07-15",
    )

    with pytest.raises(DuckDbSnapshotUnavailable, match="2026-07-16"):
        build_duckdb_snapshot_candidate(
            db_path,
            target_date="2026-07-16",
        )

    candidate = build_duckdb_snapshot_candidate(
        db_path,
        target_date="2026-07-16",
        allow_latest_before=True,
    )

    assert candidate.trade_date == "2026-07-15"
    assert candidate.document["freshness"] == "historical"
    assert candidate.document["requested_trade_date"] == "2026-07-16"


def test_rejects_sparse_stock_fact_table(tmp_path: Path) -> None:
    db_path = _build_db(
        tmp_path / "market.duckdb",
        stock_rows=3999,
    )

    with pytest.raises(DuckDbSnapshotUnavailable, match="stock rows 3999 < 4000"):
        build_duckdb_snapshot_candidate(
            db_path,
            target_date="2026-07-16",
        )


def test_uses_sector_strength_without_claiming_mainline(tmp_path: Path) -> None:
    db_path = _build_db(
        tmp_path / "market.duckdb",
        include_mainline=False,
    )

    candidate = build_duckdb_snapshot_candidate(
        db_path,
        target_date="2026-07-16",
    )

    assert candidate.document["themes"][0]["concept"] == "光模块"
    assert candidate.document["themes"][0]["trigger_types"] == [
        "duckdb_sector_strength"
    ]
    assert candidate.source_tables == (
        "fact_market_daily",
        "fact_stock_daily",
        "fact_sector_daily",
    )
