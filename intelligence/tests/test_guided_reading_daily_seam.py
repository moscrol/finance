"""带读接进每日复盘的接缝（roadmap G-03 验收 d：关掉带读 = 现有行为逐字节不变）。

这条验收在接线之前是**平凡成立**的——没人调用带读，当然不变。收据里写明过这一点。
本文件是它变成真断言的那一刀：`intelligence/cli.py` 的 daily 路径现在真的调用了
`merge_into_daily_review`，所以「不变」必须由代码保证，而不是由「没人调用」保证。

判据取 ``is`` 而不是 ``==``：只做相等还留着「重新拼一遍恰好拼回原样」的余地，
那种实现哪天多加一个换行，验收就悄悄不成立了。返回同一个对象，改动无处藏身。
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence import userspace
from intelligence.services import guided_reading as gr

REPORT = {
    "date": "2026-09-02",
    "logic_batch": {
        "results": [
            {"market_theme": "国防军工", "priority_score": 30},
            {"market_theme": "算力租赁", "priority_score": 90},
            {"matched_theme": "固态电池", "priority_score": 55},
        ]
    },
}

# 断连专用：两条同分，按名字升序应稳定取「固态电池」（固 U+56FA < 算 U+7B97）。
TIE_REPORT = {
    "date": "2026-09-02",
    "logic_batch": {
        "results": [
            {"market_theme": "算力租赁", "priority_score": 90},
            {"matched_theme": "固态电池", "priority_score": 90},
        ]
    },
}

SLICE = {
    "as_of": "2026-09-02",
    "entity_id": "990306.FP",
    "entity_name": "算力租赁",
    "knowledge_cutoff": "2026-09-02",
    "pit_grade": "strict",
    "tracks": {
        "market": [
            {
                "object_type": "label",
                "ref": "fact_sector_daily:990306.FP@2026-09-02",
                "source_hash": "abc",
                "payload": {"pct_chg": 3.2},
            }
        ]
    },
}


def _space(root: str, uid: str, *, with_history: bool):
    with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": root}, clear=False):
        us = userspace.user_space(uid)
    us.root.mkdir(parents=True, exist_ok=True)
    if with_history:
        us.checkpoints_path.write_text('{"id":"ck-1","claim":"旧判断"}\n', encoding="utf-8")
    return us


class ByteIdenticalWhenOff(unittest.TestCase):
    def test_returns_the_same_object(self) -> None:
        text = "# 2026-09-02 日报\n\n正文……\n"
        self.assertIs(gr.merge_into_daily_review(text, None), text)

    def test_empty_and_weird_inputs_unchanged(self) -> None:
        for text in ("", "\n\n", "只有一行"):
            self.assertIs(gr.merge_into_daily_review(text, None), text)

    def test_existing_user_gets_none_so_daily_is_untouched(self) -> None:
        """老用户默认关 → build_for_daily_review 返回 None → 上面那条 is 生效。"""
        with tempfile.TemporaryDirectory() as tmp:
            us = _space(tmp, "veteran", with_history=True)
            guided, reason = gr.build_for_daily_review(REPORT, us)
            self.assertIsNone(guided)
            self.assertIn("关", reason)

    def test_explicit_off_beats_new_user_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _space(tmp, "rookie", with_history=False)
            guided, _ = gr.build_for_daily_review(REPORT, us, override=False)
            self.assertIsNone(guided)


class SectionIsAppendedWhenOn(unittest.TestCase):
    def test_merge_appends_and_keeps_body(self) -> None:
        body = "# 日报\n\n原有正文\n"
        out = gr.merge_into_daily_review(body, gr.build(SLICE))
        self.assertIn("原有正文", out)
        self.assertIn("今日带读", out)
        self.assertTrue(out.startswith("# 日报"), "带读是**追加**，不能顶掉原有正文")

    def test_merge_is_idempotent(self) -> None:
        """夜跑重试 / 二次合并不该叠出两段带读。"""
        g = gr.build(SLICE)
        once = gr.merge_into_daily_review("正文", g)
        self.assertEqual(gr.merge_into_daily_review(once, g), once)

    def test_merged_output_passes_wording_lint(self) -> None:
        out = gr.merge_into_daily_review("正文", gr.build(SLICE))
        self.assertEqual(gr.lint_output(out), [])


class EntityPickIsDeterministic(unittest.TestCase):
    def test_highest_priority_wins(self) -> None:
        self.assertEqual(gr.pick_entity(REPORT), "算力租赁")

    def test_tie_broken_by_name_not_by_input_order(self) -> None:
        """同分按名字升序断连——否则同一份 report 两次渲染出不同带读，幂等验收假绿。"""
        flipped = {
            **TIE_REPORT,
            "logic_batch": {"results": list(reversed(TIE_REPORT["logic_batch"]["results"]))},
        }
        self.assertEqual(gr.pick_entity(flipped), gr.pick_entity(TIE_REPORT))
        self.assertEqual(gr.pick_entity(TIE_REPORT), "固态电池")

    def test_no_theme_returns_none_not_a_guess(self) -> None:
        for bad in ({}, {"logic_batch": {}}, {"logic_batch": {"results": []}},
                    {"logic_batch": {"results": [{"priority_score": 9}]}}):
            self.assertIsNone(gr.pick_entity(bad))

    def test_unparseable_score_does_not_crash(self) -> None:
        rep = {"logic_batch": {"results": [{"market_theme": "甲", "priority_score": "N/A"}]}}
        self.assertEqual(gr.pick_entity(rep), "甲")


class FailuresDoNotBreakTheDaily(unittest.TestCase):
    def test_missing_date_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _space(tmp, "rookie", with_history=False)
            guided, reason = gr.build_for_daily_review({**REPORT, "date": ""}, us)
            self.assertIsNone(guided)
            self.assertIn("date", reason)

    def test_slice_failure_is_swallowed_with_a_reason(self) -> None:
        """带读读不到切片就不出这一段——不能让它把整份复盘带崩。"""
        with tempfile.TemporaryDirectory() as tmp:
            us = _space(tmp, "rookie", with_history=False)
            guided, reason = gr.build_for_daily_review(
                REPORT, us, db_path="/tmp/definitely-not-a-db.duckdb"
            )
            self.assertIsNone(guided)
            self.assertIn("切片读取失败", reason)


class ProductionSeamIsWired(unittest.TestCase):
    """接线本身要被钉住：这条验收的全部意义就在于「真的有生产调用方」。"""

    def test_cli_daily_path_calls_the_seam(self) -> None:
        src = Path("intelligence/cli.py").read_text(encoding="utf-8")
        self.assertIn("build_for_daily_review", src)
        self.assertIn("merge_into_daily_review", src)
        self.assertIn("--no-guided-reading", src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
