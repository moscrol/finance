from __future__ import annotations

import json
import unittest

from intelligence.services.answer_quality import LAYER_L1, LAYER_L2, LAYER_L3, LAYER_L4
from intelligence.services.research_brief import (
    BRIEF_SECTION_ORDER,
    audit_evidence_chain,
    build_counterevidence_plan,
    build_retrieval_telemetry,
    build_stock_research_brief,
    classify_evidence_line,
)

# 三个典型样例（对应脑暴文档要求：高分 / 证据不足 / 被题材标签绑架）
FULL_CHAIN = [
    "英维克：公告披露液冷订单落地，签订供货合同（公告, 2026-06-01, 质量 high） [R1]",
    "公司主营精密温控，收入结构中数据中心占比 60%，毛利弹性来自机柜级液冷 [G1]",
    "题材研报提示液冷需求扩张，同题材核心层还有申菱环境（替代表达） [W1]",
    "板块双红，涨停热度集中，边际量放大 [S1]",
]
WEAK_CHAIN = [
    "题材研报预计公司有望受益液冷需求扩张 [W1]",
    "产业链访谈推断快接头环节弹性最大 [W2]",
]
LABEL_TRAP_CHAIN = [
    "命中概念：液冷服务器（题材标签，外围暴露，graph_only） [G1]",
    "板块涨停热度高，个股跟随新高 [S1]",
]


class ClassifyLineTests(unittest.TestCase):
    def test_official_source_plus_hard_action_is_l3(self) -> None:
        self.assertEqual(classify_evidence_line(FULL_CHAIN[0], "R"), LAYER_L3)

    def test_official_deployed_product_is_l3(self) -> None:
        line = "英维克公司公告披露液冷产品已应用于数据中心温控场景 [R1]"

        self.assertEqual(classify_evidence_line(line, "R"), LAYER_L3)

    def test_speculative_report_line_is_not_l3(self) -> None:
        line = "研报预计公司量产液冷快接头，有望进入公告披露节奏 [W1]"
        self.assertNotEqual(classify_evidence_line(line, "W"), LAYER_L3)

    def test_market_tag_is_l4(self) -> None:
        self.assertEqual(classify_evidence_line(FULL_CHAIN[3], "S"), LAYER_L4)

    def test_baseline_line_is_l2(self) -> None:
        self.assertEqual(classify_evidence_line(FULL_CHAIN[1], "G"), LAYER_L2)


class EvidenceAuditTests(unittest.TestCase):
    def test_full_chain_verdict_is_fact_validated(self) -> None:
        audit = audit_evidence_chain(FULL_CHAIN)
        self.assertTrue(audit.has_l3)
        self.assertTrue(audit.has_l4)
        self.assertEqual(audit.verdict, "事实验证")
        self.assertEqual(sum(audit.layer_counts.values()), 4)

    def test_weak_chain_flags_l1_dominance(self) -> None:
        audit = audit_evidence_chain(WEAK_CHAIN)
        self.assertFalse(audit.has_l3)
        self.assertEqual(audit.verdict, "预期交易")
        self.assertTrue(any("L1" in w and "预期交易" in w for w in audit.warnings))
        self.assertTrue(any("L3" in g for g in audit.gaps))

    def test_label_trap_chain_is_sentiment_pulse(self) -> None:
        audit = audit_evidence_chain(LABEL_TRAP_CHAIN, gap_lines=["存在 graph_only 外围暴露"])
        self.assertTrue(any("graph_only" in g for g in audit.gaps))
        self.assertTrue(any("情绪脉冲" in w for w in audit.warnings) or audit.layer_counts.get(LAYER_L1))

    def test_empty_chain_is_insufficient(self) -> None:
        audit = audit_evidence_chain(["（本轮未命中证据）"])
        self.assertEqual(audit.verdict, "证据不足")
        self.assertEqual(audit.items, [])

    def test_prompt_block_contains_verdict(self) -> None:
        block = audit_evidence_chain(FULL_CHAIN).to_prompt_block()
        self.assertIn("证据分层审计", block)
        self.assertIn("事实验证", block)


