"""同步 fact_sector_daily: 板块日行情 + 边际量。

数据源: fupanhui sector-cycle kline (单次调用返回 days 天序列)。
一次批量抓取全部板块的多日 K 线, 写入 fact_sector_daily (upsert)。
板块名与申万一级来自 dim_sector。
"""
from __future__ import annotations

from datetime import datetime, date

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
