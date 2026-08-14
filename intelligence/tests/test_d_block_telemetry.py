from __future__ import annotations

import unittest

from intelligence.services.research_brief import (
    DBlockStat,
    audit_evidence_chain,
    build_retrieval_telemetry,
    summarize_d_blocks,
)
from intelligence.services.retrieval_audit import build_audit_record


class DBlockTelemetryTests(unittest.TestCase):
    def test_summary_counts_generated_blocks(self) -> None:
        stats = [
            DBlockStat("D1", "市场价值与替代队列", attempted=True, generated=True, line_count=12),
            DBlockStat("D2", "客户证据硬度", attempted=True, generated=False, note="无匹配数据"),
        ]
        lines = summarize_d_blocks(stats)
        self.assertIn("1/2 块命中", lines[0])
        self.assertIn("命中，12 行", lines[1])
        self.assertIn("未命中（无匹配数据）", lines[2])

    def test_not_attempted_summary(self) -> None:
        line = DBlockStat("D4", "主线题材结构", note="仅 --compose 路径生成").summary_line()
        self.assertIn("未尝试", line)
        self.assertIn("仅 --compose 路径生成", line)

    def test_empty_stats_produce_no_lines(self) -> None:
        self.assertEqual(summarize_d_blocks([]), [])

    def test_audit_record_carries_d_blocks(self) -> None:
        audit = audit_evidence_chain(["公告披露中标订单 [R1]"])
        telemetry = build_retrieval_telemetry(audit=audit, citation_tags=["R1"])
        record = build_audit_record(
            query="q",
            question_type="stock_deep_dive",
            trade_date="2026-07-01",
            audit=audit,
            telemetry=telemetry,
            d_block_stats=[DBlockStat("D1", "市场价值与替代队列", attempted=True, generated=True, line_count=3)],
        )
        doc = record.to_dict()
        self.assertEqual(len(doc["d_blocks"]), 1)
        self.assertEqual(doc["d_blocks"][0]["tag"], "D1")
        self.assertTrue(doc["d_blocks"][0]["generated"])


if __name__ == "__main__":
    unittest.main()
