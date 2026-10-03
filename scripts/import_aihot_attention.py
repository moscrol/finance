#!/usr/bin/env python3
"""Import a complete AIHOT JSON export, with explicit mappings and opt-in writes.

Accept a full item array or a schemaVersion=1 envelope with terminal pagination.
No network/model calls. Unknown sources and unreviewed grouping stay unknown.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Direct script invocation, without an editable installation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.opinion_attention import (  # noqa: E402
    MAX_ITEMS,
    adapt_aihot,
    append_observations,
    canonical_url,
    default_ledger_path,
)

MAX_EXPORT_BYTES = 40 * 1024 * 1024
MAX_MAPPING_BYTES = 4 * 1024 * 1024
MAX_CURSOR_LENGTH = 4096


class ImportRejected(ValueError):
    """A safe, input-free diagnostic that may be printed by either CLI."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default error can echo a URL, credential, or unknown argument.
        self.exit(2, '{"error": "invalid arguments; see --help", "written": false}\n')


def print_error(message: str, *, written: bool | None = False) -> int:
    print(json.dumps({"error": message, "written": written}, ensure_ascii=False), file=sys.stderr)
    return 2


def decode_json(raw: bytes) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ImportRejected("duplicate JSON object key")
            obj[key] = value
        return obj

    def invalid_constant(value: str) -> None:
        raise ImportRejected("non-finite JSON number")

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs, parse_constant=invalid_constant)
        # Reject escaped lone surrogates and overflowing floats before conversion/writes.
        json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return data
    except (ValueError, RecursionError) as exc:
        raise ImportRejected("invalid UTF-8 JSON (duplicate keys and non-finite numbers are rejected)") from exc


def load_json(path: Path, *, limit: int) -> Any:
    try:
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
    except OSError as exc:
        raise ImportRejected("cannot read input JSON file") from exc
    if len(raw) > limit:
        raise ImportRejected("input JSON exceeds byte budget")
    return decode_json(raw)


def _text(value: Any, *, optional: bool = False) -> bool:
    if optional and value in (None, ""):
        return True
    return isinstance(value, str) and bool(value.strip())


def validate_mapping(mapping: Any) -> dict[str, Any]:
    if not isinstance(mapping, dict) or set(mapping) - {"sources", "entities", "items"}:
        raise ImportRejected("mapping must contain only sources, entities and items objects")
    sources, entities, items = (mapping.get(key, {}) for key in ("sources", "entities", "items"))
    if not all(isinstance(value, dict) for value in (sources, entities, items)):
        raise ImportRejected("sources, entities and items must be objects")
    for config in sources.values():
        if (not isinstance(config, dict) or set(config) - {"participant_key", "kind"}
                or any(not _text(value, optional=True) for value in config.values())):
            raise ImportRejected("invalid source mapping; use explicit text participant_key/kind")
    for config in entities.values():
        if (not isinstance(config, dict) or set(config) != {"id", "name"}
                or not all(_text(value) for value in config.values())):
            raise ImportRejected("invalid entity mapping; text id and name are required")
    for config in items.values():
        if not isinstance(config, dict) or set(config) - {"event_key", "origin_key", "entity_keys", "removed"}:
            raise ImportRejected("invalid item mapping")
        if any(not _text(config.get(key), optional=True) for key in ("event_key", "origin_key")):
            raise ImportRejected("event_key and origin_key must be explicit text or null")
        if "removed" in config and type(config["removed"]) is not bool:
            raise ImportRejected("removed must be a boolean")
        keys = config.get("entity_keys", [])
        if not isinstance(keys, list) or any(not _text(key) or key not in entities for key in keys):
            raise ImportRejected("entity_keys must be an array of resolved mapping keys")
    return mapping


def page_cursor(payload: Any, *, item_limit: int) -> str | None:
    """Validate the public v1 envelope and require an unambiguous terminal page."""
    if (not isinstance(payload, dict) or type(payload.get("schemaVersion")) is not int
            or payload["schemaVersion"] != 1 or not isinstance(payload.get("items"), list)):
        raise ImportRejected("unsupported or malformed AIHOT schema")
    if len(payload["items"]) > item_limit:
        raise ImportRejected("AIHOT item count exceeds budget")
    page = payload.get("page")
    if not isinstance(page, dict) or type(page.get("hasMore")) is not bool:
        raise ImportRejected("missing pagination completeness metadata")
    cursor = page.get("nextCursor")
    if not page["hasMore"]:
        if cursor not in (None, ""):
            raise ImportRejected("terminal page has a contradictory next cursor")
        return None
    if (not isinstance(cursor, str) or not cursor.strip() or len(cursor) > MAX_CURSOR_LENGTH
            or any(ord(char) < 32 or ord(char) == 127 for char in cursor)):
        raise ImportRejected("missing or invalid pagination cursor")
    return cursor


