"""目录/成员逻辑请求审计：合成供应商响应与临时库，禁止真实 key/外呼。"""
from datetime import date, datetime
import json

import duckdb
import pytest

from market_feature_store.db import init_db
from market_feature_store.sync import sync_hithink_sector_kline as htb

DAY = date(2026, 9, 15)
NOW = datetime(2026, 9, 15, 18)
CODE = "886053.TI"


@pytest.fixture
def con():
    with duckdb.connect(":memory:") as c:
        init_db(c)
        yield c


def _payload(items):
    return {"code": 0, "data": {"item": items}}


def _catalog():
    return _payload([{"thscode": CODE, "name": "BC电池"}])


@pytest.mark.parametrize("payload", [
    {}, {"code": 4001, "data": {"item": [{"thscode": CODE, "name": "BC"}]}},
    _payload([]), _payload([None]), _payload([{}]), _payload("bad"),
    _payload([{"thscode": CODE, "name": "BC"}] * 2),
    _payload([{"thscode": "not-a-code", "name": "BC"}]),
    _payload([{"thscode": CODE, "name": " "}]),
    {"code": False, "data": {"item": [{"thscode": CODE, "name": "BC"}]}},
    {"code": 0, "data": {"item": [], "items": [{"thscode": CODE, "name": "BC"}]}},
])
def test_catalog_rejects_empty_ambiguous_or_malformed_response(payload):
    with pytest.raises(htb.HithinkSectorSyncError):
        htb.fetch_catalog("cn_concept", lambda *a, **k: payload)


def _start(con, *, include_members=True, limit=None, clock=lambda: NOW):
    from market_feature_store.hithink_sector_capture import SectorCapture

    return SectorCapture.start(
        con, requested_end_date=date(2026, 9, 8), include_members=include_members,
        member_limit=limit, clock=clock,
    )


def _capture_catalogs(capture):
    for tag in htb.CATALOG_TAGS:
        capture.request("catalog", tag, lambda tag=tag: htb.fetch_catalog(tag, lambda *a, **k: _catalog()))


def _members(code=CODE, stocks=("600000.SH",)):
    return htb.fetch_constituents(code, lambda *a, **k: _payload([
        {"thscode": stock, "ticker": stock[:6]} for stock in stocks
    ]))


def _finish(con, stocks=("600000.SH",), clock=lambda: NOW):
    capture = _start(con, clock=clock)
    _capture_catalogs(capture)
    codes = capture.plan_members()
    assert codes == [CODE]  # 跨标签只有一个成员请求，目录标签自身完整保留
    for code in codes:
        capture.request("members", code, lambda: _members(stocks=stocks))
    report = capture.finish()
    return capture, report


def _audit(con, capture_id):
    from market_feature_store.hithink_sector_capture import audit_capture

    return audit_capture(con, capture_id)


def test_capture_is_planned_before_io_and_completed_not_provider_verified(con):
    capture = _start(con)
    assert con.execute(
        "SELECT request_key, status FROM ops_hithink_sector_request ORDER BY request_key"
    ).fetchall() == sorted((tag, "pending") for tag in htb.CATALOG_TAGS)

    def get_rows():
        assert con.execute(
            "SELECT status FROM ops_hithink_sector_request WHERE request_key='cn_concept'"
        ).fetchone() == ("requesting",)
        return htb.fetch_catalog("cn_concept", lambda *a, **k: _catalog())

    capture.request("catalog", "cn_concept", get_rows)
    for tag in htb.CATALOG_TAGS[1:]:
        capture.request("catalog", tag, lambda tag=tag: htb.fetch_catalog(tag, lambda *a, **k: _catalog()))
    assert capture.plan_members() == [CODE]
    capture.request("members", CODE, _members)
    report = capture.finish()
    assert report["status"] == "complete" and report["request_complete"]
    assert report["provider_completeness"] == "unverified"
    assert report["scope"] == "catalog-and-members"
    assert report["requested_end_date"] == "2026-09-08"
    assert report["capture_dates"] == [str(DAY)]
    assert len(report["requests"]) == 5
    assert report["requests"][0]["rows_sha256"]


def test_version_preserves_overlap_members_and_does_not_depend_on_latest_tables(con):
    from market_feature_store.hithink_sector_capture import capture_inputs

    first, _ = _finish(con)
    second, _ = _finish(con, stocks=("600001.SH",), clock=lambda: NOW.replace(hour=19))
    con.execute("DELETE FROM dim_sector_hithink; DELETE FROM fact_sector_constituent_hithink")
    for category in htb.CATALOG_TAGS:
        sectors, members, audit = capture_inputs(con, first.capture_id, category)
        assert sectors[0][0] == CODE and members[0][1] == "600000.SH"
        assert audit["request_complete"]
        assert capture_inputs(con, second.capture_id, category)[1][0][1] == "600001.SH"
    assert first.capture_id != second.capture_id


