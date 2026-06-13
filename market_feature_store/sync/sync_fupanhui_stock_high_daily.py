from __future__ import annotations

import json
import time
from datetime import date, datetime

from ..db import connect, init_db
from ..sources import fupanhui_source as fs

PERIODS = (
    ("history", "历史新高"),
    ("3y", "3年新高"),
    ("2y", "2年新高"),
    ("1y", "1年新高"),
    ("120d", "120日新高"),
    ("60d", "60日新高"),
    ("20d", "20日新高"),
)
PERIOD_RANK = {period: idx for idx, (period, _label) in enumerate(PERIODS)}
MARKET_COLUMNS = {
    "stock_high_count_history": "INTEGER",
    "stock_high_count_3y": "INTEGER",
    "stock_high_count_2y": "INTEGER",
    "stock_high_count_1y": "INTEGER",
    "stock_high_count_120d": "INTEGER",
    "stock_high_count_60d": "INTEGER",
    "stock_high_count_20d": "INTEGER",
    "stock_high_source": "TEXT",
    "stock_high_updated_at": "TIMESTAMP",
}
STOCK_HIGH_COLUMNS = {
    "primary_high_period": "TEXT",
    "primary_high_label": "TEXT",
    "high_periods_json": "TEXT",
    "is_new": "BOOLEAN",
    "price": "DOUBLE",
    "pct_chg": "DOUBLE",
    "pct_chg_10d": "DOUBLE",
    "amount": "DOUBLE",
    "market_cap": "DOUBLE",
    "fund_today": "DOUBLE",
    "limit_status": "TEXT",
    "limit_times": "INTEGER",
    "sw_l1": "TEXT",
    "sw_l2": "TEXT",
    "plate": "TEXT",
    "whitelist_sectors_json": "TEXT",
}

MARKET_UPSERT_SQL = """
    INSERT INTO fact_market_daily
        (trade_date, stock_high_count_history, stock_high_count_3y,
         stock_high_count_2y, stock_high_count_1y, stock_high_count_120d,
         stock_high_count_60d, stock_high_count_20d,
         stock_high_source, stock_high_updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date) DO UPDATE SET
        stock_high_count_history = excluded.stock_high_count_history,
        stock_high_count_3y = excluded.stock_high_count_3y,
        stock_high_count_2y = excluded.stock_high_count_2y,
        stock_high_count_1y = excluded.stock_high_count_1y,
        stock_high_count_120d = excluded.stock_high_count_120d,
        stock_high_count_60d = excluded.stock_high_count_60d,
        stock_high_count_20d = excluded.stock_high_count_20d,
        stock_high_source = excluded.stock_high_source,
        stock_high_updated_at = excluded.stock_high_updated_at
"""

