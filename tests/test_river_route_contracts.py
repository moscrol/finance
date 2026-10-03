"""HTTP projections must preserve River's missing-data and source contracts."""
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence.api import river_routes
from intelligence.services.river_query import scan_cross_section

DAYS = ["2026-08-03", "2026-08-04", "2026-08-05"]


@pytest.fixture()
def market(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.duckdb"
    monkeypatch.setattr(river_routes, "river_svc_checkpoints_path", lambda: tmp_path / "absent.jsonl")
    with duckdb.connect(str(path)) as con:
        con.execute((Path(__file__).resolve().parents[1] / "market_feature_store/schema.sql").read_text())
        con.executemany("INSERT INTO fact_market_daily (trade_date) VALUES (?)", [[d] for d in DAYS])
        con.executemany("""INSERT INTO fact_sector_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount)
            VALUES (?, 'legacy', 'S1', '测试板块', 10, 100)""", [[DAYS[0]], [DAYS[2]]])
        con.executemany("""INSERT INTO fact_stock_daily
            (trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount)
            VALUES (?, '600001.SH', '测试股', ?, ?, ?, 100)""",
            [[DAYS[0], 110, 100, 10], [DAYS[1], 121, 110, 10], [DAYS[2], 121, 121, 0]])
        con.executemany("""INSERT INTO fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
             stock_ts_code, stock_name, amount, pct_chg, fund_flow_1d, source)
            VALUES (?, 'legacy', 'S1', '测试板块', ?, ?, 100, NULL, ?, ?)""",
            [[DAYS[2], "600001.SH", "测试一", 2, "local:stitch"],
             [DAYS[2], "600002.SH", "测试二", 3, "fupanhui"]])
    app = FastAPI()
    river_routes.register_river_routes(app, market_db_path=path)
    with TestClient(app) as client:
        yield path, client


def range_result(client, entity="测试板块", **params):
    response = client.get("/api/river/range", params={
        "entity": entity, "start": DAYS[0], "end": DAYS[-1], **params,
    })
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("gap", ["missing_row", "provider_switch", "duplicate_date"])
def test_strict_range_does_not_redraw_rejected_aggregate(market, gap):
    path, client = market
    if gap != "missing_row":
        with duckdb.connect(str(path)) as con:
            con.execute("""INSERT INTO fact_sector_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount)
                VALUES (?, 'legacy', 'S1', '测试板块', 10, 100)""", [DAYS[1]])
            if gap == "provider_switch":
                con.execute("UPDATE fact_sector_daily_generation SET sector_ts_code='S2' WHERE trade_date=?", [DAYS[-1]])
            else:
                con.execute("""INSERT INTO fact_sector_daily_generation
                    (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount)
                    VALUES (?, 'legacy', 'S2', '测试板块', 15, 100)""", [DAYS[1]])
    result = range_result(client, require_complete=True)
    assert result["values"] and all(value is None for value in result["values"].values())
    assert result["curve"] == []


@pytest.mark.parametrize("null_row", [False, True])
def test_sector_curve_does_not_bridge_unknown_returns(market, null_row):
    path, client = market
    if null_row:
        with duckdb.connect(str(path)) as con:
            con.execute("""INSERT INTO fact_sector_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount)
                VALUES (?, 'legacy', 'S1', '测试板块', NULL, 100)""", [DAYS[1]])
    curve = range_result(client)["curve"]
    assert [point["date"] for point in curve] == DAYS
    assert [point["cum_pct"] for point in curve] == [10, None, None]
    estimate = range_result(client)
    assert estimate["values"]["cumulative_return_pct"] == 21
    assert estimate["trustworthy"] is False
    assert any("估计" in caveat for caveat in estimate["caveats"])
    strict = range_result(client, require_complete=True)
    assert strict["curve"] == []
    assert all(value is None for value in strict["values"].values())


@pytest.mark.parametrize("missing_baseline", [False, True])
def test_stock_curve_uses_the_same_pre_close_baseline_as_aggregate(market, missing_baseline):
    path, client = market
    if missing_baseline:
        with duckdb.connect(str(path)) as con:
            con.execute("UPDATE fact_stock_daily SET pre_close=NULL WHERE trade_date=?", [DAYS[0]])
    result = range_result(client, entity="600001.SH", kind="stock")
    assert result["curve"][-1]["cum_pct"] == result["values"]["cumulative_return_pct"]
    assert result["curve"][0]["cum_pct"] == (0 if missing_baseline else 10)


def test_stock_curve_cannot_invent_a_baseline_when_all_pre_close_values_are_missing(market):
    path, client = market
    with duckdb.connect(str(path)) as con:
        con.execute("UPDATE fact_stock_daily SET pre_close=NULL")
    result = range_result(client, entity="600001.SH", kind="stock")
    assert any(gap["metric"] == "cumulative_return_pct" for gap in result["gaps"])
    assert all(point["cum_pct"] is None for point in result["curve"])


def timeline_last(client):
    response = client.get("/api/river/timeline", params={"entity": "测试板块", "start": DAYS[0], "end": DAYS[-1]})
    assert response.status_code == 200, response.text
    return response.json()["days"][-1]


@pytest.mark.parametrize("known_pct", [None, 0, 10])
def test_timeline_breadth_counts_only_known_pct_and_reports_coverage(market, known_pct):
    path, client = market
    if known_pct is not None:
        with duckdb.connect(str(path)) as con:
            con.execute("UPDATE fact_sector_stock_daily_generation SET pct_chg=? WHERE stock_ts_code='600001.SH'", [known_pct])
    stock = timeline_last(client)["stock"]
    assert stock["n_stocks"] == 2
    assert stock["n_with_pct"] == (0 if known_pct is None else 1)
    if known_pct is None:
        assert [stock[key] for key in ("n_up", "n_down", "n_limit_like")] == [None, None, None]
    else:
        assert [stock[key] for key in ("n_up", "n_down", "n_limit_like")] == [int(known_pct > 0), 0, int(known_pct >= 9.5)]


@pytest.mark.parametrize("single_source", [False, True])
def test_timeline_capital_agrees_with_existing_scan_source_caliber(market, single_source):
    path, client = market
    if single_source:
        with duckdb.connect(str(path)) as con:
            con.execute("UPDATE fact_sector_stock_daily_generation SET source='local:stitch'")
    capital = timeline_last(client)["capital"]
    scan = scan_cross_section(DAYS[-1], db_path=path)[0]
    assert capital["fund_flow_1d"] == scan.fund_flow_1d
    assert capital["fund_caliber"] == scan.fund_caliber
    assert capital["n_with_fund"] == capital["n_stocks"] == 2
