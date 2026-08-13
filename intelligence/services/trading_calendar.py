"""Canonical A-share trading-day helpers for user-facing date semantics."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path


_SSE_CLOSURES: dict[int, frozenset[date]] = {
    2026: frozenset(
        {
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 2, 16),
            date(2026, 2, 17),
            date(2026, 2, 18),
            date(2026, 2, 19),
            date(2026, 2, 20),
            date(2026, 2, 23),
            date(2026, 4, 6),
            date(2026, 5, 1),
            date(2026, 5, 4),
            date(2026, 5, 5),
            date(2026, 6, 19),
            date(2026, 9, 25),
            date(2026, 10, 1),
            date(2026, 10, 2),
            date(2026, 10, 5),
            date(2026, 10, 6),
            date(2026, 10, 7),
        }
    ),
}


def _known_trading_days(db_path: str | Path | None) -> list[date]:
    if db_path is None:
        return []
    path = Path(db_path)
    if not path.is_file():
        return []

    try:
        import duckdb

        connection = duckdb.connect(str(path), read_only=True)
    except Exception:
        return []
    try:
        rows = connection.execute(
            "select distinct trade_date from fact_stock_daily order by trade_date"
        ).fetchall()
    except Exception:
        return []
    finally:
        connection.close()
    return [date.fromisoformat(str(row[0])) for row in rows]


# 只认带年份的完整写法。无年份写法（7.25 / 7月25日）的年份归属已由
# query_understanding.market_review_requested_date 处理，但该模块 import 本层的
# 反方向（query_understanding → task_frame → 本模块），这里不能回头引用；
# 无年份日期直接放过（返回 None），宁可少判也不猜年份。
_FULL_DATE_RE = re.compile(
    r"(20\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]?\s*(\d{1,2})\s*日?"
)


def previous_scheduled_trading_day(value: date) -> date | None:
    """按周末 + 交易所公告休市表向前找最近交易日；年份不在表内 fail closed。"""

    candidate = value - timedelta(days=1)
    for _ in range(20):
        closures = _SSE_CLOSURES.get(candidate.year)
        if closures is None:
            return None
        if candidate.weekday() < 5 and candidate not in closures:
            return candidate
        candidate -= timedelta(days=1)
    return None


def non_trading_day_note(value: date) -> str | None:
    """该日确定性休市时返回一句可直接引用的事实，交易日/无法判定返回 None。

    周末判定不依赖休市表（任何年份成立）；工作日只有当年休市表存在且命中
    才判休市——表外年份的工作日无法证明休市，fail closed 返回 None，
    宁可漏报也不把交易日说成休市。
    """

    weekday = value.weekday()
    if weekday == 5:
        reason = "周六"
    elif weekday == 6:
        reason = "周日"
    else:
        closures = _SSE_CLOSURES.get(value.year)
        if closures is None or value not in closures:
            return None
        reason = "交易所公告休市日"
    previous = previous_scheduled_trading_day(value)
    tail = (
        f"；其前一交易日为 {previous.isoformat()}"
        if previous is not None
        else ""
    )
    return f"{value.isoformat()} 为{reason}，A股休市，该日无行情数据{tail}"


def question_non_trading_note(question: str) -> str | None:
    """问题里出现的第一个「确定性休市日」的事实说明；没有则 None。

    生产形状（2026-08-13 R15-C1/C2）：「2026-07-25 市场怎么样」（周六）与
    「2026-02-17 涨停家数多少」（春节休市）都走完了整条研究链，烧几十秒后
    答「证据不足」——而「这天休市」是纯日历事实，一行代码就能判定。
    判定结果作为 task frame 假设注入，模型据此直接回答，不再盲查。
    """

    for match in _FULL_DATE_RE.finditer(str(question or "")):
        try:
            value = date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
        except ValueError:
            continue
        note = non_trading_day_note(value)
        if note is not None:
            return note
    return None


def next_trading_day(
    anchor: str | date | None,
    *,
    db_path: str | Path | None = None,
    known_trading_days: Iterable[str | date] | None = None,
) -> str | None:
    """Return the next verified A-share trading day, or ``None`` when unknown.

    Historical and preloaded future dates come from DuckDB first. If ``anchor`` is
    the latest stored date, the official SSE annual closure schedule extends the
    calendar. Unsupported years fail closed instead of guessing with ``+1 day``.
    """

    if anchor is None:
        return None
    try:
        anchor_date = (
            anchor if isinstance(anchor, date) else date.fromisoformat(anchor)
        )
    except ValueError:
        return None
    raw_days = (
        list(known_trading_days)
        if known_trading_days is not None
        else _known_trading_days(db_path)
    )
    try:
        calendar = sorted(
            {
                item if isinstance(item, date) else date.fromisoformat(str(item))
                for item in raw_days
            }
        )
    except ValueError:
        return None
    if not calendar or anchor_date not in calendar:
        return None

    stored_future = next((item for item in calendar if item > anchor_date), None)
    if stored_future is not None:
        return stored_future.isoformat()

    candidate = anchor_date + timedelta(days=1)
    for _ in range(20):
        closures = _SSE_CLOSURES.get(candidate.year)
        if closures is None:
            return None
        if candidate.weekday() < 5 and candidate not in closures:
            return candidate.isoformat()
        candidate += timedelta(days=1)
    return None


def trading_day_prompt_block(
    trade_date: str | None,
    *,
    db_path: str | Path | None,
) -> str:
    if not trade_date:
        return (
            "## 交易日历约束\n"
            "- 当前研究日期无法确认。\n"
            "- 无法确认下一交易日；不得猜测或使用自然日加一天。"
        )
    next_day = next_trading_day(trade_date, db_path=db_path)
    if next_day is None:
        return (
            "## 交易日历约束\n"
            f"- 当前研究交易日：{trade_date}。\n"
            "- 无法确认下一交易日；如需表达 T+1，只能写“下一交易日（日期待交易日历确认）”，"
            "不得输出猜测日期。"
        )
    return (
        "## 交易日历约束\n"
        f"- 当前研究交易日：{trade_date}。\n"
        f"- 下一交易日：{next_day}。\n"
        "- T+1、明天、下一交易日均指上述日期，禁止按自然日加一天。"
    )
