from __future__ import annotations

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
]
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


def main() -> int:
    date = sys.argv[1]
    con = connect(read_only=True)
    missing: list[str] = []

    print(f"CHECK {date}")
    for table in TABLES:
        max_date, count = con.execute(
            f"select max(trade_date), count(*) filter(where trade_date=?) from {table}", [date]
        ).fetchone()
        print(f"{table}: rows={count} max={max_date}")
        if not count:
            missing.append(f"{table} 无 {date} 数据，最新 {max_date}")

    row = con.execute("select * from fact_market_daily where trade_date=?", [date]).fetchdf()
    if row.empty:
        missing.append("fact_market_daily 缺失整行")
    else:
        cols = set(row.columns)
        for field in MARKET_FIELDS:
            if field not in cols:
                missing.append(f"fact_market_daily.{field} 字段不存在")
                continue
            value = row.iloc[0][field]
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

    report = Path(f"market_feature_store/exports/{date}-daily-review.md")
    if not report.exists():
        missing.append(f"{report} 不存在")
    else:
        text = report.read_text(encoding="utf-8")
        for token in PLACEHOLDERS:
            count = text.count(token)
            if count:
                missing.append(f"日报存在占位/缺失：{token} x{count}")

    print("RESULT:", "INCOMPLETE" if missing else "COMPLETE")
    for item in missing:
        print("-", item)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
