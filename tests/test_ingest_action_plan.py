from __future__ import annotations

import unittest
from pathlib import Path

from scripts.build_ingest_action_plan import build_action_plan, render_markdown


class IngestActionPlanTest(unittest.TestCase):
    def _indexed_ledger(self) -> dict:
        return {
            "trade_date": "2026-06-26",
            "items": [
                {
                    "id": "a-missing-evidence",
                    "ingest_status": "pending_review",
                    "index_status": "concept_page_exists",
                    "gap_type": "missing_evidence",
                    "theme": "光学光电子",
                    "canonical_concept": "LED芯片",
                    "rank": 1,
                    "index_probe": {"concept_page_exists": True, "rag_indexed": False},
                },
                {
                    "id": "b-missing-concept-indexed",
                    "ingest_status": "backfill_queued",
                    "index_status": "rag_indexed",
                    "gap_type": "missing_concept",
                    "theme": "存储芯片",
                    "canonical_concept": "存储芯片",
                    "rank": 2,
                    "index_probe": {"concept_page_exists": True, "rag_indexed": True},
                },
                {
                    "id": "c-placeholder",
                    "ingest_status": "backfill_queued",
                    "index_status": "missing_concept_name",
                    "gap_type": "placeholder_market_theme",
                    "theme": "连板未映射",
                    "canonical_concept": "",
                    "rank": 3,
                    "index_probe": {"concept_page_exists": False, "rag_indexed": False},
                },
                {
                    "id": "d-no-gap",
                    "ingest_status": "candidate_detected",
                    "gap_type": "",
                    "theme": "光刻机",
                    "canonical_concept": "光刻机",
                    "rank": 4,
                },
            ],
        }

    def test_maps_gaps_to_dry_run_commands_and_skips_indexed(self) -> None:
        wiki = Path("/kb/wiki")
        kb_root = Path("/kb")
        plan = build_action_plan(self._indexed_ledger(), wiki, kb_root, Path("/exports/indexed.json"))

        self.assertFalse(plan["execute"])
        # the no-gap candidate row is excluded
        self.assertEqual(plan["item_count"], 3)
        by_id = {row["id"]: row for row in plan["items"]}

        evidence = by_id["a-missing-evidence"]
        self.assertEqual(evidence["command_kind"], "kb_materialize_source_stubs_dry_run")
        self.assertEqual(evidence["action_mode"], "dry_run")
        self.assertIn("materialize_missing_source_stubs.py", evidence["recommended_command"])
        self.assertIn(str(wiki), evidence["recommended_command"])

        indexed = by_id["b-missing-concept-indexed"]
        self.assertEqual(indexed["action_mode"], "already_indexed")
        self.assertEqual(indexed["command_kind"], "skip_already_indexed")
        self.assertEqual(indexed["recommended_command"], "")

        placeholder = by_id["c-placeholder"]
        self.assertEqual(placeholder["action_mode"], "manual")
        self.assertEqual(placeholder["recommended_command"], "")

        self.assertEqual(plan["action_mode_counts"], {"already_indexed": 1, "dry_run": 1, "manual": 1})
        self.assertIn("Ingest Action Plan", render_markdown(plan))

    def test_already_indexed_items_sort_before_actionable(self) -> None:
        wiki = Path("/kb/wiki")
        kb_root = Path("/kb")
        plan = build_action_plan(self._indexed_ledger(), wiki, kb_root, Path("/exports/indexed.json"))
        self.assertEqual(plan["items"][0]["action_mode"], "already_indexed")


if __name__ == "__main__":
    unittest.main()