class RetrievalTelemetryTests(unittest.TestCase):
    def test_telemetry_reports_scores_and_l3_coverage(self) -> None:
        audit = audit_evidence_chain(FULL_CHAIN)
        tele = build_retrieval_telemetry(
            audit=audit,
            citation_tags=["S1", "G1", "R1", "W1", "W2"],
            wiki_stats={
                "attempted": True,
                "ok": True,
                "mode": "hybrid",
                "index": "structured",
                "hits": 2,
                "scores": [0.82, 0.64],
                "neighbor_hits": 1,
            },
        )
        self.assertTrue(tele.covers_l3)
        self.assertEqual(tele.source_hits, {"S": 1, "G": 1, "R": 1, "W": 2})
        self.assertAlmostEqual(tele.wiki_top_score or 0, 0.82)
        self.assertAlmostEqual(tele.wiki_mean_score or 0, 0.73)
        self.assertIn("事实验证", tele.verdict)
        joined = "\n".join(tele.summary_lines())
        self.assertIn("mode=hybrid", joined)
        self.assertIn("已覆盖", joined)

    def test_telemetry_without_hits_flags_empty_retrieval(self) -> None:
        audit = audit_evidence_chain([])
        tele = build_retrieval_telemetry(audit=audit, citation_tags=[], wiki_stats={"attempted": False})
        self.assertFalse(tele.covers_l3)
        self.assertIn("检索全空", tele.verdict)

    def test_degraded_wiki_is_surfaced(self) -> None:
        audit = audit_evidence_chain(WEAK_CHAIN)
        tele = build_retrieval_telemetry(
            audit=audit,
            citation_tags=["W1"],
            wiki_stats={"attempted": True, "ok": False, "mode": "hybrid", "warning": "rag_index timeout"},
        )
        self.assertEqual(tele.wiki_degraded, "rag_index timeout")
        self.assertIn("降级", tele.verdict)


class CounterEvidenceTests(unittest.TestCase):
    def test_missing_l3_generates_l3_rebuttal_and_downgrade(self) -> None:
        audit = audit_evidence_chain(WEAK_CHAIN)
        plan = build_counterevidence_plan(audit, stage="预期交易")
        self.assertTrue(any("L3" in r for r in plan.rebuttals))
        self.assertTrue(any("抢跑" in r for r in plan.rebuttals))
        self.assertTrue(plan.downgrade_triggers)

    def test_schedule_covers_t1_t3_t5(self) -> None:
        plan = build_counterevidence_plan(audit_evidence_chain(FULL_CHAIN), stage="事实验证但兑现分歧")
        lines = plan.follow_up_lines()
        for window in ("T+1", "T+3", "T+5"):
            self.assertTrue(any(line.startswith(f"[{window}]") for line in lines))

    def test_full_chain_flags_crowding_risk(self) -> None:
        plan = build_counterevidence_plan(audit_evidence_chain(FULL_CHAIN))
        self.assertTrue(any("拥挤" in r for r in plan.rebuttals))


class StockResearchBriefTests(unittest.TestCase):
    def _brief(self, chain: list[str], stage: str = "预期交易"):
        audit = audit_evidence_chain(chain)
        tele = build_retrieval_telemetry(audit=audit, citation_tags=["G1"], wiki_stats=None)
        plan = build_counterevidence_plan(audit, stage=stage)
        return build_stock_research_brief("深挖英维克", "stock_deep_dive", stage, audit, tele, plan)

    def test_brief_covers_all_eight_sections(self) -> None:
        brief = self._brief(FULL_CHAIN, stage="事实验证但兑现分歧")
        self.assertEqual([s.name for s in brief.sections], BRIEF_SECTION_ORDER)
        by_name = {s.name: s for s in brief.sections}
        self.assertTrue(by_name["证据硬度"].points)
        self.assertTrue(by_name["反证"].points)
        self.assertTrue(by_name["条件化结论"].points)
        self.assertTrue(any("阶段判断" in p for p in by_name["生命周期"].points))

    def test_missing_perspectives_become_explicit_gaps(self) -> None:
        brief = self._brief(WEAK_CHAIN)
        by_name = {s.name: s for s in brief.sections}
        self.assertTrue(by_name["公司本体"].gaps)
        self.assertTrue(by_name["市场价值"].gaps)
        self.assertTrue(by_name["同链对比"].gaps)

    def test_json_roundtrip(self) -> None:
        brief = self._brief(FULL_CHAIN)
        doc = json.loads(brief.to_json())
        self.assertEqual(doc["query"], "深挖英维克")
        self.assertEqual(len(doc["sections"]), 8)
        self.assertIn("evidence_audit", doc)
        self.assertIn("retrieval_telemetry", doc)
        self.assertIn("counterevidence", doc)
        self.assertIn("verdict", doc["evidence_audit"])

    def test_prompt_block_mentions_gaps(self) -> None:
        block = self._brief(LABEL_TRAP_CHAIN).to_prompt_block()
        self.assertIn("个股研究简报骨架", block)
        self.assertIn("缺口", block)


if __name__ == "__main__":
    unittest.main()
