"""第四层拦截：逐列填充率闸（2026-09-08 评审——前三层只看复制 / 错日，没有一层看空值）。

事故形状：`fact_market_daily.sh_index_pct_chg` 2026-08-17 为 NULL 两周无人知，事件定价因它丢 3 个锚点；
`fact_stock_daily` 2025-09-19 pct_chg 只有 79%。这一层扫全历史，对 git 里钉住的基线只许变好。
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from scripts import check_daily_review_data as gate

MARKET_COLS = ("sh_index_close", "sh_index_pct_chg")


def _db(market_rows, stock_rows):
    con = duckdb.connect()
    con.execute("CREATE TABLE fact_market_daily (trade_date DATE, sh_index_close DOUBLE, sh_index_pct_chg DOUBLE)")
    con.executemany("INSERT INTO fact_market_daily VALUES (?,?,?)", market_rows)
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, close DOUBLE, amount DOUBLE, pct_chg DOUBLE)")
    con.executemany("INSERT INTO fact_stock_daily VALUES (?,?,?,?,?)", stock_rows)
    return con


def _stock_day(day: str, n: int = 100, null_pct_chg: int = 0):
    rows = []
    for i in range(n):
        pct = None if i < null_pct_chg else 1.0
        rows.append((day, f"{i:06d}.SZ", 10.0 + i, 100.0 + i, pct))
    return rows


def _baseline(**overrides):
    base = {
        "fact_market_daily": {"known_null_dates": {c: ["2024-12-20"] for c in MARKET_COLS}},
        "fact_stock_daily": {"min_fill_pct": {"close": 99.0, "amount": 99.0, "pct_chg": 99.0}, "known_gaps": []},
    }
    base.update(overrides)
    return base


def test_new_null_date_outside_baseline_is_reported():
    """08-17 型：历史某天必填列被写空，基线里没有 → 报，点名日期。"""
    con = _db(
        [("2024-12-20", None, None), ("2026-08-17", None, None), ("2026-09-07", 3900.0, 0.5)],
        _stock_day("2026-09-07"),
    )
    problems = gate._check_fill_rates(con, "2026-09-07", _baseline())
    assert len(problems) == 2  # 两列各一条
    assert all("2026-08-17" in p for p in problems)
    assert any("sh_index_pct_chg" in p for p in problems)


def test_known_null_dates_pass_and_check_date_is_left_to_daily_field_check():
    """钉住的日期不报；当日那一行的空值由逐字段检查报，这里排除免得报两遍。"""
    con = _db(
        [("2024-12-20", None, None), ("2026-09-07", None, None)],
        _stock_day("2026-09-07"),
    )
    assert gate._check_fill_rates(con, "2026-09-07", _baseline()) == []


def test_fewer_nulls_than_baseline_is_not_a_problem():
    """洞补上了不用改基线：少一个空值日不报。"""
    con = _db([("2024-12-20", 3000.0, 0.1), ("2026-09-07", 3900.0, 0.5)], _stock_day("2026-09-07"))
    assert gate._check_fill_rates(con, "2026-09-07", _baseline()) == []


def test_stock_day_below_threshold_is_reported_unless_pinned():
    """个股某天 pct_chg 填充率 79% 不在已知缺口 → 报；钉进 known_gaps 后 → 不报。"""
    market = [("2025-09-19", 3800.0, 0.2), ("2026-09-07", 3900.0, 0.5)]
    con = _db(market, _stock_day("2025-09-19", null_pct_chg=21) + _stock_day("2026-09-07"))
    problems = gate._check_fill_rates(con, "2026-09-07", _baseline())
    assert len(problems) == 1
    assert "2025-09-19" in problems[0] and "pct_chg" in problems[0] and "79.00%" in problems[0]

    pinned = _baseline()
    pinned["fact_stock_daily"]["known_gaps"] = [
        {"trade_date": "2025-09-19", "column": "pct_chg", "fill_pct": 79.0, "reason": "待查"}
    ]
    assert gate._check_fill_rates(con, "2026-09-07", pinned) == []


def test_known_gap_getting_worse_is_reported():
    """已知缺口钉的是「不许更坏」：填充率比钉住的值再掉过容差 → 报。"""
    con = _db([("2026-06-23", 3800.0, 0.2)], _stock_day("2026-06-23", null_pct_chg=10))
    pinned = _baseline()
    pinned["fact_stock_daily"]["known_gaps"] = [
        {"trade_date": "2026-06-23", "column": "pct_chg", "fill_pct": 95.12, "reason": "北交所等解封"}
    ]
    problems = gate._check_fill_rates(con, "2026-09-07", pinned)
    assert len(problems) == 1 and "已知的洞变大了" in problems[0] and "95.12%" in problems[0]


def test_update_baseline_keeps_reasons_and_marks_new_gaps(tmp_path: Path):
    path = tmp_path / "fill-rate-baseline.json"
    path.write_text(json.dumps({
        "fact_market_daily": {"known_null_dates": {}},
        "fact_stock_daily": {
            "min_fill_pct": {"close": 99.0, "amount": 99.0, "pct_chg": 99.0},
            "known_gaps": [{"trade_date": "2026-06-23", "column": "pct_chg", "fill_pct": 95.0, "reason": "北交所等解封"}],
        },
    }, ensure_ascii=False), encoding="utf-8")
    con = _db(
        [("2026-06-23", None, 0.2), ("2026-09-07", 3900.0, 0.5)],
        _stock_day("2026-06-23", null_pct_chg=5) + _stock_day("2026-09-07", null_pct_chg=2),
    )
    baseline = gate.update_fill_rate_baseline(con, path, today="2026-09-08")
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written == baseline
    assert written["fact_market_daily"]["known_null_dates"]["sh_index_close"] == ["2026-06-23"]
    gaps = {(g["trade_date"], g["column"]): g for g in written["fact_stock_daily"]["known_gaps"]}
    assert gaps[("2026-06-23", "pct_chg")]["reason"] == "北交所等解封"  # 旧原因保留
    assert gaps[("2026-06-23", "pct_chg")]["fill_pct"] == 95.0
    assert gaps[("2026-09-07", "pct_chg")]["reason"].startswith("待查（2026-09-08")
    # 基线写完再检查同一库 → 全绿（基线钉的就是现状）
    assert gate._check_fill_rates(con, "2026-09-08", written) == []


def test_repo_baseline_covers_every_required_market_field():
    """仓里的基线必须与 MARKET_FIELDS 同步——少一列就是那一列没人守。"""
    baseline = gate.load_fill_rate_baseline()
    pinned = set(baseline["fact_market_daily"]["known_null_dates"])
    assert pinned == set(gate.MARKET_FIELDS)
    for column in gate.STOCK_FILL_COLUMNS:
        assert baseline["fact_stock_daily"]["min_fill_pct"][column] >= 95.0
    for gap in baseline["fact_stock_daily"]["known_gaps"]:
        assert gap["reason"], f"{gap['trade_date']} {gap['column']} 缺 reason"
