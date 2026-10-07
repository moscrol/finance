"""Public snapshot boundaries using synthetic userspace, never production data."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import export_public_research_context as context


@pytest.fixture
def sources(tmp_path):
    user = tmp_path / "private-person"
    user.mkdir()

    def put(name, data):
        path = user / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    for pid in context.PROFILES:
        put(f"perspectives/profiles/{pid}.json", context.encode({
            "id": pid, "display_name": pid, "confidence": {"known_gaps": ["~/private-person/missing"]},
        }))
        if pid == "user_framework":
            continue
        article = {key: "example" for key in context.ARTICLE_FIELDS}
        article.update(article_id="a", perspective_id=pid, raw_path="/old-machine/raw/source.md")
        put(f"perspectives/articles/{pid}/manifest.jsonl", context.encode_rows([article]))
        put(f"perspectives/articles/{pid}/raw/source.md", b"copyrighted full text")
        patch = {key: None for key in context.PATCH_FIELDS}
        patch.update(patch_id="p", perspective_id=pid, status="rejected", applied=False,
                     evidence=[{"article_id": "a", "date": "2026-01-01", "title": "example",
                                "quote": "private verbatim quote"}])
        put(f"perspectives/patches/{pid}/p.json", context.encode(patch))
    correction = {"id": "c1", "ts": "2026-01-01", "correction": "research preference"}
    status = {"record_type": "memory_status", "target_ts": "c1", "ts": "2026-01-03",
              "status": "rejected", "reason": "not confirmed"}
    rows = [correction, {"ts": "2026-01-02", "correction": "private biography"}, status]
    put("corrections.jsonl", context.encode_rows(rows))
    put("perspectives/exam/sptfei.json", context.encode({"question": "private question"}))
    selection = tmp_path / "selection.json"
    selection.write_bytes(context.encode({"correction_sha256": [context.record_hash(correction)]}))
    return user, selection, tmp_path / "snapshot"


def export(sources):
    return context.export(*sources, "a" * 40)


def test_public_export_preserves_rules_status_and_excludes_private_payload(sources):
    user, _, output = sources
    before = {p: p.read_bytes() for p in user.rglob("*") if p.is_file()}
    manifest = export(sources)
    assert manifest == context.check(output)
    assert before == {p: p.read_bytes() for p in user.rglob("*") if p.is_file()}
    texts = "\n".join(p.read_text() for p in output.rglob("*") if p.is_file())
    for excluded in ("copyrighted full text", "private verbatim quote", "private biography",
                     "private-person", "private question", "old-machine"):
        assert excluded not in texts
    assert "<USER_HOME>/<USER_ID>/missing" in texts
    assert manifest["corrections"] == {"selected": 1, "status_events": 1, "source_records": 3, "excluded": 1}
    index = json.loads((output / "alignment/index.json").read_bytes())
    assert index[0]["status_events"][0]["status"] == "rejected"
    for pid in ("sptfei", "fengyuan"):
        patch = context.parse_rows((output / f"patches/{pid}.jsonl").read_bytes())[0]
        assert patch["status"] == "rejected"
        assert patch["applied"] is False
        assert "quote" not in patch["evidence"][0]
        assert patch["evidence"][0]["quote_sha256"] == context.sha256(b"private verbatim quote")


def test_missing_applied_field_remains_absent(sources):
    path = sources[0] / "perspectives/patches/sptfei/p.json"
    patch = json.loads(path.read_bytes())
    del patch["applied"]
    path.write_bytes(context.encode(patch))
    export(sources)
    exported = context.parse_rows((sources[2] / "patches/sptfei.jsonl").read_bytes())[0]
    assert "applied" not in exported


def test_status_timestamp_target_and_absence_do_not_mint_approval():
    row = {"ts": "2026-01-01", "id": "x", "correction": "fact"}
    status = {"record_type": "memory_status", "target_ts": row["ts"], "status": "archived"}
    hashes = [context.record_hash(row)]
    assert context.select_records([row, status], hashes) == [row, status]
    assert context.select_records([row], hashes) == [row]


@pytest.mark.parametrize("change", ["overwrite", "source-overlap", "source-symlink", "unknown-fields",
                                    "missing-selection", "duplicate-selection", "credential", "missing-article"])
def test_export_rejects_invalid_or_unreviewed_input(sources, change):
    user, selection, output = sources
    if change == "overwrite":
        output.mkdir()
    elif change == "source-overlap":
        sources = user, selection, user / "new-snapshot"
    elif change == "source-symlink":
        path = user / "perspectives/profiles/sptfei.json"
        path.unlink()
        path.symlink_to(selection)
    elif change == "unknown-fields":
        (user / "perspectives/profiles/sptfei.json").write_bytes(context.encode({"id": "sptfei", "account": "private"}))
    elif change == "missing-selection":
        (user / "corrections.jsonl").write_bytes(b"{}\n")
    elif change == "duplicate-selection":
        data = json.loads(selection.read_bytes())
        data["correction_sha256"] *= 2
        selection.write_bytes(context.encode(data))
    elif change == "credential":
        (user / "perspectives/profiles/sptfei.json").write_bytes(context.encode({
            "id": "sptfei", "display_name": "ghp_" + "x" * 36,
        }))
    else:
        path = user / "perspectives/patches/sptfei/p.json"
        patch = json.loads(path.read_bytes())
        patch["evidence"][0]["article_id"] = "missing"
        path.write_bytes(context.encode(patch))
    with pytest.raises(ValueError):
        export(sources)
    if change != "overwrite":
        assert not output.exists()


def test_mutation_during_export_fails_before_writing(sources, monkeypatch):
    scan = context.scan_payload

    def mutate(payload):
        scan(payload)
        (sources[0] / "corrections.jsonl").write_text("{}\n")

    monkeypatch.setattr(context, "scan_payload", mutate)
    with pytest.raises(ValueError, match="source changed"):
        export(sources)
    assert not sources[2].exists()


@pytest.mark.parametrize("change", ["tamper", "extra", "deleted", "symlink", "manifest-traversal"])
def test_offline_check_rejects_bad_snapshot(sources, change):
    export(sources)
    root = sources[2]
    path = root / "profiles/sptfei.json"
    if change == "tamper":
        path.write_text("{}")
    elif change == "extra":
        (root / "extra.txt").write_text("unlisted")
    elif change == "deleted":
        path.unlink()
    elif change == "symlink":
        path.unlink()
        path.symlink_to(sources[1])
    else:
        manifest = json.loads((root / "manifest.json").read_bytes())
        manifest["files"][0]["path"] = "../outside"
        (root / "manifest.json").write_bytes(context.encode(manifest))
    with pytest.raises(ValueError):
        context.check(root)


def test_committed_snapshot_is_self_contained_and_checked():
    root = Path(__file__).resolve().parents[1] / "docs/cloud-research-context/snapshots/2026-10-07"
    if not root.exists():
        pytest.fail("public snapshot missing")
    manifest = context.check(root)
    assert manifest["counts"]["sptfei"]["articles"] == 50
    assert manifest["counts"]["fengyuan"]["articles"] == 24
    assert set(manifest["profiles"]) == set(context.PROFILES)
