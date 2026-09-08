"""同花顺官方涨停 / 跌停 / 炸板池 → ``fact_limit_pool_hithink``（工单 #41 C）。

按交易日串行请求，``size=200``，``pagination.pages > 1`` 才翻页。
涨停从 2020-01-01；跌停 / 炸板只拉近一年。非交易日空集不报错。
个股名接住但不落库。
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb

from ..db import DB_PATH, init_db, is_lock_conflict
from ..hithink_client import HithinkAPIError, get_json, has_api_key, shanghai_midnight_ms

POOL_UP = "limit_up"
POOL_DOWN = "limit_down"
POOL_BREAK = "limit_break"
UP_START = date(2020, 1, 1)
PAGE_SIZE = 200
INCR_DAYS = 3

PATHS = {
    POOL_UP: "/api/a-share/special-data/limit-up-pool",
    POOL_DOWN: "/api/a-share/special-data/limit-down-pool",
    POOL_BREAK: "/api/a-share/special-data/limit-break-pool",
}
SOURCES = {
    POOL_UP: "hithink:limit-up-pool",
    POOL_DOWN: "hithink:limit-down-pool",
    POOL_BREAK: "hithink:limit-break-pool",
}
FIELDS = {
    POOL_UP: (
        "thscode",
        "ticker",
        "name",
        "is_st",
        "is_new",
        "last_price",
        "price_change_ratio_pct",
        "limit_up_time",
        "limit_up_reason",
        "continue_day_text",
        "continue_day_cnt",
        "seal_money",
        "max_seal_money",
    ),
    POOL_DOWN: (
        "thscode",
        "ticker",
        "name",
        "last_price",
        "price_change_ratio_pct",
        "first_limit_time",
        "last_limit_time",
        "turnover_ratio_pct",
    ),
    POOL_BREAK: (
        "thscode",
        "ticker",
        "name",
        "last_price",
        "price_change_ratio_pct",
        "open_times",
        "turnover_ratio_pct",
        "turnover",
    ),
}
CALENDAR_TABLES = (
    "fact_stock_daily_hithink",
    "fact_market_daily",
    "fact_stock_daily",
)

GetJson = Callable[..., dict[str, Any]]


class HithinkLimitSyncError(RuntimeError):
    """涨停池同步失败。消息里不得带 key。"""


def skip_reason_if_no_key() -> str | None:
    if has_api_key():
        return None
    return "no-key"


def _open_writable(db_path: Path | str | None):
    target = Path(db_path) if db_path is not None else DB_PATH
    try:
        con = duckdb.connect(str(target))
        con.execute("SELECT 1")
        return con, False
    except duckdb.IOException as exc:
        # db_path 显式给了才允许落 sidecar（手跑回补撞上夜跑写锁时不白跑）。
        # daily-full 里 db_path 是 None、目标是 staging 副本：那里落 sidecar
        # 会在原子换库时被丢掉，而步骤还是绿的——必须让它红。
        if db_path is None or not is_lock_conflict(exc):
            raise
        sidecar = Path(str(target) + ".hithink-c.duckdb")
        print("production db locked, writing sidecar", flush=True)
        return duckdb.connect(str(sidecar)), True


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict):
        raw = data.get("item") or data.get("items") or []
    elif isinstance(data, list):
        raw = data
    else:
        raw = []
    return [row for row in raw if isinstance(row, dict)]


def _pages(payload: dict[str, Any]) -> int:
    data = payload.get("data")
    if not isinstance(data, dict):
        return 1
    pag = data.get("pagination") or {}
    try:
        return max(1, int(pag.get("pages") or 1))
    except (TypeError, ValueError):
        return 1


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema='main' AND table_name = ?
        """,
        [name],
    ).fetchone()
    return bool(row and row[0])


