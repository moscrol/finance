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
        self.assertEqual(len(gate.checks), 11)

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

    def test_bounded_certainty_context_does_not_trigger_overclaim(self) -> None:
        gate = _gate(
            WEAK_CHAIN,
            conclusion_lines=[
                "结论由确定性结构化规则生成；持续性仍不确定，无法确定直接受益。"
            ],
        )
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
        self.assertIn("输出质检助手", lines[0])
        self.assertIn("不阻断", lines[0])
        self.assertIn("6/6", lines[0])
        self.assertEqual(len(lines), 12)

    def test_five_element_gaps_are_advisory_and_do_not_change_gate_status(self) -> None:
        gate = _gate(GOOD_CHAIN, conclusion_lines=["条件化结论"])
        five = [check for check in gate.checks if check.name.startswith("结论五元素")]
        self.assertEqual(len(five), 5)
        self.assertTrue(all(check.advisory_only for check in five))
        self.assertTrue(any(check.status == WARN for check in five))
        self.assertEqual(gate.warn_count, 0)
        self.assertEqual(gate.status, PASS)

    def test_complete_five_elements_pass_advisory_checks(self) -> None:
        conclusion = (
            "## 结论\n"
            "**直接定性：** 仍是预期交易，不是业绩主升。\n"
            "**主要风险：** 若毛利率连续两季回落，判断降级。\n"
            "**下一步验证：** T+1 看放量，T+3 看扩散是否同步。\n"
            "未验证变量是单季毛利率，时点看 2026-10-31 三季报。\n"
            "替代路径：若被证伪则改看有公告订单的中游。\n"
        )
        gate = _gate(GOOD_CHAIN, conclusion_lines=[conclusion])
        five = [check for check in gate.checks if check.name.startswith("结论五元素")]
        self.assertTrue(all(check.status == PASS for check in five))

    def test_gate_is_explicitly_advisory(self) -> None:
        gate = _gate(GOOD_CHAIN)
        payload = gate.to_dict()
        self.assertEqual(payload["decision_role"], "advisory_review")
        self.assertFalse(payload["blocking"])


class StaleMislabelTests(unittest.TestCase):
    """时点错标嗅探（2026-08-26 blk-d9 实测形状的回归钉）。"""

    HINT = (("D9", "2026-08-07", "2026-08-26"),)

    def test_extract_hint_from_block_text(self) -> None:
        from intelligence.services.output_review import extract_stale_block_hints

        block = (
            "## L2 大单资金流数据块 [D9]\n"
            "- ⚠ 时点限定（先读）：最新扫描日 2026-08-07 早于盘面日期 2026-08-26，"
            "本块全部数据均为 2026-08-07 的存量扫描。\n"
        )
        hints = extract_stale_block_hints([("D9", block), ("D7", "无限定行")])
        self.assertEqual(hints, (("D9", "2026-08-07", "2026-08-26"),))

    def test_mislabeled_as_today_warns_advisory(self) -> None:
        # blk-d9 原话形状：陈旧榜单被写成「2026-08-26 当日的大单净流入扫描榜单」
        answer = "已有的资金流证据是 2026-08-26 当日的大单净流入扫描榜单，C嘉立创主买净额约5.35亿。"
        gate = _gate(GOOD_CHAIN, final_answer=answer, stale_block_hints=self.HINT)
        check = next(c for c in gate.checks if c.name == "时点错标·D9")
        self.assertEqual(check.status, WARN)
        self.assertTrue(check.advisory_only)
        self.assertIn("2026-08-07", check.note)
        self.assertEqual(gate.status, PASS)  # 只提示，不改闸门

    def test_answer_carrying_scan_date_passes(self) -> None:
        answer = "大单净流入榜为最新扫描日 2026-08-07 数据（早于报告日），非当日榜单。"
        gate = _gate(GOOD_CHAIN, final_answer=answer, stale_block_hints=self.HINT)
        check = next(c for c in gate.checks if c.name == "时点错标·D9")
        self.assertEqual(check.status, PASS)

    def test_column_header_dangri_rank_is_exempt(self) -> None:
        # 表格列名「当日名次」不算当日化表述
        answer = "榜单字段含 当日名次 列，另见附表。"
        gate = _gate(GOOD_CHAIN, final_answer=answer, stale_block_hints=self.HINT)
        check = next(c for c in gate.checks if c.name == "时点错标·D9")
        self.assertNotIn("疑似", check.note)

    def test_no_hints_adds_no_checks(self) -> None:
        gate = _gate(GOOD_CHAIN, final_answer="随便什么答案")
        self.assertFalse([c for c in gate.checks if c.name.startswith("时点错标")])


if __name__ == "__main__":
    unittest.main()
