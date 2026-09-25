from __future__ import annotations

from datetime import date

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.reports.daily_review import _coverage, _sw_l1_degradation_warning
from market_feature_store.sync import sync_akshare_sw_l1_daily as sw_sync
from scripts import check_daily_review_data


def _connect_test_db(path):
    def connect(read_only: bool = False):
        return duckdb.connect(str(path), read_only=read_only)

    return connect


def _init_test_db(path):
    def init_db():
        con = duckdb.connect(str(path))
        try:
            con.execute(db.SCHEMA_PATH.read_text(encoding="utf-8"))
        finally:
            con.close()

    return init_db


def test_sw_l1_sync_falls_back_to_fupanhui_aggregate_when_realtime_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    init_db = _init_test_db(db_path)
    connect = _connect_test_db(db_path)
    init_db()
    con = connect()
    try:
        con.executemany(
            """
            INSERT INTO fact_market_daily
                (trade_date, industry_1, industry_1_ratio, source)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("2026-07-09", "电子", 12.0, "test"),
                ("2026-07-10", "电子", 13.5, "test"),
            ],
        )
        # fact_sector_daily 是 VIEW，写入落 *_generation。snapshot_id='legacy'
        # 对应快照机制上线前的历史数据：当日无 published 快照时视图才放行。
        con.executemany(
            """
            INSERT INTO fact_sector_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 sw_l1, pct_chg, amount, diff_ratio, source)
            VALUES (?, 'legacy', ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-07-10", "A", "半导体", "电子", 2.0, 100.0, 18.0, "fupanhui"),
                ("2026-07-10", "B", "消费电子", "电子", -1.0, 300.0, -5.0, "fupanhui"),
                ("2026-07-10", "C", "软件", "计算机", 4.0, 600.0, 22.0, "fupanhui"),
            ],
        )
    finally:
        con.close()

    monkeypatch.setattr(sw_sync, "connect", connect)
    monkeypatch.setattr(sw_sync, "init_db", init_db)
    monkeypatch.setattr(
        sw_sync,
        "_fetch_sw_l1_codes",
        lambda: [
            {"code": "801080", "name": "电子"},
            {"code": "801750", "name": "计算机"},
        ],
    )
    monkeypatch.setattr(
        sw_sync,
        "_fetch_hist_by_code",
        lambda code, start, end: {
            date(2026, 7, 9): {
                "close": 100.0,
                "pre_close": 99.0,
                "pct_chg": 1.01,
                "amount": 10.0,
                "source": f"akshare:index_hist_sw:{code}",
            }
        },
    )

    def raise_empty_realtime():
        raise ValueError("Length mismatch: Expected axis has 0 elements")

    monkeypatch.setattr(sw_sync, "_fetch_realtime", raise_empty_realtime)
    monkeypatch.setattr(sw_sync.time, "sleep", lambda _seconds: None)

    stats = sw_sync.sync_akshare_sw_l1_daily(trade_date="2026-07-10", days=2)

    assert stats["degraded_rows"] == 2
    assert any(item["sw_l1"] == "realtime" for item in stats["failures"])
    con = connect(read_only=True)
    try:
        rows = con.execute(
            """
            SELECT sw_l1, pct_chg, amount, fupanhui_ratio, source
            FROM fact_sw_l1_daily
            WHERE trade_date = '2026-07-10'
            ORDER BY sw_l1
            """
        ).fetchall()
    finally:
        con.close()

    assert len(rows) == 2
    by_name = {row[0]: row[1:] for row in rows}
    pct_chg, amount, ratio, source = by_name["电子"]
    assert round(pct_chg, 4) == -0.25
    assert amount == 400.0
    assert ratio == 13.5
    assert source == "degraded_fupanhui_sw_l1_aggregate:sector_count=2"

    con = connect(read_only=True)
    try:
        coverage = _coverage(con, "2026-07-10")
        sw_l1_status = {row[0]: row[4] for row in coverage}["fact_sw_l1_daily"]
        warning = _sw_l1_degradation_warning(con, "2026-07-10")
    finally:
        con.close()
    assert sw_l1_status == "OK（降级 2/2：复盘会聚合代理）"
    assert warning is not None
    assert "不可等同于申万指数官方口径" in warning


