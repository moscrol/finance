import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.eval.runtime_status import (
    build_runtime_status,
    daily_agent_status,
    pit_manifest_status,
)


class FidelityRuntimeStatusTests(unittest.TestCase):
    def test_daily_agent_requires_nonempty_claim_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "market_feature_store" / "exports"
            output.mkdir(parents=True)
            path = output / "2026-07-10-daily-agent.json"
            path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-07-10T19:22:21+08:00",
                        "lineage_schema_version": "claim-lineage-v1",
                        "claims": [{"claim_id": "claim-1"}],
                        "evidence_catalog": {"ev-1": {"scope": "claim"}},
                    }
                ),
                encoding="utf-8",
            )

            status = daily_agent_status(root, "2026-07-10")

            self.assertTrue(status["lineage_ready"])
            self.assertEqual(status["claim_count"], 1)
            self.assertEqual(status["evidence_count"], 1)
            self.assertFalse(status["contract_ready"])

    def test_legacy_pit_manifest_is_not_contract_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "2026-07-10.manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "pit-daily-manifest-1.1",
                        "status": "frozen",
                        "replay_eligible": True,
                        "capture_root": "/runtime",
                    }
                ),
                encoding="utf-8",
            )

            status = pit_manifest_status(root, "2026-07-10")

            self.assertFalse(status["schema_ready"])
            self.assertFalse(status["contract_ready"])
            self.assertTrue(status["replay_eligible"])

    def test_runtime_requires_clean_linked_forward_provenance(self):
        daily = {
            "lineage_ready": True,
            "contract_ready": True,
            "upstream_complete": True,
            "forward_generated": True,
            "generator_commit": "a" * 40,
            "run_id": "daily-run",
            "artifact_sha": "b" * 64,
            "manifest_sha": "c" * 64,
            "report_generated_at": "2026-07-10T20:05:00+08:00",
            "evidence_cutoff": "2026-07-10T18:30:00+08:00",
            "decision_cutoff": "2026-07-10T20:05:00+08:00",
        }
        pit = {
            "schema_ready": True,
            "contract_ready": True,
            "replay_eligible": True,
            "generator_commit": "a" * 40,
            "report_generated_at": daily["report_generated_at"],
            "evidence_cutoff": daily["evidence_cutoff"],
            "decision_cutoff": daily["decision_cutoff"],
            "upstream_daily_agent": {
                "status": "valid",
                "generator_commit": daily["generator_commit"],
                "run_id": daily["run_id"],
                "artifact_sha": daily["artifact_sha"],
                "manifest_sha": daily["manifest_sha"],
            },
        }
        with (
            mock.patch(
                "intelligence.eval.runtime_status.git_runtime_status",
                return_value={
                    "clean": True,
                    "commit": "a" * 40,
                    "dirty_paths": [],
                },
            ),
            mock.patch(
                "intelligence.eval.runtime_status.daily_agent_status",
                return_value=daily,
            ),
            mock.patch(
                "intelligence.eval.runtime_status.pit_manifest_status",
                return_value=pit,
            ),
        ):
            status = build_runtime_status(
                code_root="/code",
                data_root="/data",
                snapshot_dir="/snapshots",
                report_date="2026-07-10",
            )

        self.assertTrue(status["capture_ready"])
        self.assertTrue(status["replay_ready"])
        self.assertFalse(status["decision_eligible"])

    def test_runtime_blocks_dirty_or_mismatched_provenance(self):
        with (
            mock.patch(
                "intelligence.eval.runtime_status.git_runtime_status",
                return_value={
                    "clean": False,
                    "commit": "a" * 40,
                    "dirty_paths": ["wiki/source.md"],
                },
            ),
            mock.patch(
                "intelligence.eval.runtime_status.daily_agent_status",
                return_value={
                    "lineage_ready": True,
                    "contract_ready": True,
                    "upstream_complete": True,
                    "forward_generated": True,
                    "generator_commit": "a" * 40,
                    "run_id": "daily-run",
                    "artifact_sha": "b" * 64,
                    "manifest_sha": "c" * 64,
                },
            ),
            mock.patch(
                "intelligence.eval.runtime_status.pit_manifest_status",
                return_value={
                    "schema_ready": True,
                    "contract_ready": True,
                    "replay_eligible": True,
                    "generator_commit": "a" * 40,
                    "upstream_daily_agent": {
                        "status": "valid",
                        "run_id": "different-run",
                    },
                },
            ),
        ):
            status = build_runtime_status(
                code_root="/code",
                data_root="/data",
                snapshot_dir="/snapshots",
                report_date="2026-07-10",
            )

        self.assertFalse(status["provenance_linked"])
        self.assertFalse(status["capture_ready"])
        self.assertFalse(status["replay_ready"])
