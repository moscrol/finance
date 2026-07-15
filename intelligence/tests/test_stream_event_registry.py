from __future__ import annotations

import runpy
from pathlib import Path

from intelligence.api.stream_events import (
    PUBLIC_EVENT_TYPES,
    STREAM_EVENT_REGISTRY,
    TERMINAL_EVENT_TYPES,
    event_definition,
    payload_schema_errors,
)


def test_workflow_loaded_is_public_and_schema_bound() -> None:
    definition = event_definition("workflow.loaded")

    assert definition is not None
    assert definition.public is True
    assert definition.terminal is False
    assert definition.ui_renderer == "workflow_status"
    assert payload_schema_errors(
        "workflow.loaded",
        {"owner": "theme-research"},
    ) == (
        "missing_payload_field:label",
        "missing_payload_field:execution_mode",
        "missing_payload_field:preset",
        "missing_payload_field:required_skill_ids",
        "missing_payload_field:retrieval_stages",
        "missing_payload_field:output_schema",
        "missing_payload_field:presentation_kind",
        "missing_payload_field:max_wall_time_seconds",
        "missing_payload_field:status",
    )


def test_every_public_event_has_payload_schema_and_renderer() -> None:
    for event_type in PUBLIC_EVENT_TYPES:
        definition = STREAM_EVENT_REGISTRY[event_type]
        assert definition.payload_schema["type"] == "object"
        assert isinstance(definition.payload_schema["required"], list)
        assert definition.ui_renderer != "none"

    assert TERMINAL_EVENT_TYPES == {
        "message.complete",
        "message.error",
    }


def test_smoke_uses_the_canonical_public_event_registry() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    smoke_globals = runpy.run_path(
        str(repo_root / "scripts" / "smoke_workbench_self_use.py")
    )

    assert smoke_globals["PUBLIC_EVENT_TYPES"] == set(PUBLIC_EVENT_TYPES)
