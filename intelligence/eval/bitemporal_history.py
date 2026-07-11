"""Final-history reconstruction and strict point-in-time replay views."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
BASELINE_TABLES = (
    "fact_market_daily",
    "fact_sector_daily",
    "fact_stock_daily",
)
MAJOR_FIELDS = {
    "price",
    "close",
    "pre_close",
    "amount",
    "total_amount",
    "volume",
    "vol",
    "market_cap",
    "circ_mv",
    "total_mv",
    "float_mcap_yi",
    "total_mcap_yi",
    "free_float_mcap_yi",
}
IDENTITY_FIELDS = (
    "trade_date",
    "source_date",
    "start_date",
    "end_date",
    "period_type",
    "dimension",
    "scope",
    "data_stage",
    "theme_code",
    "theme_name",
    "sector_ts_code",
    "sector_name",
    "sw_l1_code",
    "sw_l1",
    "stock_ts_code",
    "stock_name",
    "group_type",
    "sequence_no",
    "rank",
)
ARTIFACT_SUFFIXES = {
    ".csv",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_METADATA_FIELDS = {"valid_time", "known_at", "revision_note"}


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _canonical_sha(value: Any) -> str:
    body = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write_json(path: str | Path, body: dict[str, Any]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            body,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )


def cutoff_for_date(value: str) -> datetime:
    return datetime.combine(
        date.fromisoformat(value) + timedelta(days=1),
        time.min,
        tzinfo=SHANGHAI,
    )


def _connect(db_path: str | Path):
    import duckdb

    return duckdb.connect(str(Path(db_path).expanduser()), read_only=True)


def _table_columns(con: Any, table: str) -> list[str]:
    if not _IDENTIFIER.fullmatch(table):
        return []
    return [
        str(row[0])
        for row in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            ORDER BY ordinal_position
            """,
            [table],
        ).fetchall()
    ]


def _dated_fact_tables(con: Any) -> tuple[list[str], list[str]]:
    rows = con.execute(
        """
        SELECT table_name,
               COUNT(*) FILTER (
                   WHERE column_name = 'trade_date'
               ) AS has_trade_date
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name LIKE 'fact_%'
        GROUP BY table_name
        ORDER BY table_name
        """
    ).fetchall()
    dated = [str(row[0]) for row in rows if int(row[1]) == 1]
    skipped = [str(row[0]) for row in rows if int(row[1]) != 1]
    return dated, skipped


