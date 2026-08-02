"""Explicit composition metadata for replaceable agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import os
import re
import shutil
from typing import Literal, cast


RuntimeBackendName = Literal[
    "continuous_glm",
    "sdk_glm",
    "sdk_gpt",
    "codex_headless",
]
_SUPPORTED_BACKENDS = frozenset(
    {
        "continuous_glm",
        "sdk_glm",
        "sdk_gpt",
        "codex_headless",
    }
)


@dataclass(frozen=True)
class RuntimeBackendSelection:
    name: RuntimeBackendName
    benchmark_only: bool


@dataclass(frozen=True)
class RuntimeBackendReadiness:
    backend: RuntimeBackendName
    ready: bool
    reason: str
    model: str
    credential_available: bool
    benchmark_only: bool
    provider_label: str
    provider_protocol: str
    endpoint_fingerprint: str
    provider_chain_size: int

    def to_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "ready": self.ready,
            "reason": self.reason,
            "model": self.model,
            "credential_available": self.credential_available,
            "benchmark_only": self.benchmark_only,
            "provider_label": self.provider_label,
            "provider_protocol": self.provider_protocol,
            "endpoint_fingerprint": self.endpoint_fingerprint,
            "provider_chain_size": self.provider_chain_size,
        }


def endpoint_fingerprint(base_url: str | None) -> str:
    """Hash a provider endpoint without exposing its URL or credentials."""

    normalized = str(base_url or "").strip().rstrip("/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _provider_label(value: str | None, fallback: str) -> str:
    cleaned = str(value or fallback).strip()
    if not cleaned or re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", cleaned) is None:
        return fallback
    return cleaned


def _environment_provider_chain_size() -> int:
    """Count configured provider families without reading secret values."""

    if os.environ.get("LLM_API_KEY"):
        return 1
    key_names = (
        "FORESIGHT_BUILTIN_LLM_API_KEY",
        "ZHIPU_API_KEY",
        "GLM_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "KIMI_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "OPENAI_API_KEY",
    )
    return sum(bool(os.environ.get(name)) for name in key_names)


def _chain_size(value: int | None, *, credential: bool) -> int:
    if value is not None:
        if isinstance(value, bool) or value < 0:
            raise ValueError("provider_chain_size must be a non-negative integer")
        return int(value)
    inferred = _environment_provider_chain_size()
    if inferred:
        return inferred
    return 1 if credential else 0


def resolve_runtime_backend(value: str | None = None) -> RuntimeBackendSelection:
    """Resolve one backend without silently falling back from invalid input."""

    raw = value if value is not None else os.environ.get("AGENT_RUNTIME_BACKEND")
    name = str(raw or "continuous_glm").strip().lower()
    if name not in _SUPPORTED_BACKENDS:
        raise RuntimeError(f"unsupported agent runtime backend: {name}")
    return RuntimeBackendSelection(
        name=cast(RuntimeBackendName, name),
        benchmark_only=name == "codex_headless",
    )


def runtime_backend_readiness(
    selection: RuntimeBackendSelection | None = None,
    *,
    session_provider: str | None = None,
    session_model: str | None = None,
    session_base_url: str | None = None,
    provider_chain_size: int | None = None,
) -> RuntimeBackendReadiness:
    selected = selection or resolve_runtime_backend()
    if selected.name in {"continuous_glm", "sdk_glm"}:
        credential = bool(
            os.environ.get("FORESIGHT_BUILTIN_LLM_API_KEY")
            or os.environ.get("ZHIPU_API_KEY")
            or os.environ.get("GLM_API_KEY")
            or session_provider == "zhipu"
        )
        dependency_ready = (
            selected.name != "sdk_glm"
            or importlib.util.find_spec("agents") is not None
        )
        if not dependency_ready:
            reason = "openai_agents_dependency_missing"
        elif not credential:
            reason = "glm_api_key_missing"
        else:
            reason = "ready"
        base_url = (
            session_base_url
            or os.environ.get("FORESIGHT_BUILTIN_LLM_BASE_URL")
            or os.environ.get("LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://open.bigmodel.cn/api/paas/v4"
        )
        provider = _provider_label(
            os.environ.get("AGENT_RUNTIME_PROVIDER_LABEL"),
            session_provider or "zhipu",
        )
        return RuntimeBackendReadiness(
            backend=selected.name,
            ready=credential and dependency_ready,
            reason=reason,
            model=str(
                session_model
                or os.environ.get("FORESIGHT_BUILTIN_LLM_MODEL")
                or "glm-5.2"
            ).strip(),
            credential_available=credential,
            benchmark_only=selected.benchmark_only,
            provider_label=provider,
            provider_protocol="openai_chat_completions",
            endpoint_fingerprint=endpoint_fingerprint(base_url),
            provider_chain_size=_chain_size(
                provider_chain_size,
                credential=credential,
            ),
        )
    if selected.name == "sdk_gpt":
        credential = bool(
            os.environ.get("OPENAI_API_KEY") or session_provider == "openai"
        )
        dependency_ready = importlib.util.find_spec("agents") is not None
        if not dependency_ready:
            reason = "openai_agents_dependency_missing"
        elif not credential:
            reason = "openai_api_key_missing"
        else:
            reason = "ready"
        base_url = (
            session_base_url
            or os.environ.get("LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )
        provider = _provider_label(
            os.environ.get("AGENT_RUNTIME_PROVIDER_LABEL"),
            session_provider or "openai",
        )
        return RuntimeBackendReadiness(
            backend=selected.name,
            ready=credential and dependency_ready,
            reason=reason,
            model=str(
                session_model
                or os.environ.get("OPENAI_AGENT_MODEL")
                or "gpt-5.6-sol"
            ).strip(),
            credential_available=credential,
            benchmark_only=False,
            provider_label=provider,
            provider_protocol="openai_responses",
            endpoint_fingerprint=endpoint_fingerprint(base_url),
            provider_chain_size=_chain_size(
                provider_chain_size,
                credential=credential,
            ),
        )

    cli_path = os.environ.get("CODEX_HEADLESS_BIN") or shutil.which("codex")
    cli_ready = bool(cli_path and os.access(cli_path, os.X_OK))
    benchmark_enabled = (
        os.environ.get("AGENT_RUNTIME_BENCHMARK_ENABLE", "").strip() == "1"
    )
    if not cli_ready:
        reason = "codex_cli_missing"
    elif not benchmark_enabled:
        reason = "headless_benchmark_not_enabled"
    else:
        reason = "ready"
    return RuntimeBackendReadiness(
        backend=selected.name,
        ready=cli_ready and benchmark_enabled,
        reason=reason,
        model=str(
            os.environ.get("CODEX_HEADLESS_MODEL") or "codex-account-default"
        ).strip(),
        credential_available=cli_ready,
        benchmark_only=True,
        provider_label="codex_headless",
        provider_protocol="codex_cli",
        endpoint_fingerprint=endpoint_fingerprint(cli_path or ""),
        provider_chain_size=1 if cli_ready else 0,
    )


__all__ = [
    "RuntimeBackendName",
    "RuntimeBackendReadiness",
    "RuntimeBackendSelection",
    "endpoint_fingerprint",
    "resolve_runtime_backend",
    "runtime_backend_readiness",
]
