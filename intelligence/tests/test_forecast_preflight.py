from __future__ import annotations

import unittest

from intelligence.services.forecast_preflight import (
    STATUS_MISSING_DAILY_AGENT,
    STATUS_NEEDS_DEEPDIVE,
    STATUS_READY,
    build_forecast_preflight,
)


class ForecastPreflightTests(unittest.TestCase):
    def test_blocks_formal_forecast_when_ima_or_official_evidence_tasks_exist(self) -> None:
        report = {
            "research_queue": {
                "today_do_ima": [
                    {
                        "目标": "IDC",
                        "动作": "今日该做 IMA",
                        "理由": "PR188 真增量但缺 L1/L2 叙事或基线材料。",
                        "优先级": 194.0,
                        "生命周期阶段": "旧逻辑唤醒",
                        "缺失证据层": ["L2 基线", "L3 官方验证"],
                        "强势股": ["润泽科技", "奥飞数据"],
                    }
                ],
                "today_find_official_evidence": [
                    {
                        "目标": "燃机",
                        "动作": "今日该找公告/调研/订单",
                        "理由": "已有 L2 或 L3 候选，但缺 L3 官方验证。",
                        "优先级": 188.0,
                        "生命周期阶段": "升温验证",
                        "缺失证据层": ["L3 官方验证"],
                        "强势股": ["应流股份"],
                    }
                ],
                "today_wait_market_validation": [],
                "today_downgrade_or_watch": [],
                "summary": {"today_do_ima": 1, "today_find_official_evidence": 1},
            }
        }

        result = build_forecast_preflight(report, source_artifact="2026-07-01-daily-agent.json")

        self.assertEqual(result["status"], STATUS_NEEDS_DEEPDIVE)
        self.assertFalse(result["can_generate_formal"])
        self.assertTrue(result["can_generate_draft"])
        self.assertEqual(len(result["blocking_items"]), 2)
        self.assertEqual(result["blocking_items"][0]["theme"], "IDC")
        self.assertEqual(result["blocking_items"][0]["required_action"], "先补 IMA / DeepDive / 题材地图")
        self.assertEqual(result["blocking_items"][1]["required_action"], "先补公告 / 调研 / 订单 / 客户验证")
        self.assertIn("正式复盘生成前", result["human_summary"])
        self.assertIn("IDC", result["prompt_block"])
        self.assertIn("燃机", result["prompt_block"])
        self.assertIn("2026-07-01-daily-agent.json", result["prompt_block"])

    def test_ready_when_only_wait_market_or_downgrade_tasks_exist(self) -> None:
        queue = {
            "today_do_ima": [],
            "today_find_official_evidence": [],
            "today_wait_market_validation": [{"目标": "先进封装", "优先级": 91.0}],
            "today_downgrade_or_watch": [{"目标": "液冷", "优先级": 55.0}],
            "summary": {"today_wait_market_validation": 1, "today_downgrade_or_watch": 1},
        }

        result = build_forecast_preflight(queue)

        self.assertEqual(result["status"], STATUS_READY)
        self.assertTrue(result["can_generate_formal"])
        self.assertEqual(result["blocking_items"], [])
        self.assertIn("可以生成正式复盘", result["human_summary"])

    def test_missing_daily_agent_is_separate_from_no_deepdive_gap(self) -> None:
        result = build_forecast_preflight({})

        self.assertEqual(result["status"], STATUS_MISSING_DAILY_AGENT)
        self.assertFalse(result["can_generate_formal"])
        self.assertTrue(result["can_generate_draft"])
        self.assertIn("未读取到研究队列", result["human_summary"])
        self.assertIn("先生成或同步 research-queue", result["next_steps"][0])

    def test_accepts_wrapped_research_queue_artifact(self) -> None:
        artifact = {
            "schema_version": "research-queue/v1",
            "date": "2026-08-13",
            "research_queue": {
                "today_do_ima": [{"目标": "CXO", "优先级": 120, "缺失证据层": ["L1 叙事线索"]}],
                "today_find_official_evidence": [],
                "today_wait_market_validation": [],
                "today_downgrade_or_watch": [],
            },
        }
        result = build_forecast_preflight(
            artifact,
            source_artifact="2026-08-13-research-queue.json",
        )
        self.assertEqual(result["status"], STATUS_NEEDS_DEEPDIVE)
        self.assertEqual(result["blocking_items"][0]["theme"], "CXO")
        self.assertIn("2026-08-13-research-queue.json", result["prompt_block"])


if __name__ == "__main__":
    unittest.main()
