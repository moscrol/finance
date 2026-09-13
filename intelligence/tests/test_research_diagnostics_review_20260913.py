"""研究进化 04 · 2026-09-13 评审返修的反例回归（D1 / D2 / S3 / D3 / D4 / S4）。

每条缺陷都配负控：证明修复不是把检查整个关掉（失效仍能判 issue、真回检仍算已评估、
全 observed 仍标 observed、已生效替代仍追责、补全时间后判定能走向两端）。

- **D1**：追溯失效（先发生、后补记）不得反过来追责当时无从知晓的引用。规格 §4「后知更正不追责」、
  §5「按行为当时 cutoff 判断可知性」。
- **D2**：无责任系统故障进 ``excluded`` 并列原因，不进 ``evaluated`` 分母。规格 §5。
- **S3**：任一参与判定的合成来源必须传到报告 ``provenance``；来源未声明时失败关闭。总合同 §5 第 8 条。
- **D3**：已登记但尚未生效（valid_from 晚于使用时刻）的替代依据不追责当时的引用。
- **D4**：后知更正不能掩盖另一条失效事实的记录时间缺口——缺时间就只能 unknown，不进已评估分母。
- **S4**：报告级 synthetic 不能被项级 observed 升级；父子来源各自独立校验，冲突留 gap 可见。
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


def stale_findings(report, receipt_id: str):
    """引用了某条 evidence_use 收据的过期证据沿用项。"""
    return [f for f in report.findings if f.kind == "stale_evidence_reuse" and receipt_id in f.evidence_refs]


def one_stale(report, receipt_id: str):
    fs = stale_findings(report, receipt_id)
    assert len(fs) == 1, (receipt_id, [f.to_dict() for f in fs])
    return fs[0]


def denominator(report, kind: str, group: str):
    return next((d for d in report.denominators if d.kind == kind and d.actor_group == group), None)


def overdue_finding(report, object_id: str):
    return next(
        (f for f in report.findings if f.kind == "overdue_unreviewed" and f.object_refs[0].id == object_id),
        None,
    )


def overdue_exclusion(report, object_id: str):
    return next(
        (e for e in report.exclusions if e.kind == "overdue_unreviewed" and e.object_identity.endswith(f"|{object_id}")),
        None,
    )


def _mi004_before(maintenance: dict) -> dict:
    """mi-004 的前态版本 ann:004@n1，即 eu-004 在 2026-09-04 实际引用的那一版。"""
    return next(i for i in maintenance["items"] if i["id"] == "mi-004")["before"][0]


class D1BackdatedInvalidation(unittest.TestCase):
    """后来才记录的追溯失效，不能当成用户行为当时已知。"""

    def test_d1_backdated_valid_to_does_not_blame_earlier_use(self) -> None:
        # eu-004 在 2026-09-04 10:00 引用 ann:004@n1；失效事实 2026-09-07 才记录，却声称 09-03 起失效。
        mr = load_fixture("maintenance_report_01.json")
        _mi004_before(mr).update(
            recorded_at="2026-09-07T18:00:00+08:00", expired_at=None, valid_to="2026-09-03"
        )
        finding = one_stale(run_scenario(maintenance_reports=[mr]), "eu-004")
        self.assertNotEqual(finding.classification, "issue")
        self.assertEqual(finding.classification, "context")
        self.assertIn("后知", finding.observed)

    def test_d1_backdated_expired_at_does_not_blame_earlier_use(self) -> None:
        # 失效时刻本身早于使用（09-02），但这条记录 09-07 才写下：当时同样无从知晓。
        mr = load_fixture("maintenance_report_01.json")
        _mi004_before(mr).update(
            recorded_at="2026-09-07T18:00:00+08:00", expired_at="2026-09-02T18:00:00+08:00", valid_to=None
        )
        finding = one_stale(run_scenario(maintenance_reports=[mr]), "eu-004")
        self.assertNotEqual(finding.classification, "issue")
        self.assertEqual(finding.classification, "context")

    def test_d1_missing_recorded_at_on_ended_version_is_unknown_not_issue(self) -> None:
        # 缺记录时间 → 证明不了当时可知。缺证不是反证，只能 unknown。
        # 这里把更正链摘掉，隔离出「只有一条没有记录时间的失效」这一种信号。
        mr = load_fixture("maintenance_report_01.json")
        item = next(i for i in mr["items"] if i["id"] == "mi-004")
        _mi004_before(mr).update(recorded_at=None, expired_at="2026-09-02T18:00:00+08:00", valid_to=None)
        item["current"][0]["supersedes_ref"] = None
        finding = one_stale(run_scenario(maintenance_reports=[mr]), "eu-004")
        self.assertEqual(finding.classification, "unknown")
        self.assertIn("time_metadata_missing", [g.reason for g in finding.gaps])

    def test_d4_later_correction_does_not_mask_unknown_earlier_expiry(self) -> None:
        # 评审 D4：同 ref 上「记录时间缺失的失效」+「晚于使用时刻的更正」只能 unknown。
        # 后来的更正证明不了先前那条失效在使用时刻是否已知——把缺失的 recorded_at 补成
        # 09-01 得 issue、补成 09-07 得 context，两种结局都与当前输入一致，故只能 unknown
        # （规格 §4「缺原版本 / 时间 / 使用证据为 unknown」、§5「未知不算成功」）。
        mr = load_fixture("maintenance_report_01.json")
        _mi004_before(mr).update(recorded_at=None, expired_at="2026-09-02T18:00:00+08:00", valid_to=None)
        finding = one_stale(run_scenario(maintenance_reports=[mr]), "eu-004")
        self.assertEqual(finding.classification, "unknown")
        self.assertIn("time_metadata_missing", [g.reason for g in finding.gaps])

    def test_d4_filling_missing_record_time_decides_both_ways(self) -> None:
        # D4 的双向负控：补上缺失的记录时间后，判定必须能分别走到 issue 与 context，
        # 证明上面的 unknown 不是「检查被关掉」，而是「输入确实不足」。
        early = load_fixture("maintenance_report_01.json")
        _mi004_before(early).update(recorded_at="2026-09-01T18:00:00+08:00", expired_at="2026-09-02T18:00:00+08:00", valid_to=None)
        self.assertEqual(one_stale(run_scenario(maintenance_reports=[early]), "eu-004").classification, "issue")
        late = load_fixture("maintenance_report_01.json")
        _mi004_before(late).update(recorded_at="2026-09-07T18:00:00+08:00", expired_at="2026-09-02T18:00:00+08:00", valid_to=None)
        self.assertEqual(one_stale(run_scenario(maintenance_reports=[late]), "eu-004").classification, "context")


class D3FutureReplacement(unittest.TestCase):
    """已公告但尚未生效的替代依据，不得用于追责生效前的引用（评审 D3）。"""

    @staticmethod
    def _future_replacement(valid_from: str) -> dict:
        # mi-004：旧版 ann:004@n1 本身无失效标记；替代版 09-03 登记、valid_from 指定生效日。
        mr = load_fixture("maintenance_report_01.json")
        item = next(i for i in mr["items"] if i["id"] == "mi-004")
        item["before"][0].update(expired_at=None, valid_to=None)
        item["current"][0].update(ref="ann:004-future", valid_from=valid_from, recorded_at="2026-09-03T18:00:00+08:00")
        return mr

    def test_d3_announced_future_replacement_does_not_invalidate_earlier_use(self) -> None:
        # 替代 09-06 才生效，eu-004 在 09-04 引用旧版：当时旧版仍在生效，不是「当时已知失效」。
        # （规格 §4「实际投影 / 引用用了当时已知失效版本」；01 §4 先按生效再选版本。）
        mr = self._future_replacement("2026-09-06")
        finding = one_stale(run_scenario(maintenance_reports=[mr]), "eu-004")
        self.assertNotEqual(finding.classification, "issue")
        self.assertEqual(finding.classification, "context")
        self.assertIn("当时有效", finding.observed)

    def test_d3_negative_control_effective_before_use_is_still_issue(self) -> None:
        # 负控：替代 09-03 已生效且已登记，09-04 仍引用旧版 → 照判 issue。
        # 这条翻红说明 D3 的修法把替代追责整个关掉了。
        mr = self._future_replacement("2026-09-03")
        finding = one_stale(run_scenario(maintenance_reports=[mr]), "eu-004")
        self.assertEqual(finding.classification, "issue")

    def test_d1_negative_control_expiry_recorded_before_use_is_still_issue(self) -> None:
        # 负控：ann:001@h1 的失效 2026-08-20 就已记录、09-05 生效，eu-001 在 09-06 仍引用 → 照判 issue。
        # 这条翻红说明 D1 的修法把检查整个关掉了。
        finding = one_stale(run_scenario(), "eu-001")
        self.assertEqual(finding.classification, "issue")

    def test_d1_negative_control_backdating_only_moves_the_one_use(self) -> None:
        # 负控：只改 mi-004 的记录时间，不应连带改变引用 ann:001 的那条判定。
        mr = load_fixture("maintenance_report_01.json")
        _mi004_before(mr).update(
            recorded_at="2026-09-07T18:00:00+08:00", expired_at=None, valid_to="2026-09-03"
        )
        report = run_scenario(maintenance_reports=[mr])
        self.assertEqual(one_stale(report, "eu-001").classification, "issue")


class D2NonAttributableSystemFailure(unittest.TestCase):
    """无责任系统故障排除出可评估分母，但仍留在 non_attributable 清单里。"""

    def test_d2_system_responsibility_without_recheck_is_excluded(self) -> None:
        report = run_scenario()
        self.assertIsNone(overdue_finding(report, "ck-agent"))
        exclusion = overdue_exclusion(report, "ck-agent")
        self.assertIsNotNone(exclusion)
        self.assertEqual(exclusion.reason, "system_recheck_missing")
        d = denominator(report, "overdue_unreviewed", "agent_generated")
        self.assertEqual(
            (d.eligible, d.evaluated, d.issue, d.context, d.unknown, d.excluded), (0, 0, 0, 0, 0, 1)
        )
        self.assertEqual(d.exclusion_reasons, {"system_recheck_missing": 1})
        # 排除不等于消失：责任归属清单仍然点名它。
        self.assertIn(
            ("checkpoint|checkpoints.jsonl|ck-agent", "system_recheck_missing"),
            [(n.object_identity, n.reason) for n in report.non_attributable],
        )

    def test_d2_system_failure_window_is_excluded_not_issue(self) -> None:
        # ck-nodeadline 基线是 user_original 的 issue；窗口 09-06~09-08 压上系统失败后应退出分母。
        sc = load_fixture("scenario_full.json")
        base = run_scenario()
        self.assertEqual(overdue_finding(base, "ck-nodeadline").classification, "issue")
        receipts = copy.deepcopy(sc["process_receipts"])
        receipts.append(
            {
                "receipt_id": "sf-1",
                "owner_user_id": "u-alpha",
                "provenance": "synthetic",
                "kind": "system_failure",
                "occurred_at": "2026-09-06T09:00:00+08:00",
                "payload": {
                    "scope": "checkpoints",
                    "window_start": "2026-09-06",
                    "window_end": "2026-09-08",
                    "reason": "上游断流",
                },
            }
        )
        report = run_scenario(process_receipts=receipts)
        self.assertIsNone(overdue_finding(report, "ck-nodeadline"))
        exclusion = overdue_exclusion(report, "ck-nodeadline")
        self.assertIsNotNone(exclusion)
        self.assertEqual(exclusion.reason, "system_failure_window")
        self.assertIn(
            ("checkpoint|checkpoints.jsonl|ck-nodeadline", "system_failure_window"),
            [(n.object_identity, n.reason) for n in report.non_attributable],
        )

    def test_d2_negative_control_real_recheck_stays_evaluated_context(self) -> None:
        # 负控：ck-unverifiable 窗口内**有**回检动作，只是结果 unverifiable。
        # 用户履行了机会，属于已评估的非 issue，不能跟着一起被排除掉（规格 §4 该行落 context）。
        report = run_scenario()
        finding = overdue_finding(report, "ck-unverifiable")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.classification, "context")
        d = denominator(report, "overdue_unreviewed", "user_original")
        self.assertGreaterEqual(d.evaluated, 1)

    def test_d2_negative_control_plain_overdue_is_still_issue(self) -> None:
        # 负控：没有任何系统故障时，到期未回检照旧判 issue。
        self.assertEqual(overdue_finding(run_scenario(), "ck-legacy").classification, "issue")


class S3MaintenanceProvenance(unittest.TestCase):
    """合成维护证据必须把来源传到报告，不能被其他 observed 输入洗白。"""

    @staticmethod
    def _observed_scenario() -> dict:
        sc = load_fixture("scenario_full.json")
        for group in ("records", "verdicts", "process_receipts"):
            for row in sc[group]:
                row["provenance"] = "observed"
        return sc

    def test_s3_synthetic_maintenance_report_taints_report_provenance(self) -> None:
        sc = self._observed_scenario()
        report = run_scenario(
            records=sc["records"],
            verdicts=sc["verdicts"],
            process_receipts=sc["process_receipts"],
            exercise_cases=[],
        )
        self.assertEqual(report.provenance, "synthetic")

    def test_s3_undeclared_maintenance_provenance_fails_closed(self) -> None:
        # 真实 01 产物目前不带 provenance 字段：缺声明不能当成 observed。
        sc = self._observed_scenario()
        mr = load_fixture("maintenance_report_01.json")
        mr.pop("provenance")
        report = run_scenario(
            records=sc["records"],
            verdicts=sc["verdicts"],
            process_receipts=sc["process_receipts"],
            maintenance_reports=[mr],
            exercise_cases=[],
        )
        self.assertEqual(report.provenance, "synthetic")
        # 降级必须可见，否则读者看不出这是默认值而不是认证结果。
        self.assertIn("maintenance_provenance_undeclared", [g.reason for g in report.gaps])

    def test_s3_negative_control_all_observed_inputs_stay_observed(self) -> None:
        # 负控：全部输入都明确 observed 时仍标 observed。这条翻红说明修法把 provenance 写死成 synthetic。
        sc = self._observed_scenario()
        mr = load_fixture("maintenance_report_01.json")
        mr["provenance"] = "observed"
        report = run_scenario(
            records=sc["records"],
            verdicts=sc["verdicts"],
            process_receipts=sc["process_receipts"],
            maintenance_reports=[mr],
            exercise_cases=[],
        )
        self.assertEqual(report.provenance, "observed")
        self.assertNotIn("maintenance_provenance_undeclared", [g.reason for g in report.gaps])

    def test_s3_negative_control_synthetic_exercise_case_still_taints(self) -> None:
        # 负控：既有的合成练习题包来源传递不能被本次改动弄丢。
        sc = self._observed_scenario()
        mr = load_fixture("maintenance_report_01.json")
        mr["provenance"] = "observed"
        report = run_scenario(
            records=sc["records"],
            verdicts=sc["verdicts"],
            process_receipts=sc["process_receipts"],
            maintenance_reports=[mr],
        )
        self.assertEqual(report.provenance, "synthetic")


class S4ProvenancePrecedence(unittest.TestCase):
    """报告级来源是天花板：项级声明只能持平或再降档，不能把合成父报告升级成 observed（评审 S4）。"""

    @staticmethod
    def _observed_scenario() -> dict:
        sc = load_fixture("scenario_full.json")
        for group in ("records", "verdicts", "process_receipts"):
            for row in sc[group]:
                row["provenance"] = "observed"
        return sc

    def _run_with_provenance(self, report_prov, item_prov):
        sc = self._observed_scenario()
        mr = load_fixture("maintenance_report_01.json")
        mr["provenance"] = report_prov
        for item in mr["items"]:
            if item_prov is None:
                item.pop("provenance", None)
            else:
                item["provenance"] = item_prov
        return run_scenario(
            records=sc["records"],
            verdicts=sc["verdicts"],
            process_receipts=sc["process_receipts"],
            maintenance_reports=[mr],
            exercise_cases=[],
        )

    def test_s4_item_observed_cannot_upgrade_synthetic_report(self) -> None:
        report = self._run_with_provenance("synthetic", "observed")
        self.assertEqual(report.provenance, "synthetic")
        # 冲突必须可见：子项试图升级父报告这件事本身要留痕，不是静默压掉。
        self.assertIn("maintenance_provenance_conflict", [g.reason for g in report.gaps])

    def test_s4_report_observed_item_synthetic_stays_synthetic(self) -> None:
        report = self._run_with_provenance("observed", "synthetic")
        self.assertEqual(report.provenance, "synthetic")

    def test_s4_unknown_report_provenance_is_rejected_not_masked(self) -> None:
        # 报告级来源是未知枚举时，项级 observed 不能把它遮过去：父子来源各自独立校验。
        from intelligence.services.research_diagnostics.contracts import DiagnosticsInputError

        with self.assertRaises(DiagnosticsInputError):
            self._run_with_provenance("unrecognized", "observed")

    def test_s4_negative_control_observed_parent_with_silent_items_stays_observed(self) -> None:
        # 负控：父报告 observed、项未声明（继承父级）仍是 observed。这条翻红说明修法把继承弄丢了。
        report = self._run_with_provenance("observed", None)
        self.assertEqual(report.provenance, "observed")


if __name__ == "__main__":
    unittest.main()
