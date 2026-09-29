"""bridge_gap_arbitration：两源一致才补桥缺口行。每个测试钉一个失败形状。"""
from __future__ import annotations

import importlib.util
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from market_feature_store.hithink_stock_preview import preview_stock_calculation
from market_feature_store.sync import bridge_gap_arbitration as arb
from market_feature_store.sync.bridge_hithink_stock_daily import BridgeRefused

REPO_ROOT = Path(__file__).resolve().parents[1]
TD, PREV = "2026-09-29", "2026-09-28"
NOW = datetime(2026, 9, 29, 18, 0, 0)


def _bar(code, day, close, source="hithink:daily-k-10d"):
    return (code, day, close, close, close, close, 1_234_500, close * 1_234_500, "none", source, NOW)


def _db(path, bars, events, canonical, names=()):
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE fact_stock_daily_hithink (stock_ts_code VARCHAR, trade_date DATE, open DOUBLE, "
        "high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, turnover DOUBLE, adjusted VARCHAR, "
        "source VARCHAR, updated_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE fact_stock_adjustment_hithink (stock_ts_code VARCHAR, ex_date DATE, "
        "dividend_per_share DOUBLE, per_share_bonus DOUBLE, allotment_ratio DOUBLE, allotment_price DOUBLE, "
        "currency VARCHAR, source VARCHAR, updated_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, "
        "close DOUBLE, pre_close DOUBLE, pct_chg DOUBLE, amount DOUBLE, turnover DOUBLE, source VARCHAR, "
        "updated_at TIMESTAMP, open DOUBLE, high DOUBLE, low DOUBLE, volume DOUBLE)")
    con.executemany("INSERT INTO fact_stock_daily_hithink VALUES (?,?,?,?,?,?,?,?,?,?,?)", bars)
    con.executemany(
        "INSERT INTO fact_stock_adjustment_hithink VALUES (?,?,?,?,?,?,'CNY','hithink:adjustment-factors',?)",
        [(*e, NOW) for e in events])
    con.executemany(
        "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, source) VALUES (?,?,?,1,'x')",
        [(d, c, n) for d, c, n in canonical])
    for d, c, n in names:
        con.execute("INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, source) "
                    "VALUES (?,?,?,1,'x')", [d, c, n])
    return con


def ev(source, close, pre, name=None):
    return arb.Evidence(source, Decimal(str(close)), Decimal(str(pre)), name)


T, E = arb.TENCENT_CAPTURE, arb.EASTMONEY_KLINE


@pytest.fixture
def con(tmp_path):
    bars = [
        _bar("000001.SZ", PREV, 11.30), _bar("000001.SZ", TD, 11.35),
        _bar("300096.SZ", "2026-09-23", 9.02), _bar("300096.SZ", TD, 9.23),      # 复牌
        _bar("688808.SH", PREV, 2174.99), _bar("688808.SH", TD, 1496.00),        # 10 转 4.8
        _bar("301716.SZ", TD, 578.88),                                           # 新股首日
        _bar("600001.SH", "2026-09-10", 10.00), _bar("600001.SH", TD, 9.00),     # 停牌期间有除权
        _bar("600002.SH", PREV, 5.00), _bar("600002.SH", TD, 5.10),              # 已在 canonical
    ]
    events = [("688808.SH", TD, 0.0, 0.48, 0.0, 0.0), ("600001.SH", "2026-09-15", 1.0, 0.0, 0.0, 0.0)]
    canonical = [(TD, "000001.SZ", "平安银行"), (TD, "600002.SH", "某某")]
    names = [("2026-09-23", "300096.SZ", "ST易联众\x00"), ("2026-09-10", "600001.SH", "旧名")]
    c = _db(tmp_path / "t.duckdb", bars, events, canonical, names)
    yield c
    c.close()


def _items(plan):
    return {i["stock_ts_code"]: i for i in plan["items"]}


def _rows(plan):
    return {r[1]: r for r in plan["rows"]}


def test_resumption_fills_when_external_agrees(con):
    plan = arb.plan_gap_fill(con, TD, [{"300096.SZ": ev(E, 9.23, 9.02)}], now=NOW)
    item = _items(plan)["300096.SZ"]
    assert (item["kind"], item["verdict"], item["pre_close"]) == ("resumption", "two-source-agree", 9.02)
    row = _rows(plan)["300096.SZ"]
    assert row[2] == "ST易联众"                       # 历史名去 NUL
    assert row[3:6] == (9.23, 9.02, 2.33)
    assert row[8] == "hithink:daily-k-10d:gapfill-two-source"
    assert item["name_source"] == "db_history_latest_unverified"


