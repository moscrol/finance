"""Public citations preserve episode ordinals across filtering and deduplication."""

from __future__ import annotations

from dataclasses import replace

from intelligence.runtime.continuous_turn_adapter import _public_citation_projection
from intelligence.runtime.conversation_orchestrator import _sanitize_citation_list
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_protocol import (
    evidence_ordinal_table,
    resolve_evidence_refs,
)
from intelligence.tests.test_continuous_turn_adapter import _scripted_episode_result


def _evidence(digest, *, title="Quarterly results"):
    return AgentEvidence(
        tool="market_data",
        title=title,
        detail=digest,
        source="Public filing",
        source_date="2026-07-22",
        content_hash=digest,
    )


def test_ledger_identity_survives_filters_duplicate_labels_and_duplicate_hashes():
    ledger = (
        _evidence(""),
        _evidence("unbound"),
        _evidence("private", title="task_frame_hash=SECRET"),
        _evidence("revenue"),
        _evidence("profit"),
        _evidence("revenue"),
        _evidence("gap-only"),
        _evidence("no-labels", title=""),
    )
    ledger = (*ledger[:-1], replace(ledger[-1], source="", source_date=""))
    outcome = AgentOutcome(
        task_frame_hash="test",
        status="partial",
        draft="Results (E3, E4).",
        evidence=ledger,
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        usage=AgentUsage(),
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "test"}),),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment", ("private", "revenue", "profit", "no-labels")
            ),
            OutputEvidenceBinding("counterpoint", ("gap-only",)),
        ),
    )
    public = _public_citation_projection(
        outcome,
        frozenset({"SECRET"}),
        allowed_output_ids=frozenset({"direct_assessment"}),
    )
    assert [row["evidence_id"] for row in public] == ["E3", "E4"]
    assert _sanitize_citation_list(list(public)) == list(public)
    assert resolve_evidence_refs([row["evidence_id"] for row in public], ledger) == (
        "revenue",
        "profit",
    )
    assert all(set(row) == {"evidence_id", "title", "source", "date"} for row in public)
    appended = replace(outcome, evidence=(*ledger, _evidence("later")))
    assert (
        _public_citation_projection(
            appended,
            frozenset({"SECRET"}),
            allowed_output_ids=frozenset({"direct_assessment"}),
        )
        == public
    )


def test_filtered_first_record_does_not_renumber_public_answer():
    evidence = (_evidence("unbound"), _evidence("supported"))
    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer="Quarterly results improved (E2).",
        evidence=evidence,
        bindings=(OutputEvidenceBinding("direct_assessment", ("supported",)),),
    )
    assert result.status == "completed"
    assert "E2" in result.answer
    assert [row["evidence_id"] for row in result.citations] == ["E2"]
    assert (
        result.citations[0]["evidence_id"]
        == evidence_ordinal_table(evidence)["supported"]
    )


def test_sanitizer_keeps_legacy_citations_without_inventing_ordinals():
    legacy = {
        "title": "Quarterly results",
        "source": "Public filing",
        "date": "2026-07-22",
    }
    assert _sanitize_citation_list([legacy, legacy]) == [legacy]
    assert "evidence_id" not in legacy
