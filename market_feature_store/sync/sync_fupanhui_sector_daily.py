"""同步 fact_sector_daily: 板块日行情 + 边际量。

数据源: fupanhui sector-cycle kline (单次调用返回 days 天序列)。
一次批量抓取全部板块的多日 K 线, 写入 fact_sector_daily (upsert)。
板块名与申万一级来自 dim_sector。
"""
from __future__ import annotations

from datetime import datetime, date
from math import ceil
import time

from ..db import connect, init_db, get_published_snapshot_id
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


def _load_sector_dim(con):
    rows = con.execute(
        "SELECT sector_ts_code, sector_name, sw_l1 FROM dim_sector"
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def _published_sector_counts(con, dates):
    """逐日取该交易日 published 快照里的板块数，作为回填的期望覆盖基准。

    返回 (counts, errors)。errors 里的日期表示当天没有 published 快照——回填时这是
    失败，不是可以按 'legacy' 蒙混过去的情况（见 sync_fact_sector_daily_range）。
    """
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


def _validate_synced_dates(dates, sector_count: int, updated_since: datetime, min_ratio: float = 0.9):
    con = connect(read_only=True)
    try:
        counts = _fresh_sector_daily_counts(con, dates, updated_since)
    finally:
        con.close()
    minimum_rows = max(1, ceil(sector_count * min_ratio))
    return {
        trade_date: {
            **counts.get(trade_date, {"rows": 0, "fresh_rows": 0, "fresh_null_diff": 0}),
            "minimum_rows": minimum_rows,
            "ok": (
                counts.get(trade_date, {}).get("fresh_rows", 0) >= minimum_rows
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
    """抓取全部板块多日 K 线写入 fact_sector_daily_generation。返回统计。"""
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

    # 按 trade_date 分组，每个日期取对应 snapshot_id
    date_snapshot: dict[str, str] = {}
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
            d_str = str(d)
            if d_str not in date_snapshot:
                date_snapshot[d_str] = None  # 延迟到连接后获取
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
        # 获取每个日期的 snapshot_id
        snap_map: dict[str, str] = {}
        for d_str in date_snapshot:
            snap_map[d_str] = get_published_snapshot_id(con, d_str)

        # 组装带 snapshot_id 的写入行
        gen_rows = []
        for row in rows:
            d_str = str(row[0])
            snap_id = snap_map.get(d_str, "legacy")
            gen_rows.append((row[0], snap_id, row[1], row[2], row[3],
                             row[4], row[5], row[6], row[7], row[8], row[9]))

        con.execute("BEGIN TRANSACTION")
        con.executemany(
            """
            INSERT INTO fact_sector_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, sw_l1,
                 pct_chg, amount, diff_ratio, strength, source, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (trade_date, sector_universe_snapshot_id, sector_ts_code) DO UPDATE SET
                sector_name = excluded.sector_name,
                sw_l1 = excluded.sw_l1,
                pct_chg = excluded.pct_chg,
                amount = excluded.amount,
                diff_ratio = excluded.diff_ratio,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            gen_rows,
        )
        con.execute("COMMIT")
        total = con.execute("SELECT COUNT(*) FROM fact_sector_daily_generation").fetchone()[0]
        date_range = con.execute(
            "SELECT MIN(trade_date), MAX(trade_date) FROM fact_sector_daily_generation"
        ).fetchone()
        n_dates = con.execute(
            "SELECT COUNT(DISTINCT trade_date) FROM fact_sector_daily_generation"
        ).fetchone()[0]
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

    # 回报这轮实际写进了哪一版板块清单。分代机制存在的理由就是能回答「当时用的是
    # 哪一版清单」，写入方自己不报的话，调用方只能事后去 ops 表反查。
    # snapshot_ids 是逐日期的全量映射；snapshot_id 只在全程唯一时给出，避免多日期
    # 批量回填时用一个值掩盖掉实际的分代差异。
    distinct_snaps = sorted(set(snap_map.values()))
    return {
        "sectors": len(ts_codes),
        "empty_sectors": empty_sectors,
        "rows_written": len(rows),
        "fact_sector_daily_total": total,
        "distinct_dates": n_dates,
        "date_min": str(date_range[0]) if date_range[0] else None,
        "date_max": str(date_range[1]) if date_range[1] else None,
        "snapshot_ids": dict(sorted(snap_map.items())),
        "snapshot_id": distinct_snaps[0] if len(distinct_snaps) == 1 else None,
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

    # 期望覆盖基准取自当日 published 快照，而不是 dim_sector 的全局板块数：
    # 供应商会换代码、改名单，用全局数当基准会在换版当天误判覆盖率。
    #
    # 没有 published 快照的日期 **fail-closed**，既不回填也不调 API。写入侧
    # (sync_fact_sector_daily) 遇到无快照会回退 'legacy'，那是给「机制上线前的历史
    # 数据」准备的；但回填时某天本该有快照却没有，默默按 legacy 写会把一次「清单没
    # 发布」的运维故障伪装成正常数据——而且行数与 COUNT(*) 覆盖率审计全都正常。
    # 这正是 CLAUDE.md 里 fast_daily_sync.py 那类静默降级的形状。
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
        if not refresh and existing_rows >= max(1, ceil(sector_count * 0.9)) and null_diff == 0:
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
        chunk_end = chunk[-1]
        chunk_started = datetime.now()
        try:
            stats = sync_fact_sector_daily(
                trade_date=chunk_end,
                days=max(20, len(chunk) + 5),
            )
            total_rows_written += int(stats["rows_written"])
            # 逐日校验：每天用自己那版快照的板块数当基准，chunk 内跨快照版本时
            # 用同一个数会误判。API 仍按 chunk 只调一次（fupanhui 有周/月调用上限）。
            coverage = {}
            for trade_date in chunk:
                coverage.update(
                    _validate_synced_dates(
                        [trade_date], sector_counts[trade_date], chunk_started
                    )
                )
            chunk_failed = False
            for trade_date in chunk:
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
            if chunk_failed:
                failed_chunks += 1
        except Exception as e:
            failed_chunks += 1
            failures.extend({"trade_date": trade_date, "error": str(e)} for trade_date in chunk)
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
