from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from intelligence.services import foresight, interactions
from intelligence.services.foresight import (
    ForesightOptions,
    Question,
    generate,
    rank_questions,
)


def _fresh() -> list[Question]:
    return [
        Question("宏观流动性收紧后高位方向会怎样退潮", novelty=0.8, relevance=0.8),
        Question("液冷渗透率拐点何时到来对中际旭创意味着什么", novelty=0.7, relevance=0.7),
    ]


class RecordLoadTests(unittest.TestCase):
    def test_record_then_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "interactions.jsonl")
            written, rec = interactions.record_interaction(
                path,
                kind="click",
                question="液冷渗透率拐点何时到？",
                themes=["液冷", "液冷"],  # dedup
                stocks=["中际旭创"],
            )
            self.assertEqual(str(written), path)
            self.assertEqual(rec["kind"], "click")
            self.assertEqual(rec["weight"], 1.0)
            self.assertEqual(rec["themes"], ["液冷"])
            self.assertEqual(rec["stocks"], ["中际旭创"])
            records, warn = interactions.load_interactions(path)
            self.assertIsNone(warn)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["question"], "液冷渗透率拐点何时到？")

    def test_load_missing_file_is_empty(self) -> None:
        records, warn = interactions.load_interactions("/nonexistent/x/interactions.jsonl")
        self.assertEqual(records, [])
        self.assertIsNone(warn)

    def test_window_keeps_most_recent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "i.jsonl")
            for i in range(5):
                interactions.record_interaction(path, kind="view", themes=[f"题材{i}"])
            records, _ = interactions.load_interactions(path, window=2)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["themes"], ["题材3"])
            self.assertEqual(records[1]["themes"], ["题材4"])

    def test_corrupt_lines_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "i.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"kind":"click","weight":1.0,"themes":["液冷"],"stocks":[]}\n')
                fh.write("not json\n")
                fh.write("\n")
            records, warn = interactions.load_interactions(path)
            self.assertIsNone(warn)
            self.assertEqual(len(records), 1)


class WeightTests(unittest.TestCase):
    def test_rating_to_weight_bounds(self) -> None:
        self.assertEqual(interactions.rating_to_weight(5), 1.0)
        self.assertEqual(interactions.rating_to_weight(3), 0.0)
        self.assertEqual(interactions.rating_to_weight(1), -1.0)
        self.assertEqual(interactions.rating_to_weight(99), 1.0)
        self.assertEqual(interactions.rating_to_weight("oops"), 0.0)

    def test_resolve_weight_priority(self) -> None:
        # explicit weight wins
        self.assertEqual(interactions.resolve_weight("dismiss", weight=0.5), 0.5)
        # rating maps to ~like magnitude
        self.assertEqual(interactions.resolve_weight("rate", rating=5), 1.5)
        # kind default
        self.assertEqual(interactions.resolve_weight("dismiss"), -1.0)
        self.assertEqual(interactions.resolve_weight("unknown-kind"), 0.0)


class AffinityTests(unittest.TestCase):
    def test_time_decay_is_deterministic(self) -> None:
        now = datetime(2026, 6, 16, tzinfo=timezone.utc)
        records = [
            {"ts": "2026-06-16T00:00:00+00:00", "kind": "click", "weight": 1.0,
             "themes": ["液冷"], "stocks": []},
            {"ts": "2026-06-02T00:00:00+00:00", "kind": "like", "weight": 1.5,
             "themes": ["液冷"], "stocks": ["中际旭创"]},
        ]
        aff = interactions.compute_affinity(records, now=now, half_life_days=14.0)
        by_label = {a.label: a for a in aff}
        # 14 天前权重衰减一半：液冷 = 1.0*1 + 1.5*0.5 = 1.75；中际旭创 = 1.5*0.5 = 0.75
        self.assertAlmostEqual(by_label["液冷"].score, 1.75, places=3)
        self.assertEqual(by_label["液冷"].kind, "theme")
        self.assertAlmostEqual(by_label["中际旭创"].score, 0.75, places=3)
        self.assertEqual(by_label["中际旭创"].kind, "stock")
        # 排序：分数降序
        self.assertEqual(aff[0].label, "液冷")

    def test_negative_weight_lowers_score(self) -> None:
        now = datetime(2026, 6, 16, tzinfo=timezone.utc)
        records = [
            {"ts": "2026-06-16T00:00:00+00:00", "kind": "dismiss", "weight": -1.0,
             "themes": ["钠电"], "stocks": []},
        ]
        aff = interactions.compute_affinity(records, now=now)
        self.assertEqual(len(aff), 1)
        self.assertLess(aff[0].score, 0)

    def test_zero_weight_records_ignored(self) -> None:
        aff = interactions.compute_affinity(
            [{"ts": "2026-06-16T00:00:00+00:00", "kind": "rate", "weight": 0.0,
              "themes": ["算力"], "stocks": []}],
            now=datetime(2026, 6, 16, tzinfo=timezone.utc),
        )
        self.assertEqual(aff, [])