def test_sw_l1_sync_stops_when_industry_has_no_data_at_all(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    init_db = _init_test_db(db_path)
    connect = _connect_test_db(db_path)
    init_db()
    con = connect()
    try:
        con.execute(
            "INSERT INTO fact_market_daily (trade_date, source) VALUES ('2026-07-10', 'test')"
        )
    finally:
        con.close()

    monkeypatch.setattr(sw_sync, "connect", connect)
    monkeypatch.setattr(sw_sync, "init_db", init_db)
    monkeypatch.setattr(
        sw_sync, "_fetch_sw_l1_codes", lambda: [{"code": "801980", "name": "美容护理"}]
    )
    monkeypatch.setattr(sw_sync, "_fetch_hist_by_code", lambda code, start, end: {})

    def raise_realtime():
        raise ValueError("realtime unavailable")

    monkeypatch.setattr(sw_sync, "_fetch_realtime", raise_realtime)
    monkeypatch.setattr(sw_sync.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="历史/实时/板块代理全部不可用"):
        sw_sync.sync_akshare_sw_l1_daily(trade_date="2026-07-10", days=1)

    con = connect(read_only=True)
    try:
        count, = con.execute(
            "SELECT COUNT(*) FROM fact_sw_l1_daily WHERE trade_date = '2026-07-10'"
        ).fetchone()
    finally:
        con.close()
    assert count == 0


def test_data_only_gate_does_not_require_a_report_file(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    init_db = _init_test_db(db_path)
    connect = _connect_test_db(db_path)
    init_db()
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO fact_market_daily (trade_date, source)
            VALUES ('2026-07-10', 'test')
            """
        )
        con.execute(
            """
            INSERT INTO fact_sw_l1_daily
                (trade_date, sw_l1_code, sw_l1, close, pct_chg, amount, source)
            VALUES ('2026-07-10', '801080', '电子', 100.0, 1.0, 10.0, 'akshare:index_hist_sw:801080')
            """
        )
        # 板块行情闸门已从「dim_sector 全覆盖」改成「相邻交易日名称连续性」，
        # 当日零板块行情会直接判 INCOMPLETE。本例只验证 data_only 不需要报告
        # 文件，补一行最小数据避开这条无关闸门。
        con.execute(
            """
            INSERT INTO fact_sector_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 sw_l1, pct_chg, amount, diff_ratio, source)
            VALUES ('2026-07-10', 'legacy', 'A', '半导体', '电子', 2.0, 100.0, 18.0, 'test')
            """
        )
    finally:
        con.close()

    monkeypatch.setattr(check_daily_review_data, "connect", connect)
    monkeypatch.setattr(check_daily_review_data, "TABLES", ["fact_sw_l1_daily"])
    monkeypatch.setattr(check_daily_review_data, "MARKET_FIELDS", [])
    monkeypatch.setattr(check_daily_review_data, "SW_L1_COUNT", 1)
    monkeypatch.chdir(tmp_path)

    assert check_daily_review_data.main("2026-07-10", data_only=True) == 0
    assert check_daily_review_data.main("2026-07-10", data_only=False) == 1


def test_realtime_amount_is_converted_from_million_to_yi():
    """akshare 实时接口成交额是百万元，hist 是亿；表里统一亿（2026-09-07 全A/申万比 0.0102 抓出的坑）。"""
    from market_feature_store.sync.sync_akshare_sw_l1_daily import realtime_amount_to_yi

    assert abs(realtime_amount_to_yi(506527.36) - 5065.2736) < 1e-6
    assert realtime_amount_to_yi(None) is None
