"""Private self-use event ledger for the Workbench maturity gate."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Literal, cast

from intelligence.services.run_store import redact


Workflow = Literal[
    "daily_market",
    "theme_research",
    "stock_research",
    "news_impact",
    "watchlist",
]
Outcome = Literal["success", "degraded", "failed"]

WORKFLOWS: frozenset[str] = frozenset(
    {
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    }
)
OUTCOMES: frozenset[str] = frozenset({"success", "degraded", "failed"})


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class SelfUseEvent:
    trade_date: str
    workflow: Workflow
    outcome: Outcome
    manual_rescue: bool
    severe_fact_error: bool
    useful: bool
    note: str = ""
    run_id: str | None = None
    recorded_at: str | None = None
    schema_version: int = 1

    def validated(self, *, generate_recorded_at: bool = True) -> SelfUseEvent:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError(f"invalid schema_version: {self.schema_version!r}")
        if not isinstance(self.trade_date, str):
            raise ValueError("trade_date must be an ISO date string")
        trade_date = self.trade_date.strip()
        try:
            parsed_trade_date = date.fromisoformat(trade_date)
        except ValueError as exc:
            raise ValueError(f"invalid trade_date: {self.trade_date!r}") from exc
        if parsed_trade_date.isoformat() != trade_date:
            raise ValueError(f"invalid trade_date: {self.trade_date!r}")
        if not isinstance(self.workflow, str):
            raise ValueError("workflow must be a string")
        workflow = self.workflow.strip()
        if workflow not in WORKFLOWS:
            raise ValueError(f"invalid workflow: {self.workflow!r}")
        if not isinstance(self.outcome, str):
            raise ValueError("outcome must be a string")
        outcome = self.outcome.strip()
        if outcome not in OUTCOMES:
            raise ValueError(f"invalid outcome: {self.outcome!r}")
        for field_name in ("manual_rescue", "severe_fact_error", "useful"):
            if type(getattr(self, field_name)) is not bool:
                raise ValueError(f"{field_name} must be a boolean")
        if not isinstance(self.note, str):
            raise ValueError("note must be a string")
        if self.run_id is not None and not isinstance(self.run_id, str):
            raise ValueError("run_id must be a string or None")

        note = redact(self.note.strip())[:1000]
        run_id = redact(self.run_id.strip()) if self.run_id is not None else None
        if run_id == "":
            run_id = None

        if self.recorded_at is not None and not isinstance(self.recorded_at, str):
            raise ValueError("recorded_at must be an ISO datetime string or None")
        if self.recorded_at is None and not generate_recorded_at:
            raise ValueError("recorded_at is required when loading a persisted event")
        recorded_at = self.recorded_at.strip() if self.recorded_at is not None else _now_iso()
        try:
            parsed_recorded_at = datetime.fromisoformat(recorded_at)
        except ValueError as exc:
            raise ValueError(f"invalid recorded_at: {self.recorded_at!r}") from exc
        if parsed_recorded_at.tzinfo is None or parsed_recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must include a timezone offset")

        return replace(
            self,
            trade_date=trade_date,
            workflow=cast(Workflow, workflow),
            outcome=cast(Outcome, outcome),
            note=note,
            run_id=run_id,
            recorded_at=recorded_at,
        )


@dataclass(frozen=True)
class MaturityResult:
    metrics: dict[str, float | int | list[str]]
    blockers: tuple[str, ...]
    eligible_for_user_decision: bool
    user_approved: bool
    passed: bool


def evaluate_maturity(
    events: list[SelfUseEvent], *, user_approved: bool = False
) -> MaturityResult:
    """Evaluate deterministic self-use maturity without mutating the ledger."""

    if type(user_approved) is not bool:
        raise TypeError("user_approved must be a boolean")
    validated_events = [event.validated() for event in events]
    event_count = len(validated_events)
    trade_dates = {event.trade_date for event in validated_events}
    covered_workflows = sorted({event.workflow for event in validated_events})
    success_count = sum(event.outcome == "success" for event in validated_events)
    useful_count = sum(event.useful for event in validated_events)
    manual_rescue_count = sum(event.manual_rescue for event in validated_events)
    severe_fact_errors = sum(event.severe_fact_error for event in validated_events)

    def rate(numerator: int) -> float:
        return round(numerator / event_count, 6) if event_count else 0.0

    metrics: dict[str, float | int | list[str]] = {
        "distinct_trade_dates": len(trade_dates),
        "covered_workflows": covered_workflows,
        "core_success_rate": rate(success_count),
        "useful_rate": rate(useful_count),
        "manual_rescue_rate": rate(manual_rescue_count),
        "severe_fact_errors": severe_fact_errors,
        "event_count": event_count,
    }

    blockers: list[str] = []
    if len(trade_dates) < 10:
        blockers.append("minimum_trade_dates")
    if set(covered_workflows) != WORKFLOWS:
        blockers.append("missing_workflows")
    if not event_count or success_count * 100 < event_count * 95:
        blockers.append("success_rate")
    if severe_fact_errors:
        blockers.append("severe_fact_error")
    if event_count and manual_rescue_count * 100 > event_count * 5:
        blockers.append("manual_rescue_rate")
    if not event_count or useful_count * 100 < event_count * 80:
        blockers.append("useful_rate")

    blocker_tuple = tuple(blockers)
    eligible_for_user_decision = not blocker_tuple
    return MaturityResult(
        metrics=metrics,
        blockers=blocker_tuple,
        eligible_for_user_decision=eligible_for_user_decision,
        user_approved=user_approved,
        passed=eligible_for_user_decision and user_approved,
    )


class SelfUseLedgerIntegrityError(ValueError):
    """A JSONL row cannot be decoded into a valid persisted event."""


class SelfUseLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f".{self.path.name}.lock")

    def record(self, event: SelfUseEvent) -> SelfUseEvent:
        validated = event.validated()
        line = json.dumps(asdict(validated), ensure_ascii=False) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            existing = self.path.read_bytes() if self.path.exists() else b""
            separator = b"\n" if existing and not existing.endswith(b"\n") else b""
            fd, temporary_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(existing)
                    handle.write(separator)
                    handle.write(line.encode("utf-8"))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_name, self.path)
                directory_fd = os.open(
                    self.path.parent,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                )
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except BaseException:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
                raise
        return validated

    def load(self) -> list[SelfUseEvent]:
        if not self.path.exists():
            return []
        events: list[SelfUseEvent] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise TypeError("event row must be a JSON object")
                    event = SelfUseEvent(**payload).validated(generate_recorded_at=False)
                except Exception as exc:
                    raise SelfUseLedgerIntegrityError(
                        f"invalid self-use ledger {self.path} at JSONL line {line_number}"
                    ) from exc
                events.append(event)
        return events
