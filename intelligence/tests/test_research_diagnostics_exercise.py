"""研究进化 04 · 一题历史练习与三轴泄漏分档（规格 §6、§8 第 10 条）。"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from intelligence.services.research_diagnostics import (
    AnswerKey,
    ExerciseResponse,
    diagnose,
    evaluate_exercise_response,
)
from intelligence.services.research_diagnostics.contracts import DiagnosticsInputError

FX = Path(__file__).parent / "fixtures" / "research_evolution" / "04"


def load_fixture(name: str) -> dict:
    return json.loads((FX / name).read_text(encoding="utf-8"))


def run_scenario(**over):
    sc = load_fixture("scenario_full.json")
    kwargs = dict(
        owner_user_id=sc["owner_user_id"],
        start=sc["start"],
        end=sc["end"],
        knowledge_cutoff=sc["knowledge_cutoff"],
        records=sc["records"],
        verdicts=sc["verdicts"],
        maintenance_reports=[load_fixture("maintenance_report_01.json")],
        process_receipts=sc["process_receipts"],
        exercise_cases=load_fixture("exercise_pack.json"),
        policy=load_fixture("policy.json"),
        generated_at="2026-09-13T00:00:00+00:00",
    )
    kwargs.update(over)
    return diagnose(**kwargs)


def late_only_inputs():
    """只保留 os-late（唯一 issue 是迟登），其余不进。"""
    sc = load_fixture("scenario_full.json")
    rec = next(r for r in sc["records"] if r["record_id"] == "os-late")
    return dict(records=[rec], verdicts=[], process_receipts=[])


def pack_with(*case_ids: str) -> dict:
    pack = load_fixture("exercise_pack.json")
    pack["cases"] = [c for c in pack["cases"] if c["case_id"] in case_ids]
    return pack


class Selection(unittest.TestCase):
    def test_selects_one_case_deterministically_for_the_first_issue_kind(self) -> None:
        a = run_scenario()
        b = run_scenario(generated_at="2026-09-15T00:00:00+00:00")
        self.assertIsNotNone(a.exercise)
        self.assertEqual(a.exercise.to_dict(), b.exercise.to_dict())
        self.assertEqual(a.exercise.exercise_status, "ready")
        target = next(f for f in a.findings if f.id == a.exercise.target_finding_id)
        self.assertEqual(target.classification, "issue")
        self.assertEqual(target.kind, "condition_revision")  # 类别字典序第一个有 issue 的类
        self.assertEqual(a.exercise.case_ref, "case:revision:001")
        self.assertEqual(a.exercise.data_pit_grade, "strict")

    def test_no_issue_means_no_exercise_and_a_gap(self) -> None:
        sc = load_fixture("scenario_full.json")
        rec = next(r for r in sc["records"] if r["record_id"] == "ck-nodeadline")  # 只会产生 unknown
        report = run_scenario(records=[rec], verdicts=[], process_receipts=[])
        self.assertIsNone(report.exercise)
        self.assertIn("no_issue_findings", {g.reason for g in report.gaps})
        self.assertTrue(all(f.classification == "unknown" for f in report.findings))

    def test_issue_without_matching_case_is_a_gap_not_a_random_case(self) -> None:
        report = run_scenario(exercise_cases=pack_with("cx-stale-001"), **late_only_inputs())
        self.assertIsNone(report.exercise)
        gap = next(g for g in report.gaps if g.reason == "no_exercise_case_for_kind")
        self.assertEqual(gap.ref, "late_registration")


class LeakGrades(unittest.TestCase):
    def test_strict_declared_pack_with_undated_material_is_downgraded_to_unverifiable(self) -> None:
        report = run_scenario(exercise_cases=pack_with("cx-late-002"), **late_only_inputs())
        self.assertEqual(report.exercise.data_pit_grade, "unverifiable")
        self.assertIn("时间不明", report.exercise.limitation)
        good = run_scenario(exercise_cases=pack_with("cx-late-001"), **late_only_inputs())
        self.assertEqual(good.exercise.data_pit_grade, "strict")

    def test_material_dated_after_cutoff_is_downgraded(self) -> None:
        pack = pack_with("cx-late-001")
        pack["cases"][0]["materials"][0]["dated"] = "2026-06-25"  # 晚于 knowledge_cutoff 2026-06-20
        report = run_scenario(exercise_cases=pack, **late_only_inputs())
        self.assertEqual(report.exercise.data_pit_grade, "unverifiable")

    def test_model_exposure_downgrades_and_renaming_does_not_wash_it(self) -> None:
        inputs = late_only_inputs()
        receipts = [
            {
                "receipt_id": "mx-1",
                "owner_user_id": "u-alpha",
                "provenance": "synthetic",
                "kind": "model_exposure",
                "occurred_at": "2026-09-01T00:00:00+08:00",
                "payload": {"outcome_identity": "oc-late-001", "model_id": "m-synthetic"},
            }
        ]
        pack = pack_with("cx-late-001")
        pack["cases"][0]["case_id"] = "cx-late-001-renamed"
        pack["cases"][0]["case_ref"] = "case:late:001-renamed"
        pack["cases"][0]["prompt"] = pack["cases"][0]["prompt"].replace("2026-06-20", "某日")
        inputs["process_receipts"] = receipts
        report = run_scenario(exercise_cases=pack, **inputs)
        self.assertEqual(report.exercise.model_exposure_grade, "known_exposed")
        clean = run_scenario(exercise_cases=pack, **late_only_inputs())
        self.assertEqual(clean.exercise.model_exposure_grade, "deterministic_only")

    def test_learner_exposure_prefers_unseen_and_labels_repeats(self) -> None:
        pack = pack_with("cx-late-001", "cx-late-002")
        first = run_scenario(exercise_cases=pack, **late_only_inputs())
        seen_case = next(c["case_id"] for c in pack["cases"] if c["case_ref"] == first.exercise.case_ref)
        other = next(c for c in pack["cases"] if c["case_id"] != seen_case)
        inputs = late_only_inputs()
        inputs["process_receipts"] = [
            {
                "receipt_id": "xs-1",
                "owner_user_id": "u-alpha",
                "provenance": "synthetic",
                "kind": "exercise_seen",
                "occurred_at": "2026-09-02T00:00:00+08:00",
                "payload": {"case_id": seen_case},
            }
        ]
        second = run_scenario(exercise_cases=pack, **inputs)
        self.assertEqual(second.exercise.case_ref, other["case_ref"])  # 优先未见
        self.assertEqual(second.exercise.learner_exposure_grade, "not_declared")
        inputs["process_receipts"].append(
            {
                "receipt_id": "xs-2",
                "owner_user_id": "u-alpha",
                "provenance": "synthetic",
                "kind": "exercise_seen",
                "occurred_at": "2026-09-03T00:00:00+08:00",
                "payload": {"outcome_identity": other["outcome_identity"]},  # 按结局身份命中，不看题名
            }
        )
        third = run_scenario(exercise_cases=pack, **inputs)
        self.assertEqual(third.exercise.learner_exposure_grade, "seen_or_repeated")
        self.assertEqual(third.exercise.exercise_status, "ready")  # 重复题仍可交，只是分列

    def test_self_declared_unseen_is_recorded_not_verified(self) -> None:
        inputs = late_only_inputs()
        inputs["process_receipts"] = [
            {
                "receipt_id": "ld-1",
                "owner_user_id": "u-alpha",
                "provenance": "synthetic",
                "kind": "learner_declaration",
                "occurred_at": "2026-09-02T00:00:00+08:00",
                "payload": {"case_id": "cx-late-001", "declared": "unseen"},
            }
        ]
        report = run_scenario(exercise_cases=pack_with("cx-late-001"), **inputs)
        self.assertEqual(report.exercise.learner_exposure_grade, "declared_unseen")


class Feedback(unittest.TestCase):
    def _exercise_and_key(self):
        report = run_scenario(exercise_cases=pack_with("cx-late-001"), **late_only_inputs())
        case = pack_with("cx-late-001")["cases"][0]
        return report.exercise, AnswerKey.from_dict(case["answer_key"])

    def test_structured_answer_is_checked_and_prose_goes_to_manual_review(self) -> None:
        exercise, key = self._exercise_and_key()
        fb = evaluate_exercise_response(
            exercise=exercise,
            response=ExerciseResponse(exercise_id=exercise.id, selected_choices=["deadline_next_open_0930"], cited_refs=["case:late:001:script"]),
            answer_key=key,
        )
        self.assertEqual(fb.status, "checked")
        self.assertTrue(all(c.passed for c in fb.checks))
        self.assertEqual(fb.missing_evidence_refs, ())
        self.assertEqual(fb.explanation_ref, "explain:cx-late-001:v1")  # 答后才解锁
        fb2 = evaluate_exercise_response(
            exercise=exercise,
            response=ExerciseResponse(exercise_id=exercise.id, selected_choices=["wrong"], cited_refs=[], rationale="我觉得是收盘前"),
            answer_key=key,
        )
        self.assertEqual(fb2.status, "manual_review")
        self.assertFalse(any(c.passed for c in fb2.checks))
        self.assertEqual(fb2.missing_evidence_refs, ("case:late:001:script",))

    def test_wrong_answer_key_or_exercise_id_is_rejected(self) -> None:
        exercise, key = self._exercise_and_key()
        other_key = AnswerKey.from_dict(dict(copy.deepcopy(pack_with("cx-late-002")["cases"][0]["answer_key"])))
        with self.assertRaises(DiagnosticsInputError):
            evaluate_exercise_response(exercise=exercise, response=ExerciseResponse(exercise_id=exercise.id), answer_key=other_key)
        with self.assertRaises(DiagnosticsInputError):
            evaluate_exercise_response(exercise=exercise, response=ExerciseResponse(exercise_id="hx-other"), answer_key=key)


if __name__ == "__main__":
    unittest.main()
