"""时间工具：解析 / 分档 / 比较。全包唯一处理时钟语义的地方。

三种时间分开（总合同 §5 第 4 条）：市场日 ``as_of``、知识截止 ``knowledge_cutoff``、事件时间与记录时间。
这里只提供机械操作；「哪个时间该用哪个」由 ``rules.py`` 决定。

粒度判定（``classify_time``）：

- 带时区的 ISO 时刻 → ``datetime``（能判精确先后）
- 只有日期、或无时区的时刻 → ``date``（无时区的时刻不能与截止时刻比较，按只到日处理，不猜时区）
- 解析不了 → ``unknown``
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from intelligence.services.research_diagnostics.contracts import TimePoint


def parse_instant(text: str | None) -> datetime | None:
    """带时区的 ISO 时刻 → UTC datetime；无时区 / 只有日期 / 解析失败 → None。"""
    s = str(text or "").strip()
    if not s or len(s) <= 10:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def parse_day(text: str | None) -> str | None:
    s = str(text or "").strip()
    if len(s) < 10:
        return None
    try:
        return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        return None


def classify_time(text: str | None) -> TimePoint:
    s = str(text or "").strip()
    if not s:
        return TimePoint.unknown()
    if parse_instant(s) is not None:
        return TimePoint(s, "datetime")
    day = parse_day(s)
    if day is not None:
        return TimePoint(s, "date")
    return TimePoint.unknown()


def day_of(text: str | None) -> str | None:
    return parse_day(text)


def add_days(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def instant_le(a: str | None, b: str | None) -> bool | None:
    """a ≤ b（精确时刻比较）；任一边不是带时区时刻 → None（不可判）。"""
    da, db = parse_instant(a), parse_instant(b)
    if da is None or db is None:
        return None
    return da <= db


def instant_lt(a: str | None, b: str | None) -> bool | None:
    da, db = parse_instant(a), parse_instant(b)
    if da is None or db is None:
        return None
    return da < db


def day_le(a: str | None, b: str | None) -> bool | None:
    """按日比较 a ≤ b；任一边没有日期 → None。"""
    da, db = parse_day(a), parse_day(b)
    if da is None or db is None:
        return None
    return da <= db


def known_by(fact_time: str | None, at: str | None) -> bool | None:
    """某事实（记录 / 生效于 ``fact_time``）在行为时刻 ``at`` 是否已可知。

    两边都是精确时刻按时刻比；否则退到按日比（fact 的日 ≤ at 的日）。任一边没有时间 → None。
    退到按日是保守方向：同一天内的先后判不了，就按「当天已可知」处理，但调用方要据此
    把 pit_grade 降到 trade_date_only。
    """
    precise = instant_le(fact_time, at)
    if precise is not None:
        return precise
    return day_le(fact_time, at)


def in_range(day: str | None, start: str, end: str) -> bool | None:
    d = parse_day(day)
    if d is None:
        return None
    return start <= d <= end


def weakest_pit(grades: list[str]) -> str:
    order = {"strict": 0, "trade_date_only": 1, "unverifiable": 2}
    if not grades:
        return "unverifiable"
    return max(grades, key=lambda g: order.get(g, 2))
