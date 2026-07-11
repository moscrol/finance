from __future__ import annotations

import unittest

from intelligence.eval.phase2_summary import build_phase2_summary


class Phase2SummaryTest(unittest.TestCase):
    def test_preserves_negative_controls_and_isolation(self) -> None:
        summary = build_phase2_summary(
            selection={
                "selected_count": 80,
                "dates": [
                    {
                        "report_date": "2026-03-02",
                        "report_status": "missing",
                        "canonical_report_path": None,
                    },
                    {
                        "report_date": "2026-06-02",
                        "report_status": "registered",
                        "canonical_report_path": "report.md",
                    },
                ],
                "selected_strata": {
                    "report_status": {
                        "registered": 25,
                        "missing": 55,
                    }
                },
            },
            input_report={
                "status_counts": {"known": {"partial": 80}},
                "output_isolation": {"outcome_not_written": True},
            },
            claim_summary={
                "report_status_counts": {
                    "audited": 25,
                    "missing": 55,
                },
                "metrics": {},
                "historical_replay": {},
                "claim_status_counts": {},
                "causal_statement_counts": {},
                "version_gap_status_counts": {},
                "gold_candidate_status_counts": {
                    "candidate": 80,
                    "approved": 0,
                },
                "blocking_version_gap_dates": ["2026-03-02"],
                "reports": [
                    {
                        "report_date": "2026-03-02",
                        "status": "missing",
                        "metrics": {
                            "numeric_match_rate": {"checked": 0},
                            "evidence_coverage_rate": {
                                "denominator": 0
                            },
                        },
                    },
                    {
                        "report_date": "2026-06-02",
                        "status": "audited",
                        "metrics": {
                            "numeric_match_rate": {"checked": 10},
                            "evidence_coverage_rate": {
                                "denominator": 20
                            },
                        },
                    },
                ],
            },
            outcome_report={
                "status_counts": {"ready": 80},
                "output_isolation": {"contains_as_known_at": False},
            },
            comparison_report={
                "status_counts": {"partial": 80},
                "known_dir": "/inputs/as_known_at",
                "final_dir": "/outcomes/final_history",
                "physically_separate": True,
            },
        )
        self.assertTrue(
            summary["negative_controls"][
                "dates_preserved_without_substitution"
            ]
        )
        self.assertTrue(
            summary["negative_controls"][
                "denominator_isolation_passed"
            ]
        )
        self.assertEqual(
            summary["negative_controls"]["missing_report_dates"],
            ["2026-03-02"],
        )
        self.assertEqual(
            summary["negative_controls"][
                "missing_report_denominator_contribution"
            ]["numeric_match_rate"],
            0,
        )
        self.assertTrue(summary["physical_isolation"]["passed"])
        self.assertFalse(summary["decision_eligible"])
        self.assertEqual(
            summary["gates"]["blocking_version_gap_dates"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
