from __future__ import annotations

import json
import multiprocessing
import os
import stat
from dataclasses import FrozenInstanceError, asdict
from datetime import datetime
from typing import Any, get_args, get_type_hints

import pytest

from intelligence.services import self_use_maturity
from intelligence.services.self_use_maturity import (
    MaturityResult,
    SelfUseEvent,
    SelfUseLedger,
    SelfUseLedgerIntegrityError,
    evaluate_maturity,
)


def _record_from_process(path: str, start_event: Any, index: int) -> None:
    start_event.wait(timeout=10)
    SelfUseLedger(path).record(
        SelfUseEvent(
            trade_date="2026-07-11",
            workflow="daily_market",
            outcome="success",
            manual_rescue=False,
            severe_fact_error=False,
            useful=True,
            run_id=f"run_{index}",
        )
    )


def make_event(**overrides: object) -> SelfUseEvent:
    values: dict[str, object] = {
        "trade_date": "2026-07-11",
        "workflow": "daily_market",
        "outcome": "success",
        "manual_rescue": False,
        "severe_fact_error": False,
        "useful": True,
    }
    values.update(overrides)
    return SelfUseEvent(**values)  # type: ignore[arg-type]


def make_complete_maturity_events() -> list[SelfUseEvent]:
    workflows = [
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    ]
    return [
        make_event(trade_date=f"2026-06-{day:02d}", workflow=workflow)
        for day in range(1, 11)
        for workflow in workflows
    ]


def test_complete_ten_day_workflow_set_is_eligible_but_requires_user_approval() -> None:
    result = evaluate_maturity(make_complete_maturity_events())

    assert result.blockers == ()
    assert result.eligible_for_user_decision is True
    assert result.user_approved is False
    assert result.passed is False
    assert result.metrics == {
        "distinct_trade_dates": 10,
        "covered_workflows": [
            "daily_market",
            "news_impact",
            "stock_research",
            "theme_research",
            "watchlist",
        ],
        "core_success_rate": 1.0,
        "useful_rate": 1.0,
        "manual_rescue_rate": 0.0,
        "severe_fact_errors": 0,
        "event_count": 50,
    }


def test_explicit_user_approval_passes_an_eligible_result() -> None:
    result = evaluate_maturity(make_complete_maturity_events(), user_approved=True)

    assert result.eligible_for_user_decision is True
    assert result.user_approved is True
    assert result.passed is True


def test_severe_fact_error_blocks_maturity() -> None:
    events = make_complete_maturity_events()
    events[0] = make_event(
        trade_date=events[0].trade_date,
        workflow=events[0].workflow,
        severe_fact_error=True,
    )

    result = evaluate_maturity(events)

    assert result.metrics["severe_fact_errors"] == 1
    assert result.blockers == ("severe_fact_error",)
    assert result.eligible_for_user_decision is False
    assert result.passed is False


def test_user_approval_cannot_bypass_mechanical_blockers() -> None:
    result = evaluate_maturity([make_event()], user_approved=True)

    assert result.user_approved is True
    assert result.eligible_for_user_decision is False
    assert result.passed is False


def test_rate_thresholds_are_inclusive_at_95_5_and_80_percent() -> None:
    events = [
        make_event(
            trade_date=f"2026-06-{index // 2 + 1:02d}",
            workflow=(
                "daily_market",
                "theme_research",
                "stock_research",
                "news_impact",
                "watchlist",
            )[index % 5],
            outcome="failed" if index == 0 else "success",
            manual_rescue=index == 1,
            useful=index < 16,
        )
        for index in range(20)
    ]

    result = evaluate_maturity(events)

    assert result.blockers == ()
    assert result.metrics["core_success_rate"] == 0.95
    assert result.metrics["manual_rescue_rate"] == 0.05
    assert result.metrics["useful_rate"] == 0.8


def test_rates_are_rounded_to_six_decimal_places() -> None:
    events = [
        make_event(
            outcome="failed" if index == 2 else "success",
            manual_rescue=index == 0,
            useful=index < 2,
        )
        for index in range(3)
    ]

    result = evaluate_maturity(events)

    assert result.metrics["core_success_rate"] == 0.666667
    assert result.metrics["manual_rescue_rate"] == 0.333333
    assert result.metrics["useful_rate"] == 0.666667


