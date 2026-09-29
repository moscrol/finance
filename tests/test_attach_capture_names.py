"""attach_capture_names: synthetic capture bytes + tmp DuckDB only (no network, no production DB)."""
from __future__ import annotations

from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

from market_feature_store.db import init_db

DAY = date(2026, 9, 23)
SCRIPT = Path(__file__).resolve().parents[1] / "skills/duckdb-backfill/scripts/attach_capture_names.py"


def _load():
    spec = importlib.util.spec_from_file_location("attach_capture_names", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()

# 301686.SZ on 2026-09-23 as sealed in the real capture (hands; notional within OHLC bounds).
NEW_LISTING = {1: "C中塑股份", 2: "301686", 3: "283.5", 4: "433", 5: "340", 6: "66311",
               30: "20260923161406", 32: "-34.53", 33: "368", 34: "281.07",
               35: "283.5/66311/2138186731", 38: "10", 40: "0"}
NAMED = {1: "平安银行", 2: "000001", 3: "11", 4: "10", 5: "10", 6: "100",
         30: "20260923150003", 32: "10", 33: "11", 34: "10", 35: "11/100/105000", 38: "1", 40: "0"}


def quote(symbol: str, fields: dict[int, str]) -> bytes:
    values = [""] * 58
    for index, value in fields.items():
        values[index] = value
    return (f'v_{symbol}="' + "~".join(values) + '";\n').encode("gbk")


def make_capture(root: Path, lines: dict[str, bytes], *, day: date = DAY) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    raw = b"".join(lines.values())
    (root / "batch.raw").write_bytes(raw)
    codes = list(lines)
    receipt = {"target_date": day.isoformat(), "codes": codes, "captured_code_count": len(codes),
               "batches": [{"file": "batch.raw", "sha256": hashlib.sha256(raw).hexdigest(),
                            "codes": codes, "http_status": 200}]}
    (root / "receipt.json").write_text(json.dumps(receipt))
    return root


def make_db(path: Path, rows: list[tuple]) -> Path:
    con = duckdb.connect(str(path))
    try:
        init_db(con)
        con.executemany(
            "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, pre_close, "
            "pct_chg, amount, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    finally:
        con.close()
    return path


def names(path: Path) -> dict[str, str | None]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        return dict(con.execute("SELECT stock_ts_code, stock_name FROM fact_stock_daily "
                                "WHERE trade_date = ? ORDER BY 1", [DAY]).fetchall())
    finally:
        con.close()


BRIDGED_NULL = (DAY, "301686.SZ", None, 283.5, 433.0, -34.53, 21.3819, "hithink:daily-k-10d")
BRIDGED_NAMED = (DAY, "000001.SZ", "平安银行", 11.0, 10.0, 10.0, 0.0011, "hithink:daily-k-10d")


@pytest.fixture
def capture(tmp_path):
    return make_capture(tmp_path / "cap", {"301686.SZ": quote("sz301686", NEW_LISTING),
                                          "000001.SZ": quote("sz000001", NAMED | {1: "别的名字"})})


def test_fills_only_null_named_bridge_rows_and_keeps_provenance(tmp_path, capture):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL, BRIDGED_NAMED])
    receipt = tmp_path / "r.json"
    result = mod.run(DAY, capture, receipt, db_path=db)
    assert names(db) == {"000001.SZ": "平安银行", "301686.SZ": "C中塑股份"}  # existing name kept
    assert result["applied"] is True
    saved = json.loads(receipt.read_text())
    [target] = saved["targets"]
    assert target["stock_ts_code"] == "301686.SZ"
    assert target["name_source"] == "tencent:captured-dated-quote"
    assert target["quote_timestamp"] == "20260923161406"
    assert saved["capture_audit"]["capture_validated"] is True
    assert saved["capture_audit"]["receipt_sha256"] == hashlib.sha256(
        (capture / "receipt.json").read_bytes()).hexdigest()


@pytest.mark.parametrize("field, value", [("close", 283.6), ("pre_close", 432.0),
                                          ("pct_chg", -34.52), ("amount", 21.3829)])
def test_refuses_when_capture_is_not_the_same_bar(tmp_path, capture, field, value):
    row = dict(zip(("trade_date", "stock_ts_code", "stock_name", "close", "pre_close", "pct_chg",
                    "amount", "source"), BRIDGED_NULL))
    row[field] = value
    db = make_db(tmp_path / "s.duckdb", [tuple(row.values())])
    with pytest.raises(mod.AttachRefused, match="不是同一根 bar"):
        mod.run(DAY, capture, tmp_path / "r.json", db_path=db)
    assert names(db) == {"301686.SZ": None}
    assert not (tmp_path / "r.json").exists()


