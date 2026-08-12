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
_FILTER_OPERATORS = frozenset({"eq", "ne", "lt", "lte", "gt", "gte", "in", "contains"})
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
    # NULL 的业务语义因字段而异：high_status 的 NULL 是「非新高」这个事实，
    # 渲染成「未知」会让模型把"多数个股不是新高"误读成"数据没回填"
    # （2026-08-13 A10 实测：GROUP BY high_status 按成交额降序，NULL 组
    # 天然最大，top25 全显示「未知」，模型据此错误宣告数据缺口）。
    null_label: str = "未知"


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
    null_label: str = "未知",
) -> _FieldDefinition:
    return _FieldDefinition(column, label, "dimension", None, value_kind, null_label)


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
            "concentration_state": _dimension("concentration_state", "行业集中状态"),
            "leading_industry_1": _dimension("industry_1", "成交第一行业"),
            "leading_industry_2": _dimension("industry_2", "成交第二行业"),
            "leading_industry_3": _dimension("industry_3", "成交第三行业"),
        },
        metrics={
            "index_close": _metric("sh_index_close", "上证收盘"),
            "index_return_pct": _metric("sh_index_pct_chg", "上证涨跌幅"),
            "total_amount": _metric("total_amount", "市场成交额"),
            "amount_change_pct": _metric("amount_vs_yesterday_pct", "成交额环比"),
            "amount_ma20": _metric("amount_ma20", "20日平均成交额"),
            "volume_ratio": _metric("volume_ratio", "量比"),
            "advancers": _metric("advancers", "上涨家数", "avg", "integer"),
            "limit_up": _metric("limit_up", "涨停家数", "avg", "integer"),
            "limit_down": _metric("limit_down", "跌停家数", "avg", "integer"),
            "top3_industry_ratio": _metric("top3_industry_ratio", "前三行业成交占比"),
            "strength_return_pct": _metric("strength_avg_pct", "强势股加权涨幅"),
            "strength_amount_pct": _metric("strength_amount_pct", "强势股成交占比"),
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
            "high_status": _dimension(
                "high_status", "新高状态", null_label="非新高"
            ),
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
    # 新高家数结构的 canonical 表。表内只有当日创出新高的个股，直接
    # COUNT/GROUP BY 就是「新高家数结构」；此前该表没有注册，模型只能借道
    # sector_stock_daily.high_status 间接拼，且被 NULL 主导的分组误导
    # （2026-08-13 A10 实测）。
    "stock_high_daily": _DatasetDefinition(
        table="fact_stock_high_daily",
        label="个股新高日频记录",
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "high_period": _dimension("primary_high_period", "新高周期"),
            "high_label": _dimension("primary_high_label", "新高级别"),
            "is_new": _dimension("is_new", "是否首次新高", "boolean"),
            "limit_status": _dimension(
                "limit_status", "涨停状态", null_label="非涨停"
            ),
            "sw_l1": _dimension("sw_l1", "申万一级行业"),
            "sw_l2": _dimension("sw_l2", "申万二级行业"),
            "plate": _dimension("plate", "所属板块"),
        },
        metrics={
            "price": _metric("price", "价格"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "return_10d_pct": _metric("pct_chg_10d", "10日涨跌幅"),
            "amount": _metric("amount", "成交额", "sum"),
            "market_cap": _metric("market_cap", "总市值"),
            "fund_today": _metric("fund_today", "当日资金", "sum"),
            "limit_times": _metric("limit_times", "连板数", "max", "integer"),
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
            "sector_count": _metric("sector_count", "覆盖板块数", "max", "integer"),
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
            "high_status": _dimension(
                "high_status", "新高状态", null_label="非新高"
            ),
        },
        metrics={
            "return_pct": _metric("today_pct", "当日涨跌幅"),
            "limit_up_count": _metric("limit_up_count", "涨停家数", "sum", "integer"),
            "max_limit_height": _metric(
                "max_limit_height", "最高连板", "max", "integer"
            ),
            "amount": _metric("amount", "成交额", "sum"),
            "relative_amount": _metric("amount_relative_ratio", "相对成交额"),
            "net_inflow_1d": _metric("net_inflow_1d", "1日净流入", "sum"),
            "strength": _metric("strength", "强度"),
            "strength_change": _metric("strength_chg", "强度变化"),
        },
    ),
}

