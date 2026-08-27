"""W7 评测方差基线：--help、离线 replay 翻转率、A/B no_call。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from intelligence.eval.variance_baseline import (
    ab_decision,
    extract_from_run_dir,
    is_judge_unavailable,
    judge_independence_label,
    judge_verification_decision,
    load_replay,
    main,
    score_distribution,
)

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "eval_variance_baseline.py"
FIXTURE = REPO / "intelligence" / "eval" / "fixtures" / "eval-variance-baseline-fixture.json"
PYTHON = sys.executable


def test_help_exists() -> None:
    result = subprocess.run(
        [PYTHON, str(SCRIPT), "--help"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "replay" in result.stdout
    assert "441c60f2" in result.stdout
    assert "8792" in result.stdout
    assert "no_call" in result.stdout or "翻转率" in result.stdout


def test_replay_fixture_flip_rate(tmp_path: Path) -> None:
    fixture = load_replay(FIXTURE)
    scored = score_distribution(fixture)
    by_id = {item["question_id"]: item for item in scored["questions"]}

    assert by_id["Q-stable"]["flip_rate"] == pytest.approx(0.0)
    assert by_id["Q-flip"]["flip_rate"] == pytest.approx(0.2)
    assert by_id["Q-flip"]["mode"] == "completed"
    assert by_id["Q-judge"]["flip_rate"] == pytest.approx(0.4)
    assert by_id["Q-judge"]["judge_unavailable_rate"] == pytest.approx(0.4)
    # 去掉判官桶后，剩下 3 次 completed，内容层不翻
    assert by_id["Q-judge"]["content_flip_rate"] == pytest.approx(0.0)

    # 含判官噪声的翻转 0 / 0.2 / 0.4 → 0.2；内容层 0 / 0.2 / 0
    assert scored["baseline_flip_rate"] == pytest.approx(0.2)
    assert scored["judge_unavailable_rate"] == pytest.approx(0.133333, abs=1e-6)
    assert scored["content_flip_rate"] == pytest.approx(0.066667, abs=1e-6)
    assert scored["correlated_judge_rate"] == pytest.approx(0.0)
    assert scored["independent_judge_rate"] == pytest.approx(0.0)
    assert scored["unknown_judge_independence_rate"] == pytest.approx(1.0)
    assert scored["independent_n"] == 0
    assert scored["live"] is False

    dest = tmp_path / "out.json"
    code = main(
        [
            "--replay",
            str(FIXTURE),
            "--stamp",
            "20260819T080000Z",
            "--out",
            str(dest),
        ]
    )
    assert code == 0
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert payload["filename"].endswith("-fixture-var5.json")
    assert payload["live"] is False
    assert payload.get("fixture") is True
    assert "441c60f2" in payload["how_to_produce_441c60f2_live_baseline"]
    assert dest.with_suffix(".md").is_file()


def test_ab_helper_returns_no_call_below_baseline() -> None:
    baseline = 0.2
    assert ab_decision(0.05, baseline) == "no_call"
    assert ab_decision(0.25, baseline) == "callable"
    result = subprocess.run(
        [
            PYTHON,
            str(SCRIPT),
            "--decide",
            "--observed-delta",
            "0.05",
            "--baseline-flip",
            str(baseline),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "no_call"


def test_correlated_samples_cannot_call_verification_improvement() -> None:
    assert judge_independence_label(True) == "correlated"
    assert judge_independence_label(False) == "independent"
    assert judge_independence_label(None) == "unknown"
    assert judge_independence_label("false") == "unknown"
    # 内容差已经超过翻转率，但没有独立判官样本 → 仍不得下「验证变好了」
    assert (
        judge_verification_decision(
            observed_delta=0.5,
            baseline_flip_rate=0.2,
            independent_n=0,
        )
        == "no_call"
    )
    assert (
        judge_verification_decision(
            observed_delta=0.5,
            baseline_flip_rate=0.2,
            independent_n=3,
        )
        == "callable"
    )
    result = subprocess.run(
        [
            PYTHON,
            str(SCRIPT),
            "--decide",
            "--observed-delta",
            "0.5",
            "--baseline-flip",
            "0.2",
            "--independent-n",
            "0",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "no_call"
    assert payload["independent_n"] == 0


def test_score_distribution_splits_correlated_from_independent() -> None:
    scored = score_distribution(
        {
            "questions": [
                {
                    "question_id": "Q-mix",
                    "repeats": [
                        {
                            "primary_outcome": "completed",
                            "judge_status": "passed",
                            "correlated_judge": True,
                        },
                        {
                            "primary_outcome": "completed",
                            "judge_status": "passed",
                            "correlated_judge": True,
                        },
                        {
                            "primary_outcome": "completed",
                            "judge_status": "passed",
                            "correlated_judge": False,
                        },
                        {
                            "primary_outcome": "completed",
                            "judge_status": "passed",
                        },
                    ],
                }
            ]
        }
    )
    row = scored["questions"][0]
    assert row["correlated_judge_count"] == 2
    assert row["independent_judge_count"] == 1
    assert row["unknown_judge_independence_count"] == 1
    assert row["flip_rate"] == pytest.approx(0.0)
    assert scored["independent_n"] == 1
    assert scored["content_flip_rate"] == pytest.approx(0.0)


def test_ask_not_applicable_is_not_judge_unavailable() -> None:
    assert is_judge_unavailable("unavailable") is True
    assert is_judge_unavailable(None) is False
    assert is_judge_unavailable("timeout") is False
    assert is_judge_unavailable("not_applicable") is False
    assert is_judge_unavailable("passed") is False
    assert is_judge_unavailable("") is False


def test_extract_from_run_dir_reads_ask_gate_receipt(tmp_path: Path) -> None:
    run_dir = tmp_path / "ask-run"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "gate_receipt": {
                    "engine": "ask",
                    "judge_status": "not_applicable",
                    "verified_status": "not_applicable",
                    "judge_unavailable_count": 0,
                    "content_degraded_count": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps({"status": "completed", "degrades": []}),
        encoding="utf-8",
    )
    row = extract_from_run_dir(run_dir)
    assert row["judge_status"] == "not_applicable"
    assert row["judge_unavailable"] is False
    assert row["correlated_judge"] is None


def test_extract_prefers_gate_receipt_over_missing_semantic(tmp_path: Path) -> None:
    run_dir = tmp_path / "episode-run"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "gate_receipt": {
                    "engine": "episode",
                    "judge_status": "unavailable",
                    "verified_status": "partial",
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(
            {
                "structural_verifier": {"verified_status": "partial"},
                "semantic_verifier": {},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    row = extract_from_run_dir(run_dir)
    assert row["judge_status"] == "unavailable"
    assert row["judge_unavailable"] is True
    assert row["correlated_judge"] is None


def test_extract_reads_correlated_judge_from_public_report(tmp_path: Path) -> None:
    run_dir = tmp_path / "episode-correlated"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "gate_receipt": {
                    "engine": "episode",
                    "judge_status": "passed",
                    "verified_status": "completed",
                    "correlated_judge": True,
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(
            {
                "structural_verifier": {"verified_status": "completed"},
                "semantic_verifier": {
                    "judge_status": "passed",
                    "correlated_judge": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    row = extract_from_run_dir(run_dir)
    assert row["correlated_judge"] is True


def test_extract_falls_back_to_private_semantic_when_receipt_omits_flag(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "episode-legacy"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "gate_receipt": {
                    "engine": "episode",
                    "judge_status": "passed",
                    "verified_status": "completed",
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(
            {
                "semantic_verifier": {
                    "judge_status": "passed",
                    "correlated_judge": True,
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    row = extract_from_run_dir(run_dir)
    assert row["correlated_judge"] is True


def test_extract_keeps_explicit_receipt_null_over_private_false(
    tmp_path: Path,
) -> None:
    """Skip-path stamp is JSON null. Private default False must not revive it."""

    run_dir = tmp_path / "episode-skipped-judge"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "gate_receipt": {
                    "engine": "episode",
                    "judge_status": "unavailable",
                    "verified_status": "partial",
                    "correlated_judge": None,
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(
            {
                "semantic_verifier": {
                    "judge_status": "unavailable",
                    "correlated_judge": False,
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    row = extract_from_run_dir(run_dir)
    assert row["correlated_judge"] is None


def test_extract_legacy_skip_false_is_unknown(tmp_path: Path) -> None:
    run_dir = tmp_path / "episode-legacy-skip"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "gate_receipt": {
                    "engine": "episode",
                    "judge_status": "unavailable",
                    "verified_status": "partial",
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(
            {
                "semantic_verifier": {
                    "judge_status": "unavailable",
                    "correlated_judge": False,
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    row = extract_from_run_dir(run_dir)
    assert row["correlated_judge"] is None


def test_reserved_port_refused() -> None:
    result = subprocess.run(
        [PYTHON, str(SCRIPT), "--live", "--port", "8792", "--n", "1"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "8792" in result.stderr
    assert "reserved" in result.stderr.lower() or "保留" in result.stderr
