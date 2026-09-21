"""Runtime snapshots must compose with main's dispatch-level IO provenance."""
from dataclasses import replace

import pytest

from intelligence.services.episode_evidence import EpisodeEvidenceSnapshot
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.tests.test_episode_evidence_snapshot import _atom, _fixture, _legacy_payload, _resign


@pytest.mark.parametrize("effect", ["local_read", "external_or_mixed", "unknown"])
def test_v3_roundtrip_preserves_exact_io_provenance(effect):
    ledger = EvidenceLedger()
    atom = _atom(io_effect=effect)
    ledger.append(atom)
    payload = ledger.to_recovery_snapshot(episode_id="e", presented_evidence=(atom,))
    assert payload["schema_version"] == 3
    snapshot = EpisodeEvidenceSnapshot.from_dict(payload, episode_id="e")
    assert snapshot.presented_evidence == (atom,)
    assert snapshot.entries[0].atom.io_effect == effect
    assert snapshot.to_dict() == payload
    assert EvidenceLedger.from_recovery_snapshot(payload, episode_id="e").items() == (atom,)


@pytest.mark.parametrize("effect", [None, True, 1, "local", "", {}, ["local_read"]])
def test_v3_rejects_unknown_or_coerced_io_declarations(effect):
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
    assert upgraded["schema_version"] == 3
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
