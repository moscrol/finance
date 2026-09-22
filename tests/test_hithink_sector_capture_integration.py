"""既有同步器 → 请求版本 → 真只读 CLI，所有输入均为合成数据。"""
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

from market_feature_store import cli, db, hithink_client
from market_feature_store.hithink_sector_capture import audit_capture
from market_feature_store.hithink_sector_preview import preview_sector_calculation
from market_feature_store.sync import sync_hithink_sector_kline as htb

DAY = date(2026, 9, 15)
CODE = "886053.TI"
SECOND = "885725.TI"


def _payload(rows):
    return {"code": 0, "data": {"item": rows}}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "isolated.duckdb"
    monkeypatch.setattr(htb, "DB_PATH", path)
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(htb, "_shanghai_now", lambda: datetime(2026, 9, 15, 18))

    def forbidden(*a, **k):
        pytest.fail("不得取 key/请求真实供应商")

    monkeypatch.setattr(hithink_client, "load_api_key", forbidden)
    monkeypatch.setattr(hithink_client, "get_json", forbidden)
    with duckdb.connect(str(path)) as con:
        db.init_db(con)
        con.executemany(
            "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, close, pct_chg, amount, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(day, code, 10, pct, amount, "hithink:daily-k-10d")
             for day, code, pct, amount in (
                 (DAY - timedelta(days=1), "600000.SH", 0, 500), (DAY, "600000.SH", 2, 600),
                 (DAY - timedelta(days=1), "600001.SH", 0, 50), (DAY, "600001.SH", -2, 100),
             )],
        )
    return path


def _getter(*, stock="600000.SH", codes=(CODE,), fail_at=None):
    def get_json(path, params=None):
        if path.endswith("ths-index-list"):
            if fail_at == params["tag"]:
                raise htb.HithinkSectorSyncError("synthetic failure")
            return _payload([{"thscode": code, "name": f"合成板块 {code}"} for code in codes])
        if path.endswith("historical"):
            if fail_at == "kline":
                raise htb.HithinkSectorSyncError("synthetic failure")
            return _payload([{
                "date_ms": hithink_client.shanghai_midnight_ms(day), "open_price": 100,
                "high_price": 101, "low_price": 98, "close_price": close,
                "volume": 1000, "turnover": 5000,
            } for day, close in ((DAY - timedelta(days=1), 100), (DAY, 99))])
        if path.endswith("ths-stock-list"):
            if fail_at == params["thscode"]:
                raise htb.HithinkSectorSyncError("synthetic failure")
            return _payload([{"thscode": stock, "ticker": stock[:6]}])
        pytest.fail(f"unexpected path {path}")
    return get_json


def _sync(path, **kwargs):
    kwargs.setdefault("get_json_fn", _getter())
    return htb.sync_hithink_sector_kline(mode="incremental", db_path=path, end_date=DAY, **kwargs)


def _preview(con, capture_id, **kwargs):
    kwargs.setdefault("pct_basis", "member_equal_weight")
    return preview_sector_calculation(
        con, DAY, member_date=DAY, category="cn_concept", capture_id=capture_id, **kwargs,
    )