class RankingBoostTests(unittest.TestCase):
    def test_empty_affinity_is_backward_compatible(self) -> None:
        ranked = rank_questions(_fresh(), asked=[], n=2, affinity=[])
        # 没有反馈 → 综合分高者（宏观，novelty/relevance 更高）排第一，无加成
        self.assertIn("宏观流动性", ranked[0].question)
        self.assertEqual(ranked[0].affinity_boost, 0.0)
        self.assertEqual(ranked[0].affinity_reasons, [])

    def test_affinity_boost_reorders_and_is_explainable(self) -> None:
        aff = [interactions.Affinity(label="液冷", norm="液冷", kind="theme", score=1.0)]
        ranked = rank_questions(_fresh(), asked=[], n=2, affinity=aff, boost_weight=0.2)
        # 液冷被近期点过 → 含「液冷」的问题被加成后反超
        self.assertIn("液冷", ranked[0].question)
        self.assertGreater(ranked[0].affinity_boost, 0.0)
        self.assertTrue(ranked[0].affinity_reasons)
        self.assertIn("液冷", ranked[0].affinity_reasons[0])
        self.assertIn("题材", ranked[0].affinity_reasons[0])

    def test_boost_weight_zero_disables(self) -> None:
        aff = [interactions.Affinity(label="液冷", norm="液冷", kind="theme", score=5.0)]
        ranked = rank_questions(_fresh(), asked=[], n=2, affinity=aff, boost_weight=0.0)
        self.assertIn("宏观流动性", ranked[0].question)
        self.assertEqual(ranked[0].affinity_boost, 0.0)


_CANNED = json.dumps({
    "questions": [
        {"question": "宏观流动性收紧后高位成簇的新高方向会怎样退潮",
         "novelty": 0.85, "relevance": 0.85},
        {"question": "液冷渗透率拐点对中际旭创毛利率意味着什么",
         "novelty": 0.7, "relevance": 0.7},
        {"question": "固态电池量产推迟会先杀哪个上游材料的逻辑",
         "novelty": 0.6, "relevance": 0.6},
    ]
}, ensure_ascii=False)


class GenerateWiringTests(unittest.TestCase):
    """end-to-end 反馈接入（mock LLM）——VM 无 LLM key 时由此覆盖排序加成链路。"""

    def test_generate_applies_affinity_boost(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ipath = os.path.join(d, "interactions.jsonl")
            interactions.record_interaction(ipath, kind="click", themes=["液冷"],
                                            stocks=["中际旭创"])
            with mock.patch.object(
                foresight.llm_refine, "complete",
                return_value=(_CANNED, mock.Mock(name="deepseek"), ""),
            ):
                result = generate(ForesightOptions(
                    n=3, candidates=3, use_memory=False,
                    interactions_file=ipath, affinity_boost=0.2,
                ))
            self.assertEqual(result.interactions_loaded, 1)
            self.assertGreaterEqual(result.affinity_applied, 1)
            # 含「液冷」的问题被加成后反超宏观问题排到第一
            self.assertIn("液冷", result.questions[0].question)
            self.assertGreater(result.questions[0].affinity_boost, 0.0)
            self.assertTrue(result.questions[0].affinity_reasons)

    def test_generate_no_interactions_is_unboosted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ipath = os.path.join(d, "interactions.jsonl")  # not created
            with mock.patch.object(
                foresight.llm_refine, "complete",
                return_value=(_CANNED, mock.Mock(name="deepseek"), ""),
            ):
                result = generate(ForesightOptions(
                    n=3, candidates=3, use_memory=False,
                    interactions_file=ipath, affinity_boost=0.2,
                ))
            self.assertEqual(result.interactions_loaded, 0)
            self.assertEqual(result.affinity_applied, 0)
            # 无反馈 → 宏观问题（novelty/relevance 更高）仍排第一
            self.assertIn("宏观流动性", result.questions[0].question)

    def test_no_interactions_flag_skips_loading(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ipath = os.path.join(d, "interactions.jsonl")
            interactions.record_interaction(ipath, kind="click", themes=["液冷"])
            with mock.patch.object(
                foresight.llm_refine, "complete",
                return_value=(_CANNED, mock.Mock(name="deepseek"), ""),
            ):
                result = generate(ForesightOptions(
                    n=3, candidates=3, use_memory=False,
                    interactions_file=ipath, use_interactions=False,
                ))
            self.assertEqual(result.interactions_loaded, 0)
            self.assertIsNone(result.interactions_path)
            self.assertEqual(result.affinity_applied, 0)


if __name__ == "__main__":
    unittest.main()
