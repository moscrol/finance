"""Offline CLI acceptance; every destination is an isolated temporary ledger."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from intelligence.services.opinion_attention import read_ledger
from scripts import import_aihot_attention as importer

ROOT = Path(__file__).resolve().parents[1]


def item(identity="a", **changes):
    return {
        "id": identity, "title": "一条未核实的公开消息", "summary": "上游模型或编辑摘要",
        "source": {"name": "Example Source"}, "publishedAt": "2020-01-01T09:00:00+08:00",
        "discoveredAt": "2020-01-02T08:00:00Z", "links": {"original": f"https://example.invalid/{identity}"},
        **changes,
    }


def mapping():
    return {
        "sources": {"Example Source": {"participant_key": "publisher:example", "kind": "media"}},
        "entities": {"reviewed-sector": {"id": "sector:test", "name": "测试板块"}},
        "items": {"a": {"event_key": "test-event", "origin_key": "origin:test", "entity_keys": ["reviewed-sector"]}},
    }


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def run_cli(export, map_path, ledger, *extra):
    env = {**os.environ, "OPINION_ATTENTION_LEDGER": str(ledger)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/import_aihot_attention.py"), str(export), "--mapping", str(map_path), *extra],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=10,
    )


def test_offline_cli_preview_apply_idempotency_revision_removal_and_restore(tmp_path):
    export = write_json(tmp_path / "export.json", [item(recorded_at="2000-01-01T00:00:00Z")])
    map_path = write_json(tmp_path / "mapping.json", mapping())
    ledger = tmp_path / "private" / "observations.jsonl"
    before = datetime.now(timezone.utc)
    dry = run_cli(export, map_path, ledger)
    assert dry.returncode == 0, dry.stderr
    preview = json.loads(dry.stdout)
    assert (preview["mode"], preview["accepted"], preview["mapped"], preview["grouped"], preview["written"]) == (
        "dry-run", 1, 1, 1, False,
    )
    assert not ledger.parent.exists()
    applied = run_cli(export, map_path, ledger, "--apply")
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["added"] == 1
    first_bytes = ledger.read_bytes()
    repeated = run_cli(export, map_path, ledger, "--apply")
    assert repeated.returncode == 0, repeated.stderr
    assert (json.loads(repeated.stdout)["skipped"], json.loads(repeated.stdout)["written"]) == (1, False)
    assert ledger.read_bytes() == first_bytes
    write_json(export, [item(title="更正标题")])
    assert run_cli(export, map_path, ledger, "--apply").returncode == 0
    removed = mapping()
    removed["items"]["a"]["removed"] = True
    write_json(map_path, removed)
    assert run_cli(export, map_path, ledger, "--apply").returncode == 0
    write_json(map_path, mapping())
    assert run_cli(export, map_path, ledger, "--apply").returncode == 0
    rows = read_ledger(ledger)
    assert len(rows) == 4
    assert [row["removed"] for row in rows] == [False, False, True, False]
    assert [row["supersedes"] for row in rows] == [None, *(row["revision_id"] for row in rows[:-1])]
    assert len({row["revision_id"] for row in rows}) == 4
    assert all(before <= datetime.fromisoformat(row["recorded_at"]) <= datetime.now(timezone.utc) for row in rows)
    assert all(row["evidence_status"] == "unreviewed" for row in rows)


def test_complete_envelope_empty_mapping_deduplicates_without_inferring(tmp_path):
    payload = {"schemaVersion": 1, "items": [item(), item()], "page": {"hasMore": False, "nextCursor": None}}
    ledger = tmp_path / "observations.jsonl"
    report = importer.import_payload(payload, {}, apply=True, ledger=ledger)
    assert (report["accepted"], report["added"], report["mapped"], report["grouped"], report["unknown_sources"]) == (1, 1, 0, 0, 1)
    row = read_ledger(ledger)[0]
    assert row["participant_key"] is None and row["origin_key"] is None and row["entities"] == []
    assert row["grouping"] == "unclustered" and row["evidence_status"] == "unreviewed"


@pytest.mark.parametrize("payload", [
    None, {}, {"items": []}, {"schemaVersion": True, "items": [], "page": {"hasMore": False}},
    {"schemaVersion": 2, "items": [], "page": {"hasMore": False}},
    {"schemaVersion": 1, "items": [item()]},
    {"schemaVersion": 1, "items": [item()], "page": {"hasMore": True, "nextCursor": "next"}},
    {"schemaVersion": 1, "items": [], "page": {"hasMore": False, "nextCursor": "next"}},
    [item(id=None)], [item(id={"token": "secret"})], [item(id=["a"])], [item(id=1)], [item(id=True)],
    [item(id=" ")], [item(id=" a")], [item(id="a\nb")],
    [item(), item(title="conflicting revision")], [item(), item("b", title="changed", links=item()["links"])],
    [item(), item("b", title={"token": "secret"})], [item(source=3)], [item(source={})],
    [item(selected="true")], [item(summary=[])], [item(links={"original": ["secret"]})],
    [item(links={"original": "https://user:secret@example.invalid"})],
    [item(publishedAt="9999-01-01T00:00:00Z")], [item(publishedAt="0001-01-01T00:00:00+08:00")],
])
def test_invalid_export_preserves_existing_ledger_bytes(tmp_path, capsys, payload):
    ledger = tmp_path / "ledger.jsonl"
    importer.import_payload([item("seed")], {}, apply=True, ledger=ledger)
    previous = ledger.read_bytes()
    export = write_json(tmp_path / "export.json", payload)
    map_path = write_json(tmp_path / "mapping.json", {})
    code = importer.main([str(export), "--mapping", str(map_path), "--ledger", str(ledger), "--apply"])
    assert code == 2
    output = capsys.readouterr()
    assert json.loads(output.err)["written"] is False
    assert "secret" not in output.err and "Traceback" not in output.err
    assert ledger.read_bytes() == previous


@pytest.mark.parametrize("bad_mapping", [
    None, [], {"sources": []}, {"entities": []}, {"items": []}, {"items": {"a": []}},
    {"items": {"a": {"entity_keys": [{}]}}}, {"items": {"a": {"entity_keys": ["missing"]}}},
    {"entities": {"sector": {"id": 5, "name": "测试"}}}, {"sources": {"A": {"participant_key": []}}},
    {"items": {"a": {"removed": "false"}}}, {"items": {"a": {"event_key": True}}},
    {"recorded_at": "2000-01-01T00:00:00Z"}, {"sources": {"unused": {"independent": True}}},
])
def test_bad_mapping_rejects_whole_batch_before_creating_ledger(tmp_path, bad_mapping):
    ledger = tmp_path / "private" / "ledger.jsonl"
    with pytest.raises(importer.ImportRejected):
        importer.import_payload([item()], bad_mapping, apply=True, ledger=ledger)
    assert not ledger.parent.exists()


@pytest.mark.parametrize("raw", [
    b"\xff", b'{"token":"secret",}', b'{"items":[],"items":[]}', b'[NaN]', b'[1e999]',
    b'{"title":"\\ud800"}', b'[' * 2000 + b']' * 2000,
])
def test_invalid_json_has_safe_errors_and_no_write(tmp_path, capsys, raw):
    export = tmp_path / "export.json"
    export.write_bytes(raw)
    ledger = tmp_path / "private" / "ledger.jsonl"
    map_path = write_json(tmp_path / "mapping.json", {})
    assert importer.main([str(export), "--mapping", str(map_path), "--ledger", str(ledger), "--apply"]) == 2
    output = capsys.readouterr()
    assert "secret" not in output.err and json.loads(output.err)["written"] is False
    assert not ledger.parent.exists()


def test_offline_byte_and_count_budgets(tmp_path, monkeypatch):
    file = write_json(tmp_path / "oversized.json", [item()])
    with pytest.raises(importer.ImportRejected, match="byte budget"):
        importer.load_json(file, limit=10)
    monkeypatch.setattr(importer, "MAX_ITEMS", 1)
    with pytest.raises(importer.ImportRejected, match="count"):
        importer.import_payload([item(), item("b")], {}, apply=True, ledger=tmp_path / "ledger.jsonl")
    assert not (tmp_path / "ledger.jsonl").exists()


def test_missing_timezone_remains_a_gap_and_empty_export_does_not_create_ledger(tmp_path):
    row = importer.prepare_observations([item(publishedAt="2020-01-01")], {})[0]
    assert row["published_at"] is None and row["published_at_claim"] == "2020-01-01"
    ledger = tmp_path / "private" / "ledger.jsonl"
    assert importer.import_payload([], {}, apply=True, ledger=ledger)["added"] == 0
    assert not ledger.parent.exists()


def test_cli_path_error_and_parser_error_do_not_echo_input(tmp_path):
    map_path = write_json(tmp_path / "mapping.json", {})
    for extras in ([], ["--secret-token=secret"]):
        result = run_cli(tmp_path / "secret.json", map_path, tmp_path / "ledger.jsonl", *extras)
        assert result.returncode == 2
        assert "secret" not in result.stderr and "Traceback" not in result.stderr


@pytest.mark.parametrize("ledger_content", [
    '{"broken":1}\n', '[]\n', '{"token":"secret"}\n', 'not json\n', "[" * 2000 + "]" * 2000,
])
def test_corrupt_ledger_fails_without_appending_or_leaking(tmp_path, capsys, ledger_content):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(ledger_content, encoding="utf-8")
    export = write_json(tmp_path / "export.json", [item()])
    map_path = write_json(tmp_path / "mapping.json", {})
    assert importer.main([str(export), "--mapping", str(map_path), "--ledger", str(ledger), "--apply"]) == 2
    assert ledger.read_text() == ledger_content
    assert "secret" not in capsys.readouterr().err


def test_disk_failure_never_claims_zero_writes(tmp_path, monkeypatch, capsys):
    export = write_json(tmp_path / "export.json", [item()])
    map_path = write_json(tmp_path / "mapping.json", {})

    def fail(*args):
        raise OSError("secret")

    monkeypatch.setattr(importer, "append_observations", fail)
    assert importer.main([str(export), "--mapping", str(map_path), "--ledger", str(tmp_path / "ledger"), "--apply"]) == 2
    output = capsys.readouterr()
    assert "secret" not in output.err and json.loads(output.err)["written"] is None


def test_identical_canonical_url_aliases_deduplicate_stably_across_order(tmp_path):
    aliases = [
        item("b", links={"original": "https://example.invalid/shared?utm_source=second#fragment"}),
        item("a", links={"original": "https://EXAMPLE.invalid/shared?utm_source=first"}),
    ]
    ledger = tmp_path / "ledger.jsonl"
    assert importer.import_payload(aliases, {}, apply=True, ledger=ledger)["added"] == 1
    before = ledger.read_bytes()
    assert importer.import_payload(aliases[::-1], {}, apply=True, ledger=ledger)["skipped"] == 1
    assert ledger.read_bytes() == before
    row = read_ledger(ledger)[0]
    assert row["url"] == "https://example.invalid/shared" and row["upstream_id"] == "a"


@pytest.mark.parametrize("changes,review", [
    ({"source": "Different source"}, {}), ({"title": "Different title"}, {}),
    ({"summary": "x" * 12000 + "different"}, {}),
    ({}, {"items": {"b": {"event_key": "different-event"}}}),
    ({}, {"items": {"b": {"origin_key": "different-origin"}}}),
])
def test_canonical_url_alias_conflicts_are_not_silently_discarded(tmp_path, changes, review):
    first = item("a", summary="x" * 12000)
    second = {**first, "id": "b", **changes}
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(importer.ImportRejected, match="conflicting"):
        importer.import_payload([first, second], review, apply=True, ledger=ledger)
    assert not ledger.exists()


@pytest.mark.parametrize("field,value", [
    ("schema_version", 99), ("recorded_at", "not-a-time"), ("recorded_at", "0001-01-01T00:00:00+08:00"),
])
def test_valid_import_cannot_append_to_structurally_corrupt_history(tmp_path, capsys, field, value):
    row = importer.prepare_observations([item("seed")], {})[0]
    row[field] = value
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
    before = ledger.read_bytes()
    export = write_json(tmp_path / "export.json", [item()])
    map_path = write_json(tmp_path / "mapping.json", {})
    assert importer.main([str(export), "--mapping", str(map_path), "--ledger", str(ledger), "--apply"]) == 2
    assert ledger.read_bytes() == before
    assert json.loads(capsys.readouterr().err)["written"] is False


def test_two_cli_writers_share_existing_lock_and_add_only_one_revision(tmp_path):
    export = write_json(tmp_path / "export.json", [item()])
    map_path = write_json(tmp_path / "mapping.json", {})
    ledger = tmp_path / "private" / "ledger.jsonl"
    command = [sys.executable, str(ROOT / "scripts/import_aihot_attention.py"), str(export),
               "--mapping", str(map_path), "--ledger", str(ledger), "--apply"]
    processes = [subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    reports = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        reports.append(json.loads(stdout))
    assert sum(report["added"] for report in reports) == 1
    assert sum(report["skipped"] for report in reports) == 1
    assert len(read_ledger(ledger)) == 1


def test_mapping_template_is_valid_but_only_contains_explicit_placeholders():
    template = importer.load_json(ROOT / "docs/examples/aihot-attention-mapping.example.json", limit=importer.MAX_MAPPING_BYTES)
    importer.validate_mapping(template)
    report = importer.import_payload([item()], template)
    assert report["unknown_sources"] == 1 and report["mapped"] == report["grouped"] == 0


def test_legacy_v1_without_content_hash_or_supersedes_keeps_writer_fallback(tmp_path):
    # Existing append supports rows whose revision_id used to be the content hash.
    # History validation must preserve that compatibility without rewriting the row.
    old = importer.prepare_observations([item()], {})[0]
    old.pop("content_hash")
    assert "supersedes" not in old
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps(old) + "\n", encoding="utf-8")
    original_bytes = ledger.read_bytes()
    assert read_ledger(ledger) == [old]
    assert importer.import_payload([item()], {}, apply=True, ledger=ledger)["skipped"] == 1
    assert ledger.read_bytes() == original_bytes
    assert importer.import_payload([item(title="Revised")], {}, apply=True, ledger=ledger)["added"] == 1
    assert ledger.read_bytes().startswith(original_bytes)
    assert read_ledger(ledger)[1]["supersedes"] == old["revision_id"]
