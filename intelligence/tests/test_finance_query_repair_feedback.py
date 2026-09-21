"""Offline feedback delivery, not an autonomous model-quality acceptance test."""

from dataclasses import replace
import json
from threading import Event
from uuid import uuid4

import duckdb
import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services import episode_tools, finance_query
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_agent_episode import _context, _finish_turn, _frame


def _request(**overrides):
    return {
        "dataset": "market_daily",
        "dimensions": ["trade_date"],
        "metrics": ["stage_day"],
        "time_range": {"start": "2026-07-21", "end": "2026-07-21"},
        **overrides,
    }


def _setup(tmp_path, *, rows=True, table=True, max_steps=3):
    path = tmp_path / "db" / "market_feature_store.duckdb"
    path.parent.mkdir()
    with duckdb.connect(str(path)) as con:
        if table:
            con.execute(
                "CREATE TABLE fact_market_daily "
                "(trade_date DATE, stage_day INTEGER, sh_index_pct_chg DOUBLE)"
            )
            if rows:
                con.execute("INSERT INTO fact_market_daily VALUES ('2026-07-21', 3, 1.25)")
    frame = _frame()
    context = replace(
        _context(frame, max_steps=max_steps, allowed_capabilities=("finance_query",)),
        trace_parent_id=uuid4().hex,
    )
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki",
    )
    # Keep real query parsing, cutoff and runner, without unrelated prefetch/tools.
    registry = ResearchToolRegistry((registry.resolve("finance_query"),))
    return frame, context, registry, path


def _execute(registry, context, arguments):
    return registry.execute(
        "finance_query", arguments, context=context, step_id=uuid4().hex,
    )


def test_error_empty_and_missing_table_are_distinct(tmp_path):
    _, context, registry, path = _setup(tmp_path)
    before = path.read_bytes()
    invalid = _execute(registry, context, _request())
    empty = _execute(registry, context, _request(
        metrics=["index_return_pct"],
        filters=[{"field": "stage_day", "op": "eq", "value": 99}],
    ))
    good = _execute(registry, context, _request(metrics=["index_return_pct"]))
    assert invalid.trace.status == "parse_error"
    assert "stage_day→market_daily.dimension" in invalid.observation
    assert not invalid.evidence
    assert empty.trace.status == "empty"
    assert "重试提示" not in empty.observation
    assert not empty.evidence
    assert good.trace.status == "success"
    assert len(good.evidence) == 1
    assert "1.25" in good.observation
    assert path.read_bytes() == before

    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    _, context, registry, _ = _setup(missing_root, table=False)
    missing = _execute(registry, context, _request(metrics=["index_return_pct"]))
    assert missing.trace.status == "request_error"
    assert "数据源暂不可用" in missing.observation
    assert "重试提示" not in missing.observation
    assert "fact_market_daily" not in missing.observation
    assert not missing.evidence


@pytest.mark.parametrize("placement", ["metric", "dataset", "exception"])
def test_validation_diagnostic_does_not_echo_arbitrary_prose(placement):
    prose = "forbidden-prose: secret/path future market fact 99%"
    arguments = _request()
    message = prose
    if placement == "metric":
        arguments["metrics"] = [prose]
        message = f"not a metric: {prose}"
    elif placement == "dataset":
        arguments["dataset"] = prose
        message = f"unknown dataset: {prose}"
    result = episode_tools._finance_query_failure_result(
        finance_query.FinanceQuerySpec.from_arguments(arguments),
        finance_query.FinanceQueryValidationError(message),
    )
    assert not result.evidence
    assert "forbidden-prose" not in result.observation
    assert "secret/path" not in result.observation
    assert "99%" not in result.observation
    assert "重试提示" in result.observation


@pytest.mark.parametrize(("error_type", "expected"), [
    (finance_query.FinanceQueryTimedOut, "结构化查询超时"),
    (finance_query.FinanceQueryCancelled, "结构化查询已取消"),
    (finance_query.FinanceQueryLimitExceeded, "结构化查询结果超过资源上限"),
    (finance_query.FinanceQueryExecutionError, "结构化数据源暂不可用"),
])
def test_runtime_errors_keep_safe_distinct_diagnostics(tmp_path, monkeypatch, error_type, expected):
    _, context, registry, _ = _setup(tmp_path)

    def fail(*args, **kwargs):
        raise error_type("secret/path physical_table forbidden-provider-text")

    monkeypatch.setattr(finance_query.FinanceQuery, "run", fail)
    result = _execute(registry, context, _request(metrics=["index_return_pct"]))
    assert not result.evidence
    assert expected in result.observation
    assert "secret/path" not in result.observation
    assert "forbidden-provider-text" not in result.observation
    assert "重试提示" not in result.observation


class _RepairConsumer:
    def __init__(self, *, cancel=None, correct_first=False):
        self.cancel = cancel
        self.correct_first = correct_first
        self.seen = []

    def complete(self, *, messages, tools, timeout):
        observed = [json.loads(m["content"]) for m in messages if m.get("role") == "tool"]
        self.seen = observed
        if not observed:
            arguments = _request(metrics=["index_return_pct"]) if self.correct_first else _request()
        elif len(observed) == 1 and not self.correct_first:
            assert "stage_day→market_daily.dimension" in observed[-1]["observation"]
            assert "重试提示" in observed[-1]["observation"]
            assert not observed[-1]["evidence"]
            arguments = _request(
                dimensions=["trade_date", "stage_day"], metrics=["index_return_pct"],
            )
            if self.cancel is not None:
                self.cancel.set()
        else:
            assert observed[-1]["evidence"]
            return _finish_turn(
                status="partial", draft="Only diagnostic delivery is exercised.",
                hashes=(), gap="Full research quality is not exercised.",
            )
        return ModelTurn(
            "", (ModelToolCall(f"query-{len(observed)}", "finance_query", arguments),),
            "scripted-feedback", "",
        )


@pytest.mark.parametrize("correct_first", [False, True])
def test_episode_delivers_feedback_and_executes_only_requested_queries(tmp_path, correct_first):
    frame, context, registry, path = _setup(tmp_path)
    before = path.read_bytes()
    model = _RepairConsumer(correct_first=correct_first)
    result = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert result.stop_reason == "model_finish"
    expected = 1 if correct_first else 2
    assert result.usage.tool_calls == expected
    assert len(model.seen) == expected
    events = [event for event in result.events if event.kind == "tool_result"]
    assert len(events) == expected
    if not correct_first:
        assert "stage_day→market_daily.dimension" in events[0].payload["model_content"]
    assert path.read_bytes() == before


def test_cancellation_after_feedback_prevents_repair_dispatch(tmp_path):
    frame, context, registry, _ = _setup(tmp_path)
    cancelled = Event()
    model = _RepairConsumer(cancel=cancelled)
    result = ContinuousAgentEpisode(model, is_cancelled=cancelled.is_set).run(
        task_frame=frame, context=context, registry=registry,
    )
    assert result.stop_reason == "cancelled"
    assert result.usage.tool_calls == 1
    assert not result.evidence
    assert len([event for event in result.events if event.kind == "tool_result"]) == 1


def test_no_extra_tool_slot_is_minted_for_query_repair(tmp_path):
    frame, context, registry, _ = _setup(tmp_path, max_steps=1)
    model = _RepairConsumer()
    result = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert result.usage.tool_calls == 1
    assert not result.evidence
    assert len([event for event in result.events if event.kind == "tool_result"]) == 1
