from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services import corrections
from intelligence.services.memory_gate import MemoryCandidate, MemoryGate


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

    def test_validated_preference_requires_exact_explicit_correction(self) -> None:
        source = {
            "ts": "2026-07-27T10:00:00+00:00",
            "correction": "只追问会改变答案的歧义",
        }
        decision = MemoryGate().decide(
            MemoryCandidate(
                "preference-1",
                "user_preference",
                source["correction"],
                correction_ts=source["ts"],
            ),
            checkpoints=(),
            verdicts=(),
            corrections=(source,),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrections.jsonl"
            _, record = corrections.record_validated_preference(
                path,
                preference=source["correction"],
                decision=decision,
            )

            self.assertEqual(record["promotion"]["candidate_id"], "preference-1")
            self.assertEqual(
                record["promotion"]["provenance"]["correction_ts"],
                source["ts"],
            )

    def test_validated_preference_rejects_ineligible_decision(self) -> None:
        decision = MemoryGate().decide(
            MemoryCandidate(
                "volatile-1",
                "volatile_fact",
                "今日价格 123 元",
                is_volatile=True,
            ),
            checkpoints=(),
            verdicts=(),
            corrections=(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrections.jsonl"
            with self.assertRaises(ValueError):
                corrections.record_validated_preference(
                    path,
                    preference="今日价格 123 元",
                    decision=decision,
                )
            self.assertFalse(path.exists())

    def test_validated_preference_rejects_checkpoint_lesson_authority(self) -> None:
        text = "估值判断应检查反证"
        decision = MemoryGate().decide(
            MemoryCandidate(
                "lesson-1",
                "decision_lesson",
                text,
                checkpoint_id="c1",
            ),
            checkpoints=({"id": "c1", "claim": "已回检"},),
            verdicts=({"id": "c1", "verdict": "hit"},),
            corrections=(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrections.jsonl"
            with self.assertRaises(ValueError):
                corrections.record_validated_preference(
                    path,
                    preference=text,
                    decision=decision,
                )
            self.assertFalse(path.exists())


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

    def test_resident_principles_ignore_theme_and_skip_empty_principle(self) -> None:
        records = [
            {"ts": "t1", "correction": "无原则纠偏", "themes": ["液冷"]},
            {"ts": "t2", "correction": "有原则", "principle": "双红看边际量", "themes": ["液冷"]},
            {"ts": "t3", "correction": "更新的原则", "principle": "跟踪只报变化", "themes": ["固态电池"]},
        ]
        resident = corrections.select_resident_principles(records, limit=5)
        self.assertEqual([r["ts"] for r in resident], ["t3", "t2"])


if __name__ == "__main__":
    unittest.main()
