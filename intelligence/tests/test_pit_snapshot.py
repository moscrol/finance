from __future__ import annotations

import gzip
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from intelligence.eval.pit_snapshot import (
    build_daily_snapshot,
    build_historical_inventory,
    freeze_daily_snapshot,
    validate_frozen_snapshot,
)


class PitSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import duckdb
        except Exception:
            self.skipTest("duckdb is not installed")
        self.duckdb = duckdb

    def _repo(self, root: Path, name: str) -> Path:
        repo = root / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return repo

    def _commit(self, repo: Path, path: str, content: str, committed_at: str) -> None:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", path], check=True)
        env = {
            "GIT_AUTHOR_DATE": committed_at,
            "GIT_COMMITTER_DATE": committed_at,
        }
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-q",
                "-m",
                path,
            ],
            check=True,
            env={**os.environ, **env},
        )

    def _db(self, root: Path) -> Path:
        path = root / "market.duckdb"
        con = self.duckdb.connect(str(path))
        try:
            con.execute(
                """
                CREATE TABLE dim_sector (
                    sector_ts_code VARCHAR,
                    is_active BOOLEAN
                )
                """
            )
            con.execute("INSERT INTO dim_sector VALUES ('S1', TRUE)")
            table_columns = {
                "fact_market_daily": "advancers INTEGER",
                "fact_sector_daily": "sector_ts_code VARCHAR",
                "fact_sw_l1_daily": "sw_l1_code VARCHAR",
                "fact_sector_stock_daily": "sector_ts_code VARCHAR, stock_ts_code VARCHAR",
                "fact_stock_daily": "stock_ts_code VARCHAR",
                "fact_stock_high_daily": "stock_ts_code VARCHAR",
                "fact_theme_limit_heat_daily": (
                    "sector_name VARCHAR, "
                    "source_update_time TIMESTAMP, "
                    "source VARCHAR"
                ),
                "fact_theme_limit_stock_daily": "stock_ts_code VARCHAR",
                "fact_limit_advance_daily": "stock_ts_code VARCHAR",
                "fact_limit_advance_presence": "stock_ts_code VARCHAR",
                "fact_mainline_sector_daily": "sector_ts_code VARCHAR",
                "fact_mainline_theme_daily": "sector_name VARCHAR",
                "fact_mainline_stock_daily": "stock_ts_code VARCHAR",
                "fact_theme_flow_daily": "sector_name VARCHAR",
            }
            for table, extra in table_columns.items():
                con.execute(
                    f"""
                    CREATE TABLE {table} (
                        trade_date DATE,
                        {extra},
                        updated_at TIMESTAMP
                    )
                    """
                )
            con.execute(
                """
                INSERT INTO fact_market_daily VALUES
                ('2026-07-09', 3000, '2026-07-09 18:00:00'),
                ('2026-07-10', 3200, '2026-07-10 18:00:00')
                """
            )
            required = {
                "fact_sector_daily": "('2026-07-10', 'S1', '2026-07-10 18:00:00')",
                "fact_sw_l1_daily": "('2026-07-10', 'L1', '2026-07-10 18:00:00')",
                "fact_sector_stock_daily": (
                    "('2026-07-10', 'S1', '000001', '2026-07-10 18:00:00')"
                ),
                "fact_stock_daily": "('2026-07-10', '000001', '2026-07-10 18:00:00')",
                "fact_stock_high_daily": (
                    "('2026-07-10', '000001', '2026-07-10 18:00:00')"
                ),
            }
            for table, values in required.items():
                con.execute(f"INSERT INTO {table} VALUES {values}")
            con.execute(
                """
                INSERT INTO fact_theme_limit_heat_daily VALUES
                (
                    '2026-07-10',
                    '算力',
                    '2026-07-10 17:50:00',
                    'fupanhui',
                    '2026-07-10 18:00:00'
                )
                """
            )
        finally:
            con.close()
        return path

    def test_freeze_writes_immutable_pair_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            finance = self._repo(root, "finance")
            wiki = self._repo(root, "wiki")
            self._commit(finance, "README.md", "finance", "2026-07-10T10:00:00+08:00")
            self._commit(wiki, "README.md", "wiki", "2026-07-10T10:00:00+08:00")
            out = root / "snapshots"
            manifest = freeze_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
                out_dir=out,
            )
            self.assertEqual(manifest["status"], "frozen")
            self.assertEqual(manifest["write_status"], "written")
            snapshot_path = out / "2026-07-10.snapshot.json.gz"
            manifest_path = out / "2026-07-10.manifest.json"
            snapshot = json.loads(gzip.decompress(snapshot_path.read_bytes()))
            self.assertEqual(
                snapshot["schema_version"],
                "pit-daily-snapshot-1.1",
            )
            self.assertEqual(snapshot["boundary"]["max_embedded_date"], "2026-07-10")
            self.assertFalse(snapshot["boundary"]["outcome_data_included"])
            row_pit = snapshot["data"]["fact_market_daily"][-1]["_pit"]
            self.assertEqual(row_pit["valid_time"], "2026-07-10")
            self.assertEqual(row_pit["known_at"], "2026-07-10T18:00:00")
            self.assertEqual(row_pit["source_time_kind"], "ingestion_fallback")
            source_pit = snapshot["data"]["fact_theme_limit_heat_daily"][0][
                "_pit"
            ]
            self.assertEqual(
                source_pit["source_time"],
                "2026-07-10T17:50:00",
            )
            self.assertEqual(
                source_pit["source_time_kind"],
                "source_publication",
            )
            self.assertEqual(source_pit["source"], "fupanhui")
            self.assertTrue(manifest["replay_eligible"])
            self.assertEqual(
                validate_frozen_snapshot(out, "2026-07-10")[
                    "validation_status"
                ],
                "valid",
            )
            self.assertEqual(snapshot_path.stat().st_mode & 0o777, 0o444)
            self.assertEqual(manifest_path.stat().st_mode & 0o777, 0o444)

            repeated = freeze_daily_snapshot(
                db,
                as_of=None,
                finance_root=finance,
                kb_root=wiki,
                out_dir=out,
            )
            self.assertEqual(repeated["write_status"], "already_frozen")

    def test_manifest_chain_detects_previous_manifest_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            finance = self._repo(root, "finance")
            wiki = self._repo(root, "wiki")
            self._commit(
                finance,
                "README.md",
                "finance",
                "2026-07-09T10:00:00+08:00",
            )
            self._commit(
                wiki,
                "README.md",
                "wiki",
                "2026-07-09T10:00:00+08:00",
            )
            out = root / "snapshots"
            freeze_daily_snapshot(
                db,
                as_of="2026-07-09",
                finance_root=finance,
                kb_root=wiki,
                out_dir=out,
            )
            second = freeze_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
                out_dir=out,
            )
            self.assertEqual(
                second["previous_manifest"]["as_of"],
                "2026-07-09",
            )
            previous = out / "2026-07-09.manifest.json"
            previous.chmod(0o644)
            previous.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "chain mismatch"):
                validate_frozen_snapshot(out, "2026-07-10")

    def test_dirty_repository_blocks_replay_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            finance = self._repo(root, "finance")
            wiki = self._repo(root, "wiki")
            self._commit(
                finance,
                "README.md",
                "finance",
                "2026-07-10T10:00:00+08:00",
            )
            self._commit(
                wiki,
                "README.md",
                "wiki",
                "2026-07-10T10:00:00+08:00",
            )
            (wiki / "dirty.md").write_text("dirty", encoding="utf-8")
            _, manifest = build_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
            )
            self.assertFalse(manifest["replay_eligible"])
            self.assertIn(
                "wiki_dirty_worktree",
                manifest["repository_gaps"],
            )

    def test_dry_run_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            finance = self._repo(root, "finance")
            wiki = self._repo(root, "wiki")
            self._commit(finance, "README.md", "finance", "2026-07-10T10:00:00+08:00")
            self._commit(wiki, "README.md", "wiki", "2026-07-10T10:00:00+08:00")
            out = root / "snapshots"
            manifest = freeze_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
                out_dir=out,
                dry_run=True,
            )
            self.assertEqual(manifest["write_status"], "dry_run")
            self.assertFalse(out.exists())

    def test_rows_written_after_d0_cutoff_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            con = self.duckdb.connect(str(db))
            try:
                con.execute(
                    """
                    UPDATE fact_sw_l1_daily
                    SET updated_at = '2026-07-11 00:10:00'
                    WHERE trade_date = '2026-07-10'
                    """
                )
            finally:
                con.close()
            finance = self._repo(root, "finance")
            wiki = self._repo(root, "wiki")
            self._commit(finance, "README.md", "finance", "2026-07-10T10:00:00+08:00")
            self._commit(wiki, "README.md", "wiki", "2026-07-10T10:00:00+08:00")
            snapshot, manifest = build_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
            )
            self.assertEqual(manifest["status"], "pending")
            self.assertIn("fact_sw_l1_daily", manifest["required_failures"])
            self.assertEqual(
                manifest["tables"]["fact_sw_l1_daily"]["after_cutoff_rows"], 1
            )
            self.assertEqual(snapshot["data"]["fact_sw_l1_daily"], [])

    def test_inventory_only_accepts_artifact_committed_before_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            finance = self._repo(root, "finance")
            wiki = self._repo(root, "wiki")
            self._commit(
                finance,
                "market_feature_store/exports/2026-07-10-daily-agent.json",
                "{}",
                "2026-07-10T20:00:00+08:00",
            )
            self._commit(
                wiki,
                "raw/2026-07-10-note.md",
                "late",
                "2026-07-11T09:00:00+08:00",
            )
            con = self.duckdb.connect(str(db))
            try:
                for table in (
                    "fact_market_daily",
                    "fact_sector_daily",
                    "fact_stock_daily",
                ):
                    con.execute(
                        f"""
                        UPDATE {table}
                        SET updated_at = '2026-07-12 09:00:00'
                        WHERE trade_date = '2026-07-10'
                        """
                    )
            finally:
                con.close()
            inventory = build_historical_inventory(
                db,
                finance_root=finance,
                kb_root=wiki,
                start="2026-07-10",
                end="2026-07-10",
            )
            case = inventory["cases"][0]
            self.assertEqual(case["status"], "artifact_candidate")
            self.assertEqual(case["candidate_scope"], "market_state")
            self.assertEqual(case["repositories"]["finance"]["artifact_count"], 1)
            self.assertEqual(case["repositories"]["wiki"]["artifact_count"], 0)


if __name__ == "__main__":
    unittest.main()