def test_empty_events_have_zero_rates_and_expected_blockers() -> None:
    result = evaluate_maturity([])

    assert result.metrics == {
        "distinct_trade_dates": 0,
        "covered_workflows": [],
        "core_success_rate": 0.0,
        "useful_rate": 0.0,
        "manual_rescue_rate": 0.0,
        "severe_fact_errors": 0,
        "event_count": 0,
    }
    assert result.blockers == (
        "minimum_trade_dates",
        "missing_workflows",
        "success_rate",
        "useful_rate",
    )


def test_missing_workflow_is_reported_after_minimum_trade_dates_passes() -> None:
    events = [make_event(trade_date=f"2026-06-{day:02d}") for day in range(1, 11)]

    result = evaluate_maturity(events)

    assert result.blockers == ("missing_workflows",)
    assert result.metrics["covered_workflows"] == ["daily_market"]


def test_blockers_follow_stable_contract_order() -> None:
    result = evaluate_maturity(
        [
            make_event(
                outcome="failed",
                manual_rescue=True,
                severe_fact_error=True,
                useful=False,
            )
        ]
    )

    assert result.blockers == (
        "minimum_trade_dates",
        "missing_workflows",
        "success_rate",
        "severe_fact_error",
        "manual_rescue_rate",
        "useful_rate",
    )


def test_evaluation_does_not_mutate_events_or_event_list() -> None:
    events = make_complete_maturity_events()
    original_events = list(events)
    original_payloads = [asdict(event) for event in events]

    result = evaluate_maturity(events)

    assert events == original_events
    assert [asdict(event) for event in events] == original_payloads
    with pytest.raises(FrozenInstanceError):
        result.passed = True  # type: ignore[misc]
    assert isinstance(result, MaturityResult)


def test_record_appends_schema_workflow_and_run_id(tmp_path) -> None:
    path = tmp_path / "private" / "self-use" / "events.jsonl"
    ledger = SelfUseLedger(path)

    saved = ledger.record(make_event(run_id="run_20260711_001"))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["workflow"] == "daily_market"
    assert payload["run_id"] == "run_20260711_001"
    assert saved.run_id == "run_20260711_001"


def test_self_use_event_is_frozen() -> None:
    event = make_event()

    with pytest.raises(FrozenInstanceError):
        event.useful = False  # type: ignore[misc]

    hints = get_type_hints(SelfUseEvent)
    assert get_args(hints["workflow"]) == (
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    )
    assert get_args(hints["outcome"]) == ("success", "degraded", "failed")


@pytest.mark.parametrize(
    "workflow",
    [
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    ],
)
def test_record_accepts_each_supported_workflow(tmp_path, workflow: str) -> None:
    path = tmp_path / f"{workflow}.jsonl"

    SelfUseLedger(path).record(make_event(workflow=workflow))

    assert json.loads(path.read_text(encoding="utf-8"))["workflow"] == workflow


def test_invalid_workflow_does_not_create_file(tmp_path) -> None:
    path = tmp_path / "self-use" / "events.jsonl"

    with pytest.raises(ValueError, match="workflow"):
        SelfUseLedger(path).record(make_event(workflow="freeform"))

    assert not path.exists()
    assert not path.parent.exists()


@pytest.mark.parametrize("outcome", ["partial", "", "SUCCESS"])
def test_invalid_outcome_does_not_create_file(tmp_path, outcome: str) -> None:
    path = tmp_path / "events.jsonl"

    with pytest.raises(ValueError, match="outcome"):
        SelfUseLedger(path).record(make_event(outcome=outcome))

    assert not path.exists()


@pytest.mark.parametrize("trade_date", ["2026-02-30", "2026/07/11", "20260711"])
def test_invalid_trade_date_does_not_create_file(tmp_path, trade_date: str) -> None:
    path = tmp_path / "events.jsonl"

    with pytest.raises(ValueError, match="trade_date"):
        SelfUseLedger(path).record(make_event(trade_date=trade_date))

    assert not path.exists()


def test_invalid_schema_version_does_not_create_file(tmp_path) -> None:
    path = tmp_path / "events.jsonl"

    with pytest.raises(ValueError, match="schema_version"):
        SelfUseLedger(path).record(make_event(schema_version=2))

    assert not path.exists()


