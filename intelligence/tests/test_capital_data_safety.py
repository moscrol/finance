"""资金取数的错误、时间和预算边界；不发网络请求。"""
from datetime import date, timedelta
import json
from unittest.mock import Mock

import duckdb
import pytest

from intelligence.services import market_capital as capital
from intelligence.services.research_contract import ResearchDeadline


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "market.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create table fact_stock_daily (stock_ts_code varchar, stock_name varchar)")
    con.execute("insert into fact_stock_daily values ('600519.SH','贵州茅台'), ('000858.SZ','五粮液')")
    con.close()
    return path


def response(monkeypatch, payload):
    resp = Mock()
    resp.read.return_value = json.dumps(payload).encode()
    manager = Mock()
    manager.__enter__ = Mock(return_value=resp)
    manager.__exit__ = Mock(return_value=False)
    opener = Mock(return_value=manager)
    monkeypatch.setattr(capital.urllib.request, "urlopen", opener)
    return opener


def test_unlock_network_failure_is_not_no_unlock(db, monkeypatch):
    monkeypatch.setattr(capital.urllib.request, "urlopen", Mock(side_effect=TimeoutError()))
    block = capital.capital_block_for_llm("贵州茅台解禁", db)
    assert "无待解禁" not in block
    assert "request_error" in block
    assert "不能" in block


@pytest.mark.parametrize("payload", [
    {"success": False, "code": 500, "message": "upstream failed", "result": None},
    {"success": True, "result": {}},
    {"success": True, "result": {"data": "bad", "count": 1}},
    {"success": True, "result": {"data": [{}], "count": 1}},
    {"success": True, "result": {"data": [{"FREE_DATE": "bad"}], "count": 1}},
])
def test_malformed_provider_payload_is_not_empty(db, monkeypatch, payload):
    response(monkeypatch, payload)
    bundle = capital.capital_bundle_for_llm("贵州茅台解禁", db)
    assert bundle.status in {"request_error", "parse_error"}
    assert "无待解禁" not in bundle.block
    assert bundle.row_count == 0


def test_eastmoney_9201_is_scoped_empty_not_company_fact(db, monkeypatch):
    response(monkeypatch, {"success": False, "code": 9201, "message": "返回数据为空", "result": None})
    bundle = capital.capital_bundle_for_llm("贵州茅台解禁", db)
    assert bundle.status == "empty"
    assert "本次查询未返回解禁记录" in bundle.block
    assert "无待解禁" not in bundle.block


def test_partial_success_keeps_good_slice_and_failed_gap(db, monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError()
    bundle = capital.capital_bundle_for_llm(
        "贵州茅台两融和解禁", db,
        margin_fetcher=lambda *a, **k: [capital.MarginRow(date.today().isoformat(), 170.59, 1.15, 1.85)],
        unlock_fetcher=fail,
    )
    assert bundle.status == "partial"
    assert bundle.row_count == 1
    assert "170.59" in bundle.block
    assert "request_error" in bundle.block
    assert "无待解禁" not in bundle.block


def test_historical_unlock_refuses_live_schedule_before_network(db):
    fetch = Mock()
    bundle = capital.capital_bundle_for_llm("贵州茅台解禁", db, as_of="2025-08-01", unlock_fetcher=fetch)
    fetch.assert_not_called()
    assert bundle.status == "not_attempted"
    assert "历史" in bundle.block
    assert "当时" in bundle.block


def test_margin_query_applies_date_in_provider_and_locally(monkeypatch, db):
    rows = [
        {"DATE": "2025-08-01 00:00:00", "RZYE": 1e8, "SCODE": "600519"},
        {"DATE": "2026-09-17 00:00:00", "RZYE": 2e8, "SCODE": "600519"},
    ]
    opener = response(monkeypatch, {"success": True, "result": {"data": rows, "count": 2}})
    bundle = capital.capital_bundle_for_llm("贵州茅台两融", db, as_of="2025-08-01")
    from urllib.parse import unquote
    assert "DATE<='2025-08-01'" in unquote(opener.call_args.args[0].full_url)
    assert bundle.row_count == 1
    assert "2026-09-17" not in bundle.block


def test_second_slice_does_not_get_a_fresh_budget(db):
    deadline = ResearchDeadline.from_timeout(0)
    fetch = Mock()
    bundle = capital.capital_bundle_for_llm("贵州茅台两融大宗解禁", db, deadline=deadline,
                                          margin_fetcher=fetch, block_fetcher=fetch, unlock_fetcher=fetch)
    fetch.assert_not_called()
    assert bundle.row_count == 0
    assert "预算" in bundle.block


def test_shared_absolute_deadline_shrinks_for_following_slice(db, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("intelligence.services.research_contract.time.monotonic", lambda: clock[0])
    seen = []
    def margin(code, limit, timeout):
        seen.append(timeout)
        clock[0] += 3
        return [capital.MarginRow(date.today().isoformat(), 1, 2, 3)]
    def block(code, limit, timeout):
        seen.append(timeout)
        return []
    capital.capital_bundle_for_llm("贵州茅台两融大宗", db, timeout=5, margin_fetcher=margin, block_fetcher=block)
    assert seen == [5, 2]


def test_multiple_companies_are_not_silently_collapsed(db):
    fetch = Mock()
    bundle = capital.capital_bundle_for_llm("贵州茅台和五粮液两融", db, margin_fetcher=fetch)
    fetch.assert_not_called()
    assert bundle.row_count == 0
    assert "单只" in bundle.block


@pytest.mark.parametrize("query", [
    "600519和五粮液两融", "000858 贵州茅台解禁", "600519.SH和600519.SZ两融",
])
def test_conflicting_code_and_name_do_not_pick_first(db, query):
    fetch = Mock()
    bundle = capital.capital_bundle_for_llm(query, db, margin_fetcher=fetch, unlock_fetcher=fetch)
    fetch.assert_not_called()
    assert "单只" in bundle.block or "冲突" in bundle.block


@pytest.mark.parametrize("when", ["截至昨天", "上周", "截至去年", "当时", "截至2025年8月"])
def test_legacy_wrapper_does_not_hide_unresolved_history(db, when):
    fetch = Mock()
    block = capital.capital_block_for_llm(f"{when}贵州茅台解禁", db, unlock_fetcher=fetch)
    fetch.assert_not_called()
    assert "YYYY-MM-DD" in block


def test_chinese_adjacent_ticker_is_resolved(db):
    bundle = capital.capital_bundle_for_llm("查询600519两融", db, margin_fetcher=lambda *a: [])
    assert bundle.ts_code == "600519.SH"


def test_unlock_ratio_converts_before_rounding(monkeypatch):
    response(monkeypatch, {"success": True, "result": {"data": [{
        "FREE_DATE": date.today().isoformat(), "CURRENT_FREE_SHARES": 22999.1878,
        "FREE_RATIO": 0.212299414599,
    }], "count": 1}})
    rows = capital.fetch_unlock_rows("600072", date.today().isoformat())
    assert rows[0].ratio_pct == 21.23


def test_unlock_truncation_is_explicit(db):
    rows = [capital.UnlockRow((date.today() + timedelta(days=i)).isoformat(), "限售股", 1, 1) for i in range(21)]
    bundle = capital.capital_bundle_for_llm("贵州茅台解禁", db, unlock_fetcher=lambda *a: rows)
    assert bundle.row_count == 20
    assert bundle.status == "partial"
    assert "截断" in bundle.block


@pytest.mark.parametrize("bad", [float("inf"), -float("inf"), float("nan"), True])
def test_non_finite_and_boolean_are_not_numbers(bad):
    assert capital._num(bad) is None
