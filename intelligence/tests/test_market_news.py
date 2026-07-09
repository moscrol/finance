from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timedelta
from unittest import mock

from intelligence.services.market_news import (
    NewsItem,
    _within_days,
    build_news_block,
    fetch_eastmoney_news,
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

        block = news_block_for_keyword("数据安全", fetcher=fake_fetch)
        self.assertEqual(captured["kw"], "数据安全")
        self.assertIn("标题A", block)


if __name__ == "__main__":
    unittest.main()
