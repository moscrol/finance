from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services import corrections


class RecordCorrectionTests(unittest.TestCase):
    def test_record_appends_and_returns_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrections.jsonl"
            p, rec = corrections.record_correction(
                path,
                correction="先判断在哪一阶再下结论",
                original="氟化工要爆发了",
                principle="分级不二元",
                themes=["氟化工", "氟化工"],
            )
            self.assertEqual(p, path)
            self.assertEqual(rec["correction"], "先判断在哪一阶再下结论")
            self.assertEqual(rec["original"], "氟化工要爆发了")
            self.assertEqual(rec["principle"], "分级不二元")
            self.assertEqual(rec["themes"], ["氟化工"])  # 去重
            self.assertIn("ts", rec)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["correction"], "先判断在哪一阶再下结论")

    def test_empty_correction_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrections.jsonl"
            with self.assertRaises(ValueError):
                corrections.record_correction(path, correction="   ")

    def test_optional_fields_omitted_when_blank(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrections.jsonl"
            _, rec = corrections.record_correction(path, correction="只说纠正")
            self.assertNotIn("original", rec)
            self.assertNotIn("principle", rec)
            self.assertEqual(rec["themes"], [])


class LoadCorrectionsTests(unittest.TestCase):
    def test_missing_file_is_empty(self) -> None:
        recs, warn = corrections.load_corrections("/nonexistent/dir/c.jsonl")
        self.assertEqual(recs, [])
        self.assertIsNone(warn)

    def test_window_keeps_most_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.jsonl"
            for i in range(5):
                corrections.record_correction(path, correction=f"纠正{i}")
            recs, warn = corrections.load_corrections(path, window=2)
            self.assertIsNone(warn)
            self.assertEqual([r["correction"] for r in recs], ["纠正3", "纠正4"])

    def test_skips_blank_and_malformed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"correction": "有效"}, ensure_ascii=False),
                        "",
                        "not json",
                        json.dumps({"correction": ""}, ensure_ascii=False),
                        json.dumps({"no_correction": "x"}, ensure_ascii=False),
                    ]
                ),
                encoding="utf-8",
            )
            recs, _ = corrections.load_corrections(path)
            self.assertEqual([r["correction"] for r in recs], ["有效"])


class RenderForPromptTests(unittest.TestCase):
    def test_render_most_recent_first_with_principle(self) -> None:
        records = [
            {"correction": "旧的纠正", "principle": "原则A"},
            {"correction": "新的纠正", "original": "答错的话", "themes": ["铜箔"]},
        ]
        out = corrections.render_for_prompt(records)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        # 最近的在最前
        self.assertIn("新的纠正", lines[0])
        self.assertIn("别再说「答错的话」", lines[0])
        self.assertIn("（铜箔）", lines[0])
        self.assertIn("原则：原则A", lines[1])

    def test_render_empty_records(self) -> None:
        self.assertEqual(corrections.render_for_prompt([]), "")


if __name__ == "__main__":
    unittest.main()
