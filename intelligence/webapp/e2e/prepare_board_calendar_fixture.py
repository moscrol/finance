"""Synthetic, isolated calendar data for real browser → API → DuckDB tests.

Never accepts a production path: writes only webapp/test-results/board-calendar.
"""
from pathlib import Path

import duckdb


def main() -> None:
    repo = Path(__file__).resolve().parents[3]
    root = repo / "intelligence/webapp/test-results/board-calendar"
    root.mkdir(parents=True, exist_ok=True)
    db = root / "market.duckdb"
    db.unlink(missing_ok=True)
    with duckdb.connect(str(db)) as con:
        con.execute((repo / "market_feature_store/schema.sql").read_text())
        con.executemany("INSERT INTO fact_market_daily (trade_date) VALUES (?)", [
            (day,) for day in ["2026-08-28", "2026-09-01", "2026-09-22", "2026-09-24"]
        ])
        rows = [
            ("2026-08-28", "000001.SZ", "合成高标甲", 5),
            ("2026-08-31", "000001.SZ", "合成高标甲", 6),
            ("2026-08-31", "000005.SZ", "合成停牌戊", 5),
            ("2026-09-01", "000002.SZ", "合成高标乙", 6),
            ("2026-09-22", "000003.SZ", "合成缺口丙", 5),
            ("2026-09-24", "000004.SZ", "合成低板丁", 2),
        ]
        rows += [("2026-09-01", f"6000{i:02d}.SH", f"合成样本{i}", 3) for i in range(10)]
        con.executemany(
            "INSERT INTO fact_limit_advance_daily (trade_date, stock_ts_code, stock_name, boards) VALUES (?, ?, ?, ?)", rows,
        )
        # 个股行情：断板候选必须用当日行情核实，否则只能标“未核/待核”。
        # 合成高标甲当日有成交、未封涨停 → 已核断板；合成停牌戊当日无行情行 → 停牌/无成交（待核）。
        con.executemany(
            "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-09-01", "000001.SZ", "合成高标甲", 10.45, 11.00, -5.0, 120_000_000.0),
                ("2026-09-01", "000002.SZ", "合成高标乙", 12.10, 11.00, 10.0, 90_000_000.0),
            ],
        )


if __name__ == "__main__":
    main()
