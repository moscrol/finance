from datetime import datetime, timedelta, timezone
import json

import pytest

from intelligence.services.opinion_attention import (
    adapt_aihot, append_observations, attention_snapshot, canonical_url, cutoff_for_date, read_ledger,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 29, 8, tzinfo=UTC)
MAPPING = {
    "sources": {"A": {"participant_key": "publisher:A", "kind": "official"}, "B": {"participant_key": "publisher:B", "kind": "media"}},
    "entities": {"copper": {"id": "s1", "name": "铜"}},
    "items": {"a": {"event_key": "release-1", "entity_keys": ["copper"]}, "b": {"event_key": "release-1", "entity_keys": ["copper"]}},
}


def item(id="a", source="A", when=None):
    return {"id": id, "source": source, "title": "铜相关消息", "summary": "上游摘要，未经核验",
            "publishedAt": (when or NOW - timedelta(hours=1)).isoformat(),
            "discoveredAt": "2026-09-01T08:00:00+08:00", "links": {"original": f"https://example.com/{id}"}}


def adapt(items, mapping=MAPPING, now=NOW):
    rows, errors = adapt_aihot({"items": items}, mapping, now=now)
    assert not errors
    return rows


def test_local_clock_not_upstream_discovery():
    row = adapt([item()])[0]
    assert row["recorded_at"].startswith("2026-09-29")
    assert attention_snapshot([row], NOW - timedelta(seconds=1))["event_count"] == 0


def test_no_future_publication():
    rows, errors = adapt_aihot([item(when=NOW + timedelta(hours=1))], MAPPING, now=NOW)
    assert not rows and errors


def test_canonical_url_and_safety():
    assert canonical_url("https://EXAMPLE.com/a?utm_source=x&b=2#hi") == "https://example.com/a?b=2"
    for url in ["javascript:alert(1)", "file:///etc/passwd", "https://user:pw@example.com/a"]:
        with pytest.raises(ValueError):
            canonical_url(url)


def test_idempotent_import_and_lock(tmp_path):
    path = tmp_path / "obs.jsonl"
    assert append_observations(path, adapt([item()])) == {"added": 1, "skipped": 0}
    assert append_observations(path, adapt([item()], now=NOW + timedelta(hours=1))) == {"added": 0, "skipped": 1}
    assert len(read_ledger(path)) == 1


def test_revision_does_not_rewrite_history(tmp_path):
    path = tmp_path / "obs.jsonl"
    append_observations(path, adapt([item()]))
    second = item()
    second["title"] = "更正后的标题"
    append_observations(path, adapt([second], now=NOW + timedelta(hours=2)))
    rows = read_ledger(path)
    assert len(rows) == 2 and rows[1]["supersedes"] == rows[0]["revision_id"]
    assert attention_snapshot(rows, NOW)["events"][0]["title"] == "铜相关消息"
    assert attention_snapshot(rows, NOW + timedelta(hours=3))["events"][0]["title"] == "更正后的标题"


def test_source_counts_once_and_half_life():
    rows = adapt([item("a", when=NOW - timedelta(hours=24)), item("b", source="A", when=NOW - timedelta(hours=24))])
    event = attention_snapshot(rows, NOW)["events"][0]
    assert event["participant_count"] == 1 and event["heat"] == .5
    assert event["report_count"] == 2


def test_shared_origin_deduplicates_publishers():
    mapping = json.loads(json.dumps(MAPPING))
    for cfg in mapping["items"].values():
        cfg["origin_key"] = "announcement:1"
    event = attention_snapshot(adapt([item("a"), item("b", "B")], mapping), NOW)["events"][0]
    assert event["participant_count"] == 1 and event["lineage_complete"]


def test_unmapped_not_guessed_and_not_verified():
    event = attention_snapshot(adapt([item()], {}), NOW)["events"][0]
    assert event["grouping"] == "unclustered" and event["heat"] is None
    assert event["entities"] == [] and event["evidence_status"] == "unreviewed"
    assert event["unknown_sources"] == 1


def test_entity_match_is_exact():
    data = adapt([item()])
    assert attention_snapshot(data, NOW, entity_id="s1")["event_count"] == 1
    assert attention_snapshot(data, NOW, entity_id="s10")["event_count"] == 0


def test_missing_timezone_excluded_not_zero_heat():
    it = item()
    it["publishedAt"] = "2026-09-29"
    snap = attention_snapshot(adapt([it]), NOW)
    assert snap["event_count"] == 0 and snap["missing_publication_times"] == 1


def test_48h_boundary_and_no_historical_backfill_heat():
    assert attention_snapshot(adapt([item(when=NOW - timedelta(hours=48))]), NOW)["event_count"] == 0
    rows = adapt([item(when=NOW - timedelta(days=10))])
    assert attention_snapshot(rows, NOW)["event_count"] == 0
    assert attention_snapshot(rows, NOW - timedelta(days=10))["event_count"] == 0


