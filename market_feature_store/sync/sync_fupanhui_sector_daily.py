"""同步 published sector generation 的目标日行情与边际量。

数据源: fupanhui sector-cycle kline (单次调用返回 days 天序列)。
请求代码只来自目标日已发布 universe；多日响应只取目标交易日，并通过
SectorUniverseStore 原子替换该代际，禁止直接写公开视图。
"""
from __future__ import annotations

from datetime import datetime, date
import time

from ..db import connect, init_db
from ..sector_universe import SectorUniverseStore, SectorUniverseValidationError
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


def _published_sector_counts(con, dates):
    store = SectorUniverseStore(con)
    counts = {}
    errors = {}
    for trade_date in dates:
        try:
            counts[trade_date] = store.published_snapshot(trade_date).sector_count
        except SectorUniverseValidationError as exc:
            errors[trade_date] = str(exc)
    return counts, errors


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


def _fresh_sector_daily_counts(con, dates, updated_since: datetime):
    if not dates:
        return {}
    placeholders = ",".join(["?"] * len(dates))
    rows = con.execute(
        f"""
        SELECT CAST(trade_date AS VARCHAR),
               COUNT(*),
               COUNT(*) FILTER (WHERE updated_at >= ?),
               COUNT(*) FILTER (WHERE updated_at >= ? AND diff_ratio IS NULL)
        FROM fact_sector_daily
        WHERE CAST(trade_date AS VARCHAR) IN ({placeholders})
        GROUP BY trade_date
        """,
        [updated_since, updated_since, *dates],
    ).fetchall()
    return {
        r[0]: {
            "rows": int(r[1]),
            "fresh_rows": int(r[2]),
            "fresh_null_diff": int(r[3]),
        }
        for r in rows
    }


def _validate_synced_dates(dates, sector_count: int, updated_since: datetime):
    con = connect(read_only=True)
    try:
        counts = _fresh_sector_daily_counts(con, dates, updated_since)
    finally:
        con.close()
    minimum_rows = sector_count
    return {
        trade_date: {
            **counts.get(trade_date, {"rows": 0, "fresh_rows": 0, "fresh_null_diff": 0}),
            "minimum_rows": minimum_rows,
            "ok": (
                counts.get(trade_date, {}).get("fresh_rows", 0) == minimum_rows
                and counts.get(trade_date, {}).get("fresh_null_diff", 0) == 0
            ),
        }
        for trade_date in dates
    }


