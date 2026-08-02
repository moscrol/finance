#!/usr/bin/env python3
"""
⛔ DEPRECATED（2026-08-02）——对当前生产库不可用，不要跑。

两个独立原因，任一都足以停用：

1. **跑必崩**：本脚本 INSERT INTO fact_sector_daily / fact_sector_stock_daily，
   而生产库里这两个已重构为 VIEW（底层 fact_*_generation 表 + snapshot_id）。
   DuckDB 会抛 `Catalog Error: ... is not an table`。

2. **就算能跑也危险**：sector-stocks 步骤本质是「拷昨日的行、改个日期」，
   只保留 sector→stock 归属关系，price/pct_chg/amount 全为 NULL。行数对得上、
   COUNT(*) 覆盖率审计照过，但值是空壳——2026-06-22 就是这样让 daily-review
   §7 个股发动机 / §12 加权涨幅全部显示「暂无」。这类问题只有跨日期 diff 能
   抓到。见 skills/daily-full-review/SKILL.md。

替代方案：夜跑已拆分为 sync@18:30 + finalize@20:40（见
skills/daily-full-review/scripts/nightly_full_review.sh），原本的提速价值已由
该拆分承接。单步补数走 `python3 -m market_feature_store.cli` 对应子命令。

保留本文件仅供历史参考；最后一次有记录的实际使用是 2026-06-22。

---

Fast daily sync replacements for the 3 slowest steps in run_review_sync.py.
Saves ~55 minutes per daily run by eliminating online crawls.

Usage:
    python3 scripts/fast_daily_sync.py --date 2026-06-18 --all
    python3 scripts/fast_daily_sync.py --date 2026-06-18 --step sector-stocks
    python3 scripts/fast_daily_sync.py --date 2026-06-18 --step stock-daily
    python3 scripts/fast_daily_sync.py --date 2026-06-18 --step stock-high

Replaces:
    1. sector-stocks: 224 sectors × CDP page load (30-40 min) → copy yesterday (2s)
    2. stock-daily: mootdx full A-share (10-20 min, hangs) → import from daily_adj (5s)
    3. stock-high: fupanhui CDP crawl (5-10 min) → local new-high detection from daily_adj (10s)

Weekly full refresh: run with --full-refresh to force the slow fupanhui crawl for sector-stocks.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from market_feature_store.db import connect, DB_PATH

DAILY_ADJ_DB = DB_PATH.parent / "daily_adj_19901219_20260618.duckdb"

# New-high detection periods: (period_key, label, trading_days)
HIGH_PERIODS = [
    ("20d", "20日新高", 20),
    ("60d", "60日新高", 60),
    ("120d", "120日新高", 120),
    ("1y", "1年新高", 250),
    ("2y", "2年新高", 500),
    ("3y", "3年新高", 750),
    ("history", "历史新高", 9999),
]


def fast_sector_stocks(con, trade_date: str, prev_date: str | None = None):
    """Copy yesterday's sector-stock membership to today. ~2 seconds vs 30-40 min CDP."""
    print(f"\n[sector-stocks] Incremental copy for {trade_date}")
    t0 = time.time()

    # Check if today already has data
    existing = con.execute(
        "SELECT COUNT(*) FROM fact_sector_stock_daily WHERE trade_date = ?", [trade_date]
    ).fetchone()[0]
    if existing > 0:
        print(f"  Already has {existing:,} rows, skipping")
        return existing

    # Find the most recent date with data (as source)
    if prev_date is None:
        row = con.execute(
            "SELECT MAX(trade_date) FROM fact_sector_stock_daily WHERE trade_date < ?", [trade_date]
        ).fetchone()
        if not row or not row[0]:
            print("  ERROR: No previous date found to copy from!")
            return 0
        prev_date = str(row[0])

    prev_count = con.execute(
        "SELECT COUNT(*) FROM fact_sector_stock_daily WHERE trade_date = ?", [prev_date]
    ).fetchone()[0]
    print(f"  Copying {prev_count:,} rows from {prev_date} → {trade_date}")

    con.execute("""
        INSERT INTO fact_sector_stock_daily
            (trade_date, sector_ts_code, sector_name, sw_l1, stock_ts_code, stock_name,
             price, pct_chg, amount, pct_chg_5d, pct_chg_10d, pct_chg_20d,
             fund_flow_1d, fund_flow_5d, sw_industry, leader_plate, leader_sub_plate,
             source, updated_at)
        SELECT
            ?::DATE, sector_ts_code, sector_name, sw_l1, stock_ts_code, stock_name,
            NULL, NULL, NULL, NULL, NULL, NULL,
            NULL, NULL, sw_industry, leader_plate, leader_sub_plate,
            'incremental-copy', CURRENT_TIMESTAMP
        FROM fact_sector_stock_daily
        WHERE trade_date = ?
    """, [trade_date, prev_date])

    inserted = con.execute(
        "SELECT COUNT(*) FROM fact_sector_stock_daily WHERE trade_date = ?", [trade_date]
    ).fetchone()[0]
    print(f"  Done: {inserted:,} rows in {time.time()-t0:.1f}s (source={prev_date})")
    return inserted


