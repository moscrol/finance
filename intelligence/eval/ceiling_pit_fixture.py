"""Physical point-in-time exports for the sealed runtime ceiling benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Literal
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
TEMPORAL_COLUMNS = frozenset(
    {
        "trade_date",
        "date",
        "source_date",
        "report_date",
        "ann_date",
        "announcement_date",
        "end_date",
        "report_period",
        "source_update_time",
        "updated_at",
        "created_at",
        "published_at",
        "first_seen_date",
        "last_seen_date",
        "start_date",
        "similar_date",
        "first_limit_date",
        "startup_date_small",
        "startup_date_big",
        "startup_date_super",
        "startup_date_extend",
        "strength_updated_at",
        "stock_high_updated_at",
        "sh_index_updated_at",
        "multi_period_updated_at",
        "limit_update_time",
        "prev_limitup_date",
        "as_of_date",
    }
)
NON_TEMPORAL_MARKER_COLUMNS = frozenset(
    {
        "multi_period_resonance",
        "multi_period_source",
        "period_type",
        "limit_times",
        "primary_high_period",
        "high_periods_json",
        "is_realtime",
        "open_times",
    }
)
INTRADAY_TIME_COLUMNS = frozenset({"first_limit_time", "last_limit_time"})
TEMPORAL_MARKERS = ("date", "time", "year", "period", "when")
_NUMERIC_TYPES = re.compile(
    r"^(?:U?TINYINT|U?SMALLINT|U?INTEGER|U?BIGINT|HUGEINT|DECIMAL|NUMERIC)"
)


class TemporalSchemaError(ValueError):
    """Raised when a temporal column cannot be classified safely."""


class TemporalValueError(ValueError):
    """Raised when a date-bearing value cannot be parsed safely."""


@dataclass(frozen=True)
class TableCopyReceipt:
    name: str
    source_kind: Literal["BASE TABLE", "VIEW"]
    temporal_columns: tuple[str, ...]
    intraday_time_columns: tuple[str, ...]
    marker_exceptions: tuple[str, ...]
    source_rows: int
    target_rows: int
    maxima: dict[str, str | None]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "source_kind": self.source_kind,
            "temporal_columns": list(self.temporal_columns),
            "intraday_time_columns": list(self.intraday_time_columns),
            "marker_exceptions": list(self.marker_exceptions),
            "source_rows": self.source_rows,
            "target_rows": self.target_rows,
            "maxima": dict(self.maxima),
        }


@dataclass(frozen=True)
class FilteredDuckDBReceipt:
    source_path: Path
    target_path: Path
    as_of: str
    cutoff_timestamp: str
    tables: tuple[TableCopyReceipt, ...]
    target_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_path": str(self.source_path),
            "target_path": str(self.target_path),
            "as_of": self.as_of,
            "cutoff_timestamp": self.cutoff_timestamp,
            "tables": [item.to_dict() for item in self.tables],
            "target_sha256": self.target_sha256,
        }


@dataclass(frozen=True)
class FilteredDuckDBAudit:
    status: Literal["valid", "invalid"]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class _ObjectPlan:
    schema: str
    name: str
    source_kind: Literal["BASE TABLE", "VIEW"]
    columns: tuple[tuple[str, str], ...]
    temporal_columns: tuple[tuple[str, str], ...]
    intraday_time_columns: tuple[str, ...]
    marker_exceptions: tuple[str, ...]
    source_rows: int

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


def _duckdb() -> Any:
    try:
        import duckdb
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("duckdb is required for PIT fixture construction") from exc
    return duckdb


def _quote_ident(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _quote_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _qualified(schema: str, name: str, *, database: str | None = None) -> str:
    parts = [] if database is None else [_quote_ident(database)]
    parts.extend((_quote_ident(schema), _quote_ident(name)))
    return ".".join(parts)


def _cutoff(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("as_of must be non-empty")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            parsed = datetime.combine(date.fromisoformat(raw), time(23, 59, 59))
            return parsed.replace(tzinfo=SHANGHAI)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("as_of must be an ISO date or timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_sql(column: str, data_type: str) -> str:
    quoted = _quote_ident(column)
    normalized_type = data_type.upper().strip()
    if normalized_type == "TIMESTAMP WITH TIME ZONE":
        return f"CAST({quoted} AS TIMESTAMPTZ)"
    if normalized_type == "DATE" or normalized_type.startswith("TIMESTAMP"):
        return f"CAST({quoted} AS TIMESTAMP) AT TIME ZONE 'Asia/Shanghai'"
    text = f"TRIM(CAST({quoted} AS VARCHAR))"
    if _NUMERIC_TYPES.match(normalized_type):
        return (
            f"TRY_STRPTIME({text}, '%Y%m%d') "
            "AT TIME ZONE 'Asia/Shanghai'"
        )
    return (
        "CASE "
        f"WHEN REGEXP_FULL_MATCH({text}, '^[0-9]{{8}}$') "
        f"THEN TRY_STRPTIME({text}, '%Y%m%d') AT TIME ZONE 'Asia/Shanghai' "
        f"ELSE TRY_CAST({text} AS TIMESTAMPTZ) END"
    )


def _iso_datetime(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min).replace(tzinfo=SHANGHAI)
    if not isinstance(value, datetime):
        raise TypeError("temporal maximum must be date or datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=SHANGHAI)
    return value.astimezone(SHANGHAI).isoformat(timespec="seconds")


def _user_objects(connection: Any) -> tuple[tuple[str, str, str], ...]:
    rows = connection.execute(
        """
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY CASE WHEN table_type = 'BASE TABLE' THEN 0 ELSE 1 END,
                 table_schema,
                 table_name
        """
    ).fetchall()
    return tuple((str(schema), str(name), str(kind)) for schema, name, kind in rows)


def _columns(connection: Any, schema: str, name: str) -> tuple[tuple[str, str], ...]:
    rows = connection.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema, name],
    ).fetchall()
    return tuple((str(column), str(data_type)) for column, data_type in rows)


def _plan_objects(connection: Any) -> tuple[_ObjectPlan, ...]:
    plans: list[_ObjectPlan] = []
    for schema, name, kind in _user_objects(connection):
        if kind not in {"BASE TABLE", "VIEW"}:
            raise ValueError(f"unsupported DuckDB object type: {kind}")
        columns = _columns(connection, schema, name)
        unknown = tuple(
            column
            for column, _data_type in columns
            if column.casefold() not in TEMPORAL_COLUMNS
            and column.casefold() not in NON_TEMPORAL_MARKER_COLUMNS
            and column.casefold() not in INTRADAY_TIME_COLUMNS
            and any(marker in column.casefold() for marker in TEMPORAL_MARKERS)
        )
        if unknown:
            joined = ",".join(unknown)
            raise TemporalSchemaError(
                f"unclassified_temporal_column:{schema}.{name}:{joined}"
            )
        temporal = tuple(
            (column, data_type)
            for column, data_type in columns
            if column.casefold() in TEMPORAL_COLUMNS
        )
        intraday = tuple(
            column
            for column, _data_type in columns
            if column.casefold() in INTRADAY_TIME_COLUMNS
        )
        marker_exceptions = tuple(
            column
            for column, _data_type in columns
            if column.casefold() in NON_TEMPORAL_MARKER_COLUMNS
        )
        column_names = {column.casefold() for column, _data_type in columns}
        if intraday and not ({"trade_date", "date"} & column_names):
            raise TemporalSchemaError(
                f"intraday_time_without_date_anchor:{schema}.{name}:"
                + ",".join(intraday)
            )
        qualified = _qualified(schema, name)
        for column, data_type in temporal:
            expression = _normalized_sql(column, data_type)
            malformed = connection.execute(
                f"SELECT COUNT(*) FROM {qualified} "
                f"WHERE {_quote_ident(column)} IS NOT NULL AND ({expression}) IS NULL"
            ).fetchone()[0]
            if malformed:
                raise TemporalValueError(
                    f"malformed_temporal_value:{schema}.{name}:{column}:{malformed}"
                )
        for column in intraday:
            text = f"TRIM(CAST({_quote_ident(column)} AS VARCHAR))"
            valid_clock = (
                f"({text} = '0' OR "
                f"TRY_STRPTIME({text}, '%H:%M:%S') IS NOT NULL OR "
                f"(REGEXP_FULL_MATCH({text}, '^[0-9]{{5,6}}$') AND "
                f"TRY_STRPTIME(LPAD({text}, 6, '0'), '%H%M%S') IS NOT NULL))"
            )
            malformed = connection.execute(
                f"SELECT COUNT(*) FROM {qualified} "
                f"WHERE {_quote_ident(column)} IS NOT NULL AND NOT {valid_clock}"
            ).fetchone()[0]
            if malformed:
                raise TemporalValueError(
                    f"malformed_intraday_time:{schema}.{name}:{column}:{malformed}"
                )
        source_rows = int(
            connection.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0]
        )
        plans.append(
            _ObjectPlan(
                schema=schema,
                name=name,
                source_kind=kind,  # type: ignore[arg-type]
                columns=columns,
                temporal_columns=temporal,
                intraday_time_columns=intraday,
                marker_exceptions=marker_exceptions,
                source_rows=source_rows,
            )
        )
    return tuple(plans)


def _predicate(plan: _ObjectPlan) -> str:
    if not plan.temporal_columns:
        return "TRUE"
    return " AND ".join(
        "(" + _quote_ident(column) + " IS NULL OR "
        + _normalized_sql(column, data_type)
        + " <= ?::TIMESTAMPTZ)"
        for column, data_type in plan.temporal_columns
    )


def _maxima(connection: Any, plan: _ObjectPlan) -> dict[str, str | None]:
    qualified = _qualified(plan.schema, plan.name)
    maxima: dict[str, str | None] = {}
    for column, data_type in plan.temporal_columns:
        value = connection.execute(
            f"SELECT MAX({_normalized_sql(column, data_type)}) FROM {qualified}"
        ).fetchone()[0]
        maxima[column] = _iso_datetime(value)
    return maxima


def audit_filtered_duckdb(receipt: FilteredDuckDBReceipt) -> FilteredDuckDBAudit:
    issues: list[str] = []
    target = receipt.target_path
    if not target.is_file() or target.is_symlink():
        return FilteredDuckDBAudit("invalid", ("target_missing_or_non_regular",))
    if receipt.source_path.resolve() == target.resolve():
        issues.append("source_target_path_alias")
    if target.stat().st_mode & 0o777 != 0o444:
        issues.append("target_mode")
    if _sha256_file(target) != receipt.target_sha256:
        issues.append("target_hash")
    duckdb = _duckdb()
    try:
        connection = duckdb.connect(str(target), read_only=True)
        connection.execute("SET TimeZone = 'Asia/Shanghai'")
        attached = connection.execute("PRAGMA database_list").fetchall()
        target_resolved = target.resolve()
        for row in attached:
            attached_path = str(row[-1] or "").strip()
            if attached_path and Path(attached_path).resolve() != target_resolved:
                issues.append("external_database_attached")
        objects = {
            (schema, name): kind for schema, name, kind in _user_objects(connection)
        }
        for table in receipt.tables:
            schema, name = table.name.split(".", 1)
            if objects.get((schema, name)) != "BASE TABLE":
                issues.append(f"missing_materialized_table:{table.name}")
                continue
            plan = _ObjectPlan(
                schema=schema,
                name=name,
                source_kind=table.source_kind,
                columns=_columns(connection, schema, name),
                temporal_columns=tuple(
                    (column, data_type)
                    for column, data_type in _columns(connection, schema, name)
                    if column in table.temporal_columns
                ),
                intraday_time_columns=table.intraday_time_columns,
                marker_exceptions=table.marker_exceptions,
                source_rows=table.source_rows,
            )
            rows = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {_qualified(schema, name)}"
                ).fetchone()[0]
            )
            if rows != table.target_rows:
                issues.append(f"row_count:{table.name}")
            if _maxima(connection, plan) != table.maxima:
                issues.append(f"temporal_maximum:{table.name}")
        connection.close()
    except Exception:
        issues.append("target_reopen_failed")
    return FilteredDuckDBAudit(
        "invalid" if issues else "valid",
        tuple(dict.fromkeys(issues)),
    )


def build_filtered_duckdb(
    source_path: str | Path,
    target_path: str | Path,
    *,
    as_of: str,
) -> FilteredDuckDBReceipt:
    """Build one physical DuckDB whose date-bearing rows stop at ``as_of``."""

    source = Path(source_path).expanduser().resolve()
    target = Path(target_path).expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise ValueError("source DuckDB must be a regular file")
    if source == target:
        raise ValueError("source and target DuckDB paths must differ")
    if target.exists():
        raise FileExistsError("target DuckDB already exists")
    cutoff = _cutoff(as_of)
    cutoff_text = cutoff.isoformat(timespec="seconds")
    duckdb = _duckdb()
    source_connection = duckdb.connect(str(source), read_only=True)
    source_connection.execute("SET TimeZone = 'Asia/Shanghai'")
    try:
        plans = _plan_objects(source_connection)
    finally:
        source_connection.close()

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    receipts: list[TableCopyReceipt] = []
    try:
        connection = duckdb.connect(str(temporary))
        connection.execute("SET TimeZone = 'Asia/Shanghai'")
        connection.execute(
            f"ATTACH {_quote_literal(source)} AS source_db (READ_ONLY)"
        )
        try:
            for schema in sorted({plan.schema for plan in plans}):
                if schema != "main":
                    connection.execute(f"CREATE SCHEMA {_quote_ident(schema)}")
            for plan in plans:
                parameters = [cutoff_text] * len(plan.temporal_columns)
                source_name = _qualified(
                    plan.schema,
                    plan.name,
                    database="source_db",
                )
                target_name = _qualified(plan.schema, plan.name)
                connection.execute(
                    f"CREATE TABLE {target_name} AS "
                    f"SELECT * FROM {source_name} WHERE {_predicate(plan)}",
                    parameters,
                )
                target_rows = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {target_name}"
                    ).fetchone()[0]
                )
                receipts.append(
                    TableCopyReceipt(
                        name=plan.qualified_name,
                        source_kind=plan.source_kind,
                        temporal_columns=tuple(
                            column for column, _data_type in plan.temporal_columns
                        ),
                        intraday_time_columns=plan.intraday_time_columns,
                        marker_exceptions=plan.marker_exceptions,
                        source_rows=plan.source_rows,
                        target_rows=target_rows,
                        maxima=_maxima(connection, plan),
                    )
                )
            connection.execute("DETACH source_db")
        finally:
            connection.close()
        temporary.chmod(0o444)
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise

    receipt = FilteredDuckDBReceipt(
        source_path=source,
        target_path=target,
        as_of=str(as_of),
        cutoff_timestamp=cutoff_text,
        tables=tuple(receipts),
        target_sha256=_sha256_file(target),
    )
    audit = audit_filtered_duckdb(receipt)
    if audit.status != "valid":
        target.chmod(0o600)
        target.unlink(missing_ok=True)
        raise ValueError("filtered DuckDB failed post-build audit: " + ",".join(audit.issues))
    return receipt