_PROVIDER_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "market_daily": {
        "limit_up_count": "limit_up",
        "limit_down_count": "limit_down",
    }
}


def _normalize_provider_field_aliases(spec: FinanceQuerySpec) -> FinanceQuerySpec:
    aliases = _PROVIDER_FIELD_ALIASES.get(spec.dataset, {})
    if not aliases:
        return spec

    def field(value: str) -> str:
        return aliases.get(value, value)

    return replace(
        spec,
        metrics=tuple(field(value) for value in spec.metrics),
        dimensions=tuple(field(value) for value in spec.dimensions),
        filters=tuple(replace(item, field=field(item.field)) for item in spec.filters),
        group_by=tuple(field(value) for value in spec.group_by),
        order_by=tuple(
            replace(item, field=field(item.field)) for item in spec.order_by
        ),
    )


def _normalize_date_filters(
    spec: FinanceQuerySpec,
) -> tuple[FinanceQuerySpec, tuple[str, ...]]:
    """把 filters 里的日期条件搬进 time_range，只在语义完全等价时才搬。

    为什么由 Harness 代偿而不是只靠重试提示：日期该放 time_range 是本引擎的
    局部约定，不是 SQL 常识——模型按「日期就是一个普通等值筛选」的直觉写，是
    可预期的高频错法。实测一轮 research 里同一个错犯了两次（`filters` 带
    trade_date → `date filters must use time_range`），重试提示写得很清楚但隔
    一轮又犯，两个工具槽白烧，最终 `deadline_exhausted` 降级。提示词只能降低
    概率，代偿能消除这类损耗。

    等价性是硬边界，只搬三种算子：

        eq  → start = end = 值      （闭区间单日，与 `time = ?` 等价）
        gte → start = 值            （编译期用 `>=`，同为闭端）
        lte → end   = 值            （编译期用 `<=`，同为闭端）

    刻意不搬 ``gt`` / ``lt``：``time_range`` 的两端在 ``_compile_query`` 里编译成
    ``>=`` / ``<=``，把开区间搬成闭区间会**静默多带一天数据**——这比报错坏得多，
    报错只是浪费一次调用，静默改语义会让答案引用一条模型没要求的记录。同理不搬
    ``ne`` / ``in`` / ``contains``：它们表达的是集合而非区间，``time_range``
    无法表示。这些继续走原有校验报错。

    另外三种情况也不代偿，都留给原有报错：目标端点已被显式 ``time_range`` 占用
    （代偿会覆盖模型的明确意图）、值不是 ISO 日期、合并后 start > end。

    纯函数，返回新 spec 与人类可读的代偿说明；幂等（搬完 filters 里已无日期
    字段，再调一次是 no-op），所以放在多层调用链上重复调用是安全的。
    """

    dataset = _DATASETS.get(spec.dataset)
    if dataset is None or dataset.time_field is None or not spec.filters:
        return spec, ()
    time_field = dataset.time_field

    existing = spec.time_range or TimeRange()
    start = existing.start
    end = existing.end
    kept: list[QueryFilter] = []
    moved: list[str] = []
    for item in spec.filters:
        if item.field != time_field:
            kept.append(item)
            continue
        parsed: date | None
        try:
            parsed = _parse_date(item.value, "filters.value")
        except FinanceQueryValidationError:
            parsed = None
        if parsed is None:
            kept.append(item)
            continue
        if item.op == "eq" and start is None and end is None:
            start = end = parsed
        elif item.op == "gte" and start is None:
            start = parsed
        elif item.op == "lte" and end is None:
            end = parsed
        else:
            # 算子不可等价表达，或该端点已被显式 time_range 占用。
            kept.append(item)
            continue
        moved.append(f"{time_field} {item.op} {parsed.isoformat()}")

    if not moved:
        return spec, ()
    if start is not None and end is not None and start > end:
        # 合并后区间自相矛盾：原样退回，让 `date filters must use time_range`
        # 照常报错，而不是把一个空结果伪装成查询成功。
        return spec, ()

    note = (
        "已自动把 filters 中的日期条件搬到 time_range（"
        + "，".join(moved)
        + "）；后续请直接用 time_range.start/time_range.end，filters 不接受日期字段"
    )
    return (
        replace(
            spec,
            filters=tuple(kept),
            time_range=TimeRange(start=start, end=end),
        ),
        (note,),
    )


