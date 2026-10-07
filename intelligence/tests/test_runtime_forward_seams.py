"""Runtime snapshots must compose with main's dispatch-level IO provenance (v3)
and the history line's immutable source identity (v4)."""
from dataclasses import replace

import pytest

from intelligence.services.agent_research import HistoricalEvidenceProvenance
from intelligence.services.episode_evidence import EpisodeEvidenceSnapshot
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.tests.test_episode_evidence_snapshot import _atom, _fixture, _legacy_payload, _resign

REF = "run-history-review/history-query-" + "a" * 64 + ".json"


def _history_atom(identity="history-row-0", **changes):
    provenance = HistoricalEvidenceProvenance(
        query_id="history-query-stable", operation="find_analogues",
        purpose="historical_comparison", result_ref=REF,
        row_index=0, row_identity="history-query-stable:row:0", row_hash="b" * 16,
    )
    provenance.validate()
    return _atom(
        identity, tool="history_query", internal_locator=REF,
        independent_key="history-query-stable", history_provenance=provenance, **changes,
    )


@pytest.mark.parametrize("effect", ["local_read", "external_or_mixed", "unknown"])
def test_current_roundtrip_preserves_exact_io_provenance(effect):
    ledger = EvidenceLedger()
    atom = _atom(io_effect=effect)
    ledger.append(atom)
    payload = ledger.to_recovery_snapshot(episode_id="e", presented_evidence=(atom,))
    assert payload["schema_version"] == 5
    snapshot = EpisodeEvidenceSnapshot.from_dict(payload, episode_id="e")
    assert snapshot.presented_evidence == (atom,)
    assert snapshot.entries[0].atom.io_effect == effect
    assert snapshot.to_dict() == payload
    assert EvidenceLedger.from_recovery_snapshot(payload, episode_id="e").items() == (atom,)


@pytest.mark.parametrize("effect", [None, True, 1, "local", "", {}, ["local_read"]])
def test_current_rejects_unknown_or_coerced_io_declarations(effect):
    ledger = EvidenceLedger()
    atom = _atom(io_effect=effect)
    ledger.append(atom)
    with pytest.raises(ValueError):
        ledger.to_recovery_snapshot(episode_id="e", presented_evidence=(atom,))


@pytest.mark.parametrize("location", ["entries", "presentations"])
@pytest.mark.parametrize("mutation", ["missing", "forged", "extra"])
def test_io_provenance_is_integrity_bound_and_cannot_change_only_in_presentation(location, mutation):
    _, _, payload = _fixture()
    atom = payload[location][0]["atom"]
    if mutation == "missing":
        del atom["io_effect"]
    elif mutation == "extra":
        atom["unreviewed_field"] = "value"
    else:
        atom["io_effect"] = "local_read"
        with pytest.raises(ValueError, match="digest"):
            EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    _resign(payload)
    with pytest.raises(ValueError):
        EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


@pytest.mark.parametrize("version", [1, 2])
def test_old_snapshots_remain_exact_and_do_not_invent_local_read_authority(version):
    _, _, payload = _fixture()
    old = _legacy_payload(payload, version)
    restored = EpisodeEvidenceSnapshot.from_dict(old, episode_id="episode")
    assert restored.to_dict() == old
    assert all(item.io_effect == "unknown" for item in restored.presented_evidence)
    upgraded = EvidenceLedger.from_recovery_snapshot(old, episode_id="episode").to_recovery_snapshot(
        episode_id="episode", presented_evidence=restored.presented_evidence,
    )
    assert upgraded["schema_version"] == 5
    assert upgraded["entries"][0]["atom"]["io_effect"] == "unknown"
    # An old version is not a route to erase the new authority field.
    old["entries"][0]["atom"]["io_effect"] = "local_read"
    _resign(old)
    with pytest.raises(ValueError):
        EpisodeEvidenceSnapshot.from_dict(old, episode_id="episode")


def test_new_provenance_cannot_be_silently_downgraded_to_legacy_wire_shape():
    ledger = EvidenceLedger()
    atom = _atom(io_effect="local_read")
    ledger.append(atom)
    payload = ledger.to_recovery_snapshot(episode_id="e", presented_evidence=(atom,))
    snapshot = EpisodeEvidenceSnapshot.from_dict(payload, episode_id="e")
    with pytest.raises(ValueError, match="legacy"):
        replace(snapshot, schema_version=2).to_dict()


# --- v4: historical source identity travels with the private atom -------------


