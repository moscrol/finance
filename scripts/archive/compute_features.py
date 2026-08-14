#!/usr/bin/env python3
"""Archived one-off feature backfill.

No active workflow consumes these materialized tables. The script retains its
historical Mac paths and frozen 2026-06-17 cutoff for reproducibility only.
"""
import duckdb
import time
from pathlib import Path

DB_DIR = Path.home() / "Desktop" / "c c" / "金融" / "db"
FEATURE_DB = DB_DIR / "market_feature_store.duckdb"
DAILY_ADJ_DB = DB_DIR / "daily_adj_19901219_20260618.duckdb"

PERIODS = [5, 10, 20, 60]


def compute_up_line(con):
    """feature_stock_technical_daily: MA26 + 0.764*STD26 = UP; deviation = (close/UP-1)*100"""
    print("\n=== feature_stock_technical_daily (UP线) ===")
    t0 = time.time()
    con.execute(f"ATTACH '{DAILY_ADJ_DB}' AS adj (READ_ONLY)")
    con.execute("DELETE FROM feature_stock_technical_daily")
    con.execute("""
        INSERT INTO feature_stock_technical_daily
            (trade_date, stock_ts_code, stock_name, close, ma26, std26, up_value, deviation_pct, calculated_at)
        WITH prices AS (
            SELECT
                a.ts_code AS stock_ts_code,
                a.name AS stock_name,
                STRPTIME(a.trade_date, '%Y%m%d')::DATE AS trade_date,
                a.close
            FROM adj.daily_adj a
            WHERE a.ts_code IN (SELECT DISTINCT stock_ts_code FROM fact_stock_daily)
              AND STRPTIME(a.trade_date, '%Y%m%d')::DATE >= '2024-12-01'
        ),
        tech AS (
            SELECT
                stock_ts_code, stock_name, trade_date, close,
                AVG(close) OVER w AS ma26,
                STDDEV_POP(close) OVER w AS std26,
                COUNT(*) OVER w AS wc
            FROM prices
            WINDOW w AS (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 25 PRECEDING AND CURRENT ROW)
        )
        SELECT
            trade_date, stock_ts_code, stock_name, close,
            ROUND(ma26, 4), ROUND(std26, 4),
            ROUND(ma26 + 0.764 * std26, 4) AS up_value,
            ROUND((close / NULLIF(ma26 + 0.764 * std26, 0) - 1) * 100, 2) AS deviation_pct,
            CURRENT_TIMESTAMP
        FROM tech
        WHERE wc = 26 AND trade_date >= '2025-01-02' AND trade_date <= '2026-06-17'
    """)
    con.execute("DETACH adj")
    n = con.execute("SELECT COUNT(*) FROM feature_stock_technical_daily").fetchone()[0]
    d = con.execute("SELECT COUNT(DISTINCT trade_date) FROM feature_stock_technical_daily").fetchone()[0]
    s = con.execute("SELECT COUNT(DISTINCT stock_ts_code) FROM feature_stock_technical_daily").fetchone()[0]
    print(f"  {n:,} rows | {d} dates | {s} stocks | {time.time()-t0:.1f}s")


def compute_stock_window(con):
    """feature_stock_window: interval gain, avg amount, weighted gain. All via window functions."""
    print("\n=== feature_stock_window (个股多周期) ===")
    t0 = time.time()
    con.execute("DELETE FROM feature_stock_window")

    for period in PERIODS:
        print(f"  {period}d ...", end=" ", flush=True)
        pt = time.time()
        # Use pure window functions - no correlated subqueries
        con.execute(f"""
            INSERT INTO feature_stock_window
                (as_of_date, start_date, end_date, stock_ts_code, stock_name,
                 interval_gain_pct, avg_amount, weighted_gain,
                 sector_count, sector_names, sw_l1_names, calculated_at)
            WITH base AS (
                SELECT
                    trade_date,
                    stock_ts_code,
                    stock_name,
                    close,
                    amount,
                    LAG(close, {period}) OVER w AS close_start,
                    LAG(trade_date, {period}) OVER w AS start_date,
                    AVG(amount) OVER (PARTITION BY stock_ts_code ORDER BY trade_date
                        ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS avg_amt,
                    COUNT(*) OVER (PARTITION BY stock_ts_code ORDER BY trade_date
                        ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS wc
                FROM fact_stock_daily
                WINDOW w AS (PARTITION BY stock_ts_code ORDER BY trade_date)
            ),
            gains AS (
                SELECT
                    trade_date AS as_of_date,
                    start_date,
                    trade_date AS end_date,
                    stock_ts_code,
                    stock_name,
                    ROUND((close / NULLIF(close_start, 0) - 1) * 100, 2) AS interval_gain_pct,
                    ROUND(avg_amt, 4) AS avg_amount
                FROM base
                WHERE close_start IS NOT NULL AND close_start > 0 AND wc >= {period}
            )
            SELECT
                g.as_of_date, g.start_date, g.end_date,
                g.stock_ts_code, g.stock_name,
                g.interval_gain_pct,
                g.avg_amount,
                ROUND(g.avg_amount * g.interval_gain_pct / 100, 4) AS weighted_gain,
                -- sector info: join once per stock per date
                COALESCE(sec.cnt, 0),
                sec.names,
                sec.sw1,
                CURRENT_TIMESTAMP
            FROM gains g
            LEFT JOIN (
                SELECT trade_date, stock_ts_code,
                    COUNT(DISTINCT sector_name) AS cnt,
                    STRING_AGG(DISTINCT sector_name, ',' ORDER BY sector_name) AS names,
                    STRING_AGG(DISTINCT sw_l1, ',' ORDER BY sw_l1) AS sw1
                FROM fact_sector_stock_daily
                GROUP BY trade_date, stock_ts_code
            ) sec ON sec.stock_ts_code = g.stock_ts_code AND sec.trade_date = g.as_of_date
        """)
        cnt = con.execute(f"SELECT COUNT(*) FROM feature_stock_window WHERE end_date - start_date BETWEEN {period-3} AND {period+3}").fetchone()[0]
        print(f"{cnt:,} rows | {time.time()-pt:.1f}s")

    total = con.execute("SELECT COUNT(*) FROM feature_stock_window").fetchone()[0]
    print(f"  Total: {total:,} | {time.time()-t0:.1f}s")


