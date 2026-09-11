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
    requested_time_range: tuple[str | None, str | None] | None = None


def covered_date_range(source_dates: Sequence[str | None]) -> str | None:
    dates = sorted({item for item in source_dates if item})
    if not dates:
        return None
    if dates[0] == dates[-1]:
        return dates[0]
    return f"{dates[0]}..{dates[-1]}"


def truncation_notice(
    audit: FinanceQueryAudit,
    *,
    covered_range: str | None = None,
) -> str | None:
    """撞顶就提示。不再要求「harness 压低了 limit」——模型自设 limit 撞顶是主路径。

    T1b 把时间维升序改成倒序取数后，LIMIT 切掉的是窗口**前端**，不是末端。
    提示必须同时给出请求窗口和未覆盖侧，否则模型会以为「还差更多行」而把
    limit 调大——Agent 路径上限仍是 25，调大无效。
    """

    if audit.row_count < audit.applied_limit:
        return None
    text = (
        f"查询结果已按 Agent 上下文预算截断至 {audit.applied_limit} 条；"
        "未覆盖的日期请收窄 time_range 再查，不要靠调大 limit"
    )
    if covered_range:
        text += f"；实际覆盖 {covered_range}"
    requested = audit.requested_time_range
    if requested is not None:
        req_start, req_end = requested
        text += f"；请求窗口 {_format_date_range(req_start, req_end)}"
        gap = _uncovered_window_notice(requested, covered_range)
        if gap:
            text += f"；{gap}"
    return text


def _format_date_range(start: str | None, end: str | None) -> str:
    if start and end and start != end:
        return f"{start}..{end}"
    return start or end or "?"


def _uncovered_window_notice(
    requested: tuple[str | None, str | None],
    covered_range: str | None,
) -> str | None:
    if not covered_range:
        return None
    req_start, req_end = requested
    if ".." in covered_range:
        cov_start, cov_end = covered_range.split("..", 1)
    else:
        cov_start = cov_end = covered_range
    parts: list[str] = []
    if req_start and cov_start > req_start:
        parts.append(f"窗口前端未覆盖（请求从 {req_start} 起，实际从 {cov_start} 起）")
    if req_end and cov_end < req_end:
        parts.append(f"窗口末端未覆盖（实际到 {cov_end}，请求到 {req_end}）")
    return "；".join(parts) if parts else None


def _requested_time_range(
    spec: FinanceQuerySpec,
) -> tuple[str | None, str | None] | None:
    if spec.time_range is None:
        return None
    start = (
        spec.time_range.start.isoformat() if spec.time_range.start is not None else None
    )
    end = spec.time_range.end.isoformat() if spec.time_range.end is not None else None
    if start is None and end is None:
        return None
    return (start, end)


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
    population: Literal["full", "subset", "single"] = "full"
    coverage: str = ""
    # 时间残缺：该日之前不是这个宇宙的全集（历史回填残段）。和 population=subset
    # 不是一回事——后者是**每天**都只收一部分，前者是**某日之后才齐**。
    # 只写在 coverage 散文里不够：事后 advisory 必须能按 time_range 分流。
    incomplete_before: date | None = None
    # 日程表的发生日可以晚于信息截止日。默认关：行情表继续用
    # time_field <= cutoff，防止前视。只允许 event_daily 打开。
    allow_future_time_range: bool = False
    # 信息截止打在哪一列。None = 打在 time_field（行情默认）。
    # event_daily 打在 updated_at：已经写入的未来日程可见，截止日后才写入的不可见。
    cutoff_column: str | None = None

    @property
    def fields(self) -> dict[str, _FieldDefinition]:
        return {**self.dimensions, **self.metrics}


