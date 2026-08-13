from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from intelligence.services import kb_queue_receive


FAKE_RECEIVE = """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

argv_log = Path(__file__).with_name("received-argv.json")
argv_log.write_text(json.dumps(sys.argv, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"received_path": "ok.json", "task_count": 1, "idempotent": False}))
"""

FAIL_RECEIVE = """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

Path(__file__).with_name("received-argv.json").write_text(
    json.dumps(sys.argv, ensure_ascii=False), encoding="utf-8"
)
print("boom", file=sys.stderr)
raise SystemExit(1)
"""


class KbQueueReceiveTests(unittest.TestCase):
    def _queue_dir(self, root: Path, date: str = "2026-08-13") -> Path:
        exports = root / "finance" / "market_feature_store" / "exports"
        exports.mkdir(parents=True)
        queue = exports / f"{date}-kb-ingest-queue.json"
        queue.write_text("{}", encoding="utf-8")
        return queue

    def _fake_script(self, root: Path, source: str = FAKE_RECEIVE) -> Path:
        script = root / "kb" / "scripts" / "kb_ingest_queue.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(source, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return script

    def test_skips_when_queue_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = kb_queue_receive.receive_kb_ingest_queue(
                date="2026-08-13",
                finance_root=root / "finance",
                kb_wiki=root / "wiki",
            )
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.argv, [])
        self.assertIn("queue missing", result.reason)

    def test_skips_when_receive_script_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._queue_dir(root)
            result = kb_queue_receive.receive_kb_ingest_queue(
                date="2026-08-13",
                finance_root=root / "finance",
                kb_wiki=root / "wiki",
            )
        self.assertEqual(result.status, "skipped")
        self.assertIn("receive script missing", result.reason)

    def test_calls_receive_only_and_never_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = self._queue_dir(root)
            script = self._fake_script(root)
            wiki = root / "kb" / "wiki"
            wiki.mkdir()
            result = kb_queue_receive.receive_kb_ingest_queue(
                date="2026-08-13",
                finance_root=root / "finance",
                kb_wiki=wiki,
                python=sys.executable,
            )
            argv = json.loads((script.parent / "received-argv.json").read_text(encoding="utf-8"))

        self.assertEqual(result.status, "received")
        self.assertEqual(result.payload["task_count"], 1)
        self.assertEqual(argv[1], "receive")
        self.assertEqual(argv[2], str(queue))
        self.assertIn("--wiki-root", argv)
        self.assertNotIn("--apply", argv)
        self.assertNotIn("apply", argv)
        self.assertNotIn("mark", argv)
        self.assertTrue(all(token != "--apply" for token in result.argv))

    def test_receive_failure_is_warn_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._queue_dir(root)
            script = self._fake_script(root, FAIL_RECEIVE)
            wiki = root / "kb" / "wiki"
            wiki.mkdir()
            result = kb_queue_receive.receive_kb_ingest_queue(
                date="2026-08-13",
                finance_root=root / "finance",
                kb_wiki=wiki,
                python=sys.executable,
                receive_script=script,
            )
        self.assertEqual(result.status, "warn")
        self.assertIsNone(result.payload)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