def normalize_spec(
    spec: FinanceQuerySpec,
) -> tuple[FinanceQuerySpec, tuple[str, ...]]:
    """把一份模型写出的 spec 归一到引擎的规范形态。

    单一入口，供引擎内部与 Episode 工具层共用：两层都要看到同一个 spec，否则
    ``episode_tools`` 的新鲜度判定读 ``spec.time_range`` 会读到 ``None``，
    「本题授权查历史窗口」这类判断就会因为日期写错了位置而失效。
    """

    normalized, notes = _normalize_date_filters(
        _normalize_provider_field_aliases(spec)
    )
    return normalized, notes


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


def _dataset_query_schema(
    name: str,
    dataset: _DatasetDefinition,
) -> dict[str, object]:
    fields = list(dataset.fields)
    dimensions = list(dataset.dimensions)
    metrics = list(dataset.metrics)
    return {
        "type": "object",
        "properties": {
            "dataset": {"type": "string", "const": name},
            "metrics": {
                "type": "array",
                "items": {"type": "string", "enum": metrics},
                "uniqueItems": True,
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string", "enum": dimensions},
                "uniqueItems": True,
            },
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": fields},
                        "op": {
                            "type": "string",
                            "enum": sorted(_FILTER_OPERATORS),
                        },
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
                "items": {"type": "string", "enum": dimensions},
                "uniqueItems": True,
            },
            "order_by": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": fields},
                        "direction": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                        },
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


_PUBLIC_DATASETS = sorted(_DATASETS)
_PUBLIC_DIMENSIONS = sorted(
    {field for dataset in _DATASETS.values() for field in dataset.dimensions}
)
_PUBLIC_METRICS = sorted(
    {field for dataset in _DATASETS.values() for field in dataset.metrics}
)
_PUBLIC_FIELDS = sorted({*_PUBLIC_DIMENSIONS, *_PUBLIC_METRICS})


def dataset_field_hint(dataset: str | None = None) -> str:
    """Describe valid semantic fields without exposing physical table names."""

    names = (dataset,) if dataset in _DATASETS else tuple(sorted(_DATASETS))
    parts: list[str] = []
    for name in names:
        definition = _DATASETS[name]
        parts.append(
            f"{name}: dimensions={','.join(sorted(definition.dimensions))}; "
            f"metrics={','.join(sorted(definition.metrics))}"
        )
    return "；".join(parts)


