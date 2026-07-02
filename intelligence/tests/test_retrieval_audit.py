from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from intelligence.services.research_brief import audit_evidence_chain, build_retrieval_telemetry
from intelligence.services.retrieval_audit import (
    append_record,
    build_audit_record,
    load_failure_samples,
    load_records,
    summarize_ledger,
)

GOOD_CHAIN = [
    "英维克：公告披露液冷订单落地，签订供货合同（公告） [R1]",
    "板块双红，涨停热度集中 [S1]",
]
WEAK_CHAIN = ["题材研报预计有望受益 [W1]"]


def _record(chain, query="q", wiki_stats=None, citation_tags=("R1", "S1")):
    audit = audit_evidence_chain(chain)
    tele = build_retrieval_telemetry(
        audit=audit, citation_tags=list(citation_tags), wiki_stats=wiki_stats
    )
    return build_audit_record(
        query=query,
        question_type="theme_analysis",
        trade_date="2026-07-01",
        audit=audit,
        telemetry=tele,
        market_phase="主升扩散",
    )


class BuildRecordTests(unittest.TestCase):
    def test_healthy_answer_has_no_failure_tags(self) -> None:
        rec = _record(GOOD_CHAIN)
        self.assertFalse(rec.is_failure)
        self.assertTrue(rec.covers_l3)
        self.assertEqual(rec.market_phase, "主升扩散")

    def test_weak_answer_tags_no_l3(self) -> None:
        rec = _record(WEAK_CHAIN, citation_tags=("W1",))
        self.assertIn("no_l3_coverage", rec.failure_tags)

    def test_empty_retrieval_and_degradation_tagged(self) -> None:
        rec = _record(
            [],
            citation_tags=(),
            wiki_stats={"attempted": True, "ok": False, "mode": "hybrid", "warning": "timeout"},
        )
        self.assertIn("empty_retrieval", rec.failure_tags)
        self.assertIn("wiki_degraded", rec.failure_tags)
        self.assertIn("insufficient_evidence", rec.failure_tags)


class LedgerTests(unittest.TestCase):
    def test_append_load_and_summarize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger" / "retrieval_audit.jsonl"
            append_record(path, _record(GOOD_CHAIN, query="好样本"))
            append_record(path, _record(WEAK_CHAIN, query="弱样本", citation_tags=("W1",)))
            records = load_records(path)
            self.assertEqual(len(records), 2)
            failures = load_failure_samples(path)
            self.assertEqual([r["query"] for r in failures], ["弱样本"])
            summary = summarize_ledger(path)
            self.assertEqual(summary["total"], 2)
            self.assertEqual(summary["failures"], 1)
            self.assertAlmostEqual(summary["failure_rate"], 0.5)
            self.assertAlmostEqual(summary["l3_coverage_rate"], 0.5)
            self.assertIn("no_l3_coverage", summary["failure_tag_distribution"])
            self.assertIn("R", summary["source_hit_totals"])

    def test_missing_ledger_is_empty(self) -> None:
        self.assertEqual(load_records("/nonexistent/ledger.jsonl"), [])
        self.assertEqual(summarize_ledger("/nonexistent/ledger.jsonl"), {"total": 0})


if __name__ == "__main__":
    unittest.main()
