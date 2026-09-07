"""Canonical hashes and immutable teaching-framework build receipts."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Sequence

import duckdb

from intelligence.services.methodology_backtest.store import naive_utc

RECEIPT_STATUS_OK = "ok"
RECEIPT_STATUS_INCOMPARABLE = "incomparable"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"cannot canonicalize {type(value).__name__}")


def _canonical_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        # JSON's shortest decimal representation is stable across DuckDB and
        # Python for the finite values used by these labels.
        return value if value == value and abs(value) != float("inf") else None
    return value


def canonical_rows_hash(
    rows: Iterable[Sequence[Any]] | duckdb.DuckDBPyConnection,
    *,
    columns: Sequence[str] | None = None,
    primary_key: Sequence[str] | None = None,
    exclude_columns: Sequence[str] = ("computed_at",),
    table: str | None = None,
) -> str:
    """Hash rows in deterministic column/key order.

    ``computed_at`` is excluded by default because it records build time, not
    the derived object.  Columns are hashed in name order, not physical order:
    a sidecar that gained a column through ``ALTER TABLE`` and a freshly created
    one must hash identical content to the same value.  A connection plus
    ``table`` is accepted for callers rebuilding a sidecar table; an iterable is
    convenient in unit tests.
    """

    if isinstance(rows, duckdb.DuckDBPyConnection):
        if not table:
            raise ValueError("connection 输入必须同时提供 table")
        description = rows.execute(f"SELECT * FROM {table} LIMIT 0").description
        all_columns = [str(item[0]) for item in description]
        selected = sorted(name for name in all_columns if name not in set(exclude_columns))
        order = list(primary_key or selected)
        query = f"SELECT {', '.join(selected)} FROM {table}"
        if order:
            query += " ORDER BY " + ", ".join(order)
        result = rows.execute(query).fetchall()
        columns = selected
        rows = result
    else:
        if columns is None:
            raise ValueError("iterable rows 输入必须提供 columns")
        selected = sorted(name for name in columns if name not in set(exclude_columns))
        indexes = [list(columns).index(name) for name in selected]
        materialized = []
        for row in rows:
            if isinstance(row, dict):
                materialized.append([_canonical_value(row.get(name)) for name in selected])
            else:
                materialized.append([_canonical_value(row[i]) for i in indexes])
        if primary_key:
            key_indexes = [list(selected).index(name) for name in primary_key if name in selected]
            materialized.sort(key=lambda row: tuple(row[i] for i in key_indexes))
        rows = materialized
        columns = selected

    payload = {"columns": list(columns or []), "rows": [[_canonical_value(v) for v in row] for row in rows]}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def source_fingerprint(
    *, source_db: str, source_max_trade_date: Any, source_row_counts: dict[str, Any], label_version: str
) -> str:
    payload = {
        "source_db": source_db,
        "source_max_trade_date": source_max_trade_date,
        "source_row_counts": source_row_counts,
        "label_version": label_version,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def make_receipt(
    *,
    build_kind: str,
    framework_version: str,
    label_version: str,
    source_db: str,
    source_max_trade_date: Any,
    source_row_counts: dict[str, Any],
    parameter_hash: str,
    canonical_hash: str | None,
    coverage_summary: dict[str, Any] | None = None,
    gap_summary: dict[str, Any] | None = None,
    readouts: dict[str, Any] | None = None,
    computed_at: datetime | None = None,
    build_id: str | None = None,
) -> dict[str, Any]:
    ts = computed_at or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return {
        "build_id": build_id or f"{build_kind}-{uuid.uuid4().hex}",
        "build_kind": build_kind,
        "framework_version": framework_version,
        "label_version": label_version,
        "source_db": str(source_db),
        "source_max_trade_date": str(source_max_trade_date) if source_max_trade_date is not None else None,
        "source_row_counts": source_row_counts,
        "source_fingerprint": source_fingerprint(
            source_db=str(source_db),
            source_max_trade_date=source_max_trade_date,
            source_row_counts=source_row_counts,
            label_version=label_version,
        ),
        "parameter_hash": parameter_hash,
        "coverage_summary": coverage_summary or {},
        "gap_summary": gap_summary or {},
        "readouts": readouts or {},
        "canonical_hash": canonical_hash,
        "status": RECEIPT_STATUS_OK,
        "status_reason": None,
        "computed_at": ts,
    }


def write_receipt(con: duckdb.DuckDBPyConnection, receipt: dict[str, Any]) -> str:
    """Insert an immutable receipt and mark prior incompatible versions.

    The receipt row itself is never updated or deleted.  Only the status of a
    prior row is changed when its framework/parameter namespace differs; all
    prior metadata and hashes remain queryable for audit.
    """

    con.execute(
        """
        UPDATE history_teaching_receipts
        SET status = ?, status_reason = ?
        WHERE status = ? AND build_kind = ?
          AND (framework_version <> ? OR parameter_hash <> ?)
        """,
        [
            RECEIPT_STATUS_INCOMPARABLE,
            "framework_version_or_parameter_hash_changed",
            RECEIPT_STATUS_OK,
            receipt["build_kind"],
            receipt["framework_version"],
            receipt["parameter_hash"],
        ],
    )
    con.execute(
        """
        INSERT INTO history_teaching_receipts
        (build_id, build_kind, framework_version, label_version, source_db,
         source_max_trade_date, source_row_counts, source_fingerprint,
         parameter_hash, coverage_summary, gap_summary, readouts, canonical_hash,
         status, status_reason, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            receipt["build_id"],
            receipt["build_kind"],
            receipt["framework_version"],
            receipt["label_version"],
            receipt["source_db"],
            receipt["source_max_trade_date"],
            canonical_json(receipt["source_row_counts"]),
            receipt["source_fingerprint"],
            receipt["parameter_hash"],
            canonical_json(receipt["coverage_summary"]),
            canonical_json(receipt["gap_summary"]),
            canonical_json(receipt.get("readouts") or {}),
            receipt["canonical_hash"],
            receipt["status"],
            receipt["status_reason"],
            naive_utc(receipt["computed_at"]),
        ],
    )
    return str(receipt["build_id"])


# Explicit aliases make the API readable at call sites and keep room for the
# CLI to use terminology from the spec without duplicating implementation.
build_receipt = make_receipt
persist_receipt = write_receipt
