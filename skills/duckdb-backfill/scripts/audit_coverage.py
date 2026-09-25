from __future__ import annotations

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "db" / "market_feature_store.duckdb"


TABLES = [
    "fact_sector_daily",
    "fact_sector_stock_daily",
    "fact_stock_daily",
    "fact_stock_high_daily",
    "fact_theme_limit_heat_daily",
    "fact_theme_limit_stock_daily",
    "fact_limit_advance_presence",
    "fact_limit_advance_daily",
    "fact_sw_l1_daily",
]


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        start, end, days = con.execute(
            """
            SELECT MIN(trade_date), MAX(trade_date), COUNT(*)
            FROM fact_market_daily
            WHERE total_amount IS NOT NULL
            """
        ).fetchone()
        print(f"calendar_with_amount: {start} ~ {end}, days={days}")
        for table in TABLES:
            rows, table_days, tmin, tmax = con.execute(
                f"SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM {table}"
            ).fetchone()
            missing = con.execute(
                f"""
                WITH cal AS (
                    SELECT trade_date
                    FROM fact_market_daily
                    WHERE total_amount IS NOT NULL
                )
                SELECT COUNT(*)
                FROM cal
                WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM {table})
                """
            ).fetchone()[0]
            first_missing = con.execute(
                f"""
                WITH cal AS (
                    SELECT trade_date
                    FROM fact_market_daily
                    WHERE total_amount IS NOT NULL
                )
                SELECT trade_date
                FROM cal
                WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM {table})
                ORDER BY trade_date
                LIMIT 5
                """
            ).fetchall()
            dates = ",".join(str(row[0]) for row in first_missing)
            print(f"{table}: rows={rows} dates={table_days} range={tmin}~{tmax} missing={missing} first_missing=[{dates}]")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
