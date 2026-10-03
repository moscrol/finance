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


@pytest.mark.parametrize("null_row", [False, True])
def test_kline_nav_does_not_resume_after_an_unknown_sector_return(market, null_row):
    path, client = market
    if null_row:
        with duckdb.connect(str(path)) as con:
            con.execute("""INSERT INTO fact_sector_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount)
                VALUES (?, 'legacy', 'S1', '测试板块', NULL, 100)""", [DAYS[1]])
    response = client.get("/api/river/kline", params={
        "entity": "S1", "start": DAYS[0], "end": DAYS[-1],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert [row["entity_pct"] for row in result["days"]] == [10, None, 10]
    assert [row["entity_nav"] for row in result["days"]] == [1.1, None, None]
    assert result["entity"]["coverage"] == 0.667
    assert "缺" in result["entity"]["note"]


@pytest.mark.parametrize("entity, selected_code, sector_pct", [
    ("S1", "S1", 10), ("S2", "S2", 20), ("测试板块", "S1", 10),
])
def test_timeline_uses_one_sector_code_per_day_for_market_and_constituents(
    market, entity, selected_code, sector_pct,
):
    path, client = market
    with duckdb.connect(str(path)) as con:
        con.execute("DELETE FROM fact_sector_stock_daily_generation")
        con.execute("""INSERT INTO fact_sector_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount)
            VALUES (?, 'legacy', 'S2', '测试板块', 20, 100)""", [DAYS[-1]])
        con.executemany("""INSERT INTO fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
             stock_ts_code, stock_name, pct_chg, amount, fund_flow_1d, source)
            VALUES (?, 'legacy', ?, '测试板块', '600001.SH', '同一成分股', 10, 100, 2, 'local:stitch')""",
            [[DAYS[-1], "S1"], [DAYS[-1], "S2"]])
    response = client.get("/api/river/timeline", params={
        "entity": entity, "start": DAYS[0], "end": DAYS[-1],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    last = result["days"][-1]
    assert last["market"]["sector_code"] == selected_code
    assert last["market"]["sector_pct"] == sector_pct
    assert last["capital"]["fund_flow_1d"] == 2
    assert last["capital"]["n_with_fund"] == last["capital"]["n_stocks"] == 1
    assert last["stock"]["n_stocks"] == last["stock"]["n_with_pct"] == 1


@pytest.mark.parametrize("entity, registered_alias, expected_codes, expected_funds", [
    ("测试板块", False, ["S1", None, "S2"], [2, None, 3]),
    ("S2", False, [None, None, "S2"], [None, None, 3]),
    ("S2", True, ["S1", None, "S2"], [2, None, 3]),
])
def test_timeline_keeps_daily_provider_selection_across_code_changes(
    market, entity, registered_alias, expected_codes, expected_funds,
):
    path, client = market
    with duckdb.connect(str(path)) as con:
        con.execute("UPDATE fact_sector_daily_generation SET sector_ts_code='S2' WHERE trade_date=?", [DAYS[-1]])
        if registered_alias:
            con.execute("""INSERT INTO config_sector_alias
                (alias, sector_ts_code, sector_name, confidence) VALUES ('S1', 'S2', '测试板块', 1)""")
        con.execute("DELETE FROM fact_sector_stock_daily_generation")
        # The other provider has constituent rows too; only the day's selected market code applies.
        con.executemany("""INSERT INTO fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
             stock_ts_code, stock_name, pct_chg, amount, fund_flow_1d, source)
            VALUES (?, 'legacy', ?, '测试板块', '600001.SH', '同一成分股', 10, 100, ?, 'local:stitch')""",
            [[day, code, fund] for day in [DAYS[0], DAYS[-1]] for code, fund in [("S1", 2), ("S2", 3)]])
        con.executemany("""INSERT INTO fact_theme_limit_heat_daily
            (trade_date, sector_ts_code, sector_name, dimension, scope, limit_up_count)
            VALUES (?, ?, '测试板块', 'concept', 'all', ?)""",
            [[day, code, count] for day in [DAYS[0], DAYS[-1]] for code, count in [("S1", 2), ("S2", 3)]])
    response = client.get("/api/river/timeline", params={
        "entity": entity, "start": DAYS[0], "end": DAYS[-1],
    })
    assert response.status_code == 200, response.text
    days = response.json()["days"]
    assert [day["market"]["sector_code"] for day in days] == expected_codes
    assert [day["capital"]["fund_flow_1d"] if day["capital"] else None for day in days] == expected_funds
    assert [day["theme"]["limit_up_count"] if day["theme"] else None for day in days] == expected_funds
    assert [day["stock"]["n_stocks"] if day["stock"] else None for day in days] == [
        1 if code else None for code in expected_codes
    ]
