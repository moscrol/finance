from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

import duckdb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import db_delta_export as exp  # noqa: E402
from scripts import db_baseline_export as baseline_export  # noqa: E402
from scripts import db_delta_pull as pull  # noqa: E402

DATE = "2026-07-10"


def _build_db(path: str, val: int) -> None:
    con = duckdb.connect(path)
    con.execute("create table fact_a (trade_date varchar, val integer)")
    con.execute("insert into fact_a values (?, ?)", [DATE, val])
    con.close()


def _make_delta(db: str, out_zip: str) -> None:
    old = sys.argv
    sys.argv = ["db_delta_export.py", "--trade-date", DATE, "--db", db, "--out", out_zip]
    try:
        assert exp.main() == 0
    finally:
        sys.argv = old


def _make_baseline_zip(db: str, out_zip: str) -> None:
    baseline_export.export_baseline(db, out_zip, DATE)


class DeltaPullRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.sync = os.path.join(self.tmp, "sync")
        os.makedirs(self.sync)
        self.source_db = os.path.join(self.tmp, "source.duckdb")
        self.target_db = os.path.join(self.tmp, "target.duckdb")
        self.state = os.path.join(self.tmp, "state.json")
        _build_db(self.source_db, 7)
        _make_baseline_zip(self.source_db, os.path.join(self.sync, f"mfs-baseline-{DATE}.zip"))
        _make_delta(self.source_db, os.path.join(self.sync, f"mfs-delta-{DATE}.zip"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_pull(self) -> int:
        old = sys.argv
        sys.argv = [
            "db_delta_pull.py",
            "--sync-dir", self.sync,
            "--db", self.target_db,
            "--state", self.state,
        ]
        try:
            return pull.main()
        finally:
            sys.argv = old

    def test_missing_db_restores_baseline_before_delta(self) -> None:
        self.assertFalse(os.path.exists(self.target_db))
        self.assertEqual(self._run_pull(), 0)

        con = duckdb.connect(self.target_db, read_only=True)
        try:
            rows = con.execute("select val from fact_a where trade_date=?", [DATE]).fetchall()
        finally:
            con.close()
        self.assertEqual(rows, [(7,)])

        state = json.load(open(self.state, encoding="utf-8"))
        self.assertEqual(state["applied_baselines"], [f"mfs-baseline-{DATE}.zip"])
        self.assertEqual(state["applied_deltas"], [f"mfs-delta-{DATE}.zip"])
        with open(self.target_db + ".delta_schema_ledger.jsonl", encoding="utf-8") as handle:
            events = [json.loads(line)["event"] for line in handle if line.strip()]
        self.assertEqual(events, ["baseline_restore", "delta_import"])

    def test_baseline_restore_rejects_sha_mismatch_without_creating_db(self) -> None:
        bad_zip = os.path.join(self.sync, f"mfs-baseline-{DATE}.zip")
        with zipfile.ZipFile(bad_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("market_feature_store.duckdb", b"not a duckdb")
            archive.writestr("manifest.json", json.dumps({
                "schema_version": 1,
                "kind": "full_baseline",
                "trade_date": DATE,
                "db_file": "market_feature_store.duckdb",
                "sha256": "0" * 64,
            }))

        self.assertEqual(self._run_pull(), 2)
        self.assertFalse(os.path.exists(self.target_db))

    def test_corrupt_state_fails_closed(self) -> None:
        with open(self.state, "w", encoding="utf-8") as handle:
            handle.write("{not-json")

        self.assertEqual(self._run_pull(), 2)
        self.assertFalse(os.path.exists(self.target_db))


if __name__ == "__main__":
    unittest.main()
