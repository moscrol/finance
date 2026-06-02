from __future__ import annotations

from datetime import datetime, date

from ..db import connect, init_db
from ..sources import fupanhui_source as fs


STRENGTH_COLUMNS = {
    "strength_avg_pct": "DOUBLE",
    "strength_amount_pct": "DOUBLE",
    "strength_amount": "DOUBLE",
    "strength_marginal_pct": "DOUBLE",
    "strength_yesterday_avg_pct": "DOUBLE",
    "strength_ma5_avg_pct": "DOUBLE",
    "strength_ma20_avg_pct": "DOUBLE",
    "strength_status": "TEXT",
    "strength_source": "TEXT",
    "strength_updated_at": "TIMESTAMP",
}


UPSERT_SQL = """
    INSERT INTO fact_market_daily
        (trade_date, strength_avg_pct, strength_amount_pct, strength_amount,
         strength_marginal_pct, strength_yesterday_avg_pct, strength_ma5_avg_pct,
         strength_ma20_avg_pct, strength_status, strength_source, strength_updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date) DO UPDATE SET
        strength_avg_pct = excluded.strength_avg_pct,
        strength_amount_pct = excluded.strength_amount_pct,
        strength_amount = excluded.strength_amount,
        strength_marginal_pct = excluded.strength_marginal_pct,
        strength_yesterday_avg_pct = COALESCE(excluded.strength_yesterday_avg_pct, fact_market_daily.strength_yesterday_avg_pct),
        strength_ma5_avg_pct = COALESCE(excluded.strength_ma5_avg_pct, fact_market_daily.strength_ma5_avg_pct),
        strength_ma20_avg_pct = COALESCE(excluded.strength_ma20_avg_pct, fact_market_daily.strength_ma20_avg_pct),
        strength_status = COALESCE(excluded.strength_status, fact_market_daily.strength_status),
        strength_source = excluded.strength_source,
        strength_updated_at = excluded.strength_updated_at
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


def _ensure_columns(con):
    for name, typ in STRENGTH_COLUMNS.items():
        con.execute(f"ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS {name} {typ}")


def sync_fupanhui_market_strength(trade_date: str | None = None, days: int = 120) -> dict:
    init_db()
    td = trade_date or fs.get_latest_date()
    if not td:
        raise RuntimeError("无目标交易日, 请显式传 --trade-date 或确认复盘会 latest-date 可用")

    data = fs.api_get(
        "/api/v1/client/reviews/market",
        {"trade_date": td, "days": int(days), "mode": "auto"},
        timeout=120,
    )
    strength = data.get("strength") if isinstance(data, dict) else None
    if not isinstance(strength, dict):
        raise RuntimeError("复盘会 market 接口未返回 strength 数据")

    current_date = _parse_date(data.get("trade_date")) or _parse_date(td)
    now = datetime.now()
    rows = []
    for point in strength.get("strength_trend_data") or []:
        d = _parse_date(point.get("trade_date"))
        if not d:
            continue
        rows.append((
            d,
            point.get("avg_pct"),
            point.get("amount_pct"),
            None,
            point.get("marginal_pct"),
            None,
            None,
            None,
            None,
            "fupanhui:reviews/market",
            now,
        ))

    if current_date:
        rows.append((
            current_date,
            strength.get("top5_avg_pct"),
            strength.get("top5_amount_pct"),
            strength.get("top5_amount"),
            strength.get("top5_marginal_pct"),
            strength.get("yesterday_top5_pct"),
            strength.get("ma5_top5_pct"),
            strength.get("ma20_top5_pct"),
            strength.get("strength_status"),
            "fupanhui:reviews/market",
            now,
        ))

    if not rows:
        raise RuntimeError("复盘会 market strength_trend_data 为空")

    con = connect()
    try:
        _ensure_columns(con)
        con.execute("BEGIN TRANSACTION")
        con.executemany(UPSERT_SQL, rows)
        con.execute("COMMIT")
        stats = con.execute(
            """
            SELECT COUNT(*), COUNT(strength_avg_pct), COUNT(strength_amount_pct),
                   COUNT(strength_marginal_pct), MIN(trade_date), MAX(trade_date)
            FROM fact_market_daily
            """
        ).fetchone()
        current = con.execute(
            """
            SELECT strength_avg_pct, strength_amount_pct, strength_amount,
                   strength_marginal_pct, strength_status
            FROM fact_market_daily WHERE trade_date = ?
            """,
            [current_date],
        ).fetchone() if current_date else None
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()

    return {
        "trade_date": str(current_date) if current_date else td,
        "rows_written": len(rows),
        "table_total": stats[0],
        "strength_avg_count": stats[1],
        "strength_amount_pct_count": stats[2],
        "strength_marginal_count": stats[3],
        "date_min": str(stats[4]) if stats[4] else None,
        "date_max": str(stats[5]) if stats[5] else None,
        "current": current,
    }
