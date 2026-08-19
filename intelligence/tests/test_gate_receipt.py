"""W3: ask vs episode gate_receipt share keys and are dict-diffable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval.live_probe import gate_receipt_table_from_run_dir
from intelligence.services.gate_receipt import (
    ENGINE_ASK,
    ENGINE_EPISODE,
    NOT_APPLICABLE,
    RECEIPT_KEYS,
    TABLE_COLUMNS,
    build_ask_receipt,
    build_episode_receipt,
    build_gate_receipt,
    classify_degrade_counts,
    extract_gate_receipt,
    table_row,
)
from intelligence.services.judge_degrade import (
    classify_degrade_counts as classify_degrade_counts_w2,
)


def test_ask_and_episode_receipts_share_keys_and_are_diffable() -> None:
    ask = build_ask_receipt(
        rev="deadbeef",
        issues=["llm_unavailable_template_answer"],
        extra_degrade_count=1,
        timings={"elapsed_seconds": 12.5, "retrieve_seconds": 11.0},
    )
    episode = build_episode_receipt(
        rev="deadbeef",
        private_artifact={
            "structural_verifier": {
                "verified_status": "completed",
                "issues": [],
            },
            "semantic_verifier": {
                "judge_status": "passed",
                "issues": [],
                "timeout_asked": 25.0,
            },
        },
        extra_degrade_count=0,
        timings={"elapsed_seconds": 41.0, "judge_seconds": 18.2},
    )
    assert tuple(ask) == RECEIPT_KEYS
    assert tuple(episode) == RECEIPT_KEYS
    assert ask.keys() == episode.keys()
    assert ask["timings"].keys() == episode["timings"].keys()

    delta = {key: (ask[key], episode[key]) for key in ask if ask[key] != episode[key]}
    assert delta["engine"] == (ENGINE_ASK, ENGINE_EPISODE)
    assert ask["verified_status"] == NOT_APPLICABLE
    assert ask["judge_status"] == NOT_APPLICABLE
    assert episode["verified_status"] == "completed"
    assert episode["judge_status"] == "passed"
    assert ask["judge_unavailable_count"] == 0
    assert ask["content_degraded_count"] == 1
    assert episode["judge_unavailable_count"] == 0
    assert episode["content_degraded_count"] == 0


def test_ask_receipt_refuses_fake_completed_or_passed() -> None:
    with pytest.raises(ValueError, match="must not fake"):
        build_gate_receipt(
            engine=ENGINE_ASK,
            rev="deadbeef",
            verified_status="completed",
            judge_status=NOT_APPLICABLE,
        )
    with pytest.raises(ValueError, match="must not fake"):
        build_gate_receipt(
            engine=ENGINE_ASK,
            rev="deadbeef",
            verified_status=NOT_APPLICABLE,
            judge_status="passed",
        )


def test_episode_judge_unavailable_splits_from_content_degrade() -> None:
    receipt = build_episode_receipt(
        rev="deadbeef",
        private_artifact={
            "structural_verifier": {
                "verified_status": "partial",
                "issues": ["stripped unsupported evidence type"],
            },
            "semantic_verifier": {
                "judge_status": "unavailable",
                "issues": [],
                "exc_class": "TimeoutError",
                "timeout_asked": 25.0,
            },
        },
        extra_degrade_count=1,
    )
    assert receipt["judge_status"] == "unavailable"
    assert receipt["verified_status"] == "partial"
    assert receipt["judge_unavailable_count"] == 1
    assert receipt["content_degraded_count"] == 0
    assert "stripped unsupported evidence type" in receipt["issues"]


def test_simulated_artifact_files_diff_on_gate_receipt(tmp_path: Path) -> None:
    ask_dir = tmp_path / "ask_run"
    episode_dir = tmp_path / "episode_run"
    ask_dir.mkdir()
    episode_dir.mkdir()
    ask_receipt = build_ask_receipt(
        rev="deadbeef",
        issues=[],
        extra_degrade_count=0,
        timings={"elapsed_seconds": 8.0, "retrieve_seconds": 7.2},
    )
    episode_receipt = build_episode_receipt(
        rev="deadbeef",
        private_artifact={
            "structural_verifier": {"verified_status": "completed", "issues": []},
            "semantic_verifier": {"judge_status": "passed", "issues": []},
        },
        extra_degrade_count=0,
        timings={"elapsed_seconds": 33.0},
    )
    (ask_dir / "report.json").write_text(
        json.dumps({"status": "completed", "gate_receipt": ask_receipt}),
        encoding="utf-8",
    )
    (ask_dir / "summary.json").write_text(
        json.dumps({"gate_receipt": ask_receipt}),
        encoding="utf-8",
    )
    (episode_dir / "report.json").write_text(
        json.dumps({"status": "completed", "gate_receipt": episode_receipt}),
        encoding="utf-8",
    )

    ask_row = gate_receipt_table_from_run_dir(ask_dir)
    episode_row = table_row(extract_gate_receipt(
        json.loads((episode_dir / "report.json").read_text(encoding="utf-8"))
    ))
    assert tuple(ask_row) == TABLE_COLUMNS
    assert ask_row.keys() == episode_row.keys()
    assert ask_row["verified_status"] == NOT_APPLICABLE
    assert ask_row["judge_status"] == NOT_APPLICABLE
    assert episode_row["verified_status"] == "completed"
    assert episode_row["judge_status"] == "passed"
    assert ask_row["rev"] == episode_row["rev"] == "deadbeef"


def test_none_plus_timeout_is_not_judge_unavailable() -> None:
    """Missing judge_status is not an outage. Only explicit unavailable counts.

    W3 used to infer unavailable from None + timeout_asked; W2 does not.
    After merge both builders must share W2's rule.
    """

    ju, cd = classify_degrade_counts(
        judge_status=None,
        exc_class=None,
        timeout_asked=25.0,
        extra_degrade_count=1,
    )
    assert (ju, cd) == (0, 1)
    assert (ju, cd) == classify_degrade_counts_w2(
        judge_status=None,
        extra_degrade_count=1,
        timeout_asked=25.0,
    )


def test_gate_and_w2_classify_agree_on_the_status_matrix() -> None:
    cases = (
        ("unavailable", None, None, 0, (1, 0)),
        ("unavailable", "TimeoutError", 25.0, 1, (1, 0)),
        ("not_applicable", None, 25.0, 1, (0, 1)),
        ("passed", None, 25.0, 2, (0, 2)),
        (None, "TimeoutError", 25.0, 1, (0, 1)),
        (None, None, None, 0, (0, 0)),
    )
    for status, exc, timeout, extra, expected in cases:
        gate = classify_degrade_counts(
            judge_status=status,
            exc_class=exc,
            timeout_asked=timeout,
            extra_degrade_count=extra,
        )
        w2 = classify_degrade_counts_w2(
            judge_status=status,
            extra_degrade_count=extra,
            exc_class=exc,
            timeout_asked=timeout,
        )
        assert gate == expected == w2, (status, exc, timeout, extra, gate, w2)


def test_missing_block_still_emits_the_same_table_columns() -> None:
    row = table_row(extract_gate_receipt({"status": "completed"}))
    assert tuple(row) == TABLE_COLUMNS
    assert row["engine"] is None
    assert row["judge_status"] is None
