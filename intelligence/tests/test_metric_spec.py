from __future__ import annotations

from intelligence.services import market_timeseries, metric_spec
from intelligence.services.metric_spec import METRICS, bind_measured_value, metric_aliases_for_field


def test_market_timeseries_reexports_the_same_registry() -> None:
    assert market_timeseries.METRICS is metric_spec.METRICS
    assert market_timeseries.MetricSpec is metric_spec.MetricSpec


def test_bind_measured_value_scales_wan_yi_into_yi_yuan() -> None:
    bound = bind_measured_value("两市成交额约2.96万亿")
    assert bound is not None
    key, value, unit, provenance = bound
    assert key == "total_amount"
    assert value == 29600.0
    assert unit == "亿元"
    assert provenance["raw_unit"] == "万亿"
    assert provenance["raw_value"] == 2.96


def test_bind_measured_value_strips_dates_before_counting_numbers() -> None:
    bound = bind_measured_value("2026-07-21 全市成交额 21949.97 亿元")
    assert bound is not None
    key, value, unit, _provenance = bound
    assert key == "total_amount"
    assert value == 21949.97
    assert unit == "亿元"


def test_bind_measured_value_abstains_when_two_metrics_or_no_number() -> None:
    assert bind_measured_value("涨停12家、跌停3家") is None
    assert bind_measured_value("涨停家数上升") is None
    assert bind_measured_value("没有口径的 2.96万亿") is None


def test_metric_aliases_for_dated_field() -> None:
    aliases = metric_aliases_for_field("2026-07-21.total_amount")
    assert "全市成交额" in aliases
    assert "成交额" in aliases
    assert metric_aliases_for_field("close") == ()
    assert METRICS["limit_up"].caliber == "fact_market_daily.limit_up"
