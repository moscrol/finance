from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from intelligence.services.run_store import RunStore
from intelligence.services.us_stock_drawdown import (
    AlpacaDailyBarClient,
    AlpacaMarketDataError,
    DailyBar,
    DrawdownReport,
    DrawdownRow,
    MissingAlpacaCredentials,
    UsStockDrawdownService,
    calculate_max_drawdown,
    parse_trading_day_window,
)
from intelligence.workbench_skills.contracts import SkillExecutionContext
from intelligence.workbench_skills.us_ai_drawdown import UsAiDrawdownSkill


def _write_watchlist(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "测试阵营",
                "symbols": [
                    {
                        "ticker": "AAA",
                        "name": "Alpha",
                        "group": "芯片",
                        "enabled": True,
                    },
                    {
                        "ticker": "BBB",
                        "name": "Beta",
                        "group": "平台",
                        "enabled": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _context(tmp_path: Path, store: RunStore, run_id: str) -> SkillExecutionContext:
    return SkillExecutionContext(
        query="生成美股 AI 回撤榜",
        task_type="ask",
        user_id="demo",
        run_id=run_id,
        conversation_id="conversation",
        repo_root=tmp_path,
        run_store=store,
    )


def test_calculate_max_drawdown_tracks_the_actual_peak_and_trough() -> None:
    bars = [
        DailyBar(date(2026, 1, 2), 100),
        DailyBar(date(2026, 1, 5), 120),
        DailyBar(date(2026, 1, 6), 110),
        DailyBar(date(2026, 1, 7), 90),
        DailyBar(date(2026, 1, 8), 130),
    ]

    result = calculate_max_drawdown(bars, window=5)

    assert result is not None
    assert result.max_drawdown_pct == -25.0
    assert result.daily_change_pct == 44.44
    assert result.return_5d_pct is None
    assert result.return_10d_pct is None
    assert result.peak_date == "2026-01-05"
    assert result.peak_price == 120
    assert result.trough_date == "2026-01-07"
    assert result.trough_price == 90
    assert result.trading_days == 5
    assert result.status == "完整"


def test_calculate_max_drawdown_uses_last_n_deduplicated_trading_days() -> None:
    bars = [
        DailyBar(date(2026, 1, 2), 80),
        DailyBar(date(2026, 1, 2), 100),
        DailyBar(date(2026, 1, 5), 90),
        DailyBar(date(2026, 1, 6), 95),
    ]

    result = calculate_max_drawdown(bars, window=2)

    assert result is not None
    assert result.start_date == "2026-01-05"
    assert result.end_date == "2026-01-06"
    assert result.max_drawdown_pct == 0
    assert result.daily_change_pct == 5.56


def test_calculate_max_drawdown_includes_5d_and_10d_returns() -> None:
    bars = [
        DailyBar(date(2026, 1, day), 99 + day)
        for day in range(1, 13)
    ]

    result = calculate_max_drawdown(bars, window=10)

    assert result is not None
    assert result.daily_change_pct == 0.91
    assert result.return_5d_pct == 4.72
    assert result.return_10d_pct == 9.9


def test_parse_trading_day_window_defaults_and_bounds() -> None:
    assert parse_trading_day_window("美股 AI 回撤榜") == 30
    assert parse_trading_day_window("最近 60 个交易日最大回撤排序") == 60
    assert parse_trading_day_window("最近 999 个交易日") == 30


def test_alpaca_client_normalizes_multi_symbol_bars() -> None:
    captured: dict[str, object] = {}

    def transport(url: str, headers: dict[str, str]) -> bytes:
        captured["url"] = url
        captured["headers"] = headers
        return json.dumps(
            {
                "bars": {
                    "AAA": [
                        {"t": "2026-01-02T05:00:00Z", "c": 100.5},
                        {"t": "bad", "c": 101},
                    ],
                    "BBB": [{"t": "2026-01-02T05:00:00Z", "c": 50}],
                },
                "next_page_token": None,
            }
        ).encode()

    client = AlpacaDailyBarClient(
        key_id="test-key",
        secret_key="test-secret",
        transport=transport,
    )
    result = client.fetch(
        ("AAA", "BBB"),
        start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    assert result["AAA"] == (DailyBar(date(2026, 1, 2), 100.5),)
    assert result["BBB"] == (DailyBar(date(2026, 1, 2), 50.0),)
    assert "symbols=AAA%2CBBB" in str(captured["url"])
    assert captured["headers"] == {
        "Accept": "application/json",
        "APCA-API-KEY-ID": "test-key",
        "APCA-API-SECRET-KEY": "test-secret",
    }


def test_service_ranks_drawdowns_and_falls_back_to_cache(tmp_path: Path) -> None:
    watchlist = _write_watchlist(tmp_path / "watchlist.json")
    response = {
        "bars": {
            "AAA": [
                {"t": "2026-01-02T05:00:00Z", "c": 100},
                {"t": "2026-01-05T05:00:00Z", "c": 120},
                {"t": "2026-01-06T05:00:00Z", "c": 90},
            ],
            "BBB": [
                {"t": "2026-01-02T05:00:00Z", "c": 50},
                {"t": "2026-01-05T05:00:00Z", "c": 55},
                {"t": "2026-01-06T05:00:00Z", "c": 50},
            ],
        },
        "next_page_token": None,
    }
    client = AlpacaDailyBarClient(
        key_id="key",
        secret_key="secret",
        transport=lambda _url, _headers: json.dumps(response).encode(),
    )
    cache_path = tmp_path / "cache" / "bars.json"
    now = datetime(2026, 1, 7, 15, tzinfo=timezone.utc)
    service = UsStockDrawdownService(
        watchlist_path=watchlist,
        cache_path=cache_path,
        client=client,
    )

    report = service.run(window=3, now=now)

    assert [row.ticker for row in report.rows] == ["AAA", "BBB"]
    assert [row.rank for row in report.rows] == [1, 2]
    assert [row.max_drawdown_pct for row in report.rows] == [-25.0, -9.09]
    assert [row.daily_change_pct for row in report.rows] == [-25.0, -9.09]
    assert all(row.return_5d_pct is None for row in report.rows)
    assert all(row.return_10d_pct is None for row in report.rows)
    assert report.as_of == "2026-01-06"
    assert report.start_date == "2026-01-02"
    assert cache_path.exists()

    cached_service = UsStockDrawdownService(
        watchlist_path=watchlist,
        cache_path=cache_path,
        client=AlpacaDailyBarClient(key_id="", secret_key=""),
    )
    cached = cached_service.run(window=3, now=now + timedelta(minutes=30))

    assert cached.rows == report.rows
    assert cached.source.endswith("本地缓存")
    assert cached.warnings == (
        "Alpaca 刷新失败，当前展示最近一次本地缓存。",
    )


def test_service_marks_missing_and_incomplete_symbols(tmp_path: Path) -> None:
    watchlist = _write_watchlist(tmp_path / "watchlist.json")
    response = {
        "bars": {
            "AAA": [
                {"t": "2026-01-02T05:00:00Z", "c": 100},
                {"t": "2026-01-05T05:00:00Z", "c": 90},
            ],
            "BBB": [],
        },
        "next_page_token": None,
    }
    service = UsStockDrawdownService(
        watchlist_path=watchlist,
        cache_path=tmp_path / "cache.json",
        client=AlpacaDailyBarClient(
            key_id="key",
            secret_key="secret",
            transport=lambda _url, _headers: json.dumps(response).encode(),
        ),
    )

    report = service.run(
        window=3,
        now=datetime(2026, 1, 7, 15, tzinfo=timezone.utc),
    )

    assert report.rows[0].ticker == "AAA"
    assert report.rows[0].status == "交易日不足"
    assert report.rows[1].ticker == "BBB"
    assert report.rows[1].max_drawdown_pct is None
    assert report.rows[1].status == "有效交易日不足"
    assert report.warnings == (
        "以下标的数据不足，未参与排序：BBB",
        "以下标的不足完整窗口：AAA",
    )


def test_service_raises_api_error_when_no_cache_is_available(
    tmp_path: Path,
) -> None:
    def failing_transport(_url: str, _headers: dict[str, str]) -> bytes:
        raise AlpacaMarketDataError("provider unavailable")

    service = UsStockDrawdownService(
        watchlist_path=_write_watchlist(tmp_path / "watchlist.json"),
        cache_path=tmp_path / "cache.json",
        client=AlpacaDailyBarClient(
            key_id="key",
            secret_key="secret",
            transport=failing_transport,
        ),
    )

    with pytest.raises(AlpacaMarketDataError, match="provider unavailable"):
        service.run(
            window=3,
            now=datetime(2026, 1, 7, 15, tzinfo=timezone.utc),
        )


def test_skill_emits_structured_table_and_artifact(tmp_path: Path) -> None:
    config_dir = tmp_path / "intelligence" / "config"
    config_dir.mkdir(parents=True)
    _write_watchlist(config_dir / "us_ai_watchlist.json")
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("q", "ask")
    report = DrawdownReport(
        window=30,
        rows=(
            DrawdownRow(
                rank=1,
                ticker="AAA",
                name="Alpha",
                group="芯片",
                max_drawdown_pct=-25,
                daily_change_pct=2.5,
                return_5d_pct=-3.25,
                return_10d_pct=8.75,
                peak_date="2026-01-02",
                peak_price=120,
                trough_date="2026-01-20",
                trough_price=90,
                start_date="2025-12-08",
                end_date="2026-01-20",
                trading_days=30,
                status="完整",
            ),
        ),
        as_of="2026-01-20",
        start_date="2025-12-08",
        source="Alpaca Market Data（IEX、复权日线）",
        warnings=(),
        fetched_at="2026-01-21T00:00:00+00:00",
    )

    with patch.object(UsStockDrawdownService, "run", return_value=report):
        output = UsAiDrawdownSkill().execute(_context(tmp_path, store, run.run_id))

    assert output.as_of == "2026-01-20"
    assert output.answer_contract is not None
    assert output.modules[0]["table"]["rows"][0]["max_drawdown"] == "-25.00%"
    assert output.modules[0]["table"]["rows"][0]["daily_change"] == "2.50%"
    assert output.modules[0]["table"]["rows"][0]["return_5d"] == "-3.25%"
    assert output.modules[0]["table"]["rows"][0]["return_10d"] == "8.75%"
    assert output.citations[0]["evidence_layer"] == "market_data"
    assert output.raw_result_ref is not None
    persisted = json.loads(
        (store.run_dir(run.run_id) / output.raw_result_ref).read_text(
            encoding="utf-8"
        )
    )
    assert persisted["rows"][0]["ticker"] == "AAA"


def test_skill_degrades_without_credentials_or_cache(tmp_path: Path) -> None:
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("q", "ask")

    with patch.object(
        UsStockDrawdownService,
        "run",
        side_effect=MissingAlpacaCredentials("missing"),
    ):
        output = UsAiDrawdownSkill().execute(_context(tmp_path, store, run.run_id))

    assert output.answer_contract is None
    assert output.modules[0]["status"] == "degraded"
    assert output.modules[0]["table"] is None
    assert output.warnings == [
        "未配置 Alpaca 行情凭证，且没有可用的本地缓存。"
    ]
