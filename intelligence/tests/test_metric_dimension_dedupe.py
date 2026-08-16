"""metric 被同时抄进 dimensions 时归一化，而不是整条拒掉（R-20260816-23 更正版）。

**登记时的诊断是错的。** 原以为模型「看不到字段表」，实测 `dataset_field_hint()`
早已在 `episode_tools.py` 的工具描述里、且列全了 13 个 dataset 的字段。

真实形状（2026-08-16 生产 trace，4/4 个报错请求完全一致）：模型把 `dimensions`
当成「要返回的列」而不是「分组键」，于是把每个 metric 又抄了一份进 dimensions。
**字段一个都没错**，全是该 dataset 的合法字段，只是角色放错，整条查询被拒、
退回零证据；模型拿到重试提示后照样再犯（repairwin-8 连错两次）。

下面四组夹具**逐字取自那四个请求**，不是构造的。
"""

from __future__ import annotations

import pytest

from intelligence.services.finance_query import (
    FinanceQuerySpec,
    normalize_spec,
)

# 逐字取自 2026-08-16 生产 trace 的四个报错请求
_LIVE_CASES = {
    "repairwin-8/mainline_sector_daily": (
        "mainline_sector_daily",
        ("amount", "limit_up_count", "max_limit_height", "net_inflow_1d",
         "return_pct", "strength", "strength_change"),
        ("amount", "cycle_level", "cycle_status", "limit_up_count",
         "max_limit_height", "net_inflow_1d", "return_pct", "sector_name",
         "strength", "strength_change", "theme_name", "trade_date"),
    ),
    "repairwin-8/market_daily": (
        "market_daily",
        ("advancers", "index_return_pct", "limit_down", "limit_up",
         "strength_amount_pct", "strength_return_pct", "total_amount",
         "volume_ratio"),
        ("concentration_state", "index_return_pct", "leading_industry_1",
         "leading_industry_2", "leading_industry_3", "limit_down", "limit_up",
         "market_stage", "stage_day", "total_amount", "trade_date",
         "volume_ratio", "volume_state"),
    ),
    "repairwin-2/mainline_theme_daily": (
        "mainline_theme_daily",
        ("rank", "sector_count"),
        ("rank", "sector_count", "theme_code", "theme_name", "trade_date"),
    ),
    "repairwin-5/mainline_sector_daily": (
        "mainline_sector_daily",
        ("limit_up_count", "max_limit_height", "net_inflow_1d",
         "relative_amount", "return_pct", "strength"),
        ("cycle_level", "cycle_status", "limit_up_count", "max_limit_height",
         "net_inflow_1d", "relative_amount", "return_pct", "sector_name",
         "strength", "theme_name", "trade_date"),
    ),
}


@pytest.mark.parametrize("case", sorted(_LIVE_CASES))
def test_live_failing_requests_now_normalize(case: str) -> None:
    """四个真实报错请求归一化后，dimensions 里不再残留 metric。"""

    dataset, metrics, dimensions = _LIVE_CASES[case]
    spec = FinanceQuerySpec(
        dataset=dataset, metrics=metrics, dimensions=dimensions
    )
    normalized, notes = normalize_spec(spec)

    from intelligence.services.finance_query import _DATASETS

    definition = _DATASETS[dataset]
    leftover = [d for d in normalized.dimensions if d in definition.metrics]
    assert not leftover, f"{case}: dimensions 仍含 metric {leftover}"
    assert normalized.metrics == metrics, "metrics 不该被动"
    assert notes, "去重必须留下可审计的 note"


@pytest.mark.parametrize("case", sorted(_LIVE_CASES))
def test_real_dimensions_are_preserved(case: str) -> None:
    """只去掉重复的 metric，真正的分组键一个不能少。

    只断言「不再报错」会被一个「把 dimensions 清空」的实现骗过。
    """

    dataset, metrics, dimensions = _LIVE_CASES[case]
    from intelligence.services.finance_query import _DATASETS

    definition = _DATASETS[dataset]
    expected = tuple(d for d in dimensions if d in definition.dimensions)

    normalized, _ = normalize_spec(
        FinanceQuerySpec(dataset=dataset, metrics=metrics, dimensions=dimensions)
    )
    assert normalized.dimensions == expected


def test_metric_only_in_dimensions_is_left_alone() -> None:
    """字段只在 dimensions、metrics 里没有 → **不动**，交给校验器拒。

    这是刻意的边界：那种情况下「想分组」还是「想取值」无法判定，越权猜测会悄悄
    改掉查询含义。本条守的是「不要顺手把这条也一起归一化」。
    """

    spec = FinanceQuerySpec(
        dataset="mainline_sector_daily",
        metrics=(),
        dimensions=("trade_date", "strength"),
    )
    normalized, notes = normalize_spec(spec)
    assert "strength" in normalized.dimensions
    assert not notes


def test_undeclared_metric_survives_even_when_other_metrics_exist() -> None:
    """`metrics` 非空、但该字段没在里面声明 → 仍然不动。

    **这条是变异测试逼出来的。** 上一条用 `metrics=()`，被函数开头
    `not spec.metrics` 的短路挡住，根本走不到判据那一行——于是「去掉『必须已在
    metrics 声明』这个保守条件」的变异存活了。本条把 metrics 填成非空，让那行
    判据真正被执行到，守住「只去重复、不猜意图」这条边界。
    """

    spec = FinanceQuerySpec(
        dataset="mainline_sector_daily",
        metrics=("amount",),
        dimensions=("trade_date", "strength"),
    )
    normalized, notes = normalize_spec(spec)
    assert "strength" in normalized.dimensions, (
        "strength 没在 metrics 里声明过，不该被替模型决定角色"
    )
    assert "trade_date" in normalized.dimensions
    assert not notes


def test_clean_spec_is_untouched() -> None:
    """本来就写对的 spec 逐字段不变——归一化不得有副作用。"""

    spec = FinanceQuerySpec(
        dataset="mainline_sector_daily",
        metrics=("amount", "strength"),
        dimensions=("trade_date", "theme_name"),
    )
    normalized, notes = normalize_spec(spec)
    assert normalized.dimensions == spec.dimensions
    assert normalized.metrics == spec.metrics
    assert not notes
