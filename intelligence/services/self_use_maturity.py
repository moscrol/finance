"""Private self-use event ledger for the Workbench maturity gate."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path

from intelligence.services.run_store import redact


WORKFLOWS = frozenset(
    {
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    }
)
OUTCOMES = frozenset({"success", "degraded", "failed"})

_LEDGER_LOCKS: dict[str, threading.Lock] = {}
_LEDGER_LOCKS_GUARD = threading.Lock()


def _ledger_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LEDGER_LOCKS_GUARD:
        return _LEDGER_LOCKS.setdefault(key, threading.Lock())


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class SelfUseEvent:
    trade_date: str
    workflow: str
    outcome: str
    manual_rescue: bool
    severe_fact_error: bool
    useful: bool
    note: str = ""
    run_id: str | None = None
    recorded_at: str | None = None
    schema_version: int = 1

    def validated(self) -> SelfUseEvent:
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
            workflow=workflow,
            outcome=outcome,
            note=note,
            run_id=run_id,
            recorded_at=recorded_at,
        )


class SelfUseLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, event: SelfUseEvent) -> SelfUseEvent:
        validated = event.validated()
        line = json.dumps(asdict(validated), ensure_ascii=False) + "\n"
        with _ledger_lock(self.path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
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
            for line in handle:
                if line.strip():
                    events.append(SelfUseEvent(**json.loads(line)).validated())
        return events
