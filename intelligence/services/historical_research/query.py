"""Typed, bounded historical research over canonical fact tables.

The engine returns complete artifacts. Preview limits belong to presentation;
they never reduce the population used for a calculation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
from threading import Event, Thread
import time
from typing import Any

import duckdb

from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.historical_research.features import (
    FEATURES,
    FEATURE_VERSION,
    compute_features,
)

SCHEMA_VERSION = "historical-research-v1"
MAX_INPUT_ROWS = 100_000
MAX_WINDOWS = 5_000
OPERATIONS = ("inspect_history", "compute_history", "find_analogues", "compare_cases")
_ENTITY_FIELDS = {
    "sector": ("fact_sector_daily", "sector_ts_code", "sector_name"),
    "stock": ("fact_stock_daily", "stock_ts_code", "stock_name"),
}
_STOCK_FEATURES = {"return_pct", "amount_ratio", "market_relative_return_pct"}


class HistoryQueryError(ValueError):
    """Invalid or unsupported historical research request."""


class HistoryQueryCancelled(HistoryQueryError):
    pass


class HistoryQueryTimedOut(HistoryQueryError):
    pass


def _json(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _json(value), sort_keys=True, ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def _date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise HistoryQueryError(f"{field} requires ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HistoryQueryError(f"{field} requires ISO date") from exc
    if parsed.isoformat() != value:
        raise HistoryQueryError(f"{field} requires YYYY-MM-DD")
    return parsed


def _integer(value: object, field: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise HistoryQueryError(f"{field} must be {low}..{high}")
    return value


@dataclass(frozen=True)
class HistoryQuerySpec:
    operation: str
    start: date
    end: date
    entity_kind: str = "sector"
    entity_codes: tuple[str, ...] = ()
    query: str = ""
    features: tuple[str, ...] = ("return_pct",)
    search_start: date | None = None
    search_end: date | None = None
    window_days: int = 20
    step_days: int = 5
    match_mode: str = "full_path"
    condition: dict[str, Any] | None = None
    outcome: dict[str, Any] | None = None
    preview_limit: int = 25
    reference_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _json(asdict(self))

    @classmethod
    def from_arguments(cls, arguments: Mapping[str, object]) -> HistoryQuerySpec:
        if not isinstance(arguments, Mapping) or set(arguments) - set(
            cls.__dataclass_fields__
        ):
            raise HistoryQueryError("unknown historical query argument")
        operation = arguments.get("operation")
        if operation not in OPERATIONS:
            raise HistoryQueryError("unsupported operation")
        entity_kind = arguments.get("entity_kind", "sector")
        if not isinstance(entity_kind, str) or entity_kind not in _ENTITY_FIELDS:
            raise HistoryQueryError("entity_kind must be sector or stock")
        start, end = (
            _date(arguments.get("start"), "start"),
            _date(arguments.get("end"), "end"),
        )
        if end < start or (end - start).days > 1095:
            raise HistoryQueryError("invalid window; maximum 1095 calendar days")
        codes = arguments.get("entity_codes", [])
        if (
            not isinstance(codes, (list, tuple))
            or len(codes) > 20
            or any(
                not isinstance(c, str) or not c.strip() or len(c) > 80 for c in codes
            )
        ):
            raise HistoryQueryError("entity_codes requires at most 20 exact codes")
        query = arguments.get("query", "")
        if not isinstance(query, str) or len(query) > 200:
            raise HistoryQueryError("query must be at most 200 characters")
        features = arguments.get("features", ["return_pct"])
        if (
            not isinstance(features, (list, tuple))
            or not features
            or any(
                not isinstance(name, str) or name not in FEATURES for name in features
            )
        ):
            raise HistoryQueryError("unsupported_definition: unknown built-in feature")
        if operation != "inspect_history" and not codes:
            raise HistoryQueryError("exact entity_codes required for computation")
        search_start = (
            _date(arguments["search_start"], "search_start")
            if arguments.get("search_start") is not None
            else None
        )
        search_end = (
            _date(arguments["search_end"], "search_end")
            if arguments.get("search_end") is not None
            else None
        )
        if (search_start is None) != (search_end is None):
            raise HistoryQueryError(
                "search_start and search_end must be supplied together"
            )
        if (
            search_start is not None
            and search_end is not None
            and (
                search_end < search_start
                or (max(end, search_end) - min(start, search_start)).days > 1095
            )
        ):
            raise HistoryQueryError("invalid search range; maximum 1095 calendar days")
        if operation in {"find_analogues", "compare_cases"} and search_start is None:
            raise HistoryQueryError(
                "explicit search_start/search_end universe required"
            )
        mode = arguments.get("match_mode", "full_path")
        if not isinstance(mode, str) or mode not in {"full_path", "trigger_only"}:
            raise HistoryQueryError("unsupported match_mode")
        reference = arguments.get("reference_code")
        if reference is None and len(codes) == 1:
            reference = codes[0]
        if operation == "find_analogues" and reference not in codes:
            raise HistoryQueryError("reference_code must identify one declared entity")
        condition = arguments.get("condition")
        outcome = arguments.get("outcome")
        if condition is not None:
            if (
                not isinstance(condition, dict)
                or set(condition) != {"feature", "op", "value"}
                or not isinstance(condition.get("feature"), str)
                or condition.get("feature") not in FEATURES
                or not isinstance(condition.get("op"), str)
                or condition.get("op") not in {"gte", "lte"}
                or type(condition.get("value")) not in {int, float}
                or not math.isfinite(condition["value"])
            ):
                raise HistoryQueryError(
                    "unsupported_definition: condition requires one built-in feature, gte/lte, and numeric value"
                )
        if outcome is not None:
            if (
                not isinstance(outcome, dict)
                or set(outcome) != {"horizon_days", "threshold_pct"}
                or type(outcome.get("threshold_pct")) not in {int, float}
                or not math.isfinite(outcome["threshold_pct"])
            ):
                raise HistoryQueryError(
                    "unsupported_definition: outcome requires horizon_days and threshold_pct"
                )
            _integer(outcome["horizon_days"], "horizon_days", 1, 60)
        if operation == "compare_cases" and (condition is None or outcome is None):
            raise HistoryQueryError("condition and outcome required for comparison")
        selected_features = set(features) | (
            {condition["feature"]} if condition else set()
        )
        if entity_kind == "stock" and selected_features - _STOCK_FEATURES:
            raise HistoryQueryError(
                "unsupported_definition: stock supports only return_pct, amount_ratio, market_relative_return_pct"
            )
        return cls(
            operation=str(operation),
            start=start,
            end=end,
            entity_kind=entity_kind,
            entity_codes=tuple(dict.fromkeys(codes)),
            query=query,
            features=tuple(dict.fromkeys(features)),
            search_start=search_start,
            search_end=search_end,
            window_days=_integer(
                arguments.get("window_days", 20), "window_days", 2, 60
            ),
            step_days=_integer(arguments.get("step_days", 5), "step_days", 1, 60),
            match_mode=str(mode),
            condition=condition,
            outcome=outcome,
            reference_code=reference,
            preview_limit=_integer(
                arguments.get("preview_limit", 25), "preview_limit", 1, 100
            ),
        )


def history_query_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["operation", "start", "end"],
        "properties": {
            "operation": {"type": "string", "enum": list(OPERATIONS)},
            "entity_kind": {
                "type": "string",
                "enum": ["sector", "stock"],
                "default": "sector",
                "description": "Exact canonical entity family. Stock supports return_pct, amount_ratio, market_relative_return_pct; sector-only definitions fail explicitly.",
            },
            "start": {
                "type": "string",
                "format": "date",
                "description": "Inclusive YYYY-MM-DD. Inspect/compute use start..end; analogues use it as the reference window. Combined reference/search span is at most 1095 calendar days.",
            },
            "end": {
                "type": "string",
                "format": "date",
                "description": "Inclusive YYYY-MM-DD, no later than information cutoff. An analogue reference must contain exactly window_days observed canonical trading dates.",
            },
            "entity_codes": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
                "description": "Exact stock or sector codes, never joined by name; explicit fixed universe for computation. Omit only for inspect catalog discovery.",
            },
            "query": {"type": "string", "maxLength": 200},
            "features": {
                "type": "array",
                "items": {"type": "string", "enum": list(FEATURES)},
                "minItems": 1,
            },
            "preview_limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Presentation rows only; complete rows and calculation denominators are retained.",
            },
            "search_start": {
                "type": "string",
                "format": "date",
                "description": "Inclusive start of explicit analogue/comparison universe; supply with search_end. First candidate starts here on the observed trading calendar and requires a complete window_days span.",
            },
            "search_end": {
                "type": "string",
                "format": "date",
                "description": "Inclusive candidate feature cutoff, not outcome cutoff. Candidate windows remain inside search_start..search_end; comparison outcomes may extend only to information cutoff.",
            },
            "reference_code": {
                "type": "string",
                "description": "Exact reference entity, required when analogue universe contains multiple codes",
            },
            "window_days": {
                "type": "integer",
                "minimum": 2,
                "maximum": 60,
                "description": "Length in observed trading dates from the union of canonical stock and market facts, independent of entity data holes; missing entity values stay unknown. No partial leading windows.",
            },
            "step_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 60,
                "description": "Stride in the same observed trading calendar after the first complete window; not calendar days. Overlapping windows are overlap_clusters, not independent samples.",
            },
            "match_mode": {
                "type": "string",
                "enum": ["full_path", "trigger_only"],
                "description": "full_path permits retrospective full-window feature discovery. trigger_only uses only each window through its endpoint; neither mode ranks by later outcomes or certifies a method.",
            },
            "condition": {
                "type": "object",
                "additionalProperties": False,
                "required": ["feature", "op", "value"],
                "properties": {
                    "feature": {"type": "string", "enum": list(FEATURES)},
                    "op": {"type": "string", "enum": ["gte", "lte"]},
                    "value": {"type": "number"},
                },
            },
            "outcome": {
                "type": "object",
                "additionalProperties": False,
                "required": ["horizon_days", "threshold_pct"],
                "properties": {
                    "horizon_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 60,
                        "description": "Next N observed trading dates strictly after feature-window end. Incomplete calendar before cutoff is immature; missing entity returns on observed dates are missing_outcome.",
                    },
                    "threshold_pct": {"type": "number"},
                },
            },
        },
    }


_FIELDS = {
    "fact_sector_daily": (
        "trade_date",
        "sector_ts_code",
        "sector_name",
        "pct_chg",
        "amount",
        "diff_ratio",
        "source",
        "updated_at",
        "sector_universe_snapshot_id",
    ),
    "fact_market_daily": (
        "trade_date",
        "total_amount",
        "advancers",
        "limit_up",
        "limit_down",
        "sh_index_pct_chg",
        "sh_index_close",
        "market_stage",
        "volume_state",
        "concentration_state",
        "source",
        "updated_at",
    ),
    "fact_sector_stock_daily": (
        "trade_date",
        "sector_ts_code",
        "stock_ts_code",
        "stock_name",
        "price",
        "pct_chg",
        "amount",
        "float_mcap_yi",
        "role_tags_json",
        "source",
        "updated_at",
        "sector_universe_snapshot_id",
    ),
    "fact_stock_daily": (
        "trade_date",
        "stock_ts_code",
        "stock_name",
        "close",
        "pct_chg",
        "amount",
        "source",
        "updated_at",
    ),
    "fact_theme_limit_heat_daily": (
        "trade_date",
        "sector_ts_code",
        "dimension",
        "scope",
        "limit_up_count",
        "total_count",
        "source",
        "updated_at",
    ),
    "fact_event_daily": (
        "event_date",
        "event_id",
        "title",
        "content",
        "sectors",
        "source",
        "updated_at",
    ),
}


class _Reader:
    def __init__(self, con: Any, check: Callable[[], None]) -> None:
        self.con, self.check = con, check
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.gaps: list[str] = []
        self.input_rows = 0
        self.calendars: list[dict[str, Any]] = []

    def calendar(
        self, start: date, end: date, market: list[dict[str, Any]]
    ) -> list[date]:
        """Calendar is independent of the requested sector and market-field holes."""
        self.check()
        market_days = {r["trade_date"] for r in market}
        try:
            stock_days = [
                r[0]
                for r in self.con.execute(
                    "SELECT DISTINCT trade_date FROM fact_stock_daily WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
                    [start, end],
                ).fetchall()
            ]
        except duckdb.CatalogException:
            stock_days = []
            self.gaps.append("stock_calendar_unavailable:calendar_uses_market_dates")
        self.check()
        days = sorted(market_days | set(stock_days))
        self.calendars.append(
            {
                "table": "fact_stock_daily",
                "projection": "DISTINCT trade_date",
                "start": start,
                "end": end,
                "stock_dates": stock_days,
                "market_dates": sorted(market_days),
            }
        )
        return days

    def validate_calendar(
        self,
        days: list[date],
        entity_rows: list[dict[str, Any]],
        *,
        strict: bool = True,
    ) -> None:
        """Never omit known entity dates just because both calendar sources lack them."""
        missing = sorted({row["trade_date"] for row in entity_rows} - set(days))
        if missing:
            gap = "calendar_gap:entity_dates_not_corroborated:" + ",".join(
                day.isoformat() for day in missing
            )
            self.gaps.append(gap)
            if strict:
                raise HistoryQueryError(gap)

    def read(
        self,
        table: str,
        start: date,
        end: date,
        *,
        codes: tuple[str, ...] = (),
        code_field: str = "sector_ts_code",
    ) -> list[dict[str, Any]]:
        self.check()
        try:
            schema = {
                row[0] for row in self.con.execute(f'DESCRIBE "{table}"').fetchall()
            }
        except duckdb.CatalogException:
            self.gaps.append(f"missing_table:{table}")
            self.tables[table] = []
            return []
        fields = [field for field in _FIELDS[table] if field in schema]
        time_field = "event_date" if table == "fact_event_daily" else "trade_date"
        if time_field not in fields or (codes and code_field not in fields):
            self.gaps.append(f"missing_identity_fields:{table}")
            self.tables[table] = []
            return []
        sql = f'SELECT {",".join(fields)} FROM "{table}" WHERE {time_field} BETWEEN ? AND ?'
        params: list[Any] = [start, end]
        if codes:
            sql += f" AND {code_field} IN (SELECT unnest(?))"
            params.append(list(codes))
        sql += f" ORDER BY {time_field}"
        for field in (
            "sector_ts_code",
            "stock_ts_code",
            "event_id",
            "dimension",
            "scope",
        ):
            if field in fields:
                sql += "," + field
        sql += " LIMIT ?"
        params.append(MAX_INPUT_ROWS - self.input_rows + 1)
        cursor = self.con.execute(sql, params)
        rows = []
        while batch := cursor.fetchmany(1000):
            self.check()
            self.input_rows += len(batch)
            if self.input_rows > MAX_INPUT_ROWS:
                raise HistoryQueryError(
                    "input row limit exceeded; narrow the explicit scope"
                )
            for row in batch:
                data = dict(zip(fields, row))
                rows.append({field: data.get(field) for field in _FIELDS[table]})
        self.tables.setdefault(table, []).extend(rows)
        return rows

    def coverage(self) -> dict[str, Any]:
        return {
            table: {
                "rows": len(rows),
                "fields": {
                    field: {
                        "nonnull": sum(r[field] is not None for r in rows),
                        "missing": sum(r[field] is None for r in rows),
                    }
                    for field in _FIELDS[table]
                },
            }
            for table, rows in self.tables.items()
        }


def _event_matches(row: dict[str, Any], code: str) -> bool:
    try:
        sectors = json.loads(row.get("sectors") or "[]")
    except (TypeError, ValueError):
        return False
    return isinstance(sectors, list) and any(
        isinstance(item, dict) and item.get("ts_code") == code for item in sectors
    )


class HistoryQuery:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser()

    def run(
        self,
        spec: HistoryQuerySpec,
        *,
        information_cutoff: InformationCutoff,
        deadline: ResearchDeadline,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        cancelled = is_cancelled or (lambda: False)
        expires = time.monotonic() + deadline.stage_timeout(30.0)

        def check() -> None:
            if cancelled():
                raise HistoryQueryCancelled("history query cancelled")
            if time.monotonic() >= expires:
                raise HistoryQueryTimedOut("history query deadline exhausted")

        check()
        spec = HistoryQuerySpec.from_arguments(spec.to_dict())
        if max(spec.end, spec.search_end or spec.end) > information_cutoff.as_of_date:
            raise HistoryQueryError("window exceeds information cutoff")
        if not self.db_path.is_file():
            raise HistoryQueryError("database missing; never creates a database")
        stop = Event()
        con = duckdb.connect(str(self.db_path), read_only=True)

        def monitor() -> None:
            while not stop.wait(0.01):
                try:
                    check()
                except HistoryQueryError:
                    con.interrupt()
                    return

        thread = Thread(target=monitor, name="history-query-deadline", daemon=True)
        thread.start()
        reader = _Reader(con, check)
        try:
            con.execute("BEGIN TRANSACTION")
            rows, extra = self._execute(spec, reader, check, information_cutoff)
            check()
            con.execute("COMMIT")
        except duckdb.Error as exc:
            check()
            raise HistoryQueryError(
                f"read-only history query failed: {type(exc).__name__}"
            ) from exc
        finally:
            stop.set()
            thread.join(timeout=0.2)
            con.close()
        coverage = reader.coverage()
        coverage.update(extra.pop("coverage", {}))
        fingerprints = {
            name: _hash(values) for name, values in sorted(reader.tables.items())
        }
        fingerprints["calendar_inputs"] = _hash(reader.calendars)
        selected_features = tuple(
            dict.fromkeys(
                (
                    *spec.features,
                    *((spec.condition["feature"],) if spec.condition else ()),
                    *(("return_pct",) if spec.operation == "compare_cases" else ()),
                )
            )
        )
        definitions = {
            name: {
                **FEATURES[name],
                "version": FEATURE_VERSION,
                "entity_kind": spec.entity_kind,
            }
            for name in selected_features
        }
        coverage["calendar"] = {
            "basis": "union of canonical stock and market fact dates; not inferred from selected sector",
            "reads": reader.calendars,
        }
        # Null features remain visible even when their rows fall outside preview.
        for row in [*rows, extra.get("reference", {})]:
            for name, detail in row.get("feature_coverage", {}).items():
                if detail["status"] != "complete":
                    reader.gaps.append(f"feature:{name}:{detail['status']}")
            if row.get("comparison_state") in {
                "missing_feature",
                "missing_outcome",
                "immature",
            }:
                reader.gaps.append(f"comparison:{row['comparison_state']}")
        result = _json(
            {
                "schema_version": SCHEMA_VERSION,
                "query_id": _hash(
                    [spec.to_dict(), fingerprints, SCHEMA_VERSION, definitions]
                ),
                "status": "research_only",
                "research_only": True,
                "decision_eligible": False,
                "promotion_eligible": False,
                "pit_grade": "hindsight_reconstruction",
                "spec": spec.to_dict(),
                "entity_kind": spec.entity_kind,
                "rows": rows,
                "preview": rows[: spec.preview_limit],
                "total_matched": len(rows),
                "returned_count": min(len(rows), spec.preview_limit),
                "truncated": len(rows) > spec.preview_limit,
                "coverage": coverage,
                "input_fingerprint": _hash(fingerprints),
                "inputs": reader.tables,
                "calendar_inputs": reader.calendars,
                "source_refs": [
                    {
                        "table": table,
                        "input_fingerprint": fingerprints[table],
                        "row_count": len(values),
                        "snapshot_ids": sorted(
                            {
                                r["sector_universe_snapshot_id"]
                                for r in values
                                if r.get("sector_universe_snapshot_id")
                            }
                        ),
                    }
                    for table, values in reader.tables.items()
                ],
                "definition_refs": [
                    SCHEMA_VERSION,
                    FEATURE_VERSION,
                    *(f"{name}@{FEATURE_VERSION}" for name in selected_features),
                ],
                "feature_definitions": definitions,
                "gaps": list(dict.fromkeys(reader.gaps)),
                **extra,
            }
        )
        check()
        return result

    def _execute(
        self,
        spec: HistoryQuerySpec,
        reader: _Reader,
        check: Callable[[], None],
        cutoff: InformationCutoff,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if spec.operation in {"find_analogues", "compare_cases"}:
            return self._windows(spec, reader, check, cutoff)
        table, code_field, _ = _ENTITY_FIELDS[spec.entity_kind]
        source_rows = reader.read(
            table, spec.start, spec.end, codes=spec.entity_codes, code_field=code_field
        )
        if not spec.entity_codes:
            return self._catalog(source_rows, spec.query, spec.entity_kind), {}
        market = reader.read("fact_market_daily", spec.start, spec.end)
        days = reader.calendar(spec.start, spec.end, market)
        reader.validate_calendar(
            days, source_rows, strict=spec.operation != "inspect_history"
        )
        if not days:
            reader.gaps.append("trading_calendar_unavailable")
        members = (
            reader.read(
                "fact_sector_stock_daily", spec.start, spec.end, codes=spec.entity_codes
            )
            if spec.entity_kind == "sector"
            and (
                spec.operation == "inspect_history"
                or any(
                    name in {"advancer_share", "first_surge_lag"}
                    for name in spec.features
                )
            )
            else []
        )
        heat = (
            reader.read(
                "fact_theme_limit_heat_daily",
                spec.start,
                spec.end,
                codes=spec.entity_codes,
            )
            if spec.entity_kind == "sector"
            and (
                spec.operation == "inspect_history" or "limit_up_share" in spec.features
            )
            else []
        )
        if spec.operation == "compute_history":
            rows = []
            for code in spec.entity_codes:
                check()
                values, coverage = compute_features(
                    spec.features,
                    days,
                    [r for r in source_rows if r[code_field] == code],
                    members=[r for r in members if r["sector_ts_code"] == code],
                    heat=[r for r in heat if r["sector_ts_code"] == code],
                    market=market,
                )
                rows.append(
                    {
                        "entity_code": code,
                        "entity_kind": spec.entity_kind,
                        "start": spec.start,
                        "end": spec.end,
                        "features": values,
                        "feature_coverage": coverage,
                    }
                )
            return rows, {}
        if spec.operation != "inspect_history":
            raise HistoryQueryError(
                "unsupported_definition: operation is not implemented"
            )
        if spec.entity_kind == "stock":
            return self._inspect_stock(spec, source_rows, market, reader, check)
        stocks = (
            reader.read(
                "fact_stock_daily",
                spec.start,
                spec.end,
                codes=tuple(
                    sorted({r["stock_ts_code"] for r in members if r["stock_ts_code"]})
                ),
                code_field="stock_ts_code",
            )
            if members
            else []
        )
        events = reader.read("fact_event_daily", spec.start, spec.end)
        stock_groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        market_groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in stocks:
            stock_groups[(row["trade_date"], row["stock_ts_code"])].append(row)
        for row in market:
            market_groups[row["trade_date"]].append(row)
        market_map = {
            day: rows[0] if len(rows) == 1 else None
            for day, rows in market_groups.items()
        }
        rows = []
        joined = 0
        ambiguous = 0
        for sector in source_rows:
            check()
            matching_members = []
            for member in members:
                if (
                    member["trade_date"] == sector["trade_date"]
                    and member["sector_ts_code"] == sector["sector_ts_code"]
                ):
                    stock_candidates = stock_groups.get(
                        (member["trade_date"], member["stock_ts_code"]), []
                    )
                    stock = stock_candidates[0] if len(stock_candidates) == 1 else None
                    ambiguous += len(stock_candidates) > 1
                    joined += stock is not None
                    matching_members.append({**member, "stock_daily": stock})
            matching_events = [
                {
                    **event,
                    "publication_time_status": "unknown",
                    "causal_status": "unverified_editorial_calendar",
                }
                for event in events
                if event["event_date"] == sector["trade_date"]
                and _event_matches(event, sector["sector_ts_code"])
            ]
            rows.append(
                {
                    "entity_code": sector["sector_ts_code"],
                    "entity_kind": "sector",
                    "trade_date": sector["trade_date"],
                    "sector": sector,
                    "members": matching_members,
                    "market": market_map.get(sector["trade_date"]),
                    "events": matching_events,
                    "heat": [
                        r
                        for r in heat
                        if r["trade_date"] == sector["trade_date"]
                        and r["sector_ts_code"] == sector["sector_ts_code"]
                    ],
                }
            )
        return rows, {
            "coverage": {
                "member_stock_join": {
                    "expected": len(members),
                    "matched": joined,
                    "missing": len(members) - joined,
                    "ambiguous": ambiguous,
                }
            },
            "event_time_status": "reliable_publication_time_unknown",
        }

    @staticmethod
    def _inspect_stock(
        spec: HistoryQuerySpec,
        source_rows: list[dict[str, Any]],
        market: list[dict[str, Any]],
        reader: _Reader,
        check: Callable[[], None],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        memberships = reader.read(
            "fact_sector_stock_daily",
            spec.start,
            spec.end,
            codes=spec.entity_codes,
            code_field="stock_ts_code",
        )
        market_groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in market:
            market_groups[row["trade_date"]].append(row)
        rows = []
        for stock in source_rows:
            check()
            market_candidates = market_groups[stock["trade_date"]]
            rows.append(
                {
                    "entity_kind": "stock",
                    "entity_code": stock["stock_ts_code"],
                    "trade_date": stock["trade_date"],
                    "stock": stock,
                    "market": market_candidates[0]
                    if len(market_candidates) == 1
                    else None,
                    "sector_memberships": [
                        r
                        for r in memberships
                        if r["stock_ts_code"] == stock["stock_ts_code"]
                        and r["trade_date"] == stock["trade_date"]
                    ],
                    "events": [],
                }
            )
        reader.gaps.append(
            "stock_event_link_not_available:sector_membership_is_not_company_event_evidence"
        )
        return rows, {"event_time_status": "stock_event_link_not_available"}

    def _windows(
        self,
        spec: HistoryQuerySpec,
        reader: _Reader,
        check: Callable[[], None],
        cutoff: InformationCutoff,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        assert spec.search_start is not None and spec.search_end is not None
        start, end = min(spec.start, spec.search_start), max(spec.end, spec.search_end)
        names = tuple(
            dict.fromkeys(
                (
                    *spec.features,
                    *((spec.condition["feature"],) if spec.condition else ()),
                )
            )
        )
        table, code_field, _ = _ENTITY_FIELDS[spec.entity_kind]
        entity_rows = reader.read(
            table, start, end, codes=spec.entity_codes, code_field=code_field
        )
        market = reader.read("fact_market_daily", start, end)
        members = (
            reader.read("fact_sector_stock_daily", start, end, codes=spec.entity_codes)
            if any(name in {"advancer_share", "first_surge_lag"} for name in names)
            else []
        )
        heat = (
            reader.read(
                "fact_theme_limit_heat_daily", start, end, codes=spec.entity_codes
            )
            if "limit_up_share" in names
            else []
        )
        days = reader.calendar(start, end, market)
        reader.validate_calendar(days, entity_rows)
        if not days:
            reader.gaps.append("trading_calendar_unavailable")
        search_days = [d for d in days if spec.search_start <= d <= spec.search_end]

        def feature_row(code: str, selected_days: list[date]) -> dict[str, Any]:
            chosen = set(selected_days)
            values, coverage = compute_features(
                names,
                selected_days,
                [
                    r
                    for r in entity_rows
                    if r[code_field] == code and r["trade_date"] in chosen
                ],
                members=[
                    r
                    for r in members
                    if r["sector_ts_code"] == code and r["trade_date"] in chosen
                ],
                heat=[
                    r
                    for r in heat
                    if r["sector_ts_code"] == code and r["trade_date"] in chosen
                ],
                market=[r for r in market if r["trade_date"] in chosen],
            )
            return {
                "entity_code": code,
                "entity_kind": spec.entity_kind,
                "start": selected_days[0],
                "end": selected_days[-1],
                "feature_cutoff": selected_days[-1],
                "features": values,
                "feature_coverage": coverage,
                "sample_id": _hash(
                    [spec.entity_kind, code, selected_days, FEATURE_VERSION]
                ),
            }

        candidates = []
        for code in spec.entity_codes:
            for i in range(spec.window_days - 1, len(search_days), spec.step_days):
                check()
                if len(candidates) >= MAX_WINDOWS:
                    raise HistoryQueryError("window scan limit exceeded")
                candidates.append(
                    feature_row(code, search_days[i - spec.window_days + 1 : i + 1])
                )
        if spec.operation == "compare_cases":
            return self._compare(spec, reader, check, cutoff, candidates)
        reference_days = [d for d in days if spec.start <= d <= spec.end]
        if len(reference_days) != spec.window_days:
            raise HistoryQueryError(
                "reference window must contain window_days canonical trading dates"
            )
        assert spec.reference_code is not None
        reference = feature_row(spec.reference_code, reference_days)
        rows, excluded = [], []
        for candidate in candidates:
            check()
            if (
                candidate["entity_code"] == spec.reference_code
                and candidate["start"] <= spec.end
                and candidate["end"] >= spec.start
            ):
                excluded.append(
                    {
                        "sample_id": candidate["sample_id"],
                        "reason": "overlaps_reference",
                    }
                )
                continue
            shared = [
                name
                for name in spec.features
                if reference["features"][name] is not None
                and candidate["features"][name] is not None
            ]
            if not shared:
                excluded.append(
                    {
                        "sample_id": candidate["sample_id"],
                        "reason": "no_comparable_features",
                    }
                )
                continue
            differences = {
                name: candidate["features"][name] - reference["features"][name]
                for name in shared
            }
            distance = sum(
                abs(differences[name]) / max(abs(reference["features"][name]), 1.0)
                for name in shared
            ) / len(shared)
            distance += 1 - len(shared) / len(spec.features)
            rows.append(
                {
                    **candidate,
                    "distance": distance,
                    "feature_differences": differences,
                    "shared_features": shared,
                    "missing_features": [
                        name for name in spec.features if name not in shared
                    ],
                }
            )
        rows.sort(key=lambda r: (r["distance"], r["entity_code"], r["start"]))
        return rows, {
            "reference": reference,
            "excluded_candidates": excluded,
            "matching_use": "retrospective_full_path_discovery"
            if spec.match_mode == "full_path"
            else "trigger_time_features_only_research",
            "distance_definition": "mean absolute feature difference / max(abs(reference),1), plus missing-dimension share; no fitted transform or forward outcomes",
            "universe": {
                "entity_kind": spec.entity_kind,
                "entity_codes": spec.entity_codes,
                "start": spec.search_start,
                "end": spec.search_end,
                "window_days": spec.window_days,
                "step_days": spec.step_days,
                "enumerated": len(candidates),
            },
        }

    @staticmethod
    def _compare(
        spec: HistoryQuerySpec,
        reader: _Reader,
        check: Callable[[], None],
        cutoff: InformationCutoff,
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        assert (
            spec.condition is not None
            and spec.outcome is not None
            and spec.search_end is not None
        )
        condition, outcome = spec.condition, spec.outcome
        table, code_field, _ = _ENTITY_FIELDS[spec.entity_kind]
        frozen = []
        for row in candidates:
            value = row["features"][condition["feature"]]
            x = (
                None
                if value is None
                else (
                    value >= condition["value"]
                    if condition["op"] == "gte"
                    else value <= condition["value"]
                )
            )
            frozen.append({**row, "x": x})
        # Freeze the entire declared population and all X labels before any Y
        # calculation. Preview/ranking cannot remove negative or unknown cases.
        selection_fingerprint = _hash([frozen, condition, FEATURE_VERSION])
        horizon = outcome["horizon_days"]
        future_end = min(
            cutoff.as_of_date, spec.search_end + timedelta(days=3 * horizon + 14)
        )
        future_start = min(
            (r["end"] for r in frozen), default=spec.search_end
        ) + timedelta(days=1)
        future_market, future_entities = [], []
        if future_start <= future_end:
            future_market = reader.read("fact_market_daily", future_start, future_end)
            future_entities = reader.read(
                table,
                future_start,
                future_end,
                codes=spec.entity_codes,
                code_field=code_field,
            )
        future_days = (
            reader.calendar(future_start, future_end, future_market)
            if future_start <= future_end
            else []
        )
        reader.validate_calendar(future_days, future_entities)
        cells = {
            "x_true_y_true": 0,
            "x_true_y_false": 0,
            "x_false_y_true": 0,
            "x_false_y_false": 0,
        }
        missing, immature = 0, 0
        rows = []
        for candidate in frozen:
            check()
            next_days = [d for d in future_days if d > candidate["end"]][:horizon]
            row = {
                **candidate,
                "y": None,
                "forward_return_pct": None,
                "outcome_end": next_days[-1] if next_days else None,
            }
            if candidate["x"] is None:
                row["comparison_state"] = "missing_feature"
                missing += 1
            elif len(next_days) < horizon:
                row["comparison_state"] = "immature"
                immature += 1
            else:
                next_set = set(next_days)
                values, coverage = compute_features(
                    ("return_pct",),
                    next_days,
                    [
                        r
                        for r in future_entities
                        if r[code_field] == candidate["entity_code"]
                        and r["trade_date"] in next_set
                    ],
                )
                value = values["return_pct"]
                row["outcome_coverage"] = coverage["return_pct"]
                if value is None:
                    row["comparison_state"] = "missing_outcome"
                    missing += 1
                else:
                    y = value >= outcome["threshold_pct"]
                    row.update(
                        y=y, forward_return_pct=value, comparison_state="observed"
                    )
                    cells[f"x_{str(candidate['x']).lower()}_y_{str(y).lower()}"] += 1
            rows.append(row)
        # Intersecting feature/outcome intervals share a conservative overlap
        # cluster even across entities. This is NOT an independent-sample count.
        cluster, cluster_end = 0, None
        for row in sorted(rows, key=lambda r: (r["start"], r["end"], r["entity_code"])):
            if cluster_end is None or row["start"] > cluster_end:
                cluster += 1
            cluster_end = max(
                cluster_end or row["end"], row.get("outcome_end") or row["end"]
            )
            row["overlap_cluster"] = f"overlap-{cluster}"
        return rows, {
            "selection_fingerprint": selection_fingerprint,
            "execution_phases": ["features_read", "selection_frozen", "outcomes_read"],
            "comparison": {
                "four_cells": cells,
                "missing": missing,
                "immature": immature,
                "enumerated": len(rows),
                "overlap_clusters": cluster,
                "independence_status": "not_established",
                "certification_eligible": False,
            },
            "universe": {
                "entity_kind": spec.entity_kind,
                "entity_codes": spec.entity_codes,
                "start": spec.search_start,
                "end": spec.search_end,
                "window_days": spec.window_days,
                "step_days": spec.step_days,
                "unit": "each fixed-length observed-trading-calendar window at declared stride per exact code",
                "excluded_prefix_days": spec.window_days - 1,
            },
            "outcome_definition": {
                "metric": f"compounded_{spec.entity_kind}_daily_pct",
                **outcome,
                "cutoff": cutoff.as_of_date,
            },
        }

    @staticmethod
    def _catalog(
        source_rows: list[dict[str, Any]], query: str, entity_kind: str
    ) -> list[dict[str, Any]]:
        _, code_field, name_field = _ENTITY_FIELDS[entity_kind]
        rows: list[dict[str, Any]] = []
        for code in sorted(
            {r[code_field] for r in source_rows if r[code_field] is not None}
        ):
            found = [
                r
                for r in source_rows
                if r[code_field] == code
                and (not query or query in (r[name_field] or ""))
            ]
            if found:
                rows.append(
                    {
                        "entity_code": code,
                        "entity_kind": entity_kind,
                        "entity_name": found[-1][name_field],
                        "names": sorted(
                            {r[name_field] for r in found if r[name_field] is not None}
                        ),
                        "first_date": found[0]["trade_date"],
                        "last_date": found[-1]["trade_date"],
                        "dates": len(found),
                    }
                )
        return rows
