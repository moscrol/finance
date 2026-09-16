"""基准与固定平滑 recipe 的纯数学（spec 03 §5 / §6）。

基准 = 同事件、同宇宙、**发现窗**内的结果比例：各日先算比例，再对日期等权。
这样「某一天 400 个板块全涨」只算一天的证据，不会把同日共振冒充 400 个独立样本。

三条硬规则：

- 未知结果（None）**排除**，不转 0；一天全未知 → 那天不进分母。
- 跨窗 purge：事件日之后 h 个交易日若伸出窗末，剔除（读了下一窗的价格）。
- 无有效日期 → ``p_baseline=None`` + gap ``baseline_unavailable``，**不填 0.5**。

两桶 recipe ``(k+1)/(n+2)``：n = 有样本的日期数，k = 这些日比例之和。这是 Laplace 平滑
的固定配方，**不是**把加权数当成独立样本量的统计估计；n=0 返回 None 由调用方写 gap。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .contracts import Calendar, ContractError, digest, is_finite_number, iso_date

BASELINE_RECIPE: dict[str, Any] = {
    "kind": "discovery_event_days",
    "version": 1,
    "aggregation": "per-date proportion among known outcomes, then equal weight over dates with >=1 known",
    "unknown": "excluded from numerator and denominator; never coerced to 0",
    "purge": "events whose outcome window (as_of+1..as_of+h) crosses window.end are removed by calendar",
}
BASELINE_RECIPE_HASH = digest(BASELINE_RECIPE)

TWO_BUCKET_RECIPE: dict[str, Any] = {
    "recipe_id": "rule_two_bucket/v1",
    "version": 1,
    "buckets": ["condition_true", "condition_false"],
    "per_bucket": "n = dates with >=1 known outcome; k = sum of per-date proportions; p = (k+1)/(n+2)",
    "unknown_condition": "no forecast (gap arm_missing); never coerced to false",
    "unknown_outcome": "excluded; never coerced to 0",
}
TWO_BUCKET_RECIPE_HASH = digest(TWO_BUCKET_RECIPE)


@dataclass(frozen=True)
class OutcomeRow:
    """一条 (实体, 日) 的结果：value ∈ {0, 1, None}。None = 未知，不是 0。"""

    entity_id: str
    trade_date: str
    value: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise ContractError("OutcomeRow.entity_id 必须是非空字符串")
        iso_date(self.trade_date, field_name="OutcomeRow.trade_date")
        v = self.value
        if v is not None and (isinstance(v, bool) or v not in (0, 1)):
            raise ContractError(f"OutcomeRow.value 必须是 0 / 1 / None，得到 {v!r}")


def purge_cut_date(calendar: Calendar, end: str, horizon: int) -> str | None:
    """窗内最后一个「结果不跨窗」的事件日；日历不足 → None（全窗剔除）。"""
    idx = calendar.index(end) - int(horizon)
    if idx < 0:
        return None
    return calendar.dates[idx]


def daily_proportions(rows: Iterable[OutcomeRow]) -> dict[str, tuple[int, int]]:
    """{trade_date: (k_known, n_known)}；只数已知结果。"""
    out: dict[str, list[int]] = {}
    for row in rows:
        if row.value is None:
            continue
        slot = out.setdefault(row.trade_date, [0, 0])
        slot[0] += int(row.value)
        slot[1] += 1
    return {d: (k, n) for d, (k, n) in sorted(out.items())}


def equal_weight_mean(proportions: Mapping[str, tuple[int, int]]) -> tuple[float | None, int]:
    """日期等权平均比例与 n_dates；n_dates=0 → (None, 0)。"""
    ratios = [k / n for _d, (k, n) in sorted(proportions.items()) if n > 0]
    if not ratios:
        return None, 0
    return math.fsum(ratios) / len(ratios), len(ratios)


def smoothed_probability(n_dates: int, k_sum: float) -> float | None:
    """(k+1)/(n+2)。n=0 → None（写 gap，不返回 0.5 假装有数据）。"""
    if n_dates <= 0:
        return None
    if not is_finite_number(k_sum) or k_sum < 0 or k_sum > n_dates + 1e-9:
        raise ContractError(f"k_sum={k_sum!r} 必须在 [0, n_dates={n_dates}]")
    return (float(k_sum) + 1.0) / (float(n_dates) + 2.0)


def compute_baseline(
    rows: Iterable[OutcomeRow],
    *,
    window: Mapping[str, str],
    calendar: Calendar,
    horizon: int,
    source_hash: str,
) -> dict[str, Any]:
    """发现窗基准 → 可直接放进 ``StudyProtocol.baseline_spec`` 的冻结块。"""
    start, end = iso_date(window["start"]), iso_date(window["end"])
    if start > end:
        raise ContractError("window.start 晚于 end")
    cut = purge_cut_date(calendar, end, horizon)
    in_window = [r for r in rows if start <= r.trade_date <= end]
    kept = [r for r in in_window if cut is not None and r.trade_date <= cut]
    n_purged = len(in_window) - len(kept)
    n_unknown = sum(1 for r in kept if r.value is None)
    proportions = daily_proportions(kept)
    p, n_dates = equal_weight_mean(proportions)
    return {
        "kind": "discovery_event_days",
        "p_baseline": p,
        "n_dates": n_dates,
        "n_rows": len(kept),
        "n_unknown": n_unknown,
        "n_purged": n_purged,
        "source_hash": source_hash,
        "recipe_hash": BASELINE_RECIPE_HASH,
    }


def two_bucket_probabilities(
    rows: Iterable[tuple[bool | None, OutcomeRow]],
) -> dict[str, dict[str, Any]]:
    """按条件真 / 假分桶，条件未知的行**不进任何桶**。返回 {"true": {...}, "false": {...}}。"""
    buckets: dict[str, list[OutcomeRow]] = {"true": [], "false": []}
    n_condition_unknown = 0
    for condition, row in rows:
        if condition is None:
            n_condition_unknown += 1
            continue
        if not isinstance(condition, bool):
            raise ContractError(f"condition 必须是 bool 或 None，得到 {condition!r}")
        buckets["true" if condition else "false"].append(row)
    out: dict[str, dict[str, Any]] = {}
    for name, items in buckets.items():
        proportions = daily_proportions(items)
        n_dates = sum(1 for _d, (_k, n) in proportions.items() if n > 0)
        k_sum = math.fsum(k / n for _d, (k, n) in proportions.items() if n > 0)
        out[name] = {
            "n_dates": n_dates,
            "k_sum": k_sum,
            "n_rows": len(items),
            "n_unknown_outcome": sum(1 for r in items if r.value is None),
            "p": smoothed_probability(n_dates, k_sum),
        }
    out["condition_unknown_rows"] = {"n_rows": n_condition_unknown}
    return out


__all__ = [
    "BASELINE_RECIPE",
    "BASELINE_RECIPE_HASH",
    "OutcomeRow",
    "TWO_BUCKET_RECIPE",
    "TWO_BUCKET_RECIPE_HASH",
    "compute_baseline",
    "daily_proportions",
    "equal_weight_mean",
    "purge_cut_date",
    "smoothed_probability",
    "two_bucket_probabilities",
]
