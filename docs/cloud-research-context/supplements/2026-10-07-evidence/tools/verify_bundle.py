#!/usr/bin/env python3
"""Offline package validation; Python standard library only, no DB or network."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    listed = {r["path"]: r for r in manifest["files"]}
    found = {str(p.relative_to(ROOT)): p for p in ROOT.rglob("*") if p.is_file() and p != ROOT / "manifest.json"}
    assert found.keys() == listed.keys(), "File list differs from manifest"
    for name, p in found.items():
        assert not p.is_symlink(), name
        data = p.read_bytes()
        assert sha(data) == listed[name]["sha256"], "Hash mismatch: " + name
        assert len(data) == listed[name]["bytes"], "Byte count mismatch: " + name
        assert p.suffix not in (".duckdb", ".db", ".sqlite", ".zip", ".env"), name
        assert p.suffix in (".md", ".json", ".py", ".sql"), name
        text = data.decode("utf-8")
        if p.suffix == ".json":
            json.loads(text)
        if p.suffix == ".py":
            compile(text, name, "exec")
    index = json.loads((ROOT / "sources/index.json").read_text())
    excerpt_count, exact_count = 0, 0
    for item in index:
        p = ROOT / item["output"]
        if "excerpt_sha256" in item:
            body = p.read_text().split("<!-- BEGIN VERBATIM EXCERPT -->\n", 1)[1]
            n = item["char_offsets_zero_based_half_open"][1] - item["char_offsets_zero_based_half_open"][0]
            body, suffix = body[:n], body[n:]
            assert suffix in ("<!-- END VERBATIM EXCERPT -->\n", "\n<!-- END VERBATIM EXCERPT -->\n"), item["output"]
            assert sha(body.encode()) == item["excerpt_sha256"], item["output"]
            excerpt_count += 1
        if item.get("transform") == "byte-identical copy":
            assert sha(p.read_bytes()) == item["source_sha256"], item["output"]
            exact_count += 1
    originals = json.loads((ROOT / "sources/public-snapshot-integrity.json").read_text())["files"]
    assert len(originals) == 435 and all(r["match"] for r in originals)
    for pid in ("pp-440977d4ea38", "pp-484bf87f4f2d"):
        assert json.loads((ROOT / "sources/patches" / (pid + ".json")).read_text())["status"] == "rejected"
    capital = json.loads((ROOT / "data/capital_recomputed.json").read_text())
    structure = json.loads((ROOT / "data/structure_recomputed.json").read_text())
    assert len(capital["field_coverage"]) == 12
    assert len(structure["field_coverage"]) == 26
    ledger = (ROOT / "FIELD_LEDGER.md").read_text()
    for row in capital["field_coverage"] + structure["field_coverage"]:
        assert "`" + row["field"] + "`" in ledger, "Missing ledger field: " + row["field"]
        assert row["non_null_rows"] + row["null_rows"] == row["rows"] == 432
    side = json.loads((ROOT / "data/sidecar_audit.json").read_text())
    assert all(r["rows"] == 0 for r in side["tables"] if r["table"] != "history_calendar")
    receipt = json.loads((ROOT / "data/run_receipt.json").read_text())
    assert receipt["database_stat_unchanged"]
    import re
    links = 0
    for p in ROOT.glob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            if "://" not in link:
                assert (p.parent / link.split("#", 1)[0]).exists(), (p.name, link)
                links += 1
    print(json.dumps({"status": "PASS", "files_hashed": len(found), "verbatim_excerpts": excerpt_count,
                      "exact_copies": exact_count, "public_snapshot_hash_matches": 435,
                      "ledger_fields": 38, "local_links_checked": links,
                      "limits": "File integrity and stated structural checks only; not a semantic approval or full source/DB algorithm test."}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, ValueError, OSError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
