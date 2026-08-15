from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services import corrections, judgments, memory_status


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )


class RecordStatusTests(unittest.TestCase):
    def test_appends_status_line_without_touching_history(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "judgments.jsonl"
            _write_jsonl(p, [{"ts": "2026-08-01T00:00:00", "memo": "旧判断"}])
            before = p.read_text(encoding="utf-8")
            _, rec = memory_status.record_status(
                p, target_ts="2026-08-01T00:00:00", status="archived", reason="过时"
            )
            after = p.read_text(encoding="utf-8")
        self.assertTrue(after.startswith(before))  # 历史行一字未改
        self.assertEqual(rec["record_type"], "memory_status")
        self.assertEqual(rec["status"], "archived")
        self.assertEqual(rec["reason"], "过时")

    def test_rejects_invalid_input(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.jsonl"
            with self.assertRaises(ValueError):
                memory_status.record_status(p, target_ts="", status="archived")
            with self.assertRaises(ValueError):
                memory_status.record_status(p, target_ts="t", status="deleted")


class ApplyOverridesTests(unittest.TestCase):
    def test_no_status_lines_is_identity(self) -> None:
        records = [
            {"ts": "t1", "memo": "a"},
            {"ts": "t2", "memo": "b"},
        ]
        self.assertEqual(memory_status.apply_status_overrides(records), records)

    def test_archived_and_rejected_suppressed(self) -> None:
        records = [
            {"ts": "t1", "memo": "a"},
            {"ts": "t2", "memo": "b"},
            {"record_type": "memory_status", "ts": "t3", "target_ts": "t1", "status": "archived"},
        ]
        out = memory_status.apply_status_overrides(records)
        self.assertEqual([r["ts"] for r in out], ["t2"])

    def test_latest_status_wins_reinstate(self) -> None:
        records = [
            {"ts": "t1", "memo": "a"},
            {"record_type": "memory_status", "ts": "t2", "target_ts": "t1", "status": "archived"},
            {"record_type": "memory_status", "ts": "t3", "target_ts": "t1", "status": "reinstated"},
        ]
        out = memory_status.apply_status_overrides(records)
        self.assertEqual([r["ts"] for r in out], ["t1"])


class RecordIdentityTests(unittest.TestCase):
    """Q3：记录身份 id=sha256(kind+ts+content)[:12]，同秒并发不碰撞；旧行仍认 ts。"""

    def test_same_second_records_get_distinct_ids(self) -> None:
        ts = "2026-08-15T09:00:00"
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "judgments.jsonl"
            _, rec_a = judgments.record_judgment(p, memo="判断A", ts=ts)
            _, rec_b = judgments.record_judgment(p, memo="判断B", ts=ts)
        self.assertEqual(rec_a["ts"], rec_b["ts"])  # 同秒
        self.assertNotEqual(rec_a["id"], rec_b["id"])  # id 不碰撞
        for rec in (rec_a, rec_b):
            self.assertRegex(rec["id"], r"^[0-9a-f]{12}$")
            self.assertEqual(
                rec["id"],
                memory_status.memory_record_id("judgment", ts, rec["memo"]),
            )

    def test_kind_separates_ledgers_with_same_ts_and_content(self) -> None:
        ts = "2026-08-15T09:00:00"
        self.assertNotEqual(
            memory_status.memory_record_id("judgment", ts, "同一段文本"),
            memory_status.memory_record_id("correction", ts, "同一段文本"),
        )

    def test_exit_by_id_suppresses_exactly_one_of_colliding_pair(self) -> None:
        ts = "2026-08-15T09:00:00"
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "judgments.jsonl"
            _, rec_a = judgments.record_judgment(p, memo="判断A", ts=ts)
            judgments.record_judgment(p, memo="判断B", ts=ts)
            memory_status.record_status(
                p, target_ts=rec_a["id"], status="archived", reason="过时"
            )
            records, warn = judgments.load_judgments(p)
        self.assertIsNone(warn)
        self.assertEqual([r["memo"] for r in records], ["判断B"])

    def test_legacy_ts_rows_still_exit_by_ts(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "corrections.jsonl"
            # 旧行：无 id（存量不回填）
            _write_jsonl(p, [{"ts": "t-legacy", "correction": "旧纠偏"}])
            _, rec_new = corrections.record_correction(p, correction="新纠偏")
            memory_status.record_status(p, target_ts="t-legacy", status="archived")
            records, warn = corrections.load_corrections(p)
        self.assertIsNone(warn)
        self.assertEqual([r["correction"] for r in records], ["新纠偏"])
        self.assertIn("id", rec_new)


class LoaderIntegrationTests(unittest.TestCase):
    def test_load_judgments_filters_archived(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "judgments.jsonl"
            _write_jsonl(
                p,
                [
                    {"ts": "t1", "memo": "过时判断", "themes": ["液冷"]},
                    {"ts": "t2", "memo": "现役判断", "themes": ["液冷"]},
                ],
            )
            memory_status.record_status(p, target_ts="t1", status="archived")
            records, warn = judgments.load_judgments(p)
        self.assertIsNone(warn)
        self.assertEqual([r["memo"] for r in records], ["现役判断"])

    def test_load_corrections_filters_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "corrections.jsonl"
            _write_jsonl(
                p,
                [
                    {"ts": "t1", "correction": "错记的纠偏"},
                    {"ts": "t2", "correction": "有效的纠偏"},
                ],
            )
            memory_status.record_status(p, target_ts="t1", status="rejected", reason="记错了")
            records, warn = corrections.load_corrections(p)
        self.assertIsNone(warn)
        self.assertEqual([r["correction"] for r in records], ["有效的纠偏"])

    def test_ratchet_no_status_lines_behavior_unchanged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "judgments.jsonl"
            recs = [{"ts": f"t{i}", "memo": f"m{i}"} for i in range(15)]
            _write_jsonl(p, recs)
            records, _ = judgments.load_judgments(p)  # 默认 window=10
        self.assertEqual(len(records), 10)
        self.assertEqual(records[0]["memo"], "m5")

    def test_status_lines_never_recalled_as_memory(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "corrections.jsonl"
            _write_jsonl(p, [{"ts": "t1", "correction": "有效"}])
            memory_status.record_status(p, target_ts="t1", status="reinstated")
            records, _ = corrections.load_corrections(p)
        self.assertEqual(len(records), 1)
        self.assertNotIn("record_type", records[0])


class CliTests(unittest.TestCase):
    def _run(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "intelligence.cli", "memory-status", *argv],
            capture_output=True,
            text=True,
        )

    def test_cli_archives_then_recall_excludes(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "judgments.jsonl"
            _write_jsonl(p, [{"ts": "2026-08-01T00:00:00", "memo": "老判断"}])
            proc = self._run(
                "--ledger", "judgments", "--target-ts", "2026-08-01T00:00:00",
                "--status", "archived", "--reason", "过时", "--ledger-file", str(p), "--json",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            records, _ = judgments.load_judgments(p)
        self.assertEqual(records, [])

    def test_cli_accepts_record_id_as_target(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "judgments.jsonl"
            _, rec = judgments.record_judgment(p, memo="按 id 退出", ts="2026-08-15T09:00:00")
            proc = self._run(
                "--ledger", "judgments", "--target-ts", rec["id"],
                "--status", "archived", "--reason", "同秒消歧", "--ledger-file", str(p),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            records, _ = judgments.load_judgments(p)
        self.assertEqual(records, [])

    def test_cli_refuses_dangling_target(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "judgments.jsonl"
            _write_jsonl(p, [{"ts": "t1", "memo": "x"}])
            proc = self._run(
                "--ledger", "judgments", "--target-ts", "不存在的ts",
                "--status", "archived", "--ledger-file", str(p),
            )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("目标记录不存在", proc.stderr)


if __name__ == "__main__":
    unittest.main()
