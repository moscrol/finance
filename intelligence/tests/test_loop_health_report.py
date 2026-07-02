from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from intelligence import userspace

_SPEC = importlib.util.spec_from_file_location(
    "loop_health_report",
    Path(__file__).resolve().parents[2] / "scripts" / "loop_health_report.py",
)
loop_health_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(loop_health_report)


class LoopHealthReportTests(unittest.TestCase):
    def test_build_report_aggregates_all_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            users = Path(tmp) / "users"
            user_root = users / "tester"
            user_root.mkdir(parents=True)
            (user_root / "answer_scores.jsonl").write_text(
                json.dumps(
                    {
                        "ts": "2026-07-01T10:00:00+00:00",
                        "question": "q",
                        "total_score": 40,
                        "max_score": 100,
                        "grade": "F",
                        "failures": ["证据分层不足：缺少 L1-L4"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (user_root / "experience_cards.jsonl").write_text(
                json.dumps(
                    {"ts": "2026-07-01T10:00:00+00:00", "question": "q", "source": "auto-score", "promotion": "candidate"},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            kb = Path(tmp) / "kb"
            (kb / "wiki").mkdir(parents=True)
            (kb / "wiki" / "log.md").write_text(
                "### #2177 | 2026-07-01 | concept-ingest | 某研报入库\n- key\n",
                encoding="utf-8",
            )
            queue_day = kb / "wiki" / "raw" / "cross-repo-ingest-queue" / "2026-07-01"
            queue_day.mkdir(parents=True)
            (queue_day / "pack.json").write_text("{}", encoding="utf-8")

            with mock.patch.dict("os.environ", {userspace.ENV_USERS_DIR: str(users)}):
                report = loop_health_report.build_report(
                    days=7, user="tester", kb_root=str(kb), today=date(2026, 7, 2)
                )

        self.assertIn("评分次数：1", report)
        self.assertIn("F×1", report)
        self.assertIn("auto-score×1", report)
        self.assertIn("candidate 待人工复核", report)
        self.assertIn("入库条目：1", report)
        self.assertIn("concept-ingest×1", report)
        self.assertIn("1 个任务包", report)

    def test_build_report_degrades_without_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {userspace.ENV_USERS_DIR: str(Path(tmp) / "users")}):
                report = loop_health_report.build_report(
                    days=7, user="tester", kb_root=str(Path(tmp) / "nope"), today=date(2026, 7, 2)
                )
        self.assertIn("无评分记录", report)
        self.assertIn("未找到知识库仓", report)


if __name__ == "__main__":
    unittest.main()
