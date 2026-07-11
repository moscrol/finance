import json
import tempfile
import unittest
from pathlib import Path

from intelligence.eval.forward_acceptance import (
    build_acceptance_record,
    summarize_forward_acceptance,
    validate_acceptance_record,
    write_acceptance_record,
)


def _runtime_status(
    report_date: str,
    *,
    replay_ready: bool = True,
    claim_count: int = 40,
) -> dict[str, object]:
    return {
        "schema_version": "fidelity-runtime-status-1.2",
        "report_date": report_date,
        "runtime": {
            "clean": replay_ready,
            "commit": "a" * 40,
            "dirty_paths": [] if replay_ready else ["source.py"],
        },
        "daily_agent": {
            "exists": replay_ready,
            "lineage_ready": replay_ready,
            "contract_ready": replay_ready,
            "upstream_complete": replay_ready,
            "forward_generated": replay_ready,
            "claim_count": claim_count,
        },
        "pit_manifest": {
            "exists": replay_ready,
            "schema_ready": replay_ready,
            "contract_ready": replay_ready,
            "replay_eligible": replay_ready,
        },
        "provenance_linked": replay_ready,
        "generator_commit_matches": replay_ready,
        "capture_ready": replay_ready,
        "replay_ready": replay_ready,
        "decision_eligible": False,
    }


class FidelityForwardAcceptanceTests(unittest.TestCase):
    def test_builds_accepted_and_blocked_records(self):
        accepted = build_acceptance_record(
            _runtime_status("2026-07-13"),
            checked_at="2026-07-13T12:45:00+00:00",
        )
        blocked = build_acceptance_record(
            _runtime_status("2026-07-14", replay_ready=False),
            checked_at="2026-07-14T12:45:00+00:00",
        )

        self.assertEqual(accepted["result"], "accepted")
        self.assertEqual(accepted["blockers"], [])
        self.assertEqual(blocked["result"], "blocked")
        self.assertIn("runtime_dirty", blocked["blockers"])
        self.assertIn("daily_agent_missing", blocked["blockers"])
        self.assertIn("replay_not_ready", blocked["blockers"])
        self.assertFalse(blocked["decision_eligible"])
        self.assertEqual(validate_acceptance_record(accepted), [])

    def test_record_hash_detects_tampering(self):
        record = build_acceptance_record(
            _runtime_status("2026-07-13"),
            checked_at="2026-07-13T12:45:00+00:00",
        )

        record["claim_count"] = 999

        self.assertIn(
            "record_sha256 mismatch",
            validate_acceptance_record(record),
        )

    def test_writer_preserves_attempts_and_updates_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocked = build_acceptance_record(
                _runtime_status("2026-07-13", replay_ready=False),
                checked_at="2026-07-13T12:45:00+00:00",
            )
            accepted = build_acceptance_record(
                _runtime_status("2026-07-13"),
                checked_at="2026-07-13T13:00:00+00:00",
            )

            first_path = write_acceptance_record(root, blocked)
            second_path = write_acceptance_record(root, accepted)

            self.assertTrue(first_path.is_file())
            self.assertTrue(second_path.is_file())
            attempts = list((root / "records" / "2026-07-13").glob("*.json"))
            self.assertEqual(len(attempts), 2)
            latest = json.loads(
                (root / "latest" / "2026-07-13.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(latest["result"], "accepted")

    def test_older_retry_does_not_replace_latest_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accepted = build_acceptance_record(
                _runtime_status("2026-07-13"),
                checked_at="2026-07-13T13:00:00+00:00",
            )
            older_blocked = build_acceptance_record(
                _runtime_status("2026-07-13", replay_ready=False),
                checked_at="2026-07-13T12:45:00+00:00",
            )

            write_acceptance_record(root, accepted)
            write_acceptance_record(root, older_blocked)

            latest = json.loads(
                (root / "latest" / "2026-07-13.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(latest["result"], "accepted")
            self.assertEqual(latest["checked_at"], accepted["checked_at"])

    def test_summary_opens_gold_sampling_after_five_valid_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for day in range(13, 18):
                date = f"2026-07-{day}"
                record = build_acceptance_record(
                    _runtime_status(date),
                    checked_at=f"{date}T12:45:00+00:00",
                )
                write_acceptance_record(root, record)

            summary = summarize_forward_acceptance(
                root,
                start_date="2026-07-13",
                end_date="2026-07-17",
            )

            self.assertEqual(summary["accepted_day_count"], 5)
            self.assertEqual(summary["accepted_claim_count"], 200)
            self.assertTrue(summary["gold_sampling_ready"])
            self.assertFalse(summary["eligibility_observation_ready"])
            self.assertFalse(summary["decision_eligible"])

    def test_blocked_day_prevents_window_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for day in range(13, 18):
                date = f"2026-07-{day}"
                record = build_acceptance_record(
                    _runtime_status(
                        date,
                        replay_ready=day != 15,
                    ),
                    checked_at=f"{date}T12:45:00+00:00",
                )
                write_acceptance_record(root, record)

            summary = summarize_forward_acceptance(root)

            self.assertEqual(summary["accepted_day_count"], 4)
            self.assertEqual(summary["blocked_dates"], ["2026-07-15"])
            self.assertFalse(summary["gold_sampling_ready"])
            self.assertFalse(summary["decision_eligible"])

    def test_ten_valid_days_open_review_but_not_decision_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for day in range(1, 11):
                date = f"2026-08-{day:02d}"
                record = build_acceptance_record(
                    _runtime_status(date, claim_count=20),
                    checked_at=f"{date}T12:45:00+00:00",
                )
                write_acceptance_record(root, record)

            summary = summarize_forward_acceptance(root)

            self.assertTrue(summary["gold_sampling_ready"])
            self.assertTrue(summary["eligibility_observation_ready"])
            self.assertFalse(summary["decision_eligible"])
