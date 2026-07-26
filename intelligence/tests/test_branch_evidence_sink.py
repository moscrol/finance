from __future__ import annotations

from datetime import date

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.evidence_ledger import EvidenceLedger


def _evidence(
    content_hash: str,
    *,
    source_date: str | None = "2026-07-20",
    supports: tuple[str, ...] = (),
) -> AgentEvidence:
    return AgentEvidence(
        tool="news_search",
        title=f"证据 {content_hash}",
        detail="公开可核验摘要",
        source="公开来源",
        source_date=source_date,
        supports=supports,
        independent_key=f"family-{content_hash}",
        content_hash=content_hash,
    )


def test_branch_sink_can_only_append_evidence_and_read_snapshot() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    ledger.open_gap("counterpoint")
    sink = ledger.branch_sink("branch-1")

    assert sink.append(_evidence("hash-1", supports=("direct_assessment",))) == (
        "hash-1",
    )

    snapshot = sink.snapshot()
    assert snapshot.evidence_ids == ("hash-1",)
    assert snapshot.evidence_branch_owners == (("hash-1", "branch-1"),)
    assert snapshot.covered_outputs == ()
    assert snapshot.open_gaps == ("counterpoint",)
    assert not hasattr(sink, "close_gap")
    assert not hasattr(sink, "open_gap")
    assert not hasattr(sink, "mark_output_covered")


def test_branch_sink_preserves_cutoff_and_first_writer_ownership() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    first = ledger.branch_sink("branch-1")
    second = ledger.branch_sink("branch-2")

    assert first.append(_evidence("future", source_date="2026-07-25")) == ()
    assert first.append(_evidence("shared")) == ("shared",)
    assert second.append(_evidence("shared")) == ()

    snapshot = ledger.snapshot()
    assert snapshot.evidence_ids == ("shared",)
    assert snapshot.evidence_branch_owners == (("shared", "branch-1"),)


@pytest.mark.parametrize("branch_id", ["", "  "])
def test_branch_sink_requires_a_non_empty_owner(branch_id: str) -> None:
    with pytest.raises(ValueError, match="branch_id"):
        EvidenceLedger().branch_sink(branch_id)


def test_branch_sink_rejects_non_evidence_values() -> None:
    sink = EvidenceLedger().branch_sink("branch-1")

    with pytest.raises(TypeError, match="AgentEvidence"):
        sink.append((object(),))  # type: ignore[arg-type]