def validation_retry_hint(
    spec: FinanceQuerySpec,
    error: FinanceQueryValidationError,
) -> str:
    """Point a rejected semantic field to its registered dataset and role."""

    message = str(error)
    if message.startswith("unknown dataset:"):
        return "dataset 可选 " + ",".join(sorted(_DATASETS))
    if message == "date filters must use time_range":
        return "日期不要放入 filters；请改用 time_range.start/time_range.end"

    requested_fields = tuple(
        dict.fromkeys(
            (
                *spec.dimensions,
                *spec.metrics,
                *(item.field for item in spec.filters),
                *spec.group_by,
                *(item.field for item in spec.order_by),
            )
        )
    )
    current = _DATASETS.get(spec.dataset)
    problem_fields = [
        field
        for field in requested_fields
        if current is None or field not in current.fields
    ]
    for prefix in ("not a dimension:", "not a metric:", "metric cannot be grouped:"):
        if message.startswith(prefix):
            field = message.removeprefix(prefix).strip()
            if field and field not in problem_fields:
                problem_fields.append(field)

    locations: list[str] = []
    unsupported = False
    for field in problem_fields:
        owners: list[str] = []
        for dataset_name, definition in sorted(_DATASETS.items()):
            if field in definition.dimensions:
                owners.append(f"{dataset_name}.dimension")
            if field in definition.metrics:
                owners.append(f"{dataset_name}.metric")
        if owners:
            locations.append(f"{field}→{'/'.join(owners)}")
        else:
            locations.append(f"{field}→未注册")
            unsupported = True

    parts = [f"当前 dataset={spec.dataset}"]
    if locations:
        parts.append("字段归属：" + "，".join(locations))
        parts.append(
            "一次查询只能使用一个 dataset；所需字段跨 dataset 时请拆成多个查询，"
            "逐次观察结果后再汇总"
        )
    if not locations or unsupported:
        parts.append(dataset_field_hint(spec.dataset))
    return "；".join(parts)