def fast_stock_daily(con, trade_date: str):
    """Import stock daily data from local daily_adj DB. ~5 seconds vs 10-20 min mootdx."""
    print(f"\n[stock-daily] Import from daily_adj for {trade_date}")
    t0 = time.time()

    # Check if already has data
    existing = con.execute(
        "SELECT COUNT(*) FROM fact_stock_daily WHERE trade_date = ?", [trade_date]
    ).fetchone()[0]
    if existing > 0:
        print(f"  Already has {existing:,} rows, skipping")
        return existing

    if not DAILY_ADJ_DB.exists():
        print(f"  ERROR: daily_adj DB not found at {DAILY_ADJ_DB}")
        return 0

    # Convert date format: 2026-06-18 → 20260618
    date_str = trade_date.replace("-", "")

    con.execute(f"ATTACH '{DAILY_ADJ_DB}' AS adj (READ_ONLY)")

    # Check if the date exists in daily_adj
    count_in_adj = con.execute(
        "SELECT COUNT(*) FROM adj.daily_adj WHERE trade_date = ?", [date_str]
    ).fetchone()[0]
    if count_in_adj == 0:
        print(f"  WARNING: No data for {date_str} in daily_adj (not yet updated?)")
        con.execute("DETACH adj")
        return 0

    con.execute("""
        INSERT INTO fact_stock_daily
            (trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg,
             amount, turnover, source, updated_at)
        SELECT
            STRPTIME(a.trade_date, '%Y%m%d')::DATE,
            a.ts_code,
            a.name,
            a.close,
            a.pre_close,
            a.pct_chg,
            ROUND(a.amount / 100000, 4),  -- 千元 → 亿
            NULL,  -- turnover not in daily_adj
            'daily_adj_local',
            CURRENT_TIMESTAMP
        FROM adj.daily_adj a
        WHERE a.trade_date = ?
          AND a.close IS NOT NULL
          AND a.close > 0
    """, [date_str])

    con.execute("DETACH adj")

    inserted = con.execute(
        "SELECT COUNT(*) FROM fact_stock_daily WHERE trade_date = ?", [trade_date]
    ).fetchone()[0]
    print(f"  Done: {inserted:,} stocks in {time.time()-t0:.1f}s")

    # Also compute sh_week_ma and deviation for fact_market_daily if needed
    _update_market_index(con, trade_date, date_str)

    return inserted


def _update_market_index(con, trade_date: str, date_str: str):
    """Update sh_index fields in fact_market_daily from daily_adj (000001.SS / 399001.SZ)."""
    try:
        con.execute(f"ATTACH '{DAILY_ADJ_DB}' AS adj (READ_ONLY)")
        # Shanghai composite index = 000001.SS in some DBs, or may not be present
        # Try to update market_daily with advancers count from fact_stock_daily
        advancers = con.execute("""
            SELECT COUNT(*) FROM fact_stock_daily
            WHERE trade_date = ? AND pct_chg > 0
        """, [trade_date]).fetchone()[0]

        # Update fact_market_daily advancers if row exists but advancers is null
        con.execute("""
            UPDATE fact_market_daily
            SET advancers = ?
            WHERE trade_date = ? AND advancers IS NULL
        """, [advancers, trade_date])
        con.execute("DETACH adj")
    except Exception:
        try:
            con.execute("DETACH adj")
        except Exception:
            pass


