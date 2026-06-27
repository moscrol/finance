import unittest

from intelligence.services.research_queue import build_research_queue


def row(
    query: str,
    priority: float,
    stage: str,
    status: str,
    layers: list[str] | None = None,
    missing: list[str] | None = None,
    gaps: list[str] | None = None,
    stocks: list[str] | None = None,
) -> dict:
    return {
        "query": query,
        "priority_score": priority,
        "strong_stocks": stocks or ["示例股份"],
        "data_gaps": gaps or [],
        "logic_lifecycle": {"生命周期阶段": stage, "阶段变化": "测试变化", "变化原因": "测试原因"},
        "research_judgment": {
            "证据状态": status,
            "已有证据层": layers or [],
            "缺失证据层": missing or [],
            "建议动作": "测试建议",
        },
    }


class ResearchQueueTest(unittest.TestCase):
    def test_new_or_wakeup_without_l1_l2_becomes_ima_task(self):
        decision = {
            "old_logic_wakeup": [
                row(
                    "电子化学品",
                    154.08,
                    "旧逻辑唤醒",
                    "盘面触发待解释",
                    layers=["L0 图谱登记", "L4 盘面验证"],
                    missing=["L2 基线", "L3 官方验证"],
                )
            ],
            "new_logic_candidate": [],
            "data_gap": [],
            "noise_or_unconfirmed": [],
        }

        queue = build_research_queue(decision)

        self.assertEqual(queue["summary"]["today_do_ima"], 1)
        item = queue["today_do_ima"][0]
        self.assertEqual(item["目标"], "电子化学品")
        self.assertEqual(item["动作"], "今日该做 IMA")
        self.assertIn("缺 L1/L2", item["理由"])

    def test_l2_or_candidate_fact_missing_l3_becomes_official_evidence_task(self):
        decision = {
            "old_logic_wakeup": [
                row(
                    "液冷服务器",
                    88,
                    "升温验证",
                    "能力栈候选",
                    layers=["L2 官方基线", "L4 盘面验证"],
                    missing=["L3 官方验证"],
                )
            ],
            "new_logic_candidate": [],
            "data_gap": [],
            "noise_or_unconfirmed": [],
        }

        queue = build_research_queue(decision)

        self.assertEqual(queue["summary"]["today_find_official_evidence"], 1)
        item = queue["today_find_official_evidence"][0]
        self.assertEqual(item["目标"], "液冷服务器")
        self.assertEqual(item["动作"], "今日该找公告/调研/订单")
        self.assertIn("缺 L3 官方验证", item["理由"])

    def test_old_l1_material_missing_l2_l3_prefers_official_evidence_not_duplicate_ima(self):
        decision = {
            "old_logic_wakeup": [
                row(
                    "光刻胶",
                    184.57,
                    "升温验证",
                    "旧逻辑待验证",
                    layers=["L0 图谱登记", "L1 叙事线索", "L4 盘面验证"],
                    missing=["L2 基线", "L3 官方验证"],
                )
            ],
            "new_logic_candidate": [],
            "data_gap": [],
            "noise_or_unconfirmed": [],
        }

        queue = build_research_queue(decision)

        self.assertEqual(queue["summary"]["today_do_ima"], 0)
        self.assertEqual(queue["summary"]["today_find_official_evidence"], 1)
        item = queue["today_find_official_evidence"][0]
        self.assertEqual(item["目标"], "光刻胶")
        self.assertIn("已有 L1", item["理由"])

    def test_l2_l3_without_l4_becomes_wait_market_validation_task(self):
        decision = {
            "old_logic_wakeup": [
                row(
                    "先进封装",
                    91.36,
                    "旧逻辑唤醒",
                    "重点验证",
                    layers=["L2 官方基线", "L3 官方验证"],
                    missing=["L4 盘面验证"],
                )
            ],
            "new_logic_candidate": [],
            "data_gap": [],
            "noise_or_unconfirmed": [],
        }

        queue = build_research_queue(decision)

        self.assertEqual(queue["summary"]["today_wait_market_validation"], 1)
        item = queue["today_wait_market_validation"][0]
        self.assertEqual(item["目标"], "先进封装")
        self.assertEqual(item["动作"], "今日等盘面验证")
        self.assertIn("缺 L4", item["理由"])

    def test_declining_or_diverging_lifecycle_becomes_downgrade_task(self):
        decision = {
            "old_logic_wakeup": [
                row(
                    "存储芯片",
                    55.2,
                    "衰退观察",
                    "旧逻辑待验证",
                    layers=["L1 叙事线索", "L4 盘面验证"],
                    missing=["L2 基线", "L3 官方验证"],
                )
            ],
            "new_logic_candidate": [],
            "data_gap": [],
            "noise_or_unconfirmed": [],
        }

        queue = build_research_queue(decision)

        self.assertEqual(queue["summary"]["today_downgrade_or_watch"], 1)
        item = queue["today_downgrade_or_watch"][0]
        self.assertEqual(item["目标"], "存储芯片")
        self.assertEqual(item["动作"], "今日降级/观察")
        self.assertIn("生命周期转弱", item["理由"])

    def test_data_gap_rows_do_not_enter_research_task_queue(self):
        decision = {
            "old_logic_wakeup": [],
            "new_logic_candidate": [],
            "data_gap": [
                row(
                    "金属铜",
                    141.71,
                    "新出现",
                    "盘面触发待解释",
                    layers=["L4 盘面验证"],
                    missing=["L2 基线", "L3 官方验证"],
                    gaps=["missing_concept", "missing_evidence"],
                )
            ],
            "noise_or_unconfirmed": [],
        }

        queue = build_research_queue(decision)

        self.assertEqual(queue["summary"]["total"], 0)
        self.assertEqual(queue["skipped"]["data_gap_or_unconfirmed"][0]["目标"], "金属铜")


if __name__ == "__main__":
    unittest.main()
