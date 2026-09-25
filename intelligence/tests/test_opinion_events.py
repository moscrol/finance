from __future__ import annotations

import copy
import hashlib
import json

import pytest

from intelligence.services import catalyst_attribution as ca
from intelligence.services.opinion_events import (
    SCHEMA, STORE_RELPATH, OpinionDataError, load_events, record_hash,
)
from intelligence.services.workbench_overview import _load_sellside
from scripts.review_opinion_events import publish


def write_events(wiki, events):
    path = wiki / STORE_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in events), encoding="utf-8")
    return path


def event(**kwargs):
    return {
        "event_id": "e1", "report_date": "2026-09-11", "ingested_at": "2026-09-21",
        "target": "Company", "concept": "wrong theme", "hard_evidence": ["unverified"],
        **kwargs,
    }


def review(wiki, original, action="replace", **kwargs):
    raw = b"Company sent samples; orders are expected, not obtained."
    rel = "raw/sellside/original.txt"
    path = wiki / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    replacement = {
        "concept": "diamond cooling", "term": "diamond cooling", "claim_summary": raw.decode(),
        "hardness": "软推演", "hard_evidence": [], "soft_claims": [raw.decode()],
        "catalysts": [], "date_status": "confirmed", "evidence_layer": "L4",
        "verification_status": "unverified",
    }
    return {
        "event_id": original["event_id"], "base_sha256": record_hash(original), "supersedes": None,
        "action": action, "reason": "Review did not verify a primary disclosure.",
        "raw_ref": {"path": rel, "sha256": hashlib.sha256(raw).hexdigest(), "start": 0, "end": len(raw)},
        **({"replacement": replacement} if action == "replace" else {}), **kwargs,
    }


def write_batch(wiki, correction, bid="batch1", stamp="2026-09-22T01:00:00+08:00"):
    directory = (wiki / STORE_RELPATH).parent / "corrections"
    directory.mkdir(exist_ok=True)
    path = directory / f"{bid}.json"
    path.write_text(json.dumps({
        "schema": SCHEMA, "batch_id": bid, "recorded_at": stamp, "corrections": [correction],
    }), encoding="utf-8")
    return path


@pytest.mark.parametrize("stamp", [None, "", "bad", "2026-02-30", "2026-09-11junk", "2026-09-11T12:00:00"])
def test_bad_or_missing_ingestion_is_not_report_date_fallback(tmp_path, stamp):
    write_events(tmp_path, [event(ingested_at=stamp)])
    warnings = []
    assert load_events(tmp_path, as_of="2026-09-22", warnings=warnings) == []
    assert "invalid_time=1" in warnings[0]


def test_cutoff_filters_report_and_ingestion_dates_and_timezone(tmp_path):
    write_events(tmp_path, [
        event(event_id="late"),
        event(event_id="known", ingested_at="2026-09-11"),
        event(event_id="last_second", ingested_at="2026-09-11T15:59:59+00:00"),
        event(event_id="tomorrow", ingested_at="2026-09-11T16:00:00+00:00"),
        event(event_id="future_report", report_date="2026-09-12", ingested_at="2026-09-11"),
        event(event_id="inferred", ingested_at="2026-09-11", date_status="inferred_unconfirmed"),
    ])
    rows = load_events(tmp_path, as_of="2026-09-11")
    assert {r["event_id"] for r in rows} == {"known", "last_second"}
    with pytest.raises(ValueError, match="allow_hindsight"):
        load_events(tmp_path, as_of="2026-09-11", knowledge_cutoff="2026-09-22")
    later = load_events(tmp_path, as_of="2026-09-11", knowledge_cutoff="2026-09-22", allow_hindsight=True)
    assert {r["event_id"] for r in later} == {"late", "known", "last_second", "tomorrow"}


def test_correction_is_not_retroactive_and_original_unchanged(tmp_path):
    original = event()
    path = write_events(tmp_path, [original])
    before = path.read_bytes()
    write_batch(tmp_path, review(tmp_path, original))
    assert load_events(tmp_path, as_of="2026-09-11") == []
    assert load_events(tmp_path, as_of="2026-09-21")[0]["concept"] == "wrong theme"
    updated = load_events(tmp_path, as_of="2026-09-22")[0]
    assert updated["concept"] == "diamond cooling"
    assert updated["ingested_at"] == "2026-09-21"
    assert updated["recorded_at"] == "2026-09-22T01:00:00+08:00"
    assert updated["hard_evidence"] == []
    assert updated["revision_id"] == "batch1:e1"
    assert path.read_bytes() == before


@pytest.mark.parametrize("action", ["retract", "quarantine"])
def test_removed_events_not_exposed_and_no_false_market_only(tmp_path, action):
    original = event()
    write_events(tmp_path, [original])
    write_batch(tmp_path, review(tmp_path, original, action))
    warnings = []
    assert load_events(tmp_path, as_of="2026-09-22", warnings=warnings) == []
    assert f"{action}=1" in warnings[0]
    briefings = tmp_path / "briefings"
    briefings.mkdir()
    (briefings / "2026-09-22.md").write_text("Unrelated briefing content", encoding="utf-8")
    index = ca.build_catalyst_index(tmp_path, "2026-09-22", window_days=30)
    assert ca.attribute_theme(index, "wrong theme")["status"] == ca.STATUS_SOURCE_MISSING


