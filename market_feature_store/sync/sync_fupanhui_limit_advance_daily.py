from __future__ import annotations

from datetime import date, datetime
import time

from ..db import connect, init_db
from ..sources import fupanhui_source as fs


DAILY_UPSERT_SQL = """
    INSERT INTO fact_limit_advance_daily
        (trade_date, stock_ts_code, stock_name, boards, first_limit_date,
         theme, pct_chg, promotion_rate, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
        stock_name = excluded.stock_name,
        boards = excluded.boards,
        first_limit_date = excluded.first_limit_date,
        theme = excluded.theme,
        pct_chg = excluded.pct_chg,
        promotion_rate = excluded.promotion_rate,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


PRESENCE_UPSERT_SQL = """
    INSERT INTO fact_limit_advance_presence
        (trade_date, stock_name, sequence_no, source, updated_at)
    VALUES (?,?,?,?,?)
    ON CONFLICT (trade_date, stock_name) DO UPDATE SET
        sequence_no = excluded.sequence_no,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _num(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("%", "").replace("+", "").replace(",", "")
    if s in ("", "-", "—", "/", "None", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _resolve_range_dates(con, start_date: str | None, end_date: str | None, days: int | None):
    if days is not None:
        params = []
        where = ""
        if end_date:
            where = "WHERE trade_date <= ?"
            params.append(_parse_date(end_date) or end_date)
        rows = con.execute(
            f"""
            SELECT trade_date FROM fact_market_daily
            {where}
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [*params, int(days)],
        ).fetchall()
        return [str(r[0]) for r in reversed(rows)], "days"

    if not start_date or not end_date:
        raise ValueError("必须提供 --start-date/--end-date, 或使用 --days")
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if not start or not end:
        raise ValueError("日期格式必须为 YYYY-MM-DD")
    rows = con.execute(
        """
        SELECT trade_date FROM fact_market_daily
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date
        """,
        [start, end],
    ).fetchall()
    return [str(r[0]) for r in rows], "range"


def _existing_daily_counts(con, dates):
    if not dates:
        return {}
    placeholders = ",".join(["?"] * len(dates))
    rows = con.execute(
        f"""
        SELECT CAST(m.trade_date AS VARCHAR),
               COALESCE(d.daily_rows, 0),
               COALESCE(p.presence_rows, 0)
        FROM (
            SELECT DISTINCT trade_date FROM fact_market_daily
            WHERE CAST(trade_date AS VARCHAR) IN ({placeholders})
        ) m
        LEFT JOIN (
            SELECT trade_date, COUNT(*) AS daily_rows
            FROM fact_limit_advance_daily
            GROUP BY trade_date
        ) d USING (trade_date)
        LEFT JOIN (
            SELECT trade_date, COUNT(*) AS presence_rows
            FROM fact_limit_advance_presence
            GROUP BY trade_date
        ) p USING (trade_date)
        """,
        dates,
    ).fetchall()
    return {r[0]: {"daily": int(r[1]), "presence": int(r[2])} for r in rows}


def _first_limit_date(trade_dates, level):
    try:
        idx = int(level) - 1
    except (TypeError, ValueError):
        return None
    if idx < 0 or idx >= len(trade_dates):
        return None
    return _parse_date(trade_dates[idx])


def _promotion_rate(level_data):
    promoted = level_data.get("promoted_count")
    total = level_data.get("total_count")
    rate = _num(level_data.get("promotion_rate"))
    if promoted is None or total is None or rate is None:
        return None
    return f"{int(promoted)}/{int(total)}={rate:.0f}%"


def sync_fupanhui_limit_advance(trade_date: str | None = None, min_boards: int = 3) -> dict:
    init_db()
    td = trade_date or fs.get_latest_date()
    if not td:
        raise RuntimeError("无目标交易日, 请显式传 --trade-date 或确认复盘会 latest-date 可用")

    data = fs.api_get(
        "/api/v1/client/limit/ladder",
        {"trade_date": td},
        timeout=120,
    )
    if not isinstance(data, dict):
        raise RuntimeError("复盘会 limit ladder 接口未返回 dict")

    current_date = _parse_date(data.get("trade_date")) or _parse_date(td)
    if current_date is None:
        raise RuntimeError(f"无法解析连板晋级日期: {td}")

    trade_dates = data.get("trade_dates") or []
    levels = data.get("levels") or []
    now = datetime.now()
    rows = []
    skipped_status = 0
    skipped_boards = 0

    for level_data in levels:
        if not isinstance(level_data, dict):
            continue
        level = level_data.get("level")
        try:
            boards = int(level)
        except (TypeError, ValueError):
            continue
        if boards < int(min_boards):
            skipped_boards += len(level_data.get("stocks") or [])
            continue
        first_date = _first_limit_date(trade_dates, boards)
        rate = _promotion_rate(level_data)
        for stock in level_data.get("stocks") or []:
            if not isinstance(stock, dict):
                continue
            if stock.get("status_type") != "U":
                skipped_status += 1
                continue
            ts_code = stock.get("ts_code")
            name = stock.get("name")
            if not ts_code or not name:
                continue
            theme = stock.get("leader_sub_plate") or stock.get("leader_plate")
            rows.append((
                current_date,
                ts_code,
                name,
                boards,
                first_date,
                theme,
                _num(stock.get("pct_chg")),
                rate,
                "fupanhui:limit/ladder",
                now,
            ))

    rows.sort(key=lambda r: (r[4] or current_date, -r[3], r[2]))
    presence_rows = [
        (current_date, row[2], idx, "fupanhui:limit/ladder", now)
        for idx, row in enumerate(rows, start=1)
    ]

    con = connect()
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM fact_limit_advance_daily WHERE trade_date = ?", [current_date])
        con.execute("DELETE FROM fact_limit_advance_presence WHERE trade_date = ?", [current_date])
        if rows:
            con.executemany(DAILY_UPSERT_SQL, rows)
            con.executemany(PRESENCE_UPSERT_SQL, presence_rows)
        con.execute("COMMIT")
        daily_stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT stock_ts_code),
                   MIN(trade_date), MAX(trade_date)
            FROM fact_limit_advance_daily
            """
        ).fetchone()
        presence_stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT stock_name),
                   MIN(trade_date), MAX(trade_date)
            FROM fact_limit_advance_presence
            """
        ).fetchone()
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()

    return {
        "trade_date": current_date.isoformat(),
        "max_limit_days": data.get("max_limit_days"),
        "levels": len(levels),
        "rows_written": len(rows),
        "presence_rows_written": len(presence_rows),
        "skipped_status": skipped_status,
        "skipped_boards": skipped_boards,
        "table_total": daily_stats[0],
        "table_dates": daily_stats[1],
        "table_stocks": daily_stats[2],
        "date_min": str(daily_stats[3]) if daily_stats[3] else None,
        "date_max": str(daily_stats[4]) if daily_stats[4] else None,
        "presence_total": presence_stats[0],
        "presence_dates": presence_stats[1],
        "presence_stocks": presence_stats[2],
        "presence_date_min": str(presence_stats[3]) if presence_stats[3] else None,
        "presence_date_max": str(presence_stats[4]) if presence_stats[4] else None,
    }


def sync_fupanhui_limit_advance_range(
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    min_boards: int = 3,
    refresh: bool = False,
    sleep: float = 0.2,
) -> dict:
    init_db()
    con = connect()
    try:
        dates, date_source = _resolve_range_dates(con, start_date, end_date, days)
        existing = _existing_daily_counts(con, dates)
    finally:
        con.close()

    skipped = []
    synced = []
    failures = []
    total_rows = 0
    for d in dates:
        existing_info = existing.get(d, {"daily": 0, "presence": 0})
        if not refresh and existing_info["presence"] > 0:
            skipped.append({
                "trade_date": d,
                "existing_rows": existing_info["presence"],
                "existing_daily_rows": existing_info["daily"],
            })
            continue
        try:
            stats = sync_fupanhui_limit_advance(trade_date=d, min_boards=min_boards)
            synced.append(d)
            total_rows += stats["rows_written"]
        except Exception as e:
            failures.append({"trade_date": d, "error": str(e)})
        if sleep:
            time.sleep(float(sleep))

    con = connect()
    try:
        daily_stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT stock_ts_code),
                   MIN(trade_date), MAX(trade_date)
            FROM fact_limit_advance_daily
            """
        ).fetchone()
        presence_stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT stock_name),
                   MIN(trade_date), MAX(trade_date)
            FROM fact_limit_advance_presence
            """
        ).fetchone()
    finally:
        con.close()

    return {
        "requested_dates": len(dates),
        "date_source": date_source,
        "synced_dates": len(synced),
        "skipped_dates": len(skipped),
        "failed_dates": len(failures),
        "total_rows_written": total_rows,
        "skipped": skipped,
        "failures": failures,
        "table_total": daily_stats[0],
        "table_dates": daily_stats[1],
        "table_stocks": daily_stats[2],
        "date_min": str(daily_stats[3]) if daily_stats[3] else None,
        "date_max": str(daily_stats[4]) if daily_stats[4] else None,
        "presence_total": presence_stats[0],
        "presence_dates": presence_stats[1],
        "presence_stocks": presence_stats[2],
        "presence_date_min": str(presence_stats[3]) if presence_stats[3] else None,
        "presence_date_max": str(presence_stats[4]) if presence_stats[4] else None,
    }
