"""同花顺官方板块 / 指数日 K → ``fact_sector_kline_daily``（工单 #41 B）。

先拉 4 个 tag 的目录进 ``dim_sector_hithink``，再对每个 ``.TI`` 加指定指数码
各打一次历史 K。窗口**不得超过 1500 天**——上游超了不报错，只静默返回空。
日更只拉近 5 天。成分股是当前快照，带 ``captured_at``，不回写
``fact_sector_stock_daily``。``.FP`` 与 ``.TI`` 只按名字精确配对，对不上记缺口。
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import duckdb

from ..db import DB_PATH, init_db, is_lock_conflict
from ..hithink_client import get_json, has_api_key, ms_to_shanghai_date, shanghai_midnight_ms

TRADE_DATE_SQL = (
    "CAST(to_timestamp(date_ms/1000) AT TIME ZONE 'UTC' + INTERVAL 8 HOUR AS DATE)"
)

CATALOG_TAGS = ("cn_concept", "industry", "region", "tszs")
INDEX_CODES = (
    "000001.SH",
    "399001.SZ",
    "399006.SZ",
    "000300.SH",
    "000905.SH",
    "000852.SH",
)
# 闭区间天数。1500 是上游静默空的实测线，请求必须严格小于它。
MAX_WINDOW_DAYS = 1500
FULL_WINDOW_DAYS = 1499
INCR_WINDOW_DAYS = 5
BC_BATTERY_CODE = "886053.TI"
BC_BATTERY_START = date(2023, 9, 6)

SOURCE_CATALOG = "hithink:ths-index-list"
SOURCE_KLINE = "hithink:index-historical"
SOURCE_CONSTITUENT = "hithink:ths-stock-list"

CATALOG_FIELDS = ("thscode", "name")
HISTORICAL_BAR_FIELDS = (
    "date_ms",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "turnover",
)
CONSTITUENT_FIELDS = ("thscode", "ticker", "name")

GetJson = Callable[..., dict[str, Any]]


class HithinkSectorSyncError(RuntimeError):
    """板块同步失败。消息里不得带 key。"""


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
        sidecar = Path(str(target) + ".hithink-b.duckdb")
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


def window_ms(end_day: date, days: int) -> tuple[int, int]:
    """闭区间 [end_day - (days-1), end_day]，跨度 days 天，必须 < MAX_WINDOW_DAYS。"""

    if days < 1:
        raise HithinkSectorSyncError("窗口至少 1 天")
    if days >= MAX_WINDOW_DAYS:
        raise HithinkSectorSyncError(
            f"窗口 {days} 天 ≥ {MAX_WINDOW_DAYS}，上游会静默空"
        )
    start_day = end_day - timedelta(days=days - 1)
    start_ms = shanghai_midnight_ms(start_day)
    end_ms = shanghai_midnight_ms(end_day)
    span_days = (end_ms - start_ms) / 86_400_000
    if span_days >= MAX_WINDOW_DAYS:
        raise HithinkSectorSyncError("窗口毫秒跨度超线")
    return start_ms, end_ms


def fetch_catalog(tag: str, getter: GetJson) -> list[dict[str, Any]]:
    payload = getter("/api/a-share-index/catalog/ths-index-list", params={"tag": tag})
    rows = []
    for item in _items(payload):
        # 请求了就必须接住
        thscode = item.get("thscode")
        name = item.get("name")
        if thscode:
            rows.append({"thscode": str(thscode), "name": name, "category": tag})
    return rows


def fetch_historical(
    thscode: str, start_ms: int, end_ms: int, getter: GetJson
) -> list[dict[str, Any]]:
    payload = getter(
        "/api/a-share-index/prices/historical",
        params={
            "thscode": thscode,
            "interval": "1d",
            "start": start_ms,
            "end": end_ms,
        },
    )
    bars = []
    for item in _items(payload):
        bar = {field: item.get(field) for field in HISTORICAL_BAR_FIELDS}
        if bar["date_ms"] is None:
            continue
        bars.append(bar)
    return bars


def fetch_constituents(thscode: str, getter: GetJson) -> list[dict[str, Any]]:
    payload = getter(
        "/api/a-share-index/constituents/ths-stock-list",
        params={"thscode": thscode},
    )
    rows = []
    for item in _items(payload):
        code = item.get("thscode")
        ticker = item.get("ticker")
        _name = item.get("name")  # 接住但不落库：产品面不出个股名
        if code:
            rows.append({"thscode": str(code), "ticker": ticker, "name": _name})
    return rows


def _upsert_dim(con: duckdb.DuckDBPyConnection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    con.executemany(
        """
        INSERT INTO dim_sector_hithink
            (sector_ts_code, sector_name, category, source, updated_at)
        VALUES (?, ?, ?, ?, now())
        ON CONFLICT (sector_ts_code) DO UPDATE SET
            sector_name = excluded.sector_name,
            category = excluded.category,
            source = excluded.source,
            updated_at = now()
        """,
        [
            (row["thscode"], row.get("name"), row["category"], SOURCE_CATALOG)
            for row in rows
        ],
    )
    return len(rows)


def _bars_to_rows(thscode: str, bars: list[dict[str, Any]]) -> list[tuple]:
    rows = []
    for bar in bars:
        day = ms_to_shanghai_date(int(bar["date_ms"]))
        rows.append(
            (
                day,
                thscode,
                bar.get("open_price"),
                bar.get("high_price"),
                bar.get("low_price"),
                bar.get("close_price"),
                bar.get("volume"),
                bar.get("turnover"),
                SOURCE_KLINE,
            )
        )
    return rows


def _flush_parquet(
    con: duckdb.DuckDBPyConnection,
    *,
    create_sql: str,
    insert_mem_sql: str,
    copy_into_sql: str,
    rows: list[tuple],
    parquet_path: Path,
) -> int:
    """内存库攒批 → parquet → 生产库一次 INSERT。避免对 3G 库逐行 executemany。"""

    if not rows:
        return 0
    mem = duckdb.connect(":memory:")
    try:
        mem.execute(create_sql)
        mem.executemany(insert_mem_sql, rows)
        mem.execute(f"COPY t TO '{parquet_path}' (FORMAT PARQUET)")
    finally:
        mem.close()
    con.execute(copy_into_sql, [str(parquet_path)])
    return len(rows)


def _flush_kline(con: duckdb.DuckDBPyConnection, rows: list[tuple], dest: Path) -> int:
    return _flush_parquet(
        con,
        create_sql="""
            CREATE TABLE t (
                trade_date DATE, sector_ts_code TEXT,
                open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
                volume DOUBLE, turnover DOUBLE, source TEXT
            )
        """,
        insert_mem_sql="INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?)",
        copy_into_sql="""
            INSERT OR REPLACE INTO fact_sector_kline_daily
                (trade_date, sector_ts_code, open, high, low, close, volume,
                 turnover, source, updated_at)
            SELECT trade_date, sector_ts_code, open, high, low, close, volume,
                   turnover, source, now()
            FROM read_parquet(?)
        """,
        rows=rows,
        parquet_path=dest,
    )


def _flush_constituents(
    con: duckdb.DuckDBPyConnection, rows: list[tuple], dest: Path
) -> int:
    return _flush_parquet(
        con,
        create_sql="""
            CREATE TABLE t (
                captured_at DATE, sector_ts_code TEXT, stock_ts_code TEXT,
                ticker TEXT, source TEXT
            )
        """,
        insert_mem_sql="INSERT INTO t VALUES (?,?,?,?,?)",
        copy_into_sql="""
            INSERT OR REPLACE INTO fact_sector_constituent_hithink
                (captured_at, sector_ts_code, stock_ts_code, ticker, in_index,
                 source, updated_at)
            SELECT captured_at, sector_ts_code, stock_ts_code, ticker, 1, source, now()
            FROM read_parquet(?)
        """,
        rows=rows,
        parquet_path=dest,
    )


def _codes_already_fresh(
    con: duckdb.DuckDBPyConnection, end_day: date
) -> set[str]:
    rows = con.execute(
        """
        SELECT sector_ts_code FROM fact_sector_kline_daily
        GROUP BY 1
        HAVING MAX(trade_date) >= ? AND COUNT(*) >= 100
        """,
        [end_day],
    ).fetchall()
    return {str(r[0]) for r in rows}


def table_fingerprint(con: duckdb.DuckDBPyConnection) -> str:
    row = con.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT sector_ts_code),
            MIN(trade_date),
            MAX(trade_date),
            BIT_XOR(HASH(trade_date, sector_ts_code, close, turnover))
        FROM fact_sector_kline_daily
        """
    ).fetchone()
    payload = "|".join("" if v is None else str(v) for v in row)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def kline_stats(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    row = con.execute(
        """
        SELECT COUNT(*), COUNT(DISTINCT sector_ts_code),
               MIN(trade_date), MAX(trade_date),
               COUNT(*) FILTER (WHERE high IS NULL OR low IS NULL)
        FROM fact_sector_kline_daily
        """
    ).fetchone()
    return {
        "rows": int(row[0] or 0),
        "codes": int(row[1] or 0),
        "date_min": str(row[2]) if row[2] else None,
        "date_max": str(row[3]) if row[3] else None,
        "ohlc_nulls": int(row[4] or 0),
    }


def coverage_old_ti(con: duckdb.DuckDBPyConnection, as_of: date) -> dict[str, Any]:
    exists = con.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema='main' AND table_name='fact_sector_daily'
        """
    ).fetchone()[0]
    if not exists:
        return {"old_ti": 0, "covered": 0, "through_as_of": 0, "missing": 0}
    row = con.execute(
        """
        WITH old_ti AS (
            SELECT DISTINCT sector_ts_code
            FROM fact_sector_daily
            WHERE sector_ts_code LIKE '%.TI'
        )
        SELECT
            (SELECT COUNT(*) FROM old_ti),
            (SELECT COUNT(*) FROM old_ti o
             WHERE EXISTS (
                 SELECT 1 FROM fact_sector_kline_daily k
                 WHERE k.sector_ts_code = o.sector_ts_code
             )),
            (SELECT COUNT(*) FROM old_ti o
             WHERE EXISTS (
                 SELECT 1 FROM fact_sector_kline_daily k
                 WHERE k.sector_ts_code = o.sector_ts_code
                   AND k.trade_date = ?
             ))
        """,
        [as_of],
    ).fetchone()
    old_ti, covered, through = (int(row[0] or 0), int(row[1] or 0), int(row[2] or 0))
    return {
        "old_ti": old_ti,
        "covered": covered,
        "through_as_of": through,
        "missing": old_ti - covered,
    }


def compare_pct_chg(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    exists = con.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema='main' AND table_name='fact_sector_daily'
        """
    ).fetchone()[0]
    if not exists:
        return {"compared": 0, "matched": 0, "rate": None, "median_rel_diff": None}
    row = con.execute(
        """
        WITH k AS (
            SELECT trade_date, sector_ts_code, close,
                   (close / LAG(close) OVER (
                       PARTITION BY sector_ts_code ORDER BY trade_date
                   ) - 1) * 100 AS pct
            FROM fact_sector_kline_daily
        ),
        j AS (
            SELECT k.pct AS new_pct, o.pct_chg AS old_pct,
                   ABS(k.pct - o.pct_chg) AS abs_diff,
                   CASE
                     WHEN o.pct_chg IS NULL OR o.pct_chg = 0 THEN NULL
                     ELSE ABS(k.pct - o.pct_chg) / ABS(o.pct_chg)
                   END AS rel_diff
            FROM k
            INNER JOIN fact_sector_daily o
              USING (trade_date, sector_ts_code)
            WHERE k.pct IS NOT NULL AND o.pct_chg IS NOT NULL
        )
        SELECT
            COUNT(*),
            COUNT(*) FILTER (
                WHERE abs_diff < 0.05 OR (rel_diff IS NOT NULL AND rel_diff < 0.01)
            ),
            MEDIAN(rel_diff),
            MEDIAN(abs_diff)
        FROM j
        """
    ).fetchone()
    compared = int(row[0] or 0)
    matched = int(row[1] or 0)
    return {
        "compared": compared,
        "matched": matched,
        "rate": (matched / compared) if compared else None,
        "median_rel_diff": float(row[2]) if row[2] is not None else None,
        "median_abs_diff": float(row[3]) if row[3] is not None else None,
    }


