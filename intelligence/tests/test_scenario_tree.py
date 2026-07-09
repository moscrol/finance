from __future__ import annotations

import unittest

from intelligence.services.scenario_tree import (
    build_scenario_guidance,
    parse_scenario_intent,
    scenario_guidance_for_query,
)


class ParseScenarioIntentTests(unittest.TestCase):
    def test_forecast_question_type_routes(self) -> None:
        self.assertTrue(parse_scenario_intent("厦钨H1正极业务表现", "market_forecast"))

    def test_scenario_terms_route(self) -> None:
        self.assertTrue(parse_scenario_intent("推演一下正极能否扭亏"))
        self.assertTrue(parse_scenario_intent("如果它大幅降价会怎样"))
        self.assertTrue(parse_scenario_intent("这个切换的概率有多大"))

    def test_plain_questions_do_not_route(self) -> None:
        self.assertFalse(parse_scenario_intent("今天信创板块怎么样", "theme_analysis"))
        self.assertFalse(parse_scenario_intent("深信服最近一期毛利率是多少"))
        self.assertFalse(parse_scenario_intent(""))


class GuidanceContentTests(unittest.TestCase):
    def test_guidance_bans_numeric_probability(self) -> None:
        g = build_scenario_guidance()
        self.assertIn("禁止给出任何数值概率", g)
        self.assertIn("高/中/低", g)
        self.assertIn("关键变量表", g)
        self.assertIn("监控信号", g)
        self.assertIn("[M]", g)

    def test_for_query_returns_empty_when_not_routed(self) -> None:
        self.assertEqual(scenario_guidance_for_query("深信服毛利率多少", "valuation"), "")

    def test_for_query_returns_guidance_when_routed(self) -> None:
        g = scenario_guidance_for_query("推演正极扭亏路径", None)
        self.assertIn("情景树/推演表达契约", g)


if __name__ == "__main__":
    unittest.main()
