import json
import tempfile
import unittest
from pathlib import Path

from intelligence.paths import ProjectPaths
from scripts.build_daily_ops_ledger import (
    FileCheck,
    build_ledger,
    build_next_actions,
    date_compact,
    expected_market_outputs,
    render_markdown,
    scan_debts,
    scan_ima_stock,
)


class DailyOpsLedgerTest(unittest.TestCase):
    def make_paths(self, root: Path) -> ProjectPaths:
        finance = root / "finance"
        wiki = root / "knowledge" / "wiki"
        (finance / "market_feature_store" / "exports").mkdir(parents=True)
        (finance / "复盘" / "daily").mkdir(parents=True)
        (wiki / "briefings").mkdir(parents=True)
        (wiki / "relations").mkdir(parents=True)
        return ProjectPaths(finance_root=finance, knowledge_wiki=wiki, finance_site=root / "site", market_snapshot_dir=root / "snapshot", vector_index_dir=wiki.parent / ".rag_index")

    def write_debt_audits(self, paths: ProjectPaths):
        raw = paths.knowledge_wiki / "raw"
        for name, key in (
            ("theme-radar/missing-concept-audit.json", "missing_concepts"),
            ("theme-radar/missing-evidence-source-audit.json", "missing_sources"),
            ("ima-stock/audits/entity-stock-ima-coverage-2026-06-21.json", "missing"),
        ):
            path = raw / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({key: []}), encoding="utf-8")

    def test_missing_audits_are_unknown_not_zero_debt(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            debt = scan_debts(paths)
            self.assertEqual(debt["status"], "WARN")
            self.assertIsNone(debt["missing_concepts"]["count"])
            self.assertEqual(debt["missing_concepts"]["error"], "missing")
            ledger = build_ledger("2026-06-21", paths)
            self.assertTrue(any("audit reports" in action for action in ledger["next_actions"]))

    def test_only_valid_empty_audits_prove_zero_debt(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            self.write_debt_audits(paths)
            debt = scan_debts(paths)
            self.assertEqual(debt["status"], "PASS")
            self.assertEqual(debt["missing_concepts"]["count"], 0)
            self.assertEqual(debt["missing_sources"]["count"], 0)
            self.assertEqual(debt["ima_stock_coverage"]["missing_count"], 0)

    def test_invalid_audits_warn_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            cases = (
                ("theme-radar/missing-concept-audit.json", "missing_concepts", "missing_concepts", "count"),
                ("theme-radar/missing-evidence-source-audit.json", "missing_sources", "missing_sources", "count"),
                ("ima-stock/audits/entity-stock-ima-coverage-2026-06-21.json", "missing", "ima_stock_coverage", "missing_count"),
            )
            for name, key, section, count_key in cases:
                invalid = ["{", "null", "[]", "{}", json.dumps({key: None}), json.dumps({key: ""}), json.dumps({key: {}})]
                for text in invalid:
                    with self.subTest(name=name, text=text):
                        self.write_debt_audits(paths)
                        (paths.knowledge_wiki / "raw" / name).write_text(text, encoding="utf-8")
                        debt = scan_debts(paths)
                        self.assertEqual(debt["status"], "WARN")
                        self.assertIsNone(debt[section][count_key])
                        self.assertTrue(debt[section]["error"])

    def test_missing_ima_folders_are_not_an_empty_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            result = scan_ima_stock(paths, "2026-06-21")
            self.assertEqual(result["status"], "WARN")
            self.assertEqual(len(result["missing_folders"]), 3)
            for folder in result["folders"].values():
                Path(folder).mkdir()
            result = scan_ima_stock(paths, "2026-06-21")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["missing_folders"], [])

    def test_directory_does_not_satisfy_file_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(FileCheck("report", Path(tmp)).as_dict()["exists"])

    def test_warn_sections_cannot_emit_complete_surface_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            self.write_debt_audits(paths)
            for folder in ("未入库", "已入库", "待人工确认"):
                (paths.knowledge_wiki.parent / folder).mkdir()
            for check in expected_market_outputs(paths, "2026-06-21"):
                check.path.parent.mkdir(parents=True, exist_ok=True)
                check.path.write_text("fixture", encoding="utf-8")
            (paths.knowledge_wiki / "briefings" / "2026-06-21.md").write_text("fixture", encoding="utf-8")
            ledger = build_ledger("2026-06-21", paths)
            self.assertEqual(ledger["status"], "WARN")
            self.assertTrue(any("relation" in action for action in ledger["next_actions"]))
            self.assertFalse(any("surface is complete" in action for action in ledger["next_actions"]))
            for check in ledger["sections"]["relations"]["missing"]:
                Path(check["path"]).write_text("{}", encoding="utf-8")
            ledger = build_ledger("2026-06-21", paths)
            self.assertEqual(ledger["status"], "PASS")
            self.assertTrue(any("inventory" in action for action in build_next_actions(ledger)))

    def test_scope_is_visible_in_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = build_ledger("2026-06-21", self.make_paths(Path(tmp)))
            self.assertEqual(ledger["scope"], "file_inventory_only")
            self.assertIn("file_inventory_only", render_markdown(ledger))

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