def test_revision_chain_can_release_quarantine(tmp_path):
    original = event()
    write_events(tmp_path, [original])
    write_batch(tmp_path, review(tmp_path, original, "quarantine"))
    write_batch(tmp_path, review(tmp_path, original, supersedes="batch1:e1"), "batch2", "2026-09-23T01:00:00+08:00")
    assert load_events(tmp_path, as_of="2026-09-22") == []
    assert load_events(tmp_path, as_of="2026-09-23")[0]["concept"] == "diamond cooling"


@pytest.mark.parametrize("mutation", ["hash", "supersedes", "quote", "raw_hash", "path", "upgrade", "unknown", "bad_action"])
def test_invalid_review_fails_closed(tmp_path, mutation):
    original = event()
    write_events(tmp_path, [original])
    correction = review(tmp_path, original)
    if mutation == "hash":
        correction["base_sha256"] = "bad"
    elif mutation == "supersedes":
        correction["supersedes"] = "nonexistent"
    elif mutation == "quote":
        correction["replacement"]["claim_summary"] = "fabricated"
    elif mutation == "raw_hash":
        correction["raw_ref"]["sha256"] = "bad"
    elif mutation == "path":
        correction["raw_ref"]["path"] = "raw/sellside/../../../elsewhere"
    elif mutation == "upgrade":
        correction["replacement"]["evidence_layer"] = "L2"
    elif mutation == "unknown":
        correction["event_id"] = "missing"
    else:
        correction["action"] = "delete"
    write_batch(tmp_path, correction)
    with pytest.raises(OpinionDataError):
        load_events(tmp_path, as_of="2026-09-22")
    assert ca.build_catalyst_index(tmp_path, "2026-09-22").opinion_events == []
    warnings = []
    assert _load_sellside(tmp_path, as_of="2026-09-22", warnings=warnings)[2] is None
    assert warnings


def test_publisher_stamps_once_and_does_not_overwrite(tmp_path, monkeypatch):
    original = event()
    path = write_events(tmp_path, [original])
    raw_before = path.read_bytes()
    monkeypatch.setattr("scripts.review_opinion_events.utc_now", lambda: "2026-09-22T01:00:00+08:00")
    proposal = {"batch_id": "review1", "corrections": [review(tmp_path, original, "quarantine")]}
    dest, created = publish(tmp_path, proposal)
    assert created
    before = dest.read_bytes()
    assert publish(tmp_path, proposal) == (dest, False)
    assert dest.read_bytes() == before
    conflict = copy.deepcopy(proposal)
    conflict["corrections"][0]["reason"] = "Changed"
    with pytest.raises(OpinionDataError, match="different content"):
        publish(tmp_path, conflict)
    monkeypatch.setattr("scripts.review_opinion_events.utc_now", lambda: "2026-09-23T01:00:00+08:00")
    second = {"batch_id": "review2", "corrections": [review(tmp_path, original, supersedes="review1:e1")]}
    publish(tmp_path, second)
    assert load_events(tmp_path, as_of="2026-09-23")[0]["concept"] == "diamond cooling"
    assert path.read_bytes() == raw_before


def test_publisher_validates_entire_batch_before_publication(tmp_path, monkeypatch):
    original = event()
    write_events(tmp_path, [original])
    monkeypatch.setattr("scripts.review_opinion_events.utc_now", lambda: "2026-09-22T01:00:00+08:00")
    correction = review(tmp_path, original)
    with pytest.raises(OpinionDataError):
        publish(tmp_path, {"batch_id": "invalid", "corrections": [correction, correction]})
    assert not ((tmp_path / STORE_RELPATH).parent / "corrections/invalid.json").exists()
    with pytest.raises(OpinionDataError):
        publish(tmp_path, {"batch_id": "../invalid", "corrections": [correction]})


def test_catalyst_filters_late_and_uses_revised_theme(tmp_path):
    original = event()
    write_events(tmp_path, [original])
    write_batch(tmp_path, review(tmp_path, original))
    early = ca.build_catalyst_index(tmp_path, "2026-09-11")
    assert early.opinion_events == []
    assert any("late_ingestion=1" in w for w in early.warnings)
    assert ca.freshness_problems(tmp_path, "2026-09-11")
    current = ca.build_catalyst_index(tmp_path, "2026-09-22", window_days=30)
    result = ca.attribute_theme(current, "diamond cooling")
    assert result["status"] == ca.STATUS_NARRATIVE_HIT
    assert result["events"][0]["revision_id"] == "batch1:e1"
    assert ca.attribute_theme(current, "wrong theme")["events"] == []


