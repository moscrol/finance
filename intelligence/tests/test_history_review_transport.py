"""The reviewer sidecar comes from the same producer, without changing writer input."""
import hashlib
import json

import pytest

from intelligence.history_context_cli import encode_payload, history_payload
from intelligence.services import market_regime_analogs, river_lens
from intelligence.tests.test_river_history_consumption import _apply_changed_gap, _make_db


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "synthetic.duckdb"
    _make_db(path)
    return path


@pytest.mark.parametrize("changed,cutoff", [(False, "2025-04-10"), (True, "2025-04-02")])
def test_review_sidecar_keeps_public_tool_bytes_and_original_grade(db, changed, cutoff):
    if changed:
        _apply_changed_gap(db)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    public = history_payload(db, as_of=cutoff)
    reviewed = history_payload(db, as_of=cutoff, review_readouts=True)
    assert reviewed["schema_version"] == "finance-history-review-source/v1"
    assert reviewed["public_text"] == encode_payload(public)
    assert json.loads(reviewed["public_text"])["evidence_grade"] == "INFERRED"
    assert "readouts" not in public
    assert len(encode_payload(reviewed).encode()) <= 48_000
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_review_readouts_are_complete_same_source_typed_objects(db):
    reviewed = history_payload(db, as_of="2025-04-10", review_readouts=True)
    public = json.loads(reviewed["public_text"])
    expected = [
        market_regime_analogs.load_market_regime_artifact(db, as_of="2025-04-10").model_payload(),
        river_lens.lens_from_db(db_path=db, as_of="2025-04-10", knowledge_cutoff="2025-04-10", window=20, step=5, top=3).model_payload(),
    ]
    for block, item, payload in zip(public["blocks"], reviewed["readouts"], expected, strict=True):
        assert item == {"source_sha256": block["sha256"], "payload": payload}
        assert market_regime_analogs.model_readout_block(payload) in block["detail"]


def test_review_transport_preserves_absent_source_and_other_lens(db, monkeypatch):
    monkeypatch.setattr(market_regime_analogs, "load_market_regime_artifact", lambda *a, **kw: market_regime_analogs.MarketRegimeArtifact(
        window=20, current_summary={}, analogs=(), missing_features=(),
    ))
    reviewed = history_payload(db, as_of="2025-04-10", review_readouts=True)
    assert reviewed["readouts"][0]["payload"] is None
    assert "historical_analogs gap" in json.loads(reviewed["public_text"])["blocks"][0]["detail"]
    assert reviewed["readouts"][1]["payload"]["set"] == "river"


def test_review_transport_does_not_create_a_missing_database(tmp_path):
    db = tmp_path / "absent.duckdb"
    with pytest.raises(FileNotFoundError):
        history_payload(db, as_of="2025-04-10", review_readouts=True)
    assert not db.exists()