def _row_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [str(item[0]) for item in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    rows.sort(
        key=lambda row: json.dumps(
            row, ensure_ascii=False, sort_keys=True, default=_json_default
        )
    )
    return rows


def _normalize_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def _annotate_row(
    row: dict[str, Any],
    *,
    valid_time: str,
    cutoff: datetime,
    final_view: bool,
) -> dict[str, Any]:
    known = _normalize_datetime(row.get("updated_at"))
    ex_post = final_view and (known is None or known >= cutoff)
    return {
        **row,
        "valid_time": valid_time,
        "known_at": known.isoformat() if known else None,
        "revision_note": "ex-post" if ex_post else None,
    }


def _view_status(
    table_statuses: Iterable[str], has_artifacts: bool = False
) -> str:
    statuses = list(table_statuses)
    baseline_ready = all(status == "ready" for status in statuses)
    if baseline_ready:
        return "ready"
    if has_artifacts or any(
        status in {"ready", "partial"} for status in statuses
    ):
        return "partial"
    return "pending"


def _final_table(
    con: Any, table: str, value: str, cutoff: datetime
) -> dict[str, Any]:
    columns = _table_columns(con, table)
    cursor = con.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
        """,
        [value],
    )
    rows = [
        _annotate_row(row, valid_time=value, cutoff=cutoff, final_view=True)
        for row in _row_dicts(cursor)
    ]
    ex_post_rows = sum(row["revision_note"] == "ex-post" for row in rows)
    return {
        "status": "ready" if rows else "missing",
        "row_count": len(rows),
        "ex_post_rows": ex_post_rows,
        "timestamp_field": "updated_at" if "updated_at" in columns else None,
        "rows": rows,
    }


def _build_final_history_from_connection(
    date: str,
    con: Any,
) -> dict[str, Any]:
    cutoff = cutoff_for_date(date)
    tables, skipped = _dated_fact_tables(con)
    table_views = {
        table: _final_table(con, table, date, cutoff) for table in tables
    }
    baseline = {
        table: table_views.get(table, {"status": "missing"})["status"]
        for table in BASELINE_TABLES
    }
    body = {
        "schema_version": "bitemporal-history-1.0",
        "task_id": "bitemporal-history-v1",
        "view": "final_history",
        "date": date,
        "cutoff_timestamp": cutoff.isoformat(),
        "status": _view_status(baseline.values()),
        "decision_eligible": False,
        "rules": {
            "question": "What actually happened on this date?",
            "ex_post": (
                "Rows first known at or after cutoff are retained "
                "and marked ex-post."
            ),
            "missing": (
                "Missing final facts remain pending; values are never guessed."
            ),
        },
        "baseline_status": baseline,
        "skipped_fact_tables_without_trade_date": skipped,
        "tables": table_views,
    }
    body["snapshot_sha256"] = _canonical_sha(body)
    return body


def build_final_history(
    date: str,
    db_path: str | Path,
) -> dict[str, Any]:
    """Return current best facts, explicitly marking ex-post rows."""
    con = _connect(db_path)
    try:
        return _build_final_history_from_connection(date, con)
    finally:
        con.close()


def _git(
    root: str | Path, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(Path(root).expanduser()), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _git_commit_as_of(
    root: str | Path, cutoff_timestamp: datetime
) -> dict[str, Any] | None:
    try:
        sha = _git(
            root,
            [
                "rev-list",
                "-1",
                f"--before={cutoff_timestamp.isoformat()}",
                "HEAD",
            ],
        ).stdout.strip()
        if not sha:
            return None
        committed_at = _git(
            root, ["show", "-s", "--format=%cI", sha]
        ).stdout.strip()
        committed = _normalize_datetime(committed_at)
        normalized_cutoff = cutoff_timestamp.astimezone(SHANGHAI)
        if committed is None or committed > normalized_cutoff:
            return None
        return {"commit": sha, "committed_at": committed_at}
    except (OSError, subprocess.CalledProcessError):
        return None


def _artifact_kind(repo_name: str, path: str) -> str | None:
    if path.startswith("market_feature_store/exports/"):
        return "market_export"
    if path.startswith("docs/learning/forecast-review-ledger/"):
        return "answer_archive"
    if path.startswith("复盘/"):
        return "review_artifact"
    if path.startswith("raw/") or (
        repo_name == "wiki"
        and (path.startswith("wiki/raw/") or path.startswith("wiki/sources/"))
    ):
        return "source_material"
    return None


def _dated_artifacts(
    root: str | Path, commit: str, value: str, repo_name: str
) -> list[dict[str, str]]:
    try:
        paths = _git(
            root, ["ls-tree", "-r", "--name-only", commit]
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return []
    compact = value.replace("-", "")
    artifacts: list[dict[str, str]] = []
    for path in paths:
        kind = _artifact_kind(repo_name, path)
        if (
            kind
            and (value in path or compact in path)
            and Path(path).suffix.lower() in ARTIFACT_SUFFIXES
        ):
            artifacts.append({"path": path, "kind": kind})
    return sorted(artifacts, key=lambda item: (item["kind"], item["path"]))


def _known_table(
    con: Any,
    table: str,
    value: str,
    cutoff_timestamp: datetime,
) -> dict[str, Any]:
    columns = _table_columns(con, table)
    total_rows = int(
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
            """,
            [value],
        ).fetchone()[0]
    )
    if not total_rows:
        return {
            "status": "missing",
            "final_row_count": 0,
            "known_row_count": 0,
            "excluded_post_cutoff_rows": 0,
            "timestamp_field": (
                "updated_at" if "updated_at" in columns else None
            ),
            "rows": [],
        }
    if "updated_at" not in columns:
        return {
            "status": "unverifiable",
            "final_row_count": total_rows,
            "known_row_count": 0,
            "excluded_post_cutoff_rows": total_rows,
            "timestamp_field": None,
            "rows": [],
        }
    cursor = con.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
          AND updated_at < ?
        """,
        [value, cutoff_timestamp.replace(tzinfo=None)],
    )
    rows = [
        _annotate_row(
            row,
            valid_time=value,
            cutoff=cutoff_timestamp,
            final_view=False,
        )
        for row in _row_dicts(cursor)
    ]
    known_rows = len(rows)
    status = (
        "ready"
        if known_rows == total_rows
        else "partial"
        if known_rows
        else "unavailable"
    )
    return {
        "status": status,
        "final_row_count": total_rows,
        "known_row_count": known_rows,
        "excluded_post_cutoff_rows": total_rows - known_rows,
        "timestamp_field": "updated_at",
        "rows": rows,
    }


def _known_table_from_final(
    final_table: dict[str, Any],
    cutoff_timestamp: datetime,
) -> dict[str, Any]:
    total_rows = int(final_table["row_count"])
    if not total_rows:
        return {
            "status": "missing",
            "final_row_count": 0,
            "known_row_count": 0,
            "excluded_post_cutoff_rows": 0,
            "timestamp_field": final_table["timestamp_field"],
            "rows": [],
        }
    if final_table["timestamp_field"] != "updated_at":
        return {
            "status": "unverifiable",
            "final_row_count": total_rows,
            "known_row_count": 0,
            "excluded_post_cutoff_rows": total_rows,
            "timestamp_field": None,
            "rows": [],
        }
    rows = []
    for final_row in final_table["rows"]:
        known_at = _normalize_datetime(final_row.get("known_at"))
        if known_at is not None and known_at < cutoff_timestamp:
            rows.append({**final_row, "revision_note": None})
    known_rows = len(rows)
    status = (
        "ready"
        if known_rows == total_rows
        else "partial"
        if known_rows
        else "unavailable"
    )
    return {
        "status": status,
        "final_row_count": total_rows,
        "known_row_count": known_rows,
        "excluded_post_cutoff_rows": total_rows - known_rows,
        "timestamp_field": "updated_at",
        "rows": rows,
    }


def _build_as_known_at_from_connection(
    date: str,
    con: Any,
    kb_root: str | Path,
    finance_root: str | Path,
    cutoff_timestamp: datetime,
    final_tables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return only facts and repository states available before the cutoff."""
    if cutoff_timestamp.tzinfo is None:
        cutoff_timestamp = cutoff_timestamp.replace(tzinfo=SHANGHAI)
    else:
        cutoff_timestamp = cutoff_timestamp.astimezone(SHANGHAI)
    tables, skipped = _dated_fact_tables(con)
    if final_tables is None:
        table_views = {
            table: _known_table(con, table, date, cutoff_timestamp)
            for table in tables
        }
    else:
        table_views = {
            table: _known_table_from_final(
                final_tables[table],
                cutoff_timestamp,
            )
            for table in tables
        }

    repositories: dict[str, Any] = {}
    for name, root in (("finance", finance_root), ("wiki", kb_root)):
        state = _git_commit_as_of(root, cutoff_timestamp)
        artifacts = []
        if state:
            artifacts = _dated_artifacts(
                root, state["commit"], date, name
            )
        repositories[name] = {
            **(state or {"commit": None, "committed_at": None}),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        }
    baseline = {
        table: table_views.get(table, {"status": "missing"})["status"]
        for table in BASELINE_TABLES
    }
    has_artifacts = any(
        state["artifact_count"] for state in repositories.values()
    )
    body = {
        "schema_version": "bitemporal-history-1.0",
        "task_id": "bitemporal-history-v1",
        "view": "as_known_at",
        "date": date,
        "cutoff_timestamp": cutoff_timestamp.isoformat(),
        "status": _view_status(baseline.values(), has_artifacts),
        "decision_eligible": False,
        "rules": {
            "question": "What could this Agent actually know at the cutoff?",
            "database": (
                "Only rows with updated_at strictly before cutoff "
                "are included."
            ),
            "repositories": "Only commits at or before cutoff are referenced.",
            "missing": (
                "Post-cutoff backfill is excluded; "
                "missing values remain pending."
            ),
        },
        "baseline_status": baseline,
        "skipped_fact_tables_without_trade_date": skipped,
        "repositories": repositories,
        "tables": table_views,
    }
    body["snapshot_sha256"] = _canonical_sha(body)
    return body