def trading_days(
    con: duckdb.DuckDBPyConnection, start: date, end: date
) -> list[date]:
    for table in CALENDAR_TABLES:
        if not _table_exists(con, table):
            continue
        rows = con.execute(
            f"""
            SELECT DISTINCT trade_date FROM {table}
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY 1
            """,
            [start, end],
        ).fetchall()
        if rows:
            return [r[0] if isinstance(r[0], date) else date.fromisoformat(str(r[0])) for r in rows]
    raise HithinkLimitSyncError("没有交易日历（需要 fact_stock_daily_hithink 或 fact_market_daily）")


def fetch_pool_day(
    pool: str, day: date, getter: GetJson
) -> list[dict[str, Any]]:
    path = PATHS[pool]
    page = 1
    out: list[dict[str, Any]] = []
    while True:
        try:
            payload = getter(
                path,
                params={
                    "date_ms": shanghai_midnight_ms(day),
                    "page": page,
                    "size": PAGE_SIZE,
                },
            )
        except HithinkAPIError as exc:
            text = str(exc)
            # 1002/1003=窗口外；5003=上游当日行缺 ticker，当空集，不让六年回补停掉。
            if any(token in text for token in ("code=1002", "code=1003", "code=5003")):
                if "code=5003" in text:
                    print(f"{pool} {day} skip code=5003", flush=True)
                return []
            raise
        page_items = _items(payload)
        for item in page_items:
            row = {field: item.get(field) for field in FIELDS[pool]}
            if row.get("thscode"):
                out.append(row)
        pages = _pages(payload)
        if page >= pages:
            break
        page += 1
    return out


def _row_tuple(pool: str, day: date, item: dict[str, Any]) -> tuple:
    name = item.get("name")  # 接住，不落库
    return (
        day,
        pool,
        str(item.get("thscode")),
        item.get("ticker"),
        item.get("is_st"),
        item.get("is_new"),
        item.get("last_price"),
        item.get("price_change_ratio_pct"),
        item.get("limit_up_time"),
        item.get("limit_up_reason"),
        item.get("continue_day_text"),
        item.get("continue_day_cnt"),
        item.get("seal_money"),
        item.get("max_seal_money"),
        item.get("first_limit_time"),
        item.get("last_limit_time"),
        item.get("turnover_ratio_pct"),
        item.get("open_times"),
        item.get("turnover"),
        SOURCES[pool],
        name,
    )


def _flush(con: duckdb.DuckDBPyConnection, rows: list[tuple], dest: Path) -> int:
    if not rows:
        return 0
    stored = [r[:-1] for r in rows]  # 丢掉 name
    mem = duckdb.connect(":memory:")
    try:
        mem.execute(
            """
            CREATE TABLE t (
                trade_date DATE, pool TEXT, stock_ts_code TEXT, ticker TEXT,
                is_st BOOLEAN, is_new BOOLEAN, last_price DOUBLE, pct_chg DOUBLE,
                limit_up_time TEXT, limit_up_reason TEXT, continue_day_text TEXT,
                continue_day_cnt INTEGER, seal_money DOUBLE, max_seal_money DOUBLE,
                first_limit_time TEXT, last_limit_time TEXT,
                turnover_ratio_pct DOUBLE, open_times INTEGER, turnover DOUBLE,
                source TEXT
            )
            """
        )
        mem.executemany(
            "INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            stored,
        )
        mem.execute(f"COPY t TO '{dest}' (FORMAT PARQUET)")
    finally:
        mem.close()
    con.execute(
        """
        INSERT OR REPLACE INTO fact_limit_pool_hithink
            (trade_date, pool, stock_ts_code, ticker, is_st, is_new, last_price,
             pct_chg, limit_up_time, limit_up_reason, continue_day_text,
             continue_day_cnt, seal_money, max_seal_money, first_limit_time,
             last_limit_time, turnover_ratio_pct, open_times, turnover,
             source, updated_at)
        SELECT trade_date, pool, stock_ts_code, ticker, is_st, is_new, last_price,
               pct_chg, limit_up_time, limit_up_reason, continue_day_text,
               continue_day_cnt, seal_money, max_seal_money, first_limit_time,
               last_limit_time, turnover_ratio_pct, open_times, turnover,
               source, now()
        FROM read_parquet(?)
        """,
        [str(dest)],
    )
    return len(stored)


