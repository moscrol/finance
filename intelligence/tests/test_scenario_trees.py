"""情景树 v0 契约测试（工单 #37 / G-15；09-06 spec §3.3、§10 第 13、14 条、§11 第 13 条）。"""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from intelligence.services import checkpoints
from intelligence.services import scenario_trees as st
from intelligence.services.river import Gap, RiverObject, RiverSlice, TRACKS

HASH = "cp:0123456789abcdef"


def _script(**over) -> dict:
    base = {
        "variables": ["盘面轨：指数阶段、成交与边际量是否延续"],
        "downgrade_or_abandon_conditions": ["盘面轨该实体的量价对象消失或转为缺口"],
    }
    base.update(over)
    return base


def _spec(**over) -> dict:
    spec = {
        "as_of": "2026-09-01",
        "scope": "index",
        "entity_ids": ["上证指数"],
        "max_depth": 2,
        "framework_version": "tf-v0.2",
        "model_id": "gpt-5.6-sol",
        "projection_hash": HASH,
        "nodes": [
            {"node_id": "root", "depth": 0, "parent": None, "condition": None, "script": _script()},
            {"node_id": "a", "depth": 1, "parent": "root", "step_kind": "T+1",
             "condition": {"all": [{"label": "market_stage", "op": "in", "value": ["反弹"]}]}, "script": _script()},
            {"node_id": "b", "depth": 1, "parent": "root", "step_kind": "T+1",
             "condition": {"all": [{"label": "market_stage", "op": "in", "value": ["主升"]}, {"label": "volume_surge", "op": "==", "value": True}]},
             "script": _script()},
            {"node_id": "z", "depth": 1, "parent": "root", "step_kind": "T+1", "condition": "otherwise", "script": _script()},
        ],
    }
    spec.update(over)
    return spec


def _slice(day: str, *, stage: str | None = "反弹", surge: float | None = 2.0) -> RiverSlice:
    tracks: dict = {t: [] for t in TRACKS}
    payload = {}
    if stage is not None:
        payload["market_stage"] = stage
    if surge is not None:
        payload["amount_vs_yesterday_pct"] = surge
    tracks["market"] = [
        RiverObject(track="market", entity_id="SH000001", object_type="stage", ref=f"fact_market_daily:{day}",
                    source_hash="h1", valid_from=day, recorded_at=f"{day}T18:00:00", payload=payload)
    ] if payload else Gap("market", "no_data", "fixture")  # type: ignore[arg-type]
    return RiverSlice(as_of=day, entity_id="SH000001", entity_name="上证指数", knowledge_cutoff=day, tracks=tracks)


def _codes(rej: list[st.Rejection]) -> set[str]:
    return {r.code for r in rej}


class CompileGateTests(unittest.TestCase):
    def test_valid_tree_compiles(self) -> None:
        tree, rej = st.make(_spec())
        self.assertEqual(rej, [])
        assert tree is not None
        self.assertEqual(tree.root.node_id, "root")
        self.assertEqual({n.node_id for n in tree.children("root")}, {"a", "b", "z"})

    def test_unregistered_or_history_label_rejected(self) -> None:
        spec = _spec()
        spec["nodes"][1]["condition"] = {"all": [{"label": "not_a_label", "op": "==", "value": True}]}
        _, rej = st.make(spec)
        self.assertIn(st.E_CONDITION_INVALID, _codes(rej))
        spec = _spec()
        spec["nodes"][1]["condition"] = {"all": [{"label": "dual_red_streak", "op": ">=", "value": 3}]}
        _, rej = st.make(spec)
        self.assertIn(st.E_LABEL_NOT_SLICE_EVALUABLE, _codes(rej))
        self.assertTrue(any("dual_red_streak" in r.detail for r in rej))

    def test_no_otherwise_and_overlap_and_depth(self) -> None:
        spec = _spec()
        spec["nodes"] = [n for n in spec["nodes"] if n["node_id"] != "z"]
        _, rej = st.make(spec)
        self.assertIn(st.E_NO_OTHERWISE, _codes(rej))
        spec = _spec()
        # 「反弹」与「volume_surge==true」可同真（不同标签、无交集约束）→ 重叠
        spec["nodes"][2]["condition"] = {"all": [{"label": "volume_surge", "op": "==", "value": True}]}
        _, rej = st.make(spec)
        self.assertIn(st.E_SIBLINGS_OVERLAP, _codes(rej))
        spec = _spec(max_depth=4)
        _, rej = st.make(spec)
        self.assertIn(st.E_DEPTH, _codes(rej))

    def test_text_lint_rejects_strategy_direction_probability_stock(self) -> None:
        for bad in ("策略上明天做多", "大概率上涨 60%", "600519 明天买入", "目标价 20 元"):
            spec = _spec()
            spec["nodes"][1]["script"] = _script(variables=[bad])
            _, rej = st.make(spec)
            self.assertTrue(rej, bad)
            self.assertTrue(_codes(rej) & {st.E_TEXT, st.E_NODE_SCRIPT}, (bad, rej))

    def test_analog_ref_not_available_in_v0(self) -> None:
        spec = _spec()
        spec["nodes"][1]["analog_ref"] = {"n": 12}
        _, rej = st.make(spec)
        self.assertIn(st.E_ANALOG_REF_NOT_AVAILABLE, _codes(rej))

    def test_numeric_siblings_disjoint_by_interval_is_accepted(self) -> None:
        spec = _spec()
        spec["nodes"][1]["condition"] = {"all": [{"label": "limit_heat_rank", "op": "<=", "value": 3}]}
        spec["nodes"][2]["condition"] = {"all": [{"label": "limit_heat_rank", "op": ">", "value": 3}]}
        _, rej = st.make(spec)
        self.assertEqual(rej, [])
        spec["nodes"][2]["condition"] = {"all": [{"label": "limit_heat_rank", "op": ">=", "value": 3}]}
        _, rej = st.make(spec)
        self.assertIn(st.E_SIBLINGS_OVERLAP, _codes(rej))


