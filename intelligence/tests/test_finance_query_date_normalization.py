"""Harness 代偿：filters 里的日期条件自动搬进 time_range。

背景（实测，不是假想）：一轮真实 research 里模型对同一个错犯了两次——把
trade_date 放进 filters，两次都被 `date filters must use time_range` 拒掉，
两个工具槽白烧，最终 deadline_exhausted 降级。工具的重试提示写得很清楚，
但隔一轮又犯。日期该放 time_range 是本引擎的局部约定而非 SQL 常识，
所以由 Harness 代偿，不指望提示词。

这些用例的重点不是「能搬」，而是**只在语义完全等价时才搬**：静默改变查询
语义比报错坏得多，报错只浪费一次调用，多带一天数据会让答案引用一条模型
没要求的记录。
"""

from __future__ import annotations

from datetime import date

from intelligence.services.finance_query import (
    FinanceQuerySpec,
    QueryFilter,
    TimeRange,
    normalize_spec,
)


def _spec(*filters: QueryFilter, time_range: TimeRange | None = None) -> FinanceQuerySpec:
    return FinanceQuerySpec(
        dataset="market_daily",
        metrics=("index_close",),
        dimensions=("trade_date",),
        filters=filters,
        time_range=time_range,
    )


def test_eq_date_filter_becomes_closed_single_day_range():
    # eq 与闭区间单日等价：编译期 time_range 两端都是闭端。
    normalized, notes = normalize_spec(
        _spec(QueryFilter("trade_date", "eq", "2026-08-06"))
    )

    assert normalized.filters == ()
    assert normalized.time_range == TimeRange(
        start=date(2026, 8, 6),
        end=date(2026, 8, 6),
    )
    assert len(notes) == 1
    # 说明必须告诉模型正确写法，否则它只知道「这次通了」，下次还犯。
    assert "time_range" in notes[0]


def test_gte_and_lte_pair_becomes_one_range():
    normalized, notes = normalize_spec(
        _spec(
            QueryFilter("trade_date", "gte", "2026-07-01"),
            QueryFilter("trade_date", "lte", "2026-08-06"),
        )
    )

    assert normalized.filters == ()
    assert normalized.time_range == TimeRange(
        start=date(2026, 7, 1),
        end=date(2026, 8, 6),
    )
    assert notes


def test_non_date_filters_are_untouched():
    # 只搬时间字段，其他筛选原样保留——代偿不能顺手改写模型的其他意图。
    kept = QueryFilter("market_stage", "eq", "底部横盘阶段")
    normalized, notes = normalize_spec(
        _spec(kept, QueryFilter("trade_date", "eq", "2026-08-06"))
    )

    assert normalized.filters == (kept,)
    assert normalized.time_range == TimeRange(
        start=date(2026, 8, 6),
        end=date(2026, 8, 6),
    )
    assert notes


def test_strict_inequality_is_not_moved():
    # gt/lt 是开区间，time_range 编译成 >=/<=。搬过去会静默多带一天，
    # 那比报错坏得多：报错只浪费一次调用，多带一天会污染答案引用的证据。
    # 原样退回后，_compile_query 里的 `date filters must use time_range` 照常报错。
    original = _spec(QueryFilter("trade_date", "gt", "2026-08-01"))
    normalized, notes = normalize_spec(original)

    assert normalized.filters == original.filters
    assert normalized.time_range is None
    assert notes == ()


def test_set_operators_are_not_moved():
    # in/ne/contains 表达集合而非区间，time_range 无法表示。
    for op in ("in", "ne", "contains"):
        original = _spec(QueryFilter("trade_date", op, "2026-08-06"))
        normalized, notes = normalize_spec(original)

        assert normalized.filters == original.filters, op
        assert normalized.time_range is None, op
        assert notes == (), op


def test_explicit_time_range_wins_over_filter():
    # 端点已被模型显式指定时不代偿：覆盖掉明确意图比拒绝执行更危险。
    explicit = TimeRange(start=date(2026, 7, 1), end=date(2026, 7, 31))
    original = _spec(
        QueryFilter("trade_date", "eq", "2026-08-06"),
        time_range=explicit,
    )
    normalized, notes = normalize_spec(original)

    assert normalized.time_range == explicit
    assert normalized.filters == original.filters
    assert notes == ()


def test_partial_range_accepts_complementary_filter():
    # 只占了 start 时，filters 里的 lte 可以补 end——两者不冲突。
    original = _spec(
        QueryFilter("trade_date", "lte", "2026-08-06"),
        time_range=TimeRange(start=date(2026, 7, 1)),
    )
    normalized, notes = normalize_spec(original)

    assert normalized.time_range == TimeRange(
        start=date(2026, 7, 1),
        end=date(2026, 8, 6),
    )
    assert normalized.filters == ()
    assert notes


def test_contradictory_merge_is_refused():
    # 合并后 start > end：原样退回让原有校验报错，
    # 而不是把一个必然为空的结果伪装成查询成功。
    original = _spec(
        QueryFilter("trade_date", "gte", "2026-08-06"),
        QueryFilter("trade_date", "lte", "2026-07-01"),
    )
    normalized, notes = normalize_spec(original)

    assert normalized.filters == original.filters
    assert normalized.time_range is None
    assert notes == ()


def test_non_iso_value_is_left_for_the_validator():
    original = _spec(QueryFilter("trade_date", "eq", "上周五"))
    normalized, notes = normalize_spec(original)

    assert normalized.filters == original.filters
    assert normalized.time_range is None
    assert notes == ()


def test_normalization_is_idempotent():
    # 引擎内部与工具层会各调一次，重复调用必须是 no-op。
    once, first_notes = normalize_spec(
        _spec(QueryFilter("trade_date", "eq", "2026-08-06"))
    )
    twice, second_notes = normalize_spec(once)

    assert twice == once
    assert first_notes
    assert second_notes == ()


def test_provider_alias_and_date_move_compose():
    # 两个归一化在同一入口里串联：别名先换名，日期再搬位置。
    normalized, notes = normalize_spec(
        FinanceQuerySpec(
            dataset="market_daily",
            metrics=("limit_up_count",),
            dimensions=("trade_date",),
            filters=(QueryFilter("trade_date", "eq", "2026-08-06"),),
        )
    )

    assert normalized.metrics == ("limit_up",)
    assert normalized.time_range == TimeRange(
        start=date(2026, 8, 6),
        end=date(2026, 8, 6),
    )
    assert notes
