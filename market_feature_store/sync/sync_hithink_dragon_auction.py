"""同花顺龙虎榜 / 热榜 / 竞价 → 四张并跑表（工单 #41 D）。

龙虎榜一年：每日 ``board_type=all`` + ``hot_money``。
热榜一年：每日 ``hot-stock-list-history``。
竞价风向标 2026-01 起每日约 6 只；终态快照只日更（代码表 + 每批 100 码）。
个股名接住但不落库。游资名要落。
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb

from ..db import DB_PATH, init_db, is_lock_conflict
from ..hithink_client import HithinkAPIError, get_json, has_api_key

PATH_DRAGON = "/api/a-share/special-data/dragon-tiger-list"
PATH_HOT = "/api/a-share/special-data/hot-stock-list-history"
PATH_BENCH = "/api/a-share/auction/short-term-benchmark"
PATH_SNAP = "/api/a-share/auction/snapshot"
PATH_TICKERS = "/api/meta/tickers/list"

SRC_DRAGON = "hithink:dragon-tiger-list"
SRC_HOT_MONEY = "hithink:dragon-tiger-hot-money"
SRC_HOT = "hithink:hot-stock-list-history"
SRC_BENCH = "hithink:auction-benchmark"
SRC_SNAP = "hithink:auction-snapshot"

KIND_BENCH = "benchmark"
KIND_SNAP = "snapshot"
AUCTION_START = date(2026, 1, 1)
INCR_DAYS = 3
SNAP_BATCH = 100
TICKER_PAGE = 1000
EMPTY_TOKENS = ("code=1002", "code=1003", "code=5003")

DRAGON_STOCK_FIELDS = (
    "thscode",
    "ticker",
    "name",
    "concept_list",
    "change",
    "buy_value",
    "sell_value",
    "net_value",
    "net_rate",
    "org_net_value",
    "hot_money_net_value",
    "hot_rank",
    "range_days",
    "limit_reason",
)
HOT_MONEY_GROUP_FIELDS = ("name", "buying", "rows")
HOT_MONEY_ROW_FIELDS = (
    "thscode",
    "ticker",
    "name",
    "buy_value",
    "sell_value",
    "net_value",
    "net_rate",
    "org_net_value",
    "hot_money_net_value",
    "hot_money_item_net_value",
    "hot_money_item_net_rate",
    "hot_rank",
    "range_days",
)
HOT_RANK_FIELDS = ("thscode", "ticker", "name", "rank")
BENCH_FIELDS = ("thscode", "ticker", "name", "auction_pct", "tags")
SNAP_FIELDS = (
    "thscode",
    "ticker",
    "name",
    "auction_price",
    "auction_pct",
    "auction_volume",
    "auction_amount",
    "auction_unmatched",
    "auction_turnover_pct",
    "auction_yesterday_ratio_pct",
    "auction_volume_ratio",
    "pre_close_price",
    "open_price",
    "last_price",
    "float_market_cap",
)
CALENDAR_TABLES = (
    "fact_stock_daily_hithink",
    "fact_market_daily",
    "fact_stock_daily",
)

GetJson = Callable[..., dict[str, Any]]


class HithinkDragonSyncError(RuntimeError):
    """龙虎榜 / 竞价同步失败。消息里不得带 key。"""


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
        sidecar = Path(str(target) + ".hithink-d.duckdb")
        print("production db locked, writing sidecar", flush=True)
        return duckdb.connect(str(sidecar)), True


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema='main' AND table_name = ?
        """,
        [name],
    ).fetchone()
    return bool(row and row[0])


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _items(payload: dict[str, Any], key: str = "item") -> list[dict[str, Any]]:
    raw = _data(payload).get(key) or payload.get(key) or []
    if isinstance(raw, dict):
        raw = raw.get("item") or []
    return [row for row in raw if isinstance(row, dict)]