# Keep the provider-facing schema orthogonal and shallow.  Dataset-specific
# field compatibility remains a code-owned invariant in ``FinanceQuerySpec``
# and ``_compile_query``; duplicating every dataset as a top-level ``oneOf``
# made the function schema large enough that compatible providers could emit an
# empty argument object instead of a query.
FINANCE_QUERY_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "dataset": {
            "type": "string",
            "enum": _PUBLIC_DATASETS,
            "description": (
                "先选表。字段必须属于所选 dataset，跨表混用会被拒绝："
                "成交额在 market_daily 叫 total_amount，"
                "在 sector_daily / stock_daily 叫 amount。"
            ),
        },
        "metrics": {
            "type": "array",
            "items": {"type": "string", "enum": _PUBLIC_METRICS},
            "uniqueItems": True,
            "description": '要取的数值列，数组。例：["total_amount", "limit_up"]',
        },
        "dimensions": {
            "type": "array",
            "items": {"type": "string", "enum": _PUBLIC_DIMENSIONS},
            "uniqueItems": True,
            "description": (
                "标识/分组列，数组，只接受本列表里的维度字段。"
                '例：["trade_date", "sector_name"]。'
                # 实测：模型把 rank（metric）塞进 dimensions → not a dimension: rank。
                # 枚举已经排除了它，但枚举本身挡不住，得明说两个槽位不能互串。
                "数值列（如 rank、amount）属于 metrics，放进来会报 not a dimension。"
            ),
        },
        "filters": {
            "type": "array",
            # 限定语排在被限定内容之前：先说形状，再说例子，最后说禁区。
            "description": (
                # 实测 2 次：元素缺键 → each filter requires field, op, and value。
                # 「三件套」三个字不够，得把「一个都不能少」说出来。
                "数组，每个元素必须同时有 field、op、value 三个键，一个都不能少。"
                '例：[{"field": "return_pct", "op": "gt", "value": 0}]。'
                'op 为 in 时 value 必须是数组：[{"field": "sector_name", '
                '"op": "in", "value": ["电网设备", "光伏设备"]}]。'
                "⚠ 日期条件不要放这里，放 time_range。"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": _PUBLIC_FIELDS},
                    "op": {
                        "type": "string",
                        "enum": sorted(_FILTER_OPERATORS),
                    },
                    "value": {
                        "description": (
                            "字符串、数字、布尔值或这些标量的数组；"
                            "op 为 in 时必须给数组"
                        )
                    },
                },
                "required": ["field", "op", "value"],
                "additionalProperties": False,
            },
        },
        "time_range": {
            "type": "object",
            "description": (
                "闭区间，两端都包含。所有日期条件都走这里，不要写进 filters。"
                '单日查询把两端写成同一天：{"start": "2026-07-23", "end": "2026-07-23"}'
            ),
            "properties": {
                # 「隐式约定靠例子最容易传达」——ch4 §3 点名的就是这类。
                # 解析是 date.fromisoformat(value[:10])，所以 ISO 日期是唯一可靠写法。
                "start": {
                    "type": "string",
                    "description": 'ISO 日期 YYYY-MM-DD，例："2026-07-23"',
                },
                "end": {
                    "type": "string",
                    "description": 'ISO 日期 YYYY-MM-DD，例："2026-07-23"',
                },
            },
            "additionalProperties": False,
        },
        "group_by": {
            "type": "array",
            "items": {"type": "string", "enum": _PUBLIC_DIMENSIONS},
            "uniqueItems": True,
            # 2026-08-12 复核实测：24 次采样里 2 次栽在这条。schema 表达不了
            # 「group_by 必须等于 dimensions 全集」这种跨字段约束（_compile_query:1030）。
            # 先说「多数情况不要传」——那是最省事且最不会错的用法。
            "description": (
                "只在需要聚合时传；不传就按 dimensions 逐行返回原始数据，"
                "多数查询都不需要它。"
                "一旦传了，就必须把 dimensions 里的**每一个**都列进来"
                '（少一个报 all selected dimensions must appear in group_by），'
                "且此时 metrics 会被聚合而不是返回原值。"
                '例：dimensions=["sector_name"] 时传 ["sector_name"]。'
            ),
        },
        "order_by": {
            "type": "array",
            # 2026-08-12 实测的头号错法：13 次调用里 9 次把 order_by 写成单个对象。
            # schema 本来就写着 "type": "array"——**光有类型挡不住，缺的是例子**。
            # 所以这条描述的第一句就是形状，且给出「只排一个字段也要包方括号」的反例。
            "description": (
                "数组，即使只排一个字段也要用方括号包起来。"
                '例：[{"field": "strength", "direction": "desc"}]。'
                '多字段按先后依次生效：[{"field": "strength", "direction": "desc"}, '
                '{"field": "amount", "direction": "desc"}]。'
                '写成单个对象 {"field": ..., "direction": ...} 会被拒绝。'
                # 这条约束是写例子时实跑才发现的（_compile_query:1031）：
                # 光看 schema 完全看不出来，模型更不可能猜到。
                "排序字段必须已经出现在 metrics 或 dimensions 里，"
                "否则报 order field must be selected。"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": _PUBLIC_FIELDS},
                    "direction": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                    },
                },
                "required": ["field", "direction"],
                "additionalProperties": False,
            },
        },
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
    },
    "required": ["dataset", "metrics", "dimensions"],
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
        # 幂等：调用方（episode_tools）通常已归一化过，这里再调一次是 no-op。
        # 保留这一步是因为本引擎也服务非 Episode 调用方，不能假设上游做过。
        spec, _notes = normalize_spec(spec)
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
                        raise FinanceQueryCancelled("finance query cancelled") from exc
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
            batch = cursor.fetchmany(min(64, compiled.applied_limit - len(rows)))
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
                    raise FinanceQueryLimitExceeded("finance query byte limit exceeded")
                rows.append(public)
        visible_rows = tuple(
            {key: value for key, value in row.items() if key != "__source_date"}
            for row in rows
        )
        source_dates = tuple(_date_text(row.get("__source_date")) for row in rows)
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
                raise FinanceQueryValidationError(f"metric cannot be grouped: {name}")
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
            raise FinanceQueryValidationError("date filters must use time_range")
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
            f"{aliases[item.field]} {item.direction.upper()}" for item in spec.order_by
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
        raise FinanceQueryValidationError(f"unsupported operator: {item.op}")
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
        if not isinstance(item.value, Sequence) or isinstance(item.value, (str, bytes)):
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
    escaped = item.value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
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
            f"{fields[name].label}={_display_value(value, fields[name])}"
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
        raise FinanceQueryValidationError("time_range accepts only start and end")
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
            raise FinanceQueryValidationError("each order requires field and direction")
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


def _display_value(value: object, field: _FieldDefinition | None = None) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if value is None:
        return field.null_label if field is not None else "未知"
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
    "dataset_field_hint",
    "validation_retry_hint",
]
