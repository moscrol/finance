from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.research_queue import (
    SCHEMA_VERSION,
    build_research_queue,
    extract_queue,
    find_research_queue_path,
    load_research_queue,
    sibling_queue_path,
    wrap_research_queue_artifact,
    write_research_queue_outputs,
)


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


class ResearchQueueArtifactTest(unittest.TestCase):
    def test_wrap_and_extract_round_trip(self):
        queue = build_research_queue(
            {
                "old_logic_wakeup": [
                    row("电子化学品", 154.08, "旧逻辑唤醒", "盘面触发待解释", layers=["L0 图谱登记"], missing=["L2 基线", "L3 官方验证"])
                ],
                "new_logic_candidate": [],
                "data_gap": [],
                "noise_or_unconfirmed": [],
            }
        )
        artifact = wrap_research_queue_artifact(queue, date="2026-08-13", generated_at="2026-08-13T21:00:00+08:00")
        self.assertEqual(artifact["schema_version"], SCHEMA_VERSION)
        self.assertEqual(artifact["date"], "2026-08-13")
        self.assertIn("IMA 1", artifact["human_summary"])
        self.assertEqual(extract_queue(artifact)["today_do_ima"][0]["目标"], "电子化学品")
        self.assertEqual(extract_queue(queue)["today_do_ima"][0]["目标"], "电子化学品")

    def test_prefers_queue_file_over_nested_daily_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports = Path(tmp)
            (exports / "2026-08-13-daily-agent.json").write_text(
                json.dumps({"date": "2026-08-13", "research_queue": {"today_do_ima": [{"目标": "旧日报"}]}}),
                encoding="utf-8",
            )
            (exports / "2026-08-13-research-queue.json").write_text(
                json.dumps(
                    wrap_research_queue_artifact(
                        {"today_do_ima": [{"目标": "队列文件"}], "summary": {"today_do_ima": 1, "total": 1}},
                        date="2026-08-13",
                    )
                ),
                encoding="utf-8",
            )
            path, payload = load_research_queue(exports, date="2026-08-13")
            self.assertTrue(str(path).endswith("2026-08-13-research-queue.json"))
            self.assertEqual(extract_queue(payload)["today_do_ima"][0]["目标"], "队列文件")

    def test_falls_back_to_daily_agent_when_queue_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports = Path(tmp)
            (exports / "2026-08-07-daily-agent.json").write_text(
                json.dumps({"date": "2026-08-07", "research_queue": {"today_find_official_evidence": [{"目标": "液冷"}]}}),
                encoding="utf-8",
            )
            path, payload = load_research_queue(exports, date="2026-08-07")
            self.assertTrue(str(path).endswith("2026-08-07-daily-agent.json"))
            self.assertEqual(extract_queue(payload)["today_find_official_evidence"][0]["目标"], "液冷")

    def test_latest_prefers_newer_queue_over_older_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports = Path(tmp)
            (exports / "2026-08-07-daily-agent.json").write_text("{}", encoding="utf-8")
            (exports / "2026-08-13-research-queue.json").write_text(
                json.dumps({"date": "2026-08-13", "research_queue": {"today_do_ima": []}}),
                encoding="utf-8",
            )
            path = find_research_queue_path(exports)
            self.assertEqual(path.name, "2026-08-13-research-queue.json")

    def test_write_outputs_does_not_need_fidelity_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = {"today_do_ima": [{"目标": "CXO", "优先级": 1}], "summary": {"today_do_ima": 1, "total": 1}}
            written = write_research_queue_outputs(
                {"date": "2026-08-13", "generated_at": "now", "research_queue": queue},
                json_path=root / "2026-08-13-research-queue.json",
                md_path=root / "2026-08-13-research-queue.md",
                html_path=root / "2026-08-13-research-queue.html",
            )
            payload = json.loads(written["json"].read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
            self.assertIn("CXO", written["md"].read_text(encoding="utf-8"))
            self.assertIn("研究队列", written["html"].read_text(encoding="utf-8"))

    def test_sibling_queue_path_maps_dated_and_bare_agent_names(self):
        self.assertEqual(
            sibling_queue_path(Path("/tmp/2026-08-13-daily-agent.json")).name,
            "2026-08-13-research-queue.json",
        )
        self.assertEqual(sibling_queue_path(Path("/tmp/daily-agent.html")).name, "research-queue.html")
        self.assertEqual(sibling_queue_path(Path("/tmp/tampered.json")).name, "tampered-research-queue.json")


if __name__ == "__main__":
    unittest.main()
