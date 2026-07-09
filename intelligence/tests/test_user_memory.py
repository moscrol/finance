from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.user_memory import (
    build_memory_block,
    memory_block_for_query,
    select_relevant,
)


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

    def test_correction_falls_back_to_correction_text(self) -> None:
        block = build_memory_block([], [{"correction": "应该看板块容量", "ts": "2026-07-02T00:00:00Z"}])
        self.assertIn("纠偏原则：应该看板块容量", block)


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


if __name__ == "__main__":
    unittest.main()