def test_no_external_evidence_means_no_fill(con):
    plan = arb.plan_gap_fill(con, TD, [], now=NOW)
    assert plan["fill_count"] == 0
    assert _items(plan)["300096.SZ"]["verdict"] == "no-external-evidence"


def test_pre_close_conflict_blocks(con):
    plan = arb.plan_gap_fill(con, TD, [{"300096.SZ": ev(T, 9.23, 9.02)}, {"300096.SZ": ev(E, 9.23, 9.10)}])
    assert _items(plan)["300096.SZ"]["verdict"] == "conflict-pre-close"
    assert "300096.SZ" not in _rows(plan)


def test_close_mismatch_blocks(con):
    plan = arb.plan_gap_fill(con, TD, [{"300096.SZ": ev(T, 9.30, 9.02)}])
    assert _items(plan)["300096.SZ"]["verdict"] == "conflict-close"


def test_noncash_uses_formula_and_capture(con):
    plan = arb.plan_gap_fill(con, TD, [{"688808.SH": ev(T, 1496.00, 1469.59, "XR联讯仪")}], now=NOW)
    item = _items(plan)["688808.SH"]
    assert (item["kind"], item["internal_candidate"], item["verdict"]) == ("noncash", 1469.59, "two-source-agree")
    row = _rows(plan)["688808.SH"]
    assert row[2] == "XR联讯仪" and item["name_source"] == arb.TENCENT_CAPTURE
    assert row[5] == 1.8  # (1496-1469.59)/1469.59 = 1.797% → 1.80


def test_eastmoney_cannot_vouch_for_noncash(con):
    # 东财日 K 在送转日给未除权前收；即便数字碰巧一致也不算数。
    plan = arb.plan_gap_fill(con, TD, [{"688808.SH": ev(E, 1496.00, 1469.59)}])
    assert _items(plan)["688808.SH"]["verdict"] == "no-external-evidence"


def test_first_day_needs_two_external_sources(con):
    one = arb.plan_gap_fill(con, TD, [{"301716.SZ": ev(T, 578.88, 76.86, "N鸿富诚")}])
    assert _items(one)["301716.SZ"]["verdict"] == "first-day-needs-two-external"
    two = arb.plan_gap_fill(con, TD, [{"301716.SZ": ev(T, 578.88, 76.86, "N鸿富诚")},
                                      {"301716.SZ": ev(E, 578.88, 76.86)}], now=NOW)
    row = _rows(two)["301716.SZ"]
    assert row[2] == "N鸿富诚" and row[4] == 76.86 and row[5] == 653.16


def test_first_day_external_disagreement_blocks(con):
    plan = arb.plan_gap_fill(con, TD, [{"301716.SZ": ev(T, 578.88, 76.86)}, {"301716.SZ": ev(E, 578.88, 76.00)}])
    assert _items(plan)["301716.SZ"]["verdict"] == "conflict-pre-close"


def test_event_inside_suspension_blocks_even_with_evidence(con):
    plan = arb.plan_gap_fill(con, TD, [{"600001.SH": ev(T, 9.00, 9.00)}, {"600001.SH": ev(E, 9.00, 9.00)}])
    assert _items(plan)["600001.SH"]["verdict"] == "events-inside-suspension-gap"


def test_existing_codes_are_not_gaps(con):
    plan = arb.plan_gap_fill(con, TD, [])
    assert set(_items(plan)) == {"300096.SZ", "688808.SH", "301716.SZ", "600001.SH"}


def test_row_arithmetic_matches_preview(con):
    # 正常股：前收=前一计划日收盘，两套算术必须逐位一致。
    preview = preview_stock_calculation(con, TD, stock_codes=["000001.SZ"])["rows"][0]
    current = dict(zip(arb._BAR_COLUMNS, con.execute(
        f"SELECT {', '.join(arb._BAR_COLUMNS)} FROM fact_stock_daily_hithink "
        "WHERE stock_ts_code='000001.SZ' AND trade_date=?", [TD]).fetchone()))
    row = arb._row(date(2026, 9, 29), current, Decimal("11.30"), None, NOW)
    assert (row[3], row[4], row[5], row[6], row[13]) == (
        preview["close"], preview["pre_close"], preview["pct_chg"], preview["amount"], preview["volume"])


