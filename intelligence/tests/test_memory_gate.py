from __future__ import annotations

import hashlib

import pytest

from intelligence.services.memory_gate import MemoryCandidate, MemoryGate


def _decide(candidate: MemoryCandidate, *, verdicts=(), corrections=()):
    return MemoryGate().decide(
        candidate,
        checkpoints=(
            {"id": "c1", "claim": "估值框架在验证窗内有效"},
        ),
        verdicts=verdicts,
        corrections=corrections,
    )


@pytest.mark.parametrize("verdict", ["hit", "partial", "miss"])
def test_reviewed_checkpoint_lesson_is_eligible(verdict: str) -> None:
    decision = _decide(
        MemoryCandidate(
            candidate_id="lesson-1",
            kind="decision_lesson",
            content="估值判断应同时检查兑现与反证",
            checkpoint_id="c1",
        ),
        verdicts=({"id": "c1", "verdict": verdict},),
    )

    assert decision.eligible is True
    assert decision.target_layer == "durable_experience"
    assert decision.reason == "reviewed_checkpoint_lesson"
    assert decision.content_sha256 == hashlib.sha256(
        "估值判断应同时检查兑现与反证".encode("utf-8")
    ).hexdigest()
    assert dict(decision.provenance) == {
        "checkpoint_id": "c1",
        "verdict": verdict,
    }


@pytest.mark.parametrize(
    ("checkpoint_id", "verdicts", "reason"),
    [
        ("", (), "checkpoint_provenance_required"),
        ("missing", ({"id": "missing", "verdict": "hit"},), "checkpoint_not_found"),
        ("c1", (), "terminal_verdict_required"),
        ("c1", ({"id": "c1", "verdict": "unverifiable"},), "terminal_verdict_required"),
    ],
)
def test_unreviewed_lesson_is_rejected(
    checkpoint_id: str,
    verdicts: tuple[dict[str, str], ...],
    reason: str,
) -> None:
    decision = _decide(
        MemoryCandidate(
            candidate_id="lesson-unreviewed",
            kind="decision_lesson",
            content="尚未验证的模型判断",
            checkpoint_id=checkpoint_id,
        ),
        verdicts=verdicts,
    )

    assert decision.eligible is False
    assert decision.target_layer == "none"
    assert decision.reason == reason


def test_latest_terminal_verdict_is_the_promotion_provenance() -> None:
    decision = _decide(
        MemoryCandidate(
            candidate_id="lesson-rejudged",
            kind="decision_lesson",
            content="复盘后应降低该假设权重",
            checkpoint_id="c1",
        ),
        verdicts=(
            {"id": "c1", "verdict": "hit"},
            {"id": "c1", "verdict": "unverifiable"},
            {"id": "c1", "verdict": "miss"},
        ),
    )

    assert dict(decision.provenance)["verdict"] == "miss"


@pytest.mark.parametrize("kind", ["user_correction", "user_preference"])
def test_explicit_correction_can_promote_a_principle(kind: str) -> None:
    correction = {
        "ts": "2026-07-27T10:00:00+00:00",
        "correction": "默认 A 股，时间歧义才追问",
        "principle": "只追问会改变答案的歧义",
    }
    decision = _decide(
        MemoryCandidate(
            candidate_id="correction-1",
            kind=kind,
            content="只追问会改变答案的歧义",
            correction_ts=correction["ts"],
        ),
        corrections=(correction,),
    )

    assert decision.eligible is True
    assert decision.reason == "explicit_user_correction"
    assert dict(decision.provenance) == {
        "correction_ts": correction["ts"],
        "record_type": kind,
    }


def test_correction_requires_exact_timestamp_and_content_match() -> None:
    candidate = MemoryCandidate(
        candidate_id="correction-mismatch",
        kind="user_correction",
        content="模型自行概括的另一条原则",
        correction_ts="2026-07-27T10:00:00+00:00",
    )
    decision = _decide(
        candidate,
        corrections=(
            {
                "ts": "2026-07-27T10:00:00+00:00",
                "correction": "原始纠正",
            },
        ),
    )

    assert decision.eligible is False
    assert decision.reason == "correction_provenance_mismatch"


@pytest.mark.parametrize("kind", ["volatile_fact", "model_judgment"])
def test_volatile_or_unproven_model_content_never_promotes(kind: str) -> None:
    decision = _decide(
        MemoryCandidate(
            candidate_id=f"reject-{kind}",
            kind=kind,
            content="截至今日收盘为 123 元",
            is_volatile=True,
        ),
    )

    assert decision.eligible is False
    assert decision.reason == "volatile_content_forbidden"
    assert decision.provenance == ()


def test_volatile_flag_overrides_even_reviewed_checkpoint() -> None:
    decision = _decide(
        MemoryCandidate(
            candidate_id="volatile-lesson",
            kind="decision_lesson",
            content="2026-07-24 收盘价为 123 元",
            checkpoint_id="c1",
            is_volatile=True,
        ),
        verdicts=({"id": "c1", "verdict": "hit"},),
    )

    assert decision.eligible is False
    assert decision.reason == "volatile_content_forbidden"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"candidate_id": "", "kind": "decision_lesson", "content": "x"},
        {"candidate_id": "x", "kind": "unknown", "content": "x"},
        {"candidate_id": "x", "kind": "decision_lesson", "content": ""},
    ],
)
def test_memory_candidate_rejects_invalid_control_values(kwargs) -> None:
    with pytest.raises(ValueError):
        MemoryCandidate(**kwargs)
