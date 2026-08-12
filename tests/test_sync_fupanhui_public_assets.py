from __future__ import annotations

import json

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.sync import sync_fupanhui_market_daily as market_sync
from market_feature_store.sync import sync_fupanhui_public_assets as assets


def _connect_test_db(path):
    def connect(read_only: bool = False):
        return duckdb.connect(str(path), read_only=read_only)

    return connect


def _init_test_db(path):
    def init_db(con=None):
        own = con is None
        con = duckdb.connect(str(path)) if own else con
        try:
            con.execute(db.SCHEMA_PATH.read_text(encoding="utf-8"))
        finally:
            if own:
                con.close()

    return init_db


@pytest.fixture
def patched_db(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    connect = _connect_test_db(db_path)
    init_db = _init_test_db(db_path)
    init_db()
    monkeypatch.setattr(assets, "connect", connect)
    monkeypatch.setattr(assets, "init_db", init_db)
    monkeypatch.setattr(market_sync, "connect", connect)
    monkeypatch.setattr(market_sync, "init_db", init_db)
    return connect


def test_keywords_json_from_summary_list():
    assert market_sync._keywords_json({"keywords": ["光纤光缆", "CPO"]}) == '["光纤光缆", "CPO"]'
    assert market_sync._keywords_json({"keywords": []}) is None
    assert market_sync._keywords_json({}) is None


def test_historical_mapping_and_leader_height_upsert(patched_db, monkeypatch):
    monkeypatch.setattr(
        assets.fs,
        "get_historical_mapping",
        lambda td: {
            "source_date": td,
            "similar_days": [
                {
                    "date": "2025-08-12",
                    "similarity": 0.81,
                    "external_cycle": "底部横盘阶段",
                    "external_cycle_day": 11,
                    "summary": "量能接近",
                }
            ],
        },
    )
    monkeypatch.setattr(
        assets.fs,
        "get_leader_ladder",
        lambda td: {
            "height_trend": [
                {
                    "trade_date": "2026-08-11",
                    "height": 6,
                    "leader_stock": {"ts_code": "600000.SH", "name": "浦发", "limit_times": 6, "fd_amount": 1.2},
                },
                {
                    "trade_date": "2026-08-12",
                    "height": 7,
                    "leader_stock": {"ts_code": "600721.SH", "name": "百花医药", "limit_times": 7, "fd_amount": 8349.9},
                },
            ]
        },
    )
    mapped = assets.sync_historical_mapping("2026-08-12")
    heights = assets.sync_leader_height("2026-08-12")
    assert mapped["rows"] == 1
    assert heights["rows"] == 2
    con = patched_db()
    try:
        row = con.execute(
            "SELECT similar_date, similarity FROM fact_historical_mapping WHERE source_date = DATE '2026-08-12'"
        ).fetchone()
        assert str(row[0]) == "2025-08-12"
        assert row[1] == pytest.approx(0.81)
        h = con.execute(
            "SELECT height, leader_ts_code FROM fact_leader_height_daily WHERE trade_date = DATE '2026-08-12'"
        ).fetchone()
        assert h[0] == 7
        assert h[1] == "600721.SH"
    finally:
        con.close()


def test_global_market_keys_by_requested_date(patched_db, monkeypatch):
    """接口若回写别的 trade_date，仍按请求日入库，避免回补互相覆盖。"""
    monkeypatch.setattr(
        assets.fs,
        "get_global_market",
        lambda td: {
            "trade_date": "2026-08-12",
            "source_trade_date": "2026-01-27",
            "data_stage": "final",
            "markets": [
                {"code": "DJI", "name": "道指", "market_group": "us", "close": 49003.41, "pct_chg": -0.83}
            ],
            "core_stocks": [
                {"ts_code": "AAPL", "name_cn": "苹果", "close": 100.0, "pct_chg": 1.0}
            ],
        },
    )
    out = assets.sync_global_market("2026-06-02")
    assert out["index_rows"] == 1
    assert out["stock_rows"] == 1
    con = patched_db()
    try:
        idx = con.execute(
            "SELECT CAST(trade_date AS VARCHAR), CAST(source_trade_date AS VARCHAR), close "
            "FROM fact_global_index_daily WHERE code = 'DJI'"
        ).fetchone()
        assert idx[0] == "2026-06-02"
        assert idx[1] == "2026-01-27"
        assert idx[2] == pytest.approx(49003.41)
        n_aug = con.execute(
            "SELECT COUNT(*) FROM fact_global_index_daily WHERE trade_date = DATE '2026-08-12'"
        ).fetchone()[0]
        assert n_aug == 0
    finally:
        con.close()


def test_kb_root_requires_explicit_flag(monkeypatch, tmp_path):
    kb = tmp_path / "knowledge-base-private"
    kb.mkdir()
    monkeypatch.setenv("KNOWLEDGE_BASE_ROOT", str(kb))
    monkeypatch.delenv("FUPANHUI_KB_NOTES", raising=False)
    assert assets._kb_root() is None
    monkeypatch.setenv("FUPANHUI_KB_NOTES", "1")
    assert assets._kb_root() == kb


def test_orchestrator_isolates_failures(patched_db, monkeypatch):
    monkeypatch.setattr(
        assets.fs,
        "get_historical_mapping",
        lambda td: {"source_date": td, "similar_days": [{"date": "2025-01-01", "similarity": 0.5}]},
    )

    def _boom(*_a, **_k):
        raise RuntimeError("upstream down")

    for name in (
        "get_leader_ladder",
        "get_global_market",
        "get_dragon_list",
        "get_regulation_logs",
        "get_regulation_pool",
        "get_core_stocks",
        "get_auction_dashboard",
        "get_news_events_timeline",
        "get_news_events_future",
        "get_reports_page",
        "get_fundamentals_list",
    ):
        monkeypatch.setattr(assets.fs, name, _boom)

    out = assets.sync("2026-08-12")
    assert out["ok"] is True
    assert "historical_mapping" in out["results"]
    assert out["results"]["historical_mapping"]["rows"] == 1
    assert "leader_height" in out["errors"]
    assert "dragon" in out["errors"]


def test_fundamentals_writes_graph_only_note(patched_db, tmp_path, monkeypatch):
    kb = tmp_path / "knowledge-base-private"
    (kb / "wiki" / "raw").mkdir(parents=True)
    monkeypatch.setattr(
        assets.fs,
        "get_fundamentals_list",
        lambda **_k: {
            "total": 1,
            "items": [{"document_pk": 439, "title": "SAF 产业链", "core_judgement": "政策催化"}],
        },
    )
    monkeypatch.setattr(
        assets.fs,
        "get_fundamentals_detail",
        lambda pk: {
            "document_pk": pk,
            "title": "可持续航空燃油（SAF）产业链全景分析报告",
            "produced_at": "2026-07-31T17:43:38+08:00",
            "workflow_name": "归因到产业全景概览分析",
            "core_judgement": {
                "core_theme": "SAF 商业化加速",
                "verification_points": "强制加注比例细则",
                "judgement_text": "产供销打通",
            },
            "linked_themes": [{"theme_name": "化工"}],
            "linked_sectors": [{"sector_name": "航空"}],
            "industry_overview": {
                "chain_segments": [{"chain_stage": "上游", "sub_segment_product": "UCO", "value_share": "60%"}],
                "companies": [
                    {
                        "company_name": "中国石化",
                        "stock_code": "600028.SH",
                        "chain_segment": "全产业链",
                        "industry_relation": "龙头企业",
                    }
                ],
            },
            "catalyst_timeline": [
                {"expected_date_text": "2026年8月", "event_name": "民航局会议", "possible_impact": "细则"}
            ],
        },
    )
    result = assets.sync_fundamentals(sleep=0, kb_root=kb)
    assert result["rows"] == 1
    assert result["kb_notes"] == 1
    notes = list((kb / "wiki" / "raw" / "fupanhui-fundamentals").glob("*.md"))
    assert len(notes) == 1
    text = notes[0].read_text(encoding="utf-8")
    assert "graph_only: true" in text
    assert "evidence_layer: \"L1\"" in text
    assert "中国石化" in text
    assert "强制加注比例细则" in text
    con = patched_db()
    try:
        row = con.execute(
            "SELECT title, core_theme, kb_path FROM fact_theme_fundamental_doc WHERE document_pk = 439"
        ).fetchone()
        assert "SAF" in row[0]
        assert row[1] == "SAF 商业化加速"
        assert row[2].endswith(".md")
    finally:
        con.close()


def test_market_overview_persists_keywords(patched_db, monkeypatch):
    monkeypatch.setattr(market_sync.fs, "get_latest_date", lambda: "2026-08-12")

    def fake_api_get(path, params=None, timeout=60):
        if path.endswith("/reviews/summary"):
            return {
                "trade_date": "2026-08-12",
                "content": "底部横盘",
                "keywords": ["光纤光缆", "CPO"],
                "external_cycle": "底部横盘阶段",
                "external_cycle_day": 11,
            }
        if path.endswith("/reviews/cycle"):
            return {"current_stage": "底部横盘阶段", "ice_point": {"is_ice_point": False}}
        return {
            "trade_date": "2026-08-12",
            "volume": {"total_amount": 100.0, "change_pct": -1.0, "ma20_amount": 110.0, "ma20_ratio": 90.0, "volume_status": "正常量能"},
            "sentiment": {"rise_count": 3000, "distribution": [{"label": "涨停", "value": 80, "type": "up-limit"}]},
            "industry_spread": {"top3_total_pct": 12.0, "top3_industries": [{"name": "电子", "ratio": 5.0}]},
            "strength": {"top5_avg_pct": 3.0, "strength_status": "强"},
        }

    monkeypatch.setattr(market_sync.fs, "api_get", fake_api_get)
    stats = market_sync.sync_fupanhui_market_overview(trade_date="2026-08-12", days=1)
    assert stats["rows_written"] == 1
    con = patched_db()
    try:
        kw = con.execute(
            "SELECT summary_keywords FROM fact_market_daily WHERE trade_date = DATE '2026-08-12'"
        ).fetchone()[0]
        assert json.loads(kw) == ["光纤光缆", "CPO"]
    finally:
        con.close()


def _stub_empty_daily_apis(monkeypatch):
    monkeypatch.setattr(assets.fs, "get_review_summary", lambda td: {"keywords": ["光纤"]})
    monkeypatch.setattr(
        assets.fs,
        "get_historical_mapping",
        lambda td: {"source_date": td, "similar_days": [{"date": "2025-01-01", "similarity": 0.4}]},
    )
    empty = lambda *_a, **_k: {}
    for name in (
        "get_leader_ladder",
        "get_global_market",
        "get_dragon_list",
        "get_regulation_logs",
        "get_regulation_pool",
        "get_core_stocks",
        "get_auction_dashboard",
        "get_news_events_timeline",
        "get_news_events_future",
    ):
        monkeypatch.setattr(assets.fs, name, empty)


def test_sync_range_aligns_to_market_calendar_and_skips_existing(patched_db, monkeypatch):
    con = patched_db()
    try:
        con.executemany(
            "INSERT INTO fact_market_daily (trade_date, source) VALUES (?, ?)",
            [("2026-08-11", "test"), ("2026-08-12", "test")],
        )
    finally:
        con.close()
    _stub_empty_daily_apis(monkeypatch)
    first = assets.sync_range("2026-08-11", "2026-08-12", sleep=0)
    assert first["calendar_days"] == 2
    assert first["per_task"]["historical_mapping"]["synced"] == 2
    assert first["per_task"]["keywords"]["synced"] == 2
    second = assets.sync_range("2026-08-11", "2026-08-12", sleep=0)
    assert second["per_task"]["historical_mapping"]["skipped"] == 2
    assert second["per_task"]["keywords"]["skipped"] == 2
    con = patched_db()
    try:
        n = con.execute("SELECT COUNT(*) FROM fact_historical_mapping").fetchone()[0]
        kw = con.execute(
            "SELECT COUNT(*) FROM fact_market_daily WHERE summary_keywords IS NOT NULL"
        ).fetchone()[0]
    finally:
        con.close()
    assert n == 2
    assert kw == 2