def build_as_known_at(
    date: str,
    db_path: str | Path,
    kb_root: str | Path,
    finance_root: str | Path,
    cutoff_timestamp: datetime,
) -> dict[str, Any]:
    """Return only facts and repository states available before the cutoff."""
    con = _connect(db_path)
    try:
        return _build_as_known_at_from_connection(
            date,
            con,
            kb_root,
            finance_root,
            cutoff_timestamp,
        )
    finally:
        con.close()


def _identity(row: dict[str, Any]) -> str:
    parts = [
        (field, row.get(field))
        for field in IDENTITY_FIELDS
        if field in row and row.get(field) not in (None, "")
    ]
    if not parts:
        parts = sorted(
            (field, value)
            for field, value in row.items()
            if field not in _METADATA_FIELDS | {"updated_at", "source"}
        )
    return json.dumps(parts, ensure_ascii=False, default=_json_default)


def _group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_identity(row), []).append(row)
    for values in grouped.values():
        values.sort(
            key=lambda row: json.dumps(
                row, ensure_ascii=False, sort_keys=True, default=_json_default
            )
        )
    return grouped


def _comparable(row: dict[str, Any]) -> dict[str, Any]:
    return {
        field: value
        for field, value in row.items()
        if field not in _METADATA_FIELDS | {"updated_at"}
    }


