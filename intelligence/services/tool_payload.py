"""Structured caliber fields for a tool return — names and dataset, never the body.

Phase 3 of the measured-value caliber contract: a failed fact can be attributed
to retrieve vs synthesize only if the observation records which table and which
columns came back. Hashing the field-name list plus dataset (not row values)
keeps volume small and avoids persisting cell contents.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence


_PATH_MARKERS = ("/Users/", "/home/")


def _safe_token(value: object, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text or any(marker in text for marker in _PATH_MARKERS):
        return fallback
    return text


def tool_payload_meta(
    *,
    dataset: str | None = None,
    caliber: str | None = None,
    field_names: Sequence[str] | None = None,
) -> tuple[str, str, tuple[str, ...], str]:
    """Return ``(dataset, caliber, field_names, payload_sha256)``.

    Empty dataset becomes ``unknown``. Empty field names become ``("unknown",)``.
    Tokens containing ``/Users/`` or ``/home/`` are dropped (red line).
    The digest covers dataset + field names only — never row values.
    """

    dataset_s = _safe_token(dataset, fallback="unknown") or "unknown"
    caliber_s = _safe_token(caliber, fallback="")
    names: list[str] = []
    seen: set[str] = set()
    for raw in field_names or ():
        name = _safe_token(raw)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    if not names:
        names = ["unknown"]
    digest = hashlib.sha256(
        json.dumps(
            {"dataset": dataset_s, "fields": names},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return dataset_s, caliber_s, tuple(names), digest


def field_names_from_rows(
    rows: Iterable[Mapping[str, object]] | None,
    *,
    requested: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Prefer returned column names; fall back to the requested metric/dimension list."""

    names: list[str] = []
    seen: set[str] = set()
    for row in rows or ():
        for key in row:
            token = _safe_token(key)
            if not token or token in seen:
                continue
            seen.add(token)
            names.append(token)
    if names:
        return tuple(names)
    for raw in requested or ():
        token = _safe_token(raw)
        if not token or token in seen:
            continue
        seen.add(token)
        names.append(token)
    return tuple(names)