def compute_sector_window(con):
    """feature_sector_window: sector interval gain, amount change, diff trend."""
    print("\n=== feature_sector_window (板块多周期) ===")
    t0 = time.time()
    con.execute("DELETE FROM feature_sector_window")

    for period in PERIODS:
        print(f"  {period}d ...", end=" ", flush=True)
        pt = time.time()
        con.execute(f"""
            INSERT INTO feature_sector_window
                (as_of_date, start_date, end_date, sector_ts_code, sector_name, sw_l1,
                 interval_pct_chg, amount_avg, amount_change_pct,
                 diff_start, diff_end, diff_max, diff_min, diff_change, diff_trend, calculated_at)
            WITH base AS (
                SELECT
                    trade_date, sector_ts_code, sector_name, sw_l1,
                    pct_chg, amount, diff_ratio,
                    LAG(trade_date, {period}) OVER w AS start_date,
                    LAG(amount, {period}) OVER w AS amount_start,
                    LAG(diff_ratio, {period}) OVER w AS diff_start_val,
                    SUM(pct_chg) OVER (PARTITION BY sector_ts_code ORDER BY trade_date
                        ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS sum_pct,
                    AVG(amount) OVER (PARTITION BY sector_ts_code ORDER BY trade_date
                        ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS avg_amt,
                    MAX(diff_ratio) OVER (PARTITION BY sector_ts_code ORDER BY trade_date
                        ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS diff_mx,
                    MIN(diff_ratio) OVER (PARTITION BY sector_ts_code ORDER BY trade_date
                        ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS diff_mn,
                    COUNT(*) OVER (PARTITION BY sector_ts_code ORDER BY trade_date
                        ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS wc
                FROM fact_sector_daily
                WINDOW w AS (PARTITION BY sector_ts_code ORDER BY trade_date)
            )
            SELECT
                trade_date AS as_of_date,
                start_date,
                trade_date AS end_date,
                sector_ts_code, sector_name, sw_l1,
                ROUND(sum_pct, 2) AS interval_pct_chg,
                ROUND(avg_amt, 2) AS amount_avg,
                ROUND((amount / NULLIF(amount_start, 0) - 1) * 100, 2) AS amount_change_pct,
                diff_start_val AS diff_start,
                diff_ratio AS diff_end,
                diff_mx AS diff_max,
                diff_mn AS diff_min,
                ROUND(diff_ratio - COALESCE(diff_start_val, 0), 2) AS diff_change,
                CASE
                    WHEN diff_ratio - COALESCE(diff_start_val, 0) > 1 THEN 'up'
                    WHEN diff_ratio - COALESCE(diff_start_val, 0) < -1 THEN 'down'
                    ELSE 'flat'
                END AS diff_trend,
                CURRENT_TIMESTAMP
            FROM base
            WHERE start_date IS NOT NULL AND wc >= {period}
        """)
        cnt = con.execute(f"SELECT COUNT(*) FROM feature_sector_window WHERE end_date - start_date BETWEEN {period-3} AND {period+3}").fetchone()[0]
        print(f"{cnt:,} rows | {time.time()-pt:.1f}s")

    total = con.execute("SELECT COUNT(*) FROM feature_sector_window").fetchone()[0]
    print(f"  Total: {total:,} | {time.time()-t0:.1f}s")


def main():
    print(f"DB: {FEATURE_DB}")
    con = duckdb.connect(str(FEATURE_DB), read_only=False)
    compute_up_line(con)
    compute_stock_window(con)
    compute_sector_window(con)
    print("\n=== Summary ===")
    for t in ["feature_stock_technical_daily", "feature_stock_window", "feature_sector_window"]:
        n = con.execute(f"SELECT COUNT(*) FROM \"{t}\"").fetchone()[0]
        print(f"  {t}: {n:,}")
    con.close()
    print("Done!")


if __name__ == "__main__":
    main()
