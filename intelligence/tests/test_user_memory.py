from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services import user_memory as user_memory_module
from intelligence.services.user_memory import (
    PEER_HIT_MIN_N,
    RECALL_SOURCES,
    RELIABILITY_DOWNWEIGHT_THRESHOLD,
    MemoryRecall,
    build_memory_block,
    memory_block_for_query,
    peer_hit_line,
    reliability_downweight,
    select_relevant,
)
from intelligence.services.checkpoints import Calibration, CategoryStat


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")


class SelectRelevantTests(unittest.TestCase):
    def _judgments(self) -> list[dict]:
        return [
            {"memo": "数据安全出清见底，8月中报是拐点验证窗", "themes": ["数据安全"], "ts": "2026-07-01T00:00:00Z"},
            {"memo": "信创订单好但已定价", "themes": ["信创"], "ts": "2026-06-20T00:00:00Z"},
            {"memo": "白酒需求弱", "themes": ["白酒"], "ts": "2026-05-01T00:00:00Z"},
        ]

    def test_tag_hit_selected(self) -> None:
        hit = select_relevant(self._judgments(), "数据安全 中期赔率怎么看")
        self.assertEqual(len(hit), 1)
        self.assertIn("出清见底", hit[0]["memo"])

    def test_theme_entity_params_hit(self) -> None:
        hit = select_relevant(self._judgments(), "这个方向怎么看", theme="信创")
        self.assertEqual(len(hit), 1)
        self.assertIn("已定价", hit[0]["memo"])

    def test_no_hit_returns_empty(self) -> None:
        self.assertEqual(select_relevant(self._judgments(), "光模块 CPO 交换机"), [])

    def test_text_overlap_hit(self) -> None:
        hit = select_relevant(self._judgments(), "中报 拐点 在哪个板块")
        self.assertTrue(any("拐点验证窗" in r["memo"] for r in hit))


