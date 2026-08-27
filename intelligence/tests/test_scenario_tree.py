from __future__ import annotations

import unittest

from intelligence.services.scenario_tree import (
    build_scenario_guidance,
    build_scenario_guidance_for_episode,
    build_scenario_tree_artifact,
    episode_scenario_rule,
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

    def test_request_prefixes_do_not_route_as_scenarios(self) -> None:
        for question in (
            "能否帮我把复盘导出成 PDF",
            "能不能把今天的涨停股导出成表格",
            "能否解释一下什么是 PE",
            "能不能告诉我收盘价",
        ):
            with self.subTest(question=question):
                self.assertFalse(parse_scenario_intent(question))

    def test_feasibility_questions_with_subject_still_route(self) -> None:
        for question in (
            "推演一下正极能否扭亏",
            "厦门钨业正极能否扭亏",
            "量能能不能延续",
            "工业富联的代工毛利率能不能证伪算力需求见顶？",
        ):
            with self.subTest(question=question):
                self.assertTrue(parse_scenario_intent(question))

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

    def test_guidance_requires_causal_hypotheses_not_path_restyle(self) -> None:
        g = build_scenario_guidance()
        self.assertIn("互斥因果假说", g)
        self.assertIn("证据不足，两假说并立", g)
        self.assertIn("领跌相对强弱", g)
        self.assertIn("不是量能", g)

    def test_for_query_returns_empty_when_not_routed(self) -> None:
        self.assertEqual(scenario_guidance_for_query("深信服毛利率多少", "valuation"), "")

    def test_for_query_returns_guidance_when_routed(self) -> None:
        g = scenario_guidance_for_query("推演正极扭亏路径", None)
        self.assertIn("情景树/推演表达契约", g)
        self.assertIn("互斥因果假说", g)

    def test_episode_guidance_uses_evidence_ordinals_not_ask_blocks(self) -> None:
        g = build_scenario_guidance_for_episode()
        self.assertIn("互斥因果假说", g)
        self.assertIn("证据不足，两假说并立", g)
        self.assertIn("E1", g)
        for legacy_marker in ("[M]", "[V]", "[D0]", "[D6]", "[W7]"):
            self.assertNotIn(legacy_marker, g)

    def test_episode_rule_stays_empty_when_not_a_scenario(self) -> None:
        self.assertEqual(episode_scenario_rule("深信服毛利率多少", "valuation"), "")

    def test_episode_rule_fires_for_forecast_and_overnight_hybrid(self) -> None:
        local = episode_scenario_rule("昨天的反弹能持续多久", "market_forecast")
        overnight = episode_scenario_rule(
            "基于周二的盘面数据，你认为主线是什么。"
            "今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会",
            "market_forecast",
        )
        self.assertIn("互斥因果假说", local)
        self.assertIn("互斥因果假说", overnight)
        self.assertIn("领跌相对强弱", overnight)

    def test_typed_tree_uses_conditional_branches_without_numeric_probability(
        self,
    ) -> None:
        artifact = build_scenario_tree_artifact(
            theme="信创",
            horizon="3_to_6_months",
            verified_facts=(
                {
                    "text": "板块成交与涨幅同步转强",
                    "evidence_ids": ["D6"],
                    "status": "verified",
                },
            ),
            triggers=(
                {
                    "text": "公告与订单证据继续补强",
                    "evidence_ids": ["L3-1"],
                },
            ),
            counterevidence=(
                {
                    "text": "公司经营兑现弱于题材叙事",
                    "evidence_ids": ["R1"],
                },
            ),
            gaps=(),
        )

        self.assertTrue(artifact.available)
        self.assertIsNone(artifact.degrade_reason)
        self.assertEqual(
            [branch.branch_id for branch in artifact.branches],
            ["upgrade", "base", "downgrade"],
        )
        payload = artifact.to_payload()
        self.assertFalse(payload["numeric_probabilities_allowed"])
        self.assertTrue(
            all(
                branch["likelihood"] == "待验证"
                for branch in payload["branches"]
            )
        )


if __name__ == "__main__":
    unittest.main()
