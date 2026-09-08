"""题材生命周期单一词表测试（工单 #21 剩余 P1 / roadmap G-04）。"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from intelligence.services import theme_lifecycle as eight
from intelligence.services import theme_lifecycle_timeline as seven
from intelligence.services import theme_stage_vocab as v

REPO_ROOT = Path(__file__).resolve().parents[2]


class VocabTests(unittest.TestCase):
    def test_canonical_is_the_seven_stage_machine_words(self) -> None:
        self.assertEqual(
            v.CANONICAL_STAGES,
            (seven.STAGE_INCUBATION, seven.STAGE_FIRST_MOVE, seven.STAGE_FERMENT, seven.STAGE_MAIN_UP,
             seven.STAGE_DIVERGENCE, seven.STAGE_EBB, seven.STAGE_REFLOW),
        )

    def test_every_eight_stage_word_maps_and_one_to_many_carries_condition(self) -> None:
        for word in eight.LIFECYCLE_STAGES + [eight.STAGE_UNKNOWN]:
            tr = v.canonical_of(word)
            self.assertIn(tr.canonical, (*v.CANONICAL_STAGES, v.GAP), word)
        warm = v.canonical_of(eight.STAGE_WARMING)
        self.assertTrue(warm.ambiguous)
        self.assertEqual(warm.canonical, seven.STAGE_FERMENT)
        self.assertEqual(v.canonical_of(eight.STAGE_WARMING, first_signal=True).canonical, seven.STAGE_FIRST_MOVE)
        self.assertFalse(v.canonical_of(eight.STAGE_WARMING, first_signal=False).ambiguous)
        self.assertEqual(v.canonical_of(eight.STAGE_UNKNOWN).canonical, v.GAP)

    def test_five_legacy_words_are_aliases_not_values(self) -> None:
        self.assertEqual(v.canonical_of("启动").canonical, seven.STAGE_FIRST_MOVE)
        self.assertEqual(v.canonical_of("高潮").canonical, seven.STAGE_MAIN_UP)
        self.assertEqual(v.canonical_of("高潮").source_vocab, "five_legacy")
        self.assertNotIn("启动", v.CANONICAL_STAGES)
        self.assertNotIn("高潮", v.CANONICAL_STAGES)

    def test_unknown_word_is_rejected_not_passed_through(self) -> None:
        with self.assertRaises(ValueError):
            v.canonical_of("暗流")  # 舆论阶梯的词，不是题材阶段
        with self.assertRaises(ValueError):
            v.eight_to_canonical("发酵")

    def test_stage_on_day_returns_gap_outside_segments(self) -> None:
        segs = [seven.StageSegment("发酵", "2026-09-01", "2026-09-03", "t"), seven.StageSegment("退潮", "2026-09-06", "2026-09-10", "t")]
        self.assertEqual(v.stage_on_day(segs, "2026-09-02"), "发酵")
        self.assertEqual(v.stage_on_day(segs, "2026-09-04"), v.GAP)  # 段间空档
        self.assertEqual(v.stage_on_day(segs, "2026-08-30"), v.GAP)  # 首个信号之前
        self.assertEqual(v.stage_on_day(segs, "2026-09-10"), "退潮")

    def test_doc_table_equals_code_table(self) -> None:
        """UBIQUITOUS_LANGUAGE.md 的映射表由 render_mapping_markdown 生成——文档漂了这里红。"""
        doc = (REPO_ROOT / "UBIQUITOUS_LANGUAGE.md").read_text(encoding="utf-8")
        table = v.render_mapping_markdown()
        self.assertIn(table, doc, "UBIQUITOUS_LANGUAGE.md「题材生命周期」映射表与 theme_stage_vocab 不一致")

    def test_no_collision_with_opinion_or_market_vocabularies(self) -> None:
        market_words = {"底部横盘", "反弹", "主升", "顶部横盘", "下跌", "上涨", "高位震荡"}
        # 「主升」两边都有：题材七段与供应商 market_stage 共用一个词，是历史遗留；这里只钉住其余词不再新增撞名。
        overlap = set(v.CANONICAL_STAGES) & market_words
        self.assertEqual(overlap, {"主升"})
        opinion_words = {"萌芽", "扩散", "拥挤", "退热", "证伪"}
        self.assertEqual(set(v.CANONICAL_STAGES) & opinion_words, set())

    def test_five_stage_reservation_retired_in_design_doc(self) -> None:
        doc = (REPO_ROOT / "docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md").read_text(encoding="utf-8")
        self.assertIsNotNone(re.search(r"lifecycle_stage.*(作废|改用七段|theme_stage_vocab)", doc), "设计稿五段预留行应标作废并指向七段词表")


class ThemeLifecycleTimelineAliasTests(unittest.TestCase):
    def test_eight_stage_module_still_intact(self) -> None:
        """八阶段模块降为读法层别名，本单不删它。"""
        self.assertEqual(len(eight.LIFECYCLE_STAGES), 8)
        self.assertIn(eight.STAGE_WARMING, eight._STAGE_GUIDANCE)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
