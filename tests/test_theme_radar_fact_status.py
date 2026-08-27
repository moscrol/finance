"""theme-radar 读 fact_status：意向陈述不得进 delta 桶。

缺字段保持旧行为（存量索引没回填，不能假装全是意向）。
confidence / evidence_layer 不是这根轴。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_RADAR_SPEC = importlib.util.spec_from_file_location(
    "theme_radar_fact_status_script",
    Path(__file__).resolve().parents[1] / "skills" / "theme-radar" / "scripts" / "radar.py",
)
radar = importlib.util.module_from_spec(_RADAR_SPEC)
assert _RADAR_SPEC and _RADAR_SPEC.loader
sys.modules["theme_radar_fact_status_script"] = radar
_RADAR_SPEC.loader.exec_module(radar)

COMPANY = "测试股份"
CONCEPT = "光刻胶"
DELTA_SOURCE = "市场逻辑 / 2026-08-18 公告"
INTENT_TEXT = "拟投资建设光刻胶产线"


def _company() -> dict:
    return {
        "name": COMPANY,
        "code": "000001",
        "strength": "related",
        "concepts": [CONCEPT],
        "evidence_buckets": radar.empty_evidence_buckets(),
        "evidence_layers": [],
        "update_types": [],
        "source_quality": [],
    }


def _item(**overrides) -> dict:
    row = {
        "target": COMPANY,
        "concept": CONCEPT,
        "source": DELTA_SOURCE,
        "evidence": INTENT_TEXT,
        "update_type": "review_candidate",
        "evidence_layer": "L2",
        "confidence": "high",
    }
    row.update(overrides)
    return row


class IntentIsNotDeltaTests(unittest.TestCase):
    def test_planned_exposure_with_market_logic_source_is_not_delta(self) -> None:
        buckets = radar.buckets_for_exposure(
            {
                "update_type": "review_candidate",
                "fact_status": "planned",
                "sources": [DELTA_SOURCE],
                "evidence": INTENT_TEXT,
            }
        )
        self.assertNotIn("delta", buckets)

    def test_every_intent_status_is_not_delta(self) -> None:
        for status in ("planned", "framework", "disclosed", "under_validation", "rumored"):
            buckets = radar.buckets_for_exposure(
                {
                    "update_type": "review_candidate",
                    "fact_status": status,
                    "sources": [DELTA_SOURCE],
                    "evidence": INTENT_TEXT,
                }
            )
            self.assertNotIn("delta", buckets, status)

    def test_legacy_hard_delta_tag_on_planned_is_still_not_delta(self) -> None:
        buckets = radar.buckets_for_exposure(
            {
                "update_type": "hard_delta",
                "fact_status": "planned",
                "sources": [DELTA_SOURCE],
                "evidence": INTENT_TEXT,
            }
        )
        self.assertNotIn("delta", buckets)

    def test_missing_fact_status_keeps_source_token_delta(self) -> None:
        buckets = radar.buckets_for_exposure(
            {
                "update_type": "review_candidate",
                "sources": [DELTA_SOURCE],
                "evidence": INTENT_TEXT,
            }
        )
        self.assertIn("delta", buckets)

    def test_realized_keeps_source_token_delta(self) -> None:
        buckets = radar.buckets_for_exposure(
            {
                "update_type": "delta",
                "fact_status": "realized",
                "sources": [DELTA_SOURCE],
                "evidence": "已签订光刻胶供货合同",
            }
        )
        self.assertIn("delta", buckets)

    def test_enrich_does_not_score_planned_index_item_as_delta(self) -> None:
        company = _company()
        radar.enrich_companies_from_evidence_index(
            [company],
            {"items": [_item(fact_status="planned")]},
            [CONCEPT],
        )
        self.assertFalse(company["evidence_buckets"].get("delta"))
        self.assertNotIn("delta", company.get("update_types") or [])

    def test_enrich_still_scores_missing_fact_status_as_delta(self) -> None:
        company = _company()
        radar.enrich_companies_from_evidence_index(
            [company],
            {"items": [_item()]},
            [CONCEPT],
        )
        self.assertTrue(company["evidence_buckets"].get("delta"))


class IntentBucketTests(unittest.TestCase):
    """意向证据要有自己的桶——不加分，但不等于「没有证据」。

    上一版把 delta 拦掉后没给去处，意向证据落空→掉进 missing（权重 −1），
    于是「一条拟投资公告」和「一条证据都没有」同分同档；
    evidence_index 那条路更狠，兜底是 continue，整条证据连 evidence /
    evidence_layer / source_quality 都不记，凭空消失。
    """

    def test_intent_exposure_lands_in_intent_bucket_not_missing(self) -> None:
        buckets = radar.buckets_for_exposure(
            {
                "update_type": "",
                "sources": ["市场逻辑"],
                "evidence": "拟投资 A 项目",
                "fact_status": "planned",
            }
        )
        self.assertEqual(buckets, ["intent"])
        self.assertNotIn("missing", buckets)
        self.assertNotIn("delta", buckets)

    def test_intent_bucket_weight_is_zero_not_negative(self) -> None:
        """不加分，也不倒扣——倒扣等于把「未落地」当成「没有」。"""
        self.assertEqual(radar.EVIDENCE_WEIGHTS["intent"], 0)
        self.assertEqual(radar.EVIDENCE_WEIGHTS["missing"], -1)

    def test_realized_still_scores_delta(self) -> None:
        """反方向：落地证据不得被这道闸误伤。"""
        buckets = radar.buckets_for_exposure(
            {
                "update_type": "",
                "sources": ["市场逻辑"],
                "evidence": "已签合同",
                "fact_status": "realized",
            }
        )
        self.assertIn("delta", buckets)

    def test_intent_evidence_survives_the_evidence_index_path(self) -> None:
        """那条路的兜底是 continue，没有 intent 桶时整条证据会消失。"""
        company = _company()
        radar.enrich_companies_from_evidence_index(
            [company],
            {"items": [_item(fact_status="planned")]},
            [CONCEPT],
        )
        buckets = company.get("evidence_buckets", {}) or {}
        self.assertTrue(buckets.get("intent"), "意向证据应留在 intent 桶里，不该被 continue 丢掉")
        self.assertFalse(buckets.get("delta"), "意向证据不得进 delta")

    def test_intent_bucket_has_a_display_label(self) -> None:
        """没有标签会在 evidence_bucket_summary 里 KeyError。"""
        summary = radar.evidence_bucket_summary(
            {"evidence_buckets": {"intent": ["拟投资 A 项目"]}}
        )
        self.assertIn("意向", summary)
