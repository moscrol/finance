import tempfile
import unittest
from pathlib import Path

from intelligence.paths import ProjectPaths
from intelligence.workflows.daily_review import DailyReviewOptions, build_daily_review_plan, filter_plan
from scripts import render_review_workbench


class DailyReviewAgentEntryTest(unittest.TestCase):
    def make_paths(self, root: Path) -> ProjectPaths:
        finance = root / "finance"
        (finance / "market_feature_store" / "exports").mkdir(parents=True)
        (finance / "复盘" / "daily").mkdir(parents=True)
        return ProjectPaths(finance_root=finance, knowledge_wiki=root / "wiki", finance_site=root / "site", market_snapshot_dir=root / "snapshot", vector_index_dir=root / ".rag_index")

    def test_daily_plan_generates_agent_brief_before_workbench(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))

            plan = build_daily_review_plan(DailyReviewOptions(date="2026-06-11"), paths)
            names = [step.name for step in plan]

            self.assertIn("agent-daily", names)
            self.assertLess(names.index("agent-daily"), names.index("review-workbench"))
            agent = plan[names.index("agent-daily")]
            self.assertIn(str(paths.market_exports / "2026-06-11-research-queue.json"), agent.outputs)
            self.assertIn(str(paths.review_daily_root / "2026-06-11" / "2026-06-11-research-queue.html"), agent.outputs)
            self.assertIn(str(paths.market_exports / "2026-06-11-daily-agent.md"), agent.outputs)
            self.assertIn(str(paths.review_daily_root / "2026-06-11" / "2026-06-11-daily-agent.html"), agent.outputs)
            self.assertEqual(agent.argv[agent.argv.index("--semantic-rag-top-n") + 1], "0")

            self.assertIn("kb-ingest-receive", names)
            self.assertEqual(names.index("kb-ingest-receive"), names.index("agent-daily") + 1)
            receive = plan[names.index("kb-ingest-receive")]
            self.assertIn("kb-queue-receive", receive.argv)
            self.assertIn(str(paths.knowledge_wiki), receive.argv)
            self.assertNotIn("--apply", receive.argv)
            self.assertIn("ima-gap-report", names)
            self.assertEqual(names.index("ima-gap-report"), names.index("kb-ingest-receive") + 1)
            gap = plan[names.index("ima-gap-report")]
            self.assertIn("ima-gap-report", gap.argv)
            self.assertIn(str(paths.market_exports / "2026-06-11-ima-gap.json"), gap.outputs)

    def test_skip_agent_also_skips_kb_ingest_receive(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            plan = build_daily_review_plan(DailyReviewOptions(date="2026-06-11", skip_agent=True), paths)
            names = [step.name for step in plan]
            self.assertNotIn("agent-daily", names)
            self.assertNotIn("kb-ingest-receive", names)
            self.assertNotIn("ima-gap-report", names)

    def test_daily_plan_gates_and_exports_before_report_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            plan = build_daily_review_plan(DailyReviewOptions(date="2026-06-11"), paths)
            names = [step.name for step in plan]

            self.assertLess(names.index("daily-update"), names.index("quality-gate"))
            self.assertLess(names.index("quality-gate"), names.index("cross-day-quality-gate"))
            self.assertLess(names.index("cross-day-quality-gate"), names.index("export-increment"))
            self.assertLess(names.index("export-increment"), names.index("daily-review"))

    def test_resume_from_report_cannot_bypass_release_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            options = DailyReviewOptions(date="2026-06-11", from_step="daily-review")
            plan, warnings = filter_plan(build_daily_review_plan(options, paths), options)

            self.assertEqual(
                [step.name for step in plan[:4]],
                ["quality-gate", "cross-day-quality-gate", "export-increment", "daily-review"],
            )
            self.assertTrue(any("cannot bypass" in warning for warning in warnings))

    def test_daily_plan_uses_explicit_kb_wiki_for_agent_and_cockpit(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            synced_kb = Path(tmp) / "synced-knowledge" / "wiki"

            plan = build_daily_review_plan(DailyReviewOptions(date="2026-06-11", kb_wiki=synced_kb), paths)
            by_name = {step.name: step for step in plan}

            self.assertIn(str(synced_kb), by_name["agent-daily"].argv)
            self.assertIn(str(synced_kb), by_name["kb-ingest-receive"].argv)
            self.assertIn("--knowledge-root", by_name["cockpit"].argv)
            self.assertIn(str(synced_kb.parent), by_name["cockpit"].argv)

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

    def test_workbench_prefers_research_queue_tab(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "复盘" / "matrices" / "strategy-review-workbench.html"
            daily_root = root / "复盘" / "daily"
            daily_dir = daily_root / "2026-06-11"
            daily_dir.mkdir(parents=True)
            out.parent.mkdir(parents=True)
            (daily_dir / "2026-06-11-daily-review.html").write_text("review", encoding="utf-8")
            (daily_dir / "2026-06-11-daily-agent.html").write_text("agent", encoding="utf-8")
            (daily_dir / "2026-06-11-research-queue.html").write_text("queue", encoding="utf-8")

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
            self.assertEqual(reviews[0]["agent_title"], "2026-06-11 研究队列")
            self.assertTrue(str(reviews[0]["agent_src"]).endswith("2026-06-11-research-queue.html"))

    def test_workbench_discovers_queue_without_full_agent_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "复盘" / "matrices" / "strategy-review-workbench.html"
            daily_root = root / "复盘" / "daily"
            daily_dir = daily_root / "2026-08-13"
            daily_dir.mkdir(parents=True)
            out.parent.mkdir(parents=True)
            (daily_dir / "2026-08-13-daily-review.html").write_text("review", encoding="utf-8")
            (daily_dir / "2026-08-13-research-queue.html").write_text("queue", encoding="utf-8")

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
            self.assertTrue(str(reviews[0]["agent_src"]).endswith("2026-08-13-research-queue.html"))


if __name__ == "__main__":
    unittest.main()
