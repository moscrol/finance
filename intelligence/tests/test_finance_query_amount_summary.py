"""Bounded stock amount summaries, including the stored K3 arithmetic sample."""
from datetime import date, timedelta
import socket
import subprocess
from uuid import uuid4

import duckdb
import pytest

from intelligence.services import agent_research, episode_tools, finance_query
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.material_permissions import LOCAL_READ_CAPABILITIES
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.tool_hunger import hunger_context
from intelligence.services.tool_result_budget import budget_tool_observation


# Frozen from run_20260921_203845_282895 stock_daily evidence, amounts in yi.
SAMPLE = (
    ("2026-09-01", 10.3073), ("2026-09-02", 6.1252),
    ("2026-09-03", 7.3596), ("2026-09-04", 10.3892),
    ("2026-09-07", 7.0416), ("2026-09-08", 5.7172),
    ("2026-09-09", 4.8368), ("2026-09-10", 5.9842),
    ("2026-09-11", 8.1251), ("2026-09-14", 4.8754),
    ("2026-09-15", 3.9438), ("2026-09-16", 4.9138),
    ("2026-09-17", 5.5672), ("2026-09-18", 7.4283),
)


@pytest.fixture
def stock_db(tmp_path):
    path = tmp_path / "finance" / "db" / "market_feature_store.duckdb"
    path.parent.mkdir(parents=True)
    with duckdb.connect(str(path)) as con:
        con.execute("""CREATE TABLE fact_stock_daily (
            trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, amount DOUBLE,
            PRIMARY KEY (trade_date, stock_ts_code))""")
        con.executemany("INSERT INTO fact_stock_daily VALUES (?, ?, ?, ?)", [
            (day, "600673.SH", "sample\x00\x00" if day in {"2026-09-03", "2026-09-04"} else "sample", amount)
            for day, amount in SAMPLE
        ] + [
            ("2026-08-31", "600673.SH", "sample", 900.0),
            ("2026-09-21", "600673.SH", "sample", 900.0),
            ("2026-09-18", "600001.SH", "other", 900.0),
        ])
    return path


def arguments(**overrides):
    values = dict(
        dataset="stock_daily", metrics=["amount_mean", "amount_valid_count"],
        dimensions=["stock_code"], group_by=["stock_code"],
        filters=[{"field": "stock_code", "op": "eq", "value": "600673.SH"}],
        time_range={"start": "2026-09-01", "end": "2026-09-18"}, limit=1,
    )
    values.update(overrides)
    return values


def run(path, **overrides):
    return finance_query.FinanceQuery(path).run(
        finance_query.FinanceQuerySpec.from_arguments(arguments(**overrides)),
        information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
        deadline=ResearchDeadline.from_timeout(3),
    )


def test_stored_fourteen_day_sample_is_computed_before_limit(stock_db):
    result = run(stock_db, metrics=["amount", "amount_mean", "amount_valid_count"])
    row, = result.rows
    assert row["stock_code"] == "600673.SH"
    assert row["amount"] == pytest.approx(92.6147)
    assert row["amount_mean"] == pytest.approx(92.6147 / 14)
    assert row["amount_valid_count"] == 14
    assert isinstance(row["amount_valid_count"], int)
    assert result.audit.applied_limit == result.audit.row_count == 1
    assert "成交额均值亿=6.6153" in result.observation
    assert "有效成交额样本数=14" in result.observation
    assert "统计请求窗口=2026-09-01..2026-09-18" in result.evidence[0].detail
    assert "样本数不证明交易日齐全" in result.evidence[0].detail
    assert result.evidence[0].source_date == "2026-09-18"
    assert result.evidence[0].observations == ()  # Interval mean is not a daily amount.
    assert result.evidence[0].content_hash == agent_research.evidence_content_hash(result.evidence[0])
    assert 'SUM("amount")' in result.audit.physical_sql
    assert "600673.SH" not in result.audit.physical_sql
    assert "600673.SH" in result.audit.bound_parameters


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf")])
def test_mean_and_denominator_exclude_same_invalid_sample_but_keep_zero(stock_db, bad):
    with duckdb.connect(str(stock_db)) as con:
        con.execute("UPDATE fact_stock_daily SET amount = ? WHERE trade_date = '2026-09-01'", [bad])
        con.execute("UPDATE fact_stock_daily SET amount = 0 WHERE trade_date = '2026-09-02'")
    row, = run(stock_db).rows
    assert row["amount_valid_count"] == 13
    assert row["amount_mean"] == pytest.approx(sum(amount for _, amount in SAMPLE[2:]) / 13)


def test_all_null_amounts_have_unknown_mean_and_zero_valid_samples(stock_db):
    with duckdb.connect(str(stock_db)) as con:
        con.execute("UPDATE fact_stock_daily SET amount = NULL")
    result = run(stock_db)
    assert result.rows == ({"stock_code": "600673.SH", "amount_mean": None, "amount_valid_count": 0},)
    assert "成交额均值亿=未知" in result.observation


