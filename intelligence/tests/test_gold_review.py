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
    build_gold_candidate_from_sample_batch,
    build_review_template,
    collect_claim_review_samples,
    render_review_summary,
    review_completion,
    reviewer_agreement,
    select_stratified_review_dates,
    validate_claim_review_batch,
    write_json,
)
from intelligence.services.fidelity_contract import (
    build_claim_manifest_metadata,
    report_manifest_payload,
    seal_artifact,
)
from intelligence.tests.test_fidelity_contract import _valid_report


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


def _report_with_claims(count: int) -> dict[str, object]:
    report = _valid_report()
    claims = [
        claim
        for claim in report["claims"]
        if claim["manifest_scope"] == "public_narrative"
    ]
    for index in range(count):
        claims.append(
            {
                "claim_id": f"sample-claim-{index}",
                "manifest_scope": "evidence_fact",
                "text": f"样本声明 {index}",
                "text_span": f"样本声明 {index}",
                "claim_type": (
                    "number"
                    if index % 4 == 0
                    else (
                        "classification"
                        if index % 4 == 1
                        else "fact"
                    )
                ),
                "expected_type": "factual_statement",
                "subject": f"主题{index % 7}",
                "predicate": "测试",
                "value": index,
                "valid_time": "2026-07-10",
                "evidence_refs": ["ev-1"] if index % 2 else [],
            }
        )
    report["claims"] = claims
    report["claim_manifest"] = build_claim_manifest_metadata(report, claims)
    seal_artifact(
        report,
        artifact_kind="daily-agent",
        report_date="2026-07-10",
        generator_commit="a" * 40,
        snapshot_captured_at=report["snapshot_captured_at"],
        report_generated_at=report["report_generated_at"],
        manifest_payload=report_manifest_payload(report),
        run_id=report["run_id"],
    )
    return report


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
        self.assertIsNotNone(
            agreement["by_field"]["entity_classification"]["kappa"]
        )

    def test_same_reviewer_is_not_independent_review(self) -> None:
        left = _completed_review("reviewer-a")
        right = _completed_review("reviewer-a")
        with self.assertRaises(ValueError):
            reviewer_agreement(left, right)

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

    def test_claim_sampling_builds_blind_review_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = []
            for index, count in enumerate((90, 90, 90)):
                path = root / f"2026-07-{10 + index}-daily-agent.json"
                write_json(
                    path,
                    _report_with_claims(count),
                    protect_approved=False,
                )
                reports.append(path)

            batch = collect_claim_review_samples(
                reports,
                target_count=150,
                seed="unit-test-seed",
            )
            again = collect_claim_review_samples(
                list(reversed(reports)),
                target_count=150,
                seed="unit-test-seed",
            )

            self.assertEqual(batch["status"], "sampling_ready")
            self.assertEqual(batch["selected_count"], 150)
            self.assertEqual(batch["batch_sha256"], again["batch_sha256"])
            self.assertGreater(len(batch["strata"]), 1)
            self.assertFalse(validate_claim_review_batch(batch))

            candidate = build_gold_candidate_from_sample_batch(batch)
            review = build_review_template(candidate, reviewer="reviewer-a")

            self.assertEqual(review["review_status"], "in_review")
            self.assertEqual(len(review["claims"]), 150)
            self.assertEqual(
                review["source_batch_sha256"],
                batch["batch_sha256"],
            )
            self.assertEqual(
                len(review["sample_metadata"]),
                150,
            )
            self.assertIn(
                "independently",
                review["instructions"]["blind_review_protocol"],
            )

    def test_claim_sampling_flags_insufficient_forward_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-10-daily-agent.json"
            write_json(
                path,
                _report_with_claims(5),
                protect_approved=False,
            )

            batch = collect_claim_review_samples(
                [path],
                target_count=150,
            )

            self.assertEqual(batch["status"], "insufficient_forward_claims")
            self.assertIn(
                "selected_count is below 150",
                validate_claim_review_batch(batch),
            )
            with self.assertRaises(ValueError):
                build_gold_candidate_from_sample_batch(batch)


if __name__ == "__main__":
    unittest.main()