def add_unique_items(items: list[Any], identities: dict[str, str], collected: list[dict[str, Any]]) -> None:
    """Reject conflicting IDs before any adapter projection could hide a revision."""
    for item in items:
        upstream_id = item.get("id") if isinstance(item, dict) else None
        if (not isinstance(upstream_id, str) or not upstream_id.strip() or len(upstream_id) > 512
                or upstream_id != upstream_id.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in upstream_id)):
            raise ImportRejected("AIHOT item id must be a nonempty text identity")
        fingerprint = json.dumps(item, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        previous = identities.get(upstream_id)
        if previous is not None:
            if fingerprint != previous:
                raise ImportRejected("conflicting duplicate AIHOT item id; export a consistent snapshot")
            continue
        identities[upstream_id] = fingerprint
        collected.append(item)
        if len(collected) > MAX_ITEMS:
            raise ImportRejected("AIHOT item count exceeds budget")


def _material_signature(item: dict[str, Any], row: dict[str, Any]) -> str:
    # Compare full content before adapter truncation, plus reviewed mappings. Only
    # an alias ID and normalized tracking URLs can differ within one snapshot.
    raw = {key: value for key, value in item.items() if key != "id"}
    try:
        if isinstance(raw.get("links"), dict):
            raw["links"] = {**raw["links"], "original": canonical_url(raw["links"]["original"])}
        if raw.get("url"):
            raw["url"] = canonical_url(raw["url"])
    except ValueError as exc:
        raise ImportRejected("AIHOT item contains an invalid original URL") from exc
    content = {key: value for key, value in row.items()
               if key not in {"upstream_id", "recorded_at", "revision_id", "content_hash"}}
    return json.dumps([raw, content], sort_keys=True, ensure_ascii=True, allow_nan=False)


def prepare_observations(payload: Any, mapping: Any) -> list[dict[str, Any]]:
    mapping = validate_mapping(mapping)
    if isinstance(payload, list):
        items = payload
    else:
        if page_cursor(payload, item_limit=MAX_ITEMS) is not None:
            raise ImportRejected("incomplete export; combine all pages before importing")
        items = payload["items"]
    if len(items) > MAX_ITEMS:
        raise ImportRejected("AIHOT item count exceeds budget")
    unique: list[dict[str, Any]] = []
    add_unique_items(items, {}, unique)
    for item in unique:
        if not _text(item.get("title")):
            raise ImportRejected("full AIHOT items require a text title")
        for key in ("summary", "publishedAt", "discoveredAt", "url", "sourceName"):
            if item.get(key) is not None and not isinstance(item[key], str):
                raise ImportRejected("invalid AIHOT text field")
        if "selected" in item and type(item["selected"]) is not bool:
            raise ImportRejected("AIHOT selected must be a boolean")
        source = item.get("source")
        if source is not None and not isinstance(source, (dict, str)):
            raise ImportRejected("invalid AIHOT source")
        if isinstance(source, dict) and not isinstance(source.get("name"), str):
            raise ImportRejected("AIHOT source object requires a text name")
        links = item.get("links")
        if links is not None and (not isinstance(links, dict) or not isinstance(links.get("original"), str)):
            raise ImportRejected("full AIHOT items require an original URL")
    # No caller-supplied 'now': all rows get this machine's actual local knowledge time.
    try:
        rows, errors = adapt_aihot(unique, mapping)
    except (ValueError, OverflowError) as exc:
        raise ImportRejected("AIHOT conversion rejected an invalid value or out-of-range timestamp") from exc
    if errors:
        raise ImportRejected("AIHOT conversion rejected items; check original URLs and future publication times")
    materials: dict[str, tuple[str, dict[str, Any]]] = {}
    for item, row in zip(unique, rows):
        signature = _material_signature(item, row)
        prior = materials.get(row["material_id"])
        if prior and signature != prior[0]:
            raise ImportRejected("conflicting items resolve to one original URL; review content, source and mapping")
        # An identical export reordered by the server must remain idempotent.
        if prior is None or row["upstream_id"] < prior[1]["upstream_id"]:
            materials[row["material_id"]] = (signature, row)
    return [row for _, row in materials.values()]


def import_payload(payload: Any, mapping: Any, *, apply: bool = False, ledger: Path | None = None) -> dict[str, Any]:
    observations = prepare_observations(payload, mapping)
    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run", "accepted": len(observations), "errors": [],
        "mapped": sum(bool(row["entities"]) for row in observations),
        "grouped": sum(row["grouping"] == "reviewed" for row in observations),
        "unknown_sources": sum(not row["participant_key"] for row in observations),
        "written": False,
        "note": "局部导入快照，不代表全网覆盖；无连续采集证明，不判断舆论升降温。",
    }
    if apply and observations:
        try:
            counts = append_observations(ledger if ledger is not None else default_ledger_path(), observations)
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
            raise ImportRejected("ledger append rejected; check ledger format and local clock") from exc
        report.update(counts)
        report["written"] = counts["added"] > 0
    elif apply:
        report.update(added=0, skipped=0)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, help="override the private observation ledger")
    parser.add_argument("--apply", action="store_true", help="append after full validation; default is dry-run")
    args = parser.parse_args(argv)
    try:
        payload = load_json(args.input, limit=MAX_EXPORT_BYTES)
        mapping = load_json(args.mapping, limit=MAX_MAPPING_BYTES)
        report = import_payload(payload, mapping, apply=args.apply, ledger=args.ledger)
    except ImportRejected as exc:
        return print_error(str(exc))
    except OSError:
        # Disk failure can happen after a write; do not report a false no-write receipt.
        return print_error("ledger I/O failed; inspect the ledger before retrying", written=None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
