"""Read-only label admission for memory recall; never repair private ledgers."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import corrections, judgments, memory_status, user_memory


class InvalidMemoryLabels(ValueError):
    def __init__(self, report: dict[str, Any]) -> None:
        super().__init__("invalid memory labels; inspect label audit before scoring")
        self.report = report


def ledger_fingerprints(*, users_root: str | Path | None = None, user: str | None = None) -> dict[str, str | None]:
    root = Path(users_root).expanduser() if users_root is not None else userspace.user_space(user).root
    result = {}
    for name in ("judgments.jsonl", "corrections.jsonl"):
        try:
            result[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
        except FileNotFoundError:
            result[name] = None
        except OSError:
            raise InvalidMemoryLabels({"valid": False, "unavailable_ledgers": [name]}) from None
    return result


def require_unchanged_ledgers(audit: dict[str, Any], **kwargs: Any) -> None:
    if ledger_fingerprints(**kwargs) != audit["ledger_sha256"]:
        raise InvalidMemoryLabels({"valid": False, "input_changed": True})


def memory_identity(kind: str, record: dict[str, Any], mode: str = "ts") -> str:
    """Keep legacy labels explicit; stable keys distinguish source and content."""
    ts = str(record.get("ts") or "").strip()
    if mode == "ts":
        return ts
    if mode != "stable":
        raise ValueError("memory identity must be ts or stable")
    field = {"judgment": "memo", "correction": "correction"}[kind]
    key = str(record.get("id") or "").strip() or memory_status.memory_record_id(
        kind, ts, str(record.get(field) or ""),
    )
    return f"{kind}:{key}"


def audit_memory_labels(
    cases: list[dict[str, Any]],
    *,
    users_root: str | Path | None = None,
    user: str | None = None,
    identity_mode: str = "ts",
) -> dict[str, Any]:
    """Check existence, withdrawal, window and identity before any retrieval.

    Canonical loaders own eligibility. The raw inventory only distinguishes
    inactive labels from nonexistent ones. Reports contain identities and
    counts, never private text or filesystem paths.
    """
    if identity_mode not in {"ts", "stable"}:
        raise ValueError("memory identity must be ts or stable")
    fingerprints = ledger_fingerprints(users_root=users_root, user=user)
    root = Path(users_root).expanduser() if users_root is not None else userspace.user_space(user).root
    inventories: dict[str, Counter[str]] = {name: Counter() for name in ("raw", "active", "window")}
    counts = {}
    errors = []
    for kind, filename, field, loader in (
        ("judgment", "judgments.jsonl", "memo", judgments.load_judgments),
        ("correction", "corrections.jsonl", "correction", corrections.load_corrections),
    ):
        path = root / filename
        try:
            active, warning = loader(path, window=0, strict=True)
            window, window_warning = loader(path, window=user_memory.DEFAULT_LOAD_WINDOW, strict=True)
            if warning or window_warning:
                errors.append(kind)
                continue
            raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
        except (OSError, ValueError):
            errors.append(kind)
            continue
        raw = [row for row in raw if isinstance(row, dict)
               and not memory_status.is_status_record(row) and str(row.get(field) or "").strip()]
        groups = {"raw": raw, "active": active, "window": window}
        counts[kind] = {name: len(rows) for name, rows in groups.items()}
        for name, rows in groups.items():
            inventories[name].update(memory_identity(kind, row, identity_mode) for row in rows)

    ambiguous = sorted(key for key, count in inventories["window"].items() if not key or count > 1)
    audited = []
    for case in cases:
        labels = []
        for key in case["relevant"]:
            if inventories["raw"][key] > 1:
                state = "ambiguous"
            elif inventories["window"][key]:
                state = "reachable"
            elif inventories["active"][key]:
                state = "outside_window"
            elif inventories["raw"][key]:
                state = "inactive"
            else:
                state = "missing"
            labels.append({"identity": key, "state": state})
        audited.append({"case_id": str(case.get("case_id") or ""), "labels": labels})
    report = {
        "valid": not errors and not ambiguous and all(
            label["state"] == "reachable" for case in audited for label in case["labels"]
        ),
        "identity_mode": identity_mode,
        "ledger_sha256": fingerprints,
        "counts": counts,
        "unavailable_ledgers": errors,
        "ambiguous_candidates": ambiguous,
        "cases": audited,
    }
    require_unchanged_ledgers(report, users_root=users_root, user=user)
    return report


def require_memory_labels(cases: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    report = audit_memory_labels(cases, **kwargs)
    if not report["valid"]:
        raise InvalidMemoryLabels(report)
    return report
