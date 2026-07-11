from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.eval.claim_fidelity import (
    assert_stable_signature,
    build_gold_candidate,
    evaluate_registry,
    extract_claims,
    numbers_match,
    score_claims,
    verify_claim,
    verify_entity_version,
    write_gold_candidate,
)


def _claim(
    claim_id: str,
    *,
    text: str = "上涨家数为 3200",
    claim_type: str = "number",
    value: object = 3200,
    unit: str | None = None,
    source_ref: object = None,
) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "report_date": "2026-07-02",
        "report_path": "report.json",
        "location": "$.claim",
        "text_span": text,
        "claim_type": claim_type,
        "subject": "market",
        "predicate": "advancers",
        "value": value,
        "unit": unit,
        "source_ref": source_ref,
        "cutoff_timestamp": "2026-07-02T23:59:59+08:00",
        "verification_status": "unverifiable",
        "verification_reason": "",
    }


def _approved_gold(
    reviews: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "claim-fidelity-gold-1.0",
        "gold_status": "approved",
        "reviewer": "human-reviewer",
        "reviewed_at": "2026-07-11T12:00:00+08:00",
        "claims": reviews,
    }


class ClaimFidelityTests(unittest.TestCase):
    def test_numeric_units_percentages_rounding_and_tolerance(self) -> None:
        self.assertTrue(numbers_match(1.2, "亿", 12_000, "万"))
        self.assertTrue(numbers_match(5, "%", 0.05, None))
        self.assertTrue(
            numbers_match(
                3.1416,
                None,
                3.14159,
                None,
                rounding_decimals=3,
            )
        )
        self.assertTrue(
            numbers_match(
                100.1,
                None,
                100,
                None,
                relative_tolerance=0.002,
            )
        )
        self.assertFalse(numbers_match(1.2, "亿", 11_000, "万"))

    def test_entity_history_handles_rename_code_and_same_name(self) -> None:
        history = [
            {
                "entity_id": "bank-1",
                "name": "深发展A",
                "aliases": ["平安银行旧称"],
                "code": "000001.SZ",
                "classification": "银行",
                "valid_from": "1991-04-03",
                "valid_to": "2012-07-31",
            },
            {
                "entity_id": "bank-1",
                "name": "平安银行",
                "aliases": [],
                "code": "000001.SZ",
                "classification": "银行",
                "valid_from": "2012-08-01",
                "valid_to": "9999-12-31",
            },
        ]
        old_name = verify_entity_version(
            subject="深发展A",
            classification="银行",
            report_date="2011-01-01",
            history=history,
        )
        old_code = verify_entity_version(
            subject="000001",
            classification="银行",
            report_date="2011-01-01",
            history=history,
        )
        self.assertEqual(old_name["status"], "matched")
        self.assertEqual(old_code["status"], "matched")

        ambiguous = verify_entity_version(
            subject="同名公司",
            classification="材料",
            report_date="2026-01-01",
            history=[
                {
                    "entity_id": "a",
                    "name": "同名公司",
                    "classification": "材料",
                    "valid_from": "2020-01-01",
                },
                {
                    "entity_id": "b",
                    "name": "同名公司",
                    "classification": "化工",
                    "valid_from": "2020-01-01",
                },
            ],
        )
        self.assertEqual(ambiguous["status"], "needs_review")

    def test_current_constituent_cannot_replace_historical_version(
        self,
    ) -> None:
        result = verify_entity_version(
            subject="示例股份",
            classification="当前题材",
            report_date="2024-01-01",
            history=[
                {
                    "entity_id": "sample",
                    "name": "示例股份",
                    "classification": "当前题材",
                    "valid_from": "2026-01-01",
                }
            ],
        )
        self.assertEqual(result["status"], "unverifiable")
        self.assertIn("当前版本", str(result["reason"]))

    def test_report_level_reference_is_not_claim_evidence(self) -> None:
        claim = _claim(
            "N1",
            source_ref={
                "scope": "report",
                "source_time": "2026-07-02",
                "source": "fact_market_daily",
                "field": "advancers",
            },
        )
        verified = verify_claim(claim)
        metrics = score_claims([verified], None)
        self.assertEqual(verified["verification_status"], "missing")
        self.assertEqual(
            metrics["evidence_coverage_rate"]["numerator"],
            0,
        )

    def test_post_cutoff_announcement_is_rejected(self) -> None:
        claim = _claim(
            "N1",
            source_ref={
                "scope": "claim",
                "source_published_at": "2026-07-03T08:00:00+08:00",
                "source": "fact_market_daily",
                "field": "advancers",
                "valid_time": "2026-07-02",
            },
        )
        verified = verify_claim(claim, snapshot={"tables": {}})
        self.assertEqual(verified["verification_status"], "mismatch")
        self.assertTrue(verified["cutoff_violation"])

    def test_fact_inference_confusion_requires_approved_gold(self) -> None:
        claim = _claim(
            "F1",
            text="资金流入因此主线已经切换",
            claim_type="fact",
            value=None,
        )
        pending = score_claims([claim], None)
        self.assertIsNone(
            pending["fact_inference_confusion_rate"]["value"]
        )
        gold = _approved_gold(
            {
                "F1": {
                    "expected_type": "inference",
                    "entity_classification": "not_applicable",
                    "stage_feature": "not_applicable",
                    "timeline_position": None,
                    "causal_support": "fail",
                }
            }
        )
        reviewed = score_claims([claim], gold)
        self.assertEqual(
            reviewed["fact_inference_confusion_rate"]["value"],
            1.0,
        )

    def test_approved_gold_cannot_be_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "approved.gold.json"
            path.write_text(
                json.dumps(
                    {
                        "gold_status": "approved",
                        "reviewer": "human",
                        "reviewed_at": "2026-07-11",
                        "claims": {},
                    }
                ),
                encoding="utf-8",
            )
            candidate = build_gold_candidate(
                "2026-07-02",
                "abc",
                [_claim("N1")],
            )
            with self.assertRaises(FileExistsError):
                write_gold_candidate(path, candidate)

    def test_timeline_error_and_unsupported_causal_are_scored(self) -> None:
        claims = [
            _claim(
                "E1",
                text="2026-07-02 因为资金流入所以上涨",
                claim_type="inference",
                value=None,
            ),
            _claim(
                "E2",
                text="2026-07-01 公告发布",
                claim_type="fact",
                value=None,
            ),
        ]
        gold = _approved_gold(
            {
                "E1": {
                    "expected_type": "inference",
                    "entity_classification": "not_applicable",
                    "stage_feature": "not_applicable",
                    "timeline_position": 1,
                    "causal_support": "fail",
                },
                "E2": {
                    "expected_type": "fact",
                    "entity_classification": "not_applicable",
                    "stage_feature": "not_applicable",
                    "timeline_position": 2,
                    "causal_support": "not_applicable",
                },
            }
        )
        metrics = score_claims(claims, gold)
        self.assertEqual(metrics["timeline_precision"]["value"], 0.0)
        self.assertEqual(
            metrics["causal_statements"]["unsupported"],
            1,
        )

    def test_no_material_negative_control_remains_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "reports": [
                            {
                                "report_date": "2026-03-06",
                                "canonical_report_path": None,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            summary = evaluate_registry(
                registry_path=registry,
                repo_root=root,
                pit_dir=root / "pit",
                out_dir=root / "out",
            )
            report = summary["reports"][0]
            self.assertEqual(report["status"], "missing")
            self.assertIsNone(
                summary["metrics"]["numeric_match_rate"]["value"]
            )
            self.assertFalse(summary["phase_2_allowed"])

    def test_extractor_emits_required_claim_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            report.write_text(
                json.dumps(
                    {
                        "date": "2026-07-02",
                        "main_judgment": "上涨家数为 3200 家。",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            claims = extract_claims(
                "report.json",
                report_date="2026-07-02",
                repo_root=root,
            )
            required = {
                "claim_id",
                "report_date",
                "text_span",
                "claim_type",
                "subject",
                "predicate",
                "value",
                "unit",
                "source_ref",
                "cutoff_timestamp",
                "verification_status",
            }
            self.assertTrue(claims)
            self.assertTrue(required.issubset(claims[0]))

    def test_source_signature_change_fails(self) -> None:
        signature = {
            "device": 1,
            "inode": 2,
            "size": 3,
            "modified_ns": 4,
        }
        assert_stable_signature(signature, dict(signature))
        changed = {**signature, "modified_ns": 5}
        with self.assertRaises(RuntimeError):
            assert_stable_signature(signature, changed)


if __name__ == "__main__":
    unittest.main()