def test_terminal_capture_and_request_are_not_overwritten(con):
    capture, before = _finish(con)
    with pytest.raises(ValueError):
        capture.request("members", CODE, lambda: pytest.fail("already terminal"))
    with pytest.raises(ValueError):
        capture.plan_members()
    with pytest.raises(ValueError):
        capture.finish()
    assert _audit(con, capture.capture_id) == before


def test_unplanned_request_is_rejected_before_io(con):
    capture = _start(con)
    with pytest.raises(ValueError):
        capture.request("members", CODE, lambda: pytest.fail("unplanned IO"))
    with pytest.raises(ValueError):
        capture.request("catalog", "bogus", lambda: pytest.fail("unplanned IO"))


def test_error_keeps_prior_receipts_and_never_stores_exception_text(con):
    capture = _start(con)
    _capture_catalogs(capture)
    capture.plan_members()

    def broken():
        raise RuntimeError("secret-marker-do-not-log")

    with pytest.raises(RuntimeError):
        capture.request("members", CODE, broken)
    report = capture.fail()
    assert report["status"] == "failed" and not report["request_complete"]
    encoded = json.dumps(report, ensure_ascii=False)
    assert "secret-marker" not in encoded
    assert report["requests"][-1]["error_code"] == "request-error"
    assert "secret-marker" not in str(con.execute("SELECT * FROM ops_hithink_sector_request").fetchall())
    assert len([r for r in report["requests"] if r["status"] == "success"]) == 4


def test_partial_scope_and_catalog_only_never_supply_member_inputs(con):
    from market_feature_store.hithink_sector_capture import capture_inputs

    capture = _start(con, include_members=False)
    _capture_catalogs(capture)
    report = capture.finish()
    assert report["request_complete"] and report["scope"] == "catalog-only"
    with pytest.raises(ValueError):
        capture_inputs(con, capture.capture_id, "cn_concept")


def test_running_or_missing_requests_cannot_be_promoted_by_status_alone(con):
    capture, _ = _finish(con)
    con.execute("DELETE FROM ops_hithink_sector_request WHERE kind='members'")
    report = _audit(con, capture.capture_id)
    assert report["status"] == "complete" and not report["request_complete"]
    assert report["gaps"]


@pytest.mark.parametrize("sql", [
    "UPDATE ops_hithink_sector_request SET row_count=10 WHERE kind='members'",
    "UPDATE ops_hithink_sector_request SET rows_sha256='wrong' WHERE kind='members'",
    "UPDATE ops_hithink_sector_request SET normalized_rows='[]' WHERE kind='members'",
    "UPDATE ops_hithink_sector_request SET received_at=NULL WHERE kind='members'",
    "UPDATE ops_hithink_sector_request SET received_at='2026-09-16T18:00:00+08:00' WHERE kind='members'",
    "UPDATE ops_hithink_sector_capture SET members_planned=false",
])
def test_audit_revalidates_rows_hash_time_and_manifest(con, sql):
    capture, _ = _finish(con)
    con.execute(sql)
    assert not _audit(con, capture.capture_id)["request_complete"]


def test_request_does_not_store_noncontract_fields(con):
    capture = _start(con)
    for tag in htb.CATALOG_TAGS:
        def rows(tag=tag):
            payload = _catalog()
            payload["debug_key"] = "secret-marker"
            payload["data"]["item"][0]["provider_debug"] = "secret-marker"
            return htb.fetch_catalog(tag, lambda *a, **k: payload)
        capture.request("catalog", tag, rows)
    capture.plan_members()
    capture.request("members", CODE, _members)
    capture.finish()
    assert "secret-marker" not in str(con.execute("SELECT * FROM ops_hithink_sector_request").fetchall())


def test_member_plan_keeps_unrequested_limit_gaps(con):
    capture = _start(con, limit=1)
    for tag in htb.CATALOG_TAGS:
        payload = _payload([{"thscode": code, "name": code} for code in ("885725.TI", CODE)])
        capture.request("catalog", tag, lambda tag=tag: htb.fetch_catalog(tag, lambda *a, **k: payload))
    assert capture.plan_members() == ["885725.TI"]
    capture.request("members", "885725.TI", lambda: _members(code="885725.TI"))
    report = capture.finish()
    assert report["status"] == "partial" and not report["request_complete"]
    skipped = [r for r in report["requests"] if r["status"] == "skipped"]
    assert len(skipped) == 1 and skipped[0]["request_key"] == CODE


def test_incomplete_catalog_cannot_schedule_members_or_claim_complete(con):
    capture = _start(con)
    capture.request("catalog", "cn_concept", lambda: htb.fetch_catalog("cn_concept", lambda *a, **k: _catalog()))
    with pytest.raises(ValueError):
        capture.plan_members()
    report = capture.finish()
    assert not report["request_complete"] and report["status"] == "partial"


def test_cannot_seal_or_retry_inflight_request(con):
    capture = _start(con)

    def fetching():
        with pytest.raises(ValueError, match="active request"):
            capture.finish()
        with pytest.raises(ValueError):
            capture.request("catalog", "cn_concept", lambda: pytest.fail("duplicate IO"))
        return htb.fetch_catalog("cn_concept", lambda *a, **k: _catalog())

    capture.request("catalog", "cn_concept", fetching)
    report = _audit(con, capture.capture_id)
    assert report["status"] == "running" and not report["request_complete"]


