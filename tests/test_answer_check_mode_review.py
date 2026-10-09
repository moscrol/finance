"""Forensic capture contract, not approval of answer-deletion heuristics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts/review_probes/answer_check_mode_review.py"


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    output = tmp_path_factory.mktemp("answer-check-review") / "evidence"
    completed = subprocess.run(
        [sys.executable, str(PROBE), "--output-dir", str(output)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return output, json.loads((output / "mode-results.json").read_text())


def test_capture_has_explicit_identity_no_external_io_and_only_isolated_stores(captured):
    output, report = captured
    assert report["identity_stable"]
    assert report["revision"] == report["revision_after"]
    assert report["source_sha256"] == report["source_sha256_after"]
    for name, expected in report["source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    assert report["probe_sha256"] == hashlib.sha256(PROBE.read_bytes()).hexdigest()
    assert report["probe_sha256"] == report["probe_sha256_after"]
    assert report["blocked_network_attempts"] == report["blocked_database_attempts"] == 0
    assert report["real_model_calls"] == 0
    assert (output / "isolated-state").is_dir()
    assert report["isolated_database_opens"] > 0
    assert {Path(p) for p in report["isolated_database_paths"]} == {
        output / "isolated-state" / name / "workbench.sqlite3" for name in ("conversations", "runs")
    }
    assert "workbench_http_delivery" in report["not_verified"]
    assert "natural_model_revision" in report["not_verified"]


def test_capture_records_all_modes_and_original_text_not_only_selected_successes(captured):
    _, report = captured
    rows = report["rows"]
    assert len(rows) == 20
    assert len({(r["case"], r["judge_setting"], r["numeric_mark_setting"]) for r in rows}) == 20
    assert {r["judge_setting"] for r in rows} == {"off", "llm"}
    assert {r["numeric_mark_setting"] for r in rows} == {"0", "1"}
    for name in {r["case"] for r in rows}:
        variants = [r for r in rows if r["case"] == name]
        assert len(variants) == 4
        assert len({r["input_draft"] for r in variants}) == 1
        assert len({r["synthetic_evidence"] for r in variants}) == 1
    for row in rows:
        assert row["injected_judge_calls"] == (0 if row["judge_setting"] == "off" else 1)
        assert row["judge_mode_recorded"] == ("deterministic" if row["judge_setting"] == "off" else "llm")
        assert isinstance(row["sentence_verdicts"], list)
        assert isinstance(row["review_feedback"], list)
        assert row["verified_draft"]  # Keep internal text separately from publication.
        if row["case"] == "private_token":
            assert "HASH_PRIVATE_SENTINEL" in row["input_draft"]
            assert "HASH_PRIVATE_SENTINEL" not in row["public_answer"]


def test_downstream_helpers_are_separate_observations_not_semantic_verdicts(captured):
    _, report = captured
    rows = report["delivery_helper_rows"]
    assert len(rows) == 20
    assert {r["gate"] for r in rows} == {
        "apply_outlook_delivery_gate", "apply_market_watch_delivery_gate",
    }
    for row in rows:
        assert set(row) >= {"case", "input", "text", "applied", "dropped"}
        assert isinstance(row["dropped"], int)
        if row["case"] == "nonforecast_control":
            assert not row["applied"] and row["text"] == row["input"]
        if row["case"] == "watch_registered":
            assert row["applied"] and row["text"] == row["input"]
    # Do not canonize deletion of a negated sentence: retain what the gate did,
    # so the diagnostic remains useful after a later owner fixes the heuristic.
    assert len([r for r in rows if r["case"] == "forecast_negated_verification"]) == 4


def test_scripted_episode_delivery_exercises_late_gate_and_persistence(captured):
    _, report = captured
    delivery = report["scripted_delivery"]
    assert delivery["outlook_gate_calls"] == 1
    assert delivery["legacy_filter_calls"] == 0
    assert delivery["judge_setting"] == "off" and delivery["numeric_mark_setting"] == "1"
    assert delivery["status"] == delivery["message_status"] == "completed"
    assert delivery["delivered"] == delivery["persisted"]
    assert delivery["conversation_id"] and delivery["run_id"]
    assert "不能说已经验证了剧本。" in delivery["input"]
    # Deliberately no assertion requiring the negation to disappear: that is
    # observed product behavior, not a desirable capture invariant.


def test_evidence_cannot_be_overwritten_or_written_into_checkout(captured):
    output, _ = captured
    original = (output / "mode-results.json").read_bytes()
    for invalid in (output, ROOT):
        completed = subprocess.run(
            [sys.executable, str(PROBE), "--output-dir", str(invalid)],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        assert completed.returncode != 0
    assert (output / "mode-results.json").read_bytes() == original
