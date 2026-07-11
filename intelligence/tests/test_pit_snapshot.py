from __future__ import annotations

import gzip
import hashlib
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
from intelligence.services.content_delta import (
    build_content_delta,
)
from intelligence.services.fidelity_contract import (
    report_manifest_payload,
    seal_artifact,
)
from intelligence.tests.test_fidelity_contract import _valid_report


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

    def _write_manifest(
        self,
        path: Path,
        manifest: dict[str, object],
    ) -> None:
        payload = dict(manifest)
        payload.pop("manifest_sha", None)
        payload.pop("manifest_payload_sha256", None)
        digest = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        manifest["manifest_sha"] = digest
        manifest["manifest_payload_sha256"] = digest
        path.chmod(0o644)
        path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _daily_agent(
        self,
        finance: Path,
        wiki: Path,
    ) -> dict[str, object]:
        generator_commit = subprocess.run(
            ["git", "-C", str(finance), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        daily_agent = _valid_report()
        daily_agent["knowledge_snapshot"] = build_content_delta(
            wiki,
            captured_at=daily_agent["snapshot_captured_at"],
        )
        seal_artifact(
            daily_agent,
            artifact_kind="daily-agent",
            report_date="2026-07-10",
            generator_commit=generator_commit,
            snapshot_captured_at=daily_agent[
                "snapshot_captured_at"
            ],
            report_generated_at=daily_agent[
                "report_generated_at"
            ],
            manifest_payload=report_manifest_payload(daily_agent),
            run_id=daily_agent["run_id"],
        )
        return daily_agent

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
            self.assertEqual(manifest["status"], "frozen_with_gaps")
            self.assertEqual(manifest["write_status"], "written")
            snapshot_path = out / "2026-07-10.snapshot.json.gz"
            manifest_path = out / "2026-07-10.manifest.json"
            snapshot = json.loads(gzip.decompress(snapshot_path.read_bytes()))
            self.assertEqual(
                snapshot["schema_version"],
                "pit-daily-snapshot-1.3",
            )
            self.assertEqual(
                manifest["schema_version"],
                "pit-daily-manifest-1.3",
            )
            self.assertEqual(manifest["artifact_sha"], manifest["snapshot_sha256"])
            self.assertEqual(len(manifest["manifest_sha"]), 64)
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
            self.assertFalse(manifest["replay_eligible"])
            self.assertEqual(
                manifest["provenance_gaps"],
                [
                    "daily_agent_contract_not_linked",
                    "wiki_content_delta_not_replayable",
                ],
            )
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

    def test_contract_tampering_is_rejected(self) -> None:
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
            out = root / "snapshots"
            freeze_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
                out_dir=out,
            )
            path = out / "2026-07-10.manifest.json"
            original = path.read_text(encoding="utf-8")

            manifest = json.loads(original)
            manifest["manifest_sha"] = "0" * 64
            path.chmod(0o644)
            path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "manifest_sha mismatch"):
                validate_frozen_snapshot(out, "2026-07-10")

            path.write_text(original, encoding="utf-8")
            manifest = json.loads(original)
            manifest["artifact_sha"] = "0" * 64
            self._write_manifest(path, manifest)
            with self.assertRaisesRegex(ValueError, "artifact_sha mismatch"):
                validate_frozen_snapshot(out, "2026-07-10")

            path.write_text(original, encoding="utf-8")
            manifest = json.loads(original)
            manifest["snapshot_captured_at"] = (
                "2026-07-10T20:31:00+08:00"
            )
            self._write_manifest(path, manifest)
            with self.assertRaisesRegex(
                ValueError,
                "snapshot_captured_at mismatch",
            ):
                validate_frozen_snapshot(out, "2026-07-10")

            path.write_text(original, encoding="utf-8")
            manifest = json.loads(original)
            manifest["generator_commit"] = "f" * 40
            self._write_manifest(path, manifest)
            with self.assertRaisesRegex(
                ValueError,
                "generator_commit mismatch",
            ):
                validate_frozen_snapshot(out, "2026-07-10")

    def test_daily_agent_provenance_enables_replay_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            con = self.duckdb.connect(str(db))
            try:
                con.execute(
                    """
                    INSERT INTO fact_market_daily VALUES
                    ('2026-07-10', 9999, '2026-07-10 20:00:00')
                    """
                )
            finally:
                con.close()
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
            daily_agent = self._daily_agent(finance, wiki)
            daily_dir = root / "daily"
            daily_dir.mkdir()
            (daily_dir / "2026-07-10-daily-agent.json").write_text(
                json.dumps(daily_agent, ensure_ascii=False),
                encoding="utf-8",
            )

            manifest = freeze_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
                out_dir=root / "snapshots",
                daily_agent_dir=daily_dir,
            )

            self.assertEqual(manifest["status"], "frozen")
            self.assertTrue(manifest["replay_eligible"])
            self.assertEqual(manifest["provenance_gaps"], [])
            self.assertEqual(
                manifest["upstream_daily_agent"]["artifact_sha"],
                daily_agent["artifact_sha"],
            )
            validate_frozen_snapshot(root / "snapshots", "2026-07-10")
            with gzip.open(
                root / "snapshots" / "2026-07-10.snapshot.json.gz",
                "rt",
                encoding="utf-8",
            ) as handle:
                snapshot = json.load(handle)
            rows = snapshot["data"]["fact_market_daily"]
            self.assertEqual(len(rows), 2)
            self.assertTrue(
                all(
                    row["_pit"]["known_at"]
                    <= daily_agent["evidence_cutoff"]
                    for row in rows
                )
            )

    def test_content_addressed_wiki_delta_allows_replay(self) -> None:
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
            dirty = wiki / "dirty.md"
            dirty.write_text("dirty evidence\n", encoding="utf-8")
            timestamp = 1783677600
            os.utime(dirty, (timestamp, timestamp))
            daily_agent = self._daily_agent(finance, wiki)
            daily_dir = root / "daily"
            daily_dir.mkdir()
            (daily_dir / "2026-07-10-daily-agent.json").write_text(
                json.dumps(daily_agent, ensure_ascii=False),
                encoding="utf-8",
            )

            manifest = freeze_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
                out_dir=root / "snapshots",
                daily_agent_dir=daily_dir,
            )

            self.assertTrue(manifest["replay_eligible"])
            self.assertEqual(manifest["repository_gaps"], [])
            self.assertTrue(
                manifest["repositories"]["working_trees"]["wiki_dirty"]
            )
            delta = manifest["repositories"]["wiki_content_delta"]
            self.assertTrue(delta["dirty"])
            self.assertEqual(delta["entry_count"], 1)
            self.assertEqual(
                delta["artifact_sha"],
                daily_agent["knowledge_snapshot"]["artifact_sha"],
            )
            validate_frozen_snapshot(root / "snapshots", "2026-07-10")

    def test_missing_wiki_delta_blocks_replay_eligibility(self) -> None:
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
                "wiki_content_delta_invalid",
                manifest["repository_gaps"],
            )

    def test_dirty_finance_code_still_blocks_replay(self) -> None:
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
            daily_agent = self._daily_agent(finance, wiki)
            daily_dir = root / "daily"
            daily_dir.mkdir()
            (daily_dir / "2026-07-10-daily-agent.json").write_text(
                json.dumps(daily_agent, ensure_ascii=False),
                encoding="utf-8",
            )
            (finance / "dirty.py").write_text(
                "print('dirty')\n",
                encoding="utf-8",
            )

            _, manifest = build_daily_snapshot(
                db,
                as_of="2026-07-10",
                finance_root=finance,
                kb_root=wiki,
                daily_agent_path=(
                    daily_dir / "2026-07-10-daily-agent.json"
                ),
            )

            self.assertFalse(manifest["replay_eligible"])
            self.assertIn(
                "finance_dirty_worktree",
                manifest["repository_gaps"],
            )
            self.assertNotIn(
                "wiki_content_delta_invalid",
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
