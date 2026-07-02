from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_ingest_status_ledger import build_ledger, render_markdown


class IngestStatusLedgerTest(unittest.TestCase):
    def test_builds_status_ledger_from_candidate_backfill_and_review_queues(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate_path = root / "theme-candidates.json"
            backfill_path = root / "theme-backfill-queue.json"
            review_path = root / "theme-backfill-review-queue.json"
            candidates = {
                "trade_date": "2026-06-26",
                "candidates": [
                    {
                        "rank": 1,
                        "market_theme": "光刻机",
                        "canonical_concept": "光刻机",
                        "candidate_tier": "deep",
                        "priority_score": 99,
                    }
                ],
            }
            backfill_queue = {
                "trade_date": "2026-06-26",
                "items": [
                    {
                        "id": "2026-06-26-01-missing_evidence",
                        "trade_date": "2026-06-26",
                        "theme": "光刻机",
                        "canonical_concept": "光刻机",
                        "candidate_tier": "deep",
                        "rank": 1,
                        "priority": "high",
                        "priority_score": 99,
                        "gap_type": "missing_evidence",
                        "reason": "缺少本地证据支撑",
                    }
                ],
            }
            review_queue = {
                "trade_date": "2026-06-26",
                "items": [
                    {
                        "id": "2026-06-26-01-missing_evidence",
                        "trade_date": "2026-06-26",
                        "theme": "光刻机",
                        "canonical_concept": "光刻机",
                        "candidate_tier": "deep",
                        "rank": 1,
                        "priority": "high",
                        "priority_score": 99,
                        "gap_type": "missing_evidence",
                        "reason": "缺少本地证据支撑",
                        "review_status": "pending_review",
                        "review_action": "review_attach_or_archive_evidence",
                        "review_note": "先找 source。",
                    }
                ],
            }

            payload = build_ledger(candidates, backfill_queue, review_queue, candidate_path, backfill_path, review_path)

        self.assertEqual(payload["trade_date"], "2026-06-26")
        self.assertEqual(payload["status_counts"], {"candidate_detected": 1, "pending_review": 1})
        self.assertEqual(payload["item_count"], 2)
        review_item = [item for item in payload["items"] if item["gap_type"] == "missing_evidence"][0]
        self.assertEqual(review_item["ingest_status"], "pending_review")
        self.assertEqual(review_item["next_action"], "review_attach_or_archive_evidence")
        self.assertIn("Ingest Status Ledger", render_markdown(payload))

    def test_blocked_review_is_preserved(self) -> None:
        payload = build_ledger(
            {},
            {"trade_date": "2026-06-26", "items": []},
            {
                "trade_date": "2026-06-26",
                "items": [
                    {
                        "id": "blocked",
                        "trade_date": "2026-06-26",
                        "rank": 2,
                        "review_status": "blocked_review",
                        "review_action": "review_create_or_link_concept",
                    }
                ],
            },
            None,
            Path("backfill.json"),
            Path("review.json"),
        )

        self.assertEqual(payload["status_counts"], {"blocked_review": 1})
        self.assertEqual(payload["items"][0]["ingest_status"], "blocked_review")


if __name__ == "__main__":
    unittest.main()
