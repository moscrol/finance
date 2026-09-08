"""回补验收脚本：把 2026-09-07 四条教训钉成规则——空壳日历行、日历连坐、取最新源写历史日、NUL 名字。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "duckdb-backfill" / "scripts" / "qa_backfill_align.py"


def _load():
    spec = importlib.util.spec_from_file_location("qa_backfill_align", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


qa = _load()
gate = qa._load_gate_module()


def _market_table(con, date: str, hollow: bool) -> None:
    cols = ", ".join(f"{f} DOUBLE" if f != "strength_status" else f"{f} VARCHAR" for f in gate.MARKET_FIELDS)
    con.execute(f"CREATE TABLE fact_market_daily (trade_date DATE, {cols})")
    if hollow:
        con.execute("INSERT INTO fact_market_daily (trade_date, sh_index_close) VALUES (?, 3942.0)", [date])
    else:
        values = ", ".join("'强势'" if f == "strength_status" else "1.0" for f in gate.MARKET_FIELDS)
        con.execute(f"INSERT INTO fact_market_daily VALUES (?, {values})", [date])


def test_hollow_market_row_fails_even_though_row_exists():
    con = duckdb.connect()
    _market_table(con, "2026-09-03", hollow=True)
    rep = qa.Report()
    assert qa.check_market_row(con, rep, gate, "2026-09-03") is True
    fails = [i for i in rep.items if i["level"] == "FAIL"]
    assert len(fails) == 1 and fails[0]["check"] == "market-hollow"
    assert "total_amount" in fails[0]["message"]


def test_complete_market_row_passes():
    con = duckdb.connect()
    _market_table(con, "2026-09-03", hollow=False)
    rep = qa.Report()
    qa.check_market_row(con, rep, gate, "2026-09-03")
    assert not rep.failed


def test_calendar_row_with_missing_gap_tables_fails(monkeypatch):
    from market_feature_store import quality

    con = duckdb.connect()
    con.execute("CREATE TABLE fact_sector_stock_daily (trade_date DATE)")
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE)")
    con.execute("INSERT INTO fact_stock_daily VALUES ('2026-09-03')")
    monkeypatch.setattr(quality, "GAP_TABLES", ["fact_sector_stock_daily", "fact_stock_daily"])
    rep = qa.Report()
    qa.check_calendar_side_effect(con, rep, quality, "2026-09-03", has_market_row=True)
    assert rep.failed
    msg = rep.items[0]["message"]
    assert "fact_sector_stock_daily" in msg and "不换名" in msg
    # 没有日历行就不会连坐
    rep2 = qa.Report()
    qa.check_calendar_side_effect(con, rep2, quality, "2026-09-03", has_market_row=False)
    assert rep2.items == []


def test_latest_snapshot_source_written_on_another_day_fails():
    con = duckdb.connect()
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, source VARCHAR, updated_at TIMESTAMP)")
    con.execute("CREATE TABLE fact_sw_l1_daily (trade_date DATE, source VARCHAR, updated_at TIMESTAMP)")
    # 交易日当天盘后写的快照 = 合法夜跑
    con.execute("INSERT INTO fact_stock_daily VALUES ('2026-09-02', 'eastmoney:snapshot', '2026-09-02 18:31:00')")
    rep = qa.Report()
    qa.check_latest_snapshot_sources(con, rep, "2026-09-02")
    assert not rep.failed
    # 09-07 盘中拿快照写 09-03 = 污染
    con.execute("INSERT INTO fact_stock_daily VALUES ('2026-09-03', 'eastmoney:snapshot', '2026-09-07 12:33:00')")
    con.execute("INSERT INTO fact_sw_l1_daily VALUES ('2026-09-03', 'akshare:index_realtime_sw', '2026-09-07 12:33:00')")
    rep = qa.Report()
    qa.check_latest_snapshot_sources(con, rep, "2026-09-03")
    checks = [(i["level"], i["check"]) for i in rep.items]
    assert checks.count(("FAIL", "source-semantics")) == 2


def test_nul_padded_stock_names_fail():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, "
        "close DOUBLE, pre_close DOUBLE, pct_chg DOUBLE, amount DOUBLE)"
    )
    con.execute("INSERT INTO fact_stock_daily VALUES ('2026-09-02', '000799.SZ', '酒鬼酒', 100.0, 99.0, 1.0101, 5.0)")
    con.execute("INSERT INTO fact_stock_daily VALUES ('2026-09-03', '000799.SZ', '酒鬼酒' || chr(0) || chr(0), 101.0, 100.0, 1.0, 5.0)")
    rep = qa.Report()
    qa.check_stock_chain(con, rep, "2026-09-03", baseline=["2026-09-02"])
    fails = [i["check"] for i in rep.items if i["level"] == "FAIL"]
    assert fails == ["stock-names"]