def _sector_daily_table_stats():
    con = connect(read_only=True)
    try:
        return con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date),
                   COUNT(CASE WHEN diff_ratio IS NULL THEN 1 END)
            FROM fact_sector_daily
            """
        ).fetchone()
    finally:
        con.close()


def sync_fact_sector_daily(trade_date: str | None = None, days: int = 25) -> dict:
    """抓取已发布 universe 的目标日 K 线并完整替换其代际。"""
    requested_date = trade_date if trade_date is not None else fs.get_latest_date()
    target_date = _parse_date(requested_date)
    if target_date is None:
        raise SectorUniverseValidationError("canonical provider trade date is unavailable")

    init_db()
    con = connect()
    try:
        published = SectorUniverseStore(con).published_snapshot(target_date)
    finally:
        con.close()

    ts_codes = [sector.sector_ts_code for sector in published.sectors]
    klines = fs.get_sector_klines_batch(
        ts_codes,
        trade_date=target_date.isoformat(),
        days=days,
    )
    if not isinstance(klines, dict):
        raise SectorUniverseValidationError("sector K-line response must be a mapping")

    normalized_klines = {}
    for raw_code, points in klines.items():
        code = str(raw_code).strip().upper()
        if not code or code in normalized_klines:
            raise SectorUniverseValidationError(
                "sector K-line response identities must be non-empty and unique"
            )
        normalized_klines[code] = points
    if set(normalized_klines) != set(ts_codes):
        missing = len(set(ts_codes) - set(normalized_klines))
        foreign = len(set(normalized_klines) - set(ts_codes))
        raise SectorUniverseValidationError(
            f"sector K-line response must match published universe (missing={missing}, foreign={foreign})"
        )

    now = datetime.now()
    rows = []
    for ts_code in ts_codes:
        points = normalized_klines[ts_code]
        if not isinstance(points, list):
            raise SectorUniverseValidationError(
                "sector K-line series must be a list for every published identity"
            )
        target_points = [
            point
            for point in points
            if isinstance(point, dict)
            and _parse_date(point.get("trade_date")) == target_date
        ]
        if len(target_points) != 1:
            raise SectorUniverseValidationError(
                "each published sector must have exactly one target-date K-line row"
            )
        point = target_points[0]
        rows.append(
            {
                "sector_ts_code": ts_code,
                "pct_chg": point.get("pct_chg"),
                "amount": point.get("amount"),
                "diff_ratio": point.get("diff_ratio"),
                "strength": None,
                "source": "fupanhui",
                "updated_at": now,
            }
        )

    con = connect()
    try:
        written = SectorUniverseStore(con).replace_sector_daily(
            published.snapshot_id,
            rows,
        )
        total = con.execute("SELECT COUNT(*) FROM fact_sector_daily").fetchone()[0]
        date_range = con.execute(
            "SELECT MIN(trade_date), MAX(trade_date) FROM fact_sector_daily"
        ).fetchone()
        n_dates = con.execute(
            "SELECT COUNT(DISTINCT trade_date) FROM fact_sector_daily"
        ).fetchone()[0]
    finally:
        con.close()

    return {
        "snapshot_id": published.snapshot_id,
        "sectors": len(ts_codes),
        "empty_sectors": 0,
        "rows_written": written,
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
        dates, date_source = _resolve_range_dates(con, start_date, end_date, days)
        existing = _existing_sector_daily_counts(con, dates)
        sector_counts, snapshot_errors = _published_sector_counts(con, dates)
    finally:
        con.close()

    skipped = []
    targets = []
    failures = [
        {"trade_date": trade_date, "error": f"published snapshot unavailable: {error}"}
        for trade_date, error in snapshot_errors.items()
    ]
    for d in dates:
        if d in snapshot_errors:
            continue
        sector_count = sector_counts[d]
        existing_info = existing.get(d, {"rows": 0, "null_diff": 0})
        existing_rows = existing_info["rows"]
        null_diff = existing_info["null_diff"]
        if not refresh and existing_rows == sector_count and null_diff == 0:
            skipped.append({"trade_date": d, "existing_rows": existing_rows, "null_diff": null_diff})
        else:
            targets.append(d)

    synced = []
    total_rows_written = 0
    failed_chunks = len(snapshot_errors)
    chunk_days = max(1, int(chunk_days))
    for i in range(0, len(targets), chunk_days):
        chunk = targets[i:i + chunk_days]
        if not chunk:
            continue
        chunk_failed = False
        for trade_date in chunk:
            started = datetime.now()
            try:
                stats = sync_fact_sector_daily(
                    trade_date=trade_date,
                    days=20,
                )
                total_rows_written += int(stats["rows_written"])
                coverage = _validate_synced_dates(
                    [trade_date],
                    sector_counts[trade_date],
                    started,
                )
                result = coverage[trade_date]
                if result["ok"]:
                    synced.append(trade_date)
                else:
                    chunk_failed = True
                    failures.append({
                        "trade_date": trade_date,
                        "error": (
                            f"partial response: fresh_rows={result['fresh_rows']}/"
                            f"{result['minimum_rows']}, fresh_null_diff={result['fresh_null_diff']}"
                        ),
                    })
            except Exception as exc:
                chunk_failed = True
                failures.append({"trade_date": trade_date, "error": str(exc)})
        if chunk_failed:
            failed_chunks += 1
        if sleep:
            time.sleep(float(sleep))

    table_stats = _sector_daily_table_stats()

    return {
        "requested_dates": len(dates),
        "date_source": date_source,
        "synced_dates": len(synced),
        "skipped_dates": len(skipped),
        "failed_chunks": failed_chunks,
        "failed_dates": len(failures),
        "total_rows_written": total_rows_written,
        "skipped": skipped,
        "failures": failures,
        "table_total": table_stats[0],
        "table_dates": table_stats[1],
        "date_min": str(table_stats[2]) if table_stats[2] else None,
        "date_max": str(table_stats[3]) if table_stats[3] else None,
        "null_diff_ratio": int(table_stats[4] or 0),
    }
