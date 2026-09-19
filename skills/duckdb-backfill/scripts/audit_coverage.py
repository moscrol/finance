"""覆盖率审计: 每张核心事实表对着 fact_market_daily 的交易日历, 数缺了哪几天。

2026-09-03 加**值覆盖**: 只数 COUNT(*) 抓不到「行在、值空」——fact_sector_stock_daily
legacy 分区 2025-01 ~ 2026-03 约 810 万行 price 全 NULL (已停用的 fast_daily_sync 拷成分改
日期留下的归属行), 行数与日期覆盖率全绿, 复盘却拿不到任何涨幅。对声明了值列的表,
另报 value_rows / value_dates / shell_days (有行但该日值列全空的交易日数)。
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[3]
_ENV_DB = os.environ.get("MARKET_FEATURE_STORE_DB")
DB = Path(_ENV_DB).expanduser() if _ENV_DB else ROOT / "db" / "market_feature_store.duckdb"


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

# 「这张表有数据」到底指哪一列非空。没列出的表只审行覆盖。
VALUE_COLUMN = {
    "fact_sector_daily": "pct_chg",
    "fact_sector_stock_daily": "price",
    "fact_stock_daily": "close",
    "fact_sw_l1_daily": "pct_chg",
}


def _value_coverage(con: duckdb.DuckDBPyConnection, table: str, column: str) -> str:
    value_rows, value_dates = con.execute(
        f"SELECT COUNT({column}), COUNT(DISTINCT trade_date) FILTER (WHERE {column} IS NOT NULL) FROM {table}"
    ).fetchone()
    shell_days, first_shell, last_shell = con.execute(
        f"""
        SELECT COUNT(*), MIN(trade_date), MAX(trade_date)
        FROM (
            SELECT trade_date
            FROM {table}
            GROUP BY trade_date
            HAVING COUNT(*) > 0 AND COUNT({column}) = 0
        )
        """
    ).fetchone()
    text = f" value_rows={value_rows} value_dates={value_dates} shell_days={shell_days}"
    if shell_days:
        text += f" shell_range={first_shell}~{last_shell} ⚠有行无值(归属行, 不是行情)"
    return text


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
            line = f"{table}: rows={rows} dates={table_days} range={tmin}~{tmax} missing={missing} first_missing=[{dates}]"
            column = VALUE_COLUMN.get(table)
            if column:
                line += _value_coverage(con, table, column)
            print(line)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