def fast_stock_high(con, trade_date: str):
    """Detect new-high stocks from local daily_adj history. ~10s vs 5-10 min CDP."""
    print(f"\n[stock-high] Local new-high detection for {trade_date}")
    t0 = time.time()

    # Check if already has data
    existing = con.execute(
        "SELECT COUNT(*) FROM fact_stock_high_daily WHERE trade_date = ?", [trade_date]
    ).fetchone()[0]
    if existing > 0:
        print(f"  Already has {existing:,} rows, skipping")
        return existing

    if not DAILY_ADJ_DB.exists():
        print(f"  ERROR: daily_adj DB not found at {DAILY_ADJ_DB}")
        return 0

    date_str = trade_date.replace("-", "")
    con.execute(f"ATTACH '{DAILY_ADJ_DB}' AS adj (READ_ONLY)")

    # Check if date exists
    count_in_adj = con.execute(
        "SELECT COUNT(*) FROM adj.daily_adj WHERE trade_date = ?", [date_str]
    ).fetchone()[0]
    if count_in_adj == 0:
        print(f"  WARNING: No data for {date_str} in daily_adj")
        con.execute("DETACH adj")
        return 0

    # Use f-string for date (controlled YYYYMMDD value, no injection risk)
    # This avoids parameter counting issues with complex SQL
    D = date_str
    con.execute(f"""
        INSERT INTO fact_stock_high_daily
            (trade_date, stock_ts_code, stock_name, primary_high_period, primary_high_label,
             high_periods_json, is_new, price, pct_chg, pct_chg_10d,
             amount, market_cap, fund_today, limit_status, limit_times,
             sw_l1, sw_l2, plate, whitelist_sectors_json, source, updated_at)
        WITH today AS (
            SELECT ts_code, name, close, pct_chg, amount
            FROM adj.daily_adj
            WHERE trade_date = '{D}'
              AND close IS NOT NULL AND close > 0
        ),
        -- Pre-compute max close for each period for each stock (excluding today)
        maxes AS (
            SELECT
                h.ts_code,
                MAX(CASE WHEN STRPTIME(h.trade_date, '%Y%m%d')::DATE >= STRPTIME('{D}', '%Y%m%d')::DATE - 20
                         AND h.trade_date < '{D}' THEN h.close END) AS max_20d,
                MAX(CASE WHEN STRPTIME(h.trade_date, '%Y%m%d')::DATE >= STRPTIME('{D}', '%Y%m%d')::DATE - 60
                         AND h.trade_date < '{D}' THEN h.close END) AS max_60d,
                MAX(CASE WHEN STRPTIME(h.trade_date, '%Y%m%d')::DATE >= STRPTIME('{D}', '%Y%m%d')::DATE - 120
                         AND h.trade_date < '{D}' THEN h.close END) AS max_120d,
                MAX(CASE WHEN STRPTIME(h.trade_date, '%Y%m%d')::DATE >= STRPTIME('{D}', '%Y%m%d')::DATE - 250
                         AND h.trade_date < '{D}' THEN h.close END) AS max_1y,
                MAX(CASE WHEN STRPTIME(h.trade_date, '%Y%m%d')::DATE >= STRPTIME('{D}', '%Y%m%d')::DATE - 500
                         AND h.trade_date < '{D}' THEN h.close END) AS max_2y,
                MAX(CASE WHEN STRPTIME(h.trade_date, '%Y%m%d')::DATE >= STRPTIME('{D}', '%Y%m%d')::DATE - 750
                         AND h.trade_date < '{D}' THEN h.close END) AS max_3y,
                MAX(CASE WHEN h.trade_date < '{D}' THEN h.close END) AS max_all
            FROM adj.daily_adj h
            WHERE STRPTIME(h.trade_date, '%Y%m%d')::DATE >= STRPTIME('{D}', '%Y%m%d')::DATE - INTERVAL '10 YEAR'
              AND h.close IS NOT NULL AND h.close > 0
            GROUP BY h.ts_code
        ),
        highs AS (
            SELECT
                t.ts_code, t.name, t.close, t.pct_chg, t.amount,
                CASE
                    WHEN t.close > COALESCE(m.max_all, 0) THEN 'history'
                    WHEN t.close > COALESCE(m.max_3y, 0) THEN '3y'
                    WHEN t.close > COALESCE(m.max_2y, 0) THEN '2y'
                    WHEN t.close > COALESCE(m.max_1y, 0) THEN '1y'
                    WHEN t.close > COALESCE(m.max_120d, 0) THEN '120d'
                    WHEN t.close > COALESCE(m.max_60d, 0) THEN '60d'
                    WHEN t.close > COALESCE(m.max_20d, 0) THEN '20d'
                END AS primary_period,
                t.close > COALESCE(m.max_20d, 0) AS is_20d,
                t.close > COALESCE(m.max_60d, 0) AS is_60d,
                t.close > COALESCE(m.max_120d, 0) AS is_120d,
                t.close > COALESCE(m.max_1y, 0) AS is_1y,
                t.close > COALESCE(m.max_2y, 0) AS is_2y,
                t.close > COALESCE(m.max_3y, 0) AS is_3y,
                t.close > COALESCE(m.max_all, 0) AS is_all
            FROM today t
            JOIN maxes m ON m.ts_code = t.ts_code
            WHERE t.close > COALESCE(m.max_20d, 0)  -- at least 20d new high
        )
        SELECT
            STRPTIME('{D}', '%Y%m%d')::DATE AS trade_date,
            h.ts_code,
            h.name,
            h.primary_period,
            CASE h.primary_period
                WHEN 'history' THEN '历史新高'
                WHEN '3y' THEN '3年新高'
                WHEN '2y' THEN '2年新高'
                WHEN '1y' THEN '1年新高'
                WHEN '120d' THEN '120日新高'
                WHEN '60d' THEN '60日新高'
                WHEN '20d' THEN '20日新高'
            END AS primary_label,
            -- Build high_periods_json
            '[' ||
                CASE WHEN h.is_all THEN '{{"period": "history", "label": "历史新高"}}, ' ELSE '' END ||
                CASE WHEN h.is_3y THEN '{{"period": "3y", "label": "3年新高"}}, ' ELSE '' END ||
                CASE WHEN h.is_2y THEN '{{"period": "2y", "label": "2年新高"}}, ' ELSE '' END ||
                CASE WHEN h.is_1y THEN '{{"period": "1y", "label": "1年新高"}}, ' ELSE '' END ||
                CASE WHEN h.is_120d THEN '{{"period": "120d", "label": "120日新高"}}, ' ELSE '' END ||
                CASE WHEN h.is_60d THEN '{{"period": "60d", "label": "60日新高"}}, ' ELSE '' END ||
                CASE WHEN h.is_20d THEN '{{"period": "20d", "label": "20日新高"}}' ELSE '' END
            || ']' AS high_periods_json,
            TRUE AS is_new,
            h.close AS price,
            h.pct_chg,
            NULL AS pct_chg_10d,
            ROUND(h.amount / 100000, 4) AS amount,
            NULL AS market_cap,
            NULL AS fund_today,
            NULL AS limit_status,
            NULL AS limit_times,
            NULL AS sw_l1,
            NULL AS sw_l2,
            NULL AS plate,
            NULL AS whitelist_sectors_json,
            'daily_adj_local',
            CURRENT_TIMESTAMP
        FROM highs h
        WHERE h.primary_period IS NOT NULL
    """)

    con.execute("DETACH adj")

    inserted = con.execute(
        "SELECT COUNT(*) FROM fact_stock_high_daily WHERE trade_date = ?", [trade_date]
    ).fetchone()[0]

    # Enrich with sector info from fact_sector_stock_daily
    _enrich_high_sectors(con, trade_date)

    elapsed = time.time() - t0
    print(f"  Done: {inserted:,} new-high stocks in {elapsed:.1f}s")
    return inserted


