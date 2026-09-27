"""Executed query scope must reach the writer through the real Episode seams."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path

import duckdb
import pytest

from intelligence.services import episode_tools, finance_query
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.task_frame import TaskFrame


@pytest.fixture
def query_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code VARCHAR, "
            "sector_name VARCHAR, sw_l1 VARCHAR, pct_chg DOUBLE, amount DOUBLE)"
        )
        con.executemany(
            "INSERT INTO fact_sector_daily VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    day,
                    f"88{index:04d}.TI",
                    f"用于验证长观察截断之后合同依然完整的板块名称{index}",
                    "电子" if index < 50 else "机械",
                    float(index),
                    float(index + 1),
                )
                for day in ("2026-07-22", "2026-07-23")
                for index in range(60)
            ],
        )
    calls = []

    class RecordingFinanceQuery(finance_query.FinanceQuery):
        def __init__(self, *args, **kwargs):
            super().__init__(
                *args, limits=finance_query.FinanceQueryLimits(max_rows=getattr(request, "param", 200)),
                **kwargs,
            )

        def run(self, spec, **kwargs):
            result = super().run(spec, **kwargs)
            calls.append((spec, result))
            return result

    monkeypatch.setattr(episode_tools.finance_query, "FinanceQuery", RecordingFinanceQuery)
    frame = TaskFrame(
        raw_question="比较2026-07-01至2026-07-23的板块行情",
        user_goal="比较指定历史窗口的板块行情",
        question_type="theme_analysis",
        subject="电子",
        subject_kind="theme",
        market_scope="A股",
        timeframe="2026-07-01至2026-07-23",
        required_outputs=("direct_assessment", "evidence_boundary"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )
    context = build_episode_context(
        frame,
        task_id=f"query-basis-{tmp_path.name}",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-23",
        latest_data_date="2026-07-23",
    )
    registry = episode_tools.build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )
    arguments = {
        "dataset": "sector_daily",
        "metrics": ["return_pct", "amount"],
        "dimensions": ["trade_date", "sector_code", "sector_name"],
        "filters": [{"field": "sw_l1", "op": "eq", "value": "电子"}],
        "time_range": {"start": "2026-07-22", "end": "2026-07-23"},
        "group_by": [],
        "order_by": [{"field": "amount", "direction": "desc"}],
        "limit": 1000,
    }

    def execute(**changes):
        observation = registry.execute(
            "finance_query",
            {**arguments, **changes},
            context=context,
            step_id=f"{context.contract.task_id}:1",
        )
        projection = FinanceResearchHarness().project_tool_result(
            observation,
            evidence_so_far=observation.evidence,
            seen_prose=frozenset(),
        )
        return observation, projection, json.loads(projection.model_content)

    return execute, calls, db_path


@pytest.mark.parametrize("lean", ["off", "on"])
def test_executed_query_basis_survives_registry_and_model_budget(query_case, monkeypatch, lean):
    monkeypatch.setenv("ASK_EPISODE_LEAN_OBSERVATION", lean)
    execute, calls, _ = query_case
    observation, projection, facing = execute()
    executed, result = calls[0]

    assert observation.trace.status == "success"
    assert facing["ok"] is True
    assert executed.limit == result.audit.applied_limit == result.audit.row_count == 25
    assert len(observation.evidence) == 25
    assert facing["context_budget"]["truncated"] is True
    assert "截断至 25 条" in facing["observation"]
    assert "实际覆盖" in facing["observation"]
    basis = facing["query_basis"]
    assert basis == projection.audit_payload["query_basis"] == observation.query_basis
    assert basis["filters"] == [{"field": "sw_l1", "op": "eq", "value": "电子"}]
    assert basis["order_by"] == basis["selection_order_by"] == [
        {"field": "amount", "direction": "desc"}
    ]
    assert basis["group_by"] == []
    assert basis["metrics"] == ["return_pct", "amount"]
    assert basis["dimensions"] == ["trade_date", "sector_code", "sector_name"]
    assert basis["requested_time_range"] == {"start": "2026-07-22", "end": "2026-07-23"}
    assert basis["information_cutoff"] == "2026-07-23"
    assert basis["applied_limit"] == basis["returned_row_count"] == 25
    assert basis["row_unit"] == "rows"
    assert basis["candidate_pool_size"] is None
    assert basis["candidate_pool_size_status"] == "unknown_not_counted"
    serialized = json.dumps(basis, ensure_ascii=False)
    assert "1000" not in serialized and "85" not in serialized
    assert "SELECT" not in serialized and "bound_parameters" not in serialized
    assert str(result.audit.physical_sql) not in projection.model_content
    assert "/Users/" not in projection.model_content


def test_no_order_or_window_is_not_invented(query_case):
    execute, _, _ = query_case
    _, _, facing = execute(
        dimensions=["sector_name"], filters=[], time_range=None, order_by=[], limit=5,
    )
    assert facing["ok"] is True
    basis = facing["query_basis"]
    assert basis["order_by"] == basis["selection_order_by"] == []
    assert basis["requested_time_range"] is None
    assert basis["filters"] == []
    assert basis["candidate_pool_size"] is None


@pytest.mark.parametrize("query_case", [3], indirect=True)
def test_engine_limit_is_reported_even_when_lower_than_episode_cap(query_case):
    execute, calls, _ = query_case
    _, _, facing = execute()
    assert calls[0][0].limit == 25
    assert calls[0][1].audit.applied_limit == 3
    assert facing["query_basis"]["applied_limit"] == 3
    assert facing["query_basis"]["returned_row_count"] == 3
    assert facing["ok"] is True


def test_default_date_order_is_reported_from_execution(query_case):
    execute, calls, _ = query_case
    _, _, facing = execute(order_by=[], limit=5)
    assert calls[0][0].order_by == ()
    assert facing["query_basis"]["order_by"] == [
        {"field": "trade_date", "direction": "desc"}
    ]
    assert facing["query_basis"]["selection_order_by"] == facing["query_basis"]["order_by"]


def test_date_ascending_discloses_recent_slice_and_return_order(query_case):
    execute, calls, db_path = query_case
    with duckdb.connect(str(db_path)) as con:
        con.execute("DELETE FROM fact_sector_daily")
        con.executemany(
            "INSERT INTO fact_sector_daily VALUES (?, '880001.TI', '电子', '电子', 1, 1)",
            [(date(2026, 6, 14) + timedelta(days=day),) for day in range(40)],
        )
    _, _, facing = execute(
        time_range={"start": "2026-07-01", "end": "2026-07-23"},
        order_by=[{"field": "trade_date", "direction": "asc"}], limit=5,
    )
    assert [str(row["trade_date"]) for row in calls[0][1].rows] == [
        f"2026-07-{day}" for day in range(19, 24)
    ]
    basis = facing["query_basis"]
    assert basis["selection_order_by"] == [{"field": "trade_date", "direction": "desc"}]
    assert basis["order_by"] == [{"field": "trade_date", "direction": "asc"}]


def test_grouped_query_keeps_scope_and_full_group_calculation(query_case):
    execute, calls, _ = query_case
    _, _, facing = execute(
        metrics=["amount"], dimensions=["sector_code"], group_by=["sector_code"],
        limit=2,
    )
    assert [row["amount"] for row in calls[0][1].rows] == [100.0, 98.0]
    assert facing["ok"] is True
    basis = facing["query_basis"]
    assert basis["row_unit"] == "groups"
    assert basis["group_by"] == ["sector_code"]
    assert basis["applied_limit"] == basis["returned_row_count"] == 2
    assert basis["candidate_pool_size"] is None
    assert "每组统计基于筛选后全部记录" in facing["observation"]


def test_multiple_filters_and_order_keys_keep_the_executed_meaning(query_case):
    execute, calls, _ = query_case
    filters = [
        {"field": "sw_l1", "op": "in", "value": ["电子", "机械"]},
        {"field": "amount", "op": "gte", "value": 59},
    ]
    orders = [
        {"field": "amount", "direction": "desc"},
        {"field": "trade_date", "direction": "asc"},
    ]
    _, _, facing = execute(filters=filters, order_by=orders, limit=3)
    rows = calls[0][1].rows
    assert [(row["amount"], str(row["trade_date"])) for row in rows] == [
        (60.0, "2026-07-22"), (60.0, "2026-07-23"), (59.0, "2026-07-22"),
    ]
    assert facing["ok"] is True
    basis = facing["query_basis"]
    assert basis["filters"] == filters
    assert basis["order_by"] == basis["selection_order_by"] == orders
    assert basis["returned_row_count"] == 3 and basis["candidate_pool_size"] is None


def test_empty_query_keeps_real_contract_without_claiming_empty_universe(query_case):
    execute, calls, _ = query_case
    filters = [{"field": "sw_l1", "op": "eq", "value": "未命中行业"}]
    observation, _, facing = execute(filters=filters)
    assert observation.trace.status == "empty" and facing["ok"] is True
    assert calls[0][1].audit.row_count == 0
    assert facing["evidence"] == []
    basis = facing["query_basis"]
    assert basis["returned_row_count"] == 0
    assert basis["filters"] == filters
    assert basis["candidate_pool_size"] is None
    assert basis["candidate_pool_size_status"] == "unknown_not_counted"
    assert "不证明" in facing["observation"]


def test_empty_window_and_historical_followup_keep_separate_query_scopes(query_case):
    execute, _, db_path = query_case
    with duckdb.connect(str(db_path)) as con:
        con.execute("DELETE FROM fact_sector_daily WHERE trade_date = '2026-07-23' AND sw_l1 = '电子'")
    observation, _, facing = execute(
        time_range={"start": "2026-07-23", "end": "2026-07-23"},
    )
    assert observation.trace.status == "ok" and facing["ok"] is True
    assert len(observation.evidence) == 1
    assert observation.evidence[0].source_date == "2026-07-22"
    basis = facing["query_basis"]
    assert basis["requested_time_range"] == {"start": "2026-07-23", "end": "2026-07-23"}
    assert basis["returned_row_count"] == 0
    followup = basis["historical_followup"]
    assert followup["requested_time_range"] is None
    assert followup["applied_limit"] == followup["returned_row_count"] == 1
    assert followup["order_by"] == [{"field": "trade_date", "direction": "desc"}]
    assert followup["candidate_pool_size"] is None
    assert "历史记录不代替请求窗口内缺失的事实" in "".join(facing["gaps"])


def test_normalization_is_reflected_in_executed_contract(query_case):
    execute, calls, _ = query_case
    _, _, facing = execute(
        filters=[
            {"field": "trade_date", "op": "eq", "value": "2026-07-23"},
            {"field": "sw_l1", "op": "eq", "value": "电子"},
        ],
        time_range=None,
    )
    assert calls[0][0].time_range == finance_query.TimeRange(date(2026, 7, 23), date(2026, 7, 23))
    assert facing["query_basis"]["requested_time_range"] == {
        "start": "2026-07-23", "end": "2026-07-23"
    }
    assert facing["query_basis"]["filters"] == [{"field": "sw_l1", "op": "eq", "value": "电子"}]


def test_failed_query_does_not_advertise_an_executed_contract(query_case):
    execute, calls, _ = query_case
    observation, _, facing = execute(metrics=["unknown_metric"])
    assert observation.trace.status == "parse_error" and facing["ok"] is False
    assert not calls
    assert "query_basis" not in facing


def test_query_basis_also_survives_repeated_prose_pruning(query_case):
    execute, _, _ = query_case
    observation, first, _ = execute()
    repeated = FinanceResearchHarness().project_tool_result(
        replace(observation, telemetry={"private_runtime_path": "/secret/audit"}),
        evidence_so_far=observation.evidence,
        seen_prose=first.seen_prose,
    )
    facing = json.loads(repeated.model_content)
    assert facing["noise_prune"]["collapsed_prose"] is True
    assert facing["query_basis"] == observation.query_basis
    assert "telemetry" not in facing and "/secret/audit" not in repeated.model_content
