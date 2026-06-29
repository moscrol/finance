from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_finhot_evidence_to_obsidian import (
    export_report,
    stable_candidate_id,
    validate_report,
    with_candidate_ids,
)


class FinHotEvidenceObsidianExportTest(unittest.TestCase):
    def _item(self, **overrides) -> dict:
        item = {
            "task_id": "task-001",
            "item_id": "finhot:1",
            "source": "巨潮公告",
            "published_at": "2026-06-26",
            "title": "英维克液冷服务器订单公告",
            "text": "英维克液冷服务器订单公告，客户验证推进。",
            "url": "https://www.cninfo.com.cn/new/disclosure",
            "evidence_layer": "L3_current_official_catalyst",
            "evidence_type": "order",
            "confidence": 0.92,
            "matched_entities": ["英维克"],
            "matched_theme_terms": ["液冷服务器"],
            "matched_fact_terms": ["订单", "客户"],
            "reason": "命中官方来源和事实词。",
        }
        item.update(overrides)
        return item

    def _report(self) -> dict:
        return {
            "generated_at": "2026-06-29T00:00:00+00:00",
            "trade_date": "2026-06-26",
            "source": "finhot-evidence-hunter",
            "read_only": True,
            "summary": {
                "task_count": 2,
                "matched_count": 6,
                "rejected_count": 2,
                "evidence_layer_counts": {
                    "L3_current_official_catalyst": 1,
                    "L3_historical_official_fact": 1,
                    "L2_official_baseline": 1,
                    "L3_candidate": 2,
                    "L1_signal": 1,
                },
            },
            "tasks": [
                {"task_id": "task-001", "theme": "液冷服务器", "concept": "液冷服务器"},
                {"task_id": "task-002", "theme": "数据中心", "concept": "数据中心"},
            ],
            "matched_items": [
                self._item(),
                self._item(task_id="task-002", item_id="finhot:1", confidence=0.87),
                self._item(task_id="task-001", item_id="finhot:2", evidence_layer="L3_historical_official_fact", title="英维克2025年年报", confidence=0.8),
                self._item(task_id="task-001", item_id="finhot:3", evidence_layer="L2_official_baseline", title="英维克业务介绍", confidence=0.7),
                self._item(task_id="task-001", item_id="finhot:4", source="财联社", evidence_layer="L3_candidate", title="英维克订单快讯", confidence=0.65, url="https://example.com/a"),
                self._item(task_id="task-001", item_id="finhot:5", source="财联社", evidence_layer="L3_candidate", title="英维克弱线索", confidence=0.4, url="https://example.com/b"),
                self._item(task_id="task-001", item_id="finhot:6", source="雪球", evidence_layer="L1_signal", title="英维克讨论", confidence=0.9, url="https://example.com/c"),
            ],
            "rejected_items": [
                {"task_id": "task-001", "item_id": "finhot:r1", "reject_reason": "entity_mismatch"},
                {"task_id": "task-001", "item_id": "finhot:r2", "reject_reason": "no_fact_term"},
            ],
            "warnings": [],
        }

    def _write_report(self, path: Path, report: dict | None = None) -> Path:
        path.write_text(json.dumps(report or self._report(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_stable_candidate_id_uses_task_item_url_and_layer(self) -> None:
        first = stable_candidate_id(self._item())
        second = stable_candidate_id(self._item(title="标题变化不影响 ID"))
        third = stable_candidate_id(self._item(task_id="task-002"))

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertEqual(len(first), 40)

    def test_with_candidate_ids_filters_allowed_layers_and_high_confidence_candidates(self) -> None:
        items = with_candidate_ids(self._report()["matched_items"], 0.6)
        layers = [item["evidence_layer"] for item in items]

        self.assertEqual(len(items), 5)
        self.assertIn("L3_current_official_catalyst", layers)
        self.assertIn("L3_historical_official_fact", layers)
        self.assertIn("L2_official_baseline", layers)
        self.assertEqual(layers.count("L3_candidate"), 1)
        self.assertNotIn("L1_signal", layers)
        self.assertTrue(all(item.get("candidate_id") for item in items))

    def test_export_report_writes_staging_markdown_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki = root / "wiki"
            wiki.mkdir()
            report_path = self._write_report(root / "report.json")

            result = export_report(report_path, wiki, date_text="2026-06-26")

            staging = Path(result["staging_note"])
            manifest_path = Path(result["manifest"])
            self.assertTrue(staging.exists())
            self.assertTrue(manifest_path.exists())
            self.assertEqual(result["selected_candidate_count"], 5)
            self.assertEqual(result["deduped_item_count"], 4)
            md = staging.read_text(encoding="utf-8")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("type: raw_staging", md)
            self.assertIn("## L3 当前官方催化候选", md)
            self.assertIn("task-001（液冷服务器）；task-002（数据中心）", md)
            self.assertIn("reject_reason_counts", md)
            self.assertEqual(manifest["date"], "2026-06-26")
            self.assertEqual(manifest["staging_note"], "raw/finhot-evidence-staging/2026-06-26-finhot-evidence-staging.md")
            self.assertEqual(len(manifest["approvals"]), 5)
            self.assertTrue(all(row["decision"] == "pending" for row in manifest["approvals"]))

    def test_export_report_can_filter_to_l3_and_hide_rejected_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki = root / "wiki"
            wiki.mkdir()
            report_path = self._write_report(root / "report.json")

            result = export_report(report_path, wiki, date_text="2026-06-26", min_layer="L3", include_rejected_summary=False)

            staging = Path(result["staging_note"])
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            md = staging.read_text(encoding="utf-8")
            self.assertEqual(result["selected_candidate_count"], 4)
            self.assertEqual(len(manifest["approvals"]), 4)
            self.assertNotIn("reject_reason_counts", md)
            self.assertNotIn("## 被拒绝或低置信线索摘要", md)
            self.assertIn("| - | - | - | - | - | - | - | - | - | - |", md)

    def test_export_report_refuses_to_overwrite_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki = root / "wiki"
            wiki.mkdir()
            report_path = self._write_report(root / "report.json")

            export_report(report_path, wiki, date_text="2026-06-26")

            with self.assertRaises(FileExistsError):
                export_report(report_path, wiki, date_text="2026-06-26")

            result = export_report(report_path, wiki, date_text="2026-06-26", overwrite=True)
            self.assertTrue(Path(result["staging_note"]).exists())

    def test_export_report_requires_existing_wiki_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = self._write_report(root / "report.json")

            with self.assertRaises(FileNotFoundError):
                export_report(report_path, root / "missing-wiki", date_text="2026-06-26")

    def test_validate_report_requires_evidence_hunter_fields(self) -> None:
        with self.assertRaises(ValueError):
            validate_report({"matched_items": []})


if __name__ == "__main__":
    unittest.main()
