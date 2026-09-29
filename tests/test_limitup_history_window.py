import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence.api.river_routes import register_river_routes


def test_limitup_calendar_accepts_historical_end(tmp_path):
    path = tmp_path / "historical.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("""CREATE TABLE fact_market_daily (
            trade_date DATE, limit_up INT, limit_down INT, advancers INT, total_amount DOUBLE,
            amount_vs_yesterday_pct DOUBLE, market_stage TEXT, stage_day INT, sh_index_pct_chg DOUBLE, volume_state TEXT)""")
        con.execute("""CREATE TABLE fact_limit_advance_daily (
            trade_date DATE, stock_ts_code TEXT, stock_name TEXT, boards INT, theme TEXT, pct_chg DOUBLE, first_limit_date DATE)""")
        con.execute("INSERT INTO fact_market_daily (trade_date) VALUES ('2026-01-05'),('2026-01-06'),('2026-09-24')")
        con.execute("INSERT INTO fact_limit_advance_daily VALUES ('2026-01-06','s1','历史股',3,'测试',10,'2026-01-02')")
    app = FastAPI()
    register_river_routes(app, market_db_path=path)
    client = TestClient(app)
    data = client.get("/api/limitup/calendar?days=5&end=2026-01-06")
    assert data.status_code == 200
    assert data.json()["end"] == "2026-01-06"
    assert all(day["trade_date"] <= "2026-01-06" for day in data.json()["days"])
    assert data.json()["days"][-1]["details"][0]["name"] == "历史股"
    assert client.get("/api/limitup/calendar?end=oops").status_code == 422
