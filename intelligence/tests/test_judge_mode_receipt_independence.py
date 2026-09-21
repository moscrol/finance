"""Judge-off → real verifier → public receipt → eval must never claim independence."""
from __future__ import annotations

import json

import pytest

from intelligence.eval.variance_baseline import (
    extract_from_run_dir,
    judge_verification_decision,
    score_distribution,
)
from intelligence.services import llm_refine
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.gate_receipt import build_episode_receipt
from intelligence.tests.test_judge_mode_off import DRAFT, _structural, _verify


@pytest.mark.parametrize("public", ["current", "legacy_false", "missing_flag", "absent"])
@pytest.mark.parametrize("smoke", [False, True])
def test_off_real_verifier_never_becomes_independent(monkeypatch, tmp_path, public, smoke):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")

    def forbidden(*_args, **_kwargs):
        pytest.fail("judge-off must not even resolve a judge provider chain")

    monkeypatch.setattr(llm_refine, "judge_provider_chain", forbidden)
    frame, structural = _structural(DRAFT)
    semantic = _verify(SemanticEpisodeVerifier(), (frame, structural)).to_dict()
    assert semantic["judge_status"] == "passed"
    assert semantic["judge_mode"] == "deterministic"
    artifact = {
        "structural_verifier": {"verified_status": structural.verified_status},
        "semantic_verifier": semantic,
    }
    receipt = build_episode_receipt(rev="fixture", private_artifact=artifact)
    assert receipt["correlated_judge"] is None
    if public == "legacy_false":
        receipt["correlated_judge"] = False
    elif public == "missing_flag":
        receipt.pop("correlated_judge")
    if public != "absent":
        (tmp_path / "report.json").write_text(json.dumps({"gate_receipt": receipt}))
    (tmp_path / "continuous-episode.json").write_text(json.dumps(artifact))
    (tmp_path / "run.json").write_text(json.dumps({"status": "completed"}))
    if smoke:
        (tmp_path / "smoke.json").write_text(json.dumps({"terminal_outcome": "completed"}))
    row = extract_from_run_dir(tmp_path)
    assert row["judge_mode"] == "deterministic"
    assert row["correlated_judge"] is None
    score = score_distribution({"questions": [{"question_id": "q", "repeats": [row]}]})
    assert score["independent_n"] == 0
    assert score["no_judge_rate"] == 1.0
    assert score["questions"][0]["no_judge_count"] == 1
    assert judge_verification_decision(
        observed_delta=0.1, baseline_flip_rate=0, independent_n=score["independent_n"],
    ) == "no_call"


@pytest.mark.parametrize("status", ["passed", "repaired", "rejected", "unavailable"])
@pytest.mark.parametrize("raw", [True, False, None])
def test_deterministic_mode_overrides_bool_and_timing(status, raw):
    receipt = build_episode_receipt(rev="fixture", private_artifact={
        "semantic_verifier": {
            "judge_mode": "deterministic", "judge_status": status,
            "correlated_judge": raw, "timeout_asked": 30.0,
        },
    })
    assert receipt["correlated_judge"] is None


def test_replay_modes_are_separate_and_old_unknown_stays_unknown():
    repeats = [
        {"judge_mode": "deterministic", "correlated_judge": False},
        {"judge_mode": "off", "correlated_judge": True},
        {"judge_mode": "llm", "correlated_judge": False},
        {"judge_mode": "llm", "correlated_judge": True},
        {},
    ]
    score = score_distribution({"questions": [{"question_id": "q", "repeats": repeats}]})
    row = score["questions"][0]
    assert row["no_judge_count"] == 2
    assert row["independent_judge_count"] == 1
    assert row["correlated_judge_count"] == 1
    assert row["unknown_judge_independence_count"] == 1
    assert score["independent_n"] == 1


def test_public_only_current_off_receipt_is_unknown_not_independent(tmp_path):
    receipt = build_episode_receipt(rev="fixture", private_artifact={
        "semantic_verifier": {
            "judge_mode": "deterministic", "judge_status": "passed", "correlated_judge": False,
        },
    })
    (tmp_path / "report.json").write_text(json.dumps({"gate_receipt": receipt}))
    row = extract_from_run_dir(tmp_path)
    assert row["judge_mode"] is None
    assert row["correlated_judge"] is None
    score = score_distribution({"questions": [{"question_id": "q", "repeats": [row]}]})
    assert score["independent_n"] == 0
    assert score["unknown_judge_independence_rate"] == 1.0
