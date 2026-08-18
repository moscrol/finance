"""Shared metric registry: key → unit → caliber → aliases.

Lifted from ``market_timeseries`` so D0 rendering, retrieval, and the
acceptance scorer consume one table. Adding a metric means registering it
here — do not splice user text into SQL, and do not keep a second alias list
in the scorer overlay.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from market_feature_store.signals import DOUBLE_RED_SQL


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unit: str
    aliases: tuple[str, ...]
    caliber: str  # 口径说明（表.列），进入数据块与判分别名


# 白名单指标注册表。新增指标只允许在这里登记（key → 固定查询口径），
# 不允许把用户问题文本拼进 SQL。
METRICS: dict[str, MetricSpec] = {
    "limit_up": MetricSpec(
        "limit_up", "涨停家数", "家", ("涨停家数", "涨停数", "涨停"),
        "fact_market_daily.limit_up",
    ),
    "limit_down": MetricSpec(
        "limit_down", "跌停家数", "家", ("跌停家数", "跌停数", "跌停"),
        "fact_market_daily.limit_down",
    ),
    "advancers": MetricSpec(
        "advancers", "涨家数", "家", ("涨家数", "上涨家数", "涨跌家数"),
        "fact_market_daily.advancers",
    ),
    "total_amount": MetricSpec(
        "total_amount", "全市成交额", "亿元", ("全市成交额", "成交额", "总成交", "成交量"),
        "fact_market_daily.total_amount（亿元）",
    ),
    "max_boards": MetricSpec(
        "max_boards", "连板最高高度", "板", ("连板高度", "连板最高", "最高板", "最高连板", "连板"),
        "fact_limit_advance_daily 当日 max(boards)",
    ),
    "promotion_rate": MetricSpec(
        "promotion_rate", "首板晋级率", "", ("晋级率", "晋级"),
        "fact_limit_advance_daily 当日 boards=2 行携带的首板→2板晋级率原文",
    ),
    "double_red_count": MetricSpec(
        "double_red_count", "双红板块数", "个", ("双红板块", "双红题材", "双红"),
        f"fact_sector_daily 当日满足 {DOUBLE_RED_SQL} 的板块数（严格双红定义）",
    ),
}

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_DATE_TOKEN_RE = re.compile(
    r"\d{4}-\d{1,2}-\d{1,2}|\d{4}年\d{1,2}月\d{1,2}日|\b20\d{2}\b"
)
_SCALE_SUFFIX = (
    ("万亿", 10000.0, "亿元"),
    ("亿", 1.0, "亿元"),
    ("万", 0.0001, "亿元"),
)


def metric_aliases_for_field(field_name: str) -> tuple[str, ...]:
    """Map an expect_facts field (possibly ``date.metric``) onto registry aliases."""

    key = str(field_name or "").rsplit(".", 1)[-1]
    spec = METRICS.get(key)
    return spec.aliases if spec is not None else ()


def spec_for_field(field_name: str) -> MetricSpec | None:
    key = str(field_name or "").rsplit(".", 1)[-1]
    return METRICS.get(key)


def bind_measured_value(text: str) -> tuple[str, float | int, str, dict[str, object]] | None:
    """Bind a measured value when exactly one registry metric and one number appear.

    Returns ``(metric_key, value, unit, provenance)``. Scale words such as
    「万亿」stay in provenance so the stored unit matches the registry.
    Dates are stripped before counting numbers so ``2026-07-21 成交额 2.96万亿``
    still binds.
    """

    blob = str(text or "")
    if not blob:
        return None
    matched = [
        spec for spec in METRICS.values() if any(alias in blob for alias in spec.aliases)
    ]
    if len(matched) != 1:
        return None
    hit = matched[0]
    numeric_blob = _DATE_TOKEN_RE.sub(" ", blob)
    matches = list(_NUMBER_RE.finditer(numeric_blob))
    if len(matches) != 1:
        return None
    match = matches[0]
    raw = match.group(0)
    number: float | int = float(raw) if "." in raw else int(raw)
    rest = numeric_blob[match.end() :].lstrip()
    provenance: dict[str, object] = {}
    unit = hit.unit
    for suffix, factor, canonical_unit in _SCALE_SUFFIX:
        if rest.startswith(suffix) and hit.unit == canonical_unit and factor != 1.0:
            provenance["unit_conversion"] = f"{suffix}→{canonical_unit} ×{factor:g}"
            provenance["raw_value"] = number
            provenance["raw_unit"] = suffix
            number = float(number) * factor
            break
    return hit.key, number, unit, provenance
