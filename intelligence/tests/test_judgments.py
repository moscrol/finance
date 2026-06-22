from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services import judgments


class RecordJudgmentTests(unittest.TestCase):
    def test_record_appends_and_returns_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judgments.jsonl"
            p, rec = judgments.record_judgment(
                path,
                memo="**核心判断**：HVLP铜箔技术验证完成但产能爬坡滞后",
                themes=["铜箔", "铜箔"],
                stocks=["铜冠铜箔"],
                session_id="2026-06-18-1530",
            )
            self.assertEqual(p, path)
            self.assertEqual(rec["memo"], "**核心判断**：HVLP铜箔技术验证完成但产能爬坡滞后")
            self.assertEqual(rec["themes"], ["铜箔"])  # 去重
            self.assertEqual(rec["stocks"], ["铜冠铜箔"])
            self.assertEqual(rec["session_id"], "2026-06-18-1530")
            self.assertIn("ts", rec)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["memo"], rec["memo"])

    def test_empty_memo_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judgments.jsonl"
            with self.assertRaises(ValueError):
                judgments.record_judgment(path, memo="   ")
            self.assertFalse(path.exists())


class LoadJudgmentsTests(unittest.TestCase):
    def test_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recs, warn = judgments.load_judgments(Path(tmp) / "nope.jsonl")
            self.assertEqual(recs, [])
            self.assertIsNone(warn)

    def test_window_keeps_most_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judgments.jsonl"
            for i in range(5):
                judgments.record_judgment(path, memo=f"判断{i}", ts=f"2026-06-1{i}T00:00:00")
            recs, warn = judgments.load_judgments(path, window=2)
            self.assertIsNone(warn)
            self.assertEqual([r["memo"] for r in recs], ["判断3", "判断4"])

    def test_skips_blank_and_malformed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judgments.jsonl"
            path.write_text(
                '{"memo": "有效"}\n\nnot-json\n{"memo": "   "}\n',
                encoding="utf-8",
            )
            recs, warn = judgments.load_judgments(path)
            self.assertIsNone(warn)
            self.assertEqual([r["memo"] for r in recs], ["有效"])


class RenderForPromptTests(unittest.TestCase):
    def test_recent_first_with_theme_and_date(self) -> None:
        records = [
            {"memo": "判断A", "themes": ["液冷"], "ts": "2026-06-10T00:00:00"},
            {"memo": "判断B", "themes": ["铜箔"], "stocks": ["铜冠铜箔"], "ts": "2026-06-18T00:00:00"},
        ]
        rendered = judgments.render_for_prompt(records)
        lines = rendered.splitlines()
        # 最近的（判断B）在最前
        self.assertEqual(lines[0], "- 铜箔、铜冠铜箔：判断B（2026-06-18）")
        self.assertEqual(lines[1], "- 液冷：判断A（2026-06-10）")

    def test_no_theme_falls_back_to_bare_memo(self) -> None:
        rendered = judgments.render_for_prompt([{"memo": "裸判断", "ts": "2026-06-18T00:00:00"}])
        self.assertEqual(rendered, "- 裸判断（2026-06-18）")

    def test_empty_records_render_empty(self) -> None:
        self.assertEqual(judgments.render_for_prompt([]), "")


if __name__ == "__main__":
    unittest.main()
