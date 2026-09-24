"""同花顺官方 dump 入库（工单 #41 A）。夹具自造小 parquet，不碰真 key、不读 /tmp 大文件。"""

from __future__ import annotations

import email.message
import inspect
import io
import json
import urllib.error
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
import duckdb
import pytest

from market_feature_store import hithink_client
from market_feature_store.hithink_client import (
    HithinkAPIError,
    HithinkRateLimitError,
    get_json,
    ms_to_shanghai_date,
    shanghai_midnight_ms,
)
from market_feature_store.sync import sync_daily_full
from market_feature_store.sync import sync_hithink_stock_daily as htk


DAILY_DDL = """
CREATE TABLE fact_stock_daily_hithink (
    trade_date DATE,
    stock_ts_code TEXT,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    turnover DOUBLE,
    adjusted TEXT,
    source TEXT,
    updated_at TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code)
)
"""
ADJ_DDL = """
CREATE TABLE fact_stock_adjustment_hithink (
    stock_ts_code TEXT,
    ex_date DATE,
    dividend_per_share DOUBLE,
    per_share_bonus DOUBLE,
    allotment_ratio DOUBLE,
    allotment_price DOUBLE,
    currency TEXT,
    source TEXT,
    updated_at TIMESTAMP,
    PRIMARY KEY (stock_ts_code, ex_date)
)
"""
OLD_DAILY_DDL = """
CREATE TABLE fact_stock_daily (
    trade_date DATE,
    stock_ts_code TEXT,
    close DOUBLE,
    PRIMARY KEY (trade_date, stock_ts_code)
)
"""


def _write_daily_parquet(path: Path, rows: list[tuple]) -> None:
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE t (
                thscode VARCHAR, currency VARCHAR, interval VARCHAR, adjusted VARCHAR,
                date_ms BIGINT, open_price DOUBLE, high_price DOUBLE, low_price DOUBLE,
                close_price DOUBLE, volume DOUBLE, turnover DOUBLE
            )
            """
        )
        con.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")
    finally:
        con.close()


def _write_adj_parquet(path: Path, rows: list[tuple]) -> None:
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE t (
                thscode VARCHAR, ticker VARCHAR, ex_date_ms BIGINT,
                dividend_per_share DOUBLE, per_share_bonus DOUBLE,
                allotment_ratio DOUBLE, allotment_price DOUBLE, currency VARCHAR
            )
            """
        )
        con.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?)", rows)
        con.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")
    finally:
        con.close()


