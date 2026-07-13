"""Canonical A-share trading-day helpers for user-facing date semantics."""

from __future__ import annotations

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