def test_record_redacts_and_limits_note_and_redacts_run_id(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    secret = "sk-" + "supersecret12345678"

    saved = SelfUseLedger(path).record(
        make_event(
            note=f"  token={secret} " + "x" * 1100,
            run_id=f"authorization={secret}",
        )
    )

    assert secret not in saved.note
    assert saved.note.startswith("[REDACTED]")
    assert len(saved.note) == 1000
    assert saved.run_id == "[REDACTED]"
    assert secret not in path.read_text(encoding="utf-8")


def test_record_appends_to_existing_line_and_loads_validated_events(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    first = make_event(
        workflow="theme_research",
        recorded_at="2026-07-11T09:00:00+08:00",
    )
    path.write_text(json.dumps(first.__dict__, ensure_ascii=False) + "\n", encoding="utf-8")

    SelfUseLedger(path).record(make_event(workflow="stock_research"))

    loaded = SelfUseLedger(path).load()
    assert [event.workflow for event in loaded] == ["theme_research", "stock_research"]
    assert all(event.recorded_at for event in loaded)
    assert datetime.fromisoformat(loaded[1].recorded_at or "").tzinfo is not None


def test_load_missing_file_returns_empty_list(tmp_path) -> None:
    assert SelfUseLedger(tmp_path / "missing.jsonl").load() == []


def test_load_reports_path_line_and_cause_for_malformed_json(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    first = asdict(make_event(recorded_at="2026-07-11T09:00:00+08:00"))
    path.write_text(json.dumps(first) + '\n{"workflow": ', encoding="utf-8")

    with pytest.raises(SelfUseLedgerIntegrityError) as exc_info:
        SelfUseLedger(path).load()

    assert str(path) in str(exc_info.value)
    assert "line 2" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.pop("workflow"),
        lambda payload: payload.pop("recorded_at"),
        lambda payload: payload.update({"unexpected": True}),
        lambda payload: payload.update({"recorded_at": None}),
    ],
    ids=[
        "missing-required-field",
        "missing-recorded-at",
        "extra-field",
        "null-recorded-at",
    ],
)
def test_load_wraps_schema_errors_without_backfilling_recorded_at(
    tmp_path, mutation
) -> None:
    path = tmp_path / "events.jsonl"
    payload = asdict(make_event(recorded_at="2026-07-11T09:00:00+08:00"))
    mutation(payload)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(SelfUseLedgerIntegrityError) as exc_info:
        SelfUseLedger(path).load()

    assert str(path) in str(exc_info.value)
    assert "line 1" in str(exc_info.value)
    assert exc_info.value.__cause__ is not None


def test_failed_replace_leaves_existing_ledger_unchanged(tmp_path, monkeypatch) -> None:
    path = tmp_path / "events.jsonl"
    original = b'{"existing": true}\n'
    path.write_bytes(original)

    def fail_replace(_source, _destination) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(self_use_maturity.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated"):
        SelfUseLedger(path).record(make_event())

    assert path.read_bytes() == original
    assert list(tmp_path.glob(".events.jsonl.*.tmp")) == []


def test_record_fsyncs_file_then_replaces_then_fsyncs_parent(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "events.jsonl"
    calls: list[str] = []
    real_fsync = os.fsync
    real_replace = os.replace

    def tracking_fsync(fd: int) -> None:
        calls.append("dir_fsync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file_fsync")
        real_fsync(fd)

    def tracking_replace(source, destination) -> None:
        calls.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(self_use_maturity.os, "fsync", tracking_fsync)
    monkeypatch.setattr(self_use_maturity.os, "replace", tracking_replace)

    SelfUseLedger(path).record(make_event())

    assert calls == ["file_fsync", "replace", "dir_fsync"]
    assert len(SelfUseLedger(path).load()) == 1


def test_concurrent_processes_do_not_lose_appends(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    processes = [
        context.Process(target=_record_from_process, args=(str(path), start_event, index))
        for index in range(8)
    ]
    for process in processes:
        process.start()
    start_event.set()
    for process in processes:
        process.join(timeout=15)

    assert [process.exitcode for process in processes] == [0] * len(processes)
    assert {event.run_id for event in SelfUseLedger(path).load()} == {
        f"run_{index}" for index in range(8)
    }
