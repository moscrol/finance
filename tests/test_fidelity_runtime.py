import json
import tempfile
import unittest
from pathlib import Path

from intelligence.eval.runtime_status import (
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

    def test_pit_manifest_requires_v1_1_schema(self):
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

            self.assertTrue(status["schema_ready"])
            self.assertTrue(status["replay_eligible"])
