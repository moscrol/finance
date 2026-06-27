import json
import tempfile
import unittest
from pathlib import Path

from intelligence.paths import ProjectPaths
from scripts.build_daily_ops_ledger import build_ledger, date_compact, expected_market_outputs


class DailyOpsLedgerTest(unittest.TestCase):
    def make_paths(self, root: Path) -> ProjectPaths:
        finance = root / "finance"
        wiki = root / "knowledge" / "wiki"
        (finance / "market_feature_store" / "exports").mkdir(parents=True)
        (finance / "复盘" / "daily").mkdir(parents=True)
        (wiki / "briefings").mkdir(parents=True)
        (wiki / "relations").mkdir(parents=True)
        return ProjectPaths(finance_root=finance, knowledge_wiki=wiki, finance_site=root / "site", market_snapshot_dir=root / "snapshot")

    def test_date_compact_and_expected_market_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            self.assertEqual(date_compact("2026-06-21"), "20260621")
            names = [item.name for item in expected_market_outputs(paths, "2026-06-21")]
            self.assertIn("daily_review_md", names)
            self.assertIn("theme_candidates_json", names)
            self.assertIn("daily_workflow_summary_json", names)

    def test_missing_market_outputs_create_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            ledger = build_ledger("2026-06-21", paths)
            self.assertEqual(ledger["sections"]["market_review"]["missing_count"], 10)
            self.assertTrue(any("daily workflow" in action for action in ledger["next_actions"]))

    def test_inbox_and_debt_counts_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            knowledge_root = paths.knowledge_wiki.parent
            (knowledge_root / "未入库").mkdir()
            (knowledge_root / "未入库" / "sample.md").write_text("x", encoding="utf-8")
            (knowledge_root / "待人工确认").mkdir()
            (knowledge_root / "待人工确认" / "review.md").write_text("x", encoding="utf-8")
            theme = paths.knowledge_wiki / "raw" / "theme-radar"
            theme.mkdir(parents=True)
            (theme / "missing-concept-audit.json").write_text(
                json.dumps({"missing_concepts": ["a", "b"]}),
                encoding="utf-8",
            )
            ledger = build_ledger("2026-06-21", paths)
            self.assertEqual(ledger["sections"]["ima_stock"]["incoming_uningested_md_count"], 1)
            self.assertEqual(ledger["sections"]["ima_stock"]["manual_review_md_count"], 1)
            self.assertEqual(ledger["debts"]["missing_concepts"]["count"], 2)
            self.assertTrue(any("IMA stock-card ingest" in action for action in ledger["next_actions"]))


if __name__ == "__main__":
    unittest.main()
