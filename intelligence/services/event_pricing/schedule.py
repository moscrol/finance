"""官方日程文件 ``references/calendars/official_release_schedule.<year>.json`` 的加载，与 LPR 规则派生。

文件只记「何时」。每条 entry 带 ``source_id`` 指回文件头 ``sources[]`` 里的 URL、公布日与抓取日；
``schedule_published_at`` 是「这份日程何时公开」——它决定该事件的事前窗能不能读作「预期」。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .params import EventParams

SOURCE_GRADE_OFFICIAL = "official"
SOURCE_GRADE_RULE = "rule_derived"
SOURCE_GRADE_RULE_FUTURE = "rule_derived_future"
FUTURE_MONTHS_BY_RULE = 3
SOURCE_GRADE_EDITORIAL = "editorial"
SOURCE_GRADE_BOTH = "both"
SOURCE_GRADE_CONFLICT = "conflict"


@dataclass(frozen=True)
class ScheduleEntry:
    event_class: str
    indicator: str
    event_date: str
    period: str | None
    time_local: str | None
    tz: str | None
    source_id: str
    schedule_published_at: str | None
    source_grade: str

    @property
    def event_date_obj(self) -> date:
        return date.fromisoformat(self.event_date)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    date.fromisoformat(s)  # 校验格式
    return s


def load_schedule_files(params: EventParams) -> tuple[list[ScheduleEntry], list[dict[str, Any]]]:
    """读全部年份文件。返回 (entries, sources_meta)。类不在参数白名单里的条目**跳过并记入 sources_meta.skipped**。"""
    entries: list[ScheduleEntry] = []
    meta: list[dict[str, Any]] = []
    for path in params.schedule_files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: 顶层必须是对象")
        sources = {str(s.get("id")): s for s in (doc.get("sources") or []) if isinstance(s, dict)}
        skipped: list[str] = []
        n_ok = 0
        for raw in doc.get("entries") or []:
            if not isinstance(raw, dict):
                continue
            cls = str(raw.get("event_class") or "")
            spec = params.classes.get(cls)
            if spec is None:
                skipped.append(cls)
                continue
            src = sources.get(str(raw.get("source_id")), {})
            ind = str(raw.get("indicator") or cls)
            if spec.indicators and ind not in spec.indicators:
                raise ValueError(f"{path}: {cls} 的 indicator {ind!r} 不在白名单 {spec.indicators}")
            entries.append(
                ScheduleEntry(
                    event_class=cls,
                    indicator=ind,
                    event_date=_iso(raw.get("event_date")) or "",
                    period=(str(raw["period"]) if raw.get("period") else None),
                    time_local=(str(raw["time_local"]) if raw.get("time_local") else None),
                    tz=(str(raw["tz"]) if raw.get("tz") else None),
                    source_id=str(raw.get("source_id") or ""),
                    schedule_published_at=_iso(src.get("schedule_published_at")),
                    source_grade=SOURCE_GRADE_OFFICIAL,
                )
            )
            n_ok += 1
        meta.append(
            {
                "file": str(path),
                "year": doc.get("year"),
                "entered_at": doc.get("entered_at"),
                "entries": n_ok,
                "skipped_classes": sorted(set(skipped)),
                "sources": [
                    {
                        "id": sid,
                        "url": s.get("url"),
                        "schedule_published_at": s.get("schedule_published_at"),
                        "fetched_at": s.get("fetched_at"),
                    }
                    for sid, s in sources.items()
                ],
            }
        )
    bad = [e for e in entries if not e.event_date]
    if bad:
        raise ValueError(f"日程条目缺 event_date: {bad[0]}")
    entries.sort(key=lambda e: (e.event_date, e.event_class, e.indicator))
    return entries, meta


def derive_lpr_by_rule(
    params: EventParams,
    trading_days: list[date],
    existing: list[ScheduleEntry],
) -> list[ScheduleEntry]:
    """没有官方条目的月份按「每月 20 日，遇非交易日顺延」派生 LPR 报价日。

    只在交易日历覆盖的月份内派生；派生日必须落在日历内（否则该月不出条目，日历末尾的月份如实缺）。
    A 股交易日历作银行间营业日代理：两者共用法定节假日。
    """
    if "cn_lpr" not in params.classes:
        return []
    have = {e.event_date[:7] for e in existing if e.event_class == "cn_lpr"}
    if not trading_days:
        return []
    days_sorted = sorted(trading_days)
    first, last = days_sorted[0], days_sorted[-1]
    out: list[ScheduleEntry] = []
    y, m = first.year, first.month
    end_y, end_m = last.year, last.month + FUTURE_MONTHS_BY_RULE
    while end_m > 12:
        end_y, end_m = end_y + 1, end_m - 12
    while (y, m) <= (end_y, end_m):
        key = f"{y:04d}-{m:02d}"
        target = date(y, m, params.lpr_day_of_month)
        # 目标日早于日历起点的月份不派生（无法判定顺延）
        if key not in have and target >= first:
            nxt = next((d for d in days_sorted if d >= target), None)
            if nxt is not None:
                event_date, grade = nxt, SOURCE_GRADE_RULE
            else:
                # 日历还没走到：只按周末顺延（没有节假日表），标 rule_derived_future，给 latest_known 报「下一期」用；
                # reaction_day 必为 NULL（超日历），不会成为锚点。
                event_date = target
                while event_date.weekday() >= 5:
                    event_date += timedelta(days=1)
                grade = SOURCE_GRADE_RULE_FUTURE
            out.append(
                ScheduleEntry(
                    event_class="cn_lpr",
                    indicator="cn_lpr",
                    event_date=event_date.isoformat(),
                    period=key,
                    time_local="09:00",
                    tz="Asia/Shanghai",
                    source_id="lpr_rule",
                    schedule_published_at=params.lpr_rule_published_at,
                    source_grade=grade,
                )
            )
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out
