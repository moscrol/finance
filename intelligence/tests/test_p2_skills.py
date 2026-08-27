from __future__ import annotations

import unittest

from intelligence.services.event_transmission import (
    EVENT_STEP_ORDER,
    build_event_transmission_brief,
)
from intelligence.services.evidence_gap_radar import (
    DIM_CUSTOMER,
    DIM_OFFICIAL,
    GAP_DIMENSIONS,
    scan_evidence_gaps,
)
from intelligence.services.valuation_gap import VALUATION_QUESTIONS, check_valuation_gaps


class EvidenceGapRadarTests(unittest.TestCase):
    def test_full_coverage_no_gaps(self) -> None:
        report = scan_evidence_gaps(
            "英维克",
            [
                "主营精密温控，产业链位置中游 [G1]",
                "收入结构：数据中心占比 60%，毛利 30% [G2]",
                "客户导入：某云厂商送样验证 [R1]",
                "公告披露液冷订单落地 [R2]",
                "同题材核心层还有申菱环境，替代表达 [W1]",
                "相对强度领先，新高承接良好 [S1]",
            ],
        )
        self.assertEqual(report.gaps, [])
        self.assertEqual(report.coverage_rate, 1.0)
        self.assertIn("六维证据齐备", report.to_prompt_block())

    def test_missing_dimensions_generate_tasks(self) -> None:
        report = scan_evidence_gaps("某公司", ["主营电子元件 [G1]"])
        self.assertIn(DIM_CUSTOMER, report.gaps)
        self.assertIn(DIM_OFFICIAL, report.gaps)
        self.assertEqual(len(report.gap_notes), len(report.gaps))
        self.assertEqual(len(report.candidate_tasks), len(report.gaps))

    def test_empty_evidence_all_gaps(self) -> None:
        report = scan_evidence_gaps("某公司", [])
        self.assertEqual(len(report.gaps), len(GAP_DIMENSIONS))
        self.assertEqual(report.coverage_rate, 0.0)


class EventTransmissionTests(unittest.TestCase):
    def test_six_steps_always_present(self) -> None:
        brief = build_event_transmission_brief("某政策发布", [])
        self.assertEqual([s.name for s in brief.steps], EVENT_STEP_ORDER)
        self.assertTrue(brief.warnings)  # 无 L3 → 可验证假设警告

    def test_hard_fact_clears_warning(self) -> None:
        brief = build_event_transmission_brief(
            "中标事件",
            [
                "公司公告披露中标订单，签订合同 [R1]",
                "产业链上游环节传导 [W1]",
                "利润与毛利弹性测算 [W2]",
                "受益公司弹性对比 [W3]",
                "市场存在一阶/二阶混淆的预期差 [W4]",
            ],
        )
        self.assertFalse(brief.warnings)
        self.assertTrue(all(not s.gaps for s in brief.steps))

    def test_prompt_block_contains_verification(self) -> None:
        block = build_event_transmission_brief("事件", []).to_prompt_block()
        self.assertIn("验证路径", block)
        self.assertIn("不输出交易指令", block)


class ValuationGapTests(unittest.TestCase):
    def test_all_gaps_when_empty(self) -> None:
        note = check_valuation_gaps([])
        self.assertEqual(note.answered, [])
        self.assertEqual(len(note.gaps), len(VALUATION_QUESTIONS))

    def test_partial_answers(self) -> None:
        note = check_valuation_gaps(
            ["当前市值 300 亿，PS 8 倍 [G1]", "同链可比公司市值对比 [W1]"]
        )
        self.assertIn(VALUATION_QUESTIONS[0], note.answered)
        self.assertIn(VALUATION_QUESTIONS[3], note.answered)
        self.assertEqual(len(note.gaps), 2)
        self.assertIn("不给目标价", note.to_prompt_block())


if __name__ == "__main__":
    unittest.main()
