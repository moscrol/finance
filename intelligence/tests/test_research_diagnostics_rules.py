"""研究进化 04 · 五类检查的反向证伪（规格 §4、§8 第 1–8 条）。

每条验收都配「错误实现会怎样变红」：删掉某个子句（覆盖声明、曝光时序、规则生效期）后对应断言必须翻转，
所以这里既断言正例，也用改输入的方式断言负例。
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from intelligence.services.research_diagnostics import diagnose

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


def findings_of(report, kind: str, object_id: str):
    return [f for f in report.findings if f.kind == kind and f.object_refs[0].id == object_id]


def one(report, kind: str, object_id: str):
    fs = findings_of(report, kind, object_id)
    assert len(fs) == 1, (kind, object_id, [f.to_dict() for f in fs])
    return fs[0]


def denominator(report, kind: str, group: str):
    return next(d for d in report.denominators if d.kind == kind and d.actor_group == group)


class LateRegistration(unittest.TestCase):
    def test_a1_miss_with_complete_process_has_zero_issue_and_hit_with_late_registration_is_detected(self) -> None:
        report = run_scenario()
        # os-timely：按时登记、到期有 miss 回检 → 两条都是 context，零 issue
        self.assertEqual(one(report, "late_registration", "os-timely").classification, "context")
        self.assertEqual(one(report, "overdue_unreviewed", "os-timely").classification, "context")
        self.assertFalse([f for f in report.findings if f.object_refs[0].id == "os-timely" and f.classification == "issue"])
        # os-late：回检 hit，但登记晚于次日开盘 → 迟登照样检出
        late = one(report, "late_registration", "os-late")
        self.assertEqual(late.classification, "issue")
        self.assertEqual((late.rule_id, late.rule_version), ("R-LATE", "v1"))
        self.assertIn("observation_script.default_next_open", late.evidence_refs)
        self.assertEqual(one(report, "overdue_unreviewed", "os-late").classification, "context")

    def test_missing_deadline_and_date_only_are_unknown_not_issue(self) -> None:
        report = run_scenario()
        nodeadline = one(report, "late_registration", "ck-nodeadline")
        self.assertEqual(nodeadline.classification, "unknown")
        self.assertEqual([g.reason for g in nodeadline.gaps], ["deadline_missing"])
        dateonly = one(report, "late_registration", "ck-dateonly")
        self.assertEqual(dateonly.classification, "unknown")
        self.assertEqual([g.reason for g in dateonly.gaps], ["recorded_at_date_only"])
        self.assertEqual(dateonly.pit_grade, "trade_date_only")

    def test_backfill_hindsight_and_non_ex_ante_objects_are_excluded_with_reasons(self) -> None:
        report = run_scenario()
        reasons = {(e.object_identity.split("|")[-1], e.reason) for e in report.exclusions if e.kind == "late_registration"}
        self.assertIn(("os-backfill", "historical_backfill"), reasons)
        self.assertIn(("ck-hindsight", "hindsight_declared"), reasons)
        self.assertIn(("jd-memo", "not_ex_ante"), reasons)
        self.assertFalse(findings_of(report, "late_registration", "os-backfill"))

    def test_rule_not_in_effect_at_the_time_cannot_produce_issue(self) -> None:
        pol = load_fixture("policy.json")
        for rule in pol["rules"]:
            if rule["kind"] == "late_registration":
                rule["effective_from"] = "2026-09-10"  # 行为发生在 09-04，规则 09-10 才生效
        report = run_scenario(policy=pol)
        late = one(report, "late_registration", "os-late")
        self.assertEqual(late.classification, "unknown")
        self.assertEqual([g.reason for g in late.gaps], ["rule_not_in_effect"])
        self.assertIsNone(late.rule_id)


class ConditionRevision(unittest.TestCase):
    def test_a2_compliant_revision_is_context_and_missing_chain_is_unknown(self) -> None:
        report = run_scenario()
        self.assertEqual(one(report, "condition_revision", "jd-memo").classification, "context")
        undisclosed = one(report, "condition_revision", "jd-undisclosed")
        self.assertEqual(undisclosed.classification, "issue")
        self.assertIn("reason", undisclosed.observed)
        chain = one(report, "condition_revision", "jd-chain-unknown")
        self.assertEqual(chain.classification, "unknown")
        self.assertEqual([g.reason for g in chain.gaps], ["version_chain_incomplete"])

    def test_duplicate_revision_receipt_does_not_add_an_opportunity(self) -> None:
        report = run_scenario()
        d = denominator(report, "condition_revision", "user_original")
        self.assertEqual((d.eligible, d.issue, d.context, d.unknown), (3, 1, 1, 1))
        memo = one(report, "condition_revision", "jd-memo")
        self.assertIn("rv-dup-jd-memo", memo.evidence_refs)  # 重复收据并进证据，不另起一桶

    def test_undisclosed_revision_before_freeze_is_context_when_rule_only_freezes(self) -> None:
        sc = load_fixture("scenario_full.json")
        rec = copy.deepcopy(next(r for r in sc["records"] if r["record_id"] == "jd-undisclosed"))
        rec["object_kind"] = "checkpoint"
        rec["object_ref"] = {"kind": "checkpoint", "namespace": "checkpoints.jsonl", "id": "ck-frozen"}
        rec["record_id"] = "ck-frozen"
        rec["declared_deadline"] = "2026-09-07T09:30:00+08:00"  # 修改发生在 09-06，早于冻结点
        pol = load_fixture("policy.json")
        for rule in pol["rules"]:
            if rule["kind"] == "condition_revision":
                rule["params"] = {"require_disclosure_always": False, "freeze_after": "deadline"}
        report = run_scenario(records=[rec], verdicts=[], process_receipts=[], policy=pol)
        self.assertEqual(one(report, "condition_revision", "ck-frozen").classification, "context")
        rec2 = dict(rec, declared_deadline="2026-09-05T09:30:00+08:00")  # 冻结后未披露 → issue
        report2 = run_scenario(records=[rec2], verdicts=[], process_receipts=[], policy=pol)
        self.assertEqual(one(report2, "condition_revision", "ck-frozen").classification, "issue")


class StaleEvidenceReuse(unittest.TestCase):
    def test_a3_hash_only_change_is_unknown_and_known_expiry_with_use_receipt_is_issue(self) -> None:
        report = run_scenario()
        stale = [f for f in report.findings if f.kind == "stale_evidence_reuse"]
        by_ref = {f.opportunity_key.split("|")[-2]: f for f in stale}
        self.assertEqual(by_ref["ann:001"].classification, "issue")
        self.assertIn("mi-001", by_ref["ann:001"].maintenance_item_ids)
        self.assertEqual(by_ref["ann:002"].classification, "unknown")
        self.assertEqual([g.reason for g in by_ref["ann:002"].gaps], ["change_not_invalidating"])
        self.assertEqual(by_ref["ann:003"].classification, "context")
        self.assertEqual(by_ref["ann:004"].classification, "context")  # 更正晚于使用：后知不追责
        self.assertIn("后知", by_ref["ann:004"].observed)
        self.assertEqual(by_ref["ann:009"].classification, "unknown")
        self.assertEqual([g.reason for g in by_ref["ann:009"].gaps], ["evidence_validity_unknown"])

    def test_duplicate_use_receipts_collapse_to_one_opportunity(self) -> None:
        report = run_scenario()
        d = denominator(report, "stale_evidence_reuse", "user_original")
        self.assertEqual((d.eligible, d.issue, d.context, d.unknown), (5, 1, 2, 2))
        issue = next(f for f in report.findings if f.kind == "stale_evidence_reuse" and f.classification == "issue")
        self.assertIn("eu-001", issue.evidence_refs)
        self.assertIn("eu-001-dup", issue.evidence_refs)

    def test_without_use_receipt_hash_change_alone_yields_no_stale_finding(self) -> None:
        sc = load_fixture("scenario_full.json")
        receipts = [r for r in sc["process_receipts"] if r["kind"] != "evidence_use"]
        report = run_scenario(process_receipts=receipts)
        self.assertFalse([f for f in report.findings if f.kind == "stale_evidence_reuse"])

    def test_use_without_version_hash_is_unknown_version(self) -> None:
        sc = load_fixture("scenario_full.json")
        receipts = [copy.deepcopy(r) for r in sc["process_receipts"] if r["receipt_id"] == "eu-001"]
        receipts[0]["payload"].pop("version_or_hash")
        report = run_scenario(process_receipts=receipts)
        f = one(report, "stale_evidence_reuse", "jd-memo")
        self.assertEqual(f.classification, "unknown")
        self.assertEqual([g.reason for g in f.gaps], ["used_version_unknown"])


class StageMismatch(unittest.TestCase):
    def test_a4_later_relabel_is_unknown_and_contemporaneous_conflict_is_issue(self) -> None:
        report = run_scenario()
        stage = {f.evidence_refs: f for f in report.findings if f.kind == "stage_mismatch"}
        by_receipt = {next(r for r in refs if r.startswith("su-")): f for refs, f in stage.items()}
        self.assertEqual(by_receipt["su-001"].classification, "issue")
        self.assertIn("tbl-breakout-volume@v1", by_receipt["su-001"].evidence_refs)
        self.assertEqual(by_receipt["su-002"].classification, "context")
        self.assertEqual(by_receipt["su-003"].classification, "unknown")
        self.assertEqual([g.reason for g in by_receipt["su-003"].gaps], ["stage_label_hindsight"])
        self.assertEqual([g.reason for g in by_receipt["su-004"].gaps], ["stage_label_unknown"])
        self.assertEqual([g.reason for g in by_receipt["su-005"].gaps], ["applicability_table_missing"])

    def test_table_not_in_effect_at_use_time_is_unknown(self) -> None:
        pol = load_fixture("policy.json")
        pol["applicability_tables"][0]["effective_from"] = "2026-09-04"  # su-001 用在 09-03
        report = run_scenario(policy=pol)
        f = next(f for f in report.findings if f.kind == "stage_mismatch" and "su-001" in f.evidence_refs)
        self.assertEqual(f.classification, "unknown")
        self.assertEqual([g.reason for g in f.gaps], ["applicability_table_not_in_effect"])


class OverdueUnreviewed(unittest.TestCase):
    def test_a5_data_or_system_limits_are_not_user_issues(self) -> None:
        report = run_scenario()
        # ck-unverifiable：窗口内**有**回检动作，只是结果不可核验。机会已被履行 → 已评估的 context。
        unv = one(report, "overdue_unreviewed", "ck-unverifiable")
        self.assertEqual(unv.classification, "context")
        # ck-agent：回检责任在系统，用户根本没有这次机会 → 按规格 §5 落 excluded 并列原因。
        # 旧断言要它当 context，等于把无责任故障算进 evaluated 分母、夸大诊断覆盖（评审 D2）。
        self.assertFalse(findings_of(report, "overdue_unreviewed", "ck-agent"))
        excluded = next(
            e for e in report.exclusions if e.kind == "overdue_unreviewed" and e.object_identity.endswith("|ck-agent")
        )
        self.assertEqual(excluded.reason, "system_recheck_missing")
        # 排除出分母不等于从责任归属清单里消失。
        reasons = {(n.object_identity.split("|")[-1], n.reason) for n in report.non_attributable}
        self.assertIn(("ck-unverifiable", "data_or_system_limit"), reasons)
        self.assertIn(("ck-agent", "system_recheck_missing"), reasons)

    def test_user_owned_manual_checkpoint_with_complete_coverage_is_issue(self) -> None:
        report = run_scenario()
        f = one(report, "overdue_unreviewed", "ck-nodeadline")
        self.assertEqual(f.classification, "issue")
        self.assertIn("cov-verdicts", f.evidence_refs)

    def test_removing_coverage_declaration_turns_issue_into_unknown(self) -> None:
        sc = load_fixture("scenario_full.json")
        receipts = [r for r in sc["process_receipts"] if r["kind"] != "coverage"]
        report = run_scenario(process_receipts=receipts)
        f = one(report, "overdue_unreviewed", "ck-nodeadline")
        self.assertEqual(f.classification, "unknown")
        self.assertEqual([g.reason for g in f.gaps], ["coverage_unknown"])
        self.assertFalse([x for x in report.findings if x.kind == "overdue_unreviewed" and x.classification == "issue"])

    def test_coverage_window_must_cover_the_due_date(self) -> None:
        report = run_scenario()
        early = one(report, "overdue_unreviewed", "ck-early-due")  # due 09-02，覆盖声明从 09-03 起
        self.assertEqual(early.classification, "unknown")
        self.assertEqual([g.reason for g in early.gaps], ["coverage_unknown"])

    def test_not_due_and_open_window_are_excluded(self) -> None:
        report = run_scenario()
        reasons = {(e.object_identity.split("|")[-1], e.reason) for e in report.exclusions if e.kind == "overdue_unreviewed"}
        self.assertIn(("ck-notdue", "not_due_yet"), reasons)
        self.assertIn(("ck-window-open", "window_open"), reasons)
        self.assertFalse(findings_of(report, "overdue_unreviewed", "ck-notdue"))

    def test_a8_future_verdict_does_not_rescue_a_past_report(self) -> None:
        report = run_scenario()
        self.assertEqual(one(report, "overdue_unreviewed", "ck-nodeadline").classification, "issue")
        self.assertIn("filtered_after_cutoff", {g.reason for g in report.gaps})
        self.assertEqual(report.input_summary.filtered_after_cutoff, 1)
        # 同一条 verdict 若确实落在窗口内（改成 09-07），才算回检
        sc = load_fixture("scenario_full.json")
        verdicts = copy.deepcopy(sc["verdicts"])
        for v in verdicts:
            if v["verdict_id"] == "vd-ck-nodeadline-future":
                v["checked_at"] = "2026-09-07T20:00:00+08:00"
        report2 = run_scenario(verdicts=verdicts)
        self.assertEqual(one(report2, "overdue_unreviewed", "ck-nodeadline").classification, "context")

    def test_review_extension_receipt_counts_as_process(self) -> None:
        sc = load_fixture("scenario_full.json")
        receipts = copy.deepcopy(sc["process_receipts"]) + [
            {
                "receipt_id": "rv-ext",
                "owner_user_id": "u-alpha",
                "provenance": "synthetic",
                "kind": "review",
                "object_ref": {"kind": "checkpoint", "namespace": "checkpoints.jsonl", "id": "ck-nodeadline"},
                "occurred_at": "2026-09-07T09:00:00+08:00",
                "payload": {"action": "extended", "extended_until": "2026-09-15"},
            }
        ]
        report = run_scenario(process_receipts=receipts)
        f = one(report, "overdue_unreviewed", "ck-nodeadline")
        self.assertEqual(f.classification, "context")
        self.assertIn("rv-ext", f.evidence_refs)


class ActorGroupsAndDuplicates(unittest.TestCase):
    def test_a6_four_actor_groups_do_not_mix(self) -> None:
        report = run_scenario()
        groups = {d.actor_group for d in report.denominators if d.kind == "late_registration"}
        self.assertEqual(groups, {"user_original", "agent_generated", "user_after_agent", "unknown_origin"})
        self.assertEqual(one(report, "late_registration", "os-timely").actor_group, "user_after_agent")
        self.assertEqual(one(report, "late_registration", "os-late").actor_group, "user_original")
        self.assertEqual(one(report, "late_registration", "ck-agent").actor_group, "agent_generated")
        self.assertEqual(one(report, "late_registration", "ck-legacy").actor_group, "unknown_origin")
        # 看后确认的剧本保留原 agent 引用
        self.assertIn("observation_script:drafted:cp:aaa", one(report, "late_registration", "os-timely").evidence_refs)
        # 来源不明的对象出问题时归 unknown_origin，不算独立用户能力
        legacy = one(report, "overdue_unreviewed", "ck-legacy")
        self.assertEqual((legacy.classification, legacy.actor_group), ("issue", "unknown_origin"))
        self.assertIn("actor_coverage", {u.kind for u in report.uncertainty})

    def test_a7_triplicated_inputs_do_not_change_denominators(self) -> None:
        sc = load_fixture("scenario_full.json")
        base = run_scenario()
        tripled = run_scenario(
            records=sc["records"] * 3,
            verdicts=sc["verdicts"] * 3,
            process_receipts=sc["process_receipts"] * 3,
            maintenance_reports=[load_fixture("maintenance_report_01.json")] * 3,
        )
        self.assertEqual([d.to_dict() for d in base.denominators], [d.to_dict() for d in tripled.denominators])
        self.assertEqual([f.id for f in base.findings], [f.id for f in tripled.findings])
        self.assertEqual(len(base.non_attributable), len(tripled.non_attributable))

    def test_exposure_receipt_before_recording_makes_user_after_agent(self) -> None:
        sc = load_fixture("scenario_full.json")
        rec = copy.deepcopy(next(r for r in sc["records"] if r["record_id"] == "os-late"))
        receipts = [
            {
                "receipt_id": "xp-1",
                "owner_user_id": "u-alpha",
                "provenance": "synthetic",
                "kind": "exposure",
                "object_ref": rec["object_ref"],
                "occurred_at": "2026-09-04T09:00:00+08:00",
                "payload": {"target_ref": "agent:draft:007", "channel": "workbench"},
            }
        ]
        report = run_scenario(records=[rec], verdicts=[], process_receipts=receipts)
        self.assertEqual(one(report, "late_registration", "os-late").actor_group, "user_after_agent")
        # 曝光晚于登记时刻：不能倒过来证明「写之前看过」
        receipts[0]["occurred_at"] = "2026-09-05T09:00:00+08:00"
        report2 = run_scenario(records=[rec], verdicts=[], process_receipts=receipts)
        self.assertEqual(one(report2, "late_registration", "os-late").actor_group, "user_original")


if __name__ == "__main__":
    unittest.main()