class LedgerGateTests(unittest.TestCase):
    def test_register_requires_attribution_and_writes_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trees, cks = Path(tmp) / "t.jsonl", Path(tmp) / "c.jsonl"
            tree = st.ensure_valid(_spec(projection_hash=None))
            with self.assertRaises(st.ScenarioTreeRejected) as ctx:
                st.register(trees, tree, checkpoints_path=cks)
            self.assertIn("projection_hash", str(ctx.exception))
            tree = st.ensure_valid(_spec())
            _, rec = st.register(trees, tree, checkpoints_path=cks, recorded_at="2026-09-01T16:00:00+08:00")
            self.assertTrue(rec["id"].startswith("st-"))
            self.assertEqual(rec["status"], "confirmed")
            self.assertEqual(rec["realized_path"][0]["node_id"], "root")
            cks_rows, _ = checkpoints.load_checkpoints(cks)
            self.assertEqual(cks_rows[0]["object_type"], "scenario_tree")
            self.assertEqual(cks_rows[0]["projection_hash"], HASH)
            self.assertEqual(cks_rows[0]["model_id"], "gpt-5.6-sol")

    def test_ledger_is_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trees, cks = Path(tmp) / "t.jsonl", Path(tmp) / "c.jsonl"
            tree = st.ensure_valid(_spec())
            _, rec = st.register(trees, tree, checkpoints_path=cks)
            before = trees.read_text(encoding="utf-8")
            step = st.ResolutionStep(rec["id"], "2026-09-02", "root", "a", "resolving", ("r",), HASH, {"all": []}, "命中")
            st.append_step(trees, step)
            after = trees.read_text(encoding="utf-8")
            self.assertTrue(after.startswith(before))  # 只追加
            state = st.current_state(st.load(trees), rec["id"])
            assert state is not None
            self.assertEqual([p["node_id"] for p in state["realized_path"]], ["root", "a"])
            self.assertEqual(state["status"], "resolving")


