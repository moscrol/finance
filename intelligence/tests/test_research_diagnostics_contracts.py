"""研究进化 04 · 合同 / 归属 / 确定性 / 分母恒等式（规格 §3、§5、§8 第 7、9、11 条）。

夹具全部 synthetic（``intelligence/tests/fixtures/research_evolution/04/``），只作工程验收。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from intelligence.services.research_diagnostics import (
    DiagnosticPolicy,
    InvalidRef,
    ObjectRef,
    OwnerMismatch,
    ProcessReceipt,
    TimePoint,
    UnsupportedSchema,
    diagnose,
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


class RefAndTimeContracts(unittest.TestCase):
    def test_object_ref_rejects_unsafe_refs(self) -> None:
        for bad in ("../x", "/abs/path", "~/home", "a\\b"):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidRef):
                    ObjectRef(kind="judgment", namespace="judgments.jsonl", id=bad)
        with self.assertRaises(InvalidRef):
            ObjectRef(kind="judgment", namespace="judgments.jsonl")  # 既无 id 也无 ref

    def test_object_identity_ignores_version(self) -> None:
        a = ObjectRef(kind="judgment", namespace="judgments.jsonl", id="j1", version_or_hash="h1")
        b = ObjectRef(kind="judgment", namespace="judgments.jsonl", id="j1", version_or_hash="h2")
        self.assertEqual(a.identity, b.identity)

    def test_time_point_classification(self) -> None:
        self.assertEqual(TimePoint.from_dict("2026-09-02T20:00:00+08:00").granularity, "datetime")
        self.assertEqual(TimePoint.from_dict("2026-09-02").granularity, "date")
        # 无时区的时刻不能与截止比较：按只到日处理，不猜时区
        self.assertEqual(TimePoint.from_dict("2026-09-02T20:00:00").granularity, "date")
        self.assertEqual(TimePoint.from_dict("not-a-time").granularity, "unknown")
        self.assertEqual(TimePoint.from_dict(None).granularity, "unknown")

    def test_receipt_requires_kind_specific_payload(self) -> None:
        with self.assertRaises(DiagnosticsInputError):
            ProcessReceipt(receipt_id="r1", owner_user_id="u", kind="evidence_use", payload={})
        with self.assertRaises(DiagnosticsInputError):
            ProcessReceipt(receipt_id="r1", owner_user_id="u", kind="not_a_kind", payload={})


class OwnerAndSchemaGates(unittest.TestCase):
    def test_cross_owner_record_rejected_without_leaking_other_id(self) -> None:
        sc = load_fixture("scenario_full.json")
        foreign = dict(sc["records"][0], owner_user_id="u-beta-secret")
        with self.assertRaises(OwnerMismatch) as ctx:
            run_scenario(records=[foreign])
        self.assertNotIn("u-beta-secret", str(ctx.exception))

    def test_cross_owner_maintenance_report_rejected(self) -> None:
        mr = dict(load_fixture("maintenance_report_01.json"), owner_user_id="u-beta-secret")
        with self.assertRaises(OwnerMismatch):
            run_scenario(maintenance_reports=[mr])

    def test_unknown_maintenance_schema_rejected(self) -> None:
        mr = dict(load_fixture("maintenance_report_01.json"), schema_version="judgment-maintenance/v2")
        with self.assertRaises(UnsupportedSchema):
            run_scenario(maintenance_reports=[mr])

    def test_unknown_policy_schema_rejected(self) -> None:
        pol = dict(load_fixture("policy.json"), schema_version="research-diagnostics-policy/v9")
        with self.assertRaises(UnsupportedSchema):
            DiagnosticPolicy.from_dict(pol)

    def test_unknown_exercise_pack_schema_rejected(self) -> None:
        pack = dict(load_fixture("exercise_pack.json"), schema_version="other/v1")
        with self.assertRaises(UnsupportedSchema):
            run_scenario(exercise_cases=pack)

    def test_cutoff_before_end_is_rejected(self) -> None:
        with self.assertRaises(DiagnosticsInputError):
            run_scenario(knowledge_cutoff="2026-09-05")


class DeterminismAndDenominators(unittest.TestCase):
    def test_same_input_same_id_generated_at_excluded(self) -> None:
        sc = load_fixture("scenario_full.json")
        a = run_scenario(generated_at="2026-09-13T00:00:00+00:00")
        b = run_scenario(
            records=list(reversed(sc["records"])),
            verdicts=list(reversed(sc["verdicts"])),
            process_receipts=list(reversed(sc["process_receipts"])),
            generated_at="2026-09-14T09:00:00+00:00",
        )
        self.assertEqual(a.id, b.id)
        self.assertEqual(a.input_digest, b.input_digest)
        self.assertEqual([f.to_dict() for f in a.findings], [f.to_dict() for f in b.findings])
        self.assertNotEqual(a.generated_at, b.generated_at)
        self.assertNotIn("generated_at", a.content_dict())

    def test_denominator_identities_hold_and_unknown_is_not_success(self) -> None:
        report = run_scenario()
        self.assertTrue(report.denominators)
        for d in report.denominators:
            with self.subTest(kind=d.kind, group=d.actor_group):
                self.assertEqual(d.eligible, d.evaluated + d.unknown)
                self.assertEqual(d.evaluated, d.issue + d.context)
                self.assertIsNone(d.rate)
                self.assertEqual(d.unit, "original_object_check_opportunity")
        self.assertFalse([g for g in report.gaps if g.reason == "denominator_identity_broken"])
        late_user = next(d for d in report.denominators if d.kind == "late_registration" and d.actor_group == "user_original")
        self.assertGreater(late_user.unknown, 0)
        self.assertEqual(late_user.evaluated, late_user.issue + late_user.context)  # unknown 不进 evaluated

    def test_report_has_counts_only_no_rates_or_percentages(self) -> None:
        report = run_scenario()
        text = json.dumps(report.to_dict(), ensure_ascii=False)
        self.assertNotIn("%", text)
        self.assertNotIn("hit_rate", text)
        self.assertNotIn("win_rate", text)
        self.assertEqual(report.schema_version, "research-diagnostics/v1")
        self.assertEqual(report.provenance, "synthetic")

    def test_exercise_projection_carries_no_answer_key_content(self) -> None:
        report = run_scenario()
        self.assertIsNotNone(report.exercise)
        ex = report.exercise.to_dict()
        for forbidden in ("expected_choices", "expected_refs", "explanation_ref", "outcome_identity", "materials"):
            self.assertNotIn(forbidden, ex)
        self.assertTrue(ex["answer_key_ref"].startswith("answer-key:"))
        # 答案正文（题包里的 expected_choices）不得出现在整份报告里
        pack = load_fixture("exercise_pack.json")
        chosen = next(c for c in pack["cases"] if c["case_ref"] == ex["case_ref"])
        text = json.dumps(report.to_dict(), ensure_ascii=False)
        for choice in chosen["answer_key"]["expected_choices"]:
            self.assertNotIn(choice, text)


if __name__ == "__main__":
    unittest.main()
