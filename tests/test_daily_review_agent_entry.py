import tempfile
import unittest
from pathlib import Path

from intelligence.paths import ProjectPaths
from intelligence.workflows.daily_review import DailyReviewOptions, build_daily_review_plan
from scripts import render_review_workbench


class DailyReviewAgentEntryTest(unittest.TestCase):
    def make_paths(self, root: Path) -> ProjectPaths:
        finance = root / "finance"
        (finance / "market_feature_store" / "exports").mkdir(parents=True)
        (finance / "复盘" / "daily").mkdir(parents=True)
        return ProjectPaths(finance_root=finance, knowledge_wiki=root / "wiki", finance_site=root / "site")

    def test_daily_plan_generates_agent_brief_before_workbench(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))

            plan = build_daily_review_plan(DailyReviewOptions(date="2026-06-11"), paths)
            names = [step.name for step in plan]

            self.assertIn("agent-daily", names)
            self.assertLess(names.index("agent-daily"), names.index("review-workbench"))
            agent = plan[names.index("agent-daily")]
            self.assertIn(str(paths.market_exports / "2026-06-11-daily-agent.md"), agent.outputs)
            self.assertIn(str(paths.review_daily_root / "2026-06-11" / "2026-06-11-daily-agent.html"), agent.outputs)

    def test_workbench_discovers_agent_brief_tab(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "复盘" / "matrices" / "strategy-review-workbench.html"
            daily_root = root / "复盘" / "daily"
            daily_dir = daily_root / "2026-06-11"
            daily_dir.mkdir(parents=True)
            out.parent.mkdir(parents=True)
            (daily_dir / "2026-06-11-daily-review.html").write_text("review", encoding="utf-8")
            (daily_dir / "2026-06-11-daily-agent.html").write_text("agent", encoding="utf-8")

            original_out = render_review_workbench.OUT
            original_daily_root = render_review_workbench.DAILY_ROOT
            try:
                render_review_workbench.OUT = out
                render_review_workbench.DAILY_ROOT = daily_root
                reviews = render_review_workbench.daily_reviews()
            finally:
                render_review_workbench.OUT = original_out
                render_review_workbench.DAILY_ROOT = original_daily_root

            self.assertTrue(reviews[0]["has_agent"])
            self.assertEqual(reviews[0]["agent_title"], "2026-06-11 Agent 简报")
            self.assertTrue(str(reviews[0]["agent_src"]).endswith("2026-06-11-daily-agent.html"))


if __name__ == "__main__":
    unittest.main()
