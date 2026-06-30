from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.enrich_ingest_status_with_index import enrich_ledger_with_index, render_markdown


class IngestStatusIndexTest(unittest.TestCase):
    def test_enriches_items_with_concept_page_and_rag_index_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            kb_root = root / "kb"
            concepts = kb_root / "wiki" / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "光刻机.md").write_text("# 光刻机\n", encoding="utf-8")
            index = kb_root / ".rag_index" / "chunks.jsonl"
            index.parent.mkdir(parents=True)
            index.write_text('{"file_path":"wiki/concepts/光刻机.md"}\n', encoding="utf-8")
            ledger = {
                "trade_date": "2026-06-26",
                "status_counts": {"candidate_detected": 3},
                "items": [
                    {"id": "a", "ingest_status": "candidate_detected", "theme": "光刻机", "canonical_concept": "光刻机", "rank": 1},
                    {"id": "b", "ingest_status": "candidate_detected", "theme": "存储芯片", "canonical_concept": "存储芯片", "rank": 2},
                    {"id": "c", "ingest_status": "candidate_detected", "theme": "连板未映射", "canonical_concept": "", "rank": 3},
                ],
            }

            payload = enrich_ledger_with_index(ledger, kb_root)

        self.assertEqual(payload["index_status_counts"], {"not_in_kb": 2, "rag_indexed": 1})
        self.assertEqual(payload["index_probe_counts"], {"concept_page_exists": 1, "rag_indexed": 1, "not_indexed": 2})
        self.assertEqual(payload["items"][0]["index_status"], "rag_indexed")
        self.assertTrue(payload["items"][0]["index_probe"]["concept_page_exists"])
        self.assertIn("Ingest Status Index Probe", render_markdown(payload))

    def test_concept_page_exists_without_index_is_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            kb_root = Path(td) / "kb"
            concepts = kb_root / "wiki" / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "CPO.md").write_text("# CPO\n", encoding="utf-8")
            ledger = {
                "trade_date": "2026-06-26",
                "items": [
                    {"id": "a", "ingest_status": "candidate_detected", "theme": "CPO", "canonical_concept": "CPO"},
                ],
            }

            payload = enrich_ledger_with_index(ledger, kb_root)

        self.assertEqual(payload["items"][0]["index_status"], "concept_page_exists")
        self.assertEqual(payload["index_probe_counts"], {"concept_page_exists": 1, "rag_indexed": 0, "not_indexed": 1})


if __name__ == "__main__":
    unittest.main()
