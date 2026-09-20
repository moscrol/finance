"""Offline contract tests; all responses below are synthetic, not market evidence."""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.hithink_client import HithinkAPIError, shanghai_midnight_ms
from market_feature_store.sync import sync_hithink_research as research

DAY = date(2026, 9, 21)
NOW = datetime(2026, 9, 21, 18, 30, tzinfo=research.SHANGHAI)
CODE = "300750.SZ"
OTHER = "600519.SH"


def payload(kind, params):
    if kind == "anomaly":
        items = [
            {
                "thscode": CODE,
                "analysis_content": "Synthetic vendor opinion.",
                "tag_name": "rise",
                "keyword_list": ["test"],
            }
        ]
    elif kind == "valuation":
        items = [
            {"thscode": code, **dict.fromkeys(research.VALUATION_FIELDS, 12.5)}
            for code in params["thscodes"].split(",")
        ]
        items[0]["pe_ttm"] = -2.5
        items[0]["pcf_ttm"] = None
    else:
        end = date.fromisoformat(params["end_date"])
        items = [
            {
                "thscode": params["thscode"],
                "date": (end - timedelta(days=i)).isoformat(),
                "date_ms": shanghai_midnight_ms(end - timedelta(days=i)),
                "rank": 142 + i,
            }
            for i in range(2)
        ]
    return {
        "code": 0,
        "request_id": "synthetic-provider-id",
        "data": {
            "timestamp": shanghai_midnight_ms(DAY),
            "total": len(items),
            "item": items,
        },
    }


@pytest.fixture
def capture(tmp_path):
    path = tmp_path / "research.duckdb"
    calls = []

    def getter(endpoint, *, params):
        kind = next(key for key, value in research.PATHS.items() if value == endpoint)
        calls.append((kind, copy.deepcopy(params)))
        return payload(kind, params)

    def run(**kwargs):
        defaults = dict(
            db_path=path,
            codes=[CODE],
            getter=getter,
            clock=lambda: NOW,
            lookback_days=2,
        )
        defaults.update(kwargs)
        return research.sync_hithink_research(**defaults)

    return path, calls, run, getter


def query(path, sql, params=None):
    with duckdb.connect(str(path), read_only=True) as con:
        return con.execute(sql, params or []).fetchall()


def test_capture_writes_values_and_raw_request_scope(capture):
    path, calls, run, _ = capture
    result = run()
    assert result["status"] == "ok"
    assert [kind for kind, _ in calls] == ["anomaly", "valuation", "heat_trend"]
    assert query(
        path,
        "SELECT observation_date, rank FROM fact_hot_stock_trend_hithink ORDER BY 1",
    ) == [
        (DAY - timedelta(days=1), 143),
        (DAY, 142),
    ]  # Weekend points remain natural-date observations, not new trading days.
    assert query(
        path, "SELECT pe_ttm, pcf_ttm, captured_date FROM fact_stock_valuation_hithink"
    ) == [(-2.5, None, DAY)]
    receipt = query(
        path,
        "SELECT params_json, payload_json FROM ops_hithink_research_request WHERE kind='heat_trend'",
    )[0]
    assert json.loads(receipt[0])["thscode"] == CODE
    assert json.loads(receipt[1])["data"]["item"][0]["rank"] == 142
    assert query(path, "SELECT count(*) FROM fact_stock_daily") == [(0,)]


def test_repeated_capture_is_idempotent_in_facts_but_keeps_raw_versions(capture):
    path, _, run, _ = capture
    run()
    run()
    assert query(path, "SELECT count(*) FROM fact_hot_stock_trend_hithink") == [(2,)]
    assert query(path, "SELECT count(*) FROM fact_stock_anomaly_hithink") == [(1,)]
    assert query(path, "SELECT count(*) FROM ops_hithink_research_request") == [(6,)]


@pytest.mark.parametrize("day", [DAY - timedelta(days=1), DAY + timedelta(days=1)])
def test_latest_snapshot_cannot_be_backdated_or_predated(capture, day):
    path, calls, run, _ = capture
    with pytest.raises(research.HithinkResearchError, match="today"):
        run(end_date=day)
    assert not path.exists() and not calls


def test_history_only_never_calls_current_endpoints(capture):
    path, calls, run, _ = capture
    result = run(end_date=DAY - timedelta(days=3), history_only=True)
    assert result["history_only"] is True
    assert [kind for kind, _ in calls] == ["heat_trend"]
    assert query(path, "SELECT count(*) FROM fact_stock_valuation_hithink") == [(0,)]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"codes": []},
        {"codes": ["300750"]},
        {"codes": [CODE] * 101},
        {"lookback_days": 0},
        {"lookback_days": 366},
        {"lookback_days": True},
        {"end_date": DAY - timedelta(days=364), "history_only": True},
    ],
)
def test_invalid_scope_is_rejected_before_io(capture, kwargs):
    path, calls, run, _ = capture
    with pytest.raises(research.HithinkResearchError):
        run(**kwargs)
    assert not calls and not path.exists()


