"""门禁：当日个股日线不能是前一交易日的整份复制（工单 #32）。

07-20 / 08-06 两次事故的形状：行数、覆盖率、字段非空全部正常，只有逐股比对能看出整天与相邻日相同。
"""
from __future__ import annotations

import duckdb

from scripts import check_daily_review_data as gate


def _db(rows):
    con = duckdb.connect()
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, close DOUBLE, amount DOUBLE)")
    con.executemany("INSERT INTO fact_stock_daily VALUES (?,?,?,?)", rows)
    return con


def test_copied_day_is_reported(capsys):
    """整天与前一日逐股相同 → 报缺，并点名前一日与修法。"""
    prev = [("2026-07-20", f"{i:06d}.SZ", 10.0 + i, 1.0 + i) for i in range(20)]
    same = [("2026-07-21", c, px, amt) for _, c, px, amt in prev]
    con = _db(prev + same)
    problems = gate._check_stock_daily_not_copied(con, "2026-07-21")
    assert len(problems) == 1
    assert "2026-07-20" in problems[0] and "100.0%" in problems[0] and "sync-stock-daily" in problems[0]
    assert "逐股相同: 20/20" in capsys.readouterr().out


def test_normal_day_with_a_few_suspended_stocks_passes():
    """个别停牌股两天数值相同是正常的，不到线不报。"""
    prev = [("2026-07-20", f"{i:06d}.SZ", 10.0 + i, 1.0 + i) for i in range(100)]
    today = [("2026-07-21", c, px * 1.01, amt * 0.9) for _, c, px, amt in prev[:98]]
    today += [("2026-07-21", c, px, amt) for _, c, px, amt in prev[98:]]  # 2 只停牌
    con = _db(prev + today)
    assert gate._check_stock_daily_not_copied(con, "2026-07-21") == []


def test_silent_when_no_previous_day():
    con = _db([("2026-07-21", "000001.SZ", 10.0, 1.0)])
    assert gate._check_stock_daily_not_copied(con, "2026-07-21") == []


def test_compares_against_latest_earlier_day_not_calendar_yesterday():
    """前一交易日 = 表里最近的更早日期（跨周末/假日也成立）。"""
    prev = [("2026-07-17", f"{i:06d}.SZ", 10.0 + i, 1.0 + i) for i in range(20)]
    same = [("2026-07-20", c, px, amt) for _, c, px, amt in prev]
    con = _db(prev + same)
    problems = gate._check_stock_daily_not_copied(con, "2026-07-20")
    assert len(problems) == 1 and "2026-07-17" in problems[0]