class ResolveTests(unittest.TestCase):
    def _registered(self, tmp: str):
        trees, cks = Path(tmp) / "t.jsonl", Path(tmp) / "c.jsonl"
        tree = st.ensure_valid(_spec())
        _, rec = st.register(trees, tree, checkpoints_path=cks)
        return trees, cks, st.current_state(st.load(trees), rec["id"])

    def test_exactly_one_child_true_extends_path_and_registers_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trees, cks, state = self._registered(tmp)
            calls = []

            def slice_fn(as_of, entity, **kw):
                calls.append(kw)
                return _slice(as_of, stage="反弹")

            step = st.resolve(state, "2026-09-02", slice_fn=slice_fn, checkpoints_path=cks)
            self.assertEqual(step.node_id, "a")
            self.assertEqual(step.status, "resolved")  # a 是叶
            self.assertTrue(step.evidence_refs)
            self.assertTrue(step.projection_hash.startswith("cp:"))
            self.assertEqual(calls[0]["knowledge_cutoff"], "2026-09-02")  # C = as_of
            rows, _ = checkpoints.load_checkpoints(cks)
            self.assertEqual([r["object_type"] for r in rows], ["scenario_tree", "observation_script"])
            self.assertEqual(rows[1]["projection_hash"], step.projection_hash)
            self.assertIsNotNone(step.sample)
            self.assertEqual(step.sample["to_node"], "a")

    def test_missing_label_input_is_unresolvable_and_path_does_not_grow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trees, cks, state = self._registered(tmp)
            step = st.resolve(state, "2026-09-02", slice_fn=lambda a, e, **kw: _slice(a, stage=None, surge=None), checkpoints_path=cks)
            self.assertEqual(step.status, "unresolvable")
            self.assertIsNone(step.node_id)
            rows, _ = checkpoints.load_checkpoints(cks)
            self.assertEqual(len(rows), 1)  # 没有登记新剧本

    def test_otherwise_when_no_declared_branch_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trees, cks, state = self._registered(tmp)
            step = st.resolve(state, "2026-09-02", slice_fn=lambda a, e, **kw: _slice(a, stage="下跌", surge=1.0), checkpoints_path=cks)
            self.assertEqual(step.node_id, "z")
            self.assertEqual(step.condition_hit, {"otherwise": True})

    def test_cutoff_must_equal_as_of(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trees, cks, state = self._registered(tmp)

            def bad_slice(as_of, entity, **kw):
                sl = _slice(as_of)
                return RiverSlice(as_of=sl.as_of, entity_id=sl.entity_id, entity_name=sl.entity_name,
                                  knowledge_cutoff="2026-09-30", tracks=sl.tracks, hindsight=True)

            with self.assertRaises(ValueError):
                st.resolve(state, "2026-09-02", slice_fn=bad_slice, checkpoints_path=cks)

    def test_resolve_cannot_go_backwards_or_past_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trees, cks, state = self._registered(tmp)
            with self.assertRaises(ValueError):
                st.resolve(state, "2026-09-01", slice_fn=lambda a, e, **kw: _slice(a), checkpoints_path=cks)
            terminal = copy.deepcopy(state)
            terminal["status"] = "resolved"
            step = st.resolve(terminal, "2026-09-05", slice_fn=lambda a, e, **kw: _slice(a), checkpoints_path=cks)
            self.assertIsNone(step.node_id)


class RecheckTests(unittest.TestCase):
    def test_recheck_counts_and_withholds_rate_below_min_n(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trees, cks = Path(tmp) / "t.jsonl", Path(tmp) / "c.jsonl"
            tree = st.ensure_valid(_spec())
            _, rec = st.register(trees, tree, checkpoints_path=cks)
            state = st.current_state(st.load(trees), rec["id"])
            step = st.resolve(state, "2026-09-02", slice_fn=lambda a, e, **kw: _slice(a, stage="下跌", surge=1.0), checkpoints_path=cks)
            st.append_step(trees, step)
            rc = st.recheck(st.load(trees))
            self.assertEqual((rc.trees, rc.steps, rc.steps_otherwise, rc.steps_declared), (1, 1, 1, 0))
            self.assertEqual(rc.samples, 1)
            self.assertIn("样本不足", rc.to_dict()["otherwise_share"])
            # 规则样本存在 step 记录里，没有新台账文件
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["c.jsonl", "t.jsonl"])


class OldModuleUntouchedTests(unittest.TestCase):
    def test_legacy_scenario_tree_artifact_still_importable(self) -> None:
        from intelligence.services import scenario_tree as legacy

        self.assertTrue(hasattr(legacy, "ScenarioTreeArtifact"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class DailyHookSeamTests(unittest.TestCase):
    def test_hook_off_returns_same_object(self) -> None:
        """关掉时每日复盘逐字节不变：返回**同一个对象**（is），且不读盘。"""
        import os
        from unittest import mock

        body = "# 日报\n正文"
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": tmp}, clear=False):
                from intelligence import userspace

                us = userspace.user_space("hooktester")
            with mock.patch.dict(os.environ, {st.ENV_RESOLVE_FLAG: ""}, clear=False), \
                 mock.patch.object(st, "load", side_effect=AssertionError("关闭时不得读台账")):
                out = st.daily_review_hook(body, us, "2026-09-02")
        self.assertIs(out, body)

    def test_hook_on_without_trees_is_still_identity(self) -> None:
        import os
        from unittest import mock

        body = "# 日报"
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": tmp, st.ENV_RESOLVE_FLAG: "1"}, clear=False):
                from intelligence import userspace

                us = userspace.user_space("hooktester2")
                out = st.daily_review_hook(body, us, "2026-09-02")
        self.assertIs(out, body)