def test_no_key_does_not_create_database(capture, monkeypatch):
    path, calls, run, _ = capture
    monkeypatch.setattr(research, "has_api_key", lambda: False)
    assert run(getter=None)["status"] == "skip"
    assert not calls and not path.exists()


def test_production_path_refused_before_credentials_or_database(capture, monkeypatch):
    path, _, run, _ = capture
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB", str(path))
    monkeypatch.setattr(
        research, "has_api_key", lambda: pytest.fail("credentials accessed")
    )
    with pytest.raises(research.HithinkResearchError, match="production"):
        run(getter=None)
    assert not path.exists()


def test_empty_response_is_recorded_not_invented(capture):
    path, _, run, _ = capture
    run(
        getter=lambda *a, **k: {
            "code": 0,
            "data": {"timestamp": 0, "total": 0, "item": []},
        }
    )
    assert query(
        path,
        "SELECT DISTINCT status, row_count, value_rows FROM ops_hithink_research_request",
    ) == [("empty", 0, 0)]
    assert query(path, "SELECT count(*) FROM fact_hot_stock_trend_hithink") == [(0,)]


def test_partial_valuation_reports_missing_codes_and_null_rows(capture):
    path, _, run, getter = capture

    def partial(endpoint, *, params):
        result = getter(endpoint, params=params)
        if endpoint == research.PATHS["valuation"]:
            result["data"]["item"] = [
                {"thscode": CODE, **dict.fromkeys(research.VALUATION_FIELDS)}
            ]
            result["data"]["total"] = 1
        return result

    assert run(codes=[CODE, OTHER], getter=partial)["status"] == "complete_with_gaps"
    assert query(
        path,
        "SELECT status, row_count, value_rows FROM ops_hithink_research_request WHERE kind='valuation'",
    ) == [("partial", 1, 0)]
    assert query(
        path, "SELECT count(*) FROM fact_stock_valuation_hithink WHERE pe_ttm IS NULL"
    ) == [(1,)]


@pytest.mark.parametrize(
    "defect",
    [
        "wrong-code",
        "out-of-range",
        "date-ms",
        "duplicate",
        "nan",
        "bool",
        "negative-rank",
        "missing-item",
        "business-error",
    ],
)
def test_malformed_trend_fails_and_preserves_prior_facts(capture, defect):
    path, _, run, getter = capture
    run(history_only=True)

    def bad(endpoint, *, params):
        result = getter(endpoint, params=params)
        item = result["data"]["item"][0]
        if defect == "wrong-code":
            item["thscode"] = OTHER
        elif defect == "out-of-range":
            item["date"] = "2026-08-01"
        elif defect == "date-ms":
            item["date_ms"] = shanghai_midnight_ms(DAY - timedelta(days=3))
        elif defect == "duplicate":
            result["data"]["item"].append(copy.deepcopy(item))
        elif defect in {"nan", "bool", "negative-rank"}:
            item["rank"] = {"nan": float("nan"), "bool": True, "negative-rank": -1}[
                defect
            ]
        elif defect == "missing-item":
            del result["data"]["item"]
        else:
            result["code"] = 2001
        return result

    with pytest.raises(research.HithinkResearchError):
        run(history_only=True, getter=bad)
    assert query(path, "SELECT count(*) FROM fact_hot_stock_trend_hithink") == [(2,)]
    assert query(
        path, "SELECT count(*) FROM ops_hithink_research_request WHERE status='failed'"
    ) == [(1,)]


def test_stale_anomaly_timestamp_fails_not_relabelled(capture):
    path, _, run, getter = capture

    def stale(endpoint, *, params):
        result = getter(endpoint, params=params)
        result["data"]["timestamp"] = shanghai_midnight_ms(DAY - timedelta(days=1))
        return result

    with pytest.raises(research.HithinkResearchError, match="anomaly"):
        run(getter=stale)
    assert query(path, "SELECT count(*) FROM fact_stock_anomaly_hithink") == [(0,)]


def test_failure_receipt_never_echoes_upstream_secret(capture):
    path, _, run, _ = capture

    def fail(*args, **kwargs):
        raise HithinkAPIError("fake-secret-never-persist")

    with pytest.raises(research.HithinkResearchError) as exc:
        run(getter=fail)
    assert "fake-secret" not in str(exc.value)
    assert "fake-secret" not in str(
        query(path, "SELECT * FROM ops_hithink_research_request")
    )


