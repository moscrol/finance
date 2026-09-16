from __future__ import annotations

from pathlib import Path

import duckdb

from market_feature_store import db
from market_feature_store.sync import sync_fupanhui_theme_flow_daily as theme_flow
from market_feature_store.sync.sync_theme_capital_from_baskets import (
    sync_from_sector_baskets,
)

# 成分行口径 local:stitch(东财主力净额) → 面板 source
SOURCE = "local:sector-basket:em-main-net"


def _connect(path: Path):
    def connect(read_only: bool = False):
        return duckdb.connect(str(path), read_only=read_only)

    return connect


def _init(path: Path):
    def init_db(con=None):
        own = con is None
        con = con or duckdb.connect(str(path))
        try:
            con.execute(db.SCHEMA_PATH.read_text(encoding="utf-8"))
        finally:
            if own:
                con.close()

    return init_db


def _seed_sector_stocks(con: duckdb.DuckDBPyConnection, trade_date: str) -> None:
    con.executemany(
        """
        INSERT INTO fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
             stock_ts_code, stock_name, amount, fund_flow_1d, source)
        VALUES (?, 'legacy', ?, ?, ?, ?, ?, ?, 'local:stitch')
        """,
        [
            (trade_date, "990001.FP", "AI硬件", "300308.XSHE", "中际旭创", 100.0, 50.0),
            (trade_date, "990001.FP", "AI硬件", "300502.XSHE", "新易盛", 80.0, -20.0),
            (trade_date, "990002.FP", "有色", "000001.XSHE", "平安银行", 10.0, 5.0),
        ],
    )


def test_sector_baskets_sum_fund_flow_by_published_view(tmp_path, monkeypatch):
    db_path = tmp_path / "m.duckdb"
    init_db = _init(db_path)
    connect = _connect(db_path)
    init_db()
    con = connect()
    try:
        _seed_sector_stocks(con, "2026-09-03")
    finally:
        con.close()

    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    monkeypatch.setattr(baskets, "connect", connect)
    monkeypatch.setattr(baskets, "init_db", init_db)

    result = sync_from_sector_baskets("2026-09-03")
    assert result["panels"] == 2
    assert result["source"] == SOURCE

    rows = {
        code: (name, fund, amount, count, src)
        for code, name, fund, amount, count, src in connect(read_only=True).execute(
            """
            SELECT theme_code, theme_name, total_fund, total_amount, stock_count, source
            FROM fact_theme_flow_daily WHERE trade_date = '2026-09-03'
            ORDER BY theme_code
            """
        ).fetchall()
    }
    assert rows["990001.FP"][0] == "AI硬件"
    assert rows["990001.FP"][1] == 30.0
    assert rows["990001.FP"][2] == 180.0
    assert rows["990001.FP"][3] == 2
    assert rows["990001.FP"][4] == SOURCE
    assert rows["990002.FP"][1] == 5.0


def test_theme_flow_falls_back_when_fupanhui_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "m.duckdb"
    init_db = _init(db_path)
    connect = _connect(db_path)
    init_db()
    con = connect()
    try:
        _seed_sector_stocks(con, "2026-09-09")
    finally:
        con.close()

    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    monkeypatch.setattr(baskets, "connect", connect)
    monkeypatch.setattr(baskets, "init_db", init_db)
    monkeypatch.setattr(theme_flow, "connect", connect)
    monkeypatch.setattr(theme_flow, "init_db", init_db)
    monkeypatch.setattr(theme_flow.fs, "get_theme_panels", lambda _d: [])

    result = theme_flow.sync("2026-09-09")
    assert result["panels"] == 2
    assert result["source"] == SOURCE
    src = connect(read_only=True).execute(
        "SELECT DISTINCT source FROM fact_theme_flow_daily WHERE trade_date='2026-09-09'"
    ).fetchone()[0]
    assert src == SOURCE


def test_theme_flow_keeps_fupanhui_when_panels_exist(tmp_path, monkeypatch):
    db_path = tmp_path / "m.duckdb"
    init_db = _init(db_path)
    connect = _connect(db_path)
    init_db()
    called = {"baskets": 0}

    def _boom(*_a, **_k):
        called["baskets"] += 1
        raise AssertionError("有复盘会面板时不该走篮子")

    monkeypatch.setattr(theme_flow, "connect", connect)
    monkeypatch.setattr(theme_flow, "init_db", init_db)
    monkeypatch.setattr(theme_flow, "sync_from_sector_baskets", _boom)
    monkeypatch.setattr(
        theme_flow.fs,
        "get_theme_panels",
        lambda _d: [
            {
                "theme_code": "T1",
                "theme_name": "编辑格子",
                "total_fund": 9.0,
                "total_amount": 1.0,
                "stock_count": 3,
            }
        ],
    )

    result = theme_flow.sync("2026-09-02")
    assert result["panels"] == 1
    assert result["source"] == theme_flow.FUPANHUI_SOURCE
    assert called["baskets"] == 0
    row = connect(read_only=True).execute(
        "SELECT theme_name, total_fund, source FROM fact_theme_flow_daily "
        "WHERE trade_date='2026-09-02'"
    ).fetchone()
    assert row == ("编辑格子", 9.0, theme_flow.FUPANHUI_SOURCE)
