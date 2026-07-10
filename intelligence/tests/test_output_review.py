from __future__ import annotations

import unittest
from datetime import date

from intelligence.services.output_review import PASS, WARN, review_output
from intelligence.services.research_brief import (
    audit_evidence_chain,
    build_counterevidence_plan,
)

TODAY = date(2026, 7, 2)
GOOD_CHAIN = [
    "英维克：公告披露液冷订单落地，签订供货合同（公告） [R1]",
    "板块双红，涨停热度集中 [S1]",
]
WEAK_CHAIN = ["题材研报预计有望受益 [W1]"]


def _gate(chain, **kw):
    audit = audit_evidence_chain(chain)
    plan = build_counterevidence_plan(audit, stage="预期交易")
    defaults = dict(
        trade_date="2026-07-01",
        audit=audit,
        counter_plan=plan,
        gap_lines=["显式缺口一条"],
        follow_ups=plan.follow_up_lines(),
        conclusion_lines=["条件化结论"],
        today=TODAY,
    )
    defaults.update(kw)
    return review_output(**defaults)


class OutputReviewTests(unittest.TestCase):
    def test_healthy_answer_passes_all_six(self) -> None:
        gate = _gate(GOOD_CHAIN)
        self.assertEqual(gate.status, PASS)
        self.assertEqual(gate.warn_count, 0)
        self.assertEqual(len(gate.checks), 6)

    def test_stale_trade_date_warns(self) -> None:
        gate = _gate(GOOD_CHAIN, trade_date="2026-06-01")
        self.assertEqual(gate.checks[0].status, WARN)
        self.assertEqual(gate.status, WARN)

    def test_missing_trade_date_warns(self) -> None:
        gate = _gate(GOOD_CHAIN, trade_date=None)
        self.assertEqual(gate.checks[0].status, WARN)

    def test_empty_audit_and_no_counterplan_warn(self) -> None:
        gate = _gate(GOOD_CHAIN, audit=None, counter_plan=None)
        self.assertEqual(gate.checks[1].status, WARN)
        self.assertEqual(gate.checks[2].status, WARN)

    def test_no_gaps_and_no_verifiable_warn(self) -> None:
        gate = _gate(GOOD_CHAIN, gap_lines=[], follow_ups=["随便看看"])
        self.assertEqual(gate.checks[3].status, WARN)
        self.assertEqual(gate.checks[4].status, WARN)

    def test_overclaim_without_l3_warns(self) -> None:
        gate = _gate(WEAK_CHAIN, conclusion_lines=["该股确定受益，上涨板上钉钉"])
        self.assertEqual(gate.checks[5].status, WARN)
        self.assertIn("确定", gate.checks[5].note)

    def test_weak_evidence_with_bounded_conclusion_passes(self) -> None:
        gate = _gate(WEAK_CHAIN, conclusion_lines=["按预期交易档对待，待 L3 确认"])
        self.assertEqual(gate.checks[5].status, PASS)

    def test_final_answer_is_checked_instead_of_template_conclusion(self) -> None:
        gate = _gate(
            WEAK_CHAIN,
            conclusion_lines=["按预期交易档对待，待 L3 确认"],
            final_answer="该股确定受益，结论已证实。",
        )
        self.assertEqual(gate.checks[5].status, WARN)
        self.assertIn("已证实", gate.checks[5].note)

    def test_summary_lines_render(self) -> None:
        lines = _gate(GOOD_CHAIN).summary_lines()
        self.assertIn("输出质检闸门", lines[0])
        self.assertEqual(len(lines), 7)


if __name__ == "__main__":
    unittest.main()
