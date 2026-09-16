"""上下文投影契约测试（工单 #34 / roadmap G-14；09-06 spec §4.5、§10 第 11 条、§11 第 11 条）。

判据：同输入同哈希；哈希只对「选了哪些对象、对象内容指纹」敏感、对文案不敏感；
gaps / limits 强制且排在事实之前；预算按块省略不截断；默认序是领域序不是字母序；
台账对 agent 产物无哈希拒收；带读关闭路径逐字节不变。
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence import userspace
from intelligence.services import checkpoints
from intelligence.services import guided_reading as gr
from intelligence.services import river_projection as rp
from intelligence.services.river import TRACKS

REPO_ROOT = Path(__file__).resolve().parents[2]


def _obj(track: str, otype: str, ref: str, payload: dict, *, recorded_at: str | None = "2026-09-04T18:00:00", h: str | None = None):
    return {
        "track": track,
        "entity_id": "883418.FP",
        "object_type": otype,
        "ref": ref,
        "source_hash": h or ("h" + ref[-6:]),
        "valid_from": "2026-09-04",
        "recorded_at": recorded_at,
        "payload": payload,
    }


def _slice() -> dict:
    return {
        "as_of": "2026-09-04",
        "entity_id": "883418.FP",
        "entity_name": "算力租赁",
        "knowledge_cutoff": "2026-09-04",
        "pit_grade": "strict",
        "hindsight": False,
        "alias_applied": False,
        "tracks": {
            # 故意把 payload 键写成非字母序，验证渲染按 provider 序而不是排序
            "market": [
                _obj("market", "label", "fact_sector_daily:883418.FP@2026-09-04",
                     {"pct_chg": 3.2, "amount": 620.0, "diff_ratio": 18.0, "zz": 1, "aa": 2, "mm": 3, "extra_key": 9, "empty": None}),
                _obj("market", "stage", "fact_market_daily:2026-09-04", {"market_stage": "反弹", "hardness": "L2"}),
            ],
            "theme": [
                _obj("theme", "label", "fact_theme_limit_heat_daily:算力租赁@2026-09-04", {"rank": 3}),
                _obj("theme", "event", "fact_theme_limit_stock_daily:2026-09-04:883418.FP:300001.SZ",
                     {"stock_ts_code": "300001.SZ", "limit_status": "U"}),
                _obj("theme", "event", "fact_theme_limit_stock_daily:2026-09-04:883418.FP:300002.SZ",
                     {"stock_ts_code": "300002.SZ", "limit_status": "U"}),
            ],
            "opinion": [
                _obj("opinion", "narrative_version", "fact_theme_fundamental_doc:7", {"derivation": "frozen_llm", "title": "v2 订单"}),
                _obj("opinion", "label", "fact_research_report_catalog:coverage:算力租赁:2026-09-04", {"count_90d": 4}),
            ],
            "capital": {"track": "capital", "gap": True, "reason": "no_source", "detail": "北向无表"},
            "stock": [],
            "judgment": {"track": "judgment", "gap": True, "reason": "no_source", "detail": ""},
        },
    }


class HashContractTests(unittest.TestCase):
    def test_same_input_same_hash_and_no_side_effects(self) -> None:
        a = rp.project(_slice(), framework_version=None, task="guided_reading")
        b = rp.project(_slice(), framework_version=None, task="guided_reading")
        self.assertEqual(a.projection_hash, b.projection_hash)
        self.assertTrue(a.projection_hash.startswith("cp:"))
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_hash_changes_when_source_hash_changes_not_when_rendering_changes(self) -> None:
        base = rp.project(_slice(), framework_version=None, task="guided_reading")
        s2 = _slice()
        s2["tracks"]["market"][0]["source_hash"] = "republished"
        self.assertNotEqual(base.projection_hash, rp.project(s2, framework_version=None, task="guided_reading").projection_hash)
        # 文案 / 显示键数改了：哈希不变
        with mock.patch.object(rp, "RENDER_KEYS", 2):
            fewer = rp.project(_slice(), framework_version=None, task="guided_reading")
        self.assertEqual(base.projection_hash, fewer.projection_hash)
        label_full = [b for b in base.blocks if b.object_type == "label" and b.track == "market"][0]
        label_fewer = [b for b in fewer.blocks if b.object_type == "label" and b.track == "market"][0]
        self.assertNotEqual(label_full.rendered_text, label_fewer.rendered_text)
        self.assertIn("另有 5 键未显示", label_fewer.rendered_text)

    def test_hash_covers_task_budget_framework_and_source_ref(self) -> None:
        base = rp.project(_slice(), framework_version=None, task="guided_reading")
        self.assertNotEqual(base.projection_hash, rp.project(_slice(), framework_version=None, task="ask_synthesis").projection_hash)
        self.assertNotEqual(base.projection_hash, rp.project(_slice(), framework_version=None, task="guided_reading", budget=99).projection_hash)
        self.assertNotEqual(base.projection_hash, rp.project(_slice(), framework_version="tf-v0.2", task="guided_reading").projection_hash)
        self.assertNotEqual(base.projection_hash, rp.project({**_slice(), "knowledge_cutoff": "2026-09-05", "hindsight": True}, framework_version=None, task="guided_reading").projection_hash)

    def test_mandatory_blocks_cannot_be_none(self) -> None:
        cp = rp.project(_slice(), framework_version=None, task="guided_reading")
        for name in ("omitted", "omitted_refs", "limits", "gaps", "budget"):
            broken = copy.copy(cp)
            object.__setattr__(broken, name, None)
            with self.assertRaises(ValueError, msg=name):
                broken.canonical_json()

    def test_task_required(self) -> None:
        with self.assertRaises(ValueError):
            rp.project(_slice(), framework_version=None, task="")


class SelectionAndOrderTests(unittest.TestCase):
    def test_default_order_is_domain_order_not_alphabetical(self) -> None:
        cp = rp.project(_slice(), framework_version=None, task="guided_reading")
        tracks_in_order = []
        for b in cp.blocks:
            if b.track not in tracks_in_order:
                tracks_in_order.append(b.track)
        self.assertEqual(tracks_in_order, [t for t in TRACKS if t in tracks_in_order])
        self.assertEqual(tracks_in_order, ["market", "theme", "opinion"])  # 字母序会是 market, opinion, theme
        self.assertTrue(all(b.selected_by == "default" for b in cp.blocks))

    def test_within_track_hardness_desc_then_recorded_at_then_ref(self) -> None:
        cp = rp.project(_slice(), framework_version=None, task="guided_reading")
        market = [b for b in cp.blocks if b.track == "market"]
        # stage 对象带 hardness=L2，排在无硬度的 label 块之前
        self.assertEqual([b.object_type for b in market], ["stage", "label"])
        self.assertEqual(market[0].hardness, "L2")

    def test_frozen_llm_after_deterministic(self) -> None:
        cp = rp.project(_slice(), framework_version=None, task="guided_reading")
        opinion = [b for b in cp.blocks if b.track == "opinion"]
        self.assertEqual([b.derivation for b in opinion], ["deterministic", "frozen_llm"])

    def test_stock_nodes_collapse_to_count_block_no_names(self) -> None:
        cp = rp.project(_slice(), framework_version=None, task="guided_reading")
        collapsed = [b for b in cp.blocks if b.kind == "collapsed"]
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0].collapsed_count, 2)
        self.assertNotIn("300001", collapsed[0].rendered_text)
        self.assertIn("U×2", collapsed[0].rendered_text)
        # 折叠的 ref 仍在哈希覆盖范围内
        self.assertIn("fact_theme_limit_stock_daily:2026-09-04:883418.FP:300001.SZ", cp.selected_refs)

    def test_render_keeps_provider_key_order_and_reports_hidden_keys(self) -> None:
        cp = rp.project(_slice(), framework_version=None, task="guided_reading")
        label = [b for b in cp.blocks if b.track == "market" and b.object_type == "label"][0]
        self.assertTrue(label.rendered_text.startswith("label｜pct_chg=3.2，amount=620.0，diff_ratio=18.0"))
        self.assertIn("另有 1 键未显示", label.rendered_text)  # 7 个非空键，显示 6 个

    def test_gaps_and_limits_present_and_before_facts(self) -> None:
        src = {**_slice(), "pit_grade": "trade_date_only", "alias_applied": True}
        cp = rp.project(src, framework_version=None, task="guided_reading")
        self.assertTrue(any(g.startswith("capital：no_source") for g in cp.gaps))
        self.assertTrue(any(g.startswith("stock：empty") for g in cp.gaps))
        self.assertTrue(any(g.startswith("judgment：") for g in cp.gaps))
        self.assertTrue(any("pit_grade=trade_date_only" in x for x in cp.limits))
        self.assertTrue(any("alias_applied" in x for x in cp.limits))
        text = rp.render(cp)
        self.assertLess(text.index("## 限制"), text.index("## 事实块"))
        self.assertLess(text.index("## 缺口"), text.index("## 事实块"))

    def test_budget_omits_whole_blocks_never_truncates(self) -> None:
        full = rp.project(_slice(), framework_version=None, task="guided_reading")
        cp = rp.project(_slice(), framework_version=None, task="guided_reading", budget=1)
        self.assertEqual(cp.budget, {"limit": 1, "used": 1})
        self.assertEqual(len(cp.blocks), 1)
        kept = full.blocks[0]
        self.assertEqual(cp.blocks[0].object_refs, kept.object_refs)  # 整块在
        omitted_total = sum(cp.omitted.values())
        self.assertEqual(omitted_total, sum(len(b.object_refs) for b in full.blocks[1:]))
        # 每个被省的 ref 都可见（不是静默丢）
        all_refs = {r for b in full.blocks for r, _ in b.object_refs}
        omitted_refs = {r for refs in cp.omitted_refs.values() for r in refs}
        self.assertEqual(omitted_refs | {r for r, _ in cp.blocks[0].object_refs}, all_refs)
        # 缺口与限制不受预算影响
        self.assertEqual(cp.gaps, full.gaps)

    def test_rule_protocol_marks_selected_by(self) -> None:
        cp = rp.project(_slice(), framework_version="tf-test", task="guided_reading", rules={"market": rp.TopNRule(1)})
        market = [b for b in cp.blocks if b.track == "market"]
        self.assertEqual(len(market), 1)
        self.assertEqual(market[0].selected_by, "framework:test:top_n")
        self.assertEqual(cp.omitted.get("market"), 1)
        theme = [b for b in cp.blocks if b.track == "theme"]
        self.assertTrue(all(b.selected_by == "default" for b in theme))


class GuidedReadingConsumerTests(unittest.TestCase):
    def test_facts_come_from_projection_blocks(self) -> None:
        out = gr.build(_slice())
        cp = gr.project_slice(_slice())
        self.assertEqual(out.projection_hash, cp.projection_hash)
        for block in cp.blocks:
            for line in block.rendered_text.split("\n"):
                self.assertIn(line, out.facts[block.track])
        self.assertEqual(list(out.facts), ["market", "theme", "opinion"])

    def test_draft_evidence_refs_subset_of_projection(self) -> None:
        out = gr.build(_slice())
        cp = gr.project_slice(_slice())
        assert out.draft is not None
        self.assertTrue(set(out.draft.evidence_refs) <= set(cp.selected_refs))
        self.assertEqual(out.draft.projection_hash, cp.projection_hash)
        self.assertEqual(out.draft.model_id, gr.DETERMINISTIC_MODEL_ID)

    def test_render_has_hash_and_limits_before_facts(self) -> None:
        text = gr.render(gr.build(_slice()))
        self.assertIn("projection=cp:", text)
        self.assertLess(text.index("## 限制"), text.index("## 事实"))
        self.assertLess(text.index("## 缺口"), text.index("## 事实"))
        self.assertEqual(gr.lint_output(text), [])

    def test_disabled_path_untouched(self) -> None:
        """关掉带读 = 逐字节不变：``merge_into_daily_review`` 返回同一个对象，``run`` 不投影。"""
        body = "# 每日复盘\n正文"
        self.assertIs(gr.merge_into_daily_review(body, None), body)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": tmp}, clear=False):
                us = userspace.user_space("old")
            us.root.mkdir(parents=True, exist_ok=True)
            us.checkpoints_path.write_text('{"id":"ck-1","claim":"旧判断"}\n', encoding="utf-8")
            with mock.patch.object(rp, "project", side_effect=AssertionError("关闭路径不得投影")):
                result, reason = gr.run(us, _slice())
        self.assertIsNone(result)
        self.assertIn("关", reason)


class LedgerGateTests(unittest.TestCase):
    def test_observation_script_without_hash_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                checkpoints.register_checkpoint(
                    Path(tmp) / "c.jsonl", claim="x", due="2026-09-05", object_type="observation_script"
                )
            self.assertIn("projection_hash", str(ctx.exception))

    def test_agent_judgment_needs_hash_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.jsonl"
            with self.assertRaises(ValueError) as ctx:
                checkpoints.register_checkpoint(p, claim="x", due="2026-09-05", object_type="agent_judgment", projection_hash="cp:abc")
            self.assertIn("model_id", str(ctx.exception))
            _, rec = checkpoints.register_checkpoint(
                p, claim="x", due="2026-09-05", object_type="agent_judgment", projection_hash="cp:abc", model_id="gpt-5.6-sol"
            )
            self.assertEqual(rec["projection_hash"], "cp:abc")
            self.assertEqual(rec["model_id"], "gpt-5.6-sol")

    def test_user_judgment_may_omit_and_user_authored_script_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.jsonl"
            _, user = checkpoints.register_checkpoint(p, claim="用户判断", due="2026-09-05")
            self.assertIsNone(user["projection_hash"])
            self.assertNotIn("projection_hash_missing", user)
            _, manual = checkpoints.register_checkpoint(
                p, claim="手写剧本", due="2026-09-05", object_type="observation_script", user_authored=True
            )
            self.assertIsNone(manual["projection_hash"])
            self.assertEqual(manual["projection_hash_missing"], checkpoints.USER_AUTHORED)

    def test_calibrate_counts_projection_coverage_without_touching_rates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath, vpath = Path(tmp) / "c.jsonl", Path(tmp) / "v.jsonl"
            _, a = checkpoints.register_checkpoint(cpath, claim="a", due="2026-09-03", object_type="observation_script", projection_hash="cp:1")
            _, b = checkpoints.register_checkpoint(cpath, claim="b", due="2026-09-03", object_type="observation_script", user_authored=True)
            checkpoints.record_verdict(vpath, id=a["id"], verdict="hit")
            checkpoints.record_verdict(vpath, id=b["id"], verdict="miss")
            cks, _ = checkpoints.load_checkpoints(cpath)
            vds, _ = checkpoints.load_verdicts(vpath)
            cal = checkpoints.calibrate(cks, vds, today="2026-09-10")
        st = [s for s in cal.by_object_type if s.category == "observation_script"][0]
        self.assertEqual(st.n, 2)
        self.assertEqual(st.with_projection_hash, 1)
        self.assertEqual(cal.projection_hash_missing, 1)
        self.assertAlmostEqual(st.hit_rate, 0.5)
        self.assertIn("带上下文投影 1/2", checkpoints.render_report(cal))


class ReplayCliTests(unittest.TestCase):
    def test_replay_from_json_match_and_mismatch_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "slice.json"
            src.write_text(json.dumps(_slice(), ensure_ascii=False), encoding="utf-8")
            expected = rp.project(_slice(), framework_version=None, task="guided_reading").projection_hash
            cmd = [sys.executable, str(REPO_ROOT / "scripts" / "river_projection.py"), "replay", "--from-json", str(src), "--task", "guided_reading"]
            ok = subprocess.run([*cmd, "--expect", expected], capture_output=True, text=True, cwd=REPO_ROOT)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertIn("MATCH", ok.stdout)
            bad = subprocess.run([*cmd, "--expect", "cp:0000000000000000"], capture_output=True, text=True, cwd=REPO_ROOT)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("MISMATCH", bad.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
