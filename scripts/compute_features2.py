#!/usr/bin/env python3
"""Compute feature_market_window + feature_limit_advance_window."""
import duckdb
import time
from pathlib import Path

DB_DIR = Path.home() / "Desktop" / "c c" / "金融" / "db"
FEATURE_DB = DB_DIR / "market_feature_store.duckdb"
PERIODS = [5, 10, 20, 60]


def compute_market_window(con):
    """feature_market_window: market breadth, amount, limit stats over windows."""
    print("\n=== feature_market_window (大盘窗口) ===")
    t0 = time.time()
    con.execute("DELETE FROM feature_market_window")

    for period in PERIODS:
        print(f"  {period}d ...", end=" ", flush=True)
        pt = time.time()
        con.execute(f"""
            INSERT INTO feature_market_window
                (as_of_date, start_date, end_date,
                 advancers_start, advancers_end, advancers_change, advancers_ma5,
                 limit_up_avg, limit_down_avg, amount_avg, breadth_trend, calculated_at)
            WITH base AS (
                SELECT
                    trade_date,
                    advancers,
                    limit_up,
                    limit_down,
                    total_amount,
                    LAG(trade_date, {period}) OVER w AS start_date,
                    LAG(advancers, {period}) OVER w AS adv_start,
                    AVG(advancers) OVER (ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS adv_ma5,
                    AVG(limit_up) OVER (ORDER BY trade_date ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) AS lu_avg,
                    AVG(limit_down) OVER (ORDER BY trade_date ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) AS ld_avg,
                    AVG(total_amount) OVER (ORDER BY trade_date ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) AS amt_avg,
                    COUNT(*) OVER (ORDER BY trade_date ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) AS wc
                FROM fact_market_daily
                WINDOW w AS (ORDER BY trade_date)
            )
            SELECT
                trade_date AS as_of_date,
                start_date,
                trade_date AS end_date,
                adv_start AS advancers_start,
                advancers AS advancers_end,
                advancers - COALESCE(adv_start, 0) AS advancers_change,
                ROUND(adv_ma5, 1) AS advancers_ma5,
                ROUND(lu_avg, 1) AS limit_up_avg,
                ROUND(ld_avg, 1) AS limit_down_avg,
                ROUND(amt_avg, 2) AS amount_avg,
                CASE
                    WHEN advancers - COALESCE(adv_start, 0) > 200 THEN 'up'
                    WHEN advancers - COALESCE(adv_start, 0) < -200 THEN 'down'
                    ELSE 'flat'
                END AS breadth_trend,
                CURRENT_TIMESTAMP
            FROM base
            WHERE start_date IS NOT NULL AND wc >= {period}
        """)
        cnt = con.execute(f"SELECT COUNT(*) FROM feature_market_window WHERE end_date - start_date >= {period}").fetchone()[0]
        print(f"{cnt} rows | {time.time()-pt:.1f}s")

    total = con.execute("SELECT COUNT(*) FROM feature_market_window").fetchone()[0]
    print(f"  Total: {total:,} | {time.time()-t0:.1f}s")


def compute_limit_advance_window(con):
    """feature_limit_advance_window: per-stock limit-advance frequency in recent windows."""
    print("\n=== feature_limit_advance_window (连板窗口) ===")
    t0 = time.time()
    con.execute("DELETE FROM feature_limit_advance_window")

    for period in PERIODS:
        print(f"  {period}d ...", end=" ", flush=True)
        pt = time.time()
        con.execute(f"""
            INSERT INTO feature_limit_advance_window
                (as_of_date, start_date, end_date, stock_ts_code, stock_name,
                 advance_days, max_boards, first_seen_date, last_seen_date, themes, calculated_at)
            WITH date_range AS (
                SELECT DISTINCT trade_date FROM fact_limit_advance_daily
            ),
            windows AS (
                SELECT
                    d.trade_date AS as_of_date,
                    (SELECT d2.trade_date FROM date_range d2 
                     WHERE d2.trade_date <= d.trade_date 
                     ORDER BY d2.trade_date DESC 
                     LIMIT 1 OFFSET {period}) AS start_date
                FROM date_range d
            )
            SELECT
                w.as_of_date,
                w.start_date,
                w.as_of_date AS end_date,
                f.stock_ts_code,
                f.stock_name,
                COUNT(DISTINCT f.trade_date) AS advance_days,
                MAX(f.boards) AS max_boards,
                MIN(f.trade_date) AS first_seen_date,
                MAX(f.trade_date) AS last_seen_date,
                STRING_AGG(DISTINCT f.theme, ',' ORDER BY f.theme) AS themes,
                CURRENT_TIMESTAMP
            FROM windows w
            JOIN fact_limit_advance_daily f
                ON f.trade_date BETWEEN w.start_date AND w.as_of_date
            WHERE w.start_date IS NOT NULL
            GROUP BY w.as_of_date, w.start_date, f.stock_ts_code, f.stock_name
        """)
        cnt = con.execute(f"SELECT COUNT(*) FROM feature_limit_advance_window WHERE end_date - start_date >= {period}").fetchone()[0]
        print(f"{cnt:,} rows | {time.time()-pt:.1f}s")

    total = con.execute("SELECT COUNT(*) FROM feature_limit_advance_window").fetchone()[0]
    print(f"  Total: {total:,} | {time.time()-t0:.1f}s")


def main():
    print(f"DB: {FEATURE_DB}")
    con = duckdb.connect(str(FEATURE_DB), read_only=False)
    compute_market_window(con)
    compute_limit_advance_window(con)
    print("\n=== Summary ===")
    for t in ["feature_market_window", "feature_limit_advance_window"]:
        n = con.execute(f"SELECT COUNT(*) FROM \"{t}\"").fetchone()[0]
        print(f"  {t}: {n:,}")
    con.close()
    print("Done!")


if __name__ == "__main__":
    main()