STOCK_UPSERT_SQL = """
    INSERT INTO fact_stock_high_daily
        (trade_date, stock_ts_code, stock_name, primary_high_period,
         primary_high_label, high_periods_json, is_new, price, pct_chg,
         pct_chg_10d, amount, market_cap, fund_today, limit_status,
         limit_times, sw_l1, sw_l2, plate, whitelist_sectors_json,
         source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
        stock_name = excluded.stock_name,
        primary_high_period = excluded.primary_high_period,
        primary_high_label = excluded.primary_high_label,
        high_periods_json = excluded.high_periods_json,
        is_new = excluded.is_new,
        price = excluded.price,
        pct_chg = excluded.pct_chg,
        pct_chg_10d = excluded.pct_chg_10d,
        amount = excluded.amount,
        market_cap = excluded.market_cap,
        fund_today = excluded.fund_today,
        limit_status = excluded.limit_status,
        limit_times = excluded.limit_times,
        sw_l1 = excluded.sw_l1,
        sw_l2 = excluded.sw_l2,
        plate = excluded.plate,
        whitelist_sectors_json = excluded.whitelist_sectors_json,
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


def _require_date(val, name: str) -> date:
    parsed = _parse_date(val)
    if parsed is None:
        raise RuntimeError(f"无法解析{name}: {val}")
    return parsed


def _ensure_schema(con):
    for name, typ in MARKET_COLUMNS.items():
        con.execute(f"ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS {name} {typ}")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_stock_high_daily (
            trade_date              DATE,
            stock_ts_code           TEXT,
            stock_name              TEXT,
            primary_high_period     TEXT,
            primary_high_label      TEXT,
            high_periods_json       TEXT,
            is_new                  BOOLEAN,
            price                   DOUBLE,
            pct_chg                 DOUBLE,
            pct_chg_10d             DOUBLE,
            amount                  DOUBLE,
            market_cap              DOUBLE,
            fund_today              DOUBLE,
            limit_status            TEXT,
            limit_times             INTEGER,
            sw_l1                   TEXT,
            sw_l2                   TEXT,
            plate                   TEXT,
            whitelist_sectors_json  TEXT,
            source                  TEXT,
            updated_at              TIMESTAMP,
            PRIMARY KEY (trade_date, stock_ts_code)
        )
        """
    )
    for name, typ in STOCK_HIGH_COLUMNS.items():
        con.execute(f"ALTER TABLE fact_stock_high_daily ADD COLUMN IF NOT EXISTS {name} {typ}")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_stock_high_date ON fact_stock_high_daily(trade_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_stock_high_stock ON fact_stock_high_daily(stock_ts_code)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_stock_high_period ON fact_stock_high_daily(primary_high_period)")


def _resolve_range_dates(con, start_date: str | None, end_date: str | None, days: int | None) -> tuple[list[str], str]:
    if days is not None:
        if days <= 0:
            raise RuntimeError("--days 必须大于 0")
        if start_date:
            raise RuntimeError("--days 模式不能同时指定 --start-date")
        end = _require_date(end_date, "--end-date") if end_date else None
        params = []
        where = ""
        if end:
            where = "WHERE trade_date <= ?"
            params.append(end)
        rows = con.execute(
            f"""
            SELECT trade_date
            FROM fact_market_daily
            {where}
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [*params, int(days)],
        ).fetchall()
        dates = [str(r[0]) for r in reversed(rows)]
        if not dates:
            raise RuntimeError("fact_market_daily 中没有可用于 --days 的交易日")
        return dates, "fact_market_daily:days"

    if not start_date or not end_date:
        raise RuntimeError("请指定 --start-date/--end-date，或使用 --days")
    start = _require_date(start_date, "--start-date")
    end = _require_date(end_date, "--end-date")
    if start > end:
        raise RuntimeError("--start-date 不能晚于 --end-date")
    rows = con.execute(
        """
        SELECT trade_date
        FROM fact_market_daily
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date
        """,
        [start, end],
    ).fetchall()
    dates = [str(r[0]) for r in rows]
    if dates:
        return dates, "fact_market_daily:range"
    if start == end:
        return [start.isoformat()], "explicit_single_date"
    raise RuntimeError("fact_market_daily 中没有命中该日期区间的交易日，请先同步市场日表或缩小区间")


def _existing_stock_high_counts(con, dates: list[str]) -> dict[str, int]:
    if not dates:
        return {}
    rows = con.execute(
        """
        SELECT trade_date, COUNT(*)
        FROM fact_stock_high_daily
        WHERE CAST(trade_date AS VARCHAR) IN (SELECT * FROM UNNEST(?))
        GROUP BY trade_date
        """,
        [dates],
    ).fetchall()
    return {str(td): int(cnt) for td, cnt in rows}


def _fetch_period_stocks(period: str, trade_date: str, page_size: int) -> list[dict]:
    page = 1
    items: list[dict] = []
    while True:
        payload = fs.api_get(
            "/api/v1/client/data-high/stocks",
            {"period": period, "page": page, "page_size": page_size, "trade_date": trade_date},
            timeout=180,
        )
        batch = payload.get("items") if isinstance(payload, dict) else None
        if not batch:
            break
        items.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return items


def _merge_stock(agg: dict, item: dict, period: str, label: str) -> None:
    ts_code = item.get("tsCode") or item.get("ts_code")
    if not ts_code:
        return
    current = agg.get(ts_code)
    if current is None:
        current = {"best_period": period, "best_label": label, "best_item": item, "periods": [], "is_new": False}
        agg[ts_code] = current
    current["periods"].append({"period": period, "label": label})
    current["is_new"] = bool(current["is_new"] or item.get("isNew"))
    if PERIOD_RANK[period] < PERIOD_RANK[current["best_period"]]:
        current["best_period"] = period
        current["best_label"] = label
        current["best_item"] = item


def _market_row(trade_date: date, counts: dict, now: datetime):
    return (
        trade_date,
        counts.get("history"),
        counts.get("3y"),
        counts.get("2y"),
        counts.get("1y"),
        counts.get("120d"),
        counts.get("60d"),
        counts.get("20d"),
        "fupanhui:data-high",
        now,
    )


def _stock_row(trade_date: date, ts_code: str, merged: dict, now: datetime):
    item = merged["best_item"]
    periods = sorted(merged["periods"], key=lambda x: PERIOD_RANK.get(x["period"], 99))
    return (
        trade_date,
        ts_code,
        item.get("name"),
        merged["best_period"],
        merged["best_label"],
        json.dumps(periods, ensure_ascii=False),
        bool(merged["is_new"]),
        item.get("price"),
        item.get("change"),
        item.get("change10d"),
        item.get("amount"),
        item.get("marketCap"),
        item.get("fundToday"),
        item.get("limitStatus"),
        item.get("limitTimes"),
        item.get("swL1") or item.get("industry"),
        item.get("swL2") or item.get("industry2"),
        item.get("plate"),
        json.dumps(item.get("whitelistSectors") or [], ensure_ascii=False),
        "fupanhui:data-high",
        now,
    )


def sync_fupanhui_stock_high(trade_date: str | None = None, page_size: int = 200) -> dict:
    init_db()
    td = trade_date or fs.get_latest_date()
    if not td:
        raise RuntimeError("无目标交易日, 请显式传 --trade-date 或确认复盘会 latest-date 可用")

    counts_payload = fs.api_get(
        "/api/v1/client/data-high/period-counts",
        {"trade_date": td},
        timeout=120,
    )
    current_date = _parse_date(counts_payload.get("date") if isinstance(counts_payload, dict) else None) or _parse_date(td)
    if current_date is None:
        raise RuntimeError(f"无法解析新高数据日期: {td}")
    counts = counts_payload.get("counts") if isinstance(counts_payload, dict) else None
    if not isinstance(counts, dict):
        raise RuntimeError("复盘会 data-high/period-counts 未返回 counts")

    agg: dict[str, dict] = {}
    fetched_by_period = {}
    for period, label in PERIODS:
        items = _fetch_period_stocks(period, current_date.isoformat(), int(page_size))
        fetched_by_period[period] = len(items)
        for item in items:
            _merge_stock(agg, item, period, label)

    now = datetime.now()
    stock_rows = [_stock_row(current_date, ts_code, merged, now) for ts_code, merged in agg.items()]
    market_row = _market_row(current_date, counts, now)

    con = connect()
    try:
        _ensure_schema(con)
        con.execute("BEGIN TRANSACTION")
        con.execute(MARKET_UPSERT_SQL, market_row)
        con.execute("DELETE FROM fact_stock_high_daily WHERE trade_date = ?", [current_date])
        if stock_rows:
            con.executemany(STOCK_UPSERT_SQL, stock_rows)
        con.execute("COMMIT")
        market_current = con.execute(
            """
            SELECT stock_high_count_history, stock_high_count_3y, stock_high_count_2y,
                   stock_high_count_1y, stock_high_count_120d, stock_high_count_60d,
                   stock_high_count_20d
            FROM fact_market_daily WHERE trade_date = ?
            """,
            [current_date],
        ).fetchone()
        table_stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date),
                   SUM(CASE WHEN primary_high_period = 'history' THEN 1 ELSE 0 END)
            FROM fact_stock_high_daily
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
        "counts": counts,
        "fetched_by_period": fetched_by_period,
        "unique_stocks": len(stock_rows),
        "market_current": market_current,
        "table_total": table_stats[0],
        "table_dates": table_stats[1],
        "date_min": str(table_stats[2]) if table_stats[2] else None,
        "date_max": str(table_stats[3]) if table_stats[3] else None,
        "history_rows": int(table_stats[4] or 0),
    }


def sync_fupanhui_stock_high_range(
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    page_size: int = 200,
    refresh: bool = False,
    sleep: float = 0.2,
) -> dict:
    init_db()
    con = connect()
    try:
        _ensure_schema(con)
        dates, date_source = _resolve_range_dates(con, start_date, end_date, days)
        existing_counts = _existing_stock_high_counts(con, dates)
    finally:
        con.close()

    results = []
    skipped = []
    failures = []
    total_unique_stocks = 0
    total_period_fetches = {period: 0 for period, _label in PERIODS}

    for td in dates:
        existing = existing_counts.get(td, 0)
        if existing and not refresh:
            skipped.append({"trade_date": td, "existing_rows": existing})
            continue
        try:
            stats = sync_fupanhui_stock_high(trade_date=td, page_size=page_size)
            results.append(stats)
            total_unique_stocks += int(stats.get("unique_stocks") or 0)
            for period, value in stats.get("fetched_by_period", {}).items():
                total_period_fetches[period] = total_period_fetches.get(period, 0) + int(value or 0)
        except Exception as e:
            failures.append({"trade_date": td, "error": str(e)})
        if sleep and sleep > 0:
            time.sleep(float(sleep))

    table_stats = None
    con = connect(read_only=True)
    try:
        table_stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date)
            FROM fact_stock_high_daily
            """
        ).fetchone()
    finally:
        con.close()

    return {
        "dates": dates,
        "date_source": date_source,
        "requested_dates": len(dates),
        "synced_dates": len(results),
        "skipped_dates": len(skipped),
        "failed_dates": len(failures),
        "total_unique_stocks": total_unique_stocks,
        "total_period_fetches": total_period_fetches,
        "results": results,
        "skipped": skipped,
        "failures": failures,
        "table_total": table_stats[0] if table_stats else 0,
        "table_dates": table_stats[1] if table_stats else 0,
        "date_min": str(table_stats[2]) if table_stats and table_stats[2] else None,
        "date_max": str(table_stats[3]) if table_stats and table_stats[3] else None,
    }