def _enrich_high_sectors(con, trade_date: str):
    """Add sw_l1/plate/whitelist_sectors_json from sector membership data."""
    con.execute("""
        UPDATE fact_stock_high_daily h
        SET
            sw_l1 = sec.sw_l1,
            plate = sec.top_sector,
            whitelist_sectors_json = sec.sectors_json
        FROM (
            SELECT
                stock_ts_code,
                MIN(sw_l1) AS sw_l1,
                FIRST(sector_name ORDER BY sector_name) AS top_sector,
                '[' || STRING_AGG(
                    '{"code": "' || sector_ts_code || '", "name": "' || sector_name || '", "type": "N"}',
                    ', ' ORDER BY sector_name
                ) || ']' AS sectors_json
            FROM fact_sector_stock_daily
            WHERE trade_date = ?
            GROUP BY stock_ts_code
        ) sec
        WHERE h.stock_ts_code = sec.stock_ts_code
          AND h.trade_date = ?
          AND h.sw_l1 IS NULL
    """, [trade_date, trade_date])


DEPRECATION_NOTICE = """\
⛔ scripts/fast_daily_sync.py 已于 2026-08-02 停用，对当前生产库不可用。

原因 1：本脚本写 fact_sector_daily / fact_sector_stock_daily，而生产库里这两个
        已是 VIEW（底层 fact_*_generation + snapshot_id），INSERT 会直接抛
        Catalog Error。
原因 2：sector-stocks 步骤是「拷昨日的行、改个日期」，price/pct_chg/amount 全
        为 NULL。行数和 COUNT(*) 覆盖率都正常，值却是空壳（2026-06-22 事故）。

替代：夜跑已拆 sync@18:30 + finalize@20:40；单步补数走
      python3 -m market_feature_store.cli <子命令>

确实要跑历史复现，请显式设 FAST_DAILY_SYNC_ALLOW_DEPRECATED=1（后果自负）。
"""


