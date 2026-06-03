from __future__ import annotations

from datetime import datetime, date
import re
import time

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


OVERVIEW_UPSERT_SQL = """
    INSERT INTO fact_market_daily
        (trade_date, market_stage, stage_day, ice_point, total_amount,
         amount_vs_yesterday_pct, amount_ma20, volume_ratio, volume_state,
         advancers, limit_up, limit_down, top3_industry_ratio, concentration_state,
         industry_1, industry_1_ratio, industry_2, industry_2_ratio,
         industry_3, industry_3_ratio, strength_avg_pct, strength_amount_pct,
         strength_amount, strength_marginal_pct, strength_yesterday_avg_pct,
         strength_ma5_avg_pct, strength_ma20_avg_pct, strength_status,
         strength_source, strength_updated_at, note, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date) DO UPDATE SET
        market_stage = excluded.market_stage,
        stage_day = excluded.stage_day,
        ice_point = excluded.ice_point,
        total_amount = excluded.total_amount,
        amount_vs_yesterday_pct = excluded.amount_vs_yesterday_pct,
        amount_ma20 = excluded.amount_ma20,
        volume_ratio = excluded.volume_ratio,
        volume_state = excluded.volume_state,
        advancers = excluded.advancers,
        limit_up = excluded.limit_up,
        limit_down = excluded.limit_down,
        top3_industry_ratio = excluded.top3_industry_ratio,
        concentration_state = excluded.concentration_state,
        industry_1 = excluded.industry_1,
        industry_1_ratio = excluded.industry_1_ratio,
        industry_2 = excluded.industry_2,
        industry_2_ratio = excluded.industry_2_ratio,
        industry_3 = excluded.industry_3,
        industry_3_ratio = excluded.industry_3_ratio,
        strength_avg_pct = excluded.strength_avg_pct,
        strength_amount_pct = excluded.strength_amount_pct,
        strength_amount = excluded.strength_amount,
        strength_marginal_pct = excluded.strength_marginal_pct,
        strength_yesterday_avg_pct = excluded.strength_yesterday_avg_pct,
        strength_ma5_avg_pct = excluded.strength_ma5_avg_pct,
        strength_ma20_avg_pct = excluded.strength_ma20_avg_pct,
        strength_status = excluded.strength_status,
        strength_source = excluded.strength_source,
        strength_updated_at = excluded.strength_updated_at,
        note = excluded.note,
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


def _int(val):
    n = _num(val)
    return int(n) if n is not None else None


def _distribution_value(sentiment: dict, label: str, typ: str):
    for item in sentiment.get("distribution") or []:
        if not isinstance(item, dict):
            continue
        if item.get("label") == label or item.get("type") == typ:
            return _int(item.get("value"))
    return None


def _concentration_state(ratio):
    n = _num(ratio)
    if n is None:
        return None
    if n < 35:
        return "分散"
    if n <= 45:
        return "正常"
    return "集中"


def _stage_day(summary: dict):
    day = summary.get("external_cycle_day")
    if day is not None:
        return _int(day)
    content = summary.get("content") or ""
    m = re.search(r"第(\d+)天", str(content))
    return int(m.group(1)) if m else None


def _ice_point(cycle: dict):
    value = cycle.get("ice_point")
    if value in (None, "", False):
        return None
    if value is True:
        return "冰点"
    return str(value)


def _ensure_columns(con):
    for name, typ in STRENGTH_COLUMNS.items():
        con.execute(f"ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS {name} {typ}")


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


def _existing_overview_dates(con, dates):
    if not dates:
        return {}
    placeholders = ",".join(["?"] * len(dates))
    rows = con.execute(
        f"""
        SELECT CAST(trade_date AS VARCHAR), total_amount, advancers, top3_industry_ratio
        FROM fact_market_daily
        WHERE CAST(trade_date AS VARCHAR) IN ({placeholders})
        """,
        dates,
    ).fetchall()
    return {
        r[0]: all(x is not None for x in r[1:])
        for r in rows
    }


def sync_fupanhui_market_overview(trade_date: str | None = None, days: int = 60) -> dict:
    init_db()
    td = trade_date or fs.get_latest_date()
    if not td:
        raise RuntimeError("无目标交易日, 请显式传 --trade-date 或确认复盘会 latest-date 可用")

    market = fs.api_get(
        "/api/v1/client/reviews/market",
        {"trade_date": td, "days": int(days), "mode": "auto"},
        timeout=120,
    )
    summary = fs.api_get(
        "/api/v1/client/reviews/summary",
        {"trade_date": td},
        timeout=120,
    )
    cycle = fs.api_get(
        "/api/v1/client/reviews/cycle",
        {"trade_date": td, "mode": "auto"},
        timeout=120,
    )
    if not isinstance(market, dict):
        raise RuntimeError("复盘会 market 接口未返回 dict")
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(cycle, dict):
        cycle = {}

    current_date = _parse_date(market.get("trade_date")) or _parse_date(summary.get("trade_date")) or _parse_date(td)
    if current_date is None:
        raise RuntimeError(f"无法解析复盘日期: {td}")

    volume = market.get("volume") if isinstance(market.get("volume"), dict) else {}
    sentiment = market.get("sentiment") if isinstance(market.get("sentiment"), dict) else {}
    spread = market.get("industry_spread") if isinstance(market.get("industry_spread"), dict) else {}
    strength = market.get("strength") if isinstance(market.get("strength"), dict) else {}
    top_industries = [x for x in (spread.get("top3_industries") or []) if isinstance(x, dict)]
    while len(top_industries) < 3:
        top_industries.append({})

    top3_ratio = _num(spread.get("top3_total_pct"))
    now = datetime.now()
    row = (
        current_date,
        summary.get("external_cycle") or cycle.get("current_stage"),
        _stage_day(summary),
        _ice_point(cycle),
        _num(volume.get("total_amount") or volume.get("current_amount")),
        _num(volume.get("change_pct")),
        _num(volume.get("ma20_amount")),
        _num(volume.get("ma20_ratio")),
        volume.get("volume_status"),
        _int(sentiment.get("rise_count")),
        _distribution_value(sentiment, "涨停", "up-limit"),
        _distribution_value(sentiment, "跌停", "down-limit"),
        top3_ratio,
        _concentration_state(top3_ratio),
        top_industries[0].get("name"),
        _num(top_industries[0].get("ratio")),
        top_industries[1].get("name"),
        _num(top_industries[1].get("ratio")),
        top_industries[2].get("name"),
        _num(top_industries[2].get("ratio")),
        _num(strength.get("top5_avg_pct")),
        _num(strength.get("top5_amount_pct")),
        _num(strength.get("top5_amount")),
        _num(strength.get("top5_marginal_pct")),
        _num(strength.get("yesterday_top5_pct")),
        _num(strength.get("ma5_top5_pct")),
        _num(strength.get("ma20_top5_pct")),
        strength.get("strength_status"),
        "fupanhui:reviews/market",
        now,
        summary.get("content"),
        "fupanhui:reviews",
        now,
    )

    con = connect()
    try:
        _ensure_columns(con)
        con.execute("BEGIN TRANSACTION")
        con.execute(OVERVIEW_UPSERT_SQL, row)
        con.execute("COMMIT")
        stats = con.execute(
            """
            SELECT COUNT(*), COUNT(total_amount), COUNT(advancers), COUNT(top3_industry_ratio),
                   MIN(trade_date), MAX(trade_date)
            FROM fact_market_daily
            """
        ).fetchone()
        current = con.execute(
            """
            SELECT market_stage, stage_day, total_amount, volume_ratio,
                   advancers, limit_up, limit_down, top3_industry_ratio
            FROM fact_market_daily WHERE trade_date = ?
            """,
            [current_date],
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
        "rows_written": 1,
        "table_total": stats[0],
        "total_amount_count": stats[1],
        "advancers_count": stats[2],
        "top3_ratio_count": stats[3],
        "date_min": str(stats[4]) if stats[4] else None,
        "date_max": str(stats[5]) if stats[5] else None,
        "current": current,
    }


def sync_fupanhui_market_overview_range(
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    api_days: int = 60,
    refresh: bool = False,
    sleep: float = 0.2,
) -> dict:
    init_db()
    con = connect()
    try:
        dates, date_source = _resolve_range_dates(con, start_date, end_date, days)
        existing = _existing_overview_dates(con, dates)
    finally:
        con.close()

    skipped = []
    synced = []
    failures = []
    for d in dates:
        if not refresh and existing.get(d):
            skipped.append({"trade_date": d})
            continue
        try:
            sync_fupanhui_market_overview(trade_date=d, days=api_days)
            synced.append(d)
        except Exception as e:
            failures.append({"trade_date": d, "error": str(e)})
        if sleep:
            time.sleep(float(sleep))

    con = connect()
    try:
        stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date),
                   COUNT(total_amount), COUNT(advancers), COUNT(top3_industry_ratio)
            FROM fact_market_daily
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
        "skipped": skipped,
        "failures": failures,
        "table_total": stats[0],
        "table_dates": stats[1],
        "date_min": str(stats[2]) if stats[2] else None,
        "date_max": str(stats[3]) if stats[3] else None,
        "total_amount_count": stats[4],
        "advancers_count": stats[5],
        "top3_ratio_count": stats[6],
    }


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