def test_no_heat_trend_without_collection_coverage():
    snap = attention_snapshot(adapt([item()]), NOW)
    assert snap["events"][0]["trend_pct"] is None
    assert snap["collection_status"] == "imported_snapshot"


def test_correction_removal_is_append_only(tmp_path):
    path = tmp_path / "obs.jsonl"
    append_observations(path, adapt([item()]))
    mapping = json.loads(json.dumps(MAPPING))
    mapping["items"]["a"]["removed"] = True
    append_observations(path, adapt([item()], mapping, NOW + timedelta(hours=1)))
    rows = read_ledger(path)
    assert attention_snapshot(rows, NOW)["event_count"] == 1
    assert attention_snapshot(rows, NOW + timedelta(hours=2))["event_count"] == 0


def test_corrupt_ledger_fails_closed(tmp_path):
    path = tmp_path / "obs.jsonl"
    path.write_text('{"broken":1}\n')
    with pytest.raises(ValueError):
        read_ledger(path)


def test_cutoff_is_chinese_end_of_day_and_not_future():
    from datetime import date
    value = cutoff_for_date(date(2026, 9, 28), now=NOW)
    assert value.hour == 15 and value.minute == 59
    assert cutoff_for_date(date(2030, 1, 1), now=NOW) == NOW


def test_river_bridge_is_separate_from_reports_and_time_safe(tmp_path):
    from intelligence.services.opinion_attention_bridge import river_attention_objects
    path = tmp_path / "observations.jsonl"
    assert river_attention_objects("2026-09-29", "2026-09-29", "s1", ledger_path=path) == []
    append_observations(path, adapt([item()]))
    assert river_attention_objects("2026-09-28", "2026-09-28", "s1", ledger_path=path) == []
    first = river_attention_objects("2026-09-29", "2026-09-29", "s1", ledger_path=path)
    second = river_attention_objects("2026-09-29", "2026-09-29", "s1", ledger_path=path)
    assert first == second
    assert first[0]["object_type"] == "public_news_attention"
    assert first[0]["payload"]["subtrack"] == "public_attention"
    assert first[0]["payload"]["evidence_status"] == "unreviewed"


def test_slice_wires_public_attention_without_erasing_report_gap(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path

    import duckdb

    from intelligence.services.river import Gap, slice_river

    database = tmp_path / "market.duckdb"
    ledger = tmp_path / "observations.jsonl"
    checkpoints = tmp_path / "checkpoints.jsonl"
    checkpoints.write_text("", encoding="utf-8")
    monkeypatch.setenv("OPINION_ATTENTION_LEDGER", str(ledger))
    with duckdb.connect(str(database)) as con:
        con.execute((Path(__file__).resolve().parents[1] / "market_feature_store/schema.sql").read_text())
        for day in ("2026-09-28", "2026-09-29"):
            con.execute("INSERT INTO fact_market_daily (trade_date, source) VALUES (?, 'test')", [day])
            con.execute("""INSERT INTO fact_sector_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, source)
                VALUES (?, 'legacy', 's1', '铜', 1.0, 'test')""", [day])
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    kwargs = {"db_path": database, "checkpoints_path": checkpoints}
    original = slice_river("2026-09-29", "铜", **kwargs)
    assert isinstance(original.tracks["opinion"], Gap)
    append_observations(ledger, adapt([item()]))
    assert isinstance(slice_river("2026-09-28", "铜", knowledge_cutoff="2026-09-29", allow_hindsight=True, **kwargs).tracks["opinion"], Gap)
    result = slice_river("2026-09-29", "铜", **kwargs)
    objects = result.tracks["opinion"]
    assert isinstance(objects, list)
    assert objects[0].object_type == "public_news_attention"
    assert objects[0].payload["report_coverage_gap"] == original.tracks["opinion"].to_dict()
    assert result.to_dict() == slice_river("2026-09-29", "铜", **kwargs).to_dict()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_restoring_previous_content_is_a_new_revision(tmp_path):
    path = tmp_path / "obs.jsonl"
    append_observations(path, adapt([item()]))
    mapping = json.loads(json.dumps(MAPPING))
    mapping["items"]["a"]["removed"] = True
    append_observations(path, adapt([item()], mapping, NOW + timedelta(hours=1)))
    result = append_observations(path, adapt([item()], now=NOW + timedelta(hours=2)))
    assert result["added"] == 1
    rows = read_ledger(path)
    assert len({row["revision_id"] for row in rows}) == 3
    assert attention_snapshot(rows, NOW + timedelta(hours=3))["event_count"] == 1