def test_real_sync_records_scope_new_ids_overlap_and_old_version_replay(isolated):
    first = _sync(isolated)["capture_audit"]
    second = _sync(isolated, get_json_fn=_getter(stock="600001.SH"))["capture_audit"]
    assert first["capture_id"] != second["capture_id"]
    assert first["request_complete"] and first["provider_completeness"] == "unverified"
    with duckdb.connect(str(isolated)) as con:
        con.execute("DROP TABLE dim_sector_hithink; DROP TABLE fact_sector_constituent_hithink")
    before = hashlib.sha256(isolated.read_bytes()).hexdigest()
    with duckdb.connect(str(isolated), read_only=True) as con:
        old = _preview(con, first["capture_id"])
        new = _preview(con, second["capture_id"])
        assert old["rows"][0]["amount"] == 600 and old["rows"][0]["diff_ratio"] == 20
        assert old["double_red_codes"] == [CODE] and old["calculation_ready"]
        assert new["rows"][0]["amount"] == 100 and new["double_red_codes"] == []
        assert old["member_fingerprint"] != new["member_fingerprint"]
        assert old["request_complete"] and not old["production_ready"]
        index = _preview(con, first["capture_id"], pct_basis="index_close_return")
        assert index["rows"][0]["pct_chg"] == -1 and index["double_red_codes"] == []
        assert old["basis"]["members"] == "capture_version"
        with pytest.raises(ValueError, match="unknown capture_id"):
            _preview(con, "missing-capture")
    assert hashlib.sha256(isolated.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("fail_at,successes,pending,errors", [
    ("region", 2, 1, 1), ("kline", 4, 2, 0), (CODE, 5, 0, 1),
])
def test_sync_failure_retains_actual_prior_successes_and_unexecuted_plan(isolated, fail_at, successes, pending, errors):
    previous = _sync(isolated)["capture_audit"]["capture_id"]
    with pytest.raises(htb.HithinkSectorSyncError, match="synthetic failure"):
        _sync(isolated, get_json_fn=_getter(codes=(SECOND, CODE), fail_at=fail_at))
    with duckdb.connect(str(isolated), read_only=True) as con:
        failed_id = con.execute(
            "SELECT capture_id FROM ops_hithink_sector_capture WHERE status='failed'",
        ).fetchone()[0]
        report = audit_capture(con, failed_id)
        assert not report["request_complete"]
        assert sum(r["status"] == "success" for r in report["requests"]) == successes
        assert sum(r["status"] == "pending" for r in report["requests"]) == pending
        assert sum(r["status"] == "error" for r in report["requests"]) == errors
        assert audit_capture(con, previous)["request_complete"]
        with pytest.raises(ValueError, match="incomplete"):
            _preview(con, failed_id)


def test_failed_legacy_projection_does_not_seal_successful_requests_as_complete(isolated, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("synthetic projection failure")
    monkeypatch.setattr(htb, "_flush_constituents", broken)
    with pytest.raises(RuntimeError, match="projection failure"):
        _sync(isolated)
    with duckdb.connect(str(isolated), read_only=True) as con:
        capture_id = con.execute("SELECT capture_id FROM ops_hithink_sector_capture").fetchone()[0]
        report = audit_capture(con, capture_id)
        assert report["status"] == "failed" and not report["request_complete"]
        assert all(r["status"] == "success" for r in report["requests"])
        assert not _preview(con, None)["calculation_ready"]


def test_sync_cli_reports_catalog_scope_and_partial_returns_nonzero(isolated, monkeypatch, capsys):
    monkeypatch.setattr(htb, "get_json", _getter(codes=(SECOND, CODE)))
    args = ["sync-hithink-sector-kline", "--incremental", "--end-date", str(DAY)]
    assert cli.main([*args, "--skip-constituents"]) == 0
    output = capsys.readouterr().out
    assert "scope=catalog-only" in output and "provider_completeness=unverified" in output
    assert cli.main([*args, "--limit", "1"]) == 2
    assert "status=partial" in capsys.readouterr().out


def test_limit_and_resume_do_not_reduce_catalog_or_reuse_member_responses(isolated):
    full = _sync(isolated, get_json_fn=_getter(codes=(SECOND, CODE)))
    partial = _sync(isolated, get_json_fn=_getter(codes=(SECOND, CODE)), limit=1, resume=True)
    assert partial["capture_audit"]["status"] == "partial"
    with duckdb.connect(str(isolated), read_only=True) as con:
        report = audit_capture(con, partial["capture_audit"]["capture_id"])
        assert report["member_limit"] == 1 and not report["request_complete"]
        assert sum(r["kind"] == "members" for r in report["requests"]) == 2
        assert any(r["status"] == "skipped" and r["error_code"] == "limit" for r in report["requests"])
        assert audit_capture(con, full["capture_audit"]["capture_id"])["request_complete"]


@pytest.mark.parametrize("mode", ["valid", "unknown", "partial", "tampered", "missing-bars"])
def test_versioned_preview_real_cli_is_readonly_and_never_falls_back(isolated, mode):
    options = {"limit": 0} if mode == "partial" else {}
    capture_id = _sync(isolated, **options)["capture_audit"]["capture_id"]
    if mode == "unknown":
        capture_id = "unknown-id"
    if mode in ("tampered", "missing-bars"):
        with duckdb.connect(str(isolated)) as con:
            if mode == "tampered":
                con.execute("UPDATE ops_hithink_sector_request SET rows_sha256='tampered' WHERE kind='members'")
            else:
                con.execute("UPDATE fact_stock_daily SET amount=NULL WHERE trade_date=?", [DAY])
    before = hashlib.sha256(isolated.read_bytes()).hexdigest()
    result = subprocess.run(
        [sys.executable, "-m", "market_feature_store.cli", "hithink-sector-preview",
         "--trade-date", str(DAY), "--member-date", str(DAY), "--category", "cn_concept",
         "--pct-basis", "member_equal_weight", "--capture-id", capture_id],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "MARKET_FEATURE_STORE_DB": str(isolated)},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == (0 if mode == "valid" else 2), result.stderr
    report = json.loads(result.stdout)
    assert report["calculation_ready"] == (mode == "valid")
    assert not report["production_ready"]
    if mode != "valid":
        assert report["double_red_codes"] == []
    if mode in ("partial", "tampered"):
        assert report["request_complete"] is False
        assert report["gaps"] == [{"reason": "capture-not-ready"}]
        assert report["capture_audit"]["gaps"]
    assert hashlib.sha256(isolated.read_bytes()).hexdigest() == before


def test_capture_cross_midnight_keeps_actual_dates_and_rejects_mixed_day_preview(isolated, monkeypatch):
    now = [datetime(2026, 9, 14, 23, 59)]
    monkeypatch.setattr(htb, "_shanghai_now", lambda: now[0])
    getter = _getter(codes=(SECOND, CODE))

    def cross_midnight(path, params=None):
        if path.endswith("ths-stock-list") and params["thscode"] == CODE:
            now[0] = datetime(2026, 9, 15, 0, 1)
        return getter(path, params)

    capture_id = _sync(isolated, get_json_fn=cross_midnight)["capture_audit"]["capture_id"]
    with duckdb.connect(str(isolated), read_only=True) as con:
        audit = audit_capture(con, capture_id)
        assert audit["request_complete"] and audit["capture_dates"] == ["2026-09-14", "2026-09-15"]
        result = _preview(con, capture_id, max_member_age_days=1)
        assert not result["calculation_ready"] and result["request_complete"]
        assert result["double_red_codes"] == []  # 请求齐全 ≠ 同日名单可算


def test_failed_finalization_preserves_first_error_and_does_not_print_it(isolated, monkeypatch, capsys):
    from market_feature_store.hithink_sector_capture import SectorCapture

    def broken(*a, **k):
        raise RuntimeError("secondary-secret-marker")
    monkeypatch.setattr(SectorCapture, "fail", broken)
    with pytest.raises(htb.HithinkSectorSyncError, match="synthetic failure"):
        _sync(isolated, get_json_fn=_getter(fail_at="cn_concept"))
    output = capsys.readouterr().out
    assert "audit-finalization-failed" in output and "secondary-secret-marker" not in output
    with duckdb.connect(str(isolated), read_only=True) as con:
        capture_id = con.execute("SELECT capture_id FROM ops_hithink_sector_capture").fetchone()[0]
        assert not audit_capture(con, capture_id)["request_complete"]


def test_clock_reversal_blocks_unlimited_sync_and_legacy_step_is_not_green(isolated, monkeypatch):
    from market_feature_store.sync.sync_daily_full import _run_step, run_hithink_sector_kline_step

    now = [datetime(2026, 9, 15, 18)]
    monkeypatch.setattr(htb, "_shanghai_now", lambda: now[0])
    getter = _getter()

    def reversed_clock(path, params=None):
        if path.endswith("historical"):
            now[0] = datetime(2026, 9, 15, 17)
        return getter(path, params)

    monkeypatch.setattr(htb, "get_json", reversed_clock)
    monkeypatch.setattr(htb, "skip_reason_if_no_key", lambda: None)
    result = _run_step("hithink", run_hithink_sector_kline_step, str(DAY))
    assert not result["ok"] and "请求审计未通过" in result["error"]
    with duckdb.connect(str(isolated), read_only=True) as con:
        assert con.execute("SELECT status FROM ops_hithink_sector_capture").fetchone() == ("partial",)


@pytest.mark.parametrize("pct_basis", ["member_equal_weight", "index_close_return"])
def test_versioned_preview_binds_capture_and_prices_to_one_snapshot(isolated, pct_basis):
    capture_id = _sync(isolated)["capture_audit"]["capture_id"]
    with duckdb.connect(str(isolated)) as reader, duckdb.connect(str(isolated)) as writer:
        before = _preview(reader, capture_id, pct_basis=pct_basis)

        class ConcurrentCommit:
            fired = False

            def execute(self, sql, *args):
                cursor = reader.execute(sql, *args)
                if "FROM ops_hithink_sector_request" in sql and not self.fired:
                    self.fired = True
                    writer.execute("BEGIN TRANSACTION")
                    writer.execute("UPDATE fact_stock_daily SET amount=amount*2 WHERE trade_date=?", [DAY])
                    writer.execute("UPDATE fact_sector_kline_daily SET close=105 WHERE trade_date=?", [DAY])
                    writer.execute("COMMIT")
                return cursor

        racing = ConcurrentCommit()
        during = _preview(racing, capture_id, pct_basis=pct_basis)
        after = _preview(reader, capture_id, pct_basis=pct_basis)
        assert racing.fired
        assert during == before
        assert after["rows"][0]["amount"] == 1200
        assert after["rows"][0]["pct_chg"] == (2 if pct_basis == "member_equal_weight" else 5)
        assert after["request_complete"] and not after["production_ready"]


def test_preview_does_not_reread_responses_after_validation(isolated):
    capture_id = _sync(isolated)["capture_audit"]["capture_id"]
    with duckdb.connect(str(isolated), read_only=True) as con:
        class OnlyOneResponseRead:
            reads = 0

            def execute(self, sql, *args):
                if "FROM ops_hithink_sector_request" in sql:
                    self.reads += 1
                    assert self.reads == 1, "验证后必须消费已验证行，不二次读取可能变化的行"
                return con.execute(sql, *args)
        result = _preview(OnlyOneResponseRead(), capture_id)
        assert result["calculation_ready"]
