import unittest

from intelligence.services.question_router import (
    ROUTE_DATA_GAP,
    ROUTE_KNOWN,
    ROUTE_PLANNER,
    route_question,
)


class QuestionRouterTest(unittest.TestCase):
    def test_known_workflow_routes_deep_dive(self):
        decision = route_question("玻璃基板 deep-dive")

        self.assertEqual(decision.route_type, ROUTE_KNOWN)
        self.assertEqual(decision.selected_paths[0].id, "deep_dive")
        self.assertEqual(decision.next_action, "run_or_preview:deep_dive")

    def test_analysis_routes_to_planner_with_logic_market_match(self):
        decision = route_question("玻璃基板今天为什么动，是旧逻辑唤醒吗")

        self.assertEqual(decision.route_type, ROUTE_PLANNER)
        self.assertTrue(any(path.id == "logic_market_match" for path in decision.selected_paths))
        self.assertTrue(any("theme-candidates" in item for item in decision.missing_data_checks))

    def test_data_gap_routes_to_backfill_paths(self):
        decision = route_question("446 个 missing concept 和 21 个 missing source 怎么补")

        self.assertEqual(decision.route_type, ROUTE_DATA_GAP)
        ids = {path.id for path in decision.selected_paths}
        self.assertIn("concept_backfill", ids)
        self.assertIn("source_backfill", ids)
        self.assertIn("daily_ops_ledger", ids)

    def test_bare_theme_uses_planner(self):
        decision = route_question("液冷服务器")

        self.assertEqual(decision.route_type, ROUTE_PLANNER)
        self.assertEqual(decision.next_action, "run_logic_match")


if __name__ == "__main__":
    unittest.main()
