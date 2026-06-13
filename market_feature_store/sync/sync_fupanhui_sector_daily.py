"""同步 fact_sector_daily: 板块日行情 + 边际量。

数据源: fupanhui sector-cycle kline (单次调用返回 days 天序列)。
一次批量抓取全部板块的多日 K 线, 写入 fact_sector_daily (upsert)。
板块名与申万一级来自 dim_sector。
"""
from __future__ import annotations

from datetime import datetime, date
import time

from ..db import connect, init_db
from ..sources import fupanhui_source as fs


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


def _load_sector_dim(con):
    rows = con.execute(
        "SELECT sector_ts_code, sector_name, sw_l1 FROM dim_sector"
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


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


def _existing_sector_daily_counts(con, dates):
    if not dates:
        return {}
    placeholders = ",".join(["?"] * len(dates))
    rows = con.execute(
        f"""
        SELECT CAST(trade_date AS VARCHAR), COUNT(*),
               COUNT(CASE WHEN diff_ratio IS NULL THEN 1 END)
        FROM fact_sector_daily
        WHERE CAST(trade_date AS VARCHAR) IN ({placeholders})
        GROUP BY trade_date
        """,
        dates,
    ).fetchall()
    return {r[0]: {"rows": int(r[1]), "null_diff": int(r[2])} for r in rows}


def sync_fact_sector_daily(trade_date: str | None = None, days: int = 25) -> dict:
    """抓取全部板块多日 K 线写入 fact_sector_daily。返回统计。"""
    init_db()
    con = connect()
    try:
        dim = _load_sector_dim(con)
    finally:
        con.close()

    if not dim:
        raise RuntimeError("dim_sector 为空, 请先运行 sync-sectors")

    ts_codes = list(dim.keys())
    klines = fs.get_sector_klines_batch(ts_codes, trade_date=trade_date, days=days)
    now = datetime.now()

    rows = []
    empty_sectors = 0
    for ts_code, points in klines.items():
        name, sw_l1 = dim.get(ts_code, (ts_code, None))
        if not points:
            empty_sectors += 1
            continue
        for p in points:
            d = _parse_date(p.get("trade_date"))
            if not d:
                continue
            rows.append((
                d, ts_code, name, sw_l1,
                p.get("pct_chg"), p.get("amount"), p.get("diff_ratio"), None,
                "fupanhui", now,
            ))

    if not rows:
        raise RuntimeError(
            "未取到任何板块 K 线数据 (检查 CDP 登录态 / days>=20 / 字段映射)"
        )

    con = connect()
    try:
        con.execute("BEGIN TRANSACTION")
        con.executemany(
            """
            INSERT INTO fact_sector_daily
                (trade_date, sector_ts_code, sector_name, sw_l1,
                 pct_chg, amount, diff_ratio, strength, source, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (trade_date, sector_ts_code) DO UPDATE SET
                sector_name = excluded.sector_name,
                sw_l1 = excluded.sw_l1,
                pct_chg = excluded.pct_chg,
                amount = excluded.amount,
                diff_ratio = excluded.diff_ratio,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            rows,
        )
        con.execute("COMMIT")
        total = con.execute("SELECT COUNT(*) FROM fact_sector_daily").fetchone()[0]
        date_range = con.execute(
            "SELECT MIN(trade_date), MAX(trade_date) FROM fact_sector_daily"
        ).fetchone()
        n_dates = con.execute(
            "SELECT COUNT(DISTINCT trade_date) FROM fact_sector_daily"
        ).fetchone()[0]
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

    return {
        "sectors": len(ts_codes),
        "empty_sectors": empty_sectors,
        "rows_written": len(rows),
        "fact_sector_daily_total": total,
        "distinct_dates": n_dates,
        "date_min": str(date_range[0]) if date_range[0] else None,
        "date_max": str(date_range[1]) if date_range[1] else None,
    }


def sync_fact_sector_daily_range(
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    chunk_days: int = 15,
    refresh: bool = False,
    sleep: float = 0.2,
) -> dict:
    init_db()
    con = connect()
    try:
        dim = _load_sector_dim(con)
        dates, date_source = _resolve_range_dates(con, start_date, end_date, days)
        existing = _existing_sector_daily_counts(con, dates)
    finally:
        con.close()

    if not dim:
        raise RuntimeError("dim_sector 为空, 请先运行 sync-sectors")

    sector_count = len(dim)
    skipped = []
    targets = []
    for d in dates:
        existing_info = existing.get(d, {"rows": 0, "null_diff": 0})
        existing_rows = existing_info["rows"]
        null_diff = existing_info["null_diff"]
        if not refresh and existing_rows >= max(1, int(sector_count * 0.9)) and null_diff == 0:
            skipped.append({"trade_date": d, "existing_rows": existing_rows, "null_diff": null_diff})
        else:
            targets.append(d)

    synced = []
    failures = []
    total_rows_written = 0
    chunk_days = max(1, int(chunk_days))
    for i in range(0, len(targets), chunk_days):
        chunk = targets[i:i + chunk_days]
        if not chunk:
            continue
        chunk_end = chunk[-1]
        try:
            stats = sync_fact_sector_daily(
                trade_date=chunk_end,
                days=max(20, len(chunk) + 5),
            )
            synced.extend(chunk)
            total_rows_written += int(stats["rows_written"])
        except Exception as e:
            failures.append({"trade_date": chunk_end, "error": str(e)})
        if sleep:
            time.sleep(float(sleep))

    con = connect()
    try:
        table_stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date),
                   COUNT(CASE WHEN diff_ratio IS NULL THEN 1 END)
            FROM fact_sector_daily
            """
        ).fetchone()
    finally:
        con.close()

    return {
        "requested_dates": len(dates),
        "date_source": date_source,
        "synced_dates": len(synced),
        "skipped_dates": len(skipped),
        "failed_chunks": len(failures),
        "total_rows_written": total_rows_written,
        "skipped": skipped,
        "failures": failures,
        "table_total": table_stats[0],
        "table_dates": table_stats[1],
        "date_min": str(table_stats[2]) if table_stats[2] else None,
        "date_max": str(table_stats[3]) if table_stats[3] else None,
        "null_diff_ratio": int(table_stats[4] or 0),
    }
