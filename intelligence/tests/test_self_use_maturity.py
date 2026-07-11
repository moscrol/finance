from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from intelligence.services import self_use_maturity
from intelligence.services.self_use_maturity import SelfUseEvent, SelfUseLedger


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


def test_load_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"workflow": ', encoding="utf-8")

    with pytest.raises(ValueError):
        SelfUseLedger(path).load()


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
