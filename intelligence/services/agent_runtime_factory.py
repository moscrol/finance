"""Explicit composition metadata for replaceable agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass
import os
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


__all__ = [
    "RuntimeBackendName",
    "RuntimeBackendSelection",
    "resolve_runtime_backend",
]