def test_transaction_rolls_back_facts_on_mid_write_failure(capture, monkeypatch):
    path, _, run, _ = capture
    store = research._store_rows

    def broken(*args):
        store(*args)
        raise RuntimeError("synthetic failure after insert")

    monkeypatch.setattr(research, "_store_rows", broken)
    with pytest.raises(research.HithinkResearchError):
        run()
    assert query(path, "SELECT count(*) FROM fact_stock_anomaly_hithink") == [(0,)]
    assert query(path, "SELECT status FROM ops_hithink_research_request") == [
        ("failed",)
    ]


def test_current_scope_only_no_stale_fallback(capture):
    path, calls, run, _ = capture
    with duckdb.connect(str(path)) as con:
        db.init_db(con)
        con.execute(
            "INSERT INTO fact_hot_stock_rank_hithink (trade_date, stock_ts_code, rank) VALUES (?, ?, 1)",
            [DAY - timedelta(days=1), CODE],
        )
    with pytest.raises(research.HithinkResearchError, match="no target-day"):
        run(codes=None)
    assert not calls
    with duckdb.connect(str(path)) as con:
        con.execute(
            "INSERT INTO fact_hot_stock_rank_hithink (trade_date, stock_ts_code, rank) VALUES (?, ?, 2)",
            [DAY, OTHER],
        )
    assert run(codes=None)["scope"] == [OTHER]


def test_request_crossing_midnight_is_rejected(capture):
    path, _, run, _ = capture
    ticks = iter([NOW, NOW, NOW + timedelta(days=1)])
    with pytest.raises(research.HithinkResearchError):
        run(clock=lambda: next(ticks))
    assert query(path, "SELECT count(*) FROM fact_stock_anomaly_hithink") == [(0,)]


def test_cli_prints_summary_and_refuses_production(capture, monkeypatch, capsys):
    from market_feature_store import cli

    path, _, _, getter = capture
    monkeypatch.setattr(research, "DB_PATH", path)
    monkeypatch.setattr(research, "has_api_key", lambda: True)
    monkeypatch.setattr(research, "get_json", getter)
    monkeypatch.setattr(research, "_now", lambda: NOW)
    assert cli.main(["sync-hithink-research", "--thscodes", CODE]) == 0
    assert json.loads(capsys.readouterr().out)["scope"] == [CODE]
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB", str(path))
    assert cli.main(["sync-hithink-research", "--thscodes", CODE]) == 2
    assert "production" in capsys.readouterr().out


@pytest.mark.parametrize(
    "dataset,metric,expected",
    [
        ("stock_anomaly_hithink", "observations", 1),
        ("hot_stock_trend_hithink", "rank", 142),
        ("stock_valuation_hithink", "pe_ttm", -2.5),
    ],
)
def test_real_query_consumer_can_read_ingested_rows(capture, dataset, metric, expected):
    from intelligence.services.finance_query import FinanceQuery, FinanceQuerySpec
    from intelligence.services.research_contract import (
        InformationCutoff,
        ResearchDeadline,
    )

    path, _, run, _ = capture
    run()
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": dataset,
            "dimensions": ["observation_date", "stock_code"],
            "metrics": [metric],
            "time_range": {"start": DAY.isoformat(), "end": DAY.isoformat()},
        }
    )
    result = FinanceQuery(path).run(
        spec,
        information_cutoff=InformationCutoff(DAY, "requested"),
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert len(result.rows) == 1 and result.rows[0][metric] == expected
    assert result.evidence and result.evidence[0].source_date == DAY.isoformat()
    from intelligence.services.finance_query import _dataset_catalog_text

    assert f"{dataset}（子集）" in _dataset_catalog_text()


def test_historical_cutoff_cannot_see_later_collected_trend(capture):
    from intelligence.services.finance_query import FinanceQuery, FinanceQuerySpec
    from intelligence.services.research_contract import (
        InformationCutoff,
        ResearchDeadline,
    )

    path, _, run, _ = capture
    past = DAY - timedelta(days=3)
    run(end_date=past, history_only=True)
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "hot_stock_trend_hithink",
            "dimensions": ["observation_date", "stock_code"],
            "metrics": ["rank"],
            "time_range": {"start": past.isoformat(), "end": past.isoformat()},
        }
    )
    query_service = FinanceQuery(path)
    hidden = query_service.run(
        spec,
        information_cutoff=InformationCutoff(past, "requested"),
        deadline=ResearchDeadline.from_timeout(5),
    )
    visible = query_service.run(
        spec,
        information_cutoff=InformationCutoff(DAY, "requested"),
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert hidden.rows == ()
    assert len(visible.rows) == 1
    assert (
        visible.evidence[0].source_date == DAY.isoformat()
    )  # Information date, not ranking date.


def test_shanghai_capture_date_is_not_utc_day(capture):
    path, _, run, _ = capture
    early = NOW.replace(hour=1)
    run(clock=lambda: early)
    assert query(path, "SELECT captured_date FROM fact_stock_valuation_hithink") == [
        (DAY,)
    ]
