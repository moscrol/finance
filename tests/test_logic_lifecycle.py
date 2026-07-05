from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.logic_lifecycle import (
    build_lifecycle_snapshot,
    register_lifecycle_checkpoints,
)


def row(
    query: str,
    date: str,
    priority: float,
    stocks: list[str] | None = None,
    triggers: list[str] | None = None,
    judgment: dict | None = None,
    semantic_hits: bool = False,
) -> dict:
    return {
        "query": query,
        "date": date,
        "priority_score": priority,
        "trigger_types": triggers or [],
        "strong_stocks": stocks or [],
        "research_judgment": judgment or {},
        "semantic_hits": [{"title": "旧材料"}] if semantic_hits else [],
    }


class LogicLifecycleTest(unittest.TestCase):
    def test_first_appearance_is_new(self):
        current = row("液冷服务器", "2026-06-11", 88, ["强瑞技术"], ["double_red"])

        snapshot = build_lifecycle_snapshot(current, [])

        self.assertEqual(snapshot["生命周期阶段"], "新出现")
        self.assertEqual(snapshot["连续出现天数"], 1)
        self.assertIn("过去窗口未出现", snapshot["变化原因"])
        self.assertIn("先确认题材边界", snapshot["下一步"])

    def test_first_market_appearance_with_old_material_is_wakeup(self):
        current = row(
            "小金属",
            "2026-06-11",
            163.23,
            ["云南锗业", "阿石创"],
            ["double_red", "limit_heat"],
            judgment={"证据状态": "旧逻辑待验证"},
            semantic_hits=True,
        )

        snapshot = build_lifecycle_snapshot(current, [])

        self.assertEqual(snapshot["生命周期阶段"], "旧逻辑唤醒")
        self.assertEqual(snapshot["阶段变化"], "旧材料唤醒")
        self.assertIn("旧逻辑重新触发", snapshot["变化原因"])

    def test_repeated_old_material_with_rising_market_becomes_warming(self):
        current = row(
            "光刻胶",
            "2026-06-11",
            184.57,
            ["华特气体", "兴福电子", "雅克科技", "南大光电"],
            ["double_red", "limit_heat", "new_high_cluster"],
            judgment={"证据状态": "旧逻辑待验证"},
            semantic_hits=True,
        )
        history = [
            row("光刻胶", "2026-06-09", 168.95, ["华特气体"], ["double_red"], semantic_hits=True),
            row("光刻胶", "2026-06-10", 180.09, ["华特气体", "兴福电子"], ["double_red", "limit_heat"], semantic_hits=True),
        ]

        snapshot = build_lifecycle_snapshot(current, history)

        self.assertEqual(snapshot["生命周期阶段"], "升温验证")
        self.assertEqual(snapshot["阶段变化"], "连续升温")
        self.assertEqual(snapshot["连续出现天数"], 3)
        self.assertGreater(snapshot["priority变化"], 0)
        self.assertGreater(snapshot["强势股变化"], 0)
        self.assertIn("连续 3 日出现", snapshot["变化原因"])

    def test_repeated_old_material_without_previous_consecutive_days_is_wakeup(self):
        current = row(
            "小金属",
            "2026-06-11",
            163.23,
            ["云南锗业", "阿石创"],
            ["double_red", "limit_heat"],
            judgment={"证据状态": "旧逻辑待验证"},
            semantic_hits=True,
        )
        history = [row("小金属", "2026-06-05", 90.0, ["云南锗业"], ["double_red"], semantic_hits=True)]

        snapshot = build_lifecycle_snapshot(current, history)

        self.assertEqual(snapshot["生命周期阶段"], "旧逻辑唤醒")
        self.assertEqual(snapshot["阶段变化"], "沉睡后唤醒")
        self.assertIn("旧材料命中", snapshot["变化原因"])

    def test_falling_priority_and_stock_count_becomes_declining_watch(self):
        current = row(
            "先进封装",
            "2026-06-11",
            91.36,
            ["中巨芯"],
            ["double_red"],
            judgment={"证据状态": "盘面触发待解释"},
        )
        history = [
            row("先进封装", "2026-06-09", 140.0, ["中巨芯", "兴福电子", "雅克科技"], ["double_red", "limit_heat"]),
            row("先进封装", "2026-06-10", 120.0, ["中巨芯", "兴福电子"], ["double_red", "limit_heat"]),
        ]

        snapshot = build_lifecycle_snapshot(current, history)

        self.assertEqual(snapshot["生命周期阶段"], "衰退观察")
        self.assertEqual(snapshot["阶段变化"], "热度衰退")
        self.assertLess(snapshot["priority变化"], 0)
        self.assertLess(snapshot["强势股变化"], 0)
        self.assertIn("热度下降", snapshot["下一步"])


class RegisterLifecycleCheckpointsTest(unittest.TestCase):
    def _decision(self) -> dict:
        warming = row(
            "液冷服务器",
            "2026-06-11",
            95,
            ["强瑞技术"],
            ["double_red"],
        )
        warming["logic_lifecycle"] = {"生命周期阶段": "升温验证"}
        new = row("新出现题材", "2026-06-11", 60)
        new["logic_lifecycle"] = {"生命周期阶段": "新出现"}
        return {"old_logic_wakeup": [warming], "new_logic_candidate": [new], "data_gap": []}

    def test_registers_only_forward_looking_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "checkpoints.jsonl"

            added = register_lifecycle_checkpoints(
                self._decision(), date="2026-06-11", checkpoints_path=cpath
            )

            self.assertEqual(len(added), 1)
            record = added[0]
            self.assertIn("液冷服务器", record["claim"])
            self.assertEqual(record["due"], "2026-06-16")
            self.assertEqual(record["category"], "生命周期推演")
            self.assertEqual(record["source"], "logic_lifecycle")
            self.assertEqual(record["themes"], ["液冷服务器"])
            self.assertEqual(record["metric"]["type"], "kb_evidence")
            lines = [json.loads(line) for line in cpath.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lines), 1)

    def test_idempotent_same_claim_due_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "checkpoints.jsonl"
            decision = self._decision()

            first = register_lifecycle_checkpoints(decision, date="2026-06-11", checkpoints_path=cpath)
            second = register_lifecycle_checkpoints(decision, date="2026-06-11", checkpoints_path=cpath)

            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            lines = cpath.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
