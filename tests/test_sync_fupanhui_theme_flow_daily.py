from __future__ import annotations

from datetime import date

import duckdb

from market_feature_store import db
from market_feature_store.sync import sync_fupanhui_theme_flow_daily as tf_sync


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


def _rows(db_path):
    con = duckdb.connect(str(db_path))
    try:
        return con.execute(
            "SELECT trade_date, theme_code, theme_name, total_fund, total_amount, "
            "stock_count, source FROM fact_theme_flow_daily ORDER BY theme_code"
        ).fetchall()
    finally:
        con.close()


def test_sync_writes_fupanhui_panels_when_available(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    monkeypatch.setattr(tf_sync, "connect", _connect_test_db(db_path))
    monkeypatch.setattr(tf_sync, "init_db", _init_test_db(db_path))
    monkeypatch.setattr(
        tf_sync,
        "_fetch_fupanhui_panels",
        lambda trade_date: [
            {"theme_code": "T001", "theme_name": "液冷", "total_fund": 5.1,
             "total_amount": 88.0, "stock_count": 12},
        ],
    )

    def _boom():
        raise AssertionError("fupanhui 有数据时不该调用 AKShare 兜底")

    monkeypatch.setattr(tf_sync, "_fetch_akshare_concept_flow", _boom)

    result = tf_sync.sync("2026-09-10")

    assert result == {"panels": 1, "source": tf_sync.FUPANHUI_SOURCE, "fupanhui_error": None}
    rows = _rows(db_path)
    assert rows == [(date(2026, 9, 10), "T001", "液冷", 5.1, 88.0, 12, tf_sync.FUPANHUI_SOURCE)]


def test_sync_falls_back_to_akshare_when_fupanhui_fails_on_today(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    monkeypatch.setattr(tf_sync, "connect", _connect_test_db(db_path))
    monkeypatch.setattr(tf_sync, "init_db", _init_test_db(db_path))
    monkeypatch.setattr(tf_sync, "_is_shanghai_today", lambda trade_date: True)

    def _fupanhui_401(trade_date):
        raise RuntimeError("FupanhuiError: 公开 API HTTP 401")

    monkeypatch.setattr(tf_sync, "_fetch_fupanhui_panels", _fupanhui_401)
    monkeypatch.setattr(
        tf_sync,
        "_fetch_akshare_concept_flow",
        lambda: [
            {"theme_code": "ak:固态电池", "theme_name": "固态电池", "total_fund": 3.2,
             "total_amount": None, "stock_count": 40},
        ],
    )

    result = tf_sync.sync("2026-09-10")

    assert result["panels"] == 1
    assert result["source"] == tf_sync.AKSHARE_SOURCE
    assert "401" in result["fupanhui_error"]
    rows = _rows(db_path)
    assert rows == [
        (date(2026, 9, 10), "ak:固态电池", "固态电池", 3.2, None, 40, tf_sync.AKSHARE_SOURCE),
    ]


def test_sync_skips_akshare_fallback_for_non_today_backfill(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    monkeypatch.setattr(tf_sync, "connect", _connect_test_db(db_path))
    monkeypatch.setattr(tf_sync, "init_db", _init_test_db(db_path))
    monkeypatch.setattr(tf_sync, "_is_shanghai_today", lambda trade_date: False)

    def _fupanhui_401(trade_date):
        raise RuntimeError("FupanhuiError: 公开 API HTTP 401")

    monkeypatch.setattr(tf_sync, "_fetch_fupanhui_panels", _fupanhui_401)

    def _boom():
        raise AssertionError("回补历史日不该去碰 AKShare 的『即时』快照")

    monkeypatch.setattr(tf_sync, "_fetch_akshare_concept_flow", _boom)

    result = tf_sync.sync("2026-08-15")

    assert result == {"panels": 0, "source": None, "fupanhui_error": "RuntimeError: FupanhuiError: 公开 API HTTP 401"}


def test_sync_reports_both_errors_when_akshare_also_fails(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    monkeypatch.setattr(tf_sync, "connect", _connect_test_db(db_path))
    monkeypatch.setattr(tf_sync, "init_db", _init_test_db(db_path))
    monkeypatch.setattr(tf_sync, "_is_shanghai_today", lambda trade_date: True)
    monkeypatch.setattr(
        tf_sync, "_fetch_fupanhui_panels",
        lambda trade_date: (_ for _ in ()).throw(RuntimeError("401")),
    )
    monkeypatch.setattr(
        tf_sync, "_fetch_akshare_concept_flow",
        lambda: (_ for _ in ()).throw(ConnectionError("network down")),
    )

    result = tf_sync.sync("2026-09-10")

    assert result["panels"] == 0
    assert result["source"] is None
    assert "401" in result["fupanhui_error"]
    assert "network down" in result["akshare_error"]
