import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.logic_market_match import (
    LABEL_DATA_GAP,
    LABEL_NOISE,
    LABEL_OLD_WAKEUP,
    available_candidate_dates,
    batch_match_logic_to_market,
    match_logic_to_market,
)


class LogicMarketMatchTest(unittest.TestCase):
    def make_fixture(self, root: Path):
        exports = root / "exports"
        wiki = root / "wiki"
        relations = wiki / "relations"
        sources = wiki / "sources"
        exports.mkdir(parents=True)
        relations.mkdir(parents=True)
        sources.mkdir(parents=True)
        (exports / "2026-06-11-theme-candidates.json").write_text(
            json.dumps(
                {
                    "found": True,
                    "trade_date": "2026-06-11",
                    "candidates": [
                        {
                            "market_theme": "液冷服务器",
                            "canonical_concept": "液冷服务器",
                            "priority_score": 88.0,
                            "trigger_types": ["double_red", "new_high_cluster"],
                            "market_evidence": {
                                "strong_stocks": [
                                    {"stock_name": "强瑞技术", "stock_ts_code": "301128.SZ", "pct_chg": 12.3, "amount": 12.1}
                                ]
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (relations / "concept_graph.json").write_text(
            json.dumps({"concepts": {"液冷服务器": {"sources": ["[[液冷服务器深度报告]]"]}}}, ensure_ascii=False),
            encoding="utf-8",
        )
        (relations / "entity_exposures.json").write_text(
            json.dumps(
                {
                    "entities": {
                        "强瑞技术": {
                            "codes": ["301128"],
                            "concepts": {
                                "液冷服务器": {
                                    "role": "液冷测试设备",
                                    "strength": "core",
                                    "confidence": "high",
                                    "source": "[[液冷服务器深度报告]]",
                                }
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (relations / "evidence_index.json").write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "target": "液冷服务器",
                            "target_type": "concept",
                            "evidence": "液冷服务器需求随 AI 算力升级提升。",
                            "source": "[[液冷服务器深度报告]]",
                            "source_date": "2026-06-01",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (sources / "液冷服务器深度报告.md").write_text("# 液冷服务器深度报告\n", encoding="utf-8")
        return exports, wiki

    def test_old_logic_wakeup_when_market_and_knowledge_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports, wiki = self.make_fixture(Path(tmp))

            result = match_logic_to_market("液冷服务器", "2026-06-11", exports, wiki)

            self.assertEqual(result.classification, LABEL_OLD_WAKEUP)
            self.assertTrue(result.market_found)
            self.assertEqual(result.matched_theme, "液冷服务器")
            self.assertEqual(len(result.entity_exposures), 1)
            self.assertTrue(result.source_traces[0].source_exists)

    def test_data_gap_when_source_trace_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports, wiki = self.make_fixture(Path(tmp))
            (wiki / "sources" / "液冷服务器深度报告.md").unlink()

            result = match_logic_to_market("液冷服务器", "2026-06-11", exports, wiki)

            self.assertEqual(result.classification, LABEL_OLD_WAKEUP)
            self.assertIn("missing_source_trace", result.data_gaps)
            self.assertFalse(result.source_traces[0].source_exists)

    def test_data_gap_when_market_exists_but_knowledge_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports, wiki = self.make_fixture(Path(tmp))
            (wiki / "relations" / "concept_graph.json").write_text(json.dumps({"concepts": {}}, ensure_ascii=False), encoding="utf-8")
            (wiki / "relations" / "entity_exposures.json").write_text(json.dumps({"entities": {}}, ensure_ascii=False), encoding="utf-8")
            (wiki / "relations" / "evidence_index.json").write_text(json.dumps({"items": []}, ensure_ascii=False), encoding="utf-8")

            result = match_logic_to_market("液冷服务器", "2026-06-11", exports, wiki)

            self.assertEqual(result.classification, LABEL_DATA_GAP)
            self.assertIn("missing_concept", result.data_gaps)
            self.assertIn("missing_entity_exposure", result.data_gaps)
            self.assertIn("missing_evidence", result.data_gaps)

    def test_placeholder_market_theme_is_not_treated_as_missing_concept(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports, wiki = self.make_fixture(Path(tmp))
            path = exports / "2026-06-11-theme-candidates.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["candidates"].append(
                {
                    "market_theme": "连板未映射",
                    "canonical_concept": "连板未映射",
                    "priority_score": 183.0,
                    "trigger_types": ["limit_advance_cluster"],
                    "market_evidence": {"advance": {"stock_count": 11, "max_boards": 3}},
                }
            )
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

            result = match_logic_to_market("连板未映射", "2026-06-11", exports, wiki)

            self.assertEqual(result.classification, LABEL_NOISE)
            self.assertEqual(result.data_gaps, ["placeholder_market_theme"])
            self.assertNotIn("missing_concept", result.data_gaps)

    def test_available_candidate_dates_and_batch_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports, wiki = self.make_fixture(Path(tmp))
            (exports / "2026-06-10-theme-candidates.json").write_text(
                json.dumps({"found": True, "trade_date": "2026-06-10", "candidates": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            self.assertEqual(available_candidate_dates(exports), ["2026-06-10", "2026-06-11"])

            result = batch_match_logic_to_market(
                dates=["2026-06-11"],
                top_per_date=1,
                exports_dir=exports,
                kb_wiki=wiki,
            )

            self.assertEqual(result.scanned_count, 1)
            self.assertEqual(result.summary["old_logic_wakeup_count"], 1)
            self.assertEqual(result.gap_queue, [])

    def test_batch_queue_prioritizes_missing_knowledge(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports, wiki = self.make_fixture(Path(tmp))
            (wiki / "relations" / "concept_graph.json").write_text(json.dumps({"concepts": {}}, ensure_ascii=False), encoding="utf-8")
            (wiki / "relations" / "entity_exposures.json").write_text(json.dumps({"entities": {}}, ensure_ascii=False), encoding="utf-8")
            (wiki / "relations" / "evidence_index.json").write_text(json.dumps({"items": []}, ensure_ascii=False), encoding="utf-8")

            result = batch_match_logic_to_market(
                dates=["2026-06-11"],
                top_per_date=1,
                exports_dir=exports,
                kb_wiki=wiki,
            )

            self.assertEqual(len(result.gap_queue), 1)
            self.assertEqual(result.gap_queue[0].classification, LABEL_DATA_GAP)
            self.assertIn("missing_concept", result.gap_queue[0].data_gaps)


if __name__ == "__main__":
    unittest.main()
