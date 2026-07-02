from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services import kb_ingest_queue, kb_queue_receipt


def _write_receipt(kb_wiki: Path, market_date: str, tasks: list[dict]) -> None:
    day_dir = kb_wiki / "raw" / "cross-repo-ingest-queue" / market_date
    day_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "1.0",
        "market_date": market_date,
        "generated_at": "2026-07-01T20:00:00+08:00",
        "summary": {},
        "queues": [{"file": "queue.json", "tasks": tasks}],
    }
    (day_dir / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")


class KbQueueReceiptTests(unittest.TestCase):
    def test_resolved_themes_and_render_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = Path(tmp) / "wiki"
            _write_receipt(
                kb_wiki,
                "2026-06-30",
                [
                    {"task_id": "a", "task_type": "concept_ingest", "theme": "液冷", "status": "ingested", "status_note": "wiki/log.md #2170"},
                    {"task_id": "b", "task_type": "disclosure", "theme": "玻璃基板", "status": "received"},
                ],
            )

            self.assertEqual(kb_queue_receipt.resolved_themes(kb_wiki), {"液冷"})
            status = kb_queue_receipt.render_status(kb_wiki)
            self.assertIn("ingested×1", status)
            self.assertIn("received×1", status)
            self.assertIn("待处理", status)
            self.assertIn("玻璃基板", status)
            self.assertIn("已补齐", status)
            self.assertIn("wiki/log.md #2170", status)

    def test_render_status_without_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status = kb_queue_receipt.render_status(Path(tmp) / "wiki")
        self.assertIn("未找到回执", status)

    def test_build_queue_skips_resolved_themes(self) -> None:
        research_queue = {
            "today_do_ima": [
                {"目标": "液冷", "优先级": 1, "理由": "缺 L1"},
                {"目标": "玻璃基板", "优先级": 2, "理由": "缺 L2"},
            ]
        }
        queue = kb_ingest_queue.build_kb_ingest_queue(
            research_queue,
            market_date="2026-07-01",
            source_artifact="exports/2026-07-01-daily-agent.json",
            resolved_themes={"液冷"},
        )
        themes = [t["theme"] for t in queue["tasks"]]
        self.assertEqual(themes, ["玻璃基板"])
        self.assertEqual(queue["summary"]["resolved_themes_skipped"], ["液冷"])
        self.assertEqual(queue["summary"]["total_tasks"], 1)


if __name__ == "__main__":
    unittest.main()
