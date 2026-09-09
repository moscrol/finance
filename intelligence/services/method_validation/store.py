"""Content addressed JSON files, atomically published without overwrites."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .protocol import canonical_bytes, clock_now, digest, iso_date, validate_protocol

KINDS = frozenset({"history", "capture", "recheck"})
_ID = re.compile(r"[0-9a-f]{64}")


def _check_id(value: str) -> None:
    if not _ID.fullmatch(value):
        raise ValueError("invalid content id")


def _read(path: Path) -> dict:
    if path.is_symlink():
        raise ValueError("symlink records are not supported")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        canonical_bytes(result)
        if not isinstance(result, dict):
            raise ValueError("record must be an object")
        return result
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("invalid JSON record") from exc


def _publish(path: Path, value: dict) -> None:
    data = canonical_bytes(value)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".pending-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if _read(path) != value:
                raise ValueError("existing content differs or is corrupt") from None
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def register(root, protocol) -> Path:
    validate_protocol(protocol)
    parent = Path(root).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    directory = parent / protocol["protocol_id"]
    if directory.is_symlink():
        raise ValueError("symlink study directories are not supported")
    directory.mkdir(exist_ok=True)
    path = directory / "protocol.json"
    if path.exists():
        old = load_protocol(directory)
        if {k: v for k, v in old.items() if k != "created_at"} != {
            k: v for k, v in protocol.items() if k != "created_at"
        }:
            raise ValueError("protocol content differs")
        return directory
    try:
        _publish(
            path,
            {
                "schema_version": 1,
                "protocol": protocol,
                "content_sha256": digest(protocol),
            },
        )
    except ValueError:
        old = load_protocol(directory)
        if {k: v for k, v in old.items() if k != "created_at"} != {
            k: v for k, v in protocol.items() if k != "created_at"
        }:
            raise
    return directory


def load_protocol(study_dir) -> dict:
    directory = Path(study_dir)
    _check_id(directory.name)
    if directory.is_symlink():
        raise ValueError("symlink study directories are not supported")
    envelope = _read(directory / "protocol.json")
    if (
        set(envelope) != {"schema_version", "protocol", "content_sha256"}
        or envelope["schema_version"] != 1
        or envelope["content_sha256"] != digest(envelope["protocol"])
    ):
        raise ValueError("protocol envelope hash mismatch")
    protocol = envelope["protocol"]
    validate_protocol(protocol, require_current=False)
    if protocol["protocol_id"] != directory.name:
        raise ValueError("protocol directory id mismatch")
    return protocol


def write_record(study_dir, kind, payload) -> Path:
    if kind not in KINDS:
        raise ValueError("invalid record kind")
    directory = Path(study_dir)
    protocol = load_protocol(directory)
    if (
        not isinstance(payload, dict)
        or payload.get("protocol_id") != protocol["protocol_id"]
    ):
        raise ValueError("record must refer to its protocol")
    record = {"schema_version": 1, "kind": kind, "payload": payload}
    record["content_sha256"] = digest(record)
    if kind == "capture":
        if "outcomes" in payload or "comparison" in payload:
            raise ValueError("capture must contain features only")
        local_day = iso_date(payload["features"]["end"])
    else:
        local_day = clock_now().date().isoformat()
    parent = directory
    for part in (kind, local_day):
        parent = parent / part
        if parent.is_symlink():
            raise ValueError("symlink record directories are not supported")
        parent.mkdir(exist_ok=True)
    target = parent / (record["content_sha256"] + ".json")
    _publish(target, record)
    return target


def read_record(path) -> dict:
    path = Path(path)
    if path.suffix != ".json" or path.parent.parent.name not in KINDS:
        raise ValueError("invalid record path")
    _check_id(path.stem)
    iso_date(path.parent.name)
    protocol = load_protocol(path.parents[2])
    if path.parent.is_symlink() or path.parent.parent.is_symlink():
        raise ValueError("symlink record directories are not supported")
    record = _read(path)
    if set(record) != {"schema_version", "kind", "payload", "content_sha256"}:
        raise ValueError("invalid record fields")
    expected = digest({k: v for k, v in record.items() if k != "content_sha256"})
    if (
        record["schema_version"] != 1
        or record["kind"] != path.parent.parent.name
        or record["content_sha256"] != expected
        or path.stem != expected
        or not isinstance(record["payload"], dict)
        or record["payload"].get("protocol_id") != protocol["protocol_id"]
    ):
        raise ValueError("record hash or identity mismatch")
    return record