@pytest.mark.parametrize("version", [4, 5])
def test_v4_and_current_roundtrip_preserve_history_provenance_as_a_complete_record(version):
    ledger = EvidenceLedger()
    atom = _history_atom()
    ledger.append(atom)
    payload = ledger.to_recovery_snapshot(episode_id="e", presented_evidence=(atom,))
    if version == 4:
        payload = _legacy_payload(payload, 4)
    assert payload["schema_version"] == version
    stored = payload["entries"][0]["atom"]["history_provenance"]
    assert stored["query_id"] == "history-query-stable" and stored["row_index"] == 0
    assert stored["research_only"] is True and stored["promotion_eligible"] is False
    snapshot = EpisodeEvidenceSnapshot.from_dict(payload, episode_id="e")
    assert snapshot.presented_evidence == (atom,)
    assert snapshot.entries[0].atom.history_provenance == atom.history_provenance
    assert snapshot.entries[0].atom.content_hash == atom.content_hash
    assert snapshot.entries[0].atom.retrieval_direction is None
    assert snapshot.to_dict() == payload
    assert EvidenceLedger.from_recovery_snapshot(payload, episode_id="e").items() == (atom,)


@pytest.mark.parametrize("version", [4, 5])
def test_v4_and_current_ordinary_atoms_persist_an_explicit_null_provenance(version):
    _, _, payload = _fixture()
    if version == 4:
        payload = _legacy_payload(payload, 4)
    assert all(entry["atom"]["history_provenance"] is None for entry in payload["entries"])
    restored = EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    assert all(item.history_provenance is None for item in restored.presented_evidence)


@pytest.mark.parametrize("mutation", ["row_hash", "operation", "extra_key", "missing_key", "qualification"])
@pytest.mark.parametrize("version", [4, 5])
def test_v4_and_current_restore_rerun_provenance_identity_validation(mutation, version):
    ledger = EvidenceLedger()
    atom = _history_atom()
    ledger.append(atom)
    payload = ledger.to_recovery_snapshot(episode_id="e", presented_evidence=(atom,))
    if version == 4:
        payload = _legacy_payload(payload, 4)
    for location in ("entries", "presentations"):
        provenance = payload[location][0]["atom"]["history_provenance"]
        if mutation == "row_hash":
            provenance["row_hash"] = "not-hex"
        elif mutation == "operation":
            provenance["operation"] = "invent_history"
        elif mutation == "extra_key":
            provenance["signature"] = "trusted"
        elif mutation == "missing_key":
            del provenance["row_identity"]
        else:
            provenance["decision_eligible"] = True
    _resign(payload)
    with pytest.raises(ValueError):
        EpisodeEvidenceSnapshot.from_dict(payload, episode_id="e")


def test_v3_snapshots_remain_exact_and_do_not_invent_history_provenance():
    _, presented, payload = _fixture()
    old = _legacy_payload(payload, 3)
    assert "history_provenance" not in old["entries"][0]["atom"]
    restored = EpisodeEvidenceSnapshot.from_dict(old, episode_id="episode")
    assert restored.to_dict() == old
    assert all(item.history_provenance is None for item in restored.presented_evidence)
    # v3 keeps its own audited IO declaration exactly; only the v4 field is absent.
    assert restored.presented_evidence == presented
    assert [item.io_effect for item in restored.presented_evidence] == [item.io_effect for item in presented]
    upgraded = EvidenceLedger.from_recovery_snapshot(old, episode_id="episode").to_recovery_snapshot(
        episode_id="episode", presented_evidence=restored.presented_evidence,
    )
    assert upgraded["schema_version"] == 5
    assert upgraded["entries"][0]["atom"]["history_provenance"] is None
    # An old version is not a route to smuggle source identity past validation.
    old["entries"][0]["atom"]["history_provenance"] = None
    _resign(old)
    with pytest.raises(ValueError):
        EpisodeEvidenceSnapshot.from_dict(old, episode_id="episode")


def test_history_provenance_cannot_be_silently_downgraded_to_v3_wire_shape():
    ledger = EvidenceLedger()
    atom = _history_atom()
    ledger.append(atom)
    payload = ledger.to_recovery_snapshot(episode_id="e", presented_evidence=(atom,))
    snapshot = EpisodeEvidenceSnapshot.from_dict(payload, episode_id="e")
    with pytest.raises(ValueError, match="legacy"):
        replace(snapshot, schema_version=3).to_dict()


def test_retrieval_direction_cannot_hide_same_hash_historical_source_conflict():
    atom = _history_atom(retrieval_direction="support")
    ledger = EvidenceLedger()
    ledger.append(atom)
    changed = replace(
        atom, retrieval_direction="counter",
        history_provenance=replace(atom.history_provenance, row_hash="c" * 16),
    )
    with pytest.raises(ValueError, match="differs from its admitted original"):
        ledger.to_recovery_snapshot(episode_id="e", presented_evidence=(changed,))
