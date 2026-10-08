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
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        parsed = date.fromisoformat(str(value))
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
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


#: 用户口径：一只 ≥5 板的个股「收盘不再是涨停」即算高标断板（断于几板 = 断板前一日的连板数）。
HIGH_BOARD_BREAK_DEFAULT = 5


def _previous_market_trading_day(
    con: duckdb.DuckDBPyConnection, start: date, today: date
) -> date | None:
    """The market trading day immediately before ``start`` (≤ today), if any."""
    row = con.execute(
        f"SELECT MAX(trade_date) FROM {MARKET_TABLE} WHERE trade_date < ? AND trade_date <= ?",
        [start, today],
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def _high_board_breaks(
    trading_dates: list[date],
    sealed_by_day: dict[date, dict[str, tuple[str, int, str | None]]],
    present_by_day: dict[date, set[str]],
    board_data_dates: set[date],
    high_board_min: int,
    leading_day: date | None = None,
) -> tuple[dict[date, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Detect high-board (≥ ``high_board_min``) break events across consecutive days.

    A stock **断板** on day ``D`` when it was sealed on the previous *market*
    trading day at ≥ ``high_board_min`` boards and is **not** sealed at close on
    ``D``.  "Sealed at close on ``D``" means the board table carries a row for
    the stock on ``D`` (``present_by_day``); a ``boards`` value of NULL still
    means "present, just uncounted", so it never counts as a break.  Both days
    must carry board data: a day with no rows at all cannot prove "not limit-up"
    (it may just be missing), so we fail closed and record no break — the same
    stance as the succession coverage rules, where "no row" is never equated
    with "not sealed".

    The pairing sequence is the union of the market trading days, the days the
    board table actually has rows for, and ``leading_day`` (the market trading
    day just before the first range day).  A day present only in the board table
    (missing from the market table) still acts as the ``previous`` for the
    following day, so a break's height is read from the latest available data
    rather than an earlier gap.  Only in-range market trading days are ever
    reported.  Returns per-day break lists (keyed by the break day, height-
    ordered) and a flattened list in the same day-then-height order for the
    month view.

    A break whose *break day* is missing from the market table (but present in
    the board table) is not reported: that day is not a reportable trading day,
    so the event has no cell to land in.  This is the intended fail-closed
    stance — the cell is instead marked ``market_data_missing``, so the gap
    stays visible rather than a break being guessed across a hole.

    This is the **per-stock high-board break** (the 连板日历 day-cell mark).  It
    is NOT the ``LeaderSuccession`` break/birth event — an 事件锚点 in the
    event-reaction pipeline (``intelligence/services/teaching_framework/
    leader_succession.py``).  The two share the word 断板 but are different
    quantities; see ``UBIQUITOUS_LANGUAGE.md`` (Flagged ambiguities).
    """
    report_days = set(trading_dates)
    per_day: dict[date, list[dict[str, Any]]] = {day: [] for day in trading_dates}
    sequence = sorted(
        report_days | board_data_dates | ({leading_day} if leading_day is not None else set())
    )
    for previous, day in zip(sequence, sequence[1:]):
        if day not in report_days:
            continue
        if previous not in board_data_dates or day not in board_data_dates:
            continue
        previous_sealed = sealed_by_day.get(previous, {})
        day_present = present_by_day.get(day, set())
        for code, (name, boards, theme) in previous_sealed.items():
            if boards is None or boards < high_board_min or code in day_present:
                continue
            per_day[day].append(
                {
                    "date": day.isoformat(),
                    "stock_ts_code": code,
                    "stock_name": name,
                    "height_at_break": boards,
                    "theme": theme,
                }
            )
    for day in per_day:
        per_day[day].sort(key=lambda item: (-item["height_at_break"], item["stock_name"]))
    flattened = [event for day in trading_dates for event in per_day[day]]
    return per_day, flattened


def build_board_calendar(
    db_path: str | Path,
    *,
    month: str | None = None,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    min_boards: int | None = None,
    high_board_min: int | None = None,
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
    if high_board_min is not None and not 1 <= high_board_min <= 20:
        raise ValueError("high_board_min 需在 1 到 20 之间")
    hb_min = high_board_min if high_board_min is not None else HIGH_BOARD_BREAK_DEFAULT

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
            "high_board_breaks": [],
            "high_board_min": hb_min,
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
            "high_board_breaks": [],
            "high_board_min": hb_min,
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
                "high_board_breaks": [],
                "high_board_min": hb_min,
            }
        has_board_table = _table_exists(con, BOARD_TABLE)
        today = date.today()
        market_cutoff = con.execute(
            f"SELECT MAX(trade_date) FROM {MARKET_TABLE} WHERE trade_date <= ?",
            [today],
        ).fetchone()[0]
        board_cutoff = (
            con.execute(
                f"SELECT MAX(trade_date) FROM {BOARD_TABLE} WHERE trade_date <= ?",
                [today],
            ).fetchone()[0]
            if has_board_table
            else None
        )
        recommendation_end = min(end, today)
        recommended = (
            _recommended_min_boards(
                con,
                start=start,
                end=recommendation_end,
            )
            if has_board_table and start <= recommendation_end
            else 2
        )
        threshold = min_boards if min_boards is not None else recommended
        market_rows = con.execute(
            f"""
            SELECT DISTINCT trade_date
            FROM {MARKET_TABLE}
            WHERE trade_date BETWEEN ? AND ? AND trade_date <= ?
            ORDER BY trade_date
            """,
            [start, end, today],
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
                    WHERE trade_date BETWEEN ? AND ? AND trade_date <= ?
                    """,
                    [start, end, today],
                ).fetchall()
            }
            board_rows = con.execute(
                f"""
                SELECT trade_date, stock_ts_code, stock_name, boards, theme, pct_chg
                FROM {BOARD_TABLE}
                WHERE trade_date BETWEEN ? AND ? AND trade_date <= ? AND boards >= ?
                ORDER BY trade_date, boards DESC, stock_name
                """,
                [start, end, today, threshold],
            ).fetchall()
            for trading_date in sorted({row[0] for row in board_rows}):
                board_by_date[trading_date] = _group_boards(
                    [row for row in board_rows if row[0] == trading_date]
                )

        high_board_breaks_by_day: dict[date, list[dict[str, Any]]] = {
            day: [] for day in trading_dates
        }
        high_board_breaks_flat: list[dict[str, Any]] = []
        if has_board_table and trading_dates:
            # Include the market day just before ``start`` so a break landing on the
            # first day of the range is still detectable.  Unfiltered by board count:
            # a ≥5-board break must be found even though the view threshold is lower.
            leading_day = _previous_market_trading_day(con, start, today)
            window_start = leading_day or start
            sealed_by_day: dict[date, dict[str, tuple[str, int, str | None]]] = {}
            present_by_day: dict[date, set[str]] = {}
            for (
                b_trade_date,
                b_code,
                b_name,
                b_boards,
                b_theme,
            ) in con.execute(
                f"""
                SELECT trade_date, stock_ts_code, stock_name, boards, theme
                FROM {BOARD_TABLE}
                WHERE trade_date BETWEEN ? AND ? AND trade_date <= ?
                ORDER BY trade_date, stock_name
                """,
                [window_start, end, today],
            ).fetchall():
                # Any row means the stock was present on that day, even if its
                # board count is NULL; "present" is what rules out a break.
                present_by_day.setdefault(b_trade_date, set()).add(str(b_code))
                if b_boards is None:
                    continue
                sealed_by_day.setdefault(b_trade_date, {})[str(b_code)] = (
                    str(b_name or b_code),
                    int(b_boards),
                    str(b_theme) if b_theme else None,
                )
            # The leading day sits before ``start`` so it is not in ``board_data_dates``;
            # add it so the first range day can be checked against it.  Its sealed set
            # is empty unless it truly has rows, so a missing leading day still yields
            # no break (fail closed).
            break_data_dates = (
                board_data_dates | {leading_day}
                if leading_day is not None
                else board_data_dates
            )
            high_board_breaks_by_day, high_board_breaks_flat = _high_board_breaks(
                trading_dates,
                sealed_by_day,
                present_by_day,
                break_data_dates,
                hb_min,
                leading_day,
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
                "high_board_breaks": high_board_breaks_by_day.get(day, []),
            }
            for day in trading_dates
        ]
        status = "ok" if trading_days else "no_market_data"
        message = "已加载交易日与连板数据" if trading_days else "该日期范围暂无市场交易日数据"
        calendar_days: list[dict[str, Any]] = []
        trading_day_by_date = {item["date"]: item for item in trading_days}
        trading_date_set = set(trading_dates)
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
                        "is_trading_day": calendar_status == "market_data_missing",
                        "calendar_status": calendar_status,
                        "data_status": data_status,
                        "board_groups": [],
                        "stock_count": 0,
                        "high_board_breaks": [],
                    }
                )
            if current == end:
                break
            current += timedelta(days=1)

        gaps = []
        if not has_board_table:
            gaps.append("连板数据表不存在")
        elif any(day["data_status"] == "board_data_missing" for day in trading_days):
            gaps.append("部分交易日缺少连板数据")
        if any(day["calendar_status"] == "market_data_missing" for day in calendar_days):
            gaps.append("部分交易日缺少市场日数据")
        if any(day["calendar_status"] == "calendar_unknown" for day in calendar_days):
            gaps.append("部分日期无法确认交易日历")
        if gaps:
            status = "partial"
            message = "；".join([*gaps, "缺失与未知日期保持显式标记"])
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
            "high_board_breaks": high_board_breaks_flat,
            "high_board_min": hb_min,
        }
    finally:
        con.close()


def month_for_date(value: date, delta_months: int) -> str:
    """Return an ISO month after applying a month offset."""
    index = value.year * 12 + value.month - 1 + delta_months
    year, month_no = divmod(index, 12)
    return f"{year:04d}-{month_no + 1:02d}"
