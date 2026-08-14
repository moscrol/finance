from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from intelligence.services import external_market
from intelligence.services.provider_observability import ProviderTrace


def _provider_quotes(
    *,
    provider: str,
    trade_date: str,
    codes: tuple[str, ...] = ("DJI", "SPX", "IXIC"),
) -> external_market._ProviderQuotes:
    quotes = tuple(
        external_market.ExternalMarketQuote(
            code=code,
            name={"DJI": "道琼斯", "SPX": "标普500", "IXIC": "纳斯达克"}[
                code
            ],
            close=100.0 + index,
            pct_chg=0.1 + index,
            trade_date=trade_date,
            source=provider,
        )
        for index, code in enumerate(codes)
    )
    return external_market._ProviderQuotes(
        quotes=quotes,
        source_trade_date=trade_date,
        trace=ProviderTrace(
            provider=provider,
            capability="market_quotes",
            status="success",
            source_trade_date=trade_date,
            result_count=len(quotes),
        ),
    )


def test_requested_symbols_defaults_to_three_major_indices() -> None:
    assert external_market.requested_symbols("昨天美股的涨跌情况") == (
        "DJI",
        "SPX",
        "IXIC",
    )
    assert external_market.requested_symbols("昨日道指、QQQ、费半涨跌") == (
        "DJI",
        "SOX",
        "QQQ",
    )


def test_target_trade_date_uses_last_completed_us_session() -> None:
    now = datetime(2026, 7, 14, 14, 0, tzinfo=ZoneInfo("America/New_York"))

    assert external_market.target_trade_date("昨天美股涨跌", now=now).isoformat() == (
        "2026-07-13"
    )
    assert external_market.target_trade_date("美股最新行情", now=now).isoformat() == (
        "2026-07-13"
    )


def test_structured_market_data_avoids_finance_fallback(monkeypatch) -> None:
    structured = _provider_quotes(
        provider=external_market.FUPANHUI_PROVIDER,
        trade_date="2026-07-13",
    )
    monkeypatch.setattr(
        external_market,
        "fetch_fupanhui_global_market",
        lambda *args, **kwargs: structured,
    )

    def fail_finance(*args, **kwargs):
        raise AssertionError("finance fallback should not run")

    monkeypatch.setattr(
        external_market,
        "fetch_yahoo_finance_quotes",
        fail_finance,
    )
    result = external_market.resolve_external_market(
        "昨天美股的涨跌情况",
        now=datetime(
            2026,
            7,
            14,
            14,
            0,
            tzinfo=ZoneInfo("America/New_York"),
        ),
    )

    assert result.selected_provider == external_market.FUPANHUI_PROVIDER
    assert result.source_trade_date == "2026-07-13"
    assert [trace.status for trace in result.provider_traces] == [
        "success",
        "not_attempted",
        "not_attempted",
    ]


def test_stale_structured_data_uses_finance_fallback(monkeypatch) -> None:
    structured = _provider_quotes(
        provider=external_market.FUPANHUI_PROVIDER,
        trade_date="2026-07-10",
    )
    finance = _provider_quotes(
        provider=external_market.YAHOO_PROVIDER,
        trade_date="2026-07-13",
    )
    monkeypatch.setattr(
        external_market,
        "fetch_fupanhui_global_market",
        lambda *args, **kwargs: structured,
    )
    monkeypatch.setattr(
        external_market,
        "fetch_yahoo_finance_quotes",
        lambda *args, **kwargs: finance,
    )

    result = external_market.resolve_external_market(
        "昨日道指、纳指、标普涨跌",
        now=datetime(
            2026,
            7,
            14,
            14,
            0,
            tzinfo=ZoneInfo("America/New_York"),
        ),
    )

    assert result.selected_provider == external_market.YAHOO_PROVIDER
    assert result.source_trade_date == "2026-07-13"
    assert all(
        quote.source == external_market.YAHOO_PROVIDER
        for quote in result.quotes
    )
    assert [trace.status for trace in result.provider_traces[:2]] == [
        "stale",
        "fallback_success",
    ]


def test_partial_finance_fallback_exposes_retained_stale_quote(
    monkeypatch,
) -> None:
    structured = _provider_quotes(
        provider=external_market.FUPANHUI_PROVIDER,
        trade_date="2026-07-10",
    )
    finance = _provider_quotes(
        provider=external_market.YAHOO_PROVIDER,
        trade_date="2026-07-13",
        codes=("DJI", "SPX"),
    )
    monkeypatch.setattr(
        external_market,
        "fetch_fupanhui_global_market",
        lambda *args, **kwargs: structured,
    )
    monkeypatch.setattr(
        external_market,
        "fetch_yahoo_finance_quotes",
        lambda *args, **kwargs: finance,
    )

    result = external_market.resolve_external_market(
        "昨天美股的涨跌情况",
        now=datetime(
            2026,
            7,
            14,
            14,
            0,
            tzinfo=ZoneInfo("America/New_York"),
        ),
    )

    assert result.gap is not None
    assert "纳斯达克(2026-07-10)" in result.gap
    assert next(
        quote for quote in result.quotes if quote.code == "IXIC"
    ).trade_date == "2026-07-10"


def test_provider_failure_exposes_gap_without_news_substitution(
    monkeypatch,
) -> None:
    empty = external_market._ProviderQuotes(
        quotes=(),
        source_trade_date=None,
        trace=ProviderTrace(
            provider=external_market.FUPANHUI_PROVIDER,
            capability="structured_market_quotes",
            status="request_error",
            detail="TimeoutError",
        ),
    )
    monkeypatch.setattr(
        external_market,
        "fetch_fupanhui_global_market",
        lambda *args, **kwargs: empty,
    )
    monkeypatch.setattr(
        external_market,
        "fetch_yahoo_finance_quotes",
        lambda *args, **kwargs: external_market._ProviderQuotes(
            quotes=(),
            source_trade_date=None,
            trace=ProviderTrace(
                provider=external_market.YAHOO_PROVIDER,
                capability="finance_market_quotes",
                status="request_error",
                detail="OSError",
            ),
        ),
    )

    result = external_market.resolve_external_market(
        "昨天美股的涨跌情况",
        now=datetime(
            2026,
            7,
            14,
            14,
            0,
            tzinfo=ZoneInfo("America/New_York"),
        ),
    )

    assert result.quotes == ()
    assert result.gap is not None
    assert "新闻标题不会被当作精确涨跌数据" in result.gap
    assert result.provider_traces[-1].provider == external_market.BING_NEWS_PROVIDER
    assert result.provider_traces[-1].status == "not_attempted"