def test_no_matching_rows_is_empty_not_zero_mean(stock_db):
    result = run(stock_db, filters=[{"field": "stock_code", "op": "eq", "value": "999999.SH"}])
    assert result.rows == result.evidence == ()


def test_more_than_agent_row_cap_is_not_a_truncated_mean(stock_db):
    with duckdb.connect(str(stock_db)) as con:
        con.execute("DELETE FROM fact_stock_daily")
        con.executemany("INSERT INTO fact_stock_daily VALUES (?, '600673.SH', 'sample', ?)", [
            (date(2026, 8, 20) + timedelta(days=i), i + 1) for i in range(30)
        ])
    result = run(stock_db, time_range={"start": "2026-08-20", "end": "2026-09-18"})
    assert result.rows == ({"stock_code": "600673.SH", "amount_mean": 15.5, "amount_valid_count": 30},)


def test_each_stock_is_aggregated_before_sort_and_group_limit(stock_db):
    result = run(stock_db, filters=[], limit=2,
                 order_by=[{"field": "amount_mean", "direction": "desc"}])
    assert [row["stock_code"] for row in result.rows] == ["600001.SH", "600673.SH"]
    assert [row["amount_valid_count"] for row in result.rows] == [1, 14]
    assert [row["amount_mean"] for row in result.rows] == pytest.approx([900, 92.6147 / 14])
    limited = run(stock_db, filters=[], order_by=[{"field": "amount_mean", "direction": "desc"}])
    assert limited.rows == result.rows[:1]


def test_summary_connection_is_read_only(stock_db):
    calls = []

    def connect(path, *, read_only):
        calls.append(read_only)
        return duckdb.connect(path, read_only=read_only)

    finance_query.FinanceQuery(stock_db, connect=connect).run(
        finance_query.FinanceQuerySpec.from_arguments(arguments()),
        information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
        deadline=ResearchDeadline.from_timeout(3),
    )
    assert calls == [True]


def test_summary_windows_are_part_of_evidence_identity(stock_db):
    first = run(stock_db)
    # A different requested window remains distinguishable even when rows match.
    second = run(stock_db, time_range={"start": "2026-09-02", "end": "2026-09-18"})
    assert first.evidence[0].content_hash != second.evidence[0].content_hash
    assert second.rows[0]["amount_valid_count"] == 13
    assert "2026-09-02..2026-09-18" in second.evidence[0].detail
    same_rows = run(stock_db, time_range={"start": "2026-09-05", "end": "2026-09-18"})
    shifted = run(stock_db, time_range={"start": "2026-09-06", "end": "2026-09-18"})
    assert same_rows.rows == shifted.rows
    assert same_rows.evidence[0].content_hash != shifted.evidence[0].content_hash


@pytest.mark.parametrize("overrides, match", [
    ({"metrics": ["amount_mean"]}, "together"),
    ({"metrics": ["amount_valid_count"]}, "together"),
    ({"group_by": []}, "dimensions and group_by"),
    ({"dimensions": ["stock_name"], "group_by": ["stock_name"]}, "dimensions and group_by"),
    ({"dimensions": ["stock_code", "stock_name"], "group_by": ["stock_code", "stock_name"]}, "dimensions and group_by"),
    ({"dimensions": ["stock_code", "trade_date"], "group_by": ["stock_code", "trade_date"]}, "dimensions and group_by"),
    ({"time_range": None}, "explicit time_range"),
    ({"time_range": {"start": "2026-09-01"}}, "explicit time_range"),
    ({"time_range": {"end": "2026-09-18"}}, "explicit time_range"),
    ({"filters": [{"field": "amount", "op": "gt", "value": 7}]}, "only stock_code"),
    ({"filters": [{"field": "stock_name", "op": "eq", "value": "sample"}]}, "only stock_code"),
    ({"filters": [{"field": "amount_mean", "op": "gt", "value": 7}]}, "cannot be used as row filters"),
    ({"time_range": {"start": "2026-09-01", "end": "2026-09-21"}}, "cutoff"),
    ({"filters": [{"field": "stock_code", "op": "eq", "value": "600673"}]}, "market suffix"),
])
def test_invalid_summary_rejected_before_any_database_access(tmp_path, overrides, match):
    with pytest.raises(finance_query.FinanceQueryValidationError, match=match):
        run(tmp_path / "missing.duckdb", **overrides)


def test_summary_retry_hint_explains_valid_shape():
    spec = finance_query.FinanceQuerySpec.from_arguments(arguments(group_by=[]))
    hint = finance_query.validation_retry_hint(
        spec, finance_query.FinanceQueryValidationError("amount summary requires grouping")
    )
    assert all(word in hint for word in ("amount_mean", "amount_valid_count", "stock_code", "time_range"))


