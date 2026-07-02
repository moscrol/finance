from __future__ import annotations

import unittest

from intelligence.services.market_structure import (
    PHASE_HIGH_LOW_SWITCH,
    PHASE_HIGH_REALIZATION,
    PHASE_ICE_REPAIR,
    PHASE_MAIN_RISE,
    PHASE_SHRINK_ROTATION,
    PHASE_TREND_DIVERGENCE,
    PHASE_UNKNOWN,
    classify_market_structure,
)
from intelligence.services.sellside_divergence import (
    BUCKET_CONFIRM_ONLY,
    BUCKET_CONTRARIAN_CAUTION,
    BUCKET_EXPLORE,
    diverge_sellside_views,
)
from intelligence.services.theme_lifecycle import (
    STAGE_ACCELERATION,
    STAGE_DECAY_WATCH,
    STAGE_FALSIFIED_EXIT,
    STAGE_HIGH_DIVERGENCE,
    STAGE_NEW,
    STAGE_SECOND_WAVE,
    STAGE_WARMING,
    diagnose_theme_lifecycle,
)


class MarketStructureTests(unittest.TestCase):
    def test_main_rise_needs_expansion_plus_cluster(self) -> None:
        state = classify_market_structure(
            ["板块双红，边际量放大 [S1]", "新高成簇，涨停热度集中 [S2]"]
        )
        self.assertEqual(state.phase, PHASE_MAIN_RISE)
        self.assertFalse(state.missing)

    def test_single_sided_signal_flags_low_confidence(self) -> None:
        state = classify_market_structure(["涨停热度集中 [S1]"])
        self.assertEqual(state.phase, PHASE_MAIN_RISE)
        self.assertTrue(state.missing)

    def test_divergence_beats_main_rise(self) -> None:
        state = classify_market_structure(["板块放量但高位分歧加剧，龙头高开低走 [S1]"])
        self.assertEqual(state.phase, PHASE_TREND_DIVERGENCE)

    def test_high_realization(self) -> None:
        state = classify_market_structure(["主线高位缩量，资金流出，抱团松动 [S1]"])
        self.assertEqual(state.phase, PHASE_HIGH_REALIZATION)

    def test_high_low_switch_and_ice_repair_priority(self) -> None:
        self.assertEqual(
            classify_market_structure(["主线退潮，资金高低切至低位补涨 [S1]"]).phase,
            PHASE_HIGH_LOW_SWITCH,
        )
        self.assertEqual(
            classify_market_structure(["情绪冰点后超跌反弹修复 [S1]"]).phase,
            PHASE_ICE_REPAIR,
        )

    def test_shrink_rotation_and_unknown(self) -> None:
        self.assertEqual(
            classify_market_structure(["全市场缩量轮动，无主线 [S1]"]).phase,
            PHASE_SHRINK_ROTATION,
        )
        empty = classify_market_structure([])
        self.assertEqual(empty.phase, PHASE_UNKNOWN)
        self.assertTrue(empty.missing)

    def test_trigger_types_feed_classification(self) -> None:
        state = classify_market_structure([], ["double_red", "new_high_cluster"])
        self.assertEqual(state.phase, PHASE_MAIN_RISE)

    def test_prompt_block_contains_phase_and_playbook(self) -> None:
        block = classify_market_structure(["板块双红，新高成簇 [S1]"]).to_prompt_block()
        self.assertIn("市场结构状态机", block)
        self.assertIn(PHASE_MAIN_RISE, block)


