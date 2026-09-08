"""同花顺官方个股日 K dump → ``fact_stock_daily_hithink``（工单 #41 A）。

``--full`` 走 ``daily-k``（十年），``--incremental`` 走 ``daily-k-10d``。
``date_ms`` 用工单指定的上海零点公式，不走会话时区。本地 ``--parquet`` 优先，
没有再签预签名 URL；只 GET，不 HEAD。

turnover 是元（dump 原值），不是 ``fact_stock_daily.amount`` 的亿。
source 按端点写 ``hithink:daily-k`` / ``hithink:daily-k-10d`` /
``hithink:adjustment-factors``。产品面打印只报行数 / 日期 / 代码数。
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any, Callable

import duckdb

from ..db import connect, init_db, is_lock_conflict
from ..hithink_client import fetch_dump_parquet, has_api_key

# 工单指定：date_ms = Asia/Shanghai 零点毫秒。DuckDB 里先当 UTC 解开再加 8 小时。
# 1473264000000 → 2016-09-08。不要改成 timezone() / 会话时区，那会跟 dump 对不上。
TRADE_DATE_SQL = (
    "CAST(to_timestamp(date_ms/1000) AT TIME ZONE 'UTC' + INTERVAL 8 HOUR AS DATE)"
)
EX_DATE_SQL = (
    "CAST(to_timestamp(ex_date_ms/1000) AT TIME ZONE 'UTC' + INTERVAL 8 HOUR AS DATE)"
)

KIND_FULL = "daily-k"
KIND_INCREMENTAL = "daily-k-10d"
KIND_ADJUSTMENTS = "adjustment-factors"

SOURCE_BY_KIND = {
    KIND_FULL: "hithink:daily-k",
    KIND_INCREMENTAL: "hithink:daily-k-10d",
    KIND_ADJUSTMENTS: "hithink:adjustment-factors",
}

# 官方 dump 契约列。请求了（读了 parquet）就必须在 SQL 里出现，不许丢掉。
DUMP_DAILY_COLUMNS = (
    "thscode",
    "currency",
    "interval",
    "adjusted",
    "date_ms",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "turnover",
)
DUMP_ADJ_COLUMNS = (
    "thscode",
    "ticker",
    "ex_date_ms",
    "dividend_per_share",
    "per_share_bonus",
    "allotment_ratio",
    "allotment_price",
    "currency",
)

INSERT_DAILY_SQL = f"""
INSERT OR REPLACE INTO fact_stock_daily_hithink
SELECT
    {TRADE_DATE_SQL} AS trade_date,
    thscode AS stock_ts_code,
    open_price AS open,
    high_price AS high,
    low_price AS low,
    close_price AS close,
    volume,
    turnover,
    adjusted,
    ? AS source,
    current_timestamp AS updated_at
FROM (
    SELECT
        thscode, currency, interval, adjusted, date_ms,
        open_price, high_price, low_price, close_price, volume, turnover
    FROM read_parquet(?)
)
WHERE thscode IS NOT NULL
  AND date_ms IS NOT NULL
  AND currency = 'CNY'
  AND interval = '1d'
"""

INSERT_ADJ_SQL = f"""
INSERT OR REPLACE INTO fact_stock_adjustment_hithink
SELECT
    thscode AS stock_ts_code,
    {EX_DATE_SQL} AS ex_date,
    dividend_per_share,
    per_share_bonus,
    allotment_ratio,
    allotment_price,
    currency,
    ? AS source,
    current_timestamp AS updated_at
FROM (
    SELECT
        thscode, ticker, ex_date_ms,
        dividend_per_share, per_share_bonus,
        allotment_ratio, allotment_price, currency
    FROM read_parquet(?)
)
WHERE thscode IS NOT NULL
  AND ex_date_ms IS NOT NULL