@pytest.mark.parametrize("group_by, has_axis", [([], True), (["stock_code"], False), (["trade_date"], True)])
def test_group_max_date_does_not_impersonate_covered_date_axis(group_by, has_axis):
    spec = finance_query.FinanceQuerySpec.from_arguments(arguments(
        metrics=["amount"], dimensions=group_by or ["trade_date"], group_by=group_by,
    ))
    assert finance_query.result_has_date_axis(spec) is has_axis


@pytest.mark.parametrize("metric", ["amount_mean", "amount_valid_count"])
def test_summary_alias_cannot_be_a_row_filter_without_selecting_it(tmp_path, metric):
    with pytest.raises(finance_query.FinanceQueryValidationError, match="cannot be used as row filters"):
        run(tmp_path / "missing.duckdb", metrics=["amount"], group_by=[],
            filters=[{"field": metric, "op": "gt", "value": 7}])


def test_existing_amount_detail_and_sum_keep_their_semantics(stock_db):
    summary = run(stock_db, metrics=["amount"])
    assert summary.rows == ({"stock_code": "600673.SH", "amount": pytest.approx(92.6147)},)
    detail = run(stock_db, metrics=["amount"], dimensions=["stock_code", "trade_date"], group_by=[],
                 order_by=[{"field": "trade_date", "direction": "desc"}])
    assert detail.rows == ({"stock_code": "600673.SH", "trade_date": "2026-09-18", "amount": 7.4283},)
    assert "统计请求窗口" not in detail.observation


@pytest.mark.parametrize("mode, limit", [("summary", 1), ("summary", 25), ("empty", 25), ("date_groups", 25)])
def test_local_registry_delivers_summary_without_external_io(stock_db, tmp_path, monkeypatch, mode, limit):
    frame = understand_query(
        "只用本地已有资料，不联网：东阳光(600673.SH)2026-09-01至2026-09-18的日均成交额和有效样本数？"
    ).task_frame
    context = build_episode_context(
        frame, task_id=f"local-amount-summary-{uuid4().hex}", capabilities=tuple(sorted(LOCAL_READ_CAPABILITIES)),
        today="2026-09-18", latest_data_date="2026-09-18", timeout=10, synthesis_reserve=0,
    )
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError("unexpected network/subprocess")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(agent_research, "build_default_tools", forbidden)
    monkeypatch.setattr(episode_tools, "_calc_loader_for", forbidden)
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=stock_db.parent.parent, knowledge_wiki=tmp_path / "wiki",
        memory_users_root=tmp_path / "users", derived_calculation_runner=forbidden,
    )
    assert set(context.contract.allowed_capabilities) == LOCAL_READ_CAPABILITIES
    assert registry.read_scope == "local_only"
    assert set(registry.names()) == LOCAL_READ_CAPABILITIES
    definitions = registry.tool_definitions(context.contract.allowed_capabilities)
    definition = next(item["function"] for item in definitions if item["function"]["name"] == "finance_query")
    properties = definition["parameters"]["properties"]
    assert {"amount_mean", "amount_valid_count"} <= set(properties["metrics"]["items"]["enum"])
    assert "amount_mean" in properties["dataset"]["description"]
    events = []

    class Sink:
        def record(self, event):
            events.append(event)

    requested = arguments(limit=limit)
    if mode == "empty":
        requested["filters"] = [{"field": "stock_code", "op": "eq", "value": "999999.SH"}]
    elif mode == "date_groups":
        with duckdb.connect(str(stock_db)) as con:
            con.execute("DELETE FROM fact_stock_daily WHERE trade_date < '2026-09-14'")
        requested.update(metrics=["amount"], dimensions=["trade_date"], group_by=["trade_date"])
    with hunger_context(Sink()):
        result = registry.execute("finance_query", requested, context=context, step_id="summary")
    assert attempts == []
    if mode == "empty":
        assert result.evidence == ()
        assert any(event["event_type"] == "window_uncovered" for event in events)
        return
    if mode == "date_groups":
        assert len(result.evidence) == 5
        assert result.trace.status == "success"
        assert any(event["event_type"] == "window_uncovered" for event in events)
        return
    assert len(result.evidence) == 1
    assert result.evidence[0].io_effect == "local_read"
    assert result.trace.status == "success"
    assert ("聚合结果最多返回 1 组" in result.observation) is (limit == 1)
    assert "窗口前端未覆盖" not in result.observation
    assert not any(event["event_type"] == "window_uncovered" for event in events)
    assert "成交额均值亿=6.6153" in result.observation
    assert "有效成交额样本数=14" in result.observation
    assert "2026-09-01..2026-09-18" in result.observation
    delivered = budget_tool_observation({
        "observation": result.observation,
        "evidence": [{"detail": item.detail} for item in result.evidence],
    })
    assert "成交额均值亿=6.6153" in delivered["observation"]
    assert "有效成交额样本数=14" in delivered["evidence"][0]["detail"]
    assert "2026-09-01..2026-09-18" in delivered["evidence"][0]["detail"]
