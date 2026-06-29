from __future__ import annotations

import unittest

from intelligence.services.kb_ingest_queue import build_kb_ingest_queue


class KnowledgeBaseIngestQueueTest(unittest.TestCase):
    def test_builds_human_review_tasks_from_research_queue_and_data_gaps(self):
        research_queue = {
            "today_do_ima": [
                {
                    "目标": "电子化学品",
                    "动作": "今日该做 IMA",
                    "理由": "盘面触发但缺 L1/L2 叙事或基线材料。",
                    "优先级": 154.08,
                    "缺失证据层": ["L1 叙事线索", "L2 基线"],
                    "强势股": ["示例股份"],
                    "建议动作": "补 IMA/题材地图。",
                }
            ],
            "today_find_official_evidence": [
                {
                    "目标": "液冷服务器",
                    "动作": "今日该找公告/调研/订单",
                    "理由": "已有 L2，但缺 L3 官方验证。",
                    "优先级": 88,
                    "缺失证据层": ["L3 官方验证"],
                    "强势股": ["强瑞技术"],
                    "建议动作": "查公告、互动易、调研纪要。",
                }
            ],
            "today_wait_market_validation": [
                {
                    "目标": "先进封装",
                    "动作": "今日等盘面验证",
                    "理由": "已有 L2/L3，但缺 L4 盘面验证。",
                    "优先级": 77,
                    "缺失证据层": ["L4 盘面验证"],
                }
            ],
            "today_downgrade_or_watch": [],
            "skipped": {
                "data_gap_or_unconfirmed": [
                    {
                        "目标": "金属铜",
                        "动作": "暂不进入研究任务",
                        "理由": "仍有概念、公司、证据、来源或占位缺口。",
                        "优先级": 141.71,
                        "缺失证据层": ["L2 基线", "L3 官方验证"],
                        "数据缺口": ["missing_concept", "missing_evidence", "missing_source_trace"],
                    }
                ],
                "no_clear_action": [],
            },
        }

        queue = build_kb_ingest_queue(
            research_queue,
            market_date="2026-06-11",
            source_artifact="market_feature_store/exports/2026-06-11-daily-agent.json",
        )

        self.assertEqual(queue["schema_version"], "1.0")
        self.assertEqual(queue["source_repo"], "finance-workspace-private")
        self.assertEqual(queue["market_date"], "2026-06-11")
        self.assertEqual(queue["summary"]["total_tasks"], 5)
        self.assertEqual(queue["summary"]["by_task_type"]["concept_ingest"], 2)
        self.assertEqual(queue["summary"]["by_task_type"]["disclosure"], 2)
        self.assertEqual(queue["summary"]["by_task_type"]["source_trace"], 1)

        tasks = queue["tasks"]
        self.assertEqual([task["theme"] for task in tasks], ["电子化学品", "液冷服务器", "金属铜", "金属铜", "金属铜"])
        self.assertEqual([task["task_type"] for task in tasks], ["concept_ingest", "disclosure", "concept_ingest", "disclosure", "source_trace"])
        self.assertTrue(all(task["requires_human_review"] is True for task in tasks))
        self.assertTrue(all(task["auto_apply"] is False for task in tasks))
        self.assertTrue(all(task["status"] == "pending" for task in tasks))
        self.assertEqual(tasks[0]["task_id"], "2026-06-11-concept_ingest-dian-zi-hua-xue-pin-001")
        self.assertIn("检索增强生成", queue["glossary"]["RAG"])

    def test_wait_market_validation_does_not_create_kb_write_task(self):
        queue = build_kb_ingest_queue(
            {
                "today_do_ima": [],
                "today_find_official_evidence": [],
                "today_wait_market_validation": [{"目标": "先进封装", "优先级": 77}],
                "today_downgrade_or_watch": [],
                "skipped": {"data_gap_or_unconfirmed": [], "no_clear_action": []},
            },
            market_date="2026-06-11",
            source_artifact="daily-agent.json",
        )

        self.assertEqual(queue["tasks"], [])
        self.assertEqual(queue["summary"]["total_tasks"], 0)


if __name__ == "__main__":
    unittest.main()
