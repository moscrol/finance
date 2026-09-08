"""带读模式的契约测试（roadmap G-03 第 2 件；终局 spec §2.1 / §4.3）。

三条判据：默认开关按「有没有历史台账」、缺轨不被别的轨补、产品自己的产物过自己的硬门。
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from intelligence import userspace
from intelligence.services import guided_reading as gr
from intelligence.services import observation_script as osc

SLICE = {
    "as_of": "2026-09-04",
    "entity_id": "883418.FP",
    "entity_name": "算力租赁",
    "knowledge_cutoff": "2026-09-04",
    "pit_grade": "strict",
    "alias_applied": False,
    "tracks": {
        "market": [
            {
                "object_type": "label",
                "ref": "fact_sector_daily:883418.FP@2026-09-04",
                "source_hash": "abc123",
                "payload": {"pct_chg": 3.2, "amount": 620.0, "diff_ratio": 18.0, "empty": None},
            }
        ],
        "theme": [
            {
                "object_type": "label",
                "ref": "fact_theme_limit_heat_daily:算力租赁@2026-09-04",
                "source_hash": "def456",
                "payload": {"lifecycle_stage": "升温验证"},
            }
        ],
        "opinion": {"track": "opinion", "gap": True, "reason": "no_data", "detail": "当日无覆盖事件"},
        "capital": {"track": "capital", "gap": True, "reason": "no_source", "detail": "北向无表"},
        "stock": [],
        "judgment": {"track": "judgment", "gap": True, "reason": "no_source", "detail": ""},
    },
}


def _user_space(tmp: str, *, with_history: bool):
    with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": tmp}, clear=False):
        us = userspace.user_space("tester")
    us.root.mkdir(parents=True, exist_ok=True)
    if with_history:
        us.checkpoints_path.write_text('{"id":"ck-1","claim":"旧判断"}\n', encoding="utf-8")
    return us


class SwitchTests(unittest.TestCase):
    def test_new_user_defaults_on(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            enabled, reason = gr.resolve_enabled(_user_space(tmp, with_history=False))
            self.assertTrue(enabled)
            self.assertIn("零历史", reason)

    def test_existing_user_defaults_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            enabled, reason = gr.resolve_enabled(_user_space(tmp, with_history=True))
            self.assertFalse(enabled)
            self.assertIn("历史", reason)

    def test_empty_ledger_file_still_counts_as_new(self) -> None:
        """文件存在但零行 = 没历史。按 ``exists()`` 判会把新用户判成老用户。"""
        with tempfile.TemporaryDirectory() as tmp:
            us = _user_space(tmp, with_history=False)
            us.checkpoints_path.write_text("\n \n", encoding="utf-8")
            self.assertTrue(gr.is_new_user(us))

    def test_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _user_space(tmp, with_history=True)
            with mock.patch.dict(os.environ, {gr.ENV_FLAG: "on"}, clear=False):
                enabled, reason = gr.resolve_enabled(us)
            self.assertTrue(enabled)
            self.assertIn(gr.ENV_FLAG, reason)

    def test_explicit_override_beats_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _user_space(tmp, with_history=False)
            with mock.patch.dict(os.environ, {gr.ENV_FLAG: "on"}, clear=False):
                enabled, reason = gr.resolve_enabled(us, override=False)
            self.assertFalse(enabled)
            self.assertEqual(reason, "显式参数")

    def test_disabled_run_reads_and_writes_nothing(self) -> None:
        """老用户路径必须零动作——这是「关掉后逐字节不变」现在能钉住的那部分。"""
        with tempfile.TemporaryDirectory() as tmp:
            us = _user_space(tmp, with_history=True)
            before = sorted(p.name for p in us.root.iterdir())
            result, reason = gr.run(us, SLICE)
            self.assertIsNone(result)
            self.assertIn("关", reason)
            self.assertEqual(sorted(p.name for p in us.root.iterdir()), before)


class BuildTests(unittest.TestCase):
    def test_facts_only_from_present_tracks(self) -> None:
        out = gr.build(SLICE)
        self.assertEqual(sorted(out.facts), ["market", "theme"])
        self.assertIn("pct_chg=3.2", out.facts["market"][0])
        self.assertIn("ref=", out.facts["market"][0])

    def test_gap_tracks_are_declared_not_filled(self) -> None:
        out = gr.build(SLICE)
        reasons = " ".join(out.gaps)
        for track in ("opinion", "capital", "judgment"):
            self.assertIn(track, reasons)
        # 缺轨不许被别的轨补：缺口段里出现的轨，不能同时出现在事实段。
        self.assertEqual(set(out.facts) & {"opinion", "capital", "judgment"}, set())

    def test_empty_list_is_a_gap_not_no_change(self) -> None:
        """空列表不是「今天没变化」，是读不出来——当成没变化会把缺数说成事实。"""
        out = gr.build(SLICE)
        self.assertTrue(any(g.startswith("stock：empty") for g in out.gaps))

    def test_pit_downgrade_becomes_a_limit(self) -> None:
        out = gr.build({**SLICE, "pit_grade": "trade_date_only"})
        self.assertTrue(any("pit_grade" in x for x in out.limits))

    def test_alias_applied_survives_serialization(self) -> None:
        """限定语从切片自己读：调用方漏传就丢掉换源警告。"""
        out = gr.build({**SLICE, "alias_applied": True})
        self.assertTrue(any("alias_applied" in x for x in out.limits))

    def test_no_inference_section(self) -> None:
        """G-01 母本没写完前不生成判读——留空并写明原因，比编一段没出处的话诚实。"""
        text = gr.render(gr.build(SLICE))
        self.assertIn("## 判读", text)
        self.assertIn("G-01", text)

    def test_deterministic(self) -> None:
        self.assertEqual(gr.build(SLICE).to_dict(), gr.build(SLICE).to_dict())

    def test_all_gap_slice_has_no_draft(self) -> None:
        empty = {**SLICE, "tracks": {t: {"gap": True, "reason": "no_data"} for t in SLICE["tracks"]}}
        out = gr.build(empty)
        self.assertIsNone(out.draft)
        self.assertTrue(any("六轨全缺" in x for x in out.limits))


class DraftTests(unittest.TestCase):
    def test_draft_passes_its_own_hard_gate(self) -> None:
        """产品自己生成的骨架过不了自己的硬门，是硬故障。"""
        draft = gr.build(SLICE).draft
        assert draft is not None
        self.assertEqual(osc.validate(draft), [])

    def test_draft_is_drafted_and_carries_evidence(self) -> None:
        draft = gr.build(SLICE).draft
        assert draft is not None
        self.assertEqual(draft.status, "drafted")
        self.assertTrue(draft.evidence_refs)
        self.assertTrue(draft.downgrade_or_abandon_conditions)
        self.assertIn("骨架", draft.scope_note)

    def test_draft_variables_track_what_is_readable(self) -> None:
        draft = gr.build(SLICE).draft
        assert draft is not None
        joined = " ".join(draft.variables)
        self.assertIn("盘面轨", joined)
        self.assertIn("题材轨", joined)
        self.assertNotIn("资金轨", joined, "读不出来的轨不该出现在明天要看的变量里")

    def test_rendered_output_passes_wording_lint(self) -> None:
        self.assertEqual(gr.lint_output(gr.render(gr.build(SLICE))), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