def test_interrupted_process_leaves_unfinished_not_fake_success(con):
    capture = _start(con)

    def interrupted():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        capture.request("catalog", "cn_concept", interrupted)
    report = _audit(con, capture.capture_id)
    assert not report["request_complete"] and report["status"] == "running"
    assert report["requests"][0]["status"] == "requesting"
    assert report["requests"][0]["received_at"] is None


def test_same_snapshot_reads_across_database_timezones(con):
    capture, expected = _finish(con)
    for timezone in ("UTC", "America/New_York", "Asia/Shanghai"):
        con.execute("SET TimeZone = ?", [timezone])
        assert _audit(con, capture.capture_id) == expected
    assert expected["requests"][0]["received_at"] == "2026-09-15T18:00:00+08:00"


def test_future_contract_is_not_silently_interpreted_as_current(con):
    capture, _ = _finish(con)
    con.execute("UPDATE ops_hithink_sector_capture SET contract_version='future-version'")
    report = _audit(con, capture.capture_id)
    assert not report["request_complete"] and "unsupported-contract-version" in report["gaps"]


def test_clock_reversal_is_partial_not_complete(con):
    now = [NOW]
    capture = _start(con, clock=lambda: now[0])
    _capture_catalogs(capture)
    capture.plan_members()
    capture.request("members", CODE, _members)
    now[0] = NOW.replace(hour=17)
    report = capture.finish()
    assert report["status"] == "partial" and not report["request_complete"]


def test_rows_and_hash_changed_together_still_break_sealed_manifest(con):
    from market_feature_store.hithink_sector_capture import _hash, _json

    capture, _ = _finish(con)
    forged = [{"thscode": "600001.SH", "ticker": "600001"}]
    con.execute(
        "UPDATE ops_hithink_sector_request SET normalized_rows=?, rows_sha256=? WHERE kind='members'",
        [_json(forged), _hash(forged)],
    )
    report = _audit(con, capture.capture_id)
    assert not report["request_complete"] and "capture-manifest-mismatch" in report["gaps"]


@pytest.mark.parametrize("items", [
    [{"thscode": "bad"}], [{"thscode": "600000.SH", "ticker": "600001"}],
    [{"thscode": "600000.SH"}, {"thscode": "600000.sh "}],
])
def test_invalid_member_code_or_ticker_cannot_be_saved(items):
    with pytest.raises(htb.HithinkSectorSyncError):
        htb.fetch_constituents(CODE, lambda *a, **k: _payload(items))


def test_capture_setup_and_member_plan_are_atomic(con):
    class FailingInsert:
        def __init__(self, target):
            self.target = target

        def execute(self, *args, **kwargs):
            return con.execute(*args, **kwargs)

        def executemany(self, sql, parameters):
            parameters = list(parameters)
            con.executemany(sql, parameters[:1])
            raise RuntimeError(self.target)

    with pytest.raises(RuntimeError, match="setup"):
        _start(FailingInsert("setup"))
    assert con.execute("SELECT count(*) FROM ops_hithink_sector_capture").fetchone() == (0,)
    assert con.execute("SELECT count(*) FROM ops_hithink_sector_request").fetchone() == (0,)
    capture = _start(con)
    _capture_catalogs(capture)
    capture.con = FailingInsert("plan")
    with pytest.raises(RuntimeError, match="plan"):
        capture.plan_members()
    assert con.execute("SELECT count(*) FROM ops_hithink_sector_request WHERE kind='members'").fetchone() == (0,)
    assert con.execute("SELECT members_planned FROM ops_hithink_sector_capture").fetchone() == (False,)


def test_parallel_writer_conflicts_on_capture_head_and_cannot_seal_it(con):
    from market_feature_store.hithink_sector_capture import SectorCapture

    capture = _start(con)
    other = con.cursor()  # 同一 DuckDB 的独立事务连接，不共享 cursor 事务状态。
    try:
        contender = SectorCapture(other, capture.capture_id, lambda: NOW)
        with capture._writing():
            with pytest.raises(duckdb.TransactionException):
                contender.finish()
        assert _audit(con, capture.capture_id)["status"] == "running"
        contender.fail()
        with pytest.raises(ValueError, match="not running"):
            capture.request("catalog", "cn_concept", lambda: pytest.fail("terminal IO"))
    finally:
        other.close()


def test_reservation_committed_and_no_transaction_held_across_fetch(con):
    capture = _start(con)
    other = con.cursor()
    try:
        def fetching():
            assert other.execute(
                "SELECT status FROM ops_hithink_sector_request WHERE request_key='cn_concept'"
            ).fetchone() == ("requesting",)
            # 独立连接能更新批次头，说明慢 IO 期间不持有写事务。
            other.execute("UPDATE ops_hithink_sector_capture SET status=status")
            return htb.fetch_catalog("cn_concept", lambda *a, **k: _catalog())
        capture.request("catalog", "cn_concept", fetching)
    finally:
        other.close()
