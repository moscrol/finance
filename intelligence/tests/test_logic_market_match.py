"""Tests for logic_market_match classification seam and label safety."""
from __future__ import annotations

import unittest

from intelligence.services import logic_market_match, research_brief


class TestClassifyMarketLogic(unittest.TestCase):
    """Test the pure-classification seam exposed for ask/agent paths."""

    def test_old_logic_wakeup_when_all_present(self) -> None:
        verdict = logic_market_match.classify_market_logic(
            market_found=True,
            concept_count=3,
            exposure_count=5,
            evidence_count=4,
            trace_missing=0,
        )
        self.assertEqual(verdict.classification, "old_logic_wakeup")
        self.assertEqual(verdict.label, "旧逻辑重新活跃")
        self.assertGreater(verdict.confidence, 0.8)
        self.assertEqual(len(verdict.data_gaps), 0)
        self.assertIn("front-map", str(verdict.next_actions))

    def test_new_logic_candidate_when_market_only(self) -> None:
        verdict = logic_market_match.classify_market_logic(
            market_found=True,
            concept_count=0,
            exposure_count=0,
            evidence_count=0,
            trace_missing=0,
        )
        # market_found + gaps -> data_gap (现有逻辑)
        self.assertEqual(verdict.classification, "data_gap")
        self.assertEqual(verdict.label, "数据待补")
        self.assertGreater(len(verdict.data_gaps), 0)

    def test_data_gap_when_knowledge_present_market_absent(self) -> None:
        verdict = logic_market_match.classify_market_logic(
            market_found=False,
            concept_count=2,
            exposure_count=1,
            evidence_count=1,
            trace_missing=0,
        )
        self.assertEqual(verdict.classification, "data_gap")
        self.assertIn("missing_market_signal", verdict.data_gaps)

    def test_noise_when_nothing_present(self) -> None:
        verdict = logic_market_match.classify_market_logic(
            market_found=False,
            concept_count=0,
            exposure_count=0,
            evidence_count=0,
            trace_missing=0,
        )
        self.assertEqual(verdict.classification, "noise_or_unconfirmed")
        self.assertEqual(verdict.label, "未确认线索")
        self.assertLess(verdict.confidence, 0.2)

    def test_confidence_decreases_with_trace_missing(self) -> None:
        v1 = logic_market_match.classify_market_logic(
            market_found=True, concept_count=3, exposure_count=5, evidence_count=4, trace_missing=0
        )
        v2 = logic_market_match.classify_market_logic(
            market_found=True, concept_count=3, exposure_count=5, evidence_count=4, trace_missing=3
        )
        self.assertLess(v2.confidence, v1.confidence)


class TestLabelSafetyAgainstL4Terms(unittest.TestCase):
    """Regression: 中文标签不得含 research_brief._L4_TERMS 里的词。
    
    否则四分类标签拼进证据行后，会被 classify_evidence_line 误判成 L4 盘面证据，
    导致 audit.has_l4 翻 True，反证计划从「盘面未验证」跳成「拥挤度」。
    """

    def test_all_four_labels_avoid_l4_terms(self) -> None:
        """四个中文标签都不得撞 _L4_TERMS。"""
        labels = logic_market_match.CLASSIFICATION_LABELS
        self.assertEqual(len(labels), 4, "本测试假设四分类有四个档位")
        for key, label in labels.items():
            with self.subTest(classification=key, label=label):
                hits = [term for term in research_brief._L4_TERMS if term in label]
                self.assertEqual(
                    hits,
                    [],
                    f"{key} 的中文标签「{label}」撞中 _L4_TERMS: {hits}；"
                    f"会使证据行被误分成 L4 盘面证据",
                )

    def test_labels_do_not_flip_knowledge_line_to_l4(self) -> None:
        """End-to-end：标签拼进证据行后不能改变分层结果（必须保持 L1）。"""
        base_line = "川环科技：券商研报提及客户验证（东吴证券, 2026-05-20, 质量 ?） [R1]"
        baseline_layer = research_brief.classify_evidence_line(base_line, "R")
        self.assertEqual(baseline_layer, "L1", "baseline 应是 L1")

        labels = logic_market_match.CLASSIFICATION_LABELS
        for key, label in labels.items():
            with self.subTest(classification=key, label=label):
                line_with_mark = f"川环科技：券商研报提及客户验证（东吴证券, 2026-05-20, 质量 ? ｜{label}） [R1]"
                layer = research_brief.classify_evidence_line(line_with_mark, "R")
                self.assertEqual(
                    layer,
                    "L1",
                    f"标签「{label}」拼入后证据行从 L1 翻成 {layer}；"
                    f"会导致 audit.has_l4 误判，影响反证计划",
                )

    def test_mutation_bad_label_does_flip_to_l4(self) -> None:
        """变异测试：含「信号」的标签确实会翻成 L4（验证检测机制有效）。"""
        base_line = "川环科技：券商研报提及客户验证（东吴证券, 2026-05-20, 质量 ?） [R1]"
        baseline_layer = research_brief.classify_evidence_line(base_line, "R")
        self.assertEqual(baseline_layer, "L1")

        bad_label = "待确认信号"  # 「信号」在 _L4_TERMS 里
        self.assertIn("信号", research_brief._L4_TERMS, "前提检查：「信号」必须在 _L4_TERMS 里")
        bad_line = f"川环科技：券商研报提及客户验证（东吴证券, 2026-05-20, 质量 ? ｜{bad_label}） [R1]"
        bad_layer = research_brief.classify_evidence_line(bad_line, "R")
        self.assertEqual(
            bad_layer,
            "L4",
            "变异测试：含「信号」的标签应翻成 L4，证明检测机制有效",
        )


class TestDeriveDataGaps(unittest.TestCase):
    """Test gap derivation logic (shared between match_logic_to_market and classify_market_logic)."""

    def test_all_gaps_when_nothing_found(self) -> None:
        gaps = logic_market_match.derive_data_gaps(
            market_found=False,
            concept_count=0,
            exposure_count=0,
            evidence_count=0,
            trace_missing=0,
        )
        self.assertIn("missing_market_signal", gaps)
        self.assertIn("missing_concept", gaps)
        self.assertIn("missing_entity_exposure", gaps)
        self.assertIn("missing_evidence", gaps)

    def test_trace_missing_added_when_nonzero(self) -> None:
        gaps = logic_market_match.derive_data_gaps(
            market_found=True,
            concept_count=3,
            exposure_count=5,
            evidence_count=4,
            trace_missing=2,
        )
        self.assertIn("missing_source_trace", gaps)

    def test_no_gaps_when_all_present(self) -> None:
        gaps = logic_market_match.derive_data_gaps(
            market_found=True,
            concept_count=3,
            exposure_count=5,
            evidence_count=4,
            trace_missing=0,
        )
        self.assertEqual(gaps, [])
