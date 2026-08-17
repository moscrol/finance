# -*- coding: utf-8 -*-
"""evidence_providers 的独立单测（端到端行为由 test_golden_answers.py 保护）。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from intelligence.services.ask_types import AskOptions, AskResult, Citation
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services import evidence_providers as ep


class _CatalogKnowledge:
    """按 target/concept 精确过滤，复现 adapter 把错位概念绑到锚定实体时的空命中。"""

    def __init__(self, catalog: dict[str, list[dict]]) -> None:
        self.catalog = catalog
        self.calls: list[tuple[str, str | None]] = []

    def get_evidence(self, target, concept=None, limit=20, include_invalidated=False):
        self.calls.append((target, concept))
        items = list(self.catalog.get(target, []))
        if concept:
            items = [item for item in items if item.get("concept") == concept]
        matched = items[:limit]
        return {"found": bool(matched), "items": matched}


def _evidence_ctx(*, query: str, knowledge, anchor: EntityAnchor | None = None) -> ep.EvidenceContext:
    options = AskOptions(query=query, max_evidence=8)
    result = AskResult(
        query=query,
        trade_date=None,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
    )
    citations: list[Citation] = []

    def cite(prefix: str, source: str, detail: str = "") -> str:
        tag = f"{prefix}{sum(1 for item in citations if item.tag.startswith(prefix)) + 1}"
        citations.append(Citation(tag=tag, source=source, detail=detail))
        return f"[{tag}]"

    return ep.EvidenceContext(
        options=options,
        result=result,
        knowledge=knowledge,
        question_plan=SimpleNamespace(),
        anchor=anchor,
        candidate=None,
        doc={},
        export_name="export.json",
        claim_theme=query,
        graph_query=query,
        cite=cite,
        structured_claims=[],
        company_candidates=[],
        is_stale=lambda _item: False,
        confidence_score=lambda _value: None,
        stage_timeout=lambda limit: limit,
    )


class CompanyExposureTierTests(unittest.TestCase):
    def test_core_requires_direct_company_evidence(self) -> None:
        row = {"strength": "core", "confidence": "high", "evidence_layer": "L3"}
        self.assertEqual(ep._company_exposure_tier(row), "core")

    def test_graph_only_is_peripheral(self) -> None:
        row = {"strength": "core", "confidence": "high", "evidence_layer": "graph_only"}
        self.assertEqual(ep._company_exposure_tier(row), "peripheral")

    def test_default_other(self) -> None:
        row = {"strength": "medium", "confidence": "mid", "evidence_layer": "L2"}
        self.assertEqual(ep._company_exposure_tier(row), "other")


class PriorConclusionPageTests(unittest.TestCase):
    def test_synthesis_and_briefings_are_prior(self) -> None:
        self.assertTrue(ep._is_prior_conclusion_page("synthesis/2026-07-01.md"))
        self.assertTrue(ep._is_prior_conclusion_page("briefings/foo.md"))
        self.assertTrue(ep._is_prior_conclusion_page("/synthesis/foo.md"))

    def test_other_pages_are_not_prior(self) -> None:
        self.assertFalse(ep._is_prior_conclusion_page("concepts/液冷.md"))


class CompanyNameFromOfficialTitleTests(unittest.TestCase):
    def test_extracts_company_before_keyword(self) -> None:
        self.assertEqual(
            ep._company_name_from_official_title("申菱环境：投资者关系活动记录"),
            "申菱环境",
        )

    def test_rejects_non_name_prefix(self) -> None:
        self.assertIsNone(
            ep._company_name_from_official_title("关于近期市场传闻的说明！？公告"),
        )


class CollectEvidenceIndexAnchorTests(unittest.TestCase):
    """R 通道：锚定实体不能被图谱暴露概念滤空。"""

    def _catalog(self) -> dict[str, list[dict]]:
        return {
            "长电科技": [
                {
                    "target": "长电科技",
                    "concept": "AI算力",
                    "source": "[[AI算力产业新格局与供应链深度研究报告]]",
                    "evidence": "2025年前三季度营收 286.69 亿元，同比增长 18%",
                    "source_date": "2025-10-31",
                    "confidence": "high",
                }
            ],
            "富信科技": [
                {
                    "target": "富信科技",
                    "concept": "CPO",
                    "source": "[[富信科技_688662_最新逻辑跟踪_20260612]]",
                    "evidence": "Micro TEC国产替代",
                    "source_date": "2026-06-12",
                    "confidence": "medium",
                }
            ],
        }

    def test_anchored_entity_evidence_survives_mismatched_graph_concept(self) -> None:
        knowledge = _CatalogKnowledge(self._catalog())
        ctx = _evidence_ctx(
            query="长电科技的营收规模怎么看",
            knowledge=knowledge,
            anchor=EntityAnchor(entity="长电科技", ticker="600584", matched_by="name"),
        )
        bundle = ep.collect_evidence_index(
            ctx,
            {"长电科技": "1.6T CPO", "富信科技": "CPO"},
        )
        joined = "\n".join(bundle.lines)
        self.assertIn("286.69", joined)
        self.assertIn("长电科技", joined)
        self.assertIn(("长电科技", None), knowledge.calls)

    def test_unanchored_query_still_uses_graph_concept_filter(self) -> None:
        knowledge = _CatalogKnowledge(self._catalog())
        ctx = _evidence_ctx(
            query="光模块温控怎么看",
            knowledge=knowledge,
            anchor=None,
        )
        bundle = ep.collect_evidence_index(ctx, {"富信科技": "CPO", "长电科技": "1.6T CPO"})
        joined = "\n".join(bundle.lines)
        self.assertIn("富信科技", joined)
        self.assertIn("Micro TEC", joined)
        self.assertNotIn("286.69", joined)
        self.assertIn(("富信科技", "CPO"), knowledge.calls)
        self.assertIn(("长电科技", "1.6T CPO"), knowledge.calls)


if __name__ == "__main__":
    unittest.main()