def _empty_db(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(DAILY_DDL)
        con.execute(ADJ_DDL)
        con.execute(OLD_DAILY_DDL)
    finally:
        con.close()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "mfs.duckdb"
    _empty_db(path)
    return path


def test_date_ms_formula_is_shanghai_midnight() -> None:
    """工单指定公式：1473264000000 → 2016-09-08，与客户端同一口径。"""

    assert shanghai_midnight_ms(date(2016, 9, 8)) == 1473264000000
    assert ms_to_shanghai_date(1473264000000) == date(2016, 9, 8)
    con = duckdb.connect(":memory:")
    try:
        row = con.execute(
            f"SELECT {htk.TRADE_DATE_SQL} FROM (SELECT 1473264000000::BIGINT AS date_ms)"
        ).fetchone()
        assert row[0] == date(2016, 9, 8)
    finally:
        con.close()


def test_dump_columns_are_all_in_insert_sql() -> None:
    """请求了就必须接住：官方 dump 列必须出现在入库 SQL 里。"""

    daily_sql = htk.INSERT_DAILY_SQL
    for col in htk.DUMP_DAILY_COLUMNS:
        assert col in daily_sql, col
    adj_sql = htk.INSERT_ADJ_SQL
    for col in htk.DUMP_ADJ_COLUMNS:
        assert col in adj_sql, col


def test_ingest_upsert_and_fingerprint(db_path: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(htk, "init_db", lambda con: None)
    parquet = tmp_path / "daily.parquet"
    adj = tmp_path / "adj.parquet"
    d0 = 1473264000000
    d1 = shanghai_midnight_ms(date(2026, 9, 2))
    _write_daily_parquet(
        parquet,
        [
            (
                "600000.SH", "CNY", "1d", "none", d0,
                10.0, 11.0, 9.0, 10.5, 1000.0, 1.05e7,
            ),
            (
                "000001.SZ", "CNY", "1d", "none", d0,
                8.0, 8.5, 7.5, 8.1, 2000.0, 1.6e7,
            ),
            (
                "600000.SH", "CNY", "1d", "none", d1,
                12.0, 12.5, 11.5, 12.2, 1100.0, 1.3e7,
            ),
        ],
    )
    _write_adj_parquet(
        adj,
        [
            (
                "600000.SH", "600000", 1473264000000,
                0.1, 0.0, 0.0, 0.0, "CNY",
            ),
        ],
    )
    first = htk.sync_hithink_stock_daily(
        mode="full",
        parquet=parquet,
        adjustments_parquet=adj,
        db_path=db_path,
    )
    assert first["daily"]["rows"] == 3
    assert first["daily"]["codes"] == 2
    assert first["daily"]["date_min"] == "2016-09-08"
    assert first["daily"]["ohlc_nulls"] == 0
    assert first["adjustments"]["rows"] == 1
    assert first["source"] == "hithink:daily-k"

    # 同一只同一天改 close，UPSERT 覆盖
    _write_daily_parquet(
        parquet,
        [
            (
                "600000.SH", "CNY", "1d", "none", d0,
                10.0, 11.0, 9.0, 10.8, 1000.0, 1.05e7,
            ),
            (
                "000001.SZ", "CNY", "1d", "none", d0,
                8.0, 8.5, 7.5, 8.1, 2000.0, 1.6e7,
            ),
            (
                "600000.SH", "CNY", "1d", "none", d1,
                12.0, 12.5, 11.5, 12.2, 1100.0, 1.3e7,
            ),
        ],
    )
    second = htk.sync_hithink_stock_daily(
        mode="incremental",
        parquet=parquet,
        adjustments_parquet=adj,
        db_path=db_path,
    )
    assert second["source"] == "hithink:daily-k-10d"
    assert second["daily"]["rows"] == 3
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        close = con.execute(
            "SELECT close FROM fact_stock_daily_hithink "
            "WHERE stock_ts_code='600000.SH' AND trade_date='2016-09-08'"
        ).fetchone()[0]
        source = con.execute(
            "SELECT source FROM fact_stock_daily_hithink "
            "WHERE stock_ts_code='600000.SH' AND trade_date='2016-09-08'"
        ).fetchone()[0]
    finally:
        con.close()
    assert close == pytest.approx(10.8)
    assert source == "hithink:daily-k-10d"

    # 同一份 parquet 再灌一次，指纹不变
    again = htk.sync_hithink_stock_daily(
        mode="incremental",
        parquet=parquet,
        adjustments_parquet=adj,
        db_path=db_path,
    )
    assert again["fingerprint"] == second["fingerprint"]
    assert again["adjustments_fingerprint"] == second["adjustments_fingerprint"]


def test_compare_close_rate(db_path: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(htk, "init_db", lambda con: None)
    parquet = tmp_path / "daily.parquet"
    d1 = shanghai_midnight_ms(date(2026, 9, 2))
    _write_daily_parquet(
        parquet,
        [
            (
                "600000.SH", "CNY", "1d", "none", d1,
                12.0, 12.5, 11.5, 12.2, 1100.0, 1.3e7,
            ),
            (
                "000001.SZ", "CNY", "1d", "none", d1,
                8.0, 8.5, 7.5, 8.1, 2000.0, 1.6e7,
            ),
        ],
    )
    con = duckdb.connect(str(db_path))
    try:
        con.executemany(
            "INSERT INTO fact_stock_daily VALUES (?,?,?)",
            [
                ("2026-09-02", "600000.SH", 12.2),
                ("2026-09-02", "000001.SZ", 8.1),
                ("2026-09-02", "000002.SZ", 9.0),
            ],
        )
    finally:
        con.close()
    stats = htk.sync_hithink_stock_daily(
        mode="full",
        parquet=parquet,
        skip_adjustments=True,
        db_path=db_path,
        compare_days=20,
    )
    compare = stats["compare"]
    assert compare["matched"] == 2
    assert compare["compared"] == 2
    assert compare["rate"] == 1.0
    assert compare["old_only"] == 1
    assert compare["new_only"] == 0


def test_skip_without_key(monkeypatch) -> None:
    monkeypatch.setattr(htk, "has_api_key", lambda: False)
    assert htk.skip_reason_if_no_key() == "no-key"


def test_daily_full_schedules_hithink_after_stock_daily() -> None:
    src = inspect.getsource(sync_daily_full.run_daily_update)
    assert "sync-hithink-stock-daily" in src
    assert src.index("sync-stock-daily") < src.index("sync-hithink-stock-daily")
    assert "run_hithink_stock_daily_step" in sync_daily_full.run_daily_update.__code__.co_names


def test_daily_full_step_skips_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "market_feature_store.sync.sync_hithink_stock_daily.skip_reason_if_no_key",
        lambda: "no-key",
    )
    result = sync_daily_full.run_hithink_stock_daily_step()
    assert result == {"skipped": True, "reason": "no-key"}


def test_key_not_in_api_error(monkeypatch) -> None:
    secret = "test-key-must-not-leak-xyz"

    class _Resp:
        status = 200

        def read(self):
            return json.dumps({"code": 2003, "message": "auth failed"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setenv("HITHINK_FINANCE_API_KEY", secret)
    monkeypatch.setattr(hithink_client, "_last_request_monotonic", 0.0)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    with pytest.raises(HithinkAPIError) as excinfo:
        get_json("/api/meta/tickers/search", gap_seconds=0, retries=1)
    text = f"{excinfo.value!s}{excinfo.value!r}"
    assert secret not in text


def test_4001_retries_then_ok(monkeypatch) -> None:
    secret = "test-key-must-not-leak-xyz"
    calls = {"n": 0}

    class _Resp:
        def __init__(self, payload: dict):
            self.status = 200
            self._raw = json.dumps(payload).encode()

        def read(self):
            return self._raw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _urlopen(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp({"code": 4001, "message": "rate limited"})
        return _Resp({"code": 0, "data": {"ok": True}})

    monkeypatch.setenv("HITHINK_FINANCE_API_KEY", secret)
    monkeypatch.setattr(hithink_client, "_last_request_monotonic", 0.0)
    monkeypatch.setattr(hithink_client.time, "sleep", lambda *_: None)
    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    payload = get_json("/api/dump/market-dumps/daily-k/download-url", gap_seconds=0)
    assert payload["code"] == 0
    assert calls["n"] == 2
    assert secret not in json.dumps(payload)


# --- 全局限流（HTTP 429）退避 -------------------------------------------------
# 载荷形状取自 2026-09-21 10:24 盘中实测（~/.finance-runtime/
# hithink-anomaly-sample-20260921T1020/valuation-probe.log）：HTTP 429 +
# 业务码 429，正文是合法 JSON，头里没有 Retry-After。修复前 429 既不匹配
# code==0 也不匹配 4001，会在首个请求处直接抛错、中止整轮采集。

_LIMIT_BODY = json.dumps(
    {"code": 429, "message": "Global request rate limit exceeded"}
).encode()
_LIMIT_HEADERS = {
    "Date": "Mon, 21 Sep 2026 02:24:06 GMT",
    "Content-Type": "application/json",
    "Server": "Stargate",
}


def _headers(mapping):
    msg = email.message.Message()
    for key, value in (mapping or {}).items():
        msg[key] = value
    return msg


def _limit_error(body=_LIMIT_BODY, *, status=429, headers=_LIMIT_HEADERS):
    return urllib.error.HTTPError(
        "https://fuyao.aicubes.cn/api/x",
        status,
        "Too Many Requests",
        _headers(headers),
        io.BytesIO(body),
    )


class _OkResp:
    def __init__(self, payload):
        self.status = 200
        self.headers = _headers({"Content-Type": "application/json"})
        self._raw = json.dumps(payload).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _arm(monkeypatch, responses):
    """按序回放 responses；元素是 Exception 就 raise。返回 (calls, slept)。"""

    calls = {"n": 0}
    slept: list[float] = []
    elapsed = [0.0]

    def sleep(seconds):
        slept.append(seconds)
        elapsed[0] += seconds

    def _urlopen(*a, **k):
        index = calls["n"]
        calls["n"] += 1
        item = responses[min(index, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setenv("HITHINK_FINANCE_API_KEY", "test-key-must-not-leak-xyz")
    monkeypatch.delenv(hithink_client.ENV_RATE_LIMIT_BUDGET, raising=False)
    monkeypatch.setattr(hithink_client, "_last_request_monotonic", 0.0)
    monkeypatch.setattr(hithink_client.time, "sleep", sleep)
    monkeypatch.setattr(hithink_client.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    return calls, slept


def test_http_429_retries_then_ok(monkeypatch) -> None:
    calls, slept = _arm(
        monkeypatch,
        [_limit_error(), _limit_error(), _OkResp({"code": 0, "data": {"item": []}})],
    )
    payload = get_json("/api/a-share/valuations/snapshot", gap_seconds=0)
    assert payload["code"] == 0
    assert calls["n"] == 3
    assert slept == [0.8, 1.6]


def test_http_429_with_non_json_body_retries(monkeypatch) -> None:
    """网关返 HTML 时也算限流，不能误报成「非 JSON 响应」。"""

    calls, _ = _arm(
        monkeypatch,
        [
            _limit_error(
                b"<html><body>429 Too Many Requests</body></html>",
                headers={"Content-Type": "text/html"},
            ),
            _OkResp({"code": 0, "data": {"item": []}}),
        ],
    )
    payload = get_json("/api/a-share/anomaly-analysis-list", gap_seconds=0)
    assert payload["code"] == 0
    assert calls["n"] == 2


def test_retry_after_seconds_header_wins_over_backoff(monkeypatch) -> None:
    headers = dict(_LIMIT_HEADERS, **{"Retry-After": "12"})
    _, slept = _arm(
        monkeypatch,
        [
            _limit_error(headers=headers),
            _OkResp({"code": 0, "data": {"item": []}}),
        ],
    )
    get_json("/api/a-share/valuations/snapshot", gap_seconds=0)
    assert slept == [12.0]


def test_retry_after_http_date_header_is_parsed(monkeypatch) -> None:
    when = datetime.now(tz=timezone.utc) + timedelta(seconds=30)
    headers = dict(_LIMIT_HEADERS, **{"Retry-After": format_datetime(when, usegmt=True)})
    _, slept = _arm(
        monkeypatch,
        [
            _limit_error(headers=headers),
            _OkResp({"code": 0, "data": {"item": []}}),
        ],
    )
    get_json("/api/a-share/valuations/snapshot", gap_seconds=0)
    assert len(slept) == 1
    assert 20.0 < slept[0] <= 30.0


def test_retry_after_is_capped(monkeypatch) -> None:
    """上游给个离谱的 Retry-After 也不能让夜跑挂死。"""

    headers = dict(_LIMIT_HEADERS, **{"Retry-After": "86400"})
    _, slept = _arm(
        monkeypatch,
        [
            _limit_error(headers=headers),
            _OkResp({"code": 0, "data": {"item": []}}),
        ],
    )
    get_json("/api/a-share/valuations/snapshot", gap_seconds=0, rate_limit_budget_seconds=600)
    assert slept == [hithink_client.MAX_RATE_LIMIT_SLEEP_SECONDS]


def test_rate_limit_budget_exhausts_and_fails_closed(monkeypatch) -> None:
    calls, slept = _arm(monkeypatch, [_limit_error()])
    with pytest.raises(HithinkRateLimitError) as excinfo:
        get_json(
            "/api/a-share/valuations/snapshot",
            gap_seconds=0,
            rate_limit_budget_seconds=5,
        )
    text = f"{excinfo.value!s}{excinfo.value!r}"
    assert "限流退避耗尽" in text
    assert "test-key-must-not-leak-xyz" not in text
    assert sum(slept) <= 5  # 不越预算
    assert calls["n"] < 20  # 有界，不死循环


def test_zero_budget_disables_rate_limit_retry(monkeypatch) -> None:
    calls, slept = _arm(monkeypatch, [_limit_error()])
    with pytest.raises(HithinkAPIError):
        get_json(
            "/api/a-share/valuations/snapshot",
            gap_seconds=0,
            rate_limit_budget_seconds=0,
        )
    assert calls["n"] == 1
    assert slept == []


def test_rate_limit_budget_reads_environment(monkeypatch) -> None:
    calls, slept = _arm(monkeypatch, [_limit_error()])
    monkeypatch.setenv(hithink_client.ENV_RATE_LIMIT_BUDGET, "0")
    with pytest.raises(HithinkAPIError):
        get_json("/api/a-share/valuations/snapshot", gap_seconds=0)
    assert calls["n"] == 1
    assert slept == []


def test_business_429_retries_then_ok(monkeypatch) -> None:
    calls, slept = _arm(
        monkeypatch, [_OkResp({"code": 429}), _OkResp({"code": 0})]
    )
    assert get_json("/api/x", gap_seconds=0)["code"] == 0
    assert calls["n"] == 2 and slept == [0.8]


def test_4001_preserves_legacy_attempt_budget(monkeypatch) -> None:
    calls, slept = _arm(monkeypatch, [_OkResp({"code": 4001})])
    with pytest.raises(HithinkAPIError) as exc:
        get_json("/api/x", gap_seconds=0, retries=3, rate_limit_budget_seconds=0)
    assert type(exc.value) is HithinkAPIError
    assert calls["n"] == 3 and slept == [0.8, 1.6]


@pytest.mark.parametrize("terminal", ["network", "business", "4001"])
def test_429_does_not_reclassify_later_ordinary_failure(monkeypatch, terminal) -> None:
    last = (
        urllib.error.URLError("synthetic connection reset")
        if terminal == "network"
        else _OkResp({"code": 4001 if terminal == "4001" else 2003})
    )
    calls, slept = _arm(
        monkeypatch,
        [_OkResp({"code": 4001}) for _ in range(3)] + [_limit_error(), last],
    )
    with pytest.raises(HithinkAPIError) as exc:
        get_json("/api/x", gap_seconds=0, retries=4, rate_limit_budget_seconds=300)
    assert type(exc.value) is HithinkAPIError
    assert calls["n"] == 5
    assert slept == [0.8, 1.6, 3.2, 0.8]
    assert sum(slept) < 300
    assert hithink_client.MAX_RATE_LIMIT_RETRIES > 1


def test_429_budget_counts_request_elapsed_time(monkeypatch) -> None:
    calls, slept = _arm(monkeypatch, [_limit_error(), _OkResp({"code": 0})])
    elapsed = iter([0.0, 0.0, 6.0, 6.0, 6.0, 6.0])
    monkeypatch.setattr(hithink_client.time, "monotonic", lambda: next(elapsed))
    with pytest.raises(HithinkRateLimitError):
        get_json("/api/x", gap_seconds=0, rate_limit_budget_seconds=5)
    assert calls["n"] == 1 and slept == []


def test_zero_retry_after_is_bounded(monkeypatch) -> None:
    responses = [
        _limit_error(headers={"Retry-After": "0"}) for _ in range(20)
    ] + [_OkResp({"code": 0})]
    calls, _ = _arm(monkeypatch, responses)
    with pytest.raises(HithinkRateLimitError):
        get_json("/api/x", gap_seconds=0, rate_limit_budget_seconds=5)
    assert calls["n"] <= 11


def test_429_retry_count_is_bounded_independently_of_time(monkeypatch) -> None:
    responses = [_limit_error() for _ in range(20)] + [_OkResp({"code": 0})]
    calls, _ = _arm(monkeypatch, responses)
    with pytest.raises(HithinkRateLimitError):
        get_json("/api/x", gap_seconds=0, rate_limit_budget_seconds=10000)
    assert calls["n"] <= 11


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_rate_limit_budget_fails_before_network(monkeypatch, value) -> None:
    calls, _ = _arm(monkeypatch, [_OkResp({"code": 0})])
    with pytest.raises(HithinkAPIError):
        get_json("/api/x", gap_seconds=0, rate_limit_budget_seconds=value)
    assert calls["n"] == 0


def test_non_rate_limit_code_still_fails_fast(monkeypatch) -> None:
    """只放行限流码；其余业务错误仍须立即失败，不被新退避吞掉。"""

    calls, slept = _arm(monkeypatch, [_OkResp({"code": 2003, "message": "auth failed"})])
    with pytest.raises(HithinkAPIError) as excinfo:
        get_json("/api/a-share/valuations/snapshot", gap_seconds=0)
    assert calls["n"] == 1
    assert slept == []
    assert "code=2003" in str(excinfo.value)
