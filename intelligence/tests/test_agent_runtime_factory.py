from __future__ import annotations

import sys

import pytest

from intelligence.runtime.agent_runtime_factory import (
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


def test_continuous_runtime_accepts_a_session_openai_provider(monkeypatch) -> None:
    """壳的选择与模型的选择是两个正交的轴。

    回归：凭证门只认 zhipu，把 provider-neutral 的 Continuous 壳锁死在 GLM 上
    （`GLMModelClient` 的 docstring 明写 adapter 本身 provider-neutral）。后果是
    「想用自建壳就只能用 GLM」，而 2026-07-25 同模型九题盲评是 Continuous 195 /
    SDK 175——换模型不该被迫连壳一起换。
    """
    for name in ("FORESIGHT_BUILTIN_LLM_API_KEY", "ZHIPU_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    readiness = runtime_backend_readiness(
        resolve_runtime_backend("continuous_glm"),
        session_provider="openai",
        session_model="gpt-5.6-sol",
    )

    assert readiness.ready is True
    assert readiness.reason == "ready"
    assert readiness.credential_available is True
    # 报的必须是生效值（BYOK 实际拿到的模型），不是那个历史默认 glm-5.2。
    assert readiness.model == "gpt-5.6-sol"


def test_continuous_runtime_accepts_openai_env_credential(monkeypatch) -> None:
    for name in ("FORESIGHT_BUILTIN_LLM_API_KEY", "ZHIPU_API_KEY", "GLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")

    readiness = runtime_backend_readiness(resolve_runtime_backend("continuous_glm"))

    assert readiness.ready is True
    assert readiness.credential_available is True


def test_continuous_runtime_without_any_credential_is_not_ready(monkeypatch) -> None:
    """放开 provider 不等于放开「没有凭证也算就绪」。"""
    for name in (
        "FORESIGHT_BUILTIN_LLM_API_KEY", "ZHIPU_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    readiness = runtime_backend_readiness(resolve_runtime_backend("continuous_glm"))

    assert readiness.ready is False
    assert readiness.credential_available is False
    # 理由不再谎称「缺 GLM key」——缺的是任一可用凭证。
    assert readiness.reason == "llm_credential_missing"


def test_unknown_runtime_backend_fails_without_fallback(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "mystery")

    with pytest.raises(RuntimeError, match="unsupported agent runtime backend"):
        resolve_runtime_backend()