def table_fingerprint(con: duckdb.DuckDBPyConnection) -> str:
    row = con.execute(
        """
        SELECT COUNT(*), COUNT(DISTINCT trade_date),
               MIN(trade_date), MAX(trade_date),
               BIT_XOR(HASH(trade_date, pool, stock_ts_code, continue_day_cnt, last_price))
        FROM fact_limit_pool_hithink
        """
    ).fetchone()
    payload = "|".join("" if v is None else str(v) for v in row)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def pool_stats(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    rows = con.execute(
        """
        SELECT pool, COUNT(*), COUNT(DISTINCT trade_date),
               MIN(trade_date), MAX(trade_date)
        FROM fact_limit_pool_hithink
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    out: dict[str, Any] = {}
    for pool, n, days, dmin, dmax in rows:
        out[str(pool)] = {
            "rows": int(n or 0),
            "days": int(days or 0),
            "date_min": str(dmin) if dmin else None,
            "date_max": str(dmax) if dmax else None,
        }
    return out


def yearly_up_counts(con: duckdb.DuckDBPyConnection) -> dict[int, int]:
    rows = con.execute(
        """
        SELECT EXTRACT(year FROM trade_date)::INTEGER, COUNT(*)
        FROM fact_limit_pool_hithink
        WHERE pool = 'limit_up'
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    return {int(y): int(n) for y, n in rows}


def compare_limit_up_counts(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    if not _table_exists(con, "fact_market_daily"):
        return {"compared": 0, "matched": 0, "rate": None}
    row = con.execute(
        """
        WITH h AS (
            SELECT trade_date, COUNT(*) AS n
            FROM fact_limit_pool_hithink
            WHERE pool = 'limit_up'
              AND trade_date >= CURRENT_DATE - INTERVAL 365 DAY
            GROUP BY 1
        ),
        o AS (
            SELECT trade_date, limit_up AS n
            FROM fact_market_daily
            WHERE limit_up IS NOT NULL
              AND trade_date >= CURRENT_DATE - INTERVAL 365 DAY
        )
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE h.n = o.n),
            MEDIAN(ABS(h.n - o.n)),
            MIN(h.n - o.n),
            MAX(h.n - o.n)
        FROM h INNER JOIN o USING (trade_date)
        """
    ).fetchone()
    compared = int(row[0] or 0)
    matched = int(row[1] or 0)
    return {
        "compared": compared,
        "matched": matched,
        "rate": (matched / compared) if compared else None,
        "median_abs_diff": float(row[2]) if row[2] is not None else None,
        "min_diff": int(row[3]) if row[3] is not None else None,
        "max_diff": int(row[4]) if row[4] is not None else None,
    }


def compare_boards(con: duckdb.DuckDBPyConnection, days: int = 20) -> dict[str, Any]:
    if not _table_exists(con, "fact_limit_advance_daily"):
        return {"compared": 0, "matched": 0, "rate": None, "days": 0}
    dates = [
        r[0]
        for r in con.execute(
            """
            SELECT DISTINCT trade_date FROM fact_limit_advance_daily
            ORDER BY 1 DESC LIMIT ?
            """,
            [days],
        ).fetchall()
    ]
    if not dates:
        return {"compared": 0, "matched": 0, "rate": None, "days": 0}
    placeholders = ",".join("?" * len(dates))
    row = con.execute(
        f"""
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE h.continue_day_cnt = a.boards)
        FROM fact_limit_pool_hithink h
        INNER JOIN fact_limit_advance_daily a
          USING (trade_date, stock_ts_code)
        WHERE h.pool = 'limit_up'
          AND h.trade_date IN ({placeholders})
        """,
        dates,
    ).fetchone()
    compared = int(row[0] or 0)
    matched = int(row[1] or 0)
    return {
        "compared": compared,
        "matched": matched,
        "rate": (matched / compared) if compared else None,
        "days": len(dates),
    }


def _dates_done(con: duckdb.DuckDBPyConnection, pool: str) -> set[date]:
    if not _table_exists(con, "fact_limit_pool_hithink"):
        return set()
    return {
        r[0] if isinstance(r[0], date) else date.fromisoformat(str(r[0]))
        for r in con.execute(
            """
            SELECT DISTINCT trade_date FROM fact_limit_pool_hithink
            WHERE pool = ?
            """,
            [pool],
        ).fetchall()
    }


def _plan_ranges(
    *,
    mode: str,
    end: date,
    start: date | None,
) -> dict[str, tuple[date, date]]:
    if mode == "incremental":
        begin = end - timedelta(days=21)
        return {pool: (begin, end) for pool in PATHS}
    if mode != "full":
        raise HithinkLimitSyncError("mode 只能是 full 或 incremental")
    up_start = start or UP_START
    down_start = end - timedelta(days=365)
    return {
        POOL_UP: (up_start, end),
        POOL_DOWN: (down_start, end),
        POOL_BREAK: (down_start, end),
    }


def sync_hithink_limit_pools(
    *,
    mode: str,
    db_path: Path | str | None = None,
    start: date | None = None,
    end_date: date | None = None,
    resume: bool = False,
    compare: bool = False,
    dates: Iterable[date] | None = None,
    get_json_fn: GetJson | None = None,
) -> dict[str, Any]:
    getter = get_json_fn or get_json
    end = end_date or date.today()
    ranges = _plan_ranges(mode=mode, end=end, start=start)

    con, sidecar = _open_writable(db_path)
    try:
        # 3G 库上重放 schema.sql 会卡很久；表已在就别 init。
        if not _table_exists(con, "fact_limit_pool_hithink"):
            init_db(con)
        print(f"opened db sidecar={sidecar} mode={mode}", flush=True)
        done = {pool: _dates_done(con, pool) for pool in PATHS} if resume else {}
        written = 0
        empty_days = 0
        requests = 0
        buf: list[tuple] = []
        with tempfile.TemporaryDirectory(prefix="hithink-c-") as tmp:
            tmp_path = Path(tmp)
            batch = 0
            for pool, (p_start, p_end) in ranges.items():
                if dates is not None:
                    days = [d for d in dates if p_start <= d <= p_end]
                else:
                    days = trading_days(con, p_start, p_end)
                    if mode == "incremental":
                        days = days[-INCR_DAYS:]
                if resume:
                    days = [d for d in days if d not in done.get(pool, set())]
                for i, day in enumerate(days, start=1):
                    items = fetch_pool_day(pool, day, getter)
                    requests += 1
                    if items:
                        buf.extend(_row_tuple(pool, day, item) for item in items)
                        written += len(items)
                    else:
                        empty_days += 1
                    if len(buf) >= 4000:
                        batch += 1
                        _flush(con, buf, tmp_path / f"p-{batch}.parquet")
                        buf = []
                    if i % 50 == 0 or i == len(days):
                        print(
                            f"{pool} {i}/{len(days)} rows={written} empty_days={empty_days}",
                            flush=True,
                        )
            if buf:
                batch += 1
                _flush(con, buf, tmp_path / f"p-{batch}.parquet")

        stats = pool_stats(con)
        result: dict[str, Any] = {
            "mode": mode,
            "sidecar": sidecar,
            "rows_written": written,
            "empty_days": empty_days,
            "requests": requests,
            "pools": stats,
            "yearly_up": yearly_up_counts(con),
            "fingerprint": table_fingerprint(con),
        }
        if compare:
            result["count_compare"] = compare_limit_up_counts(con)
            result["boards_compare"] = compare_boards(con)
        return result
    finally:
        con.close()
