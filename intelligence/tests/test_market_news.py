from __future__ import annotations

import io
import json
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from intelligence.services import market_news
from intelligence.services.market_news import (
    PROVIDER_EASTMONEY,
    PROVIDER_WEB,
    NewsItem,
    NewsFetchResult,
    _normalize_time_text,
    _within_days,
    build_news_block,
    english_alias,
    fetch_eastmoney_news,
    fetch_eastmoney_news_result,
    fetch_web_access_news,
    merge_news_items,
    news_block_for_keyword,
    news_block_result_for_keyword,
    parse_news_intent,
    query_date_cutoff,
    resolve_news_keyword,
)
from intelligence.services.provider_observability import ProviderTrace


class FetchTitleRelevanceFilterTests(unittest.TestCase):
    def test_drops_articles_without_keyword_in_title(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        articles = [
            {"date": today, "title": "<em>后量子密码</em>标准落地", "mediaName": "证券时报", "url": "http://x/1"},
            {"date": today, "title": "高盛重磅发声：做多中国AI价值链", "mediaName": "财联社", "url": "http://x/2"},
        ]
        payload = "x(" + json.dumps({"result": {"cmsArticleWebOld": articles}}, ensure_ascii=False) + ")"
        resp = mock.MagicMock()
        resp.__enter__.return_value = io.BytesIO(payload.encode("utf-8"))
        with mock.patch("urllib.request.urlopen", return_value=resp):
            items = fetch_eastmoney_news("后量子密码")
        self.assertEqual(len(items), 1)
        self.assertIn("后量子密码", items[0].title)

    def test_market_cause_title_requires_market_anchor_and_direction(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        articles = [
            {
                "date": today,
                "title": "A股市场缩量调整，主要指数集体收跌",
                "mediaName": "证券时报",
                "url": "http://x/a-share",
            },
            {
                "date": today,
                "title": "7月24日港股回购日报",
                "mediaName": "财联社",
                "url": "http://x/hk-buyback",
            },
        ]
        payload = "x(" + json.dumps(
            {"result": {"cmsArticleWebOld": articles}},
            ensure_ascii=False,
        ) + ")"
        resp = mock.MagicMock()
        resp.__enter__.return_value = io.BytesIO(payload.encode("utf-8"))

        with mock.patch("urllib.request.urlopen", return_value=resp):
            items = fetch_eastmoney_news(
                "2026年7月24日 A股 大跌 原因 上证指数 7月20日至24日"
            )

        self.assertEqual(
            [item.title for item in items],
            ["A股市场缩量调整，主要指数集体收跌"],
        )


class EastmoneyQueryToleranceTests(unittest.TestCase):
    @staticmethod
    def _result(keyword: str, *items: NewsItem, status: str = "empty"):
        return NewsFetchResult(
            tuple(items),
            ProviderTrace(
                provider=PROVIDER_EASTMONEY,
                capability="directional_news",
                status="success" if items else status,
                detail=f"scripted:{keyword}",
                result_count=len(items),
            ),
        )

    def test_natural_market_question_retries_simpler_keywords(self) -> None:
        calls: list[str] = []

        def fake_fetch(keyword: str, **_kwargs) -> NewsFetchResult:
            calls.append(keyword)
            if keyword == "A股调整":
                return self._result(
                    keyword,
                    NewsItem(
                        "2026-07-24",
                        "证券时报",
                        "A股市场缩量调整",
                        "https://example.com/a",
                    ),
                )
            return self._result(keyword)

        with mock.patch.object(
            market_news,
            "_fetch_eastmoney_news_uncached",
            side_effect=fake_fetch,
        ):
            result = fetch_eastmoney_news_result(
                "上周A股下跌原因",
                timeout=2.0,
            )

        self.assertEqual(calls[:2], ["上周A股下跌原因", "A股下跌"])
        self.assertIn("A股调整", calls)
        self.assertNotIn("A股", calls)
        self.assertLessEqual(len(calls), 4)
        self.assertEqual([item.title for item in result.items], ["A股市场缩量调整"])
        self.assertEqual(result.trace.status, "fallback_success")
        self.assertIn("上周A股下跌原因", result.trace.detail)
        self.assertIn("A股调整", result.trace.detail)

    def test_spaced_market_query_keeps_anchor_and_direction_together(self) -> None:
        calls: list[str] = []

        def fake_fetch(keyword: str, **_kwargs) -> NewsFetchResult:
            calls.append(keyword)
            if keyword == "A股调整":
                return self._result(
                    keyword,
                    NewsItem(
                        "2026-07-24",
                        "证券时报",
                        "A股下跌原因复盘",
                        "https://example.com/market-cause",
                    ),
                )
            return self._result(keyword)

        with mock.patch.object(
            market_news,
            "_fetch_eastmoney_news_uncached",
            side_effect=fake_fetch,
        ):
            result = fetch_eastmoney_news_result(
                "A股 本周 下跌 原因 2026年7月",
                timeout=2.0,
            )

        self.assertEqual(
            calls[:3],
            ["A股 本周 下跌 原因 2026年7月", "A股下跌", "A股调整"],
        )
        self.assertEqual([item.title for item in result.items], ["A股下跌原因复盘"])

    def test_market_fallback_never_degrades_to_date_or_broad_anchor(self) -> None:
        calls: list[str] = []

        def fake_fetch(keyword: str, **_kwargs) -> NewsFetchResult:
            calls.append(keyword)
            if keyword in {"24日", "24日下跌", "24日调整", "A股"}:
                return self._result(
                    keyword,
                    NewsItem(
                        "2026-07-24",
                        "财联社",
                        "7月24日港股回购日报",
                        "https://example.com/hk-buyback",
                    ),
                )
            return self._result(keyword)

        with mock.patch.object(
            market_news,
            "_fetch_eastmoney_news_uncached",
            side_effect=fake_fetch,
        ):
            result = fetch_eastmoney_news_result(
                "2026年7月24日 A股 大跌 原因 上证指数 7月20日至24日",
                timeout=2.0,
            )

        self.assertEqual(result.items, ())
        self.assertNotIn("24日", calls)
        self.assertNotIn("24日下跌", calls)
        self.assertNotIn("24日调整", calls)
        self.assertNotIn("A股", calls)
        self.assertTrue({"A股下跌", "A股调整"}.intersection(calls))

    def test_explicit_compound_query_merges_single_keyword_results(self) -> None:
        calls: list[str] = []

        def fake_fetch(keyword: str, **_kwargs) -> NewsFetchResult:
            calls.append(keyword)
            items = {
                "低空经济": NewsItem(
                    "2026-07-24",
                    "财联社",
                    "低空经济政策推进",
                    "https://example.com/low-altitude",
                ),
                "商业航天": NewsItem(
                    "2026-07-23",
                    "证券时报",
                    "商业航天发射计划更新",
                    "https://example.com/space",
                ),
            }
            return self._result(keyword, *([items[keyword]] if keyword in items else []))

        with mock.patch.object(
            market_news,
            "_fetch_eastmoney_news_uncached",
            side_effect=fake_fetch,
        ):
            result = fetch_eastmoney_news_result(
                "低空经济 商业航天",
                timeout=2.0,
            )

        self.assertEqual(calls[:3], ["低空经济 商业航天", "低空经济", "商业航天"])
        self.assertEqual(
            [item.title for item in result.items],
            ["低空经济政策推进", "商业航天发射计划更新"],
        )
        self.assertEqual(result.trace.status, "fallback_success")

    def test_provider_error_does_not_trigger_query_fallback_storm(self) -> None:
        calls: list[str] = []

        def fake_fetch(keyword: str, **_kwargs) -> NewsFetchResult:
            calls.append(keyword)
            return self._result(keyword, status="request_error")

        with mock.patch.object(
            market_news,
            "_fetch_eastmoney_news_uncached",
            side_effect=fake_fetch,
        ):
            result = fetch_eastmoney_news_result(
                "上周A股下跌原因",
                timeout=2.0,
            )

        self.assertEqual(calls, ["上周A股下跌原因"])
        self.assertEqual(result.trace.status, "request_error")

    def test_fallback_merge_deduplicates_same_url_or_title(self) -> None:
        duplicate = NewsItem(
            "2026-07-24",
            "财联社",
            "共同标题",
            "https://example.com/same",
        )

        def fake_fetch(keyword: str, **_kwargs) -> NewsFetchResult:
            if keyword in {"低空经济", "商业航天"}:
                return self._result(keyword, duplicate)
            return self._result(keyword)

        with mock.patch.object(
            market_news,
            "_fetch_eastmoney_news_uncached",
            side_effect=fake_fetch,
        ):
            result = fetch_eastmoney_news_result(
                "低空经济 商业航天",
                timeout=2.0,
            )

        self.assertEqual(len(result.items), 1)

    def test_historical_cutoff_pages_until_it_finds_eligible_news(self) -> None:
        calls: list[tuple[str, int]] = []

        def fake_fetch(keyword: str, **kwargs) -> NewsFetchResult:
            page_index = int(kwargs.get("page_index", 1))
            calls.append((keyword, page_index))
            if keyword != "A股调整":
                return self._result(keyword)
            if page_index == 1:
                return self._result(
                    keyword,
                    NewsItem(
                        "2026-07-27 09:00:00",
                        "证券时报",
                        "A股最新动态",
                        "https://example.com/future",
                    ),
                )
            return self._result(
                keyword,
                NewsItem(
                    "2026-07-24 15:00:00",
                    "证券时报",
                    "A股7月24日缩量调整",
                    "https://example.com/cutoff",
                ),
                NewsItem(
                    "2026-07-23 15:00:00",
                    "财联社",
                    "A股7月23日盘面复盘",
                    "https://example.com/prior",
                ),
            )

        with mock.patch.object(
            market_news,
            "_fetch_eastmoney_news_uncached",
            side_effect=fake_fetch,
        ):
            result = fetch_eastmoney_news_result(
                "上周A股下跌原因",
                timeout=2.0,
                as_of="2026-07-24",
            )

        self.assertIn(("A股调整", 1), calls)
        self.assertIn(("A股调整", 2), calls)
        self.assertEqual(
            [item.date[:10] for item in result.items],
            ["2026-07-24", "2026-07-23"],
        )
        self.assertEqual(result.trace.status, "fallback_success")
        self.assertEqual(result.trace.requested_date, "2026-07-24")
        self.assertIn("pages=2", result.trace.detail)


class QueryDateCutoffTests(unittest.TestCase):
    def test_uses_latest_explicit_date_in_compressed_market_window(self) -> None:
        self.assertEqual(
            query_date_cutoff(
                "A股 2026年7月20日至24日 下跌原因",
                upper_bound=date(2026, 7, 27),
            ),
            date(2026, 7, 24),
        )

    def test_keeps_global_cutoff_when_query_has_no_date(self) -> None:
        self.assertEqual(
            query_date_cutoff(
                "这一周A股为什么下跌",
                upper_bound=date(2026, 7, 27),
            ),
            date(2026, 7, 27),
        )

    def test_explicit_future_date_cannot_expand_global_cutoff(self) -> None:
        self.assertEqual(
            query_date_cutoff(
                "2026-07-30 A股下跌原因",
                upper_bound=date(2026, 7, 27),
            ),
            date(2026, 7, 27),
        )


class ParseNewsIntentTests(unittest.TestCase):
    def test_event_questions_route(self) -> None:
        self.assertTrue(parse_news_intent("数据安全最近有什么催化事件"))
        self.assertTrue(parse_news_intent("PI 膜近期涨价了吗，海外对标情况"))
        self.assertTrue(parse_news_intent("这个方向最新进展和消息面"))

    def test_non_event_questions_do_not_route(self) -> None:
        self.assertFalse(parse_news_intent("深信服今天的估值分位是多少"))
        self.assertFalse(parse_news_intent("信创板块当日双红强度"))


class ResolveKeywordTests(unittest.TestCase):
    def test_entity_preferred_over_theme(self) -> None:
        self.assertEqual(resolve_news_keyword("q", theme="数据安全", entity="深信服"), "深信服")

    def test_theme_when_no_entity(self) -> None:
        self.assertEqual(resolve_news_keyword("q", theme="数据安全", entity=None), "数据安全")

    def test_none_when_both_missing(self) -> None:
        self.assertIsNone(resolve_news_keyword("q", theme=None, entity=""))

    def test_query_fallback_strips_scaffolding(self) -> None:
        self.assertEqual(
            resolve_news_keyword("后量子密码最近90天有什么实质催化", theme=None, entity=None),
            "后量子密码",
        )

    def test_theme_equal_to_query_falls_through_to_extraction(self) -> None:
        q = "后量子密码最近90天有什么实质催化"
        self.assertEqual(resolve_news_keyword(q, theme=q, entity=None), "后量子密码")

    def test_query_fallback_none_when_residual_too_long(self) -> None:
        self.assertIsNone(
            resolve_news_keyword("请帮我系统性梳理一下整个半导体产业链上下游各环节的所有相关公司情况如何", theme=None, entity=None)
        )


class WithinDaysTests(unittest.TestCase):
    def test_recent_kept(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d 09:00:00")
        self.assertTrue(_within_days(today, 90))

    def test_old_dropped(self) -> None:
        old = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d 09:00:00")
        self.assertFalse(_within_days(old, 90))

    def test_unparseable_kept(self) -> None:
        self.assertTrue(_within_days("", 90))

    def test_zero_window_keeps_all(self) -> None:
        old = (datetime.now() - timedelta(days=999)).strftime("%Y-%m-%d 09:00:00")
        self.assertTrue(_within_days(old, 0))


class BuildNewsBlockTests(unittest.TestCase):
    def _items(self) -> list[NewsItem]:
        return [
            NewsItem("2026-07-08 15:07:00", "21世纪经济报道", "金融业网络安全升级，绿盟科技20cm涨停", "http://x/1"),
            NewsItem("2026-07-06 07:14:48", "上海证券报", "量子计算愈发吸金", "http://x/2"),
        ]

    def test_renders_rows_source_url_and_usage(self) -> None:
        block = build_news_block("数据安全", self._items())
        self.assertIn("[W7]", block)
        self.assertIn("21世纪经济报道", block)
        self.assertIn("绿盟科技20cm涨停", block)
        self.assertIn("http://x/1", block)
        self.assertIn("使用要求", block)

    def test_empty_declares_gap(self) -> None:
        block = build_news_block("冷门词", [])
        self.assertIn("缺消息面", block)
        self.assertNotIn("http", block)

    def test_fetch_disabled_flag(self) -> None:
        block = build_news_block("x", [], fetch_disabled=True)
        self.assertIn("已被 FINANCE_NEWS_FETCH=0 关闭", block)


class NewsBlockForKeywordTests(unittest.TestCase):
    def test_empty_keyword_returns_empty(self) -> None:
        self.assertEqual(news_block_for_keyword(None), "")
        self.assertEqual(news_block_for_keyword("  "), "")

    def test_uses_injected_fetcher(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch(kw: str, page_size: int, within_days: int) -> list[NewsItem]:
            captured["kw"] = kw
            return [NewsItem("2026-07-08 10:00:00", "新华财经", "标题A", "http://x/a")]

        block = news_block_for_keyword("数据安全", fetcher=fake_fetch, web_fetcher=lambda *a: [])
        self.assertEqual(captured["kw"], "数据安全")
        self.assertIn("标题A", block)

    def test_merges_web_provider_items(self) -> None:
        def fake_em(kw: str, page_size: int, within_days: int) -> list[NewsItem]:
            return [NewsItem("2026-07-08 10:00:00", "新华财经", "标题A", "http://x/a")]

        def fake_web(kw: str, page_size: int, within_days: int) -> list[NewsItem]:
            return [NewsItem("2026-07-07", "Reuters", "PQC executive order", "http://x/b", provider=PROVIDER_WEB)]

        block = news_block_for_keyword("后量子密码", fetcher=fake_em, web_fetcher=fake_web)
        self.assertIn("标题A", block)
        self.assertIn("PQC executive order", block)
        self.assertIn("[web]", block)
        self.assertIn("东财 1 + web 1", block)

    def test_pqc_news_path_records_both_provider_statuses(self) -> None:
        result = news_block_result_for_keyword(
            "PQC",
            fetcher=lambda *args: [
                NewsItem(
                    "2026-07-08",
                    "证券时报",
                    "PQC标准进展",
                    "http://x/a",
                )
            ],
            web_fetcher=lambda *args: [
                NewsItem(
                    "2026-07-07",
                    "Reuters",
                    "PQC news",
                    "http://x/b",
                    provider=PROVIDER_WEB,
                )
            ],
        )

        self.assertIn("PQC标准进展", result.block)
        self.assertEqual(
            [trace.status for trace in result.traces],
            ["success", "success"],
        )

    def test_provider_failure_is_not_silently_reported_as_empty(self) -> None:
        result = news_block_result_for_keyword(
            "PQC",
            fetcher=lambda *args: (_ for _ in ()).throw(TimeoutError()),
            web_fetcher=lambda *args: (_ for _ in ()).throw(OSError()),
        )

        self.assertEqual(
            [trace.status for trace in result.traces],
            ["request_error", "request_error"],
        )
        self.assertIn("缺消息面", result.block)

    def test_web_disabled_by_env(self) -> None:
        def fake_em(kw: str, page_size: int, within_days: int) -> list[NewsItem]:
            return [NewsItem("2026-07-08 10:00:00", "新华财经", "标题A", "http://x/a")]

        def fail_web(*args: object) -> list[NewsItem]:
            raise AssertionError("web fetcher should not be called when disabled")

        with mock.patch.dict("os.environ", {"FINANCE_NEWS_WEB_FETCH": "0"}):
            block = news_block_for_keyword("数据安全", fetcher=fake_em, web_fetcher=fail_web)
        self.assertIn("标题A", block)


class EnglishAliasTests(unittest.TestCase):
    def test_known_theme_maps_to_english(self) -> None:
        self.assertEqual(english_alias("后量子密码"), "post-quantum cryptography")

    def test_unknown_returns_none(self) -> None:
        self.assertIsNone(english_alias("不存在的题材"))
        self.assertIsNone(english_alias(""))

    def test_web_fetcher_receives_alias_and_block_notes_it(self) -> None:
        captured: dict[str, str] = {}

        def fake_web(kw: str, page_size: int, within_days: int) -> list[NewsItem]:
            captured["kw"] = kw
            return [NewsItem("2026-07-07", "Reuters", "PQC news", "http://x/b", provider=PROVIDER_WEB)]

        block = news_block_for_keyword("后量子密码", fetcher=lambda *a: [], web_fetcher=fake_web)
        self.assertEqual(captured["kw"], "post-quantum cryptography")
        self.assertIn("web 检索词「post-quantum cryptography」", block)


class MergeNewsItemsTests(unittest.TestCase):
    def test_dedupes_by_url_and_title(self) -> None:
        em = [NewsItem("2026-07-08 10:00:00", "证券时报", "同一标题", "http://x/a")]
        web = [
            NewsItem("2026-07-08", "Bing", "同一标题", "http://x/other", provider=PROVIDER_WEB),
            NewsItem("2026-07-07", "Bing", "另一条", "http://x/a/", provider=PROVIDER_WEB),
            NewsItem("2026-07-06", "Reuters", "unique", "http://x/c", provider=PROVIDER_WEB),
        ]
        merged = merge_news_items(em, web)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].provider, PROVIDER_EASTMONEY)
        self.assertEqual(merged[1].title, "unique")

    def test_sorts_dated_desc_and_keeps_undated_last(self) -> None:
        items = merge_news_items(
            [NewsItem("2026-07-06 09:00:00", "a", "旧", "http://x/1")],
            [
                NewsItem("刚刚", "b", "无日期", "http://x/2", provider=PROVIDER_WEB),
                NewsItem("2026-07-08", "c", "新", "http://x/3", provider=PROVIDER_WEB),
            ],
        )
        self.assertEqual([it.title for it in items], ["新", "旧", "无日期"])


class NormalizeTimeTextTests(unittest.TestCase):
    def test_relative_chinese(self) -> None:
        self.assertEqual(_normalize_time_text("2 天前"), (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"))
        self.assertTrue(_normalize_time_text("3 小时前").startswith((datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d")))

    def test_relative_english(self) -> None:
        self.assertEqual(_normalize_time_text("2 days ago"), (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"))

    def test_absolute_chinese_date(self) -> None:
        self.assertEqual(_normalize_time_text("2026年7月1日"), "2026-07-01")

    def test_absolute_us_date(self) -> None:
        self.assertEqual(_normalize_time_text("6/24/2026"), "2026-06-24")

    def test_non_time_text_dropped(self) -> None:
        self.assertEqual(_normalize_time_text("Opinion"), "")
        self.assertEqual(_normalize_time_text("刚刚"), "")
        self.assertEqual(_normalize_time_text(""), "")


class FetchWebAccessNewsTests(unittest.TestCase):
    def test_proxy_unreachable_returns_empty(self) -> None:
        with mock.patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            self.assertEqual(fetch_web_access_news("后量子密码"), [])

    def test_empty_keyword_returns_empty(self) -> None:
        self.assertEqual(fetch_web_access_news(""), [])

    def test_parses_proxy_responses(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        cards = [
            {"title": "ST launches PQC chip", "url": "http://x/1", "source": "Reuters", "time": "2 天前"},
            {"title": "", "url": "http://x/2", "source": "a", "time": "1 天前"},
        ]
        responses = [
            "{}",  # /health
            json.dumps({"targetId": "T1"}),  # /new
            json.dumps({"value": json.dumps(cards)}),  # /eval
            "{}",  # /close
        ]

        def fake_urlopen(req, timeout=0):  # noqa: ANN001, ANN202
            resp = mock.MagicMock()
            resp.__enter__.return_value = io.BytesIO(responses.pop(0).encode("utf-8"))
            return resp

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            items = fetch_web_access_news("后量子密码")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].provider, PROVIDER_WEB)
        self.assertEqual(items[0].source, "Reuters")
        self.assertNotEqual(items[0].date, today)  # 2 天前
        self.assertIn("PQC", items[0].title)


if __name__ == "__main__":
    unittest.main()
