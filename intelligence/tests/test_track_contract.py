from __future__ import annotations

import unittest

from intelligence.services.track_contract import (
    build_track_guidance,
    parse_track_intent,
    track_guidance_for_query,
)


class ParseTrackIntentTests(unittest.TestCase):
    def test_theme_track_question_type_routes(self) -> None:
        self.assertTrue(parse_track_intent("光伏产业链", "theme_track"))

    def test_track_terms_route(self) -> None:
        self.assertTrue(parse_track_intent("动力电池产业链近况跟踪一下"))
        self.assertTrue(parse_track_intent("液冷自上次之后有什么新变化"))
        self.assertTrue(parse_track_intent("固态电池最新进展如何"))
        self.assertTrue(parse_track_intent("相比上次，算力板块怎么样了"))

    def test_plain_questions_do_not_route(self) -> None:
        # 一次性全景/事实题不注入跟踪契约：泛化问法交由 question_type 兜底
        self.assertFalse(parse_track_intent("今天信创板块怎么样", "theme_analysis"))
        self.assertFalse(parse_track_intent("深信服最近一期毛利率是多少"))
        self.assertFalse(parse_track_intent("光伏行业全景分析"))
        self.assertFalse(parse_track_intent(""))


class GuidanceContentTests(unittest.TestCase):
    def test_guidance_contains_q8_contract_pieces(self) -> None:
        g = build_track_guidance()
        # q8 三件套：delta-only / 四态对照 / TTL + 下期关注
        self.assertIn("delta-only", g)
        self.assertIn("支持 / 削弱 / 无变化 / 信息不足", g)
        self.assertIn("复核期限", g)
        self.assertIn("30 天", g)
        self.assertIn("90 天", g)
        self.assertIn("下期关注清单", g)
        # 无基线时禁止虚构
        self.assertIn("无上期基线", g)
        self.assertIn("[M]", g)
        self.assertIn("[V]", g)

    def test_for_query_returns_empty_when_not_routed(self) -> None:
        self.assertEqual(track_guidance_for_query("深信服毛利率多少", "valuation"), "")

    def test_for_query_returns_guidance_when_routed(self) -> None:
        g = track_guidance_for_query("光伏最近一个月有什么新变化", None)
        self.assertIn("跟踪表达契约", g)
        g2 = track_guidance_for_query("光伏产业链", "theme_track")
        self.assertIn("跟踪表达契约", g2)


class AskOptionsWiringTests(unittest.TestCase):
    def test_include_track_guidance_flag_exists_and_defaults_on(self) -> None:
        from intelligence.services.ask import AskOptions

        options = AskOptions(query="q")
        self.assertTrue(options.include_track_guidance)
        off = AskOptions(query="q", include_track_guidance=False)
        self.assertFalse(off.include_track_guidance)


if __name__ == "__main__":
    unittest.main()
