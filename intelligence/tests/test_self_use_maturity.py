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
    SelfUseEvent,
    SelfUseLedger,
    SelfUseLedgerIntegrityError,
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