def test_apply_inserts_only_and_is_not_repeatable(con):
    evidence = [{"300096.SZ": ev(E, 9.23, 9.02), "688808.SH": ev(T, 1496.00, 1469.59)}]
    other_before = con.execute("SELECT count(*), sum(hash(d)::HUGEINT) FROM fact_stock_daily d "
                               "WHERE trade_date <> ?", [TD]).fetchone()
    result = arb.apply_gap_fill(con, arb.plan_gap_fill(con, TD, evidence, now=NOW))
    assert result == {"trade_date": TD, "inserted": 2, "rows_before": 2, "rows_after": 4,
                      "existing_rows_unchanged": True, "other_days_unchanged": True}
    assert con.execute("SELECT count(*), sum(hash(d)::HUGEINT) FROM fact_stock_daily d "
                       "WHERE trade_date <> ?", [TD]).fetchone() == other_before
    again = arb.plan_gap_fill(con, TD, evidence, now=NOW)
    assert again["fill_count"] == 0
    # 过期计划重放：代码已存在 → 拒绝且回滚
    with pytest.raises(BridgeRefused, match="只插不改"):
        arb.apply_gap_fill(con, {"trade_date": TD, "rows": [
            (date(2026, 9, 29), "300096.SZ", "x", 1, 1, 0, 0, None, "s", NOW, 1, 1, 1, 1)]})
    assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?", [TD]).fetchone()[0] == 4


def test_empty_canonical_day_is_refused(con):
    con.execute("DELETE FROM fact_stock_daily WHERE trade_date = ?", [TD])
    with pytest.raises(BridgeRefused, match="先走桥"):
        arb.plan_gap_fill(con, TD, [])


def test_loaders(tmp_path):
    cap = tmp_path / "cap"
    cap.mkdir()
    (cap / "batch-0001.raw").write_bytes('v_sz301716="51~N鸿富诚~301716~578.88~76.86~80.00~1";'.encode("gbk"))
    assert arb.load_tencent_capture(cap)["301716.SZ"] == ev(T, 578.88, 76.86, "N鸿富诚")
    em = tmp_path / "em"
    em.mkdir()
    (em / "601995.SH.json").write_text(json.dumps({"data": {"klines": [
        "2026-09-14,31.96,31.80,32.24,31.76,267002,853044040.00,-0.66,-0.21",
        "2026-09-23,32.18,32.65,33.28,31.80,472137,1546556175.00,2.67,0.85"]}}), encoding="utf-8")
    (em / "broken.SZ.json").write_text("{not json", encoding="utf-8")
    got = arb.load_eastmoney_kline(em, "2026-09-23")
    assert got == {"601995.SH": ev(E, 32.65, 31.80)}


def test_script_refuses_production_and_defaults_to_dry_run(con, tmp_path, capsys):
    con.close()
    spec = importlib.util.spec_from_file_location("backfill_bridge_gaps",
                                                  REPO_ROOT / "scripts" / "backfill_bridge_gaps.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    db = tmp_path / "t.duckdb"
    assert mod.main(["--db", str(db), "--trade-date", TD, "--production-db", str(db)]) == 2
    em = tmp_path / "em"
    em.mkdir()
    (em / "300096.SZ.json").write_text(json.dumps({"data": {"klines": [
        "2026-09-29,9.10,9.23,9.30,9.00,1,1,2.33,0.21"]}}), encoding="utf-8")
    receipt = tmp_path / "r.json"
    assert mod.main(["--db", str(db), "--trade-date", TD, "--eastmoney-dir", str(em),
                     "--receipt", str(receipt)]) == 0
    assert json.loads(receipt.read_text(encoding="utf-8"))["applied"] is False
    check = duckdb.connect(str(db), read_only=True)
    assert check.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?", [TD]).fetchone()[0] == 2
    check.close()
    assert mod.main(["--db", str(db), "--trade-date", TD, "--eastmoney-dir", str(em), "--apply"]) == 0
    check = duckdb.connect(str(db), read_only=True)
    assert check.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?", [TD]).fetchone()[0] == 3
    check.close()
    assert "可补 1" in capsys.readouterr().out