def _safe_get(getter: GetJson, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return getter(path, params=params)
    except HithinkAPIError as exc:
        text = str(exc)
        if any(token in text for token in EMPTY_TOKENS):
            return None
        raise


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
            return [
                r[0] if isinstance(r[0], date) else date.fromisoformat(str(r[0]))
                for r in rows
            ]
    raise HithinkDragonSyncError("没有交易日历")


def _dates_done(con: duckdb.DuckDBPyConnection, table: str, extra: str = "") -> set[date]:
    if not _table_exists(con, table):
        return set()
    sql = f"SELECT DISTINCT trade_date FROM {table}"
    if extra:
        sql += f" WHERE {extra}"
    return {
        r[0] if isinstance(r[0], date) else date.fromisoformat(str(r[0]))
        for r in con.execute(sql).fetchall()
    }


def fetch_dragon_all(day: date, getter: GetJson) -> list[dict[str, Any]]:
    payload = _safe_get(
        getter, PATH_DRAGON, {"board_type": "all", "date": day.isoformat()}
    )
    if payload is None:
        return []
    out = []
    for item in _items(payload, "stock_items"):
        row = {field: item.get(field) for field in DRAGON_STOCK_FIELDS}
        if row.get("thscode"):
            out.append(row)
    return out


def fetch_dragon_hot_money(day: date, getter: GetJson) -> list[dict[str, Any]]:
    payload = _safe_get(
        getter, PATH_DRAGON, {"board_type": "hot_money", "date": day.isoformat()}
    )
    if payload is None:
        return []
    out = []
    for group in _items(payload, "hot_money_items"):
        group_name = group.get("name")
        buying = group.get("buying")
        rows = group.get("rows") or []
        if not group_name:
            continue
        for item in rows:
            if not isinstance(item, dict) or not item.get("thscode"):
                continue
            row = {field: item.get(field) for field in HOT_MONEY_ROW_FIELDS}
            row["hot_money_name"] = group_name
            row["group_buying"] = buying
            out.append(row)
    return out


def fetch_hot_rank(day: date, getter: GetJson) -> list[dict[str, Any]]:
    payload = _safe_get(getter, PATH_HOT, {"date": day.isoformat()})
    if payload is None:
        return []
    out = []
    for item in _items(payload, "item"):
        row = {field: item.get(field) for field in HOT_RANK_FIELDS}
        if row.get("thscode"):
            out.append(row)
    return out


def fetch_benchmark(day: date, getter: GetJson) -> list[dict[str, Any]]:
    payload = _safe_get(getter, PATH_BENCH, {"date": day.isoformat()})
    if payload is None:
        return []
    out = []
    for item in _items(payload, "item"):
        row = {field: item.get(field) for field in BENCH_FIELDS}
        if row.get("thscode"):
            tags = row.get("tags")
            if isinstance(tags, list):
                row["tags"] = ",".join(str(t) for t in tags)
            out.append(row)
    return out


def fetch_ticker_codes(getter: GetJson) -> list[str]:
    offset = 0
    codes: list[str] = []
    while True:
        payload = _safe_get(
            getter,
            PATH_TICKERS,
            {
                "exchange": "SH,SZ,BJ",
                "asset_type": "a-share",
                "limit": TICKER_PAGE,
                "offset": offset,
            },
        )
        if payload is None:
            break
        page = _items(payload, "item")
        for item in page:
            code = item.get("thscode")
            if code:
                codes.append(str(code))
        if len(page) < TICKER_PAGE:
            break
        offset += TICKER_PAGE
    return codes


def fetch_auction_snapshot(codes: list[str], getter: GetJson) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(0, len(codes), SNAP_BATCH):
        batch = codes[i : i + SNAP_BATCH]
        payload = _safe_get(
            getter,
            PATH_SNAP,
            {"thscodes": ",".join(batch), "stage": "final"},
        )
        if payload is None:
            continue
        for item in _items(payload, "item"):
            row = {field: item.get(field) for field in SNAP_FIELDS}
            if row.get("thscode"):
                out.append(row)
    return out


def _flush(con: duckdb.DuckDBPyConnection, table: str, columns: list[str], rows: list[tuple], dest: Path) -> int:
    if not rows:
        return 0
    mem = duckdb.connect(":memory:")
    try:
        col_sql = ", ".join(f"{c} VARCHAR" if c != "trade_date" else "trade_date DATE" for c in columns)
        # 数值列用 DOUBLE/INTEGER 会在 COPY 时更稳，这里先全当 VARCHAR 再 INSERT SELECT 让 DuckDB 转型。
        mem.execute(f"CREATE TABLE t ({col_sql})")
        placeholders = ",".join("?" * len(columns))
        mem.executemany(f"INSERT INTO t VALUES ({placeholders})", rows)
        mem.execute(f"COPY t TO '{dest}' (FORMAT PARQUET)")
    finally:
        mem.close()
    dest_cols = ", ".join(columns)
    con.execute(
        f"""
        INSERT OR REPLACE INTO {table} ({dest_cols}, updated_at)
        SELECT {dest_cols}, now() FROM read_parquet(?)
        """,
        [str(dest)],
    )
    return len(rows)


def _count_stats(con: duckdb.DuckDBPyConnection, table: str) -> dict[str, Any]:
    if not _table_exists(con, table):
        return {"rows": 0, "days": 0, "date_min": None, "date_max": None}
    row = con.execute(
        f"""
        SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date)
        FROM {table}
        """
    ).fetchone()
    return {
        "rows": int(row[0] or 0),
        "days": int(row[1] or 0),
        "date_min": str(row[2]) if row[2] else None,
        "date_max": str(row[3]) if row[3] else None,
    }


def table_fingerprint(con: duckdb.DuckDBPyConnection) -> str:
    parts: list[str] = []
    specs = (
        (
            "fact_dragon_tiger_hithink",
            "HASH(trade_date, stock_ts_code, net_value)",
        ),
        (
            "fact_dragon_hot_money_hithink",
            "HASH(trade_date, hot_money_name, stock_ts_code, net_value)",
        ),
        (
            "fact_hot_stock_rank_hithink",
            "HASH(trade_date, stock_ts_code, rank)",
        ),
        (
            "fact_auction_hithink",
            "HASH(trade_date, stock_ts_code, kind, auction_pct)",
        ),
    )
    for table, expr in specs:
        if not _table_exists(con, table):
            parts.append(f"{table}:0")
            continue
        row = con.execute(
            f"SELECT COUNT(*), BIT_XOR({expr}) FROM {table}"
        ).fetchone()
        parts.append(f"{table}:{row[0]}:{row[1]}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def compare_net_amount(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    if not _table_exists(con, "fact_dragon_tiger_daily"):
        return {"compared": 0, "matched": 0, "rate": None}
    row = con.execute(
        """
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE ABS(h.net_value - o.net_amount) < 1e-6),
            COUNT(*) FILTER (WHERE ABS(h.net_value/1e8 - o.net_amount) < 0.01),
            MEDIAN(ABS(h.net_value - o.net_amount)),
            MEDIAN(ABS(h.net_value/1e8 - o.net_amount))
        FROM fact_dragon_tiger_hithink h
        INNER JOIN fact_dragon_tiger_daily o USING (trade_date, stock_ts_code)
        WHERE h.trade_date >= CURRENT_DATE - INTERVAL 365 DAY
          AND h.net_value IS NOT NULL AND o.net_amount IS NOT NULL
        """
    ).fetchone()
    compared = int(row[0] or 0)
    matched_raw = int(row[1] or 0)
    matched_yi = int(row[2] or 0)
    best = max(matched_raw, matched_yi)
    return {
        "compared": compared,
        "matched_raw": matched_raw,
        "matched_yi": matched_yi,
        "matched": best,
        "unit": "yi" if matched_yi >= matched_raw else "raw",
        "rate": (best / compared) if compared else None,
        "median_abs_raw": float(row[3]) if row[3] is not None else None,
        "median_abs_yi": float(row[4]) if row[4] is not None else None,
    }


def compare_hot_money_groups(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    if not _table_exists(con, "fact_dragon_seat_daily"):
        return {"compared": 0, "matched": 0, "rate": None}
    row = con.execute(
        """
        WITH h AS (
            SELECT trade_date, COUNT(DISTINCT hot_money_name) AS n
            FROM fact_dragon_hot_money_hithink
            GROUP BY 1
        ),
        o AS (
            SELECT trade_date, COUNT(DISTINCT COALESCE(hm_name, exalter)) AS n
            FROM fact_dragon_seat_daily
            WHERE seat_type = '游资' OR hm_name IS NOT NULL
            GROUP BY 1
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


def _pick_days(
    con: duckdb.DuckDBPyConnection,
    *,
    start: date,
    end: date,
    mode: str,
    dates: Iterable[date] | None,
    done: set[date],
    resume: bool,
) -> list[date]:
    if dates is not None:
        days = [d for d in dates if start <= d <= end]
    else:
        days = trading_days(con, start, end)
        if mode == "incremental":
            days = days[-INCR_DAYS:]
    if resume:
        days = [d for d in days if d not in done]
    return days


def sync_hithink_dragon_auction(
    *,
    mode: str,
    db_path: Path | str | None = None,
    end_date: date | None = None,
    resume: bool = False,
    compare: bool = False,
    skip_auction_snapshot: bool = False,
    dates: Iterable[date] | None = None,
    get_json_fn: GetJson | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    if mode not in {"full", "incremental"}:
        raise HithinkDragonSyncError("mode 只能是 full 或 incremental")
    getter = get_json_fn or get_json
    today = today or date.today()
    end = end_date or today
    year_start = end - timedelta(days=365)
    bench_start = max(AUCTION_START, year_start) if mode == "incremental" else AUCTION_START

    con, sidecar = _open_writable(db_path)
    try:
        needed = (
            "fact_dragon_tiger_hithink",
            "fact_dragon_hot_money_hithink",
            "fact_hot_stock_rank_hithink",
            "fact_auction_hithink",
        )
        if any(not _table_exists(con, name) for name in needed):
            init_db(con)
        print(f"opened db sidecar={sidecar} mode={mode}", flush=True)

        dragon_days = _pick_days(
            con,
            start=year_start,
            end=end,
            mode=mode,
            dates=dates,
            done=_dates_done(con, "fact_dragon_tiger_hithink") if resume else set(),
            resume=resume,
        )
        hot_days = _pick_days(
            con,
            start=year_start,
            end=end,
            mode=mode,
            dates=dates,
            done=_dates_done(con, "fact_hot_stock_rank_hithink") if resume else set(),
            resume=resume,
        )
        bench_days = _pick_days(
            con,
            start=bench_start,
            end=end,
            mode=mode,
            dates=dates,
            done=_dates_done(con, "fact_auction_hithink", extra="kind='benchmark'")
            if resume
            else set(),
            resume=resume,
        )

        requests = 0
        empty_days = 0
        written = {
            "dragon": 0,
            "hot_money": 0,
            "hot_rank": 0,
            "benchmark": 0,
            "snapshot": 0,
        }
        with tempfile.TemporaryDirectory(prefix="hithink-d-") as tmp:
            tmp_path = Path(tmp)
            batch_i = 0

            dragon_buf: list[tuple] = []
            money_buf: list[tuple] = []
            for i, day in enumerate(dragon_days, start=1):
                stocks = fetch_dragon_all(day, getter)
                requests += 1
                groups = fetch_dragon_hot_money(day, getter)
                requests += 1
                if not stocks:
                    empty_days += 1
                for item in stocks:
                    item.get("name")
                    dragon_buf.append(
                        (
                            day,
                            str(item.get("thscode")),
                            item.get("ticker"),
                            item.get("change"),
                            item.get("buy_value"),
                            item.get("sell_value"),
                            item.get("net_value"),
                            item.get("net_rate"),
                            item.get("org_net_value"),
                            item.get("hot_money_net_value"),
                            item.get("hot_rank"),
                            item.get("range_days"),
                            item.get("limit_reason"),
                            SRC_DRAGON,
                        )
                    )
                for item in groups:
                    item.get("name")
                    money_buf.append(
                        (
                            day,
                            str(item.get("hot_money_name")),
                            str(item.get("thscode")),
                            item.get("ticker"),
                            item.get("group_buying"),
                            item.get("buy_value"),
                            item.get("sell_value"),
                            item.get("net_value"),
                            item.get("net_rate"),
                            item.get("org_net_value"),
                            item.get("hot_money_net_value"),
                            item.get("hot_money_item_net_value"),
                            item.get("hot_money_item_net_rate"),
                            item.get("hot_rank"),
                            item.get("range_days"),
                            SRC_HOT_MONEY,
                        )
                    )
                written["dragon"] += len(stocks)
                written["hot_money"] += len(groups)
                if len(dragon_buf) >= 2000:
                    batch_i += 1
                    _flush(
                        con,
                        "fact_dragon_tiger_hithink",
                        [
                            "trade_date",
                            "stock_ts_code",
                            "ticker",
                            "pct_chg",
                            "buy_value",
                            "sell_value",
                            "net_value",
                            "net_rate",
                            "org_net_value",
                            "hot_money_net_value",
                            "hot_rank",
                            "range_days",
                            "limit_reason",
                            "source",
                        ],
                        dragon_buf,
                        tmp_path / f"d-{batch_i}.parquet",
                    )
                    dragon_buf = []
                if len(money_buf) >= 2000:
                    batch_i += 1
                    _flush(
                        con,
                        "fact_dragon_hot_money_hithink",
                        [
                            "trade_date",
                            "hot_money_name",
                            "stock_ts_code",
                            "ticker",
                            "group_buying",
                            "buy_value",
                            "sell_value",
                            "net_value",
                            "net_rate",
                            "org_net_value",
                            "hot_money_net_value",
                            "hot_money_item_net_value",
                            "hot_money_item_net_rate",
                            "hot_rank",
                            "range_days",
                            "source",
                        ],
                        money_buf,
                        tmp_path / f"m-{batch_i}.parquet",
                    )
                    money_buf = []
                if i % 50 == 0 or i == len(dragon_days):
                    print(
                        f"dragon {i}/{len(dragon_days)} "
                        f"rows={written['dragon']} groups={written['hot_money']}",
                        flush=True,
                    )
            if dragon_buf:
                batch_i += 1
                _flush(
                    con,
                    "fact_dragon_tiger_hithink",
                    [
                        "trade_date",
                        "stock_ts_code",
                        "ticker",
                        "pct_chg",
                        "buy_value",
                        "sell_value",
                        "net_value",
                        "net_rate",
                        "org_net_value",
                        "hot_money_net_value",
                        "hot_rank",
                        "range_days",
                        "limit_reason",
                        "source",
                    ],
                    dragon_buf,
                    tmp_path / f"d-{batch_i}.parquet",
                )
            if money_buf:
                batch_i += 1
                _flush(
                    con,
                    "fact_dragon_hot_money_hithink",
                    [
                        "trade_date",
                        "hot_money_name",
                        "stock_ts_code",
                        "ticker",
                        "group_buying",
                        "buy_value",
                        "sell_value",
                        "net_value",
                        "net_rate",
                        "org_net_value",
                        "hot_money_net_value",
                        "hot_money_item_net_value",
                        "hot_money_item_net_rate",
                        "hot_rank",
                        "range_days",
                        "source",
                    ],
                    money_buf,
                    tmp_path / f"m-{batch_i}.parquet",
                )

            hot_buf: list[tuple] = []
            for i, day in enumerate(hot_days, start=1):
                ranks = fetch_hot_rank(day, getter)
                requests += 1
                if not ranks:
                    empty_days += 1
                for item in ranks:
                    item.get("name")
                    hot_buf.append(
                        (
                            day,
                            str(item.get("thscode")),
                            item.get("ticker"),
                            item.get("rank"),
                            SRC_HOT,
                        )
                    )
                written["hot_rank"] += len(ranks)
                if i % 50 == 0 or i == len(hot_days):
                    print(
                        f"hot {i}/{len(hot_days)} rows={written['hot_rank']}",
                        flush=True,
                    )
            if hot_buf:
                batch_i += 1
                _flush(
                    con,
                    "fact_hot_stock_rank_hithink",
                    ["trade_date", "stock_ts_code", "ticker", "rank", "source"],
                    hot_buf,
                    tmp_path / f"h-{batch_i}.parquet",
                )

            bench_buf: list[tuple] = []
            for i, day in enumerate(bench_days, start=1):
                items = fetch_benchmark(day, getter)
                requests += 1
                if not items:
                    empty_days += 1
                for item in items:
                    item.get("name")
                    bench_buf.append(
                        (
                            day,
                            str(item.get("thscode")),
                            KIND_BENCH,
                            item.get("ticker"),
                            None,
                            item.get("auction_pct"),
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            item.get("tags"),
                            SRC_BENCH,
                        )
                    )
                written["benchmark"] += len(items)
                if i % 50 == 0 or i == len(bench_days):
                    print(
                        f"benchmark {i}/{len(bench_days)} rows={written['benchmark']}",
                        flush=True,
                    )
            if bench_buf:
                batch_i += 1
                _flush(
                    con,
                    "fact_auction_hithink",
                    [
                        "trade_date",
                        "stock_ts_code",
                        "kind",
                        "ticker",
                        "auction_price",
                        "auction_pct",
                        "auction_volume",
                        "auction_amount",
                        "auction_unmatched",
                        "auction_turnover_pct",
                        "auction_yesterday_ratio_pct",
                        "auction_volume_ratio",
                        "pre_close_price",
                        "open_price",
                        "last_price",
                        "float_market_cap",
                        "tags",
                        "source",
                    ],
                    bench_buf,
                    tmp_path / f"b-{batch_i}.parquet",
                )

            # 终态快照端点没有日期参数（只收 thscodes + stage），拿回来的永远是
            # 「当前」那一份。用 end 当 trade_date 只在 end 就是今天时成立；
            # --end-date 指到过去、或跨零点跑，会把今天的竞价盖上别人的日戳。
            snapshot_skipped = None
            if not skip_auction_snapshot and end != today:
                snapshot_skipped = f"end-date {end.isoformat()} != today {today.isoformat()}"
                print(f"snapshot skipped: {snapshot_skipped}", flush=True)
            if not skip_auction_snapshot and snapshot_skipped is None:
                codes = fetch_ticker_codes(getter)
                requests += max(1, (len(codes) + TICKER_PAGE - 1) // TICKER_PAGE) if codes else 1
                snaps = fetch_auction_snapshot(codes, getter)
                requests += (len(codes) + SNAP_BATCH - 1) // SNAP_BATCH if codes else 0
                snap_rows = []
                for item in snaps:
                    item.get("name")
                    snap_rows.append(
                        (
                            end,
                            str(item.get("thscode")),
                            KIND_SNAP,
                            item.get("ticker"),
                            item.get("auction_price"),
                            item.get("auction_pct"),
                            item.get("auction_volume"),
                            item.get("auction_amount"),
                            item.get("auction_unmatched"),
                            item.get("auction_turnover_pct"),
                            item.get("auction_yesterday_ratio_pct"),
                            item.get("auction_volume_ratio"),
                            item.get("pre_close_price"),
                            item.get("open_price"),
                            item.get("last_price"),
                            item.get("float_market_cap"),
                            None,
                            SRC_SNAP,
                        )
                    )
                written["snapshot"] = len(snap_rows)
                if snap_rows:
                    batch_i += 1
                    _flush(
                        con,
                        "fact_auction_hithink",
                        [
                            "trade_date",
                            "stock_ts_code",
                            "kind",
                            "ticker",
                            "auction_price",
                            "auction_pct",
                            "auction_volume",
                            "auction_amount",
                            "auction_unmatched",
                            "auction_turnover_pct",
                            "auction_yesterday_ratio_pct",
                            "auction_volume_ratio",
                            "pre_close_price",
                            "open_price",
                            "last_price",
                            "float_market_cap",
                            "tags",
                            "source",
                        ],
                        snap_rows,
                        tmp_path / f"s-{batch_i}.parquet",
                    )
                print(
                    f"snapshot codes={len(codes)} rows={len(snap_rows)}",
                    flush=True,
                )

        stats = {
            "dragon": _count_stats(con, "fact_dragon_tiger_hithink"),
            "hot_money": _count_stats(con, "fact_dragon_hot_money_hithink"),
            "hot_rank": _count_stats(con, "fact_hot_stock_rank_hithink"),
            "auction": _count_stats(con, "fact_auction_hithink"),
        }
        result: dict[str, Any] = {
            "mode": mode,
            "sidecar": sidecar,
            "rows_written": written,
            "empty_days": empty_days,
            "requests": requests,
            "tables": stats,
            "fingerprint": table_fingerprint(con),
        }
        if snapshot_skipped:
            result["snapshot_skipped"] = snapshot_skipped
        if compare:
            result["net_compare"] = compare_net_amount(con)
            result["hot_money_compare"] = compare_hot_money_groups(con)
        return result
    finally:
        con.close()
