"""双轨对账脚本：钉住 2026-09-07 实测出来的涨跌停口径（交易所分档取整、ST 不计）。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "duckdb-backfill" / "scripts" / "qa_local_vs_fupanhui.py"


def _load():
    spec = importlib.util.spec_from_file_location("qa_local_vs_fupanhui", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


qa = _load()


def _up_px(pre: float, lim: float, code: str) -> float:
    con = duckdb.connect()
    return con.execute(
        f"SELECT {qa.up_px_sql('pre', 'lim', 'code')} FROM (SELECT ? AS pre, ? AS lim, ? AS code)", [pre, lim, code]
    ).fetchone()[0]


def test_sh_sz_limit_price_rounds_half_up():
    # 15.05×1.1 = 16.555 → 16.56（fupanhui 涨停明细 434/451 tie 向上）
    assert abs(_up_px(15.05, 0.10, "600769.SH") - 16.56) < 1e-9
    # 56.13×1.2 = 67.356 → 67.36（创业板 20%）
    assert abs(_up_px(56.13, 0.20, "300684.SZ") - 67.36) < 1e-9


def test_bse_limit_price_truncates():
    # 16.25×1.3 = 21.125 → 21.12（北交所 40/40 向下取整；花溪科技 2026-08-28 实测）
    assert abs(_up_px(16.25, 0.30, "920895.BJ") - 21.12) < 1e-9
    # 12.5×1.3 = 16.25 整，取整不变
    assert abs(_up_px(12.5, 0.30, "920895.BJ") - 16.25) < 1e-9


def test_lim_table_excludes_st_and_new_listings_from_limit_stats():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, close DOUBLE, "
        "pre_close DOUBLE, pct_chg DOUBLE, amount DOUBLE)"
    )
    rows = [
        ("2026-09-02", "600540.SH", "新赛股份", 6.73, 6.12, 9.97, 1.0),     # 真涨停
        ("2026-09-02", "002514.SZ", "*ST宝馨", 2.27, 2.06, 10.19, 1.0),    # 涨停但 ST → fupanhui 口径不计
        ("2026-09-02", "301999.SZ", "C新股", 30.0, 20.0, 50.0, 1.0),       # 新股无板
        ("2026-09-02", "000001.SZ", "平安银行", 10.0, 10.0, 0.0, 1.0),      # 平盘
        ("2026-09-02", "600000.SH", "浦发银行", 11.0, 10.0, 10.0, 0.0),     # 停牌占位（amount=0）
    ]
    con.executemany("INSERT INTO fact_stock_daily VALUES (?,?,?,?,?,?,?)", rows)
    qa.build_lim(con, ["2026-09-02"])
    got = con.execute(
        "SELECT stock_ts_code, is_up, is_st FROM lim ORDER BY 1"
    ).fetchall()
    flags = {code: (up, st) for code, up, st in got}
    assert flags["600540.SH"] == (True, False)
    assert flags["002514.SZ"] == (True, True)     # 判定为涨停，但统计口径按 NOT is_st 剔除
    assert flags["301999.SZ"][0] is False
    assert flags["000001.SZ"][0] is False
    assert flags["600000.SH"][0] is False
    n = con.execute("SELECT COUNT(*) FILTER (WHERE is_up AND NOT is_st) FROM lim").fetchone()[0]
    assert n == 1
