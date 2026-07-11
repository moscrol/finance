from __future__ import annotations

import unittest

from intelligence.eval.phase2_summary import build_phase2_summary


class Phase2SummaryTest(unittest.TestCase):
    def test_preserves_negative_controls_and_isolation(self) -> None:
        summary = build_phase2_summary(
            selection={
                "selected_count": 80,
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
                "preserved_without_substitution"
            ]
        )
        self.assertTrue(summary["physical_isolation"]["passed"])
        self.assertFalse(summary["decision_eligible"])
        self.assertEqual(
            summary["gates"]["blocking_version_gap_dates"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
