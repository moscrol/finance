from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_feature_store.db import connect

TABLES = [
    "fact_market_daily",
    "fact_sector_daily",
    "fact_sw_l1_daily",
    "fact_sector_stock_daily",
    "fact_stock_high_daily",
    "fact_theme_limit_heat_daily",
    "fact_theme_limit_stock_daily",
    "fact_limit_advance_daily",
    "fact_stock_daily",
    "fact_mainline_theme_daily",
    "fact_mainline_stock_daily",
    "fact_mainline_sector_daily",
    "fact_sector_period_rank_daily",
    "feature_market_window",
    "feature_sector_window",
    "feature_stock_window",
    "feature_stock_technical_daily",
]
DATE_COLUMNS = {
    "feature_market_window": "as_of_date",
    "feature_sector_window": "as_of_date",
    "feature_stock_window": "as_of_date",
    "feature_stock_technical_daily": "trade_date",
}
L2_TABLES = [
    "feature_l2_capital_flow_daily",
    "feature_l2_quant_orders_daily",
]
L2_STEPS = ("limitup", "top100", "quant")
MARKET_FIELDS = [
    "sh_index_close",
    "sh_index_pct_chg",
    "sh_week_ma",
    "sh_deviation_pct",
    "total_amount",
    "amount_vs_yesterday_pct",
    "amount_ma20",
    "volume_ratio",
    "advancers",
    "limit_up",
    "limit_down",
    "top3_industry_ratio",
    "strength_avg_pct",
    "strength_amount_pct",
    "strength_status",
]
PLACEHOLDERS = [
    "| 周均线 | - |",
    "| 偏离度 | - |",
    "| 涨停方向 | 核心涨停题材： |",
    "暂无",
    "未返回",
]


def is_null(value: object) -> bool:
    return value is None or str(value) in {"nan", "NaT", "None"}


def check_data(date: str) -> list[str]:
    missing: list[str] = []
    con = connect(read_only=True)
    try:
        print(f"CHECK DATA {date}")
        for table in TABLES:
            date_column = DATE_COLUMNS.get(table, "trade_date")
            max_date, count = con.execute(
                f"SELECT MAX({date_column}), COUNT(*) FILTER (WHERE {date_column} = ?) FROM {table}",
                [date],
            ).fetchone()
            print(f"{table}: rows={count} max={max_date}")
            if not count:
                missing.append(f"{table} 无 {date} 数据，最新 {max_date}")

        cursor = con.execute("select * from fact_market_daily where trade_date=?", [date])
        values = cursor.fetchone()
        if values is None:
            missing.append("fact_market_daily 缺失整行")
        else:
            row = {column[0]: value for column, value in zip(cursor.description, values)}
            for field in MARKET_FIELDS:
                if field not in row:
                    missing.append(f"fact_market_daily.{field} 字段不存在")
                    continue
                value = row[field]
                if is_null(value):
                    missing.append(f"fact_market_daily.{field} 为空")

        empty_detail = con.execute(
            """
            SELECT h.sector_ts_code, h.sector_name, h.limit_up_count, COUNT(s.stock_ts_code) AS stock_rows
            FROM fact_theme_limit_heat_daily h
            LEFT JOIN fact_theme_limit_stock_daily s
              ON h.trade_date = s.trade_date AND h.sector_ts_code = s.sector_ts_code
            WHERE h.trade_date = ? AND COALESCE(h.limit_up_count, 0) > 0
            GROUP BY 1, 2, 3
            HAVING COUNT(s.stock_ts_code) = 0
            ORDER BY h.limit_up_count DESC
            """,
            [date],
        ).fetchall()
        for code, name, limit_up_count, _stock_rows in empty_detail:
            missing.append(f"涨停题材 {code}/{name} 有 {limit_up_count} 个涨停但明细为空")
        mainline_gaps = con.execute(
            """
            SELECT t.theme_code, t.theme_name,
                   COUNT(DISTINCT s.stock_ts_code) AS stock_rows,
                   COUNT(DISTINCT m.sector_ts_code) AS sector_rows
            FROM fact_mainline_theme_daily t
            LEFT JOIN fact_mainline_stock_daily s
              ON t.trade_date = s.trade_date AND t.theme_code = s.theme_code
            LEFT JOIN fact_mainline_sector_daily m
              ON t.trade_date = m.trade_date AND t.theme_code = m.theme_code
            WHERE t.trade_date = ?
            GROUP BY 1, 2
            HAVING COUNT(DISTINCT s.stock_ts_code) = 0
                OR COUNT(DISTINCT m.sector_ts_code) = 0
            ORDER BY 1
            """,
            [date],
        ).fetchall()
        for code, name, stock_rows, sector_rows in mainline_gaps:
            missing.append(
                f"主线题材 {code}/{name} 覆盖不完整：个股 {stock_rows} 行，核心板块 {sector_rows} 行"
            )
        return missing
    finally:
        con.close()


def check_report(date: str) -> list[str]:
    missing: list[str] = []
    report = Path(f"market_feature_store/exports/{date}-daily-review.md")
    if not report.exists():
        missing.append(f"{report} 不存在")
    else:
        text = report.read_text(encoding="utf-8")
        for token in PLACEHOLDERS:
            count = text.count(token)
            if count:
                missing.append(f"日报存在占位/缺失：{token} x{count}")
    return missing


def check_l2(date: str) -> list[str]:
    missing: list[str] = []
    con = connect(read_only=True)
    try:
        print(f"CHECK L2 {date}")
        for step in L2_STEPS:
            row = con.execute(
                """
                SELECT status, row_count, finished_at
                FROM ops_pipeline_run_daily
                WHERE trade_date = ? AND pipeline = 'l2-moneyflow' AND step = ?
                """,
                [date, step],
            ).fetchone()
            print(f"l2-moneyflow/{step}: {row or 'missing'}")
            if row is None:
                missing.append(f"L2 步骤 {step} 无 {date} 完成记录")
            elif row[0] != "complete":
                missing.append(f"L2 步骤 {step} 状态为 {row[0]}，未完成")
        for table in L2_TABLES:
            max_date, count = con.execute(
                f"SELECT MAX(trade_date), COUNT(*) FILTER (WHERE trade_date = ?) FROM {table}",
                [date],
            ).fetchone()
            print(f"{table}: rows={count} max={max_date}")
        return missing
    finally:
        con.close()


def main(argv: list[str] | str | None = None, data_only: bool = False) -> int:
    direct_date = isinstance(argv, str)
    if direct_date:
        argv = [argv]
    if data_only:
        argv = [*(argv or []), "--phase", "data"]
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("--phase", choices=("data", "report", "l2", "all"), default="all")
    args = parser.parse_args(argv)

    missing: list[str] = []
    if args.phase in {"data", "all"}:
        missing.extend(check_data(args.date))
    if args.phase in {"report", "all"}:
        missing.extend(check_report(args.date))
    if args.phase in {"l2", "all"}:
        missing.extend(check_l2(args.date))

    print("RESULT:", "INCOMPLETE" if missing else "COMPLETE")
    for item in missing:
        print("-", item)
    if not missing:
        return 0
    return 1 if direct_date else 2


if __name__ == "__main__":
    raise SystemExit(main())
