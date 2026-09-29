"""scripts/report_bridge_gaps.py：桥静默缺行报告，每个测试钉一个失败形状。

变异自检（手工）：
- 把复牌判定 `last_bar["date"] < prev` 改成 `<=` → test_noncash_formula_matches_capture、
  test_pre_close_mismatch_is_conflict 红（前一日有 bar 的送转股被误当复牌）；
- 去掉 `_verdict` 里的收盘核对 → test_close_mismatch_is_conflict 红；
- 送转公式去掉配股项 → test_allotment_formula 红；
- main() 改成读写连接 → test_main_is_read_only_and_fail_on_gaps 红（库文件设为只读权限，读写连接打不开）。
以上四条已于 2026-09-29 实跑确认。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "scripts" / "report_bridge_gaps.py"
_spec = importlib.util.spec_from_file_location("report_bridge_gaps", _SCRIPT)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

TD, PREV = "2026-09-29", "2026-09-28"
NOW = datetime(2026, 9, 29, 18, 0, 0)


def _bar(code, day, close):
    return (code, day, close, close, close, close, 1_000_000, close * 1_000_000, "none",
            "hithink:daily-k-10d", NOW)


def _make_db(path: Path, bars, events, canonical):
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE fact_stock_daily_hithink (stock_ts_code VARCHAR, trade_date DATE, open DOUBLE, "
        "high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, turnover DOUBLE, adjusted VARCHAR, "
        "source VARCHAR, updated_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE fact_stock_adjustment_hithink (stock_ts_code VARCHAR, ex_date DATE, "
        "dividend_per_share DOUBLE, per_share_bonus DOUBLE, allotment_ratio DOUBLE, allotment_price DOUBLE, "
        "currency VARCHAR, source VARCHAR, updated_at TIMESTAMP)")
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR)")
    con.executemany("INSERT INTO fact_stock_daily_hithink VALUES (?,?,?,?,?,?,?,?,?,?,?)", bars)
    con.executemany(
        "INSERT INTO fact_stock_adjustment_hithink VALUES (?,?,?,?,?,?,'CNY','hithink:adjustment-factors',?)",
        [(*e, NOW) for e in events])
    con.executemany("INSERT INTO fact_stock_daily VALUES (?,?,'x')", [(TD, c) for c in canonical])
    return con


def _capture_dir(tmp_path: Path, quotes: dict[str, tuple[str, float, float]]) -> Path:
    out = tmp_path / "capture"
    out.mkdir()
    lines = []
    for code, (name, close, pre_close) in quotes.items():
        num, market = code.split(".")
        lines.append(f'v_{market.lower()}{num}="51~{name}~{num}~{close}~{pre_close}~{close}~1~2~3";')
    (out / "batch-0001.raw").write_bytes("\n".join(lines).encode("gbk"))
    return out


@pytest.fixture
def scenario(tmp_path):
    bars = [
        _bar("000001.SZ", PREV, 11.30), _bar("000001.SZ", TD, 11.35),        # 正常，已入库
        _bar("300096.SZ", "2026-09-23", 9.02), _bar("300096.SZ", TD, 9.23),  # 复牌
        _bar("601238.SH", "2026-09-11", 5.50), _bar("601238.SH", TD, 5.60),  # 复牌，捕获里没有
        _bar("688808.SH", PREV, 2174.99), _bar("688808.SH", TD, 1500.00),    # 10 转 4.8
        _bar("301716.SZ", TD, 578.88),                                       # 新股首日
        _bar("600001.SH", "2026-09-10", 10.00), _bar("600001.SH", TD, 9.00), # 复牌，停牌期间有除权
    ]
    events = [
        ("688808.SH", TD, 0.0, 0.48, 0.0, 0.0),
        ("600001.SH", "2026-09-15", 1.0, 0.0, 0.0, 0.0),
    ]
    con = _make_db(tmp_path / "t.duckdb", bars, events, canonical=["000001.SZ"])
    capture = mod.load_capture(_capture_dir(tmp_path, {
        "000001.SZ": ("平安银行", 11.35, 11.30),
        "300096.SZ": ("易联众", 9.23, 9.02),
        "688808.SH": ("XR联讯仪", 1500.00, 1469.59),
        "301716.SZ": ("N鸿富诚", 578.88, 76.86),
        "600001.SH": ("某某股份", 9.00, 9.00),
    }))
    yield con, capture
    con.close()


def _by_code(report):
    return {g["stock_ts_code"]: g for g in report["gaps"]}


def test_capture_parser_reads_gbk_names(scenario):
    _, capture = scenario
    assert capture["301716.SZ"] == {"name": "N鸿富诚", "close": 578.88, "pre_close": 76.86}


def test_only_vendor_minus_canonical_is_reported(scenario):
    con, capture = scenario
    report = mod.build_report(con, TD, capture)
    assert report["vendor_codes"] == 6 and report["canonical_rows"] == 1
    assert set(_by_code(report)) == {"300096.SZ", "601238.SH", "688808.SH", "301716.SZ", "600001.SH"}
    assert report["database_writes"] is False


def test_resumption_two_source_agree(scenario):
    con, capture = scenario
    g = _by_code(mod.build_report(con, TD, capture))["300096.SZ"]
    assert g["reasons"] == ["missing-previous-bar"]
    assert g["last_bar"] == {"date": "2026-09-23", "close": 9.02}
    assert g["candidate_pre_close"] == 9.02
    assert g["candidate_basis"] == "resumption_last_close_no_recorded_event"
    assert g["verdict"] == "two-source-agree"


def test_resumption_missing_from_capture_is_named(scenario):
    con, capture = scenario
    g = _by_code(mod.build_report(con, TD, capture))["601238.SH"]
    assert g["candidate_pre_close"] == 5.5 and g["verdict"] == "no-capture"


def test_noncash_formula_matches_capture(scenario):
    con, capture = scenario
    g = _by_code(mod.build_report(con, TD, capture))["688808.SH"]
    assert g["reasons"] == ["unsupported-noncash-action"]
    assert g["candidate_pre_close"] == 1469.59
    assert g["verdict"] == "two-source-agree"


def test_first_day_is_capture_only(scenario):
    con, capture = scenario
    g = _by_code(mod.build_report(con, TD, capture))["301716.SZ"]
    assert g["last_bar"] is None and g["candidate_pre_close"] is None
    assert g["candidate_basis"] == "no_prior_bar" and g["verdict"] == "capture-only"


def test_event_inside_suspension_gap_blocks_candidate(scenario):
    con, capture = scenario
    g = _by_code(mod.build_report(con, TD, capture))["600001.SH"]
    assert g["candidate_pre_close"] is None
    assert g["candidate_basis"] == "events_inside_suspension_gap"
    assert [e["ex_date"] for e in g["events_in_gap"]] == ["2026-09-15"]


def test_close_mismatch_is_conflict(scenario):
    con, capture = scenario
    capture["300096.SZ"] = {"name": "易联众", "close": 9.30, "pre_close": 9.02}
    g = _by_code(mod.build_report(con, TD, capture))["300096.SZ"]
    assert g["verdict"] == "conflict"


def test_pre_close_mismatch_is_conflict(scenario):
    con, capture = scenario
    capture["688808.SH"] = {"name": "XR联讯仪", "close": 1500.00, "pre_close": 1470.00}
    assert _by_code(mod.build_report(con, TD, capture))["688808.SH"]["verdict"] == "conflict"


def test_without_capture_verdict_is_none(scenario):
    con, _ = scenario
    report = mod.build_report(con, TD, None)
    assert report["capture_checked"] is False
    assert all(g["verdict"] is None and g["capture"] is None for g in report["gaps"])


def test_allotment_formula():
    event = {"dividend_per_share": 0.1, "per_share_bonus": 0.0, "allotment_ratio": 0.3,
             "allotment_price": 5.0}
    # (10 - 0.1 + 5*0.3) / 1.3 = 8.769… → 8.77
    assert str(mod.noncash_reference(10.0, event)) == "8.77"


def test_main_is_read_only_and_fail_on_gaps(scenario, tmp_path, capsys):
    con, _ = scenario
    con.close()
    db = tmp_path / "t.duckdb"
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    db.chmod(0o444)  # 只读权限：脚本若开读写连接会直接失败
    out = tmp_path / "r.json"
    cap = tmp_path / "capture"
    assert mod.main(["--trade-date", TD, "--db", str(db), "--capture-dir", str(cap), "--json", str(out)]) == 0
    assert mod.main(["--trade-date", TD, "--db", str(db), "--fail-on-gaps"]) == 1
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    db.chmod(0o644)
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["gap_count"] == 5
    assert "300096.SZ" in capsys.readouterr().out


def test_main_rejects_bad_input(tmp_path):
    assert mod.main(["--trade-date", "20260929", "--db", str(tmp_path / "x.duckdb")]) == 2
    assert mod.main(["--trade-date", TD, "--db", str(tmp_path / "missing.duckdb")]) == 2
