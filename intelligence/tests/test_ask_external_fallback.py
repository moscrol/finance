from __future__ import annotations

from intelligence.services import ask, external_market, web_research
from intelligence.services.closed_loop_retrieval import ClosedLoopRetrievalResult
from intelligence.services.provider_observability import ProviderTrace


def test_external_market_query_skips_local_a_share_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(
        ask.external_market,
        "resolve_external_market",
        lambda query: external_market.ExternalMarketResult(
            target_trade_date="2026-07-13",
            source_trade_date="2026-07-13",
            selected_provider=external_market.FUPANHUI_PROVIDER,
            quotes=(
                external_market.ExternalMarketQuote(
                    code="DJI",
                    name="道琼斯",
                    close=44600.0,
                    pct_chg=0.4,
                    trade_date="2026-07-13",
                    source=external_market.FUPANHUI_PROVIDER,
                ),
            ),
            provider_traces=(
                ProviderTrace(
                    provider=external_market.FUPANHUI_PROVIDER,
                    capability="structured_market_quotes",
                    status="success",
                    source_trade_date="2026-07-13",
                    result_count=1,
                ),
            ),
        ),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="昨天美股的涨跌情况",
            compose=False,
            synthesize=False,
        )
    )

    assert result.question_plan is not None
    assert result.question_plan.question_type == "external_market"
    assert result.routed_modules == []
    assert result.market_data_source == external_market.FUPANHUI_PROVIDER
    assert result.trade_date == "2026-07-13"
    assert "A 股" in result.sections["交易含义"][0]
    assert all(not citation.source.startswith("knowledge-base") for citation in result.citations)


def test_definition_miss_upgrades_to_general_web_search(monkeypatch) -> None:
    monkeypatch.setattr(
        ask.closed_loop_retrieval,
        "retrieve_closed_loop",
        lambda *args, **kwargs: ClosedLoopRetrievalResult(),
    )
    monkeypatch.setattr(
        ask.web_research,
        "fetch_web_search",
        lambda query: web_research.WebSearchResult(
            items=(
                web_research.WebSearchItem(
                    title="卫星互联网概述",
                    url="https://example.com/satellite",
                    snippet="卫星互联网通过卫星星座提供网络连接。",
                ),
            ),
            trace=ProviderTrace(
                provider=web_research.PROVIDER_BING_WEB,
                capability="general_web_search",
                status="success",
                result_count=1,
            ),
        ),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="卫星互联网是什么",
            compose=False,
            synthesize=False,
        )
    )

    assert result.question_plan is not None
    assert result.question_plan.question_type == "concept_definition"
    assert result.routed_modules == []
    assert result.citations[0].detail == "https://example.com/satellite"
    assert [trace.status for trace in result.provider_traces] == [
        "empty",
        "success",
    ]
    assert "A 股盘面材料" in result.data_notice


def test_definition_provider_failure_preserves_explicit_gap(monkeypatch) -> None:
    monkeypatch.setattr(
        ask.closed_loop_retrieval,
        "retrieve_closed_loop",
        lambda *args, **kwargs: ClosedLoopRetrievalResult(),
    )
    monkeypatch.setattr(
        ask.web_research,
        "fetch_web_search",
        lambda query: web_research.WebSearchResult(
            items=(),
            trace=ProviderTrace(
                provider=web_research.PROVIDER_BING_WEB,
                capability="general_web_search",
                status="proxy_unavailable",
                detail="CDP proxy health check failed",
            ),
        ),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="卫星互联网是什么",
            compose=False,
            synthesize=False,
        )
    )

    assert result.citations == []
    assert result.sections["证据链"] == []
    assert "未使用无关 A 股资料替代" in result.sections["分歧反证"][0]
