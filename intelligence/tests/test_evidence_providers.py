# -*- coding: utf-8 -*-
"""evidence_providers 的独立单测（端到端行为由 test_golden_answers.py 保护）。"""
from __future__ import annotations

import unittest

from intelligence.services import evidence_providers as ep


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


if __name__ == "__main__":
    unittest.main()