def map_fp_names(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """``.FP`` 与 ``.TI`` 只按名字精确相等配对，一对多记缺口，不模糊。"""

    exists = con.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema='main' AND table_name='fact_sector_daily'
        """
    ).fetchone()[0]
    if not exists:
        return {"matched": [], "gaps": [], "ti_name_diff": []}
    fp_rows = con.execute(
        """
        SELECT sector_ts_code, ANY_VALUE(sector_name)
        FROM fact_sector_daily
        WHERE sector_ts_code LIKE '%.FP' AND sector_name IS NOT NULL
        GROUP BY 1
        """
    ).fetchall()
    ti_rows = con.execute(
        """
        SELECT sector_ts_code, sector_name
        FROM dim_sector_hithink
        WHERE sector_name IS NOT NULL
        """
    ).fetchall()
    by_name: dict[str, list[str]] = {}
    for code, name in ti_rows:
        by_name.setdefault(str(name), []).append(str(code))
    matched: list[tuple[str, str, str]] = []
    gaps: list[tuple[str, str, str]] = []
    for fp, name in fp_rows:
        hits = by_name.get(str(name), [])
        if len(hits) == 1:
            matched.append((str(fp), str(name), hits[0]))
        elif len(hits) > 1:
            gaps.append((str(fp), str(name), "ambiguous"))
        else:
            gaps.append((str(fp), str(name), "unmatched"))
    old_ti = con.execute(
        """
        SELECT sector_ts_code, ANY_VALUE(sector_name)
        FROM fact_sector_daily
        WHERE sector_ts_code LIKE '%.TI' AND sector_name IS NOT NULL
        GROUP BY 1
        """
    ).fetchall()
    hithink_name = {
        str(code): name
        for code, name in con.execute(
            "SELECT sector_ts_code, sector_name FROM dim_sector_hithink"
        ).fetchall()
    }
    ti_name_diff = []
    for code, old_name in old_ti:
        new_name = hithink_name.get(str(code))
        if new_name and new_name != old_name:
            ti_name_diff.append((str(code), str(old_name), str(new_name)))
    return {
        "matched": matched,
        "gaps": gaps,
        "ti_name_diff": ti_name_diff,
        "fp_total": len(fp_rows),
        "old_ti_total": len(old_ti),
    }


def render_fp_mapping(mapping: dict[str, Any]) -> str:
    lines = [
        "# 同花顺 `.TI` ↔ 复盘会 `.FP` 名字对照（精确匹配，不猜）",
        "",
        f"日期：{date.today().isoformat()}。只按名字**完全相等**配对；",
        "一对多或对不上都进缺口，不做模糊匹配（「芯片」≠「芯片概念」）。",
        "",
        f"- `.FP` 总数：{mapping.get('fp_total', len(mapping['matched']) + len(mapping['gaps']))}",
        f"- 名字对上：{len(mapping['matched'])}",
        f"- 缺口：{len(mapping['gaps'])}",
        f"- 旧 `.TI` 同码不同名：{len(mapping['ti_name_diff'])}（不是映射，只记账）",
        "",
        "## 对上",
        "",
        "| 复盘会 .FP | 名字 | 同花顺 .TI |",
        "|---|---|---|",
    ]
    for fp, name, ti in sorted(mapping["matched"]):
        lines.append(f"| `{fp}` | {name} | `{ti}` |")
    lines += ["", "## 缺口", "", "| 复盘会 .FP | 名字 | 原因 |", "|---|---|---|"]
    for fp, name, reason in sorted(mapping["gaps"]):
        lines.append(f"| `{fp}` | {name} | {reason} |")
    lines += [
        "",
        "## 旧 .TI 同码不同名",
        "",
        "| 代码 | 我们库里的名字 | 同花顺目录名 |",
        "|---|---|---|",
    ]
    for code, old, new in sorted(mapping["ti_name_diff"]):
        lines.append(f"| `{code}` | {old} | {new} |")
    lines.append("")
    return "\n".join(lines)


def sync_hithink_sector_kline(
    *,
    mode: str,
    db_path: Path | str | None = None,
    skip_constituents: bool = False,
    resume: bool = False,
    limit: int | None = None,
    end_date: date | None = None,
    compare: bool = False,
    mapping_path: Path | str | None = None,
    get_json_fn: GetJson | None = None,
) -> dict[str, Any]:
    if mode == "full":
        days = FULL_WINDOW_DAYS
    elif mode == "incremental":
        days = INCR_WINDOW_DAYS
    else:
        raise HithinkSectorSyncError("mode 只能是 full 或 incremental")

    getter = get_json_fn or get_json
    end_day = end_date or date.today()
    start_ms, end_ms = window_ms(end_day, days)

    con, sidecar = _open_writable(db_path)
    try:
        init_db(con)
        catalog_rows: list[dict[str, Any]] = []
        for tag in CATALOG_TAGS:
            catalog_rows.extend(fetch_catalog(tag, getter))
        for code in INDEX_CODES:
            catalog_rows.append(
                {"thscode": code, "name": None, "category": "index"}
            )
        dim_n = _upsert_dim(con, catalog_rows)

        codes = [row["thscode"] for row in catalog_rows]
        if resume:
            fresh = _codes_already_fresh(con, end_day)
            codes = [c for c in codes if c not in fresh]
        if limit is not None:
            codes = codes[:limit]

        written = 0
        empty = 0
        kline_buf: list[tuple] = []
        with tempfile.TemporaryDirectory(prefix="hithink-b-") as tmp:
            tmp_path = Path(tmp)
            for i, code in enumerate(codes, start=1):
                bars = fetch_historical(code, start_ms, end_ms, getter)
                if bars:
                    kline_buf.extend(_bars_to_rows(code, bars))
                    written += len(bars)
                else:
                    empty += 1
                if len(kline_buf) >= 40_000 or i == len(codes):
                    _flush_kline(con, kline_buf, tmp_path / f"kline-{i}.parquet")
                    kline_buf = []
                if i % 50 == 0 or i == len(codes):
                    print(
                        f"kline {i}/{len(codes)} written_bars={written} empty={empty}",
                        flush=True,
                    )

            constituent_n = 0
            if not skip_constituents:
                member_codes = [
                    row["thscode"]
                    for row in catalog_rows
                    if row["category"] != "index"
                ]
                if limit is not None:
                    member_codes = member_codes[:limit]
                const_buf: list[tuple] = []
                for i, code in enumerate(member_codes, start=1):
                    members = fetch_constituents(code, getter)
                    const_buf.extend(
                        (
                            end_day,
                            code,
                            row["thscode"],
                            row.get("ticker"),
                            SOURCE_CONSTITUENT,
                        )
                        for row in members
                    )
                    constituent_n += len(members)
                    if len(const_buf) >= 20_000 or i == len(member_codes):
                        _flush_constituents(
                            con, const_buf, tmp_path / f"const-{i}.parquet"
                        )
                        const_buf = []
                    if i % 50 == 0 or i == len(member_codes):
                        print(
                            f"constituents {i}/{len(member_codes)} rows={constituent_n}",
                            flush=True,
                        )
                con.execute(
                    """
                    UPDATE dim_sector_hithink d
                    SET constituent_count = s.n,
                        constituents_captured_at = s.captured,
                        updated_at = now()
                    FROM (
                        SELECT sector_ts_code, captured_at AS captured, COUNT(*) AS n
                        FROM fact_sector_constituent_hithink
                        WHERE captured_at = ?
                        GROUP BY 1, 2
                    ) s
                    WHERE d.sector_ts_code = s.sector_ts_code
                    """,
                    [end_day],
                )

        stats = kline_stats(con)
        result: dict[str, Any] = {
            "mode": mode,
            "window_days": days,
            "end_date": end_day.isoformat(),
            "sidecar": sidecar,
            "dim_rows": dim_n,
            "kline": stats,
            "bars_written": written,
            "empty_codes": empty,
            "constituent_rows": constituent_n,
            "fingerprint": table_fingerprint(con),
            "old_ti": coverage_old_ti(con, end_day),
        }
        bc = con.execute(
            """
            SELECT MIN(trade_date), MAX(trade_date), COUNT(*)
            FROM fact_sector_kline_daily WHERE sector_ts_code = ?
            """,
            [BC_BATTERY_CODE],
        ).fetchone()
        result["bc_battery"] = {
            "min": str(bc[0]) if bc[0] else None,
            "max": str(bc[1]) if bc[1] else None,
            "rows": int(bc[2] or 0),
            "starts_on_publish": (
                bc[0] == BC_BATTERY_START if bc[0] is not None else False
            ),
        }
        if compare:
            result["pct_compare"] = compare_pct_chg(con)
            mapping = map_fp_names(con)
            result["fp_map"] = {
                "matched": len(mapping["matched"]),
                "gaps": len(mapping["gaps"]),
                "ti_name_diff": len(mapping["ti_name_diff"]),
                "fp_total": mapping.get("fp_total"),
            }
            if mapping_path:
                Path(mapping_path).write_text(
                    render_fp_mapping(mapping), encoding="utf-8"
                )
                result["mapping_path"] = Path(mapping_path).name
        return result
    finally:
        con.close()
