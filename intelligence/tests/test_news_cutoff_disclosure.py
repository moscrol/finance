"""P0 T2：时点检索被 as_of 全滤时不得静默变 0 条。

选定 T2-a：把晚于问句日的条目标注后交给模型，trace 仍是 future_of_cutoff。
对应质量稿 §7.5。
"""

from __future__ import annotations

from datetime import date
from unittest import mock

from intelligence.services import market_news
from intelligence.services.agent_research import AgentToolContext, build_default_tools
from intelligence.services.market_news import NewsFetchResult, NewsItem
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)


def _future_only_result(keyword: str, **_kwargs) -> NewsFetchResult:
    return NewsFetchResult(
        (
            NewsItem(
                "2026-08-17 09:00:00",
                "证券时报",
                "电网设备高景气延续",
                "https://example.com/0817",
            ),
            NewsItem(
                "2026-08-18 09:00:00",
                "财联社",
                "特高压招标落地",
                "https://example.com/0818",
            ),
        ),
        ProviderTrace(
            provider=market_news.PROVIDER_EASTMONEY,
            capability="directional_news",
            status="success",
            detail=f"scripted:{keyword}",
            result_count=2,
        ),
    )


def test_cutoff_filtered_news_not_silently_empty() -> None:
    """电网形：as_of=07-23、源只回 08-17/18 → 不得静默 0 条。"""

    with mock.patch.object(
        market_news,
        "_fetch_eastmoney_news_uncached",
        side_effect=_future_only_result,
    ):
        fetched = market_news.fetch_eastmoney_news_result(
            "电网设备 板块 大涨 特高压 2026年7月23日",
            timeout=2.0,
            as_of="2026-07-23",
        )

    assert fetched.trace.status == "future_of_cutoff"
    assert fetched.after_cutoff_items
    assert {item.date[:10] for item in fetched.after_cutoff_items} == {
        "2026-08-17",
        "2026-08-18",
    }

    def kb(_query: str, _timeout: float):
        raise AssertionError("kb_search should not run")

    tools = build_default_tools(kb)
    context = AgentToolContext(
        deadline=ResearchDeadline.from_timeout(8.0),
        information_cutoff=InformationCutoff(date(2026, 7, 23), "requested"),
    )
    with mock.patch.object(
        market_news,
        "_fetch_eastmoney_news_uncached",
        side_effect=_future_only_result,
    ):
        evidence, observation, trace = tools["news_search"](
            "电网设备 板块 大涨 特高压 2026年7月23日",
            context,
        )

    assert evidence, "T2-a：全滤时要把越界条目标注后交给模型"
    assert trace.status == "future_of_cutoff"
    assert "晚于问句日" in observation
    assert "不是源里没有" in observation or "不是源里没有" in " ".join(
        item.title + item.detail for item in evidence
    )
    assert "无资讯" not in observation


def test_overnight_news_discloses_after_cutoff(monkeypatch) -> None:
    """market_forecast 旁路 _overnight_news_evidence 不得只读 items、把全滤写成空。"""

    from intelligence.services.episode_tools import _overnight_news_evidence
    from intelligence.services.market_news import NewsFetchResult, NewsItem
    from intelligence.services.provider_observability import ProviderTrace

    def fake_fetch(_keyword: str, **_kwargs) -> NewsFetchResult:
        return NewsFetchResult(
            (),
            ProviderTrace(
                provider=market_news.PROVIDER_EASTMONEY,
                capability="directional_news",
                status="future_of_cutoff",
                result_count=0,
            ),
            after_cutoff_items=(
                NewsItem(
                    "2026-08-18 22:00:00",
                    "证券时报",
                    "费城半导体指数大跌",
                    "http://eastmoney.test/sox-cutoff",
                ),
            ),
        )

    monkeypatch.setattr(
        market_news,
        "fetch_eastmoney_news_result",
        fake_fetch,
    )
    evidence, observation = _overnight_news_evidence(
        as_of=date(2026, 7, 23),
        timeout=2.0,
    )
    assert evidence
    assert "晚于问句日" in observation
    assert "不是源里没有" in observation
    assert "费城半导体" in observation
