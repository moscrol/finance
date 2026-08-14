from __future__ import annotations

import unittest

from scripts.audit_marker_vocabulary import (
    acceptance_report,
    baseline_from_report,
    build_report,
    classify_must_mention,
    compare_with_baseline,
    marker_vocabulary,
    slot_universe,
)


class SlotUniverseTest(unittest.TestCase):
    def test_contains_type_defaults_with_provenance(self):
        slots = slot_universe()
        self.assertIn("risk_signals", slots)
        self.assertIn("type:market_watch", slots["risk_signals"])

    def test_contains_wording_branch_slots(self):
        """比较类槽位只在措辞分支里出现，live 调用（空问句）拿不到——
        AST 那半漏了的话这条会红。"""
        slots = slot_universe()
        self.assertIn("comparison_conclusion", slots)
        self.assertIn(
            "wording:_explicit_required_outputs",
            slots["comparison_conclusion"],
        )


class ClassifyMustMentionTest(unittest.TestCase):
    def test_discharged_wins_over_everything(self):
        result = classify_must_mention(
            "缩量",
            equivalents={},
            discharged_by={"缩量": "fact:amount_vs_yesterday_pct"},
            marker_phrases={"缩量"},
        )
        self.assertEqual(result, "discharged")

    def test_marker_named_via_equivalent_substring(self):
        result = classify_must_mention(
            "证伪",
            equivalents={"证伪": ["失效"]},
            discharged_by={},
            marker_phrases={"失效条件"},
        )
        self.assertEqual(result, "marker_named")

    def test_grader_only_when_no_vocabulary_names_it(self):
        result = classify_must_mention(
            "断层",
            equivalents={},
            discharged_by={},
            marker_phrases={"当前主线", "失效条件"},
        )
        self.assertEqual(result, "grader_only")


class AcceptanceReportTest(unittest.TestCase):
    def test_totals_add_up_and_cases_cover_28(self):
        report = acceptance_report(marker_vocabulary())
        self.assertEqual(len(report["cases"]), 28)
        per_case = sum(
            len(row["discharged"]) + len(row["marker_named"]) + len(row["grader_only"])
            for row in report["cases"]
        )
        self.assertEqual(per_case, sum(report["totals"].values()))


class RatchetTest(unittest.TestCase):
    def test_current_report_passes_its_own_baseline(self):
        report = build_report()
        baseline = baseline_from_report(report)
        self.assertEqual(compare_with_baseline(report, baseline), [])

    def test_new_blind_slot_is_intercepted(self):
        report = build_report()
        baseline = baseline_from_report(report)
        baseline["slots_without_markers"] = [
            slot
            for slot in baseline["slots_without_markers"]
            if slot != "risk_signals"
        ]
        violations = compare_with_baseline(report, baseline)
        self.assertTrue(any("risk_signals" in item for item in violations))

    def test_new_grader_only_phrase_is_intercepted(self):
        report = build_report()
        baseline = baseline_from_report(report)
        baseline["grader_only"] = [
            {
                "case_id": row["case_id"],
                "phrases": [p for p in row["phrases"] if p != "断层"],
            }
            for row in baseline["grader_only"]
        ]
        violations = compare_with_baseline(report, baseline)
        self.assertTrue(any("断层" in item for item in violations))


if __name__ == "__main__":
    unittest.main()