class ThemeLifecycleTests(unittest.TestCase):
    def _state(self, lines: list[str]):
        return classify_market_structure(lines)

    def test_falsified_exit_wins_over_everything(self) -> None:
        diag = diagnose_theme_lifecycle(
            "固态电池",
            ["公司公告澄清：相关订单不属实 [R1]", "板块双红新高成簇 [S1]"],
            [],
            self._state(["板块双红，新高成簇 [S1]"]),
        )
        self.assertEqual(diag.stage, STAGE_FALSIFIED_EXIT)

    def test_acceleration_requires_hard_follow(self) -> None:
        diag = diagnose_theme_lifecycle(
            "液冷",
            ["英维克公告披露液冷订单 [R1]"],
            [],
            self._state(["板块双红，边际量放大，新高成簇 [S1]"]),
        )
        self.assertEqual(diag.stage, STAGE_ACCELERATION)

    def test_warming_without_hard_evidence_flags_gap(self) -> None:
        diag = diagnose_theme_lifecycle(
            "液冷",
            ["研报提示需求扩张 [W1]"],
            [],
            self._state(["板块双红，边际量放大，涨停热度集中 [S1]"]),
        )
        self.assertEqual(diag.stage, STAGE_WARMING)
        self.assertTrue(any("L3" in g for g in diag.gaps))

    def test_high_divergence_from_market_phase(self) -> None:
        diag = diagnose_theme_lifecycle(
            "液冷", [], [], self._state(["板块放量分歧，炸板增多 [S1]"])
        )
        self.assertEqual(diag.stage, STAGE_HIGH_DIVERGENCE)

    def test_second_wave_when_reawakened_in_switch(self) -> None:
        diag = diagnose_theme_lifecycle(
            "机器人",
            ["旧逻辑被新催化再度唤醒 [W1]"],
            [],
            self._state(["主线退潮，高低切至低位 [S1]"]),
        )
        self.assertEqual(diag.stage, STAGE_SECOND_WAVE)

    def test_decay_watch_from_high_realization(self) -> None:
        diag = diagnose_theme_lifecycle(
            "液冷", [], [], self._state(["高位缩量兑现，资金流出 [S1]"])
        )
        self.assertEqual(diag.stage, STAGE_DECAY_WATCH)

    def test_new_theme_detected_from_gap_lines(self) -> None:
        diag = diagnose_theme_lifecycle(
            "具身智能电子皮肤",
            [],
            ["知识图谱未命中该词：可能是新词/别名未登记"],
            self._state([]),
        )
        self.assertEqual(diag.stage, STAGE_NEW)

    def test_prompt_block_mentions_stage(self) -> None:
        diag = diagnose_theme_lifecycle(
            "液冷", [], [], self._state(["板块放量分歧 [S1]"]), candidate_tier="deep"
        )
        block = diag.to_prompt_block()
        self.assertIn("题材生命周期诊断", block)
        self.assertIn(diag.stage, block)
        self.assertIn("deep", block)


class SellsideDivergenceTests(unittest.TestCase):
    def test_three_buckets(self) -> None:
        state = classify_market_structure(["全市场缩量轮动，无主线 [S1]"])
        report = diverge_sellside_views(
            [
                "某券商首次覆盖：公司公告披露快接头订单落地，签订供货合同",
                "多家覆盖集体上调目标价，一致预期强化，发布会催化临近",
                "重申买入评级，维持盈利预测",
            ],
            state,
        )
        self.assertEqual(report.views[0].bucket, BUCKET_EXPLORE)
        self.assertEqual(report.views[1].bucket, BUCKET_CONTRARIAN_CAUTION)
        self.assertEqual(report.views[2].bucket, BUCKET_CONTRARIAN_CAUTION)

    def test_high_coverage_hard_evidence_calm_phase_is_confirm_only(self) -> None:
        state = classify_market_structure(["板块双红，新高成簇 [S1]"])
        report = diverge_sellside_views(
            ["多家覆盖重申：公司公告量产落地，产能爬坡确认"], state
        )
        self.assertEqual(report.views[0].bucket, BUCKET_CONFIRM_ONLY)

    def test_high_risk_phase_downgrades_hard_evidence(self) -> None:
        state = classify_market_structure(["板块放量分歧，高开低走 [S1]"])
        report = diverge_sellside_views(
            ["多家覆盖：公司公告订单落地，签订合同"], state
        )
        self.assertEqual(report.views[0].bucket, BUCKET_CONTRARIAN_CAUTION)

    def test_prompt_block_lists_buckets(self) -> None:
        state = classify_market_structure([])
        block = diverge_sellside_views(["首次覆盖某冷门标的"], state).to_prompt_block()
        self.assertIn("优先发散", block)
        self.assertIn("反向谨慎", block)


if __name__ == "__main__":
    unittest.main()
