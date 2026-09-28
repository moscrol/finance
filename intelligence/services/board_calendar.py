"""Read-only projection for the trading calendar and consecutive-board ladder.

The calendar is anchored on ``fact_market_daily`` (the market database's
observed trading dates), while board members come from
``fact_limit_advance_daily``.  These are deliberately kept as separate
signals: a trading day with no board rows is not silently turned into a
holiday, and a stale board feed is disclosed in the response.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb

from market_feature_store.trading_days import trading_day_verdict


BOARD_TABLE = "fact_limit_advance_daily"
MARKET_TABLE = "fact_market_daily"


def _date_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _parse_date(value: str | date | None, *, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD") from exc


def _month_bounds(month: str | None) -> tuple[date, date]:
    if month is None:
        today = date.today()
        return today.replace(day=1), today.replace(day=monthrange(today.year, today.month)[1])
    try:
        if len(month) != 7 or month[4] != "-":
            raise ValueError
        year_text, month_text = month[:4], month[5:]
        if not year_text.isdigit() or not month_text.isdigit():
            raise ValueError
        first = date(int(year_text), int(month_text), 1)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("month 必须是 YYYY-MM") from exc
    return first, first.replace(day=monthrange(first.year, first.month)[1])


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table],
        ).fetchone()[0]
    )


def _recommended_min_boards(
    con: duckdb.DuckDBPyConnection,
    *,
    start: date,
    end: date,
) -> int:
    """Keep the default readable without hiding the 2-board option.

    The product rule is intentionally small and deterministic: if a month has
    more than 12 two-board-or-higher names on a typical trading day, default to
    three boards.  The threshold is based on the board table itself, not on a
    UI guess, and callers can always request either 2 or 3 explicitly.
    """

    row = con.execute(
        f"""
        SELECT COALESCE(AVG(day_count), 0)
        FROM (
            SELECT trade_date, COUNT(*) AS day_count
            FROM {BOARD_TABLE}
            WHERE trade_date BETWEEN ? AND ? AND boards >= 2
            GROUP BY trade_date
        )
        """,
        [start, end],
    ).fetchone()
    average = float(row[0] or 0) if row else 0.0
    return 3 if average > 12 else 2


def _group_boards(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for trade_date, code, name, boards, theme, pct_chg in rows:
        if boards is None:
            continue
        level = int(boards)
        grouped.setdefault(level, []).append(
            {
                "stock_ts_code": str(code or ""),
                "stock_name": str(name or code or "未知个股"),
                "boards": level,
                "theme": str(theme) if theme else None,
                "pct_chg": float(pct_chg) if pct_chg is not None else None,
            }
        )
    return [
        {"boards": level, "stocks": sorted(stocks, key=lambda item: item["stock_name"])}
        for level, stocks in sorted(grouped.items(), reverse=True)
    ]


def build_board_calendar(
    db_path: str | Path,
    *,
    month: str | None = None,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    min_boards: int | None = None,
) -> dict[str, Any]:
    """Return one month (or an explicit date range) of board-calendar data."""

    if month is not None and (start_date is not None or end_date is not None):
        raise ValueError("month 不能与 start_date/end_date 同时使用")
    if month is not None:
        start, end = _month_bounds(month)
    else:
        start = _parse_date(start_date, field="start_date")
        end = _parse_date(end_date, field="end_date")
        if start is None and end is None:
            start, end = _month_bounds(None)
        elif start is None or end is None:
            raise ValueError("start_date 与 end_date 必须同时提供")
    assert start is not None and end is not None
    if start > end:
        raise ValueError("start_date 不能晚于 end_date")
    if (end - start).days > 366:
        raise ValueError("日期范围不能超过 367 天")
    if min_boards is not None and min_boards < 2:
        raise ValueError("min_boards 最小为 2")
    if min_boards is not None and min_boards > 20:
        raise ValueError("min_boards 最大为 20")

    path = Path(db_path).expanduser()
    if not path.is_file():
        return {
            "status": "missing",
            "message": "市场数据库不存在",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "min_boards": min_boards or 2,
            "recommended_min_boards": 2,
            "market_data_cutoff": None,
            "board_data_cutoff": None,
            "calendar_days": [],
            "trading_days": [],
        }

    try:
        con = duckdb.connect(str(path), read_only=True)
    except Exception as exc:
        return {
            "status": "unavailable",
            "message": f"市场数据库暂时不可读：{type(exc).__name__}",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "min_boards": min_boards or 2,
            "recommended_min_boards": 2,
            "market_data_cutoff": None,
            "board_data_cutoff": None,
            "calendar_days": [],
            "trading_days": [],
        }

    try:
        if not _table_exists(con, MARKET_TABLE):
            return {
                "status": "missing",
                "message": "市场交易日表不存在",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "min_boards": min_boards or 2,
                "recommended_min_boards": 2,
                "market_data_cutoff": None,
                "board_data_cutoff": None,
                "calendar_days": [],
                "trading_days": [],
            }
        has_board_table = _table_exists(con, BOARD_TABLE)
        market_cutoff, board_cutoff = con.execute(
            f"""
            SELECT
                (SELECT MAX(trade_date) FROM {MARKET_TABLE}),
                {f'(SELECT MAX(trade_date) FROM {BOARD_TABLE})' if has_board_table else 'NULL'}
            """
        ).fetchone()
        recommended = (
            _recommended_min_boards(con, start=start, end=end)
            if has_board_table
            else 2
        )
        threshold = min_boards if min_boards is not None else recommended
        market_rows = con.execute(
            f"""
            SELECT trade_date
            FROM {MARKET_TABLE}
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            [start, end],
        ).fetchall()
        trading_dates = [row[0] for row in market_rows]
        board_by_date: dict[date, list[dict[str, Any]]] = {}
        board_data_dates: set[date] = set()
        if has_board_table and trading_dates:
            board_data_dates = {
                row[0]
                for row in con.execute(
                    f"""
                    SELECT DISTINCT trade_date
                    FROM {BOARD_TABLE}
                    WHERE trade_date BETWEEN ? AND ?
                    """,
                    [start, end],
                ).fetchall()
            }
            board_rows = con.execute(
                f"""
                SELECT trade_date, stock_ts_code, stock_name, boards, theme, pct_chg
                FROM {BOARD_TABLE}
                WHERE trade_date BETWEEN ? AND ? AND boards >= ?
                ORDER BY trade_date, boards DESC, stock_name
                """,
                [start, end, threshold],
            ).fetchall()
            for trading_date in sorted({row[0] for row in board_rows}):
                board_by_date[trading_date] = _group_boards(
                    [row for row in board_rows if row[0] == trading_date]
                )

        trading_days = [
            {
                "date": day.isoformat(),
                "weekday": day.weekday(),
                "is_trading_day": True,
                "calendar_status": "trading",
                "data_status": (
                    "available" if day in board_data_dates else "board_data_missing"
                ),
                "board_groups": board_by_date.get(day, []),
                "stock_count": sum(
                    len(group["stocks"]) for group in board_by_date.get(day, [])
                ),
            }
            for day in trading_dates
        ]
        status = "ok" if trading_days else "no_market_data"
        message = "已加载交易日与连板数据" if trading_days else "该日期范围暂无市场交易日数据"
        if has_board_table and board_cutoff is not None and board_cutoff < max(trading_dates, default=start):
            message = "连板数据落后于市场交易日；缺失日期保持显式标记"
            status = "partial"
        if not has_board_table:
            message = "连板数据表不存在；仅返回交易日"
            status = "partial"

        calendar_days: list[dict[str, Any]] = []
        trading_day_by_date = {item["date"]: item for item in trading_days}
        trading_date_set = set(trading_dates)
        today = date.today()
        current = start
        while current <= end:
            current_text = current.isoformat()
            if current in trading_date_set:
                calendar_days.append(trading_day_by_date[current_text])
            else:
                verdict = trading_day_verdict(current)
                # ``trading_day_verdict`` checks weekends before future dates.
                # The dashboard still needs to tell a future Saturday from a
                # historical weekend, so future is an explicit UI state here.
                if current > today:
                    calendar_status = "future"
                    data_status = "not_applicable"
                elif verdict.is_closed:
                    calendar_status = "closed"
                    data_status = "not_applicable"
                elif verdict.is_trading:
                    calendar_status = "market_data_missing"
                    data_status = "market_data_missing"
                else:
                    calendar_status = "calendar_unknown"
                    data_status = "calendar_unknown"
                calendar_days.append(
                    {
                        "date": current_text,
                        "weekday": current.weekday(),
                        "is_trading_day": False,
                        "calendar_status": calendar_status,
                        "data_status": data_status,
                        "board_groups": [],
                        "stock_count": 0,
                    }
                )
            current += timedelta(days=1)

        if has_board_table and any(
            day["data_status"] == "board_data_missing" for day in trading_days
        ):
            status = "partial"
            message = "部分交易日缺少连板数据；缺失日期保持显式标记"
        return {
            "status": status,
            "message": message,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "min_boards": threshold,
            "recommended_min_boards": recommended,
            "market_data_cutoff": _date_text(market_cutoff),
            "board_data_cutoff": _date_text(board_cutoff),
            "calendar_days": calendar_days,
            "trading_days": trading_days,
        }
    finally:
        con.close()


def month_for_date(value: date, delta_months: int) -> str:
    """Return an ISO month after applying a month offset."""
    index = value.year * 12 + value.month - 1 + delta_months
    year, month_no = divmod(index, 12)
    return f"{year:04d}-{month_no + 1:02d}"