def test_overview_unverified_hardness_never_grants_priority(tmp_path):
    original = event()
    write_events(tmp_path, [original])
    _, flow, day = _load_sellside(tmp_path, as_of="2026-09-21")
    assert day == "2026-09-11"
    assert not flow["priority"]
    assert flow["confirmation"]
    write_batch(tmp_path, review(tmp_path, original))
    _, flow, _ = _load_sellside(tmp_path, as_of="2026-09-22")
    assert flow["confirmation"][0]["theme"] == "diamond cooling"
    assert not flow["priority"]


def test_overview_outcomes_require_matching_revision_and_known_computation(tmp_path):
    original = event()
    store = write_events(tmp_path, [original]).parent
    outcomes = [{
        "event_id": "e1", "source_id": "s1", "computed_at": "2026-09-21",
        "ret_5d_complete": True, "excess_5d": 1.0,
    }] * 5
    path = store / "outcomes.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in outcomes), encoding="utf-8")
    assert len(_load_sellside(tmp_path, as_of="2026-09-21")[0]) == 1
    write_batch(tmp_path, review(tmp_path, original))
    assert _load_sellside(tmp_path, as_of="2026-09-22")[0] == []
    outcomes = [{**row, "revision_id": "batch1:e1", "computed_at": "2026-09-23"} for row in outcomes]
    path.write_text("".join(json.dumps(row) + "\n" for row in outcomes), encoding="utf-8")
    assert _load_sellside(tmp_path, as_of="2026-09-22")[0] == []
    assert len(_load_sellside(tmp_path, as_of="2026-09-23")[0]) == 1


def test_corrupted_json_is_not_an_empty_healthy_source(tmp_path):
    path = write_events(tmp_path, [])
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(OpinionDataError):
        load_events(tmp_path, as_of="2026-09-22")
    assert not ca.build_catalyst_index(tmp_path, "2026-09-22").opinion_source_available


@pytest.mark.parametrize("bad_id", [None, "", [], {}, 5])
def test_invalid_and_duplicate_ids_are_excluded(tmp_path, bad_id):
    write_events(tmp_path, [event(event_id=bad_id), event(), event()])
    warnings = []
    assert load_events(tmp_path, as_of="2026-09-22", warnings=warnings) == []
    assert "invalid_or_duplicate_id=3" in warnings[0]


def test_corrupt_future_review_never_falls_back_to_original(tmp_path):
    original = event()
    write_events(tmp_path, [original])
    path = write_batch(tmp_path, review(tmp_path, original), stamp="2026-09-25T01:00:00+08:00")
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(OpinionDataError):
        load_events(tmp_path, as_of="2026-09-21")


def test_research_consumers_use_cutoff_and_reviewed_projection(tmp_path):
    from intelligence.services.event_pricing.narrative import load_opinion_events as pricing_load
    from intelligence.services.teaching_framework.narrative import load_opinion_events as teaching_load

    original = event()
    write_events(tmp_path, [original])
    write_batch(tmp_path, review(tmp_path, original))
    assert teaching_load(tmp_path, as_of="2026-09-11") == []
    assert pricing_load(tmp_path, str(STORE_RELPATH), as_of="2026-09-11")[0] == []
    assert teaching_load(tmp_path, as_of="2026-09-21")[0]["concept"] == "wrong theme"
    assert teaching_load(tmp_path, as_of="2026-09-22")[0]["revision_id"] == "batch1:e1"
    rows, gaps = pricing_load(tmp_path, str(STORE_RELPATH), as_of="2026-09-22")
    assert not gaps
    assert rows[0].concept == "diamond cooling"
    assert rows[0].event_id == "batch1:e1"
    assert rows[0].hardness == "软推演"


def test_research_entrypoints_surface_quarantine_as_gap(tmp_path):
    from intelligence.services.event_pricing.narrative import load_opinion_events as pricing_load
    from scripts.teaching_framework import _merge_narrative

    original = event(report_date="2020-01-01", ingested_at="2020-01-02")
    write_events(tmp_path, [original])
    write_batch(tmp_path, review(tmp_path, original, "quarantine"), stamp="2020-01-03T01:00:00+08:00")
    rows, gaps = pricing_load(tmp_path, str(STORE_RELPATH), as_of="2026-09-22")
    assert not rows and any("quarantine=1" in g.detail for g in gaps)
    sector_rows = [{"trade_date": "2020-01-02"}]
    note = _merge_narrative(sector_rows, str(tmp_path), ["2020-01-01", "2020-01-02"], {})
    assert note["status"] == "partial"
    assert sector_rows[0]["narrative_gap"] == "narrative_source_filtered"
    assert "narrative_events" not in sector_rows[0]


def test_inferred_replacement_requires_explicit_opt_in(tmp_path):
    original = event()
    write_events(tmp_path, [original])
    correction = review(tmp_path, original)
    correction["replacement"]["date_status"] = "inferred_unconfirmed"
    write_batch(tmp_path, correction)
    assert load_events(tmp_path, as_of="2026-09-22") == []
    assert len(load_events(tmp_path, as_of="2026-09-22", allow_inferred=True)) == 1
