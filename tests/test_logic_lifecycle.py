import unittest

from intelligence.services.logic_lifecycle import build_lifecycle_snapshot


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


if __name__ == "__main__":
    unittest.main()