def compare_snapshots(
    final: dict[str, Any],
    known: dict[str, Any],
) -> dict[str, Any]:
    """Compare paired views and flag major-field revisions for human review."""
    if final.get("date") != known.get("date"):
        raise ValueError("snapshot dates do not match")
    if (
        final.get("view") != "final_history"
        or known.get("view") != "as_known_at"
    ):
        raise ValueError("expected final_history and as_known_at snapshots")

    tables = sorted(
        set((final.get("tables") or {})) | set((known.get("tables") or {}))
    )
    table_results: dict[str, Any] = {}
    totals: Counter[str] = Counter()
    review_items: list[dict[str, Any]] = []
    for table in tables:
        final_table = (final.get("tables") or {}).get(table) or {}
        known_table = (known.get("tables") or {}).get(table) or {}
        final_rows = final_table.get("rows") or []
        known_rows = known_table.get("rows") or []
        final_grouped = _group_rows(final_rows)
        known_grouped = _group_rows(known_rows)
        changes: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        for identity in sorted(set(final_grouped) | set(known_grouped)):
            left = final_grouped.get(identity, [])
            right = known_grouped.get(identity, [])
            width = max(len(left), len(right))
            for index in range(width):
                final_row = left[index] if index < len(left) else None
                known_row = right[index] if index < len(right) else None
                if final_row is None:
                    status = "known_only"
                    fields: list[dict[str, Any]] = []
                elif known_row is None:
                    status = "missing"
                    fields = []
                else:
                    left_fields = _comparable(final_row)
                    right_fields = _comparable(known_row)
                    fields = [
                        {
                            "field": field,
                            "final": left_fields.get(field),
                            "known": right_fields.get(field),
                            "major": field in MAJOR_FIELDS,
                        }
                        for field in sorted(
                            set(left_fields) | set(right_fields)
                        )
                        if left_fields.get(field) != right_fields.get(field)
                    ]
                    status = "updated" if fields else "unchanged"
                counts[status] += 1
                if status != "unchanged":
                    item = {
                        "identity": json.loads(identity),
                        "occurrence": index + 1,
                        "status": status,
                        "field_changes": fields,
                    }
                    changes.append(item)
                    for field in fields:
                        if field["major"]:
                            review_items.append(
                                {
                                    "table": table,
                                    "identity": item["identity"],
                                    **field,
                                }
                            )
        totals.update(counts)
        table_results[table] = {
            "counts": dict(counts),
            "changes": changes,
        }
    status = (
        "needs_review"
        if review_items
        else "partial"
        if totals["missing"] or totals["updated"] or totals["known_only"]
        else "unchanged"
    )
    body = {
        "schema_version": "bitemporal-history-comparison-1.0",
        "task_id": "bitemporal-history-v1",
        "date": final["date"],
        "status": status,
        "counts": dict(totals),
        "needs_review": review_items,
        "tables": table_results,
    }
    body["comparison_sha256"] = _canonical_sha(body)
    return body


