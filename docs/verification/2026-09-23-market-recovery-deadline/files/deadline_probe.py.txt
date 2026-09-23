"""Deterministic deadline checks; no real scheduler or database is required."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from intelligence.services import finance_query as fq
from intelligence.services import research_contract as contract


@pytest.fixture
def harness(monkeypatch):
    state = SimpleNamespace(
        now=100.0,
        delay_at="",
        delay=0.2,
        executed=False,
        interrupted=False,
        closed=False,
        cancelled=False,
        target=None,
        run_monitor=False,
        cancel_at="",
        connected=False,
    )
    clock = SimpleNamespace(monotonic=lambda: state.now)
    # Replace module bindings, not the process-wide time.monotonic function.
    monkeypatch.setattr(fq, "time", clock)
    monkeypatch.setattr(contract, "time", clock)

    def advance(phase):
        if state.cancel_at == phase:
            state.cancelled = True
        if state.delay_at == phase:
            state.now += state.delay

    class MonitorEvent:
        stopped = False
        waits = 0

        def is_set(self):
            return self.stopped

        def set(self):
            self.stopped = True

        def wait(self, timeout):
            if not self.stopped:
                self.waits += 1
                assert self.waits < 100, "monitor failed to interrupt"
                state.now += timeout
            return self.stopped

    class DeferredThread:
        def __init__(self, *, target, **kwargs):
            state.target = target

        def start(self):
            advance("thread_start")

        def join(self, *, timeout):
            pass

    class Connection:
        def execute(self, sql, parameters):
            state.executed = True
            advance("execute")
            if state.run_monitor:
                state.target()
                assert state.interrupted
                raise RuntimeError("interrupted")
            return self

        def fetchmany(self, count):
            advance("fetch")
            return []

        def interrupt(self):
            state.interrupted = True

        def close(self):
            advance("close")
            state.closed = True

    def connect(path, *, read_only):
        assert read_only is True
        state.connected = True
        advance("connect")
        return Connection()

    monkeypatch.setattr(fq, "Event", MonitorEvent)
    monkeypatch.setattr(fq, "Thread", DeferredThread)
    query = fq.FinanceQuery(
        Path("unused.duckdb"),
        connect=connect,
        limits=fq.FinanceQueryLimits(timeout=0.03),
    )
    spec = fq.FinanceQuerySpec.from_arguments(
        {
            "dataset": "market_daily",
            "metrics": ["total_amount"],
            "dimensions": ["trade_date"],
        }
    )
    cutoff = contract.InformationCutoff(date(2026, 7, 24), "requested")

    def run(*, deadline=None):
        return query.run(
            spec,
            information_cutoff=cutoff,
            deadline=deadline or contract.ResearchDeadline.from_timeout(2.0),
            is_cancelled=lambda: state.cancelled,
        )

    return state, run


@pytest.mark.parametrize("phase", ["connect", "thread_start"])
def test_exhausted_setup_never_executes_sql(harness, phase):
    state, run = harness
    state.delay_at = phase
    with pytest.raises(fq.FinanceQueryTimedOut):
        run()
    assert not state.executed
    assert state.closed


def test_late_monitor_does_not_restart_timeout(harness):
    state, run = harness
    state.delay_at = "execute"
    state.run_monitor = True
    with pytest.raises(fq.FinanceQueryTimedOut):
        run()
    assert state.interrupted
    assert state.closed
    assert state.now == pytest.approx(100.2)


@pytest.mark.parametrize("phase", ["execute", "fetch", "close"])
def test_late_result_is_not_success_even_without_monitor_scheduling(harness, phase):
    state, run = harness
    state.delay_at = phase
    with pytest.raises(fq.FinanceQueryTimedOut):
        run()
    assert state.closed


def test_root_synthesis_reserve_is_not_regranted(harness):
    state, run = harness
    state.delay_at = "connect"
    state.delay = 0.02
    with pytest.raises(fq.FinanceQueryTimedOut):
        run(deadline=contract.ResearchDeadline(100.51, synthesis_reserve=0.5))
    assert not state.executed
    assert state.closed


def test_query_within_budget_returns_and_closes(harness):
    state, run = harness
    state.delay_at = "connect"
    state.delay = 0.01
    result = run()
    assert result.rows == ()
    assert state.executed
    assert state.closed
    assert not state.interrupted


def test_monitor_interrupts_at_original_deadline(harness):
    state, run = harness
    state.run_monitor = True
    with pytest.raises(fq.FinanceQueryTimedOut):
        run()
    assert state.interrupted
    assert state.closed
    assert state.now == pytest.approx(100.03)


def test_connection_time_is_deducted_from_monitor_budget(harness):
    state, run = harness
    state.delay_at = "connect"
    state.delay = 0.02
    state.run_monitor = True
    with pytest.raises(fq.FinanceQueryTimedOut):
        run()
    assert state.interrupted
    assert state.closed
    assert state.now == pytest.approx(100.03)


@pytest.mark.parametrize("phase", ["connect", "thread_start"])
def test_cancelled_during_setup_never_executes_sql(harness, phase):
    state, run = harness
    state.cancel_at = phase
    with pytest.raises(fq.FinanceQueryCancelled):
        run()
    assert not state.executed
    assert state.closed


def test_monitor_preserves_cancellation_reason(harness):
    state, run = harness
    state.cancel_at = "execute"
    state.run_monitor = True
    with pytest.raises(fq.FinanceQueryCancelled):
        run()
    assert state.interrupted
    assert state.closed


def test_exhausted_root_never_opens_connection(harness):
    state, run = harness
    with pytest.raises(fq.FinanceQueryTimedOut):
        run(deadline=contract.ResearchDeadline(100.0))
    assert not state.connected
    assert not state.executed