def main():
    if os.environ.get("FAST_DAILY_SYNC_ALLOW_DEPRECATED", "").strip() not in {"1", "true", "yes"}:
        # 不是静默退出：让人看到为什么，而不是几十行后一句莫名其妙的 Catalog Error。
        print(DEPRECATION_NOTICE, file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser(
        description="[DEPRECATED] Fast daily sync: replaces 3 slowest steps (saves ~55 min)")
    ap.add_argument("--date", required=True, help="Trade date YYYY-MM-DD")
    ap.add_argument("--step", choices=["sector-stocks", "stock-daily", "stock-high", "all"],
                    default="all", help="Which step to run (default: all)")
    ap.add_argument("--all", action="store_true", help="Run all 3 steps")
    ap.add_argument("--full-refresh", action="store_true",
                    help="For sector-stocks: skip incremental, hint to use full fupanhui crawl")
    args = ap.parse_args()

    steps = ["sector-stocks", "stock-daily", "stock-high"] if (args.step == "all" or args.all) else [args.step]

    print(f"Fast Daily Sync | date={args.date} | steps={steps}")
    print(f"DB: {DB_PATH}")
    print(f"daily_adj: {DAILY_ADJ_DB} (exists={DAILY_ADJ_DB.exists()})")

    con = connect(read_only=False)
    results = {}
    total_t0 = time.time()

    try:
        if "sector-stocks" in steps:
            if args.full_refresh:
                print("\n[sector-stocks] --full-refresh: use standard sync-sector-stocks instead")
                results["sector-stocks"] = "skipped (full-refresh requested)"
            else:
                results["sector-stocks"] = fast_sector_stocks(con, args.date)

        if "stock-daily" in steps:
            results["stock-daily"] = fast_stock_daily(con, args.date)

        if "stock-high" in steps:
            results["stock-high"] = fast_stock_high(con, args.date)
    finally:
        con.close()

    total = time.time() - total_t0
    print(f"\n=== Complete in {total:.1f}s ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("\n  (Compare: original takes 50-70 min for these 3 steps)")


if __name__ == "__main__":
    raise SystemExit(main() or 0)
