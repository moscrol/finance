import tempfile
import unittest
from pathlib import Path

from intelligence.paths import ProjectPaths
from intelligence.workflows.daily_review import DailyReviewOptions, build_daily_review_plan
from scripts import render_cockpit


class CockpitAgentEntryTest(unittest.TestCase):
    def make_paths(self, root: Path) -> ProjectPaths:
        finance = root / "finance"
        (finance / "market_feature_store" / "exports").mkdir(parents=True)
        (finance / "复盘" / "daily").mkdir(parents=True)
        (finance / "复盘" / "matrices").mkdir(parents=True)
        return ProjectPaths(finance_root=finance, knowledge_wiki=root / "wiki", finance_site=root / "site")

    def test_daily_plan_rebuilds_cockpit_after_workbench(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))

            plan = build_daily_review_plan(DailyReviewOptions(date="2026-06-11"), paths)
            names = [step.name for step in plan]

            self.assertIn("review-workbench", names)
            self.assertIn("cockpit", names)
            self.assertLess(names.index("review-workbench"), names.index("cockpit"))
            cockpit = plan[names.index("cockpit")]
            self.assertIn(str(paths.finance_root / "复盘" / "index.html"), cockpit.outputs)

    def test_cockpit_daily_cards_link_agent_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fupan = root / "复盘"
            daily_root = fupan / "daily"
            daily_dir = daily_root / "2026-06-11"
            daily_dir.mkdir(parents=True)
            (daily_dir / "2026-06-11-daily-review.html").write_text("review", encoding="utf-8")
            (daily_dir / "2026-06-11-daily-agent.html").write_text("agent", encoding="utf-8")

            original_daily = render_cockpit.DAILY
            original_out = render_cockpit.OUT_PATH
            try:
                render_cockpit.DAILY = daily_root
                render_cockpit.OUT_PATH = fupan / "index.html"
                cards = render_cockpit.daily_cards()
            finally:
                render_cockpit.DAILY = original_daily
                render_cockpit.OUT_PATH = original_out

            self.assertEqual(len(cards), 1)
            self.assertIn("Agent 简报", cards[0])
            self.assertIn("2026-06-11-daily-agent.html", cards[0])


if __name__ == "__main__":
    unittest.main()
