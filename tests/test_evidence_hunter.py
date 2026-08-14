from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.build_evidence_hunter_report import (
    build_report,
    classify_row_for_task,
    render_markdown,
    tasks_from_daily_report,
)


class EvidenceHunterTest(unittest.TestCase):
    def _task(self, **overrides) -> dict:
        task = {
            "task_id": "t1",
            "source": "test",
            "trade_date": "2026-06-26",
            "theme": "液冷服务器",
            "concept": "液冷服务器",
            "claim": "找 L3 官方验证",
            "entities": ["英维克"],
            "target_layer": "L3_current_official_catalyst",
            "target_evidence_types": ["announcement", "order", "capacity"],
            "query_terms": ["液冷服务器", "英维克"],
            "priority": "P0",
            "lookback_days": 14,
        }
        task.update(overrides)
        return task

    def _row(self, **overrides) -> dict:
        row = {
            "id": "1",
            "source": "财联社",
            "title": "英维克液冷服务器订单增长",
            "content": "英维克液冷服务器相关订单增长，客户验证推进。",
            "url": "",
            "ts": 0,
            "day": "2026-06-26",
            "effective_ts": 0,
            "score": 0.8,
            "admitted": 1,
            "dup_group": None,
            "event_id": None,
        }
        row.update(overrides)
        return row

    def _db(self, rows: list[dict]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "finhot.db"
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE items ("
            "id TEXT PRIMARY KEY, source TEXT, title TEXT, content TEXT, url TEXT, "
            "ts INTEGER, day TEXT, effective_ts INTEGER, score REAL, admitted INTEGER, dup_group TEXT, event_id TEXT)"
        )
        conn.executemany(
            "INSERT INTO items VALUES (:id, :source, :title, :content, :url, :ts, :day, :effective_ts, :score, :admitted, :dup_group, :event_id)",
            rows,
        )
        conn.commit()
        conn.close()
        return path

    def test_daily_decision_generates_find_official_task(self) -> None:
        report = {
            "date": "2026-06-26",
            "decision": {
                "old_logic_wakeup": [
                    {
                        "query": "液冷服务器",
                        "priority_score": 130,
                        "strong_stocks": [{"stock_name": "英维克", "stock_ts_code": "002837.SZ"}],
                        "logic_lifecycle": {"生命周期阶段": "升温验证"},
                        "research_judgment": {
                            "证据状态": "能力栈候选",
                            "已有证据层": ["L2 官方基线"],
                            "缺失证据层": ["L3 官方验证"],
                        },
                    }
                ],
                "new_logic_candidate": [],
                "data_gap": [],
                "noise_or_unconfirmed": [],
            },
        }

        tasks = tasks_from_daily_report(report, 14)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["theme"], "液冷服务器")
        self.assertEqual(tasks[0]["entities"], ["英维克"])
        self.assertEqual(tasks[0]["target_layer"], "L3_current_official_catalyst")
        self.assertEqual(tasks[0]["priority"], "P0")

    def test_finance_alert_order_is_l3_candidate(self) -> None:
        candidate, reject = classify_row_for_task(self._task(), self._row())

        self.assertIsNone(reject)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["evidence_layer"], "L3_candidate")
        self.assertEqual(candidate["evidence_type"], "order")
        self.assertIn("需继续追官方原文", candidate["reason"])

    def test_official_announcement_is_current_catalyst(self) -> None:
        candidate, reject = classify_row_for_task(
            self._task(),
            self._row(source="巨潮公告", url="https://www.cninfo.com.cn/new/disclosure", title="英维克液冷服务器订单公告"),
        )

        self.assertIsNone(reject)
        self.assertEqual(candidate["evidence_layer"], "L3_current_official_catalyst")
        self.assertEqual(candidate["source_tier"], "official")

    def test_annual_report_hard_fact_is_historical_fact(self) -> None:
        candidate, reject = classify_row_for_task(
            self._task(),
            self._row(source="巨潮公告", title="英维克2025年年度报告", content="公司液冷服务器产品已实现批量出货并形成收入。"),
        )

        self.assertIsNone(reject)
        self.assertEqual(candidate["evidence_layer"], "L3_historical_official_fact")

    def test_annual_report_baseline_only_stays_l2(self) -> None:
        candidate, reject = classify_row_for_task(
            self._task(),
            self._row(source="巨潮公告", title="英维克2025年年度报告", content="公司液冷服务器产品应用于数据中心散热业务。"),
        )

        self.assertIsNone(reject)
        self.assertEqual(candidate["evidence_layer"], "L2_official_baseline")
        self.assertEqual(candidate["evidence_type"], "baseline")

    def test_entity_mismatch_is_rejected(self) -> None:
        candidate, reject = classify_row_for_task(
            self._task(),
            self._row(title="高澜股份液冷服务器订单增长", content="高澜股份液冷服务器相关订单增长。"),
        )

        self.assertIsNone(candidate)
        self.assertEqual(reject["reject_reason"], "entity_mismatch")

    def test_build_report_searches_sqlite_and_renders(self) -> None:
        db = self._db([
            self._row(id="1"),
            self._row(id="2", source="巨潮公告", title="英维克液冷服务器订单公告", url="https://www.cninfo.com.cn/new/disclosure"),
            self._row(id="3", title="高澜股份液冷服务器订单增长", content="高澜股份液冷服务器订单增长。"),
        ])

        report = build_report([self._task()], db, "2026-06-26")
        md = render_markdown(report)

        self.assertEqual(report["summary"]["task_count"], 1)
        self.assertEqual(report["tasks"][0]["status"], "official_candidate_found")
        self.assertGreaterEqual(report["summary"]["matched_count"], 2)
        self.assertGreaterEqual(report["summary"]["rejected_count"], 1)
        self.assertIn("FinHot Evidence Hunter", md)
        self.assertIn("L3_current_official_catalyst", md)
        self.assertIn("entity_mismatch", md)

    def test_missing_finhot_db_returns_input_gap_report(self) -> None:
        report = build_report([self._task()], Path("/tmp/no-such-finhot.db"), "2026-06-26")

        self.assertEqual(report["tasks"][0]["status"], "input_gap")
        self.assertEqual(report["summary"]["matched_count"], 0)
        self.assertTrue(report["warnings"])


if __name__ == "__main__":
    unittest.main()
