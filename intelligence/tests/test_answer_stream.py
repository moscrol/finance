from __future__ import annotations

import pytest

from intelligence.services.answer_stream import AnswerSnapshot


def test_answer_snapshot_payload() -> None:
    snapshot = AnswerSnapshot(
        revision=1,
        phase="verified_draft",
        text="# 英维克\n\n证据不足。",
        final=False,
    )

    assert snapshot.payload() == {
        "revision": 1,
        "phase": "verified_draft",
        "text": "# 英维克\n\n证据不足。",
        "final": False,
    }


@pytest.mark.parametrize(
    ("revision", "phase", "text", "final"),
    [
        (0, "verified_draft", "draft", False),
        (True, "verified_draft", "draft", False),
        (1, "unknown", "draft", False),
        (1, "verified_draft", " ", False),
        (1, "verified_draft", "draft", True),
        (2, "validated_synthesis", "answer", False),
        (2, "verified_fallback", "answer", False),
        (2, "verified_fallback", "answer", 1),
        (2, "decision_brief_fallback", "answer", False),
        (2, "evidence_gap_fallback", "answer", False),
    ],
)
def test_answer_snapshot_rejects_invalid_payloads(
    revision: object,
    phase: object,
    text: object,
    final: object,
) -> None:
    with pytest.raises(ValueError):
        AnswerSnapshot(
            revision=revision,  # type: ignore[arg-type]
            phase=phase,  # type: ignore[arg-type]
            text=text,  # type: ignore[arg-type]
            final=final,  # type: ignore[arg-type]
        )
