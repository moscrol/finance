import pytest

from intelligence.services.answer_stream import AnswerSnapshot


@pytest.mark.parametrize(
    ("phase", "final"),
    [
        ("verified_draft", False),
        ("validated_synthesis", True),
        ("verified_fallback", True),
    ],
)
def test_answer_snapshot_payload_has_only_public_contract_fields(
    phase: str,
    final: bool,
) -> None:
    snapshot = AnswerSnapshot(
        revision=1,
        phase=phase,
        text="已核验正文",
        final=final,
    )

    assert snapshot.to_payload() == {
        "revision": 1,
        "phase": phase,
        "text": "已核验正文",
        "final": final,
    }
    assert set(snapshot.to_payload()) == {"revision", "phase", "text", "final"}


@pytest.mark.parametrize("revision", [0, -1, True, 1.5, "1"])
def test_answer_snapshot_rejects_invalid_revision(revision: object) -> None:
    with pytest.raises((TypeError, ValueError), match="revision"):
        AnswerSnapshot(
            revision=revision,  # type: ignore[arg-type]
            phase="verified_draft",
            text="正文",
            final=False,
        )


@pytest.mark.parametrize("text", ["", "  ", None, 1])
def test_answer_snapshot_rejects_empty_or_non_text_body(text: object) -> None:
    with pytest.raises((TypeError, ValueError), match="text"):
        AnswerSnapshot(
            revision=1,
            phase="verified_draft",
            text=text,  # type: ignore[arg-type]
            final=False,
        )


def test_answer_snapshot_rejects_unknown_phase() -> None:
    with pytest.raises(ValueError, match="phase"):
        AnswerSnapshot(
            revision=1,
            phase="raw_draft",  # type: ignore[arg-type]
            text="正文",
            final=False,
        )


@pytest.mark.parametrize(
    ("phase", "final"),
    [
        ("verified_draft", True),
        ("validated_synthesis", False),
        ("verified_fallback", False),
    ],
)
def test_answer_snapshot_enforces_draft_and_terminal_finality(
    phase: str,
    final: bool,
) -> None:
    with pytest.raises(ValueError, match="final"):
        AnswerSnapshot(
            revision=1,
            phase=phase,
            text="正文",
            final=final,
        )
