from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from intelligence.eval.claim_fidelity import build_gold_candidate
from intelligence.eval.gold_review import (
    HUMAN_APPROVAL_CONFIRMATION,
    approve_consensus,
    build_consensus_candidate,
    build_review_template,
    render_review_summary,
    review_completion,
    reviewer_agreement,
    select_stratified_review_dates,
    write_json,
)


def _candidate() -> dict[str, object]:
    claims = [
        {
            "claim_id": "claim-1",
            "text_span": "光刻胶涨幅为 2.21%",
        },
        {
            "claim_id": "claim-2",
            "text_span": "光刻胶属于电子行业",
        },
    ]
    return build_gold_candidate("2026-06-11", "sha256", claims)


def _completed_review(
    reviewer: str,
    *,
    entity_second: str = "pass",
) -> dict[str, object]:
    review = build_review_template(_candidate(), reviewer=reviewer)
    claims = review["claims"]
    assert isinstance(claims, dict)
    for claim_id, decision in claims.items():
        assert isinstance(decision, dict)
        decision["expected_type"] = (
            "number" if claim_id == "claim-1" else "classification"
        )
        decision["entity_classification"] = (
            entity_second if claim_id == "claim-2" else "not_applicable"
        )
        decision["stage_feature"] = "not_applicable"
        decision["causal_support"] = "not_applicable"
    review["review_status"] = "completed"
    review["reviewed_at"] = "2026-07-11T12:00:00+00:00"
    return review


class GoldReviewTests(unittest.TestCase):
    def test_review_template_never_auto_approves(self) -> None:
        review = build_review_template(_candidate(), reviewer="reviewer-a")
        self.assertEqual(review["review_status"], "in_review")
        self.assertNotIn("gold_status", review)
        self.assertFalse(review_completion(review)["complete"])

    def test_dual_reviewer_agreement_counts_field_decisions(self) -> None:
        left = _completed_review("reviewer-a")
        right = _completed_review("reviewer-b", entity_second="fail")
        agreement = reviewer_agreement(left, right)
        self.assertEqual(agreement["agreed"], 7)
        self.assertEqual(agreement["compared"], 8)
        self.assertEqual(agreement["value"], 0.875)
        self.assertTrue(agreement["target_met"])
        self.assertEqual(len(agreement["disagreements"]), 1)

    def test_disagreement_requires_adjudication_before_approval(self) -> None:
        consensus = build_consensus_candidate(
            _candidate(),
            [
                _completed_review("reviewer-a"),
                _completed_review("reviewer-b", entity_second="fail"),
            ],
        )
        self.assertEqual(consensus["gold_status"], "needs_review")
        with self.assertRaises(ValueError):
            approve_consensus(
                consensus,
                approver="lead-reviewer",
                confirmation=HUMAN_APPROVAL_CONFIRMATION,
            )

    def test_explicit_human_confirmation_is_required_for_approval(
        self,
    ) -> None:
        left = _completed_review("reviewer-a")
        consensus = build_consensus_candidate(
            _candidate(),
            [left, deepcopy(left) | {"reviewer": "reviewer-b"}],
        )
        self.assertEqual(consensus["gold_status"], "candidate")
        with self.assertRaises(PermissionError):
            approve_consensus(
                consensus,
                approver="lead-reviewer",
                confirmation="yes",
            )
        approved = approve_consensus(
            consensus,
            approver="lead-reviewer",
            confirmation=HUMAN_APPROVAL_CONFIRMATION,
            reviewed_at="2026-07-11T13:00:00+00:00",
        )
        self.assertEqual(approved["gold_status"], "approved")
        self.assertEqual(approved["reviewer"], "lead-reviewer")

    def test_approved_gold_cannot_be_overwritten(self) -> None:
        left = _completed_review("reviewer-a")
        consensus = build_consensus_candidate(
            _candidate(),
            [left, deepcopy(left) | {"reviewer": "reviewer-b"}],
        )
        approved = approve_consensus(
            consensus,
            approver="lead-reviewer",
            confirmation=HUMAN_APPROVAL_CONFIRMATION,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gold.json"
            write_json(path, approved)
            with self.assertRaises(FileExistsError):
                write_json(path, _candidate())

    def test_stratified_selection_excludes_missing_reports(self) -> None:
        selection = {
            "dates": [
                {
                    "report_date": "2026-03-02",
                    "month": "2026-03",
                    "market_stage": "上升",
                    "data_completeness": "partial",
                    "report_status": "registered",
                    "canonical_report_path": "a.json",
                },
                {
                    "report_date": "2026-03-03",
                    "month": "2026-03",
                    "market_stage": "上升",
                    "data_completeness": "pending",
                    "report_status": "missing",
                    "canonical_report_path": None,
                },
                {
                    "report_date": "2026-04-01",
                    "month": "2026-04",
                    "market_stage": "震荡",
                    "data_completeness": "partial",
                    "report_status": "registered",
                    "canonical_report_path": "b.json",
                },
            ]
        }
        selected = select_stratified_review_dates(selection, count=20)
        self.assertEqual(
            [row["report_date"] for row in selected],
            ["2026-03-02", "2026-04-01"],
        )

    def test_summary_reports_pair_agreement(self) -> None:
        summary, html = render_review_summary(
            [
                _completed_review("reviewer-a"),
                _completed_review("reviewer-b"),
            ]
        )
        self.assertEqual(summary["completed_review_count"], 2)
        self.assertEqual(summary["paired_report_count"], 1)
        self.assertEqual(summary["agreement"]["value"], 1.0)
        self.assertIn("Gold 人工审核工作台", html)


if __name__ == "__main__":
    unittest.main()