def test_refuses_null_name_from_a_non_bridge_source(tmp_path, capture):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL[:7] + ("eastmoney:snapshot",)])
    with pytest.raises(mod.AttachRefused, match="不是同花顺桥接行"):
        mod.run(DAY, capture, tmp_path / "r.json", db_path=db)
    assert names(db) == {"301686.SZ": None}


def test_refuses_when_a_null_row_has_no_quote(tmp_path):
    cap = make_capture(tmp_path / "cap", {"000001.SZ": quote("sz000001", NAMED)})
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL])
    with pytest.raises(mod.AttachRefused, match="捕获里没有"):
        mod.run(DAY, cap, tmp_path / "r.json", db_path=db)
    assert names(db) == {"301686.SZ": None}


def test_refuses_canonical_production_before_opening_anything(tmp_path, capture, monkeypatch):
    import market_feature_store.write_path as write_path

    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL])
    monkeypatch.setattr(write_path, "is_canonical_production", lambda path=None: True)
    with pytest.raises(mod.AttachRefused, match="canonical 生产库"):
        mod.run(DAY, capture, tmp_path / "r.json", db_path=db)
    assert names(db) == {"301686.SZ": None}


def test_capture_must_be_from_the_trade_date_and_untampered(tmp_path, capture):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL])
    with pytest.raises(ValueError):  # receipt target_date is 09-23, asked for 09-24
        mod.run(date(2026, 9, 24), capture, tmp_path / "r.json", db_path=db)
    (capture / "batch.raw").write_bytes((capture / "batch.raw").read_bytes() + b"\n")
    with pytest.raises(ValueError):  # raw bytes no longer match the sealed sha256
        mod.run(DAY, capture, tmp_path / "r2.json", db_path=db)
    assert names(db) == {"301686.SZ": None}


@pytest.mark.parametrize("mutation", [
    {"target_date": "2026-09-24"},          # receipt claims another day; quotes still dated DAY
    {"captured_code_count": 3},             # receipt scope disagrees with its own codes
])
def test_receipt_scope_defects_are_refused_even_when_quotes_parse(tmp_path, capture, mutation):
    receipt = json.loads((capture / "receipt.json").read_text())
    receipt.update(mutation)
    (capture / "receipt.json").write_text(json.dumps(receipt))
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL])
    with pytest.raises(ValueError):
        mod.run(DAY, capture, tmp_path / "r.json", db_path=db)
    assert names(db) == {"301686.SZ": None}


def test_pinned_receipt_hash_must_match(tmp_path, capture):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL])
    with pytest.raises(ValueError, match="pinned"):
        mod.run(DAY, capture, tmp_path / "r.json", db_path=db, expect_receipt_sha256="0" * 64)
    assert names(db) == {"301686.SZ": None}
    pinned = hashlib.sha256((capture / "receipt.json").read_bytes()).hexdigest()
    mod.run(DAY, capture, tmp_path / "r2.json", db_path=db, expect_receipt_sha256=pinned)
    assert names(db) == {"301686.SZ": "C中塑股份"}


def test_dry_run_and_existing_receipt_write_nothing(tmp_path, capture):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL])
    result = mod.run(DAY, capture, tmp_path / "dry.json", db_path=db, dry_run=True)
    assert result["applied"] is False and len(result["targets"]) == 1
    assert names(db) == {"301686.SZ": None}
    with pytest.raises(mod.AttachRefused, match="已存在"):
        mod.run(DAY, capture, tmp_path / "dry.json", db_path=db)
    assert names(db) == {"301686.SZ": None}


def test_cli_refusal_exit_code(tmp_path, capture, monkeypatch, capsys):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL[:7] + ("eastmoney:snapshot",)])
    import market_feature_store.db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", db)
    rc = mod.main(["--trade-date", DAY.isoformat(), "--capture-dir", str(capture),
                   "--receipt", str(tmp_path / "r.json")])
    assert rc == 2
    assert json.loads(capsys.readouterr().out)["attached"] is False
    assert names(db) == {"301686.SZ": None}


# ——— 过时名更正（合同 1 扩展，用户 2026-09-29 夜同意；--refresh-stale-names）———
# 09-29 实测：桥接行 46 / 5559 过时（摘帽、C / XD 前缀残留、截断、更名），格式差异 0 例。

STALE_ST = {1: "易联众", 2: "300096", 3: "9.23", 4: "9.02", 5: "9.1", 6: "2000",
            30: "20260923150003", 32: "2.33", 33: "9.3", 34: "9.0", 35: "9.23/2000/1859400", 38: "1", 40: "0"}
