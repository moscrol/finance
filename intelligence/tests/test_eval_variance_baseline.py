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
