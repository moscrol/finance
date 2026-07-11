"""Versioned stream envelopes and PR181 report-event compatibility aliases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STREAM_SCHEMA_VERSION = 1

LEGACY_TO_CANONICAL = {
    "report_start": "report.start",
    "report_module": "report.module",
    "report_complete": "report.complete",
    "report_error": "report.error",
}
CANONICAL_TO_LEGACY = {value: key for key, value in LEGACY_TO_CANONICAL.items()}


def canonical_event_type(event_type: str) -> str:
    return LEGACY_TO_CANONICAL.get(event_type, event_type)


def legacy_event_type(event_type: str) -> str | None:
    return CANONICAL_TO_LEGACY.get(event_type)


@dataclass(frozen=True)
class StreamEnvelope:
    schema_version: int
    event_id: str
    event_type: str
    run_id: str
    conversation_id: str | None
    message_id: str | None
    seq: int
    created_at: str
    payload: dict[str, Any]