"""

REL_CLOSE_TOLERANCE = 0.001  # 相对差 < 0.1%


class HithinkSyncError(RuntimeError):
    """入库失败。消息里不得带 key / 预签名 query。"""


def skip_reason_if_no_key() -> str | None:
    """daily-full 用：没 key 就跳过这一步，不让整条链红。"""

    if has_api_key():
        return None
    return "no-key"


def _connect(db_path: Path | str | None):
    if db_path is not None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(path))
    return connect()


def _open_writable(db_path: Path | str | None):
    """生产库被占写锁时改写 sidecar，不把路径写进返回值以外的地方。"""

    try:
        con = _connect(db_path)
        con.execute("SELECT 1")
        return con, False
    except duckdb.IOException as exc:
        if db_path is None or not is_lock_conflict(exc):
            raise
        sidecar = Path(str(db_path) + ".hithink-a.duckdb")
        con = duckdb.connect(str(sidecar))
        return con, True


def _resolve_parquet(
    kind: str,
    parquet: Path | str | None,
    dest_dir: Path,
    fetcher: Callable[[str, Path], Path] | None,
) -> Path:
    if parquet is not None:
        path = Path(parquet)
        if not path.is_file():
            raise HithinkSyncError(f"parquet 不存在: {path.name}")
        return path
    dest = dest_dir / f"hithink-{kind}.parquet"
    fetch = fetcher or fetch_dump_parquet
    return fetch(kind, dest)


def _daily_stats(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    row = con.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT stock_ts_code),
            MIN(trade_date),
            MAX(trade_date),
            COUNT(*) FILTER (WHERE high IS NULL OR low IS NULL)
        FROM fact_stock_daily_hithink
        """
    ).fetchone()
    return {
        "rows": int(row[0] or 0),
        "codes": int(row[1] or 0),
        "date_min": str(row[2]) if row[2] else None,
        "date_max": str(row[3]) if row[3] else None,
        "ohlc_nulls": int(row[4] or 0),
    }


