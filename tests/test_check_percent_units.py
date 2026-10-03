"""量纲核验脚本：同日原值反算能分清百分数和小数，配对太少或比值不集中时不下结论。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import duckdb
import pytest

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("check_percent_units", REPO / "scripts" / "check_percent_units.py")
units = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("check_percent_units", units)
_SPEC.loader.exec_module(units)


def _db(tmp_path: Path, *, scale_auction: float, scale_global: float, rows: int = 40) -> Path:
    path = tmp_path / "mfs.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fact_stock_daily(trade_date DATE, stock_ts_code TEXT, open DOUBLE, close DOUBLE, pre_close DOUBLE)")
    con.execute("CREATE TABLE fact_auction_stock_daily(trade_date DATE, panel_key TEXT, stock_ts_code TEXT, auction_pct DOUBLE, pct_chg DOUBLE)")
    con.execute("CREATE TABLE fact_auction_hithink(trade_date DATE, stock_ts_code TEXT, kind TEXT, auction_price DOUBLE, pre_close_price DOUBLE, auction_pct DOUBLE)")
    con.execute("CREATE TABLE fact_global_stock_daily(trade_date DATE, source_trade_date DATE, ts_code TEXT, close DOUBLE, pct_chg DOUBLE, pct_chg_5d DOUBLE)")
    for i in range(rows):
        code = f"{600000 + i}.SH"
        pre, opening, close = 10.0, 10.0 * (1 + (i % 7 + 1) / 100), 10.0 * (1 + (i % 5 + 2) / 100)
        con.execute("INSERT INTO fact_stock_daily VALUES ('2026-08-03', ?, ?, ?, ?)", [code, opening, close, pre])
        auction = (opening / pre - 1) * 100 * scale_auction
        con.execute("INSERT INTO fact_auction_stock_daily VALUES ('2026-08-03', 'zt', ?, ?, ?)",
                    [code, auction, (close / pre - 1) * 100 * scale_auction])
        con.execute("INSERT INTO fact_auction_hithink VALUES ('2026-08-03', ?, 'snapshot', ?, ?, ?)",
                    [code, opening, pre, auction])
    for i in range(6):
        code = f"US{i}"
        closes = [100.0 * (1.03 ** (day + i % 3)) for day in range(12)]
        for day, value in enumerate(closes):
            p5 = (value / closes[day - 5] - 1) * 100 * scale_global if day >= 5 else None
            p1 = (value / closes[day - 1] - 1) * 100 * scale_global if day >= 1 else None
            con.execute("INSERT INTO fact_global_stock_daily VALUES (?, ?, ?, ?, ?, ?)",
                        [f"2026-08-{day + 3:02d}", f"2026-08-{day + 2:02d}", code, value, p1, p5])
    con.close()
    return path


def _verdicts(path: Path) -> dict[str, str]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        return {row["name"]: row["verdict"] for row in units.run_checks(con)}
    finally:
        con.close()


def test_percent_columns_are_recognised(tmp_path):
    verdicts = _verdicts(_db(tmp_path, scale_auction=1.0, scale_global=1.0))
    assert set(verdicts.values()) == {"percent"}


def test_fraction_columns_are_recognised(tmp_path):
    verdicts = _verdicts(_db(tmp_path, scale_auction=0.01, scale_global=0.01))
    assert set(verdicts.values()) == {"fraction"}


def test_mixed_scale_is_unclear_not_guessed(tmp_path):
    pairs = [(2.0, 2.0)] * 15 + [(0.02, 2.0)] * 15
    assert units.judge_pairs(pairs)["verdict"] == "unclear"


def test_tiny_denominators_and_small_samples_do_not_decide():
    # 反算 0.1% 的配对不进比值（四舍五入就能带飞）；进比值的不足 20 对 → 不下结论。
    pairs = [(0.3, 0.1)] * 50 + [(2.0, 2.0)] * 10
    result = units.judge_pairs(pairs)
    assert result["ratio_pairs"] == 10 and result["verdict"] == "insufficient"


def test_missing_tables_are_reported(tmp_path):
    path = tmp_path / "empty.duckdb"
    duckdb.connect(str(path)).close()
    assert set(_verdicts(path).values()) == {"table_missing"}


def test_cli_is_read_only_and_renders(tmp_path, capsys):
    path = _db(tmp_path, scale_auction=1.0, scale_global=0.01)
    before = path.stat().st_mtime_ns
    assert units.main(["--db", str(path)]) == 0
    out = capsys.readouterr().out
    assert "复盘会竞价涨幅 auction_pct" in out and "percent" in out and "fraction" in out
    assert path.stat().st_mtime_ns == before
    assert units.main(["--db", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {r["name"]: r["verdict"] for r in payload["results"]}["海外个股 pct_chg_5d"] == "fraction"


def test_missing_db_exits_2(tmp_path):
    assert units.main(["--db", str(tmp_path / "nope.duckdb")]) == 2


@pytest.mark.parametrize("name", [c["name"] for c in units.CHECKS])
def test_every_check_names_the_finance_query_label_it_decides(name):
    check = next(c for c in units.CHECKS if c["name"] == name)
    assert check["label"]
