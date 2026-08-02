from __future__ import annotations

import json
import sys

import pytest

from intelligence.services.agent_runtime_factory import (
    resolve_runtime_backend,
    runtime_backend_readiness,
)


def test_default_runtime_backend_preserves_continuous_glm(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_RUNTIME_BACKEND", raising=False)

    selection = resolve_runtime_backend()

    assert selection.name == "continuous_glm"
    assert selection.benchmark_only is False


def test_codex_headless_is_explicitly_benchmark_only(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "codex_headless")

    selection = resolve_runtime_backend()

    assert selection.name == "codex_headless"
    assert selection.benchmark_only is True


def test_codex_headless_readiness_accepts_explicit_cli_path(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "codex_headless")
    monkeypatch.setenv("AGENT_RUNTIME_BENCHMARK_ENABLE", "1")
    monkeypatch.setenv("CODEX_HEADLESS_BIN", sys.executable)

    readiness = runtime_backend_readiness()

    assert readiness.ready is True
    assert readiness.reason == "ready"
    assert readiness.benchmark_only is True


def test_sdk_gpt_readiness_accepts_session_openai_provider(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    readiness = runtime_backend_readiness(
        resolve_runtime_backend("sdk_gpt"),
        session_provider="openai",
        session_model="gpt-5.6-sol",
    )

    assert readiness.ready is True
    assert readiness.reason == "ready"
    assert readiness.credential_available is True
    assert readiness.model == "gpt-5.6-sol"


def test_sdk_gpt_readiness_exposes_non_secret_cockpit_identity(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "never-print")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:57244/v1")
    monkeypatch.setenv("OPENAI_AGENT_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("AGENT_RUNTIME_PROVIDER_LABEL", "cockpit_local")

    readiness = runtime_backend_readiness(
        resolve_runtime_backend("sdk_gpt"),
        provider_chain_size=1,
    )

    payload = readiness.to_dict()
    assert readiness.provider_label == "cockpit_local"
    assert readiness.provider_protocol == "openai_responses"
    assert readiness.provider_chain_size == 1
    assert len(readiness.endpoint_fingerprint) == 64
    assert "never-print" not in json.dumps(payload)
    assert "57244" not in json.dumps(payload)


def test_unknown_runtime_backend_fails_without_fallback(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "mystery")

    with pytest.raises(RuntimeError, match="unsupported agent runtime backend"):
        resolve_runtime_backend()