BRIDGED_STALE = (DAY, "300096.SZ", "ST易联众", 9.23, 9.02, 2.33, 0.0186, "hithink:daily-k-10d")


def test_refresh_is_off_by_default(tmp_path, capture):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL, BRIDGED_NAMED])
    result = mod.run(DAY, capture, tmp_path / "r.json", db_path=db)
    assert names(db)["000001.SZ"] == "平安银行"
    assert result["refresh_stale"] is False and result["refreshed"] == [] and result["refresh_planned"] == []


def test_refresh_corrects_stale_bridge_names_on_the_same_bar(tmp_path):
    cap = make_capture(tmp_path / "cap", {"301686.SZ": quote("sz301686", NEW_LISTING),
                                         "000001.SZ": quote("sz000001", NAMED | {1: "别的名字"}),
                                         "300096.SZ": quote("sz300096", STALE_ST)})
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL, BRIDGED_NAMED, BRIDGED_STALE])
    receipt = tmp_path / "r.json"
    result = mod.run(DAY, cap, receipt, db_path=db, refresh_stale=True)
    assert names(db) == {"000001.SZ": "别的名字", "300096.SZ": "易联众", "301686.SZ": "C中塑股份"}
    saved = json.loads(receipt.read_text())
    assert [(t["stock_ts_code"], t["stock_name_before"], t["stock_name"]) for t in saved["refreshed"]] == [
        ("000001.SZ", "平安银行", "别的名字"), ("300096.SZ", "ST易联众", "易联众")]
    assert all(t["name_source"] == "tencent:captured-dated-quote" for t in saved["refreshed"])
    assert saved["refresh_skipped"] == [] and result["applied"] is True
    assert "合同 1 扩展" in saved["decision_required"]


def test_refresh_skips_a_different_bar_without_blocking_others(tmp_path):
    cap = make_capture(tmp_path / "cap", {"301686.SZ": quote("sz301686", NEW_LISTING),
                                         "000001.SZ": quote("sz000001", NAMED | {1: "别的名字"}),
                                         "300096.SZ": quote("sz300096", STALE_ST)})
    wrong_bar = BRIDGED_STALE[:3] + (9.30,) + BRIDGED_STALE[4:]      # 收盘对不上：不是同一根 bar
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL, BRIDGED_NAMED, wrong_bar])
    result = mod.run(DAY, cap, tmp_path / "r.json", db_path=db, refresh_stale=True)
    assert names(db) == {"000001.SZ": "别的名字", "300096.SZ": "ST易联众", "301686.SZ": "C中塑股份"}
    [skip] = result["refresh_skipped"]
    assert skip["stock_ts_code"] == "300096.SZ" and "不是同一根 bar" in skip["reason"]


def test_refresh_never_touches_rows_from_other_sources(tmp_path, capture):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL, BRIDGED_NAMED[:7] + ("eastmoney:snapshot",)])
    result = mod.run(DAY, capture, tmp_path / "r.json", db_path=db, refresh_stale=True)
    assert names(db)["000001.SZ"] == "平安银行"
    assert result["refresh_planned"] == [] and result["refresh_skipped"] == []


def test_refresh_does_not_run_when_null_fill_refuses(tmp_path):
    # 补空名仍是全有或全无：它拒跑时整步不写，过时名也不改。
    cap = make_capture(tmp_path / "cap", {"000001.SZ": quote("sz000001", NAMED | {1: "别的名字"})})
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL, BRIDGED_NAMED])
    with pytest.raises(mod.AttachRefused, match="捕获里没有"):
        mod.run(DAY, cap, tmp_path / "r.json", db_path=db, refresh_stale=True)
    assert names(db) == {"000001.SZ": "平安银行", "301686.SZ": None}


def test_refresh_dry_run_plans_without_writing(tmp_path, capture):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL, BRIDGED_NAMED])
    result = mod.run(DAY, capture, tmp_path / "r.json", db_path=db, refresh_stale=True, dry_run=True)
    assert names(db) == {"000001.SZ": "平安银行", "301686.SZ": None}
    assert [t["stock_ts_code"] for t in result["refresh_planned"]] == ["000001.SZ"] and result["refreshed"] == []


def test_cli_flag_reaches_run(tmp_path, capture, monkeypatch, capsys):
    db = make_db(tmp_path / "s.duckdb", [BRIDGED_NULL, BRIDGED_NAMED])
    import market_feature_store.db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", db)
    assert mod.main(["--trade-date", DAY.isoformat(), "--capture-dir", str(capture),
                     "--receipt", str(tmp_path / "r.json"), "--refresh-stale-names"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["refreshed"] == [["000001.SZ", "平安银行", "别的名字"]]
    assert names(db)["000001.SZ"] == "别的名字"
