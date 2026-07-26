from datetime import date

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.repair_coordinator import progress_from_ledger


def _evidence(content_hash: str, source: str = "source-a") -> AgentEvidence:
    return AgentEvidence(
        tool="web_search",
        title="evidence",
        detail="detail",
        source=source,
        source_date="2026-07-24",
        independent_key=source,
        content_hash=content_hash,
    )


def test_snapshot_is_immutable_and_duplicate_append_is_idempotent() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    assert ledger.append(_evidence("e1"), covered_outputs=("direct",)) == ("e1",)
    snapshot = ledger.snapshot()
    assert ledger.append(_evidence("e1")) == ()
    ledger.open_gap("counterpoint")
    assert snapshot.open_gaps == ()
    assert snapshot.evidence_ids == ("e1",)
    assert snapshot.covered_outputs == ("direct",)


def test_future_evidence_is_filtered_before_it_enters_the_ledger() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    assert ledger.append(_evidence("future", source="future")) == ("future",)
    # A source_date beyond the cutoff must be rejected by the append boundary.
    future = AgentEvidence(
        tool="web_search",
        title="future",
        detail="future",
        source="future",
        source_date="2026-07-25",
        content_hash="future-2",
    )
    assert ledger.append(future) == ()
    assert "future-2" not in ledger.snapshot().evidence_ids


def test_unbound_new_evidence_cannot_count_as_gap_progress() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    ledger.open_gap("counterpoint")
    before = ledger.snapshot()

    ledger.append(_evidence("unrelated", source="unrelated-source"))
    ledger.close_gap("counterpoint")
    progress = progress_from_ledger(before, ledger.snapshot())

    assert progress.effective_new_evidence == 0
    assert not progress.coverage_delta.progressed
