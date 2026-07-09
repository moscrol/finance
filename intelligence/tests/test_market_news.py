from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timedelta
from unittest import mock

from intelligence.services.market_news import (
    PROVIDER_EASTMONEY,
    PROVIDER_WEB,
    NewsItem,
    _normalize_time_text,
    _within_days,
    build_news_block,
    fetch_eastmoney_news,
    fetch_web_access_news,
    merge_news_items,
    news_block_for_keyword,
    parse_news_intent,
    resolve_news_keyword,
)


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

    def test_web_disabled_by_env(self) -> None:
        def fake_em(kw: str, page_size: int, within_days: int) -> list[NewsItem]:
            return [NewsItem("2026-07-08 10:00:00", "新华财经", "标题A", "http://x/a")]

        def fail_web(*args: object) -> list[NewsItem]:
            raise AssertionError("web fetcher should not be called when disabled")

        with mock.patch.dict("os.environ", {"FINANCE_NEWS_WEB_FETCH": "0"}):
            block = news_block_for_keyword("数据安全", fetcher=fake_em, web_fetcher=fail_web)
        self.assertIn("标题A", block)


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