class BuildMemoryBlockTests(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(build_memory_block([], []), "")

    def test_renders_judgments_corrections_and_calibration(self) -> None:
        block = build_memory_block(
            [{"memo": "数据安全出清见底", "themes": ["数据安全"], "ts": "2026-07-01T00:00:00Z"}],
            [{"correction": "别把当日强度当中期赔率", "principle": "时间尺度要对齐", "ts": "2026-07-02T00:00:00Z"}],
            "- 拐点类：4 中 3 命中（命中率 75%，靠谱）",
        )
        self.assertIn("[M]", block)
        # W2 逐条归属：每条自带「这是你 X 日的判断/纠偏原则」，日期逐条不丢。
        self.assertIn("[M·你的判断 2026-07-01][数据安全]", block)
        self.assertIn("[M·你的纠偏原则 2026-07-02]：时间尺度要对齐", block)
        self.assertIn("回检校准", block)
        self.assertIn("命中率 75%", block)
        self.assertIn("使用要求", block)
        self.assertIn("历史先验（prior）", block)
        self.assertIn("相比上次发生了什么变化", block)
        self.assertIn("价格、产能、订单等易变项必须以本轮检索为准", block)

    def test_expired_judgment_ttl_is_annotated_in_memory_block(self) -> None:
        block = build_memory_block(
            [
                {
                    "memo": "扩产逻辑仍在。复核期限：2026-07-01。",
                    "themes": ["固态电池"],
                    "ts": "2026-06-18T00:00:00Z",
                    "valid_until": "2026-07-01",
                }
            ],
            [],
            as_of="2026-08-19",
        )
        self.assertIn("扩产逻辑仍在", block)
        self.assertIn("已过期，待复核", block)

    def test_correction_falls_back_to_correction_text(self) -> None:
        block = build_memory_block([], [{"correction": "应该看板块容量", "ts": "2026-07-02T00:00:00Z"}])
        self.assertIn("[M·你的纠偏原则 2026-07-02]：应该看板块容量", block)


class PeerHitLineTests(unittest.TestCase):
    """KC-11 三态：够 N / 不够 N / 零裁决。召回次数和 confidence 不得当胜率。"""

    def test_enough_n_renders_hits_over_adjudicated(self) -> None:
        n = PEER_HIT_MIN_N
        line = peer_hit_line(CategoryStat(category="生命周期推演", n=n, hits=4, miss=n - 4))
        self.assertEqual(line, f"同类判断历史 4/{n} 命中（分母=已裁决数）")

    def test_below_n_is_hidden(self) -> None:
        self.assertIsNone(peer_hit_line(CategoryStat(category="拐点", n=1, hits=1)))
        # 2026-09-04 前 min_n=2：两条裁决就出胜率行。现在 n < 10 一律不出，见 checkpoints.DEFAULT_CALIBRATION_MIN_N。
        self.assertIsNone(peer_hit_line(CategoryStat(category="拐点", n=PEER_HIT_MIN_N - 1, hits=PEER_HIT_MIN_N - 1)))

    def test_zero_verdicts_is_hidden(self) -> None:
        self.assertIsNone(peer_hit_line(None))
        self.assertIsNone(peer_hit_line(CategoryStat(category="未分类", n=0)))

    def test_recall_count_and_confidence_are_not_win_rate(self) -> None:
        n = PEER_HIT_MIN_N + 2
        line = peer_hit_line(CategoryStat(category="生命周期推演", n=n, hits=1, miss=n - 1))
        assert line is not None
        self.assertNotIn("99", line)
        self.assertNotIn("80%", line)
        self.assertNotIn("召回", line)
        self.assertNotIn("置信", line)
        self.assertNotIn("命中率", line)


class ReadSideContractTests(unittest.TestCase):
    """W1：读侧「记忆 = prior」契约（spec 2026-09-10-knevo-arch-delta-worklist）。

    防的两个失败形状：(a) 来源清单静默漂移（新源绕过写侧闸直进答案）；
    (b) [M] 块丢掉「只是先验」的使用约束脚注。工具侧的证据分级钉子在
    test_episode_tools（evidence_tier/先验自标/freshness）。
    """

    def test_recall_pool_sources_are_pinned(self) -> None:
        self.assertEqual(RECALL_SOURCES, ("judgments", "corrections", "methods"))
        self.assertEqual(
            set(MemoryRecall.__slots__),
            {"judgments", "corrections", "methods", "judgments_path", "corrections_path"},
            "MemoryRecall 出现新来源槽位：先在 RECALL_SOURCES 登记并在 PR 里声明"
            "该源为什么不含易变事实，再更新本断言",
        )

    def test_memory_block_footer_keeps_prior_discipline(self) -> None:
        block = build_memory_block(
            [{"memo": "出清见底", "themes": ["数据安全"], "ts": "2026-07-01T00:00:00Z"}], []
        )
        for token in (
            "使用要求",
            "历史先验（prior）",
            "不是当前市场事实",
            "易变项必须以本轮检索为准",
        ):
            self.assertIn(token, block)


class ReliabilityDownweightTests(unittest.TestCase):
    """W3：降权口径 = 计分率（partial=0.5，分母=已终态裁决数）；双闸 min-N；
    阈值默认关闭直到 evolution 回测过 + 人工确认。"""

    @staticmethod
    def _cal(*stats: CategoryStat) -> Calibration:
        return Calibration(by_category=list(stats))

    def test_threshold_defaults_to_none_until_backtested(self) -> None:
        self.assertIsNone(
            RELIABILITY_DOWNWEIGHT_THRESHOLD,
            "阈值必须先过 evolution 回测队列（evolution/backtest-queue.md）并经人工确认"
            "才允许填数；直接填数会让本测试变红，这是故意的",
        )
        records = [{"memo": "a", "category": "拐点"}]
        ordered, warns = reliability_downweight(
            records,
            [],
            self._cal(CategoryStat(category="拐点", n=20, miss=20, score_sum=0.0)),
            threshold=None,
        )
        self.assertEqual(ordered, records)
        self.assertEqual(warns, [None])

    def test_mixed_partial_sample_uses_score_rate_not_strict_rate(self) -> None:
        # 4 hit + 6 partial：整命中口径 40%，计分率 70%——驱动口径必须是后者，读数唯一。
        stat = CategoryStat(category="生命周期推演", n=10, hits=4, partial=6, miss=0, score_sum=7.0)
        records = [{"memo": "液冷验证", "category": "生命周期推演"}]
        # 阈值 0.5：若误用整命中口径（40%）会降权；计分率 70% 不该降。
        _ordered, warns = reliability_downweight(records, [], self._cal(stat), threshold=0.5)
        self.assertEqual(warns, [None])
        # 阈值 0.75：计分率 70% 低于阈值 → 降权 + 警告，警告里的读数是 70% 不是 40%。
        _ordered, warns = reliability_downweight(records, [], self._cal(stat), threshold=0.75)
        self.assertIsNotNone(warns[0])
        assert warns[0] is not None
        self.assertIn("70%", warns[0])
        self.assertIn("N=10", warns[0])
        self.assertIn("partial 计 0.5", warns[0])
        self.assertNotIn("40%", warns[0])

    def test_low_reliability_category_sinks_below_others(self) -> None:
        good = CategoryStat(category="拐点", n=12, hits=11, miss=1, score_sum=11.0)
        bad = CategoryStat(category="情绪外推", n=12, hits=1, miss=11, score_sum=1.0)
        records = [
            {"memo": "情绪还能涨", "category": "情绪外推"},
            {"memo": "拐点已确认", "category": "拐点"},
        ]
        ordered, warns = reliability_downweight(records, [], self._cal(good, bad), threshold=0.4)
        self.assertEqual([r["memo"] for r in ordered], ["拐点已确认", "情绪还能涨"])
        self.assertIsNone(warns[0])
        self.assertIn("情绪外推", warns[1] or "")

    def test_small_sample_is_not_downweighted(self) -> None:
        n = PEER_HIT_MIN_N - 1
        bad_small = CategoryStat(category="情绪外推", n=n, miss=n, score_sum=0.0)
        records = [{"memo": "情绪还能涨", "category": "情绪外推"}]
        ordered, warns = reliability_downweight(records, [], self._cal(bad_small), threshold=0.4)
        self.assertEqual(ordered, records)
        self.assertEqual(warns, [None])

    def test_uncategorized_record_is_untouched(self) -> None:
        records = [{"memo": "无分类判断"}]
        ordered, warns = reliability_downweight(records, [], self._cal(), threshold=0.4)
        self.assertEqual(ordered, records)
        self.assertEqual(warns, [None])

    def test_end_to_end_block_downweights_and_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            n = PEER_HIT_MIN_N
            _write_jsonl(root / "judgments.jsonl", [
                {"memo": "液冷情绪还能冲", "themes": ["液冷"], "ts": "2026-08-01T00:00:00Z", "category": "情绪外推"},
                {"memo": "液冷拐点已确认", "themes": ["液冷"], "ts": "2026-07-01T00:00:00Z", "category": "拐点"},
            ])
            _write_jsonl(
                root / "checkpoints.jsonl",
                [{"id": f"g{i}", "claim": f"拐点{i}", "category": "拐点", "due": "2026-06-01"} for i in range(n)]
                + [{"id": f"b{i}", "claim": f"情绪{i}", "category": "情绪外推", "due": "2026-06-01"} for i in range(n)],
            )
            _write_jsonl(
                root / "verdicts.jsonl",
                [{"id": f"g{i}", "verdict": "hit"} for i in range(n)]
                + [{"id": f"b{i}", "verdict": "miss"} for i in range(n)],
            )
            with mock.patch.object(user_memory_module, "RELIABILITY_DOWNWEIGHT_THRESHOLD", 0.4):
                block = memory_block_for_query("液冷怎么看", users_root=root)
            self.assertIn("⚠ 该类判断（情绪外推）", block)
            self.assertIn("计分率", block)
            # 低可靠条目沉底：召回原序是情绪在前（ts 更新），降权后拐点在前。
            self.assertLess(block.index("拐点已确认"), block.index("情绪还能冲"))
            # 展示口径（整命中 x/n）仍在，与警告行并存但各自标明口径。
            self.assertIn(f"同类判断历史 0/{n} 命中（分母=已裁决数）", block)
            # 默认态（阈值 None）：同样的台账不降权、不出警告——未回测不生效。
            block_off = memory_block_for_query("液冷怎么看", users_root=root)
            self.assertNotIn("⚠ 该类判断", block_off)
            self.assertLess(block_off.index("情绪还能冲"), block_off.index("拐点已确认"))


class MemoryBlockForQueryTests(unittest.TestCase):
    def test_missing_files_return_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(memory_block_for_query("数据安全怎么看", users_root=tmp), "")

    def test_end_to_end_with_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "judgments.jsonl", [
                {"memo": "数据安全出清见底，等中报拐点", "themes": ["数据安全"], "ts": "2026-07-01T00:00:00Z"},
                {"memo": "白酒需求弱", "themes": ["白酒"], "ts": "2026-05-01T00:00:00Z"},
            ])
            _write_jsonl(root / "corrections.jsonl", [
                {"correction": "数据安全别只看当日涨幅", "themes": ["数据安全"], "principle": "看出清周期", "ts": "2026-07-02T00:00:00Z"},
            ])
            _write_jsonl(root / "checkpoints.jsonl", [
                {"id": "c1", "claim": "数据安全Q2收入转正", "category": "拐点", "due": "2026-08-31"},
            ])
            _write_jsonl(root / "verdicts.jsonl", [
                {"id": "c1", "verdict": "hit"},
            ])
            block = memory_block_for_query("数据安全 中期赔率", users_root=root)
            self.assertIn("出清见底", block)
            self.assertIn("看出清周期", block)
            self.assertNotIn("白酒", block)
            # W2：端到端路径上逐条归属+日期也在（同一字串注入复盘 user 消息与 ask 链 M 块）。
            self.assertIn("[M·你的判断 2026-07-01]", block)
            self.assertIn("[M·你的纠偏原则 2026-07-02]", block)

    def test_irrelevant_query_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "judgments.jsonl", [
                {"memo": "白酒需求弱", "themes": ["白酒"], "ts": "2026-05-01T00:00:00Z"},
            ])
            self.assertEqual(memory_block_for_query("光模块 CPO 份额", users_root=root), "")

    def test_recalled_judgment_gets_peer_hit_line_when_category_has_enough(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "judgments.jsonl", [
                {
                    "id": "j-life",
                    "memo": "液冷渗透还在客户验证，不看产能公告",
                    "themes": ["液冷"],
                    "ts": "2026-07-01T00:00:00Z",
                    "category": "生命周期推演",
                    "hitCount": 99,
                    "confidence": "80%",
                },
            ])
            # 类别刚好够 min_n 条终态判定（跟着 PEER_HIT_MIN_N 走，不写死 2026-09-04 前的 2）
            n, hits = PEER_HIT_MIN_N, PEER_HIT_MIN_N - 3
            _write_jsonl(root / "checkpoints.jsonl", [
                {"id": f"c{i}", "claim": f"液冷验证 {i}", "category": "生命周期推演", "due": "2026-06-01"}
                for i in range(n)
            ])
            _write_jsonl(root / "verdicts.jsonl", [
                {"id": f"c{i}", "verdict": "hit" if i < hits else "miss"} for i in range(n)
            ])
            block = memory_block_for_query("液冷渗透率怎么看", users_root=root)
            self.assertIn("客户验证", block)
            self.assertIn(f"同类判断历史 {hits}/{n} 命中（分母=已裁决数）", block)
            self.assertNotIn("99", block)
            self.assertNotIn("80%", block)

    def test_peer_hit_hidden_when_category_below_n(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "judgments.jsonl", [
                {"memo": "数据安全出清见底", "themes": ["数据安全"], "ts": "2026-07-01T00:00:00Z", "category": "拐点"},
            ])
            _write_jsonl(root / "checkpoints.jsonl", [
                {"id": "c1", "claim": "数据安全Q2收入转正", "category": "拐点", "due": "2026-08-31"},
            ])
            _write_jsonl(root / "verdicts.jsonl", [
                {"id": "c1", "verdict": "hit"},
            ])
            block = memory_block_for_query("数据安全 中期赔率", users_root=root)
            self.assertIn("出清见底", block)
            self.assertNotIn("同类判断历史", block)

    def test_peer_hit_hidden_when_no_verdicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "judgments.jsonl", [
                {"memo": "数据安全出清见底", "themes": ["数据安全"], "ts": "2026-07-01T00:00:00Z", "category": "拐点"},
            ])
            block = memory_block_for_query("数据安全 中期赔率", users_root=root)
            self.assertIn("出清见底", block)
            self.assertNotIn("同类判断历史", block)

    def test_calibration_shows_without_judgment_hit_when_corrections_recall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "corrections.jsonl", [
                {"correction": "液冷别只看产能", "themes": ["液冷"], "principle": "先看验证", "ts": "2026-07-02T00:00:00Z"},
            ])
            n = PEER_HIT_MIN_N
            _write_jsonl(root / "checkpoints.jsonl", [
                {"id": f"c{i}", "claim": f"液冷验证 {i}", "category": "生命周期推演", "due": "2026-06-01"}
                for i in range(n)
            ])
            _write_jsonl(root / "verdicts.jsonl", [
                {"id": f"c{i}", "verdict": "hit" if i % 2 == 0 else "miss"} for i in range(n)
            ])
            block = memory_block_for_query("液冷怎么看", users_root=root)
            self.assertIn("[M]", block)
            self.assertIn("先看验证", block)
            self.assertIn("回检校准", block)
            self.assertIn("生命周期推演", block)


if __name__ == "__main__":
    unittest.main()