# ``population`` 是**机器可读的覆盖面**，``coverage`` 是给模型看的同一件事的散文。
# ``incomplete_before`` 是第三种：**宇宙本身是全集，但某日之前回填不齐**。
#
# 为什么需要它：A5 实测（2026-08-18）问「涨停集中在哪些题材」，模型选了
# ``mainline_sector_daily``。那张表**结构上完全合法**——它确实有 ``limit_up_count``
# 这一列，数值也和权威表逐行相等（07-23 重叠的 7 个板块 7/7 相同）。错的不是数值，
# 是**分母**：它只收当日「主线」板块（十余行），而问题问的是全量榜（两百余行）。
# 在十余行的子集里取 top-N，答案结构性地不可能对，而校验器一声不吭——因为
# 「字段属不属于这张表」这个维度上它没毛病。
#
# 所以覆盖面必须和字段归属一样，是**模型下单前**就能看到的信息，不能只在
# 事后 observation 里补。这与 ``_agent_finance_parameters`` 里把行数上限写进 schema
# 是同一条理由：模型感知到的世界与工具操作的世界之间不能存在系统性偏差。
#
# **两种失败形状不要共用 subset 旗标**：
# - 结构子集（每天都只收一部分）→ ``population="subset"``，advisory 指向真正的全集表。
# - 时间残缺（某日之后才齐）→ ``population="full"`` + ``incomplete_before``，
#   advisory 只在问句窗落到残缺区间时出声。把后者标成 subset，catalog 会把近端
#   合法排名说成「子集内部名次」，再按通用字段名把模型推向个股表。
#
# **刻意不写具体行数**：行数天天变，写进源码就是手抄第二事实源，漂了没人知道。
# 这里只声明**性质**（全量 / 子集 / 单行 / 分界日），性质是稳定的。要精确行数就去查库。


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
        population="single",
        coverage=(
            "全市场每天 1 行的总量口径。涨停家数在这里是**全市合计**，不按板块拆——要板块分布用 "
            "theme_limit_heat_daily。"
        ),
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
            "total_amount": _metric("total_amount", "市场成交额亿"),
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
        population="full",
        coverage=(
            "全市个股全集，每股每日一行。"
        ),
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
            "amount": _metric("amount", "成交额亿", "sum"),
            "turnover": _metric("turnover", "换手率"),
        },
    ),
    "sector_daily": _DatasetDefinition(
        table="fact_sector_daily",
        label="板块日频行情",
        population="full",
        coverage=(
            "全量板块全集（涨幅 / 成交额 / 边际量 diff_ratio），双红判断主表。"
        ),
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
            "amount": _metric("amount", "成交额亿", "sum"),
            "marginal_volume_pct": _metric("diff_ratio", "边际量"),
            "strength": _metric("strength", "强度"),
        },
    ),
    "sector_stock_daily": _DatasetDefinition(
        table="fact_sector_stock_daily",
        label="板块成分股日频行情",
        population="full",
        coverage=(
            "板块×成分股全集，本库行数最大的一张，务必先加筛选再查。"
        ),
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
            "amount": _metric("amount", "成交额亿", "sum"),
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
        population="full",
        coverage=(
            "**表内只含当日创新高的个股**；按 high_period / sw_l1 分组计数即新高结构。"
        ),
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
            "amount": _metric("amount", "成交额亿", "sum"),
            "market_cap": _metric("market_cap", "总市值"),
            "fund_today": _metric("fund_today", "当日资金", "sum"),
            "limit_times": _metric("limit_times", "连板数", "max", "integer"),
        },
    ),
    "mainline_theme_daily": _DatasetDefinition(
        table="fact_mainline_theme_daily",
        label="主线题材日频结构",
        population="subset",
        coverage=(
            "**只含当日被判为「主线」的题材，是个位数量级的子集**，不是题材全集。"
        ),
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
        population="subset",
        coverage=(
            "**只含当日「主线」板块，十余行的人工筛选子集，不是全市板块全集**。它也有 limit_up_count "
            "且数值与权威表一致，但在这张表里排序只能得到「主线内部的 top」，**回答不了「全市涨停集中在哪些板块」**——那个要 "
            "theme_limit_heat_daily。"
        ),
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
            "amount": _metric("amount", "成交额亿", "sum"),
            "relative_amount": _metric("amount_relative_ratio", "相对成交额"),
            "net_inflow_1d": _metric("net_inflow_1d", "1日净流入", "sum"),
            "strength": _metric("strength", "强度"),
            "strength_change": _metric("strength_chg", "强度变化"),
        },
    ),
    "auction_stock_daily": _DatasetDefinition(
        table="fact_auction_stock_daily",
        label="集合竞价看板个股日频",
        population="subset",
        coverage=(
            "复盘会竞价看板：**每个面板每日只收 top 10**（实测上限 10，均值 9.8）。"
            "**这是全表最容易被误用的地方**——`zt` 面板永远约 10 行，而前一日真实涨停"
            "常有 37~106 只（实测 2026-08-18：表内 10 vs 真实 106）。**问「昨天多少只涨停」"
            "「涨停都有谁」绝不能用本表**，那要 `market_daily.limit_up` 或 "
            "`theme_limit_heat_daily`。本表只回答「这批被选进看板的票，今天竞价表现如何」。\n"
            "七个面板（`panel_key`）：`zt` 昨日涨停 / `lb` 昨日连板 / `db` 1日前断板 / "
            "`qdb` 2日前 / `dqdb` 3日前 / `db4` 4日前 / `db5` 5日前。\n"
            "**时间语义**：`trade_date` 是**竞价发生日**，面板名描述的是此前发生的事——"
            "`zt` 那行的意思是「该股在 trade_date 的前一交易日涨停，本日竞价表现如下」。\n"
            "覆盖 2026-01-16 起 145 个交易日；金额单位为亿（与 `fact_stock_daily.amount` "
            "逐位对账一致）；`limit_seq` 是连板数不是排名（`lb` 面板最小值为 2）。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "竞价交易日", "date"),
            "panel": _dimension("panel_key", "看板面板"),
            "panel_label": _dimension("panel_label", "面板中文名"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "leader_plate": _dimension("leader_plate", "所属题材"),
        },
        metrics={
            "auction_return_pct": _metric("auction_pct", "竞价涨幅"),
            "return_pct": _metric("pct_chg", "当日涨跌幅"),
            "auction_amount": _metric("auction_amount", "竞价成交额亿", "sum"),
            "day_amount": _metric("day_amount", "全日成交额亿", "sum"),
            "limit_times": _metric("limit_seq", "连板数", "max", "integer"),
        },
    ),
    "regulation_pool_daily": _DatasetDefinition(
        table="fact_regulation_pool_daily",
        label="监管安全池日频快照",
        population="subset",
        coverage=(
            "复盘会**安全池**的每日快照，不是监管宇宙全集。"
            "实测每日 1~89 行（中位约 12），库里目前只有 `safe`（写入器认 waiting，生产 0 行）。"
            "**问「多少只股在异动/监管」不能用本表**。"
            "`effective_date` 是快照日；信息截止打在这一列。"
            "`updated_at` 是入库时间（大量行写于 2026-08-12 回填墙），**不能当 PIT 信息日**。"
            "**不开放涨幅**：`pct_chg_10d` 存的是小数（0.507=+50.7%），不是百分数；"
            "开放会被读成「涨了 0.51%」。也不开放 close——池接口自带价，"
            "与 `fact_stock_daily.close` 并非逐日相等"
            "（实测 1186/6453 不一致，另 81 行对不上行情表）。"
            "窗口内缺 2026-08-19（事件表同日也缺）。"
        ),
        time_field="effective_date",
        dimensions={
            "effective_date": _dimension("effective_date", "快照日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "pool_status": _dimension("pool_status", "池状态"),
        },
        metrics={
            "safe_days_10d": _metric("safe_days_10d", "10日安全天数", "min", "integer"),
        },
    ),
    "regulation_event_daily": _DatasetDefinition(
        table="fact_regulation_event_daily",
        label="监管在场名单日频快照",
        population="subset",
        coverage=(
            "每天把还在监管窗里的票**重拍一遍**，不是「事件发生一次记一行」。"
            "2026-01-15 起几乎每个交易日都有行（147 天里缺 2026-08-19）。"
            "`effective_date` 是快照日；`start_date`/`end_date` 是监管窗，**不是时间轴**。"
            "`updated_at` 同样是入库时间，不能当 PIT。"
            "问「今天谁还在监管名单」用本表 + time_range；"
            "问还剩几天用 `days_remaining`，**禁止把 end_date 当 as-of**——"
            "约 89% 的 end_date 晚于快照日，当时间轴会让整批被判成晚于问句日。"
            "`event_type` 约四成为空，不是漏了。"
        ),
        time_field="effective_date",
        dimensions={
            "effective_date": _dimension("effective_date", "快照日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "start_date": _dimension("start_date", "监管开始日", "date"),
            "end_date": _dimension("end_date", "监管结束日", "date"),
            "status_type": _dimension("status_type", "退出状态"),
            "event_type": _dimension("event_type", "监管类型"),
            "leader_plate": _dimension("leader_plate", "所属题材"),
        },
        metrics={
            "days_remaining": _metric(
                "days_remaining_trading", "剩余交易日", "min", "integer"
            ),
        },
    ),
    "historical_mapping": _DatasetDefinition(
        table="fact_historical_mapping",
        label="历史相似日映射",
        population="full",
        coverage=(
            "「这一天像历史上哪一天」。有行的日子通常 2 条相似日"
            "（实测 335 天为 2、17 天为 1），不是个股宇宙。"
            "`as_of` 是被对照的交易日；`similar_date` 是历史相似日，只做维度。"
            "**不要按 similar_date 当时间轴**——那会把后来才算出来的映射漏进更早的问句。"
            "**不要把 `updated_at` 当信息日**：671/687 行写于 2026-08-12 回填墙，"
            "那是入库时间不是算法计算时间。本表不能做 08-12 之前的 PIT 重放——"
            "问句日早于回填日仍看得到后来才写入的映射。"
            "缺行是接口空（ops 记 empty），不是没同步。"
            "相似日可早于本库行情起点（最早到 2022）。"
        ),
        time_field="as_of",
        dimensions={
            "as_of": _dimension("source_date", "被对照的交易日", "date"),
            "similar_date": _dimension("similar_date", "历史相似日", "date"),
            "external_cycle": _dimension("external_cycle", "外部周期"),
            "summary": _dimension("summary", "相似日摘要"),
        },
        metrics={
            "similarity": _metric("similarity", "相似度"),
            "cycle_day": _metric("cycle_day", "周期第几天", "max", "integer"),
        },
    ),
    "sw_l1_daily": _DatasetDefinition(
        table="fact_sw_l1_daily",
        label="申万一级行业日频行情",
        population="full",
        incomplete_before=date(2026, 6, 5),
        coverage=(
            "申万一级 31 个行业指数的日行情。**完整度分两段（实测 2026-08-25）**："
            "`2026-06-05` 起每日 31/31，这一宇宙已齐，可直接排序；"
            "**此前多数交易日只有 3~10 个行业**（344 天平均 7.7，部分回填残段，"
            "夹着少量满 31 的孤岛）。**在分界日之前取 top-N 会在残缺分母里排序**——"
            "问「某月哪个行业最强」若落在 06-05 之前，先声明覆盖不足，不要给排名。"
            "与 `sector_daily` 不是一回事：那是约 224 个概念板块（一只股可进多板块），"
            "这是 31 个申万一级行业。行业涨跌用本表，题材热度用 `sector_daily` 或 "
            "`theme_limit_heat_daily`。"
            "**本表不提供成交额**：库里那列不是「亿」（写入侧原样存 AKShare 值；"
            "2026-08-24 全行业合计约 198 万对大盘 20,072 亿，比值≈100，即百万元口径）。"
            "不要对 `sector_daily` 按申万一级加总冒充行业成交额——"
            "概念重叠会重复计算，加总会大于全市。"
            "另 `fupanhui_ratio` 约 27% 有值、`amount_ma120*` 约 2%，同样未开放，不是漏了。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "sw_l1": _dimension("sw_l1", "申万一级行业"),
            "sw_l1_code": _dimension("sw_l1_code", "申万一级代码"),
        },
        # 刻意不放 amount：见上面 coverage。语义层「八处成交额口径一致（亿）」是
        # test_amount_metric_labels_carry_unit 钉住的不变量；为了多一个指标去放宽它，
        # 等于改门禁迁就代码。要暴露就得先在写入侧统一单位，那是另一个单子。
        metrics={
            "close": _metric("close", "行业指数收盘"),
            "pre_close": _metric("pre_close", "前收盘"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
        },
    ),
    "stock_technical_daily": _DatasetDefinition(
        table="feature_stock_technical_daily",
        label="个股 UP 线与偏离度日频",
        population="full",
        coverage=(
            "全 A 个股逐日 UP 线（布林带变体 `UP = MA26 + 0.764×STD26`，N=26/P=20）与偏离度 "
            "`(close/UP - 1)×100`。**满 26 个交易日收盘价才算得出**，新上市与长期停牌股当日缺行——"
            "2026-08-24 实测 5519/5540（99.6%）。**缺行 ≠ 没偏离，是算不出**。"
            "`deviation_pct > 0` 即站上 UP 线，`< 0` 为低于。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
        },
        metrics={
            "close": _metric("close", "收盘价"),
            "ma26": _metric("ma26", "26日均价"),
            "std26": _metric("std26", "26日收盘标准差"),
            "up_value": _metric("up_value", "UP线"),
            "deviation_pct": _metric("deviation_pct", "UP偏离度"),
        },
    ),
    # ── 复盘会公开资产（2026-08-13 接入语义层，此前入库但 agent 够不着）──
    "dragon_summary_daily": _DatasetDefinition(
        table="fact_dragon_summary_daily",
        label="龙虎榜全市场日汇总（机构/游资净买入）",
        population="single",
        coverage=(
            "龙虎榜每日 1 行的全市场汇总。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
        },
        metrics={
            "listed_count": _metric("stock_count", "上榜个股数", "max", "integer"),
            "inst_net_buy": _metric("inst_net_buy", "机构净买入亿", "sum"),
            "retail_net_buy": _metric("youzi_net_buy", "游资净买入亿", "sum"),
            "active_brokers": _metric("active_brokers", "活跃营业部数", "max", "integer"),
        },
    ),
    "dragon_seat_daily": _DatasetDefinition(
        table="fact_dragon_seat_daily",
        label="龙虎榜席位级明细（谁买谁卖）",
        population="full",
        coverage=(
            "龙虎榜席位级明细全集。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "side": _dimension("side", "买卖方向"),
            "seat_type": _dimension("seat_type", "席位类型"),
            "seat_name": _dimension("exalter", "营业部/席位名"),
            "hot_money": _dimension("hm_name", "游资名", null_label="非游资"),
        },
        metrics={
            "buy": _metric("buy", "买入额亿", "sum"),
            "sell": _metric("sell", "卖出额亿", "sum"),
            "net_buy": _metric("net_buy", "净买入亿", "sum"),
            "buy_rate": _metric("buy_rate", "买入占比"),
        },
    ),
    "dragon_tiger_daily": _DatasetDefinition(
        table="fact_dragon_tiger_daily",
        label="龙虎榜个股汇总",
        population="full",
        coverage=(
            "当日上榜个股全集；未上榜的个股不在表内。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "reason": _dimension("reason", "上榜原因"),
        },
        metrics={
            "close": _metric("close", "收盘价"),
            "return_pct": _metric("pct_change", "涨跌幅"),
            "net_amount": _metric("net_amount", "龙虎榜净买入亿", "sum"),
            "buy_amount": _metric("l_buy", "买入额亿", "sum"),
            "sell_amount": _metric("l_sell", "卖出额亿", "sum"),
            "amount": _metric("amount", "成交额亿", "sum"),
        },
    ),
    "core_leader_daily": _DatasetDefinition(
        table="fact_core_leader_daily",
        label="核心个股（自家：主线 × 正宗 × 人气）",
        population="subset",
        coverage=(
            "**每日约 20 只**，从当日主线题材的成员股里选：人气分（成交额/涨停/连板/新高/5日涨幅 "
            "各取池内百分位加权）+ 0.15 × 正宗度（知识库年报/主营暴露度）。"
            "与 `core_stock_daily` 是两个口径，别混着说：那张是成交额前 50，这张是主线里的正宗龙头。"
            "⚠️ 2026-04~09 消融实测：正宗度加权**降低**前瞻收益（w 越大越低，同量纲置换检验下显著为负）——"
            "这张表回答「谁是正宗龙头」，不是选股信号，不要拿它写「买入建议」。"
            "`kb_sector_covered=false` 时 `authenticity=0` 只表示知识库没有该板块的概念（没得查），"
            "不表示「查过、不正宗」。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "theme_name": _dimension("theme_name", "所属主线题材"),
            "sector_name": _dimension("sector_name", "命中板块"),
            "kb_concept": _dimension("kb_concept", "知识库概念（正宗度出处）"),
            "kb_strength": _dimension("kb_strength", "暴露强度 core/related/peripheral"),
            "kb_evidence_layer": _dimension("kb_evidence_layer", "证据层 L1/L2/L3 硬，*_candidate/graph_only 软"),
        },
        metrics={
            "rank": _metric("rank", "核心榜名次", "min", "integer"),
            "close": _metric("close", "收盘价"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "amount": _metric("amount", "成交额亿", "sum"),
            "gain_5d": _metric("gain_5d", "5日涨幅"),
            "boards": _metric("boards", "连板高度", "max", "integer"),
            "popularity": _metric("popularity", "人气分 0~1"),
            "authenticity": _metric("authenticity", "正宗度 0~1"),
            "score": _metric("score", "综合分"),
        },
    ),
    "core_stock_daily": _DatasetDefinition(
        table="fact_core_stock_daily",
        label="市场核心个股 TOP50",
        population="subset",
        coverage=(
            "**固定 50 只的核心股池**，不是全市个股——不要在这张表上写「全市最…」。"
            "口径已反推：就是当日全市场成交额前 50（405 日 20250 行实测命中 99.5%）。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "sw_l1": _dimension("sw_l1_name", "申万一级行业"),
            "leader_plate": _dimension("leader_plate", "所属题材"),
        },
        metrics={
            "rank": _metric("rank", "核心榜名次", "min", "integer"),
            "close": _metric("close", "收盘价"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "amount": _metric("amount", "成交额亿", "sum"),
            "float_market_cap": _metric("circ_mv", "流通市值亿"),
            "fund_flow_today": _metric("fund_flow_today", "当日资金流亿", "sum"),
            "gain_5d": _metric("gain_5d", "5日涨幅"),
            "gain_10d": _metric("gain_10d", "10日涨幅"),
        },
    ),
    "leader_height_daily": _DatasetDefinition(
        table="fact_leader_height_daily",
        label="连板龙头高度日频",
        population="single",
        coverage=(
            "每日 1 行的连板高度。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "leader_code": _dimension("leader_ts_code", "龙头代码"),
            "leader_name": _dimension("leader_name", "龙头名称"),
        },
        metrics={
            "height": _metric("height", "最高连板高度", "max", "integer"),
            "limit_times": _metric("limit_times", "龙头连板数", "max", "integer"),
            "seal_amount": _metric("fd_amount", "封单额", "max"),
        },
    ),
    # 连板梯队的个股明细。leader_height_daily 只有「每日 1 行的最高度」，
    # 「某股几板、题材归属、晋级率、梯队断层」都在这张。2026-08-27 A3 实测
    # （run_20260827_145613_094860）：个股深挖 episode 只拿到行情窗口，
    # 「6 连板、当日高度标、题材=电站」躺在库里却无查询通路——专用消费方
    # （timeline/analogs/pack 构建器）不是 agent 的查询面。
    "limit_advance_daily": _DatasetDefinition(
        table="fact_limit_advance_daily",
        label="连板梯队个股日频",
        population="subset",
        coverage=(
            "**只收当日连板梯队股（约二板及以上），且天然稀疏（部分交易日无行）**——"
            "无行 ≠ 当日无涨停，只说明梯队未同步或为空。全市涨停总数用 market_daily，"
            "按题材看涨停分布用 theme_limit_heat_daily。本表回答「谁在梯队、最高几板、"
            "题材归属、晋级率」；promotion_rate 是文本（如 1/2=50%），不能当数值聚合。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "theme": _dimension("theme", "题材归属", null_label="未标注"),
            "first_limit_date": _dimension("first_limit_date", "首板日", "date"),
            "promotion_rate": _dimension("promotion_rate", "晋级率"),
        },
        metrics={
            "boards": _metric("boards", "连板数", "max", "integer"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
        },
    ),
    # 2026-08-27 转正（工单 dataset-exemption-semantics）：原豁免理由
    # 「dedicated_path：adapter ALLOWED_TABLES 内，按需直查」——adapter 直查是
    # 代码通路，不是模型的查询面，与 #454 同形状。表是活的（05-06~08-27 日更）。
    "sector_period_rank_daily": _DatasetDefinition(
        table="fact_sector_period_rank_daily",
        label="板块区间涨幅榜（日频快照）",
        population="subset",
        coverage=(
            "**每日每档只收涨幅榜 top10，不是板块全量**——period_type ∈ "
            "daily/day3/day5/day10（当日/近3日/近5日/近10日涨幅榜），早期"
            "（2026-05-06 起约 22 个交易日）只有两档。无行 ≠ 板块不存在，只是"
            "没上榜。全量板块行情（pct_chg/diff_ratio/amount）用 sector_daily；"
            "本表回答「榜上谁最强、某板块是否连续在榜、榜内涨停家数与徽标」。"
            "badge ∈ sharp/fund/width（尖刀/资金/宽度徽标），缺省即无徽标。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "period_type": _dimension("period_type", "榜单档位"),
            "sector_code": _dimension("sector_ts_code", "板块代码"),
            "sector_name": _dimension("sector_name", "板块名称"),
            "badge": _dimension("badge", "徽标", null_label="无徽标"),
        },
        metrics={
            "rank": _metric("rank", "榜单名次", "min", "integer"),
            "change_pct": _metric("change_pct", "区间涨幅"),
            "limit_up_count": _metric("limit_up_count", "榜内涨停家数", "max", "integer"),
        },
    ),
    "global_index_daily": _DatasetDefinition(
        table="fact_global_index_daily",
        label="海外指数日频（隔夜外盘）",
        population="full",
        coverage=(
            "隔夜外盘指数全集，每日固定 5 个：DJI 道琼斯 / IXIC 纳斯达克 / SPX 标普500 / "
            "HSI 恒生 / HKTECH 恒生科技（实测与个股表同一 399 个 A 股交易日）。"
            "`trade_date` 是 A 股日历（隔夜对照日=信息日）；`session_date` 是外盘实际会话日，只做维度。"
            "多数日子两日同一天；美股休市/时差时 session 会早 1 或 3 天。"
            "**不要按 session_date 当时间轴**——问「今天隔夜」应对 A 股日。"
            "`updated_at` 大量写于 2026-08-12 回填墙，不能当 PIT。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "A股对照日", "date"),
            "session_date": _dimension("source_trade_date", "外盘会话日", "date"),
            "index_code": _dimension("code", "指数代码"),
            "index_name": _dimension("name", "指数名称"),
            "market_group": _dimension("market_group", "市场分组"),
        },
        metrics={
            "close": _metric("close", "收盘"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
        },
    ),
    "global_stock_daily": _DatasetDefinition(
        table="fact_global_stock_daily",
        label="海外核心股日频（隔夜外盘）",
        population="full",
        coverage=(
            "隔夜外盘核心股全集，每日固定 194 只（NASDAQ/NYSE；"
            "实测 399 个交易日天天 194，首末日 ticker 集合同一）。"
            "`trade_date` 是 A 股日历（隔夜对照日=信息日）；`session_date` 是外盘实际会话日，只做维度。"
            "多数日子两日同一天；美股休市/时差时 session 会早 1 或 3 天。"
            "**不要按 session_date 当时间轴**——问「今天隔夜英伟达」应对 A 股日。"
            "代码是 `NVDA` 这种美股 ticker，不是 `.SH/.SZ`。"
            "涨跌幅是百分数（1.30=+1.3%），与 A 股 `stock_daily` 同量纲。"
            "**不开放市值**：`market_cap_usd` 是原样美元（英伟达约 5.4e12），不是亿。"
            "`updated_at` 大量写于 2026-08-12 回填墙，不能当 PIT。"
            "与 `global_index_daily` 同一套 A 股日历。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "A股对照日", "date"),
            "session_date": _dimension("source_trade_date", "外盘会话日", "date"),
            "ticker": _dimension("ts_code", "美股代码"),
            "stock_name": _dimension("name_cn", "中文名"),
            "name_en": _dimension("name_en", "英文名"),
            "exchange": _dimension("exchange", "交易所"),
            "business": _dimension("business", "主营业务"),
            "industry_position": _dimension("industry_position", "产业位置"),
        },
        metrics={
            "close": _metric("close", "收盘"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "gain_5d": _metric("pct_chg_5d", "5日涨幅"),
        },
    ),
    # 2026-08-13 曾故意不注册稀疏事件表以收敛工具面。2026-08-23
    # 「下周大事」现场：表里已有英伟达/Jackson Hole，finance_query 却查不着，
    # 模型去搜维基年历。入库 ≠ 可消费；只翻 event，不翻 auction/regulation。
    "event_daily": _DatasetDefinition(
        table="fact_event_daily",
        label="复盘会事件日历（编辑催化）",
        population="subset",
        coverage=(
            "复盘会**编辑**催化日历，不是 BEA / 公司 IR / 交易所官方日程全集。"
            "event_date 是计划发生日，可以晚于信息截止日、也可以是周末；"
            "缺行是编辑没收，不是库坏了。下周/周末大事先查这张，"
            "不得把新闻标题或维基年历当日历真本源。"
        ),
        time_field="event_date",
        allow_future_time_range=True,
        cutoff_column="updated_at",
        dimensions={
            "event_date": _dimension("event_date", "事件日期", "date"),
            "event_id": _dimension("event_id", "事件编号"),
            "title": _dimension("title", "事件标题"),
            "content": _dimension("content", "事件正文"),
            "event_type": _dimension("event_type", "事件类型"),
            "sectors": _dimension("sectors", "关联板块"),
            "is_future": _dimension("is_future", "是否未来事件", "boolean"),
            "source": _dimension("source", "来源"),
        },
        metrics={
            "importance": _metric("importance", "重要性", "max", "integer"),
        },
    ),
    # A5：涨停集中题材的 canonical 表。未注册时模型只能借道主线/板块表，
    # 给出电力 8 家而不是储能 40 家（2026-08-18 实测）。
    "theme_limit_heat_daily": _DatasetDefinition(
        table="fact_theme_limit_heat_daily",
        label="题材涨停热度日频",
        population="full",
        coverage=(
            "**全量板块的涨停热度榜**（每板块涨停家数 / 占比 / "
            "排名）。「涨停集中在哪些题材」「哪个板块涨停最多」这类**全市分布**问题用这张。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "sector_code": _dimension("sector_ts_code", "板块代码"),
            "sector_name": _dimension("sector_name", "板块名称"),
            "dimension": _dimension("dimension", "热度维度"),
            "scope": _dimension("scope", "统计范围"),
        },
        metrics={
            "limit_up_count": _metric("limit_up_count", "涨停家数", "sum", "integer"),
            "market_limit_up_count": _metric(
                "market_limit_up_count", "全市场涨停家数", "max", "integer"
            ),
            "total_count": _metric("total_count", "题材家数", "max", "integer"),
            "limit_up_ratio": _metric("limit_up_ratio", "涨停占比"),
            "market_share": _metric("market_share", "市场占比"),
            "rank": _metric("rank", "热度排名", "min", "integer"),
        },
    ),
    # theme_limit_heat_daily 的个股明细层：聚合表答「哪个题材涨停多」，这张答
    # 「该题材具体哪些票涨停」。宇宙实测（2026-07-23）：116 只涨停股 → 578 行，
    # 去重后与 market_daily.limit_up 精确相等——一股多题材会多行，家数不可跨行直加。
    "theme_limit_stock_daily": _DatasetDefinition(
        table="fact_theme_limit_stock_daily",
        label="题材涨停个股明细日频",
        population="subset",
        coverage=(
            "**只收当日涨停个股 × 其所属题材（一股多题材会多行）**，不是全市场行情。"
            "数涨停家数要先按 stock_code 去重，或直接用 theme_limit_heat_daily（聚合层）/ "
            "market_daily.limit_up（全市总数）；全市场个股行情用 stock_daily。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "sector_code": _dimension("sector_ts_code", "题材代码"),
            "sector_name": _dimension("sector_name", "题材名称"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "sw_l1": _dimension("sw_l1", "申万一级行业"),
            "limit_status": _dimension("limit_status", "涨停状态", null_label="未知"),
            "leader_plate": _dimension("leader_plate", "龙头板块", null_label="未标注"),
        },
        metrics={
            "close": _metric("price", "收盘价"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "amount": _metric("amount", "成交额亿", "sum"),
            "limit_times": _metric("limit_times", "连板数", "max", "integer"),
            "open_times": _metric("open_times", "开板次数", "max", "integer"),
            "fund_flow_1d": _metric("fund_flow_1d", "1日资金流", "sum"),
            "float_market_cap_yi": _metric("circ_mv", "流通市值亿元", "max"),
        },
    ),
    # C3：技术面快照口径。当前常年 0 行，注册后查询路径诚实返回空，
    # 不得改走价格表。空表披露由 honesty_gates.empty_caliber_disclosure 短路。
    "stock_technical_snapshot": _DatasetDefinition(
        table="fact_stock_technical_snapshot",
        label="个股技术面快照",
        population="full",
        coverage=(
            "个股技术面快照。**当前是空表（0 行）**——取不到不是查询写错，是该口径暂无数据，应如实声明不可得。"
            "⚠️ 但 UP 线/偏离度**不要用这张**：有数据的是 `stock_technical_daily`（203 万行、日更）。"
            "这张表只服务「技术面快照」这一口径本身。"
        ),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "stock_name": _dimension("stock_name", "股票名称"),
            "source_table": _dimension("source_table", "来源表"),
        },
        metrics={
            "up_value": _metric("up_value", "UP 线"),
            "deviation_pct": _metric("deviation_pct", "乖离率"),
        },
    ),
    # 同花顺官方并跑源（工单 #41 A）。未切主：问「今天收盘」仍走 stock_daily。
    # turnover 是元不是亿；十年 dump 只有今天在市的票（幸存者偏差）。
    "stock_daily_hithink": _DatasetDefinition(
        table="fact_stock_daily_hithink",
        label="同花顺个股日K（未复权并跑）",
        population="full",
        coverage=(
            "同花顺官方全市场日 K dump，未复权 OHLCV。**并跑源，未切主**——"
            "日常收盘/涨幅仍用 stock_daily。"
            "**成交额 turnover 单位是元**，不是 stock_daily.amount 的亿。"
            "只有**今天在市**的股票：2016 年约一半代码没有行，已退市的不在，"
            "横截面回测有幸存者偏差。没有昨收/涨幅/换手率/股票名（dump 不带）。"
        ),
        incomplete_before=date(2016, 9, 8),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "adjusted": _dimension("adjusted", "复权标记"),
        },
        metrics={
            "open": _metric("open", "开盘价"),
            "high": _metric("high", "最高价"),
            "low": _metric("low", "最低价"),
            "close": _metric("close", "收盘价"),
            "volume": _metric("volume", "成交量股", "sum"),
            "turnover": _metric("turnover", "成交额元", "sum"),
        },
    ),
    "stock_adjustment_hithink": _DatasetDefinition(
        table="fact_stock_adjustment_hithink",
        label="同花顺复权事件",
        population="subset",
        coverage=(
            "分红 / 送股 / 配股事件，不是日频行情。一股多日才有行。"
            "从 1991 年起；含已公告未除权的未来日。"
        ),
        time_field="ex_date",
        allow_future_time_range=True,
        cutoff_column="updated_at",
        dimensions={
            "ex_date": _dimension("ex_date", "除权日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
        },
        metrics={
            "dividend_per_share": _metric("dividend_per_share", "每股现金分红"),
            "per_share_bonus": _metric("per_share_bonus", "每股送股"),
            "allotment_ratio": _metric("allotment_ratio", "配股比例"),
            "allotment_price": _metric("allotment_price", "配股价格"),
        },
    ),
    "sector_kline_daily": _DatasetDefinition(
        table="fact_sector_kline_daily",
        label="同花顺板块/指数日K",
        population="full",
        coverage=(
            "同花顺官方板块 / 指数日 K（``.TI`` / ``.SH`` / ``.SZ``），带开高低收。"
            "**深度约三年**：请求窗口超过约 1500 天会静默返回空。**并跑源，未切主**——"
            "板块涨幅/成交额日常仍用 sector_daily。"
            "**成交额 turnover 单位是元**。成分股只有当前，见 sector_constituent_hithink，"
            "不要拿来回算历史板块成交占比。"
        ),
        incomplete_before=date(2022, 8, 1),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "sector_code": _dimension("sector_ts_code", "板块代码"),
        },
        metrics={
            "open": _metric("open", "开盘价"),
            "high": _metric("high", "最高价"),
            "low": _metric("low", "最低价"),
            "close": _metric("close", "收盘价"),
            "volume": _metric("volume", "成交量", "sum"),
            "turnover": _metric("turnover", "成交额元", "sum"),
        },
    ),
    "sector_constituent_hithink": _DatasetDefinition(
        table="fact_sector_constituent_hithink",
        label="同花顺板块当前成分快照",
        population="subset",
        coverage=(
            "**只有当前成分**，带 captured_at，不是历史调入调出。"
            "禁止当历史成分用，也不要拿去改 sector_stock_daily。"
            "产品面不出个股名（表里没有 name）。"
        ),
        time_field="captured_at",
        dimensions={
            "captured_at": _dimension("captured_at", "快照日", "date"),
            "sector_code": _dimension("sector_ts_code", "板块代码"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "ticker": _dimension("ticker", "纯代码"),
        },
        metrics={
            "in_index": _metric("in_index", "是否当前成分", "max", "integer"),
        },
    ),
    "limit_pool_hithink": _DatasetDefinition(
        table="fact_limit_pool_hithink",
        label="同花顺涨停/跌停/炸板池",
        population="subset",
        coverage=(
            "三池一张表，``pool`` 列区分 limit_up / limit_down / limit_break。"
            "涨停**有效数据从 2020-07-01 起**（2020-01～06 上游返空）；跌停与炸板只有**一年**。"
            "**2023-07 ~ 2024-04 约 100 个交易日上游返 5003（池子缺 ticker）**，"
            "这些日子表里没有行，**不等于当天零涨停**，做承接 / 促进率不要拿它当分母。"
            "**并跑源，未切主**——全市涨停家数仍用 market_daily.limit_up；"
            "连板用 limit_advance_daily。两边口径可能差 ST / 北交所，先看一致率再判。"
            "六年池子里没有北交所（`.BJ`）。产品面不出个股名（表里没有 name）。"
        ),
        incomplete_before=date(2020, 7, 1),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "pool": _dimension("pool", "池"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "ticker": _dimension("ticker", "纯代码"),
            "is_st": _dimension("is_st", "是否ST", "boolean"),
            "is_new": _dimension("is_new", "是否次新", "boolean"),
            "limit_up_reason": _dimension("limit_up_reason", "涨停原因"),
        },
        metrics={
            "last_price": _metric("last_price", "最新价"),
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "continue_day_cnt": _metric(
                "continue_day_cnt", "连板数", "max", "integer"
            ),
            "seal_money": _metric("seal_money", "封单金额元", "sum"),
            "max_seal_money": _metric("max_seal_money", "最大封单元", "max"),
            "open_times": _metric("open_times", "开板次数", "max", "integer"),
            "turnover": _metric("turnover", "成交额元", "sum"),
        },
    ),
    "dragon_tiger_hithink": _DatasetDefinition(
        table="fact_dragon_tiger_hithink",
        label="同花顺龙虎榜个股",
        population="subset",
        coverage=(
            "官方 ``dragon-tiger-list?board_type=all``，**只有一年**。"
            "**并跑源，未切主**——净额仍用 dragon_tiger_daily.net_amount。"
            "两边单位可能是元 vs 亿，先看一致率再判，不硬改。"
            "产品面不出个股名。"
        ),
        incomplete_before=date(2025, 9, 8),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "ticker": _dimension("ticker", "纯代码"),
            "limit_reason": _dimension("limit_reason", "上榜原因"),
        },
        metrics={
            "return_pct": _metric("pct_chg", "涨跌幅"),
            "buy_value": _metric("buy_value", "买入额", "sum"),
            "sell_value": _metric("sell_value", "卖出额", "sum"),
            "net_value": _metric("net_value", "净额", "sum"),
            "org_net_value": _metric("org_net_value", "机构净额", "sum"),
            "hot_money_net_value": _metric("hot_money_net_value", "游资净额", "sum"),
        },
    ),
    "dragon_hot_money_hithink": _DatasetDefinition(
        table="fact_dragon_hot_money_hithink",
        label="同花顺龙虎榜游资组",
        population="subset",
        coverage=(
            "官方 ``dragon-tiger-list?board_type=hot_money``，一年。"
            "一行=一日×一游资×一股。**并跑**，组数对 fact_dragon_seat_daily 游资侧，不硬改。"
            "存游资名，不存个股名。"
        ),
        incomplete_before=date(2025, 9, 8),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "hot_money_name": _dimension("hot_money_name", "游资名"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "ticker": _dimension("ticker", "纯代码"),
        },
        metrics={
            "group_buying": _metric("group_buying", "游资组买入", "sum"),
            "net_value": _metric("net_value", "净额", "sum"),
            "hot_money_item_net_value": _metric(
                "hot_money_item_net_value", "游资单项净额", "sum"
            ),
        },
    ),
    "hot_stock_rank_hithink": _DatasetDefinition(
        table="fact_hot_stock_rank_hithink",
        label="同花顺历史热股榜",
        population="subset",
        coverage=(
            "官方 ``hot-stock-list-history``，一年、每日约 30 名。"
            "注意力名次新视角，不是复盘会主源。产品面不出个股名。"
        ),
        incomplete_before=date(2025, 9, 8),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "ticker": _dimension("ticker", "纯代码"),
        },
        metrics={
            "rank": _metric("rank", "热榜名次", "min", "integer"),
        },
    ),
    "auction_hithink": _DatasetDefinition(
        table="fact_auction_hithink",
        label="同花顺竞价（风向标+终态）",
        population="subset",
        coverage=(
            "``kind=benchmark`` 是短线风向标，**每天约 6 只**，2026-01 起，"
            "替代不了复盘会全量竞价看板。"
            "``kind=snapshot`` 是 ``auction/snapshot?stage=final`` 日更终态。"
            "**并跑未切主**。产品面不出个股名。"
        ),
        incomplete_before=date(2026, 1, 1),
        time_field="trade_date",
        dimensions={
            "trade_date": _dimension("trade_date", "交易日", "date"),
            "stock_code": _dimension("stock_ts_code", "股票代码"),
            "kind": _dimension("kind", "benchmark或snapshot"),
            "ticker": _dimension("ticker", "纯代码"),
            "tags": _dimension("tags", "风向标标签"),
        },
        metrics={
            "auction_pct": _metric("auction_pct", "竞价涨跌幅"),
            "auction_amount": _metric("auction_amount", "竞价成交额", "sum"),
            "auction_volume": _metric("auction_volume", "竞价量手", "sum"),
            "auction_unmatched": _metric("auction_unmatched", "未匹配量", "sum"),
            "float_market_cap": _metric("float_market_cap", "流通市值", "max"),
        },
    ),
}


# ``schema.sql`` 里的每张 fact_/feature_ 表，要么在上面注册、要么在这里写明为什么不注册。
# 二选一由 ``scripts/audit_dataset_registration.py`` 在 pre-commit 里强制。
#
# 为什么需要它：2026-08-13 那轮把复盘会 6 张表接进语义层时，处置理由
# （「稀疏/半结构表暂不注册，保持工具面收敛」）只写在 asset-inventory 文档正文里。
# 文档里的决定不是机器可读的——2026-08-25 复查时它被读成「漏了」，差点组织人去
# 「补」一个当初有意做过的决定。**豁免必须和注册表放在一起，让改动者同屏看见。**
#
# 同一轮还差点把 ``fact_top_gainers`` 注册进来：它只有 schema、没有写入链，
# 注册的结果是一个永远返回 0 行的 dataset。所以理由里区分 ``no_writer``——
# 「建表 ≠ 入库」是「入库 ≠ agent 能查到」的姊妹病，前者靠 COUNT(*) 才抓得住。
_UNREGISTERED_TABLES: dict[str, str] = {
    # ── 无写入链：只有 schema，注册即得永久空 dataset ──
    "fact_top_gainers": "no_writer：涨幅排行是「只展示不入库」设计，0 行",
    "fact_high_volume_gainers": "no_writer：大成交排行同上，0 行",
    # ── 基础设施：不是市场事实，不该出现在模型的 dataset 枚举里 ──
    "fact_sector_daily_generation": "internal：代际物理表，读口是同名 VIEW（见 check_sector_fact_access.py）",
    "fact_sector_stock_daily_generation": "internal：同上，读口是 VIEW",
    "fact_sector_universe_daily": "internal：快照台账名单，供完整度校验用",
    # ── 物化窗口：CLAUDE.md 明记「无活跃消费者，可能过期」，先别喂给模型 ──
    "feature_market_window": "stale_materialized：历史物化窗口，无活跃消费者",
    "feature_sector_window": "stale_materialized：同上",
    "feature_stock_window": "stale_materialized：同上",
    "feature_limit_advance_window": "stale_materialized：同上",
    # ── 2026-08-27 工单 dataset-exemption-semantics：dedicated_path 前缀废除 ──
    # 「代码消费得到」≠「模型够得着」：pack/adapter/证据块是预取注入面，不是模型的
    # 查询面。#454（连板梯队）与 fact_sector_period_rank_daily（本批转正，见
    # _DATASETS["sector_period_rank_daily"]）两次翻案都是这个前缀遮蔽的真缺口。
    # 留下的两类是真豁免，但理由换成回答「为什么模型不该/不需要够到」：
    "feature_l2_capital_flow_daily": (
        "stale_since：2026-08-07 后断更（L2 侧线 ClickHouse→特征表未日更，"
        "2026-08-27 实测落后 20 天）——注册停更表=喂模型旧数据。在更期消费方是 "
        "D9 证据块 market_moneyflow.py。复活条件：恢复日更后按 #454 形状转正"
    ),
    "feature_l2_quant_orders_daily": (
        "stale_since：同上（06-15~08-07，2600 行），恢复日更后一并转正"
    ),
    "fact_mainline_stock_daily": (
        "model_reachable_via：mainline_context 工具（episode 级快照注入，"
        "合同文案明确覆盖个股表）——模型已可达，再开 dataset 会双口径；"
        "主线题材/板块层另有 mainline_* 两个 dataset"
    ),
    # ── 2026-08-12 有意豁免过的稀疏/半结构表，已于 2026-08-25 转正 ──
    # 当初「无 trade_date、不是 drop-in」属实，变的是工具面：population / coverage /
    # incomplete_before / cutoff_column 能表达子集和双时态了。
    # 转正依据（先量后判，理由留在这里而不是默默删掉）：
    # - fact_auction_stock_daily → auction_stock_daily：145 天、每日 50~99 行，并不稀疏。
    # - fact_regulation_* → *_daily：effective_date 是快照日；updated_at 是入库时间
    #   （大量行写于 2026-08-12 回填墙），不能当 PIT。事件表是每日重拍的在场名单，
    #   不是「有事件才记一行」。end_date 约 89% 在未来，禁止当时间轴。
    # - fact_historical_mapping → historical_mapping：time_field 用别名 as_of，
    #   物理列仍是 source_date。禁止把 similar_date 当时间轴（过滤太松、前视）。
    #   表列 source_date 与证据层 source_date 同名不同义，靠别名隔离，不靠换列。
    #   两义并不碰巧对齐：updated_at 几乎全是回填墙，不能当信息日。
    # - fact_global_stock_daily → global_stock_daily：每日固定 194，与指数表同一
    #   A 股日历；time_field=trade_date，session_date 只做维度。市值是原样美元未开放。
    # ── 2026-08-27 转正两张（原豁免理由 dedicated_path，翻案依据留在这里）──
    # 「专用消费方」都是 pack/timeline/analogs 构建器，不是 agent 的查询面；
    # A3 live 实测（run_20260827_145613_094860，个股深挖题）episode 只拿到行情窗口，
    # 「6 连板、当日高度标、题材=电站」在库里却够不着。物理表同一张，注册只是
    # 加读口，不产生第二口径。
    # - fact_limit_advance_daily → limit_advance_daily（连板梯队个股明细）
    # - fact_theme_limit_stock_daily → theme_limit_stock_daily（涨停×题材个股明细，
    #   07-23 实测 116 只涨停股→578 行，去重后与 market_daily.limit_up 精确相等）
    # ── 有数据、无通路、先量后判：暂不注册 ──
    "fact_theme_flow_daily": (
        "candidate：45 天自 2026-06-23，每日 57~109 条；amount 貌似亿，"
        "但 08-25 合计 1884 vs 大盘 18316 vs sector_daily 加总 216801，未对账"
    ),
    "fact_research_report_catalog": "kb_side：467 行列表元数据，正文不在本表，偏知识库检索",
    "fact_theme_fundamental_doc": "kb_side：37 行，kb_path 指向知识库，graph_only",
    "fact_limit_advance_presence": (
        "overlap：仅姓名+序号；完整晋级在 dedicated_path 的 fact_limit_advance_daily"
    ),
}

# 注册了但**当前是空表**的，必须在这里声明是有意为之，否则审计判失败。
# ``fact_stock_technical_snapshot`` 是运行时诚实闸 ``honesty_gates._EMPTY_CALIBER_TABLE``
# 的锚点：它存在的意义就是让「问技术面快照」这一口径能如实回「暂无数据」。
_EMPTY_BY_DESIGN: frozenset[str] = frozenset({"fact_stock_technical_snapshot"})

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
    normalized, dedupe_notes = _drop_metrics_duplicated_into_dimensions(normalized)
    return normalized, notes + dedupe_notes


def _drop_metrics_duplicated_into_dimensions(
    spec: FinanceQuerySpec,
) -> tuple[FinanceQuerySpec, tuple[str, ...]]:
    """同一字段既在 ``metrics`` 又在 ``dimensions`` 时，从 dimensions 里去掉。

    2026-08-16 实测形状（4/4 个报错请求完全一致）：模型把 ``dimensions`` 当成
    「要返回的列」而不是「分组键」，于是把每个 metric 又抄了一份进 dimensions：

        dataset=mainline_sector_daily
        metrics    = [amount, limit_up_count, …, strength, strength_change]
        dimensions = [amount, cycle_level, …, strength, strength_change, trade_date]
        → not a dimension: strength

    **字段一个都没错**，全是该 dataset 的合法字段，只是角色放错。整条查询因此
    被拒、退回零证据，模型拿到重试提示后照样再犯（repairwin-8 连错两次）。

    去重是安全的：该字段**已经**在 ``metrics`` 里声明过，dimensions 里那份是
    重复而非另一种意图，去掉它不改变查询语义。

    **刻意不做的**：字段只出现在 ``dimensions``（metrics 里没有）时**不动**。
    那种情况下「想分组」还是「想取值」无法判定，越权猜测会悄悄改掉查询含义；
    仍交由校验器拒绝并给 ``validation_retry_hint``。这条边界有测试钉住。
    """

    dataset = _DATASETS.get(spec.dataset)
    if dataset is None or not spec.dimensions or not spec.metrics:
        return spec, ()
    declared_metrics = set(spec.metrics)
    redundant = tuple(
        name
        for name in spec.dimensions
        if name in declared_metrics and name in dataset.metrics
    )
    if not redundant:
        return spec, ()
    kept = tuple(name for name in spec.dimensions if name not in set(redundant))
    note = (
        "以下字段已在 metrics 中声明，已从 dimensions 移除（它们是度量不是分组键）："
        + ",".join(redundant)
    )
    return replace(spec, dimensions=kept), (note,)


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

_POPULATION_LABEL = {
    "full": "全集",
    "subset": "子集",
    "single": "单行",
}


def _dataset_catalog_text() -> str:
    """把注册表里每张表各自**覆盖多大人群**写进 schema，从注册表生成，不手抄。

    改这段之前先读 ``_DatasetDefinition.population`` 上方那段注释：模型此前
    看到的是 15 个**光秃秃的表名**，没有任何一句说明它们覆盖面差着两三个数量级
    （单行 / 十余行的主线子集 / 两百余行的全量榜）。A5 就是在这个条件下选了
    子集表回答全市问题——**它不是不知道有那张表（热度表一直在 enum 里），
    是没人告诉它两张表的分母不一样。**

    生成而非手写，理由同 ``_agent_finance_parameters``：手抄的目录会和注册表
    分叉，而分叉时没有任何门禁会发红。
    ``test_dataset_catalog_covers_every_dataset`` 钉住「每张表都在目录里」。
    """

    lines = [
        "先选表。**先看覆盖面再选**：下面每行是「表名（覆盖面）：它收哪些行」。",
        "问全市分布类问题（最多/集中在哪/排名）必须选覆盖面为「全集」的表；"
        "在「子集」表上排序只能得到子集内部的名次，那回答不了全市问题。",
        "字段必须属于所选 dataset，跨表混用会被拒绝："
        "成交额在 market_daily 叫 total_amount，在 sector_daily / stock_daily 叫 amount。",
        "",
    ]
    for name in _PUBLIC_DATASETS:
        definition = _DATASETS[name]
        scope = _POPULATION_LABEL[definition.population]
        lines.append(f"- {name}（{scope}）：{definition.coverage}")
    return "\n".join(lines)
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


def dataset_physical_table(dataset: str) -> str:
    """Physical table behind a semantic dataset. Empty string if unregistered."""

    definition = _DATASETS.get(str(dataset or "").strip())
    return definition.table if definition else ""


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


def _window_hits_incomplete(spec: FinanceQuerySpec, before: date) -> bool:
    """问句窗是否可能包含 ``before`` 之前的日期。

    ``time_range`` 缺失或 start 开着，当成无界过去——认不出来就 fail closed。
    只看 start：start 已经落在分界日当天或之后，整窗都在完整区间。
    """

    window = spec.time_range
    if window is None:
        return True
    return window.start is None or window.start < before


def _temporal_coverage_advisory(
    spec: FinanceQuerySpec, definition: _DatasetDefinition
) -> str:
    before = definition.incomplete_before
    if before is None:
        return ""
    if not _window_hits_incomplete(spec, before):
        return ""
    return (
        f"覆盖面提示：dataset={spec.dataset} 在 {before.isoformat()} 之前覆盖不齐"
        "（多数交易日只有部分成员，不是该宇宙的全集）。"
        "本窗落在残缺区间，排序得到的名次不能当成全集排名。"
        "请把 time_range 收到该日及以后，或先声明覆盖不足、不要给排名。"
    )


def coverage_advisory(spec: FinanceQuerySpec) -> str:
    """查询成功但分母可能错时，往 observation 上挂一句。

    这是 ``validation_retry_hint`` 够不着的那一半。那个函数只在查询**被拒**时
    说话，判据是「字段属不属于这张表」；而 A5 那次查询**完全合法**——
    ``mainline_sector_daily`` 确实有 ``limit_up_count``，数值也和权威表逐行相等。
    错的是分母：十余行的主线子集 vs 两百余行的全量榜。结构性校验原理上抓不到
    这类错，因为错表在结构上没毛病。

    两种分母错误分开处理：

    1. **时间残缺**（``incomplete_before``）：宇宙是全集，但某日之前回填不齐。
       只在问句窗可能落到残缺区间时出声，不指向别的表。
    2. **结构子集**（``population="subset"``）：每天都只收一部分。有真正的全集表
       才提示改表；排序字段若出现在很多全集表上（``return_pct`` / ``close``），
       按字段名找超集会指向错误粒度，此时宁可不说。

    **只在真的会被分母影响时才出声**：有 ``order_by``（即在做「最多 / 前几名」）
    才提示。纯粹取某个具体标的的值是正当用法，对它唠叨就是噪声。

    判据**不看 ``limit``**：它有默认值 50，恒为真，拿它当信号等于没有信号。

    返回空串表示无话可说——**调用方据此决定要不要把这句挂到 observation 上**，
    本函数不自己决定交付形态。
    """

    definition = _DATASETS.get(spec.dataset)
    if definition is None or not spec.order_by:
        return ""

    temporal = _temporal_coverage_advisory(spec, definition)
    if temporal:
        return temporal
    if definition.population != "subset":
        return ""

    # **只看排序字段**，不看 metrics 里搭车的那些列。决定名次的只有排序字段。
    # 通用列（return_pct）出现在很多全集表上：超过两张就不当超集信号，
    # 否则会把申万一级/竞价看板的排名改写成个股榜。A5 的 limit_up_count
    # 几乎只属于题材热度表，启发式才成立。
    wanted = tuple(dict.fromkeys(item.field for item in spec.order_by))
    alternatives: list[str] = []
    for field in wanted:
        owners = [
            name
            for name in _PUBLIC_DATASETS
            if name != spec.dataset
            and _DATASETS[name].population == "full"
            and field in _DATASETS[name].fields
        ]
        if len(owners) > 2:
            continue
        for name in owners:
            entry = f"{field}→{name}"
            if entry not in alternatives:
                alternatives.append(entry)
    if not alternatives:
        return ""
    return (
        f"覆盖面提示：dataset={spec.dataset} 只收当日子集，"
        "在它上面排序得到的是**子集内部的名次**，不是全市名次。"
        "若问的是全市分布（最多/集中在哪/排名），改用全集表："
        + "，".join(alternatives)
        + "。若确实只要子集内部的名次，忽略本提示。"
    )


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
            "description": _dataset_catalog_text(),
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
    reverse_after_fetch: bool = False


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
                if compiled.reverse_after_fetch:
                    rows = tuple(reversed(rows))
                    source_dates = tuple(reversed(source_dates))
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
            requested_time_range=_requested_time_range(spec),
        )
        return FinanceQueryResult(
            rows=rows,
            evidence=evidence,
            observation=observation,
            served_date=max(dates) if dates else None,
            audit=audit,
        )

    def dataset_max_date(
        self,
        spec: FinanceQuerySpec,
        *,
        information_cutoff: InformationCutoff,
        deadline: ResearchDeadline,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> str | None:
        """同一时间窗口内、**去掉 filters** 之后该数据集的最新日期。

        用途只有一个：把「该主体退出了集合」与「整条管道陈旧」分开。

        `FinanceQueryResult.served_date` 取的是**被筛结果**的 max。筛子集停在更早
        有两种截然不同的成因：

        - `fact_mainline_sector_daily` 整体有到 2026-08-14 的行，而「AI算力」最后
          一天是 08-07 → **该题材掉出了主线**。这是行业生命周期观察，是答案本身，
          不该当过期数据丢弃（2026-08-17 用户口径）。
        - 数据集整体也停在 08-07 → 同步管道真的落后了，仍须拒绝。

        两者在 `served_date` 上完全同码，只有再读一次「不加 filter 的 max」才能分开。

        **只在即将判 stale 时调用**：happy path 一次额外查询都不发。探针本身
        `limit=1` 且按时间倒序，成本是一行。
        """

        dataset = _DATASETS.get(spec.dataset)
        if dataset is None or not dataset.time_field:
            return None
        # spec 里的维度名未必等于物理列名（如 sector_code → sector_ts_code），
        # 也可能是语义别名（as_of → source_date）。优先认 time_field 本身。
        time_dimension = _semantic_time_dimension(dataset)
        if time_dimension is None:
            return None
        probe = replace(
            spec,
            filters=(),
            dimensions=(time_dimension,),
            metrics=(),
            group_by=(),
            order_by=(Order(field=time_dimension, direction="desc"),),
            limit=1,
        )
        try:
            result = self.run(
                probe,
                information_cutoff=information_cutoff,
                deadline=deadline,
                is_cancelled=is_cancelled,
            )
        except FinanceQueryError:
            # 探针失败不改变原判定——调用方按原来的 stale 处理。
            # 这里吞异常是刻意的：探针是为了**放宽**误判，它自己坏掉时
            # 必须落回更严的那一侧，不能把 stale 洗成通过。
            return None
        return result.served_date

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


def _semantic_time_dimension(dataset: _DatasetDefinition) -> str | None:
    """模型侧时间维名。``time_field`` 可能是语义别名（``as_of``），物理列另叫 ``source_date``。

    不能只用 ``field.column == dataset.time_field`` 反查：别名一旦拆开，T1b 和
    ``dataset_max_date`` 探针会静默关掉——LIMIT 切掉窗口末端、过期判定拿不到全集 max。
    """

    if dataset.time_field is None:
        return None
    if dataset.time_field in dataset.dimensions:
        return dataset.time_field
    return next(
        (
            name
            for name, field in dataset.dimensions.items()
            if field.column == dataset.time_field
        ),
        None,
    )


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
        if (
            not dataset.allow_future_time_range
            and spec.time_range.start is not None
            and spec.time_range.start > cutoff
        ):
            raise FinanceQueryValidationError(
                "time range conflicts with information cutoff"
            )
        if (
            not dataset.allow_future_time_range
            and spec.time_range.end is not None
            and spec.time_range.end > cutoff
        ):
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
    elif dataset.cutoff_column:
        # source_date 全仓语义是信息日。日历的 time_field 是发生日，
        # 流进去会被 registry 的 filter_future_dated 整批标成越界。
        cutoff_ident = _quote(dataset.cutoff_column)
        source_expr = f"CAST({cutoff_ident} AS DATE)"
        if group_by:
            source_expr = f"MAX({source_expr})"
        select_parts.append(f"{source_expr} AS __source_date")
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
        if dataset.cutoff_column:
            cutoff_ident = _quote(dataset.cutoff_column)
            where_parts.append(
                f"({cutoff_ident} IS NULL OR CAST({cutoff_ident} AS DATE) <= ?)"
            )
            parameters.append(cutoff.isoformat())
        elif not dataset.allow_future_time_range:
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
    # T1b：time_range + 按日期升序 + LIMIT 会先丢掉窗口末端（问句锚定日）。
    # 取数改倒序，返回前再翻回升序，观察顺序不变。只在「全部 order 都是时间维
    # 升序」时翻转，避免打乱 amount desc 这类次键。
    time_dimension = _semantic_time_dimension(dataset)
    fetch_orders = spec.order_by
    reverse_after_fetch = False
    if (
        spec.time_range is not None
        and time_dimension is not None
        and spec.order_by
        and all(
            item.field == time_dimension and item.direction == "asc"
            for item in spec.order_by
        )
    ):
        fetch_orders = tuple(
            replace(item, direction="desc") for item in spec.order_by
        )
        reverse_after_fetch = True
    if fetch_orders:
        sql += " ORDER BY " + ", ".join(
            f"{aliases[item.field]} {item.direction.upper()}" for item in fetch_orders
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
        reverse_after_fetch=reverse_after_fetch,
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
    # ESCAPE 后面必须是**一个字符**。这里曾写 f"... ESCAPE '\\\\'"，在 f-string 里
    # 求值成 SQL 字面量 `'\\'`——SQL 字符串里反斜杠不是转义符，故那是**两个字符**，
    # DuckDB 直接抛 `Invalid escape string. Escape string must be empty or one
    # character.`，整条 `contains` 查询在 SQL 层就炸了。
    #
    # 后果不是报错给用户看，而是**静默降级**：episode_tools 把
    # FinanceQueryExecutionError 归进兜底分支，返回 `ok=true` +「结构化数据源暂
    # 不可用」+ 零证据。模型看到 ok 以为查过了，实际一行都没拿到。
    # 2026-08-16 实测：题材题里 `contains` 是模型按主题名筛选的唯一自然写法
    # （`theme_name contains 算力`），4/4 个样本全部命中此 bug、全部空手而归；
    # 同表 `eq` / `in` / 无 filter 均正常，故与数据、编码、库路径都无关。
    return f"{column} LIKE ? ESCAPE '\\'", (f"%{escaped}%",)


# 哪些数据集的行产结构化观察值：subject 维度字段 + 指标白名单（**底层列名**，
# 与预取观察值同一指标空间，槽/门禁两侧才能对上）。只登记行级明细数据集；
# 聚合类/无主体数据集不产——没有主体的数进槽只会制造错绑。
_OBSERVATION_SUBJECT_FIELDS: dict[str, str] = {
    "sector_daily": "sector_name",
    "sector_stock_daily": "stock_name",
}
_OBSERVATION_METRIC_COLUMNS: dict[str, tuple[str, ...]] = {
    "sector_daily": ("pct_chg", "amount", "diff_ratio"),
    "sector_stock_daily": ("pct_chg", "amount"),
}


def _row_observations(
    rows: tuple[dict[str, object], ...],
    *,
    source_dates: tuple[str | None, ...],
    dataset_name: str,
    dataset: _DatasetDefinition,
) -> tuple[tuple[agent_research.StructuredObservation, ...], ...]:
    """把工具行里的数以机器可读形态挂回各自的证据卡。

    动机（生产实锤 run_20260821_152044_472523）：预取锚空表时模型靠本工具
    拿回全对的行写稿，但这些数没有 observations，删句连坐检测 / 槽补回 /
    数值门禁全都看不见它们，判官一刀下去真值随句子静默消失。带收据的
    工具行必须与预取行同权。

    同 (主体, 日期, 指标) 出现矛盾值时**该格不产观察值**——与
    ``asof_prefetch.sector_timeline_observations`` 同规则：把矛盾当事实
    投递，下游会把「有分歧」写成「就是这个数」。值相同的重复格照常产出。
    """

    subject_field = _OBSERVATION_SUBJECT_FIELDS.get(dataset_name)
    if subject_field is None:
        return tuple(() for _ in rows)
    metric_columns = _OBSERVATION_METRIC_COLUMNS[dataset_name]
    fields = dataset.fields
    seen: dict[tuple[str, str, str], set[float]] = {}
    per_row: list[list[tuple[str, str, str, float]]] = []
    for index, row in enumerate(rows):
        as_of = source_dates[index] or ""
        subject = row.get(subject_field)
        cells: list[tuple[str, str, str, float]] = []
        if as_of and isinstance(subject, str) and subject:
            for name, value in row.items():
                field = fields.get(name)
                if field is None or field.column not in metric_columns:
                    continue
                if value is None or isinstance(value, bool):
                    continue
                try:
                    number = float(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                seen.setdefault((subject, as_of, field.column), set()).add(number)
                cells.append((subject, as_of, field.column, number))
        per_row.append(cells)
    return tuple(
        tuple(
            agent_research.StructuredObservation(
                subject=subject, as_of=as_of, metric=metric, value=value
            )
            for subject, as_of, metric, value in cells
            if len(seen[(subject, as_of, metric)]) == 1
        )
        for cells in per_row
    )


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
    observations = _row_observations(
        rows,
        source_dates=source_dates,
        dataset_name=dataset_name,
        dataset=dataset,
    )
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
            observations=observations[index - 1],
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
