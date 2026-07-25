"""Explicit composition metadata for replaceable agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
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

    def to_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "ready": self.ready,
            "reason": self.reason,
            "model": self.model,
            "credential_available": self.credential_available,
            "benchmark_only": self.benchmark_only,
        }


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
) -> RuntimeBackendReadiness:
    selected = selection or resolve_runtime_backend()
    if selected.name in {"continuous_glm", "sdk_glm"}:
        credential = bool(
            os.environ.get("FORESIGHT_BUILTIN_LLM_API_KEY")
            or os.environ.get("ZHIPU_API_KEY")
            or os.environ.get("GLM_API_KEY")
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
        return RuntimeBackendReadiness(
            backend=selected.name,
            ready=credential and dependency_ready,
            reason=reason,
            model=str(
                os.environ.get("FORESIGHT_BUILTIN_LLM_MODEL") or "glm-5.2"
            ).strip(),
            credential_available=credential,
            benchmark_only=selected.benchmark_only,
        )
    if selected.name == "sdk_gpt":
        credential = bool(os.environ.get("OPENAI_API_KEY"))
        dependency_ready = importlib.util.find_spec("agents") is not None
        if not dependency_ready:
            reason = "openai_agents_dependency_missing"
        elif not credential:
            reason = "openai_api_key_missing"
        else:
            reason = "ready"
        return RuntimeBackendReadiness(
            backend=selected.name,
            ready=credential and dependency_ready,
            reason=reason,
            model=str(
                os.environ.get("OPENAI_AGENT_MODEL") or "gpt-5.6-sol"
            ).strip(),
            credential_available=credential,
            benchmark_only=False,
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
    )


__all__ = [
    "RuntimeBackendName",
    "RuntimeBackendReadiness",
    "RuntimeBackendSelection",
    "resolve_runtime_backend",
    "runtime_backend_readiness",
]