def _feature_contract_check_from_connection(
    date: str,
    con: Any,
    required_window_days: int,
    table: str,
    metric: str,
) -> dict[str, Any]:
    """Verify a metric has a complete PIT-visible trading-day window."""
    if required_window_days <= 0:
        raise ValueError("required_window_days must be positive")
    if not _IDENTIFIER.fullmatch(table) or not _IDENTIFIER.fullmatch(metric):
        raise ValueError("unsafe table or metric identifier")
    cutoff = cutoff_for_date(date)
    columns = _table_columns(con, table)
    if not columns or "trade_date" not in columns:
        return {
            "date": date,
            "table": table,
            "metric": metric,
            "required_window_days": required_window_days,
            "eligible": False,
            "status": "pending",
            "reason": "table or trade_date is missing",
            "expected_dates": [],
            "available_dates": [],
            "missing_dates": [],
        }
    if "updated_at" not in columns or metric not in columns:
        return {
            "date": date,
            "table": table,
            "metric": metric,
            "required_window_days": required_window_days,
            "eligible": False,
            "status": "pending",
            "reason": "updated_at or metric is missing",
            "expected_dates": [],
            "available_dates": [],
            "missing_dates": [],
        }
    expected_dates = [
        str(row[0])[:10]
        for row in con.execute(
            """
            SELECT DISTINCT trade_date
            FROM fact_market_daily
            WHERE CAST(trade_date AS DATE) <= CAST(? AS DATE)
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [date, required_window_days],
        ).fetchall()
    ]
    expected_dates.reverse()
    if len(expected_dates) < required_window_days:
        return {
            "date": date,
            "table": table,
            "metric": metric,
            "required_window_days": required_window_days,
            "eligible": False,
            "status": "ineligible",
            "reason": "insufficient trading-calendar history",
            "cutoff_timestamp": cutoff.isoformat(),
            "expected_dates": expected_dates,
            "available_dates": [],
            "missing_dates": expected_dates,
        }
    placeholders = ", ".join("?" for _ in expected_dates)
    available_dates = [
        str(row[0])[:10]
        for row in con.execute(
            f"""
            SELECT DISTINCT trade_date
            FROM {table}
            WHERE CAST(trade_date AS VARCHAR) IN ({placeholders})
              AND updated_at < ?
              AND {metric} IS NOT NULL
            ORDER BY trade_date
            """,
            [*expected_dates, cutoff.replace(tzinfo=None)],
        ).fetchall()
    ]
    available = set(available_dates)
    missing_dates = [
        expected for expected in expected_dates if expected not in available
    ]
    eligible = not missing_dates
    return {
        "schema_version": "feature-contract-1.0",
        "date": date,
        "table": table,
        "metric": metric,
        "required_window_days": required_window_days,
        "eligible": eligible,
        "status": "eligible" if eligible else "ineligible",
        "reason": "" if eligible else "PIT-visible trading-day gaps detected",
        "cutoff_timestamp": cutoff.isoformat(),
        "expected_dates": expected_dates,
        "available_dates": available_dates,
        "missing_dates": missing_dates,
    }


def feature_contract_check(
    date: str,
    db_path: str | Path,
    required_window_days: int,
    table: str,
    metric: str,
) -> dict[str, Any]:
    """Verify a metric has a complete PIT-visible trading-day window."""
    con = _connect(db_path)
    try:
        return _feature_contract_check_from_connection(
            date,
            con,
            required_window_days,
            table,
            metric,
        )
    finally:
        con.close()


def _seal_snapshot(body: dict[str, Any]) -> None:
    body.pop("snapshot_sha256", None)
    body["snapshot_sha256"] = _canonical_sha(body)


def _validate_pair(
    final: dict[str, Any],
    known: dict[str, Any],
) -> None:
    for table, final_table in final["tables"].items():
        known_table = known["tables"][table]
        final_rows = int(final_table["row_count"])
        source_rows = int(known_table["final_row_count"])
        known_rows = int(known_table["known_row_count"])
        excluded_rows = int(known_table["excluded_post_cutoff_rows"])
        if final_rows != source_rows:
            raise RuntimeError(
                f"source changed while building {final['date']}:{table}"
            )
        if known_rows + excluded_rows != source_rows:
            raise RuntimeError(
                f"invalid PIT partition for {final['date']}:{table}"
            )
        if known_rows + int(final_table["ex_post_rows"]) != final_rows:
            raise RuntimeError(
                f"ex-post partition mismatch for {final['date']}:{table}"
            )


def _database_signature(db_path: str | Path) -> dict[str, int]:
    stat = Path(db_path).expanduser().stat()
    return {
        "device": int(stat.st_dev),
        "inode": int(stat.st_ino),
        "size": int(stat.st_size),
        "modified_ns": int(stat.st_mtime_ns),
    }


def iter_pilot_cases(
    dates: Iterable[str],
    db_path: str | Path,
    kb_root: str | Path,
    finance_root: str | Path,
    contracts: Iterable[tuple[str, str, int]],
) -> Iterator[dict[str, Any]]:
    """Yield paired views while rejecting a changing source database."""
    source_signature = _database_signature(db_path)
    con = _connect(db_path)
    con.execute("BEGIN TRANSACTION")
    try:
        for value in dates:
            cutoff = cutoff_for_date(value)
            final = _build_final_history_from_connection(value, con)
            known = _build_as_known_at_from_connection(
                value,
                con,
                kb_root,
                finance_root,
                cutoff,
                final["tables"],
            )
            _validate_pair(final, known)
            current_signature = _database_signature(db_path)
            if current_signature != source_signature:
                raise RuntimeError(
                    "source database changed during pilot generation"
                )
            source_snapshot = _canonical_sha(
                {
                    table: {
                        "row_count": table_view["row_count"],
                        "rows": table_view["rows"],
                    }
                    for table, table_view in final["tables"].items()
                }
            )
            final["source_snapshot_sha256"] = source_snapshot
            known["source_snapshot_sha256"] = source_snapshot
            final["source_database_signature"] = source_signature
            known["source_database_signature"] = source_signature
            _seal_snapshot(final)
            _seal_snapshot(known)
            feature_contracts = [
                _feature_contract_check_from_connection(
                    value,
                    con,
                    days,
                    table,
                    metric,
                )
                for table, metric, days in contracts
            ]
            current_signature = _database_signature(db_path)
            if current_signature != source_signature:
                raise RuntimeError(
                    "source database changed during pilot generation"
                )
            yield {
                "date": value,
                "cutoff": cutoff,
                "final": final,
                "known": known,
                "comparison": compare_snapshots(final, known),
                "feature_contracts": feature_contracts,
            }
    finally:
        con.execute("ROLLBACK")
        con.close()


def build_gold_standard_template(date: str) -> dict[str, Any]:
    return {
        "schema_version": "bitemporal-history-gold-1.0",
        "task_id": "bitemporal-history-v1",
        "date": date,
        "reviewer": None,
        "reviewed_at": None,
        "events": [
            {
                "event_id": "",
                "valid_time": None,
                "known_at": None,
                "statement": "",
                "source_refs": [],
                "timeline_status": "pending",
                "notes": "",
            }
        ],
        "entity_classifications": [
            {
                "entity": "",
                "expected_classification": "",
                "source_refs": [],
                "status": "pending",
                "notes": "",
            }
        ],
        "causal_statements": [
            {
                "claim": "",
                "evidence_refs": [],
                "alternative_explanations": [],
                "status": "pending",
                "notes": "",
            }
        ],
        "instructions": {
            "statuses": ["pass", "fail", "pending", "not_applicable"],
            "rule": (
                "Evidence gaps remain pending. Do not infer missing facts."
            ),
        },
    }


def render_pilot_report(report: dict[str, Any]) -> str:
    counts = report["status_counts"]
    lines = [
        "# 双时态历史评测 10 日 Pilot",
        "",
        f"- 日期数：{report['date_count']}",
        (
            "- final ready / partial / pending："
            f"{counts['final'].get('ready', 0)} / "
            f"{counts['final'].get('partial', 0)} / "
            f"{counts['final'].get('pending', 0)}"
        ),
        (
            "- PIT ready / partial / pending："
            f"{counts['known'].get('ready', 0)} / "
            f"{counts['known'].get('partial', 0)} / "
            f"{counts['known'].get('pending', 0)}"
        ),
        f"- needs_review：{counts['comparison'].get('needs_review', 0)}",
        "- 决策资格：否（只评测历史忠实度，不证明预测有效）。",
        "",
        (
            "| 日期 | final | final行 | ex-post | PIT | PIT行 "
            "| 字段覆盖 | 冲突字段 | Git资料 | 对照 | MA20 |"
        ),
        (
            "|---|---:|---:|---:|---:|---:|---:|---:|"
            "---:|---:|---:|"
        ),
    ]
    for case in report["cases"]:
        lines.append(
            f"| {case['date']} | {case['final_status']} "
            f"| {case['final_rows']} "
            f"| {case['ex_post_rows']} | {case['known_status']} "
            f"| {case['known_rows']} | {case['field_coverage_pct']:.2f}% "
            f"| {case['conflict_field_count']} "
            f"| {case['artifact_count']} "
            f"| {case['comparison_status']} "
            f"| {case['feature_contract_status']} |"
        )
    lines.extend(
        [
            "",
            "## 判定纪律",
            "",
            (
                "- `final_history` 接受事后校正值，但 D0 后获知的行"
                "必须标记 `ex-post`。"
            ),
            (
                "- `as_known_at` 只接受 `updated_at < cutoff` 的行"
                "和 cutoff 前 Git commit。"
            ),
            "- 两套 JSON 位于独立目录；最终事实不得回流为当时输入。",
            (
                "- 缺失为 `pending`，部分覆盖为 `partial`，"
                "重大字段��突为 `needs_review`。"
            ),
            "",
        ]
    )
    return "\n".join(lines)
