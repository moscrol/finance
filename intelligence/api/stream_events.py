"""Versioned stream envelopes and canonical event registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LEGACY_TO_CANONICAL = {
    "report_start": "report.start",
    "report_module": "report.module",
    "report_complete": "report.complete",
    "report_error": "report.error",
}
CANONICAL_TO_LEGACY = {value: key for key, value in LEGACY_TO_CANONICAL.items()}
STREAM_EVENT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "contracts" / "stream_events.json"
)


@dataclass(frozen=True)
class StreamEventDefinition:
    event_type: str
    payload_schema: dict[str, Any]
    public: bool
    terminal: bool
    ui_renderer: str


def _load_registry() -> tuple[int, dict[str, StreamEventDefinition]]:
    raw = json.loads(STREAM_EVENT_REGISTRY_PATH.read_text(encoding="utf-8"))
    version = int(raw["schema_version"])
    definitions: dict[str, StreamEventDefinition] = {}
    for item in raw["events"]:
        definition = StreamEventDefinition(
            event_type=str(item["event_type"]),
            payload_schema=dict(item["payload_schema"]),
            public=bool(item["public"]),
            terminal=bool(item["terminal"]),
            ui_renderer=str(item["ui_renderer"]),
        )
        if definition.event_type in definitions:
            raise ValueError(
                f"duplicate stream event type: {definition.event_type}"
            )
        definitions[definition.event_type] = definition
    return version, definitions


STREAM_SCHEMA_VERSION, STREAM_EVENT_REGISTRY = _load_registry()
PUBLIC_EVENT_TYPES = frozenset(
    event_type
    for event_type, definition in STREAM_EVENT_REGISTRY.items()
    if definition.public
)
TERMINAL_EVENT_TYPES = frozenset(
    event_type
    for event_type, definition in STREAM_EVENT_REGISTRY.items()
    if definition.terminal
)


def canonical_event_type(event_type: str) -> str:
    return LEGACY_TO_CANONICAL.get(event_type, event_type)


def legacy_event_type(event_type: str) -> str | None:
    return CANONICAL_TO_LEGACY.get(event_type)


def event_definition(event_type: str) -> StreamEventDefinition | None:
    return STREAM_EVENT_REGISTRY.get(canonical_event_type(event_type))


def payload_schema_errors(
    event_type: str,
    payload: dict[str, Any],
) -> tuple[str, ...]:
    definition = event_definition(event_type)
    if definition is None:
        return ("unregistered_event_type",)
    required = definition.payload_schema.get("required", [])
    if not isinstance(required, list):
        return ("invalid_registry_payload_schema",)
    return tuple(
        f"missing_payload_field:{field}"
        for field in required
        if isinstance(field, str) and field not in payload
    )


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
