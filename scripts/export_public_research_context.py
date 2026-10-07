#!/usr/bin/env python3
"""Read-only, allowlisted research-context export. No upload or runtime import.

Public publication still requires human scope review and a credential scan.
Use a fresh destination; historical articles, quotes, cards and private exams
are intentionally omitted. The offline checker needs no user data or network.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

PROFILES = ("sptfei", "user_framework", "fengyuan")
PROFILE_FIELDS = frozenset((
    "schema_version", "id", "display_name", "type", "created_at", "updated_at",
    "source_policy", "market_lenses", "opportunity_preferences", "risk_triggers",
    "evidence_hierarchy", "reasoning_patterns", "anti_patterns", "falsification_style",
    "contradictions", "honest_boundaries", "voice_guidance", "confidence", "patch_history",
))
ARTICLE_FIELDS = ("schema_version", "article_id", "perspective_id", "title", "date",
                  "source", "ingested_at", "chars")
PATCH_FIELDS = ("schema_version", "patch_id", "perspective_id", "field", "value", "status",
                "supporting_article_count", "created_at", "reviewed_at", "review_note", "applied")
CORRECTION_FIELDS = frozenset(("ts", "id", "original", "correction", "principle", "themes",
                              "record_type", "status", "target_ts", "reason"))
SECRET_PATTERNS = (
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    r"\bsk-[A-Za-z0-9_-]{20,}", r"\bAKIA[A-Z0-9]{16}\b",
    r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]{16,}",
    r"(?i)[?&](?:access_token|api_key|password|secret)=[^\s&\"<>]{8,}",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def encode_rows(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode()


def record_hash(row: dict) -> str:
    return sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode())


def parse_rows(data: bytes) -> list[dict]:
    rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSONL rows must be objects")
    return rows


def safe_path(root: Path, name: str) -> Path:
    rel = Path(name)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError("unsafe relative path")
    cursor = root
    for part in ("", *rel.parts):
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("symlink not allowed")
    return root / rel


def public_value(value: object, user_id: str) -> object:
    if isinstance(value, str):
        value = re.sub(r"/(?:Users|home)/[^/\s\"']+", "<USER_HOME>", value)
        return value.replace("~/", "<USER_HOME>/").replace(user_id, "<USER_ID>")
    if isinstance(value, list):
        return [public_value(item, user_id) for item in value]
    if isinstance(value, dict):
        return {key: public_value(item, user_id) for key, item in value.items()}
    return value


def scan_payload(payload: dict[str, bytes]) -> None:
    for name, data in payload.items():
        text = data.decode()
        if any(re.search(pattern, text) for pattern in SECRET_PATTERNS):
            raise ValueError(f"possible credential: {name}")  # Never echo the match.
        if re.search(r"/(?:Users|home)/[^/\s]+", text):
            raise ValueError(f"unredacted home path: {name}")


def select_records(rows: list[dict], hashes: list[str]) -> list[dict]:
    if not hashes or len(hashes) != len(set(hashes)):
        raise ValueError("selection must be nonempty and unique")
    candidates = [row for row in rows if "correction" in row and record_hash(row) in hashes]
    if len(candidates) != len(hashes):
        raise ValueError("selected correction missing, duplicated or changed")
    identities = {str(row[key]) for row in candidates for key in ("id", "ts") if row.get(key)}
    selected = [row for row in rows if row in candidates or
                (row.get("record_type") == "memory_status" and str(row.get("target_ts")) in identities)]
    if any(row.keys() - CORRECTION_FIELDS for row in selected):
        raise ValueError("new correction fields require scope review")
    return selected


def export(user_root: Path, selection_path: Path, output: Path, revision: str) -> dict:
    user_root = user_root.resolve()
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("destination exists; use a fresh snapshot directory")
    if output.resolve().is_relative_to(user_root) or user_root.is_relative_to(output.resolve()):
        raise ValueError("destination overlaps live userspace")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("finance revision must be a full commit SHA")
    selection_data = selection_path.read_bytes()
    selection = json.loads(selection_data)
    sources, payload, counts = {}, {}, {}

    def read(name: str) -> bytes:
        data = safe_path(user_root, name).read_bytes()
        if name in sources and sources[name] != data:
            raise ValueError("source changed during export")
        sources[name] = data
        return data

    def put(name: str, value: object, jsonl: bool = False) -> None:
        value = public_value(value, user_root.name)
        payload[name] = encode_rows(value) if jsonl else encode(value)

    for pid in PROFILES:
        profile = json.loads(read(f"perspectives/profiles/{pid}.json"))
        if profile.get("id") != pid or profile.keys() - PROFILE_FIELDS:
            raise ValueError("profile identity/fields require review")
        put(f"profiles/{pid}.json", profile)
        if pid == "user_framework":
            continue
        base = f"perspectives/articles/{pid}"
        articles = parse_rows(read(f"{base}/manifest.jsonl"))
        ids = [article["article_id"] for article in articles]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate article IDs")
        public_articles = []
        for article in articles:
            if article["perspective_id"] != pid:
                raise ValueError("article identity mismatch")
            # Legacy manifests may point to a previous machine. Read only the
            # canonical raw directory's basename, never the old absolute path.
            raw_name = Path(article["raw_path"]).name
            raw = read(f"{base}/raw/{raw_name}")
            public_articles.append({**{key: article[key] for key in ARTICLE_FIELDS},
                                    "raw_sha256": sha256(raw), "raw_included": False})
        put(f"articles/{pid}.jsonl", public_articles, True)
        patches = []
        directory = safe_path(user_root, f"perspectives/patches/{pid}")
        for path in sorted(directory.glob("*.json")):
            patch = json.loads(read(str(path.relative_to(user_root))))
            if patch["perspective_id"] != pid:
                raise ValueError("patch identity mismatch")
            evidence = []
            for item in patch["evidence"]:
                if item["article_id"] not in ids:
                    raise ValueError("patch references missing article")
                evidence.append({**{key: item[key] for key in ("article_id", "title", "date")},
                                 "quote_sha256": sha256(item["quote"].encode()), "quote_included": False})
            patches.append({**{key: patch[key] for key in PATCH_FIELDS if key in patch}, "evidence": evidence})
        put(f"patches/{pid}.jsonl", patches, True)
        counts[pid] = {"articles": len(articles), "patches": len(patches)}

    all_rows = parse_rows(read("corrections.jsonl"))
    selected = select_records(all_rows, selection["correction_sha256"])
    put("alignment/corrections.jsonl", selected, True)
    index = []
    for line, row in enumerate(selected, 1):
        if "correction" not in row:
            continue
        identities = {str(row[key]) for key in ("id", "ts") if row.get(key)}
        events = [event for event in selected if event.get("record_type") == "memory_status"
                  and str(event.get("target_ts")) in identities]
        index.append({"line": line, "id": row.get("id"), "ts": row["ts"],
                      "source_record_sha256": record_hash(row),
                      "status_events": events})
    put("alignment/index.json", index)
    put("selection.json", selection)
    scan_payload(payload)
    for name, data in sources.items():
        if safe_path(user_root, name).read_bytes() != data:
            raise ValueError("source changed during export; retry when idle")
    if selection_path.read_bytes() != selection_data:
        raise ValueError("selection changed during export")
    manifest = {
        "schema_version": 1, "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "finance_revision": revision, "scope": "owner-authorized public research reference, not runtime state",
        "profiles": list(PROFILES), "counts": counts,
        "corrections": {"selected": len(index), "status_events": len(selected) - len(index),
                        "source_records": len(all_rows), "excluded": len(all_rows) - len(selected)},
        "transformations": ["home paths and production user ID replaced by placeholders",
                            "article metadata only; raw content replaced by SHA256",
                            "patch evidence quotes replaced by SHA256; review status/value preserved",
                            "reviewed correction SHA256 allowlist plus matching lifecycle events in original order"],
        "excluded": ["article full text, extracted cards, private exam questions",
                     "unselected memory, biography, accounts, credentials, holdings, conversations, databases"],
        "limits": ["nontransactional snapshot; selected source bytes reread unchanged",
                   "hashes show integrity, not truth, authority or current approval",
                   "no explicit memory status does not imply active or approved",
                   "raw evidence withheld; cloud review alone cannot verify full-text fidelity"],
        "source_files": {name: {"sha256": sha256(data), "bytes": len(data)}
                         for name, data in sorted(sources.items())},
        "files": [{"path": name, "sha256": sha256(data), "bytes": len(data)}
                  for name, data in sorted(payload.items())],
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, data in payload.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (output / "manifest.json").write_bytes(encode(manifest))
    check(output)
    return manifest


def check(root: Path) -> dict:
    manifest = json.loads(safe_path(root, "manifest.json").read_bytes())
    declared = [entry["path"] for entry in manifest["files"]]
    actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() or path.is_symlink()}
    if len(set(declared)) != len(declared) or actual != set(declared) | {"manifest.json"}:
        raise ValueError("snapshot inventory mismatch")
    payload = {}
    for entry in manifest["files"]:
        data = safe_path(root, entry["path"]).read_bytes()
        if sha256(data) != entry["sha256"] or len(data) != entry["bytes"]:
            raise ValueError(f"integrity mismatch: {entry['path']}")
        if entry["path"].endswith(".jsonl"):
            parse_rows(data)
        else:
            json.loads(data)
        payload[entry["path"]] = data
    for pid in ("sptfei", "fengyuan"):
        articles = parse_rows(payload[f"articles/{pid}.jsonl"])
        ids = {article["article_id"] for article in articles}
        for patch in parse_rows(payload[f"patches/{pid}.jsonl"]):
            if any(item["article_id"] not in ids for item in patch["evidence"]):
                raise ValueError("unresolved patch evidence")
    scan_payload({**payload, "manifest.json": encode(manifest)})
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export_cmd = sub.add_parser("export")
    for arg in ("user-root", "selection", "output"):
        export_cmd.add_argument(f"--{arg}", type=Path, required=True)
    export_cmd.add_argument("--finance-revision", required=True)
    check_cmd = sub.add_parser("check")
    check_cmd.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    result = (check(args.snapshot) if args.command == "check" else
              export(args.user_root, args.selection, args.output, args.finance_revision))
    print(json.dumps({"files": len(result["files"]), "counts": result["counts"],
                      "corrections": result["corrections"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