def _adj_stats(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    row = con.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT stock_ts_code),
            MIN(ex_date),
            MAX(ex_date)
        FROM fact_stock_adjustment_hithink
        """
    ).fetchone()
    return {
        "rows": int(row[0] or 0),
        "codes": int(row[1] or 0),
        "date_min": str(row[2]) if row[2] else None,
        "date_max": str(row[3]) if row[3] else None,
    }


def table_fingerprint(con: duckdb.DuckDBPyConnection, table: str) -> str:
    """同一天两次全新同步应对上的结构指纹。只含计数与合计，不含个股名。"""

    if table == "fact_stock_daily_hithink":
        row = con.execute(
            """
            SELECT
                COUNT(*),
                COUNT(DISTINCT stock_ts_code),
                MIN(trade_date),
                MAX(trade_date),
                BIT_XOR(HASH(trade_date, stock_ts_code, close, turnover))
            FROM fact_stock_daily_hithink
            """
        ).fetchone()
    elif table == "fact_stock_adjustment_hithink":
        row = con.execute(
            """
            SELECT
                COUNT(*),
                COUNT(DISTINCT stock_ts_code),
                MIN(ex_date),
                MAX(ex_date),
                BIT_XOR(HASH(stock_ts_code, ex_date, dividend_per_share))
            FROM fact_stock_adjustment_hithink
            """
        ).fetchone()
    else:
        raise HithinkSyncError(f"未知指纹表: {table}")
    payload = "|".join("" if v is None else str(v) for v in row)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compare_recent_close(
    con: duckdb.DuckDBPyConnection,
    *,
    days: int = 20,
) -> dict[str, Any]:
    """与 ``fact_stock_daily`` 最近 N 个交易日逐只 close 比。默认只回计数。"""

    exists = con.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = 'fact_stock_daily'
        """
    ).fetchone()[0]
    if not exists:
        return {
            "compared": 0,
            "matched": 0,
            "rate": None,
            "old_only": 0,
            "new_only": 0,
            "days": 0,
            "skipped": "no-fact_stock_daily",
        }
    dates = [
        str(r[0])
        for r in con.execute(
            """
            SELECT DISTINCT trade_date FROM fact_stock_daily
            WHERE close IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [days],
        ).fetchall()
    ]
    if not dates:
        return {
            "compared": 0,
            "matched": 0,
            "rate": None,
            "old_only": 0,
            "new_only": 0,
            "days": 0,
        }
    row = con.execute(
        """
        WITH old AS (
            SELECT trade_date, stock_ts_code, close
            FROM fact_stock_daily
            WHERE trade_date IN (SELECT UNNEST(?::DATE[]))
              AND close IS NOT NULL
        ),
        new AS (
            SELECT trade_date, stock_ts_code, close
            FROM fact_stock_daily_hithink
            WHERE trade_date IN (SELECT UNNEST(?::DATE[]))
              AND close IS NOT NULL
        )
        SELECT
            COUNT(*) FILTER (
                WHERE o.close IS NOT NULL AND n.close IS NOT NULL
            ),
            COUNT(*) FILTER (
                WHERE o.close IS NOT NULL AND n.close IS NOT NULL
                  AND ABS(n.close - o.close) / ABS(o.close) < ?
            ),
            COUNT(*) FILTER (WHERE o.close IS NOT NULL AND n.close IS NULL),
            COUNT(*) FILTER (WHERE o.close IS NULL AND n.close IS NOT NULL)
        FROM old o
        FULL OUTER JOIN new n
          USING (trade_date, stock_ts_code)
        """,
        [dates, dates, REL_CLOSE_TOLERANCE],
    ).fetchone()
    compared = int(row[0] or 0)
    matched = int(row[1] or 0)
    return {
        "compared": compared,
        "matched": matched,
        "rate": (matched / compared) if compared else None,
        "old_only": int(row[2] or 0),
        "new_only": int(row[3] or 0),
        "days": len(dates),
        "date_min": min(dates),
        "date_max": max(dates),
    }


def sync_hithink_stock_daily(
    *,
    mode: str,
    parquet: Path | str | None = None,
    adjustments_parquet: Path | str | None = None,
    db_path: Path | str | None = None,
    skip_adjustments: bool = False,
    compare_days: int = 0,
    fetch_dump: Callable[[str, Path], Path] | None = None,
) -> dict[str, Any]:
    """把 dump 写入并跑表。``mode`` 只能是 full / incremental。"""

    if mode == "full":
        kind = KIND_FULL
    elif mode == "incremental":
        kind = KIND_INCREMENTAL
    else:
        raise HithinkSyncError("mode 只能是 full 或 incremental")

    con, sidecar = _open_writable(db_path)
    try:
        init_db(con)
        with tempfile.TemporaryDirectory(prefix="hithink-a-") as tmp:
            daily_path = _resolve_parquet(kind, parquet, Path(tmp), fetch_dump)
            con.execute(INSERT_DAILY_SQL, [SOURCE_BY_KIND[kind], str(daily_path)])
            adj_stats = None
            if not skip_adjustments:
                adj_path = _resolve_parquet(
                    KIND_ADJUSTMENTS, adjustments_parquet, Path(tmp), fetch_dump
                )
                con.execute(
                    INSERT_ADJ_SQL,
                    [SOURCE_BY_KIND[KIND_ADJUSTMENTS], str(adj_path)],
                )
                adj_stats = _adj_stats(con)
        daily = _daily_stats(con)
        result: dict[str, Any] = {
            "mode": mode,
            "kind": kind,
            "source": SOURCE_BY_KIND[kind],
            "sidecar": sidecar,
            "daily": daily,
            "adjustments": adj_stats,
            "fingerprint": table_fingerprint(con, "fact_stock_daily_hithink"),
        }
        if adj_stats is not None:
            result["adjustments_fingerprint"] = table_fingerprint(
                con, "fact_stock_adjustment_hithink"
            )
        if compare_days:
            result["compare"] = compare_recent_close(con, days=compare_days)
        return result
    finally:
        con.close()
