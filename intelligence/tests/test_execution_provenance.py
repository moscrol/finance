from __future__ import annotations

from collections.abc import Mapping

import pytest

from intelligence.services.execution_provenance import (
    EXECUTION_PATHS,
    RuntimeExecutionIdentity,
    validate_execution_path,
)


def _identity() -> RuntimeExecutionIdentity:
    return RuntimeExecutionIdentity(
        runtime_instance_id="runtime-a",
        source_revision="a" * 40,
        source_dirty=False,
        code_root="/candidate",
        import_root="/candidate",
        python_executable="/python",
        backend="sdk_gpt",
        model="gpt-5.6-sol",
        provider_label="cockpit_local",
        provider_protocol="openai_responses",
        endpoint_fingerprint="b" * 64,
    )


def test_execution_paths_are_closed_enum() -> None:
    assert EXECUTION_PATHS == {
        "continuous_episode",
        "continuous_fast_path",
        "continuous_clarification",
        "legacy_direct",
    }
    assert validate_execution_path("continuous_episode") == "continuous_episode"


@pytest.mark.parametrize("value", ["", "unknown", None, True])
def test_invalid_execution_path_fails_closed(value: object) -> None:
    with pytest.raises(ValueError):
        validate_execution_path(value)  # type: ignore[arg-type]


def test_runtime_identity_from_payload_rejects_missing_agent_runtime() -> None:
    with pytest.raises(ValueError, match="agent_runtime"):
        RuntimeExecutionIdentity.from_runtime_payload(
            {"runtime_instance_id": "runtime-a"}
        )


def test_runtime_identity_from_payload_does_not_retain_unknown_secret_fields() -> None:
    payload: Mapping[str, object] = {
        "runtime_instance_id": "runtime-a",
        "source_revision": "a" * 40,
        "source_dirty": False,
        "code_root": "/candidate",
        "import_root": "/candidate",
        "python_executable": "/python",
        "api_key": "never-write",
        "agent_runtime": {
            "backend": "sdk_gpt",
            "model": "gpt-5.6-sol",
            "provider_label": "cockpit_local",
            "provider_protocol": "openai_responses",
            "endpoint_fingerprint": "b" * 64,
        },
    }

    identity = RuntimeExecutionIdentity.from_runtime_payload(payload)

    assert "never-write" not in repr(identity)
