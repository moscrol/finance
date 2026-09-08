from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.user_memory import (
    PEER_HIT_MIN_N,
    build_memory_block,
    memory_block_for_query,
    peer_hit_line,
    select_relevant,
)
from intelligence.services.checkpoints import CategoryStat


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
        self.assertIn("核心判断[数据安全]", block)
        self.assertIn("纠偏原则：时间尺度要对齐", block)
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
        self.assertIn("纠偏原则：应该看板块容量", block)


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
