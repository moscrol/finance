"""Versioned built-in historical features, with explicit missing values."""

from __future__ import annotations

from collections.abc import Sequence
from collections import defaultdict
import math
from typing import Any

from market_feature_store.signals import is_double_red, DOUBLE_RED_DESCRIPTION

FEATURE_VERSION = "history-features-v1"
FEATURES = {
    "return_pct": {
        "fields": ("pct_chg",),
        "unit": "percent",
        "rule": "compound every daily percentage in the declared window",
    },
    "amount_ratio": {
        "fields": ("amount",),
        "unit": "ratio",
        "rule": "last amount / first amount; require complete window and nonzero denominator",
    },
    "double_red_days": {
        "fields": ("pct_chg", "amount", "diff_ratio"),
        "unit": "trading_days",
        "rule": DOUBLE_RED_DESCRIPTION,
    },
    "max_double_red_streak": {
        "fields": ("pct_chg", "amount", "diff_ratio"),
        "unit": "trading_days",
        "rule": "maximum consecutive days satisfying " + DOUBLE_RED_DESCRIPTION,
    },
    "advancer_share": {
        "fields": ("members.pct_chg",),
        "unit": "ratio",
        "rule": "mean daily positive-return member share; denominator is unique observed membership each day",
    },
    "limit_up_share": {
        "fields": ("heat.limit_up_count", "heat.total_count"),
        "unit": "ratio",
        "rule": "mean daily limit_up_count / total_count; require exactly one heat scope per date",
    },
    "first_surge_lag": {
        "fields": ("pct_chg", "amount", "diff_ratio", "members.pct_chg"),
        "unit": "trading_days",
        "rule": "first member >=7% day minus first strict-double-red day; daily ordering only; no trigger is not_observed",
    },
    "market_relative_return_pct": {
        "fields": ("pct_chg", "market.sh_index_pct_chg"),
        "unit": "percentage_points",
        "rule": "entity compounded return minus index compounded return over identical days",
    },
}


def finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def compute_features(
    names: Sequence[str],
    days: Sequence[Any],
    entity_rows: Sequence[dict[str, Any]],
    *,
    members: Sequence[dict[str, Any]] = (),
    heat: Sequence[dict[str, Any]] = (),
    market: Sequence[dict[str, Any]] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """A missing day or input is unknown, including for a zero-valued statistic."""
    by_day = {row["trade_date"]: row for row in entity_rows}
    member_days: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    heat_days: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    market_days: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in members:
        member_days[row["trade_date"]].append(row)
    for row in heat:
        heat_days[row["trade_date"]].append(row)
    for row in market:
        market_days[row["trade_date"]].append(row)
    values: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    for name in names:
        definition = FEATURES[name]
        fields = definition["fields"]

        def complete_day(day: Any) -> bool:
            if day not in by_day:
                return False
            for field in fields:
                if field == "members.pct_chg":
                    selected = member_days[day]
                    if (
                        not selected
                        or len({r.get("stock_ts_code") for r in selected})
                        != len(selected)
                        or not all(finite(r.get("pct_chg")) for r in selected)
                    ):
                        return False
                elif field.startswith("heat."):
                    selected = heat_days[day]
                    if len(selected) != 1 or not all(
                        finite(selected[0].get(key))
                        for key in ("limit_up_count", "total_count")
                    ):
                        return False
                    if (
                        selected[0].get("total_count", 0) <= 0
                        or not 0
                        <= selected[0].get("limit_up_count", -1)
                        <= selected[0]["total_count"]
                    ):
                        return False
                elif field.startswith("market."):
                    selected = market_days[day]
                    if len(selected) != 1 or not finite(
                        selected[0].get(field.split(".")[1])
                    ):
                        return False
                elif not finite(by_day[day].get(field)):
                    return False
            return True

        good = [d for d in days if complete_day(d)]
        status = (
            "complete"
            if days and len(good) == len(days) and len(by_day) == len(entity_rows)
            else "missing"
        )
        coverage[name] = {
            "expected_dates": len(days),
            "nonnull_dates": len(good),
            "status": status,
            "missing_dates": [d for d in days if d not in good],
            "fields": list(fields),
        }
        value = None
        if status == "complete":
            rows = [by_day[d] for d in days]
            if name == "return_pct":
                value = (math.prod(1 + row["pct_chg"] / 100 for row in rows) - 1) * 100
            elif name == "amount_ratio":
                if rows[0]["amount"]:
                    value = rows[-1]["amount"] / rows[0]["amount"]
                else:
                    coverage[name]["status"] = "zero_denominator"
            elif name in {"double_red_days", "max_double_red_streak"}:
                flags = [
                    is_double_red(r["pct_chg"], r["diff_ratio"], r["amount"])
                    for r in rows
                ]
                if name == "double_red_days":
                    value = sum(flags)
                else:
                    value, streak = 0, 0
                    for flag in flags:
                        streak = streak + 1 if flag else 0
                        value = max(value, streak)
            elif name == "advancer_share":
                value = sum(
                    sum(r["pct_chg"] > 0 for r in member_days[d]) / len(member_days[d])
                    for d in days
                ) / len(days)
            elif name == "limit_up_share":
                value = sum(
                    heat_days[d][0]["limit_up_count"] / heat_days[d][0]["total_count"]
                    for d in days
                ) / len(days)
            elif name == "market_relative_return_pct":
                entity = math.prod(1 + r["pct_chg"] / 100 for r in rows)
                baseline = math.prod(
                    1 + market_days[d][0]["sh_index_pct_chg"] / 100 for d in days
                )
                value = (entity - baseline) * 100
            elif name == "first_surge_lag":
                member_first = next(
                    (
                        i
                        for i, d in enumerate(days)
                        if any(r["pct_chg"] >= 7 for r in member_days[d])
                    ),
                    None,
                )
                sector_first = next(
                    (
                        i
                        for i, r in enumerate(rows)
                        if is_double_red(r["pct_chg"], r["diff_ratio"], r["amount"])
                    ),
                    None,
                )
                if member_first is not None and sector_first is not None:
                    value = member_first - sector_first
                else:
                    coverage[name]["status"] = "not_observed"
        values[name] = value
    return values, coverage
