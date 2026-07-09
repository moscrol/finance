from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.checkpoint_recall import (
    build_recall_block,
    latest_verdicts,
    recall_block_for_query,
    select_relevant_checkpoints,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")


def _checkpoints() -> list[dict]:
    return [
        {
            "id": "c1",
            "claim": "数据安全板块 Q2 订单同比转正",
            "due": "2026-06-30",
            "category": "拐点",
            "themes": ["数据安全"],
            "ts": "2026-05-01T00:00:00Z",
        },
        {
            "id": "c2",
            "claim": "信创央企采购放量带动指数跑赢",
            "due": "2026-09-30",
            "category": "产能时点",
            "themes": ["信创"],
            "ts": "2026-06-10T00:00:00Z",
        },
        {
            "id": "c3",
            "claim": "数据安全龙头中报扭亏",
            "due": "2026-08-31",
            "category": "业绩兑现",
            "themes": ["数据安全"],
            "stocks": ["三六零"],
            "ts": "2026-06-20T00:00:00Z",
        },
    ]


def _verdicts() -> list[dict]:
    return [
        {"id": "c1", "verdict": "unverifiable", "reason": "数据缺失", "checked_at": "2026-06-30T10:00:00Z"},
        {"id": "c1", "verdict": "hit", "reason": "订单同比 +12%", "checked_at": "2026-07-05T10:00:00Z"},
    ]


class SelectRelevantCheckpointsTests(unittest.TestCase):
    def test_theme_tag_hit(self) -> None:
        hit = select_relevant_checkpoints(_checkpoints(), "数据安全 现在怎么看")
        self.assertEqual({r["id"] for r in hit}, {"c1", "c3"})

    def test_entity_param_hit(self) -> None:
        hit = select_relevant_checkpoints(_checkpoints(), "这只票的旧判断", entity="三六零")
        self.assertEqual([r["id"] for r in hit], ["c3"])

    def test_no_hit_returns_empty(self) -> None:
        self.assertEqual(select_relevant_checkpoints(_checkpoints(), "光模块 CPO"), [])


class LatestVerdictsTests(unittest.TestCase):
    def test_last_write_wins(self) -> None:
        by_id = latest_verdicts(_verdicts())
        self.assertEqual(by_id["c1"]["verdict"], "hit")


class BuildRecallBlockTests(unittest.TestCase):
    def test_empty_matched_returns_empty(self) -> None:
        self.assertEqual(build_recall_block([], {}), "")

    def test_renders_verdict_and_statuses(self) -> None:
        cks = _checkpoints()
        block = build_recall_block(
            cks,
            latest_verdicts(_verdicts()),
            today="2026-07-09",
            ledger=("2026-06-20", "2026-07-05"),
        )
        self.assertIn("[V]", block)
        self.assertIn("命中 ✓", block)  # c1 terminal hit
        self.assertIn("订单同比 +12%", block)  # verdict reason surfaced
        self.assertIn("跟踪中", block)  # c2/c3 未到期无终态裁决
        self.assertIn("最新登记 2026-06-20", block)
        self.assertIn("最近回检 2026-07-05", block)
        self.assertIn("使用要求", block)

    def test_due_passed_without_verdict_marks_pending(self) -> None:
        ck = {"id": "x1", "claim": "老判断", "due": "2026-01-01", "category": "拐点", "themes": ["数据安全"]}
        block = build_recall_block([ck], {}, today="2026-07-09")
        self.assertIn("到期待判", block)

    def test_unverifiable_not_treated_as_terminal(self) -> None:
        ck = {"id": "c1", "claim": "旧判断", "due": "2026-06-30", "themes": ["数据安全"]}
        block = build_recall_block(
            [ck],
            {"c1": {"id": "c1", "verdict": "unverifiable", "reason": "数据缺失"}},
            today="2026-07-09",
        )
        self.assertIn("暂无法判定", block)
        self.assertNotIn("命中 ✓", block)

    def test_freshness_stale_declared(self) -> None:
        ck = _checkpoints()[0]
        block = build_recall_block([ck], {}, today="2026-07-09", data_asof="2026-07-01")
        self.assertIn("⚠数据新鲜度", block)
        self.assertIn("落后今日 8 天", block)

    def test_freshness_fresh(self) -> None:
        ck = _checkpoints()[0]
        block = build_recall_block([ck], {}, today="2026-07-09", data_asof="2026-07-08")
        self.assertIn("视为新鲜", block)
        self.assertNotIn("⚠数据新鲜度", block)

    def test_freshness_missing_db_declared(self) -> None:
        ck = _checkpoints()[0]
        block = build_recall_block([ck], {}, today="2026-07-09", data_asof=None)
        self.assertIn("未做增量核对", block)


class RecallBlockForQueryTests(unittest.TestCase):
    def test_missing_files_return_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(recall_block_for_query("数据安全怎么看", users_root=tmp), "")

    def test_end_to_end_with_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "checkpoints.jsonl", _checkpoints())
            _write_jsonl(root / "verdicts.jsonl", _verdicts())
            block = recall_block_for_query(
                "数据安全 之前的判断验证得怎么样",
                users_root=root,
                today="2026-07-09",
            )
            self.assertIn("Q2 订单同比转正", block)
            self.assertIn("命中 ✓", block)
            self.assertNotIn("信创", block)  # irrelevant checkpoint not recalled

    def test_irrelevant_query_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "checkpoints.jsonl", _checkpoints())
            self.assertEqual(recall_block_for_query("光模块 CPO 份额", users_root=root), "")


if __name__ == "__main__":
    unittest.main()
