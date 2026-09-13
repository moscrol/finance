"""研究进化 04 · 旧台账只读适配（规格 §2、§7 第 0/4 步、§8 第 9 条）。

用**真实写入者**（register_checkpoint / record_verdict / record_judgment / observation_script.register /
scenario_trees.register）在临时目录造台账，再经适配器进 diagnose；全程台账字节不变。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from intelligence.services import checkpoints, judgments, observation_script
from intelligence.services import scenario_trees as st
from intelligence.services.research_diagnostics import diagnose
from intelligence.services.research_diagnostics.adapters import load_legacy_inputs

FX = Path(__file__).parent / "fixtures" / "research_evolution" / "04"
HASH = "cp:0123456789abcdef"
OWNER = "u-legacy"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def _script(as_of: str, recorded_at: str) -> observation_script.ObservationScript:
    return observation_script.make(
        as_of=as_of,
        scope="index",
        entity_ids=["上证指数"],
        variables=["盘面轨：指数阶段、成交与边际量是否延续"],
        downgrade_or_abandon_conditions=["盘面轨该实体的量价对象消失或转为缺口"],
        status="confirmed",
        recorded_at=recorded_at,
        projection_hash=HASH,
        model_id="m-test",
        framework_version="tf-v0.2",
        knowledge_cutoff=as_of,
    )


def _tree_spec() -> dict:
    script = {
        "variables": ["盘面轨：指数阶段、成交与边际量是否延续"],
        "downgrade_or_abandon_conditions": ["盘面轨该实体的量价对象消失或转为缺口"],
    }
    return {
        "as_of": "2026-09-01",
        "scope": "index",
        "entity_ids": ["上证指数"],
        "max_depth": 1,
        "framework_version": "tf-v0.2",
        "model_id": "m-test",
        "projection_hash": HASH,
        "nodes": [
            {"node_id": "root", "depth": 0, "parent": None, "condition": None, "script": dict(script)},
            {"node_id": "a", "depth": 1, "parent": "root", "step_kind": "T+1",
             "condition": {"all": [{"label": "market_stage", "op": "in", "value": ["反弹"]}]}, "script": dict(script)},
            {"node_id": "z", "depth": 1, "parent": "root", "step_kind": "T+1", "condition": "otherwise", "script": dict(script)},
        ],
    }


def build_ledgers(root: Path) -> dict[str, Path]:
    """真实写入者造台账。剧本 / 树登记 checkpoint 时用写入者自己的时钟盖 ``ts``，这里把它钉在 2026-09-02，
    让派生 checkpoint 行落在诊断区间内（否则会被 knowledge_cutoff 过滤——那是正确行为，不是要测的东西）。"""
    with mock.patch.object(checkpoints, "_now", return_value=datetime(2026, 9, 2, 12, 5, tzinfo=timezone.utc)):
        return _build_ledgers(root)


def _build_ledgers(root: Path) -> dict[str, Path]:
    paths = {
        "checkpoints": root / "checkpoints.jsonl",
        "verdicts": root / "verdicts.jsonl",
        "judgments": root / "judgments.jsonl",
        "scripts": root / "observation_scripts.jsonl",
        "trees": root / "scenario_trees.jsonl",
    }
    # 用户判断（人工判定 → 回检责任在用户）
    _, ck_user = checkpoints.register_checkpoint(
        paths["checkpoints"], claim="用户判断：产能爬坡滞后", due="2026-09-05", object_type="judgment", ts="2026-09-02T04:00:00+00:00"
    )
    # agent 判断（机检 → 系统责任）
    _, ck_agent = checkpoints.register_checkpoint(
        paths["checkpoints"], claim="agent 判断：板块量能延续", due="2026-09-04", object_type="agent_judgment",
        ts="2026-09-02T05:00:00+00:00", projection_hash=HASH, model_id="m-test",
        metric={"type": "stock_return", "op": ">=", "target": 3, "target_name": "示例"},
    )
    # 存量行：没有 object_type / source → unknown_legacy
    with paths["checkpoints"].open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "ck-legacy-1", "ts": "2026-09-02T06:00:00+00:00", "claim": "存量未标类型", "due": "2026-09-04"}, ensure_ascii=False) + "\n")
    # 及时确认的剧本（登记 checkpoint）与迟登剧本（status=late，不登记 checkpoint）
    _, s_timely = observation_script.register(
        paths["scripts"], _script("2026-09-02", "2026-09-02T20:00:00+08:00"),
        checkpoints_path=paths["checkpoints"], due="2026-09-03",
    )
    _, s_late = observation_script.register(
        paths["scripts"], _script("2026-09-03", "2026-09-04T10:15:00+08:00"),
        checkpoints_path=paths["checkpoints"], due="2026-09-04",
    )
    # 情景树（agent 产物，同时登记一条 scenario_tree checkpoint）
    tree = st.ensure_valid(_tree_spec())
    _, t_rec = st.register(paths["trees"], tree, checkpoints_path=paths["checkpoints"], recorded_at="2026-09-01T20:00:00+08:00")
    # 用户 memo
    judgments.record_judgment(paths["judgments"], memo="核心判断：HVLP 铜箔验证完成但爬坡滞后", themes=["铜箔"], ts="2026-09-02T02:00:00+00:00")
    # 回检：及时剧本的 checkpoint 到期 miss；agent 判断 unverifiable（数据未到）
    checkpoints.record_verdict(paths["verdicts"], id=s_timely["checkpoint_id"], verdict="miss", checked_at="2026-09-03T12:00:00+00:00", data_source="market_daily", auto=True)
    checkpoints.record_verdict(
        paths["verdicts"], id=ck_agent["id"], verdict="unverifiable", checked_at="2026-09-04T12:00:00+00:00", data_source="duckdb",
        degradation={"attempted": [{"source": "duckdb", "status": "missing"}], "impact": "本机无 DuckDB", "owed_source": "duckdb"}, auto=True,
    )
    assert s_timely["status"] == "confirmed" and s_timely["checkpoint_id"]
    assert s_late["status"] == "late" and s_late["checkpoint_id"] is None
    paths["_ids"] = {"ck_user": ck_user["id"], "ck_agent": ck_agent["id"], "s_timely": s_timely["id"], "s_late": s_late["id"], "tree": t_rec["id"], "tree_ck": t_rec["checkpoint_id"], "s_timely_ck": s_timely["checkpoint_id"]}  # type: ignore[assignment]
    return paths


def policy() -> dict:
    return json.loads((FX / "policy.json").read_text(encoding="utf-8"))


class LegacyAdapters(unittest.TestCase):
    def test_real_writers_to_adapter_to_diagnose_leaves_ledgers_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = build_ledgers(root)
            ids = paths.pop("_ids")  # type: ignore[assignment]
            before = {k: _sha(p) for k, p in paths.items()}

            inputs = load_legacy_inputs(
                owner_user_id=OWNER,
                checkpoints_path=paths["checkpoints"],
                verdicts_path=paths["verdicts"],
                judgments_path=paths["judgments"],
                scripts_path=paths["scripts"],
                trees_path=paths["trees"],
            )
            by_id = {r.object_ref.id: r for r in inputs.records}
            # 作者映射只看写下的字段
            self.assertEqual(by_id[ids["ck_user"]].actor.author, "user")
            self.assertEqual(by_id[ids["ck_agent"]].actor.author, "agent")
            self.assertEqual(by_id["ck-legacy-1"].actor.author, "unknown")
            self.assertEqual(by_id[ids["tree"]].actor.author, "agent")
            timely = by_id[ids["s_timely"]]
            self.assertEqual(timely.actor.author, "user")
            self.assertTrue(timely.actor.agent_refs)  # 系统起草、用户确认 → 保留 agent 引用
            self.assertEqual(timely.declared_deadline, "2026-09-03T09:30:00+08:00")
            self.assertEqual(timely.recorded_at.granularity, "datetime")
            self.assertIsNone(timely.due)  # 回检机会在派生 checkpoint 行上
            self.assertEqual(by_id[ids["s_timely_ck"]].derived_from, timely.object_ref.identity)
            self.assertEqual(by_id[ids["tree_ck"]].derived_from, by_id[ids["tree"]].object_ref.identity)
            self.assertEqual(by_id[ids["ck_user"]].review_responsibility, "user")
            self.assertEqual(by_id[ids["ck_agent"]].review_responsibility, "system")
            self.assertEqual(by_id["ck-legacy-1"].review_responsibility, "user")
            self.assertIn("legacy_no_coverage_declaration", {g.reason for g in inputs.gaps})
            self.assertFalse([g for g in inputs.gaps if g.reason == "late_flag_disagrees"])
            self.assertEqual(len(inputs.verdicts), 2)

            report = diagnose(
                owner_user_id=OWNER, start="2026-09-01", end="2026-09-10", knowledge_cutoff="2026-09-12",
                records=inputs.records, verdicts=inputs.verdicts, process_receipts=[], policy=policy(),
                generated_at="2026-09-13T00:00:00+00:00",
            )
            f = {(x.kind, x.object_refs[0].id): x for x in report.findings}
            self.assertEqual(f[("late_registration", ids["s_timely"])].classification, "context")
            self.assertEqual(f[("late_registration", ids["s_late"])].classification, "issue")
            self.assertEqual(f[("late_registration", ids["tree"])].classification, "unknown")
            self.assertEqual([g.reason for g in f[("late_registration", ids["ck_user"])].gaps], ["deadline_missing"])
            self.assertEqual(f[("late_registration", "ck-legacy-1")].actor_group, "unknown_origin")
            excl = {(e.object_identity.split("|")[-1], e.reason) for e in report.exclusions}
            self.assertIn((ids["s_timely_ck"], "derived_object"), excl)
            self.assertIn((ids["tree_ck"], "derived_object"), excl)
            self.assertTrue(any(reason == "not_ex_ante" for _, reason in excl))  # memo 判断
            # 存量无覆盖声明：没有 verdict 的到期对象只能 unknown，不能判漏检
            self.assertEqual(f[("overdue_unreviewed", ids["ck_user"])].classification, "unknown")
            self.assertEqual([g.reason for g in f[("overdue_unreviewed", ids["ck_user"])].gaps], ["coverage_unknown"])
            self.assertEqual(f[("overdue_unreviewed", ids["s_timely_ck"])].classification, "context")
            self.assertEqual(f[("overdue_unreviewed", ids["ck_agent"])].classification, "context")
            self.assertIn(("data_or_system_limit"), {n.reason for n in report.non_attributable})
            self.assertNotIn(("overdue_unreviewed", ids["s_timely"]), f)  # 原剧本行不重复算到期
            self.assertEqual(report.provenance, "observed")

            after = {k: _sha(p) for k, p in paths.items()}
            self.assertEqual(before, after)

    def test_coverage_declaration_from_06_unlocks_overdue_judgement_by_responsibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_ledgers(Path(tmp))
            ids = paths.pop("_ids")  # type: ignore[assignment]
            inputs = load_legacy_inputs(
                owner_user_id=OWNER, checkpoints_path=paths["checkpoints"], verdicts_path=paths["verdicts"],
                judgments_path=paths["judgments"], scripts_path=paths["scripts"], trees_path=paths["trees"],
            )
            coverage = {
                "receipt_id": "cov-1", "owner_user_id": OWNER, "kind": "coverage",
                "recorded_at": "2026-09-11T00:00:00+08:00",
                "payload": {"ledger": "verdicts", "complete_from": "2026-09-01", "complete_through": "2026-09-10"},
            }
            report = diagnose(
                owner_user_id=OWNER, start="2026-09-01", end="2026-09-10", knowledge_cutoff="2026-09-12",
                records=inputs.records, verdicts=inputs.verdicts, process_receipts=[coverage], policy=policy(),
                generated_at="2026-09-13T00:00:00+00:00",
            )
            f = {(x.kind, x.object_refs[0].id): x for x in report.findings}
            self.assertEqual(f[("overdue_unreviewed", ids["ck_user"])].classification, "issue")  # 人工判定、无回检
            legacy = f[("overdue_unreviewed", "ck-legacy-1")]
            self.assertEqual((legacy.classification, legacy.actor_group), ("issue", "unknown_origin"))
            # 树由系统逐日解析：回检责任不在用户，按规格 §5 排除出可评估分母，不再计成 context。
            # 旧断言把它当 context，等于把无责任系统故障算进 evaluated（评审 D2）。
            self.assertNotIn(("overdue_unreviewed", ids["tree_ck"]), f)
            tree_excluded = next(
                e for e in report.exclusions
                if e.kind == "overdue_unreviewed" and e.object_identity.endswith("|" + ids["tree_ck"])
            )
            self.assertEqual(tree_excluded.reason, "system_recheck_missing")
            self.assertIn("system_recheck_missing", {n.reason for n in report.non_attributable})

    def test_missing_recorded_at_with_known_as_of_is_trade_date_only_not_unverifiable(self) -> None:
        """09-06 终局 spec §4.1：历史对象缺 recorded_at 标 trade_date_only，与 strict 分开统计，不是「不可验证」。"""
        from intelligence.services.research_diagnostics.adapters import checkpoint_to_record, script_to_record, tree_to_record

        legacy_script = {"id": "os-legacy", "as_of": "2026-09-02", "status": "confirmed", "late": None, "due": "2026-09-03", "projection_hash": HASH}
        rec, gaps = script_to_record(legacy_script, owner_user_id=OWNER)
        self.assertEqual(rec.recorded_at.granularity, "unknown")
        self.assertEqual(rec.pit_grade, "trade_date_only")
        self.assertEqual(rec.declared_deadline, "2026-09-03T09:30:00+08:00")
        self.assertFalse(gaps)
        tree = tree_to_record({"id": "st-legacy", "record": "tree", "as_of": "2026-09-01", "knowledge_cutoff": "2026-09-01"}, owner_user_id=OWNER)
        self.assertEqual(tree.pit_grade, "trade_date_only")
        # 既无登记时刻也无市场日：才是 unverifiable
        bare = checkpoint_to_record({"id": "ck-bare", "claim": "x", "due": "2026-09-05"}, owner_user_id=OWNER)
        self.assertEqual(bare.pit_grade, "unverifiable")
        report = diagnose(
            owner_user_id=OWNER, start="2026-09-01", end="2026-09-10", knowledge_cutoff="2026-09-12",
            records=[rec], policy=policy(), generated_at="2026-09-13T00:00:00+00:00",
        )
        late = next(f for f in report.findings if f.kind == "late_registration")
        self.assertEqual(late.classification, "unknown")
        self.assertEqual([g.reason for g in late.gaps], ["recorded_at_unknown"])
        self.assertEqual(late.pit_grade, "trade_date_only")

    def test_adapter_rejects_wrong_owner_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_ledgers(Path(tmp))
            paths.pop("_ids")
            inputs = load_legacy_inputs(owner_user_id=OWNER, checkpoints_path=paths["checkpoints"], verdicts_path=paths["verdicts"])
            from intelligence.services.research_diagnostics import OwnerMismatch

            with self.assertRaises(OwnerMismatch):
                diagnose(
                    owner_user_id="u-someone-else", start="2026-09-01", end="2026-09-10", knowledge_cutoff="2026-09-12",
                    records=inputs.records, verdicts=inputs.verdicts, policy=policy(),
                )


if __name__ == "__main__":
    unittest.main()
