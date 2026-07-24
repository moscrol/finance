from __future__ import annotations

import pytest

from intelligence.services.agent_runtime_factory import resolve_runtime_backend


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


def test_unknown_runtime_backend_fails_without_fallback(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "mystery")

    with pytest.raises(RuntimeError, match="unsupported agent runtime backend"):
        resolve_runtime_backend()
