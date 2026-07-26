"""Typed, read-only semantic queries over the canonical finance DuckDB.

The model chooses semantic datasets, fields, filters, and ordering.  This module
alone knows physical tables and columns, injects the immutable information
cutoff, binds every value, enforces resource caps, and mints evidence lineage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from threading import Event, Thread
import time
from typing import Any, Literal

from intelligence.services import agent_research
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)


class FinanceQueryError(RuntimeError):
    """Base class for typed structured-query failures."""


class FinanceQueryValidationError(FinanceQueryError, ValueError):
    """The semantic query is outside the registered production surface."""


class FinanceQueryExecutionError(FinanceQueryError):
    """DuckDB could not execute an otherwise valid semantic query."""


class FinanceQueryLimitExceeded(FinanceQueryError):
    """The bounded result exceeded a hard output limit."""


class FinanceQueryCancelled(FinanceQueryError):
    """The caller cancelled before the result could be published."""


class FinanceQueryTimedOut(FinanceQueryError, TimeoutError):
    """The root or statement deadline interrupted execution."""


FilterOperator = Literal[
    "eq",
    "ne",
    "lt",
    "lte",
    "gt",
    "gte",
    "in",
    "contains",
]
OrderDirection = Literal["asc", "desc"]
_FILTER_OPERATORS = frozenset(
    {"eq", "ne", "lt", "lte", "gt", "gte", "in", "contains"}
)
_ORDER_DIRECTIONS = frozenset({"asc", "desc"})
_TOP_LEVEL_KEYS = frozenset(
    {
        "dataset",
        "metrics",
        "dimensions",
        "filters",
        "time_range",
        "group_by",
        "order_by",
        "limit",
    }
)


@dataclass(frozen=True)
class QueryFilter:
    field: str
    op: FilterOperator
    value: object


@dataclass(frozen=True)
class TimeRange:
    start: date | None = None
    end: date | None = None


@dataclass(frozen=True)
class Order:
    field: str
    direction: OrderDirection = "asc"


@dataclass(frozen=True)
class FinanceQuerySpec:
    dataset: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    filters: tuple[QueryFilter, ...] = ()
    time_range: TimeRange | None = None
    group_by: tuple[str, ...] = ()
    order_by: tuple[Order, ...] = ()
    limit: int = 50

    @classmethod
    def from_arguments(
        cls,
        arguments: Mapping[str, object],
    ) -> FinanceQuerySpec:
        unknown = set(arguments) - _TOP_LEVEL_KEYS
        if unknown:
            raise FinanceQueryValidationError(
                "unknown query argument: " + ",".join(sorted(unknown))
            )
        dataset = _required_text(arguments.get("dataset"), "dataset")
        metrics = _string_tuple(arguments.get("metrics", ()), "metrics")
        dimensions = _string_tuple(
            arguments.get("dimensions", ()),
            "dimensions",
        )
        if not metrics and not dimensions:
            raise FinanceQueryValidationError(
                "at least one metric or dimension is required"
            )
        filters = _parse_filters(arguments.get("filters", ()))
        time_range = _parse_time_range(arguments.get("time_range"))
        group_by = _string_tuple(arguments.get("group_by", ()), "group_by")
        order_by = _parse_orders(arguments.get("order_by", ()))
        raw_limit = arguments.get("limit", 50)
        if (
            isinstance(raw_limit, bool)
            or not isinstance(raw_limit, int)
            or raw_limit < 1
            or raw_limit > 1000
        ):
            raise FinanceQueryValidationError(
                "limit must be an integer between 1 and 1000"
            )
        return cls(
            dataset=dataset,
            metrics=metrics,
            dimensions=dimensions,
            filters=filters,
            time_range=time_range,
            group_by=group_by,
            order_by=order_by,
            limit=raw_limit,
        )


@dataclass(frozen=True)
class FinanceQueryLimits:
    max_rows: int = 200
    max_bytes: int = 256_000
    timeout: float = 8.0

    def __post_init__(self) -> None:
        if self.max_rows < 1 or self.max_bytes < 1 or self.timeout <= 0:
            raise ValueError("finance query limits must be positive")


@dataclass(frozen=True)
class FinanceQueryAudit:
    dataset: str
    physical_sql: str
    bound_parameters: tuple[object, ...]
    sql_fingerprint: str
    applied_limit: int
    row_count: int
    output_bytes: int
    elapsed_seconds: float


@dataclass(frozen=True)
class FinanceQueryResult:
    rows: tuple[dict[str, object], ...]
    evidence: tuple[agent_research.AgentEvidence, ...]
    observation: str
    served_date: str | None
    audit: FinanceQueryAudit


@dataclass(frozen=True)
class _FieldDefinition:
    column: str
    label: str
    role: Literal["dimension", "metric"]
    aggregate: Literal["avg", "sum", "max", "min"] | None = None
    value_kind: Literal["text", "number", "integer", "boolean", "date"] = "text"


@dataclass(frozen=True)
class _DatasetDefinition:
    table: str
    label: str
    time_field: str | None
    dimensions: Mapping[str, _FieldDefinition]
    metrics: Mapping[str, _FieldDefinition]
    evidence_tier: str = "L4_structured"

    @property
    def fields(self) -> dict[str, _FieldDefinition]:
        return {**self.dimensions, **self.metrics}


def _dimension(
    column: str,
    label: str,
    value_kind: Literal["text", "number", "integer", "boolean", "date"] = "text",
) -> _FieldDefinition:
    return _FieldDefinition(column, label, "dimension", None, value_kind)


def _metric(
    column: str,
    label: str,
    aggregate: Literal["avg", "sum", "max", "min"] = "avg",
    value_kind: Literal["number", "integer"] = "number",
) -> _FieldDefinition:
    return _FieldDefinition(column, label, "metric", aggregate, value_kind)


_DATASETS: dict[str, _DatasetDefinition] = {
    "market_daily": _DatasetDefinition(
        table="fact_market_daily",
        label="市场日频总览",
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "market_stage": _dimension("market_stage", "市场阶段"),
            "stage_day": _dimension("stage_day", "阶段天数", "integer"),
            "volume_state": _dimension("volume_state", "量能状态"),
            "concentration_state": _dimension(
                "concentration_state", "行业集中状态"
            ),
            "leading_industry_1": _dimension("industry_1", "成交第一行业"),
            "leading_industry_2": _dimension("industry_2", "成交第二行业"),
            "leading_industry_3": _dimension("industry_3", "成交第三行业"),
        },
        metrics={
            "index_close": _metric("sh_index_close", "上证收盘"),
            "index_return_pct": _metric("sh_index_pct_chg", "上证涨跌幅"),
            "total_amount": _metric("total_amount", "市场成交额"),
            "amount_change_pct": _metric(
                "amount_vs_yesterday_pct", "成交额环比"
            ),
            "amount_ma20": _metric("amount_ma20", "20日平均成交额"),
            "volume_ratio": _metric("volume_ratio", "量比"),
            "advancers": _metric("advancers", "上涨家数", "avg", "integer"),
            "limit_up": _metric("limit_up", "涨停家数", "avg", "integer"),
            "limit_down": _metric(
                "limit_down", "跌停家数", "avg", "integer"
            ),
            "top3_industry_ratio": _metric(
                "top3_industry_ratio", "前三行业成交占比"
            ),
            "strength_return_pct": _metric(
                "strength_avg_pct", "强势股加权涨幅"
            ),
            "strength_amount_pct": _metric(
                "strength_amount_pct", "强势股成交占比"
            ),
        },
    ),
    "stock_daily": _DatasetDefinition(
        table="fact_stock_daily",
        label="个股日频行情",
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
        },
        metrics={
            "close": _metric("close", "收盘价"),
            "pre_close": _metric("pre_close", "前收盘价"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "amount": _metric("amount", "成交额", "sum"),
            "turnover": _metric("turnover", "换手率"),
        },
    ),
    "sector_daily": _DatasetDefinition(
        table="fact_sector_daily",
        label="板块日频行情",
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "sector_code": _dimension("sector_ts_code", "板块代码"),
            "sector_name": _dimension("sector_name", "板块名称"),
            "sw_l1": _dimension("sw_l1", "申万一级行业"),
            "multi_period_resonance": _dimension(
                "multi_period_resonance", "多周期共振", "boolean"
            ),
        },
        metrics={
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "amount": _metric("amount", "成交额", "sum"),
            "marginal_volume_pct": _metric("diff_ratio", "边际量"),
            "strength": _metric("strength", "强度"),
        },
    ),
    "sector_stock_daily": _DatasetDefinition(
        table="fact_sector_stock_daily",
        label="板块成分股日频行情",
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "sector_code": _dimension("sector_ts_code", "板块代码"),
            "sector_name": _dimension("sector_name", "板块名称"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "sw_industry": _dimension("sw_industry", "申万行业"),
            "high_status": _dimension("high_status", "新高状态"),
        },
        metrics={
            "price": _metric("price", "价格"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "return_5d_pct": _metric("pct_chg_5d", "5日涨跌幅"),
            "return_10d_pct": _metric("pct_chg_10d", "10日涨跌幅"),
            "return_20d_pct": _metric("pct_chg_20d", "20日涨跌幅"),
            "amount": _metric("amount", "成交额", "sum"),
            "fund_flow_1d": _metric("fund_flow_1d", "1日资金流"),
            "fund_flow_5d": _metric("fund_flow_5d", "5日资金流"),
            "float_market_cap_yi": _metric("float_mcap_yi", "流通市值亿元"),
        },
    ),
    "mainline_theme_daily": _DatasetDefinition(
        table="fact_mainline_theme_daily",
        label="主线题材日频结构",
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "theme_code": _dimension("theme_code", "题材代码"),
            "theme_name": _dimension("theme_name", "题材名称"),
        },
        metrics={
            "sector_count": _metric(
                "sector_count", "覆盖板块数", "max", "integer"
            ),
            "rank": _metric("min_sort", "主线排序", "min", "integer"),
        },
    ),
    "mainline_sector_daily": _DatasetDefinition(
        table="fact_mainline_sector_daily",
        label="主线板块日频结构",
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "theme_name": _dimension("theme_name", "题材名称"),
            "sector_code": _dimension("sector_ts_code", "板块代码"),
            "sector_name": _dimension("sector_name", "板块名称"),
            "cycle_level": _dimension("cycle_level", "周期层级"),
            "cycle_status": _dimension("cycle_status", "周期状态"),
            "high_status": _dimension("high_status", "新高状态"),
        },
        metrics={
            "return_pct": _metric("today_pct", "当日涨跌幅"),
            "limit_up_count": _metric(
                "limit_up_count", "涨停家数", "sum", "integer"
            ),
            "max_limit_height": _metric(
                "max_limit_height", "最高连板", "max", "integer"
            ),
            "amount": _metric("amount", "成交额", "sum"),
            "relative_amount": _metric(
                "amount_relative_ratio", "相对成交额"
            ),
            "net_inflow_1d": _metric("net_inflow_1d", "1日净流入", "sum"),
            "strength": _metric("strength", "强度"),
            "strength_change": _metric("strength_chg", "强度变化"),
        },
    ),
}


_ALL_FIELDS = tuple(
    sorted({field for dataset in _DATASETS.values() for field in dataset.fields})
)
_SCALAR_SCHEMA = {
    "anyOf": [
        {"type": "string"},
        {"type": "number"},
        {"type": "integer"},
        {"type": "boolean"},
        {
            "type": "array",
            "items": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                    {"type": "integer"},
                    {"type": "boolean"},
                ]
            },
        },
    ]
}
FINANCE_QUERY_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "dataset": {"type": "string", "enum": list(_DATASETS)},
        "metrics": {
            "type": "array",
            "items": {"type": "string", "enum": list(_ALL_FIELDS)},
        },
        "dimensions": {
            "type": "array",
            "items": {"type": "string", "enum": list(_ALL_FIELDS)},
        },
        "filters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(_ALL_FIELDS)},
                    "op": {"type": "string", "enum": sorted(_FILTER_OPERATORS)},
                    "value": _SCALAR_SCHEMA,
                },
                "required": ["field", "op", "value"],
                "additionalProperties": False,
            },
        },
        "time_range": {
            "anyOf": [
                {
                    "type": "object",
                    "properties": {
                        "start": {"type": ["string", "null"]},
                        "end": {"type": ["string", "null"]},
                    },
                    "required": ["start", "end"],
                    "additionalProperties": False,
                },
                {"type": "null"},
            ]
        },
        "group_by": {
            "type": "array",
            "items": {"type": "string", "enum": list(_ALL_FIELDS)},
        },
        "order_by": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(_ALL_FIELDS)},
                    "direction": {"type": "string", "enum": ["asc", "desc"]},
                },
                "required": ["field", "direction"],
                "additionalProperties": False,
            },
        },
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
    },
    "required": [
        "dataset",
        "metrics",
        "dimensions",
        "filters",
        "time_range",
        "group_by",
        "order_by",
        "limit",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class _CompiledQuery:
    sql: str
    parameters: tuple[object, ...]
    output_fields: tuple[str, ...]
    source_date_index: int
    applied_limit: int


DuckDbConnect = Callable[..., Any]


def _duckdb_connect(path: str, *, read_only: bool) -> Any:
    import duckdb

    return duckdb.connect(path, read_only=read_only)


class FinanceQuery:
    """Compile and execute one model-owned semantic query under code-owned caps."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        limits: FinanceQueryLimits | None = None,
        connect: DuckDbConnect | None = None,
    ) -> None:
        self._db_path = Path(db_path).expanduser()
        self._limits = limits or FinanceQueryLimits()
        self._connect = connect or _duckdb_connect

    def run(
        self,
        spec: FinanceQuerySpec,
        *,
        information_cutoff: InformationCutoff,
        deadline: ResearchDeadline,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> FinanceQueryResult:
        cancelled = is_cancelled or (lambda: False)
        if cancelled():
            raise FinanceQueryCancelled("finance query cancelled")
        compiled = _compile_query(
            spec,
            information_cutoff=information_cutoff,
            max_rows=self._limits.max_rows,
        )
        timeout = min(
            self._limits.timeout,
            max(0.0, deadline.stage_timeout(self._limits.timeout)),
        )
        if timeout <= 0.001:
            raise FinanceQueryTimedOut("finance query deadline exhausted")
        started = time.monotonic()
        connection: Any | None = None
        stop_monitor = Event()
        interrupted_for: list[str] = []
        try:
            if cancelled():
                raise FinanceQueryCancelled("finance query cancelled")
            connection = self._connect(str(self._db_path), read_only=True)

            def monitor() -> None:
                expires_at = time.monotonic() + timeout
                while not stop_monitor.wait(0.01):
                    if cancelled():
                        interrupted_for.append("cancelled")
                        connection.interrupt()
                        return
                    if time.monotonic() >= expires_at:
                        interrupted_for.append("timeout")
                        connection.interrupt()
                        return

            monitor_thread = Thread(
                target=monitor,
                name="finance-query-deadline",
                daemon=True,
            )
            monitor_thread.start()
            try:
                cursor = connection.execute(
                    compiled.sql,
                    list(compiled.parameters),
                )
                rows, source_dates, output_bytes = self._fetch_rows(
                    cursor,
                    compiled,
                    cancelled=cancelled,
                )
            except Exception as exc:
                if interrupted_for:
                    if interrupted_for[0] == "cancelled":
                        raise FinanceQueryCancelled(
                            "finance query cancelled"
                        ) from exc
                    raise FinanceQueryTimedOut(
                        "finance query statement timeout"
                    ) from exc
                if isinstance(exc, FinanceQueryError):
                    raise
                raise FinanceQueryExecutionError(
                    f"finance query execution failed: {type(exc).__name__}"
                ) from exc
            finally:
                stop_monitor.set()
                monitor_thread.join(timeout=0.2)
            if interrupted_for:
                if interrupted_for[0] == "cancelled":
                    raise FinanceQueryCancelled("finance query cancelled")
                raise FinanceQueryTimedOut("finance query statement timeout")
            if cancelled():
                raise FinanceQueryCancelled("finance query cancelled")
        finally:
            stop_monitor.set()
            if connection is not None:
                connection.close()

        elapsed = time.monotonic() - started
        fingerprint = hashlib.sha256(compiled.sql.encode("utf-8")).hexdigest()[:16]
        dataset = _DATASETS[spec.dataset]
        evidence = _rows_to_evidence(
            rows,
            source_dates=source_dates,
            dataset_name=spec.dataset,
            dataset=dataset,
            fingerprint=fingerprint,
        )
        dates = tuple(item.source_date for item in evidence if item.source_date)
        observation = "；".join(item.detail for item in evidence)
        if not observation:
            observation = f"{dataset.label}：结构化查询无结果"
        audit = FinanceQueryAudit(
            dataset=spec.dataset,
            physical_sql=compiled.sql,
            bound_parameters=compiled.parameters,
            sql_fingerprint=fingerprint,
            applied_limit=compiled.applied_limit,
            row_count=len(rows),
            output_bytes=output_bytes,
            elapsed_seconds=round(elapsed, 6),
        )
        return FinanceQueryResult(
            rows=rows,
            evidence=evidence,
            observation=observation,
            served_date=max(dates) if dates else None,
            audit=audit,
        )

    def _fetch_rows(
        self,
        cursor: Any,
        compiled: _CompiledQuery,
        *,
        cancelled: Callable[[], bool],
    ) -> tuple[tuple[dict[str, object], ...], tuple[str | None, ...], int]:
        rows: list[dict[str, object]] = []
        output_bytes = 0
        while len(rows) < compiled.applied_limit:
            if cancelled():
                raise FinanceQueryCancelled("finance query cancelled")
            batch = cursor.fetchmany(
                min(64, compiled.applied_limit - len(rows))
            )
            if not batch:
                break
            for raw_row in batch:
                public = {
                    field: _json_value(raw_row[index])
                    for index, field in enumerate(compiled.output_fields)
                }
                source_date = _date_text(raw_row[compiled.source_date_index])
                public["__source_date"] = source_date
                encoded = json.dumps(
                    public,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
                output_bytes += len(encoded)
                if output_bytes > self._limits.max_bytes:
                    raise FinanceQueryLimitExceeded(
                        "finance query byte limit exceeded"
                    )
                rows.append(public)
        visible_rows = tuple(
            {
                key: value
                for key, value in row.items()
                if key != "__source_date"
            }
            for row in rows
        )
        source_dates = tuple(
            _date_text(row.get("__source_date")) for row in rows
        )
        return visible_rows, source_dates, output_bytes


def _compile_query(
    spec: FinanceQuerySpec,
    *,
    information_cutoff: InformationCutoff,
    max_rows: int,
) -> _CompiledQuery:
    dataset = _DATASETS.get(spec.dataset)
    if dataset is None:
        raise FinanceQueryValidationError(f"unknown dataset: {spec.dataset}")
    fields = dataset.fields
    for name in spec.dimensions:
        field = fields.get(name)
        if field is None:
            raise FinanceQueryValidationError(f"unknown field: {name}")
        if field.role != "dimension":
            raise FinanceQueryValidationError(f"not a dimension: {name}")
    for name in spec.metrics:
        field = fields.get(name)
        if field is None:
            raise FinanceQueryValidationError(f"unknown field: {name}")
        if field.role != "metric":
            raise FinanceQueryValidationError(f"not a metric: {name}")
    selected = tuple(dict.fromkeys((*spec.dimensions, *spec.metrics)))
    if len(selected) != len(spec.dimensions) + len(spec.metrics):
        raise FinanceQueryValidationError("selected fields must be unique")
    group_by = tuple(dict.fromkeys(spec.group_by))
    if len(group_by) != len(spec.group_by):
        raise FinanceQueryValidationError("group_by fields must be unique")
    for name in group_by:
        if name not in spec.dimensions:
            raise FinanceQueryValidationError(
                "group_by fields must be selected dimensions"
            )
    if group_by and set(spec.dimensions) != set(group_by):
        raise FinanceQueryValidationError(
            "all selected dimensions must appear in group_by"
        )
    selected_set = set(selected)
    for order in spec.order_by:
        if order.field not in selected_set:
            raise FinanceQueryValidationError(
                f"order field must be selected: {order.field}"
            )
    cutoff = information_cutoff.as_of_date
    if spec.time_range is not None:
        if spec.time_range.start is not None and spec.time_range.start > cutoff:
            raise FinanceQueryValidationError(
                "time range conflicts with information cutoff"
            )
        if spec.time_range.end is not None and spec.time_range.end > cutoff:
            raise FinanceQueryValidationError(
                "time range conflicts with information cutoff"
            )
        if (
            spec.time_range.start is not None
            and spec.time_range.end is not None
            and spec.time_range.start > spec.time_range.end
        ):
            raise FinanceQueryValidationError("time range start exceeds end")
    if dataset.time_field is None and spec.time_range is not None:
        raise FinanceQueryValidationError("dataset has no time dimension")

    aliases: dict[str, str] = {}
    select_parts: list[str] = []
    for index, name in enumerate(selected):
        field = fields[name]
        alias = f"c{index}"
        aliases[name] = alias
        expression = _quote(field.column)
        if group_by and field.role == "metric":
            if field.aggregate is None:
                raise FinanceQueryValidationError(
                    f"metric cannot be grouped: {name}"
                )
            expression = f"{field.aggregate.upper()}({expression})"
        select_parts.append(f"{expression} AS {alias}")
    if dataset.time_field is None:
        select_parts.append("NULL AS __source_date")
    elif group_by:
        time_column = fields[dataset.time_field].column
        select_parts.append(f"MAX({_quote(time_column)}) AS __source_date")
    else:
        time_column = fields[dataset.time_field].column
        select_parts.append(f"{_quote(time_column)} AS __source_date")

    where_parts: list[str] = []
    parameters: list[object] = []
    if dataset.time_field is not None:
        time_column = fields[dataset.time_field].column
        where_parts.append(f"{_quote(time_column)} <= ?")
        parameters.append(cutoff.isoformat())
        if spec.time_range is not None and spec.time_range.start is not None:
            where_parts.append(f"{_quote(time_column)} >= ?")
            parameters.append(spec.time_range.start.isoformat())
        if spec.time_range is not None and spec.time_range.end is not None:
            where_parts.append(f"{_quote(time_column)} <= ?")
            parameters.append(spec.time_range.end.isoformat())
    for item in spec.filters:
        field = fields.get(item.field)
        if field is None:
            raise FinanceQueryValidationError(f"unknown field: {item.field}")
        if item.field == dataset.time_field:
            raise FinanceQueryValidationError(
                "date filters must use time_range"
            )
        clause, values = _filter_clause(field, item)
        where_parts.append(clause)
        parameters.extend(values)

    sql = f"SELECT {', '.join(select_parts)} FROM {_quote(dataset.table)}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if group_by:
        sql += " GROUP BY " + ", ".join(
            _quote(fields[name].column) for name in group_by
        )
    if spec.order_by:
        sql += " ORDER BY " + ", ".join(
            f"{aliases[item.field]} {item.direction.upper()}"
            for item in spec.order_by
        )
    elif dataset.time_field in aliases:
        sql += f" ORDER BY {aliases[dataset.time_field]} DESC"
    applied_limit = min(spec.limit, max_rows)
    sql += " LIMIT ?"
    parameters.append(applied_limit)
    return _CompiledQuery(
        sql=sql,
        parameters=tuple(parameters),
        output_fields=selected,
        source_date_index=len(selected),
        applied_limit=applied_limit,
    )


def _filter_clause(
    field: _FieldDefinition,
    item: QueryFilter,
) -> tuple[str, tuple[object, ...]]:
    column = _quote(field.column)
    if item.op not in _FILTER_OPERATORS:
        raise FinanceQueryValidationError(
            f"unsupported operator: {item.op}"
        )
    operators = {
        "eq": "=",
        "ne": "!=",
        "lt": "<",
        "lte": "<=",
        "gt": ">",
        "gte": ">=",
    }
    if item.op in operators:
        return f"{column} {operators[item.op]} ?", (item.value,)
    if item.op == "in":
        if not isinstance(item.value, Sequence) or isinstance(
            item.value, (str, bytes)
        ):
            raise FinanceQueryValidationError("in filter requires an array")
        values = tuple(item.value)
        if not values:
            raise FinanceQueryValidationError("in filter cannot be empty")
        placeholders = ", ".join("?" for _ in values)
        return f"{column} IN ({placeholders})", values
    if field.value_kind != "text" or not isinstance(item.value, str):
        raise FinanceQueryValidationError(
            "contains filter requires a text field and string value"
        )
    escaped = (
        item.value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"{column} LIKE ? ESCAPE '\\\\'", (f"%{escaped}%",)


def _rows_to_evidence(
    rows: tuple[dict[str, object], ...],
    *,
    source_dates: tuple[str | None, ...],
    dataset_name: str,
    dataset: _DatasetDefinition,
    fingerprint: str,
) -> tuple[agent_research.AgentEvidence, ...]:
    evidence: list[agent_research.AgentEvidence] = []
    fields = dataset.fields
    for index, row in enumerate(rows, start=1):
        source_date = source_dates[index - 1]
        detail = "；".join(
            f"{fields[name].label}={_display_value(value)}"
            for name, value in row.items()
        )
        title = dataset.label + (f"（{source_date}）" if source_date else "")
        item = agent_research.AgentEvidence(
            tool="finance_query",
            title=title,
            detail=detail,
            source=f"本地结构化数据 · {dataset.label}",
            internal_locator=f"finance-query:{fingerprint}:{index}",
            source_date=source_date,
            evidence_tier=dataset.evidence_tier,
            independent_key=f"duckdb:{dataset_name}:{source_date or 'undated'}",
            freshness="current",
        )
        evidence.append(
            replace(
                item,
                content_hash=agent_research.evidence_content_hash(item),
            )
        )
    return tuple(evidence)


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FinanceQueryValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FinanceQueryValidationError(f"{name} must be an array of strings")
    items = tuple(_required_text(item, name) for item in value)
    if len(set(items)) != len(items):
        raise FinanceQueryValidationError(f"{name} values must be unique")
    return items


def _parse_filters(value: object) -> tuple[QueryFilter, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FinanceQueryValidationError("filters must be an array")
    parsed: list[QueryFilter] = []
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != {"field", "op", "value"}:
            raise FinanceQueryValidationError(
                "each filter requires field, op, and value"
            )
        field = _required_text(raw.get("field"), "filter field")
        op = _required_text(raw.get("op"), "filter op")
        if op not in _FILTER_OPERATORS:
            raise FinanceQueryValidationError(f"unsupported operator: {op}")
        parsed.append(QueryFilter(field, op, raw.get("value")))
    return tuple(parsed)


def _parse_time_range(value: object) -> TimeRange | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) - {"start", "end"}:
        raise FinanceQueryValidationError(
            "time_range accepts only start and end"
        )
    return TimeRange(
        start=_parse_date(value.get("start"), "time_range.start"),
        end=_parse_date(value.get("end"), "time_range.end"),
    )


def _parse_orders(value: object) -> tuple[Order, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FinanceQueryValidationError("order_by must be an array")
    parsed: list[Order] = []
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != {"field", "direction"}:
            raise FinanceQueryValidationError(
                "each order requires field and direction"
            )
        field = _required_text(raw.get("field"), "order field")
        direction = _required_text(raw.get("direction"), "order direction")
        if direction not in _ORDER_DIRECTIONS:
            raise FinanceQueryValidationError(
                f"unsupported order direction: {direction}"
            )
        parsed.append(Order(field, direction))
    return tuple(parsed)


def _parse_date(value: object, name: str) -> date | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise FinanceQueryValidationError(f"{name} must be an ISO date")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise FinanceQueryValidationError(f"{name} must be an ISO date") from exc


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _date_text(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            return None
    return None


def _display_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if value is None:
        return "未知"
    return str(value)


__all__ = [
    "FINANCE_QUERY_PARAMETERS",
    "FinanceQuery",
    "FinanceQueryAudit",
    "FinanceQueryCancelled",
    "FinanceQueryError",
    "FinanceQueryExecutionError",
    "FinanceQueryLimitExceeded",
    "FinanceQueryLimits",
    "FinanceQueryResult",
    "FinanceQuerySpec",
    "FinanceQueryTimedOut",
    "FinanceQueryValidationError",
    "Order",
    "QueryFilter",
    "TimeRange",
]
