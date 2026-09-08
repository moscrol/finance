"""工单 #41 E：授课框架读口切到同花顺并跑表。"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from intelligence.services.teaching_framework.source_views import (
    AUCTION_ZT_VIEW,
    DRAGON_VIEW,
    HIGH_VIEW,
    SECTOR_PX_VIEW,
    STOCK_VIEW,
    attach_teaching_sources,
)
from scripts.teaching_framework import _open_source


def test_attach_falls_back_when_hithink_tables_absent(tmp_path: Path) -> None:
    path = tmp_path / "old.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, close DOUBLE, high DOUBLE, amount DOUBLE, pct_chg DOUBLE)")
    con.execute("INSERT INTO fact_stock_daily VALUES ('2026-01-05', 'X', 'x', 10, 11, 3.0, 1.5)")
    con.execute("CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code VARCHAR, sector_name VARCHAR, pct_chg DOUBLE, amount DOUBLE)")
    con.execute("CREATE TABLE fact_stock_high_daily (trade_date DATE, stock_ts_code VARCHAR, primary_high_period VARCHAR, sw_l1 VARCHAR)")
    con.execute("INSERT INTO fact_stock_high_daily VALUES ('2026-01-05', 'X', '1y', '电子')")
    con.execute("INSERT INTO fact_stock_high_daily VALUES ('2026-01-05', 'Y', '20d', '电子')")
    con.execute("CREATE TABLE fact_dragon_tiger_daily (trade_date DATE, stock_ts_code VARCHAR, net_amount DOUBLE)")
    con.execute("INSERT INTO fact_dragon_tiger_daily VALUES ('2026-01-05', 'X', 2.0)")
    con.execute("CREATE TABLE fact_auction_stock_daily (trade_date DATE, panel_key VARCHAR, stock_ts_code VARCHAR, auction_pct DOUBLE, auction_amount DOUBLE)")
    con.execute("INSERT INTO fact_auction_stock_daily VALUES ('2026-01-05', 'zt', 'X', 3.0, 0.5)")
    con.close()

    source, used = _open_source(path)
    try:
        assert used == {
            "stock": "fact_stock_daily",
            "sector_px": "fact_sector_daily",
            "new_high": "fact_stock_high_daily",
            "dragon": "fact_dragon_tiger_daily",
            "auction_zt": "fact_auction_stock_daily",
        }
        assert source.execute(f"SELECT amount, pct_chg FROM {STOCK_VIEW}").fetchone() == (3.0, 1.5)
        assert source.execute(f"SELECT COUNT(*) FROM {HIGH_VIEW}").fetchone()[0] == 1
        assert source.execute(f"SELECT net_amount FROM {DRAGON_VIEW}").fetchone()[0] == 2.0
        assert source.execute(f"SELECT auction_pct FROM {AUCTION_ZT_VIEW}").fetchone()[0] == 3.0
    finally:
        source.close()


def test_hithink_stock_and_dragon_unit_conversion(tmp_path: Path) -> None:
    path = tmp_path / "new.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """CREATE TABLE fact_stock_daily_hithink (
            trade_date DATE, stock_ts_code VARCHAR, close DOUBLE, high DOUBLE, low DOUBLE, open DOUBLE, turnover DOUBLE)"""
    )
    con.executemany(
        "INSERT INTO fact_stock_daily_hithink VALUES (?, 'X', ?, ?, 9, 10, 300000000)",
        [("2026-01-05", 10.0, 11.0), ("2026-01-06", 11.0, 12.0)],
    )
    con.execute("CREATE TABLE fact_dragon_tiger_hithink (trade_date DATE, stock_ts_code VARCHAR, net_value DOUBLE)")
    con.execute("INSERT INTO fact_dragon_tiger_hithink VALUES ('2026-01-06', 'X', 200000000)")
    sources = attach_teaching_sources(con)
    assert sources["stock"] == "fact_stock_daily_hithink"
    assert sources["dragon"] == "fact_dragon_tiger_hithink"
    rows = con.execute(f"SELECT trade_date, amount, pct_chg FROM {STOCK_VIEW} ORDER BY 1").fetchall()
    assert rows[0][1] == pytest.approx(3.0)
    assert rows[0][2] is None
    assert rows[1][1] == pytest.approx(3.0)
    assert rows[1][2] == pytest.approx(10.0)
    assert con.execute(f"SELECT stock_name FROM {STOCK_VIEW} LIMIT 1").fetchone()[0] is None
    assert con.execute(f"SELECT net_amount FROM {DRAGON_VIEW}").fetchone()[0] == pytest.approx(2.0)
    con.close()


def test_new_high_from_ten_year_k(tmp_path: Path) -> None:
    """1 年新高 = 过去 365 个日历日窗口内的最高价，且要有满一年的历史。"""
    path = tmp_path / "highs.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """CREATE TABLE fact_stock_daily_hithink (
            trade_date DATE, stock_ts_code VARCHAR, close DOUBLE, high DOUBLE, low DOUBLE, open DOUBLE, turnover DOUBLE)"""
    )
    start = date(2024, 1, 2)
    days = [start + timedelta(days=i) for i in range(500)]
    con.executemany(
        "INSERT INTO fact_stock_daily_hithink VALUES (?, 'UP', ?, ?, 1, 1, 1)",
        [(d, 10.0 + i, 10.0 + i) for i, d in enumerate(days)],
    )
    # DN 一路阴跌：任何一天的窗口里最高价都在一年前，永远不是新高
    con.executemany(
        "INSERT INTO fact_stock_daily_hithink VALUES (?, 'DN', 50, ?, 1, 1, 1)",
        [(d, 100.0 - i * 0.1) for i, d in enumerate(days)],
    )
    attach_teaching_sources(con)
    last = days[-1]
    codes = {row[0] for row in con.execute(f"SELECT stock_ts_code FROM {HIGH_VIEW} WHERE trade_date = ?", [last]).fetchall()}
    assert codes == {"UP"}
    first_ok = start + timedelta(days=365)
    assert con.execute(f"SELECT COUNT(*) FROM {HIGH_VIEW} WHERE trade_date = ? AND stock_ts_code = 'UP'", [first_ok]).fetchone()[0] == 1
    assert con.execute(f"SELECT COUNT(*) FROM {HIGH_VIEW} WHERE trade_date = ? AND stock_ts_code = 'UP'", [first_ok - timedelta(days=1)]).fetchone()[0] == 0


def test_new_high_survives_a_suspension_inside_the_window(tmp_path: Path) -> None:
    """一年里停牌过一天不该把整只股永久剔除（旧的 252 连续行口径会）。"""
    path = tmp_path / "susp.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """CREATE TABLE fact_stock_daily_hithink (
            trade_date DATE, stock_ts_code VARCHAR, close DOUBLE, high DOUBLE, low DOUBLE, open DOUBLE, turnover DOUBLE)"""
    )
    start = date(2024, 1, 2)
    days = [start + timedelta(days=i) for i in range(500)]
    gap = days[400]
    con.executemany(
        "INSERT INTO fact_stock_daily_hithink VALUES (?, 'SUSP', ?, ?, 1, 1, 1)",
        [(d, 10.0 + i, 10.0 + i) for i, d in enumerate(days) if d != gap],
    )
    attach_teaching_sources(con)
    assert con.execute(
        f"SELECT COUNT(*) FROM {HIGH_VIEW} WHERE trade_date = ? AND stock_ts_code = 'SUSP'",
        [days[-1]],
    ).fetchone()[0] == 1
    con.close()


def test_pct_chg_uses_ex_dividend_adjusted_prev_close(tmp_path: Path) -> None:
    """未复权 dump 上，除权日要用复权事件还原前收盘，否则送转会算成暴跌。"""
    path = tmp_path / "adj.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """CREATE TABLE fact_stock_daily_hithink (
            trade_date DATE, stock_ts_code VARCHAR, close DOUBLE, high DOUBLE, low DOUBLE, open DOUBLE, turnover DOUBLE)"""
    )
    con.executemany(
        "INSERT INTO fact_stock_daily_hithink VALUES (?, 'X', ?, ?, 1, 1, 1)",
        [("2026-05-26", 26.19, 26.19), ("2026-05-27", 18.30, 18.30)],
    )
    con.execute(
        """CREATE TABLE fact_stock_adjustment_hithink (
            stock_ts_code VARCHAR, ex_date DATE, dividend_per_share DOUBLE,
            per_share_bonus DOUBLE, allotment_ratio DOUBLE, allotment_price DOUBLE)"""
    )
    # 10 送 4 派 0.5：adj_prev = (26.19 − 0.05) / 1.4 = 18.671 → −1.99%，不是 −30.13%
    con.execute("INSERT INTO fact_stock_adjustment_hithink VALUES ('X', '2026-05-27', 0.05, 0.4, 0, 0)")
    sources = attach_teaching_sources(con)
    assert sources["stock"] == "fact_stock_daily_hithink+adjustment"
    pct = con.execute(
        f"SELECT pct_chg FROM {STOCK_VIEW} WHERE trade_date = DATE '2026-05-27'"
    ).fetchone()[0]
    assert pct == pytest.approx(-1.987, abs=0.01)
    con.close()


def test_dragon_falls_back_to_legacy_on_days_hithink_lacks(tmp_path: Path) -> None:
    """同花顺龙虎榜只回溯一年，整天没有的日子必须回退旧表，不能丢标签。"""
    path = tmp_path / "dragon.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fact_dragon_tiger_hithink (trade_date DATE, stock_ts_code VARCHAR, net_value DOUBLE)")
    con.execute("INSERT INTO fact_dragon_tiger_hithink VALUES ('2026-01-06', 'X', 200000000)")
    con.execute("CREATE TABLE fact_dragon_tiger_daily (trade_date DATE, stock_ts_code VARCHAR, net_amount DOUBLE)")
    con.executemany(
        "INSERT INTO fact_dragon_tiger_daily VALUES (?, ?, ?)",
        [("2025-03-04", "OLD", 1.5), ("2026-01-06", "OLD", 9.9)],
    )
    used = attach_teaching_sources(con)
    assert used["dragon"] == "fact_dragon_tiger_hithink+legacy_fill"
    rows = {
        (str(d), s): v
        for d, s, v in con.execute(
            f"SELECT trade_date, stock_ts_code, net_amount FROM {DRAGON_VIEW}"
        ).fetchall()
    }
    assert rows[("2025-03-04", "OLD")] == pytest.approx(1.5)  # 新源没有这天 → 旧表补
    assert rows[("2026-01-06", "X")] == pytest.approx(2.0)
    assert ("2026-01-06", "OLD") not in rows  # 新源有这天 → 整天不混旧表，避免重复计数
    con.close()


def test_broad_indexes_are_not_sectors(tmp_path: Path) -> None:
    """000001.SH 这类宽基指数不能进「板块涨幅中位 / 上涨比」的分母。"""
    path = tmp_path / "sector.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """CREATE TABLE fact_sector_kline_daily (
            trade_date DATE, sector_ts_code VARCHAR, close DOUBLE, turnover DOUBLE)"""
    )
    con.executemany(
        "INSERT INTO fact_sector_kline_daily VALUES (?, ?, ?, 1)",
        [
            ("2026-01-05", "886053.TI", 100.0), ("2026-01-06", "886053.TI", 110.0),
            ("2026-01-05", "000001.SH", 3000.0), ("2026-01-06", "000001.SH", 3030.0),
        ],
    )
    con.execute(
        """CREATE TABLE dim_sector_hithink (
            sector_ts_code VARCHAR, sector_name VARCHAR, category VARCHAR)"""
    )
    con.executemany(
        "INSERT INTO dim_sector_hithink VALUES (?, ?, ?)",
        [("886053.TI", "BC电池", "cn_concept"), ("000001.SH", None, "index")],
    )
    attach_teaching_sources(con)
    codes = {
        r[0] for r in con.execute(f"SELECT DISTINCT sector_ts_code FROM {SECTOR_PX_VIEW}").fetchall()
    }
    assert codes == {"886053.TI"}
    con.close()


def test_auction_zt_is_snapshot_intersect_yesterday_limit(tmp_path: Path) -> None:
    path = tmp_path / "au.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
    con.executemany("INSERT INTO fact_market_daily VALUES (?)", [("2026-01-05",), ("2026-01-06",), ("2026-01-07",)])
    con.execute("CREATE TABLE fact_theme_limit_stock_daily (trade_date DATE, stock_ts_code VARCHAR, limit_status VARCHAR)")
    con.execute("INSERT INTO fact_theme_limit_stock_daily VALUES ('2026-01-05', 'X', 'U')")
    con.execute("INSERT INTO fact_theme_limit_stock_daily VALUES ('2026-01-06', 'Z', 'U')")
    con.execute(
        """CREATE TABLE fact_auction_hithink (
            trade_date DATE, stock_ts_code VARCHAR, kind VARCHAR, auction_pct DOUBLE, auction_amount DOUBLE)"""
    )
    con.executemany(
        "INSERT INTO fact_auction_hithink VALUES ('2026-01-06', ?, 'snapshot', ?, 1.0)",
        [("X", 9.0), ("Y", 8.0)],
    )
    con.execute(
        """CREATE TABLE fact_auction_stock_daily (
            trade_date DATE, panel_key VARCHAR, stock_ts_code VARCHAR, auction_pct DOUBLE, auction_amount DOUBLE)"""
    )
    con.execute("INSERT INTO fact_auction_stock_daily VALUES ('2026-01-05', 'zt', 'OLD', -1.0, 0.2)")
    con.execute("INSERT INTO fact_auction_stock_daily VALUES ('2026-01-06', 'zt', 'OLD', 4.0, 0.2)")
    con.execute("INSERT INTO fact_auction_stock_daily VALUES ('2026-01-07', 'zt', 'OLD', 2.0, 0.2)")
    used = attach_teaching_sources(con)
    assert used["auction_zt"] == "fact_auction_hithink+legacy_fill"
    rows = {
        (str(d), s): pct
        for d, s, pct in con.execute(
            f"SELECT trade_date, stock_ts_code, auction_pct FROM {AUCTION_ZT_VIEW} ORDER BY 1, 2"
        ).fetchall()
    }
    assert rows[("2026-01-05", "OLD")] == -1.0
    assert rows[("2026-01-06", "X")] == 9.0
    assert ("2026-01-06", "Y") not in rows
    assert ("2026-01-06", "OLD") not in rows
    assert rows[("2026-01-07", "OLD")] == 2.0
    con.close()
