from datetime import date, timedelta

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence.api.river_daily_routes import register_daily_river_routes
from intelligence.services.river_daily_overview import daily_overview


@pytest.fixture
def market(tmp_path):
    path = tmp_path / "market.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fact_market_daily (trade_date DATE, sh_index_close DOUBLE, total_amount DOUBLE)")
    con.execute("CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code TEXT, sector_name TEXT, pct_chg DOUBLE, amount DOUBLE, diff_ratio DOUBLE)")
    con.execute("CREATE TABLE fact_limit_advance_daily (trade_date DATE, stock_ts_code TEXT, stock_name TEXT, boards INTEGER, theme TEXT, pct_chg DOUBLE)")
    for i in range(30):
        day = date(2026, 1, 1) + timedelta(days=i)
        con.execute("INSERT INTO fact_market_daily VALUES (?, ?, ?)", [day, 3000 + i, 10000 + i])
        con.execute("INSERT INTO fact_sector_daily VALUES (?, 's1', '铜', 0, 100, NULL)", [day])
        if i != 28:
            con.execute("INSERT INTO fact_sector_daily VALUES (?, 's2', '铜缆', 2, 90, 0.4)", [day])
    con.execute("INSERT INTO fact_limit_advance_daily VALUES ('2026-01-30', '000001', '测试股', 3, '测试题材', 10)")
    con.close()
    return path


def test_daily_dates_and_missing_cells(market):
    data = daily_overview(market, days=5)
    assert len(data["days"]) == 5 and len(data["calendar"]) == 30
    assert data["days"][-1]["sector_count"] == 2
    copper = next(s for s in data["sectors"] if s["id"] == "s1")
    cable = next(s for s in data["sectors"] if s["id"] == "s2")
    assert copper["points"][-2][0] == 0
    assert cable["points"][-2] is None
    assert data["days"][-1]["sector_flat_count"] == 1
    assert data["days"][-1]["sector_losers"] == []
    assert data["days"][-1]["limitup"]["max_boards"] == 3
    assert data["days"][-2]["limitup"] is None


def test_ma_prewarm_and_schema_missing_field(market):
    data = daily_overview(market, days=5)
    assert data["days"][-1]["ma20"] == pytest.approx(sum(range(3010, 3030)) / 20)
    assert data["days"][0]["sh_index_open"] is None


def test_historical_window_and_empty(market):
    data = daily_overview(market, days=5, end=date(2026, 1, 12))
    assert data["end"] == "2026-01-12"
    assert data["latest_market_date"] == "2026-01-30"
    assert daily_overview(market, days=5, end=date(2020, 1, 1))["days"] == []


def test_no_implicit_rename_merge(market):
    con = duckdb.connect(str(market))
    con.execute("UPDATE fact_sector_daily SET sector_name='铜新版' WHERE sector_ts_code='s1' AND trade_date='2026-01-30'")
    con.close()
    data = daily_overview(market, days=5)
    assert len([s for s in data["sectors"] if s["id"] == "s1"]) == 2


def test_duplicate_snapshot_not_arbitrarily_picked(market):
    con = duckdb.connect(str(market))
    con.execute("INSERT INTO fact_sector_daily SELECT * FROM fact_sector_daily LIMIT 1")
    con.close()
    with pytest.raises(ValueError, match="duplicate"):
        daily_overview(market, days=40)


def test_routes_validation_and_empty_attention(market, tmp_path):
    app = FastAPI()
    register_daily_river_routes(app, market_db_path=market, attention_ledger_path=tmp_path / "none.jsonl")
    client = TestClient(app)
    assert client.get('/api/river/daily-overview?days=5').status_code == 200
    assert client.get('/api/river/daily-overview?days=1000').status_code == 422
    assert client.get('/api/river/daily-overview?end=oops').status_code == 422
    response = client.get('/api/river/opinion-attention?as_of=2026-01-30')
    assert response.status_code == 200 and response.json()["collection_status"] == "not_connected"
    assert client.get('/api/river/opinion-attention?as_of=not-a-date').status_code == 422


def test_missing_database_does_not_create(tmp_path):
    path = tmp_path / "missing.duckdb"
    with pytest.raises(FileNotFoundError):
        daily_overview(path)
    assert not path.exists()
