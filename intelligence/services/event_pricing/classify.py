"""编辑日历（``fact_event_daily``）行 → 事件类。白名单正则 + 排除词 + ``event_type``，不匹配即 ``unparsed``，不猜。

分类顺序 = 参数文件里 ``event_classes`` 的书写顺序：market 标题类在前、sector 类型类在后。一行命中多个
market 类记 ``ambiguous_class`` 进缺口表，不入任何类。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from .params import EventClassSpec, EventParams

_MONTH_RE = re.compile(r"(?<!\d)(1[0-2]|[1-9])\s*月")
_YEAR_RE = re.compile(r"(20\d\d)\s*年")


@dataclass(frozen=True)
class EditorialRow:
    event_id: str
    event_date: str
    title: str
    event_type: str | None
    sectors_json: str | None


@dataclass(frozen=True)
class ClassifiedEvent:
    event_class: str
    indicator: str
    event_date: str
    period: str | None
    event_id: str
    title: str
    sector_codes: tuple[str, ...]
    sector_names: tuple[str, ...]


@dataclass(frozen=True)
class ClassifyGap:
    event_id: str
    event_date: str
    reason: str
    detail: str


def _contains_any(title: str, words: tuple[str, ...]) -> bool:
    t = title.upper()
    return any(w.upper() in t for w in words)


def _title_matches(title: str, spec: EventClassSpec) -> bool:
    if not spec.title_any:
        return False
    if not _contains_any(title, spec.title_any):
        return False
    if spec.title_all_any and not _contains_any(title, spec.title_all_any):
        return False
    if spec.title_none and _contains_any(title, spec.title_none):
        return False
    return True


def parse_sectors(raw: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``sectors`` 列是 JSON 列表 ``[{ts_code, name, type}]``；解析失败或为空返回空元组。"""
    if not raw:
        return (), ()
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return (), ()
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            return (), ()
    if not isinstance(data, list):
        return (), ()
    codes: list[str] = []
    names: list[str] = []
    for item in data:
        if isinstance(item, dict):
            code = str(item.get("ts_code") or "").strip()
            if code and code not in codes:
                codes.append(code)
                names.append(str(item.get("name") or "").strip())
        elif isinstance(item, str) and item.strip() and item.strip() not in codes:
            codes.append(item.strip())
            names.append("")
    return tuple(codes), tuple(names)


def parse_period(title: str, event_date: str, spec: EventClassSpec) -> str | None:
    """所属期。``title_month``：标题里的「N月」，年份取标题年或事件年（跨年回绕：1 月发 12 月数据）。"""
    kind = spec.period_kind
    if kind == "none":
        return None
    if kind == "event_date":
        return event_date
    if kind == "release_month":
        return event_date[:7]
    m = _MONTH_RE.search(title)
    if not m:
        return None
    month = int(m.group(1))
    ed = date.fromisoformat(event_date)
    ym = _YEAR_RE.search(title)
    year = int(ym.group(1)) if ym else ed.year
    if not ym and month > ed.month + 1:
        year -= 1
    return f"{year:04d}-{month:02d}"


def _indicators_for(title: str, spec: EventClassSpec) -> tuple[str, ...]:
    if len(spec.indicators) <= 1:
        return spec.indicators or ("",)
    # 多指标类（CPI / PPI 同日）：按标题里出现的指标名拆；都没出现 → 全部指标
    t = title.upper()
    hits = tuple(ind for ind in spec.indicators if ind.rsplit("_", 1)[-1].upper() in t)
    return hits or spec.indicators


def classify_row(row: EditorialRow, params: EventParams) -> tuple[list[ClassifiedEvent], ClassifyGap | None]:
    title = (row.title or "").strip()
    codes, names = parse_sectors(row.sectors_json)
    market_hits = [s for s in params.classes.values() if s.scope == "market" and _title_matches(title, s)]
    if len(market_hits) > 1:
        return [], ClassifyGap(
            row.event_id, row.event_date, "ambiguous_class", ",".join(s.name for s in market_hits) + " | " + title[:80]
        )
    if len(market_hits) == 1:
        spec = market_hits[0]
        period = parse_period(title, row.event_date, spec)
        out = [
            ClassifiedEvent(spec.name, ind, row.event_date, period, row.event_id, title, codes, names)
            for ind in _indicators_for(title, spec)
        ]
        return out, None
    et = (row.event_type or "").strip()
    for spec in params.classes.values():
        if spec.scope != "sector" or not spec.event_type_in:
            continue
        if et not in spec.event_type_in:
            continue
        if spec.require_sectors and not codes:
            return [], ClassifyGap(row.event_id, row.event_date, "sector_class_without_sectors", f"{spec.name} | {title[:80]}")
        return [ClassifiedEvent(spec.name, "", row.event_date, None, row.event_id, title, codes, names)], None
    return [], ClassifyGap(row.event_id, row.event_date, "unparsed", f"{et or '-'} | {title[:80]}")


def classify_rows(rows: list[EditorialRow], params: EventParams) -> tuple[list[ClassifiedEvent], list[ClassifyGap]]:
    events: list[ClassifiedEvent] = []
    gaps: list[ClassifyGap] = []
    for row in rows:
        ev, gap = classify_row(row, params)
        events.extend(ev)
        if gap is not None:
            gaps.append(gap)
    return events, gaps


def summarize(events: list[ClassifiedEvent], gaps: list[ClassifyGap]) -> dict[str, Any]:
    by_class: dict[str, int] = {}
    for e in events:
        by_class[e.event_class] = by_class.get(e.event_class, 0) + 1
    by_reason: dict[str, int] = {}
    for g in gaps:
        by_reason[g.reason] = by_reason.get(g.reason, 0) + 1
    return {"classified_rows": len(events), "by_class": by_class, "gaps": by_reason}
