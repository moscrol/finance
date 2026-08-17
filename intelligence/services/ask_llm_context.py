"""Env-gated persistence of the LLM-facing ask context.

Workbench API runs otherwise keep ``prepared_synthesis_messages`` only in
process. Live probes need that blob on disk so assertions like「⚠️已被新证据
取代」are grep-able first-hand evidence, not inferences from ``answer.md``.

Production 8792 does not set ``WORKBENCH_PERSIST_LLM_CONTEXT``; the sidecar
probe does. The file is an internal artifact and is not exposed on public
artifact routes.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

LLM_CONTEXT_FILENAME = "llm_context.json"
PERSIST_ENV = "WORKBENCH_PERSIST_LLM_CONTEXT"


def persist_enabled() -> bool:
    return os.environ.get(PERSIST_ENV, "0").strip() == "1"


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _jsonable(to_dict())
    public = getattr(value, "__dict__", None)
    if isinstance(public, dict) and public:
        return _jsonable(
            {key: item for key, item in public.items() if not str(key).startswith("_")}
        )
    return str(value)


def llm_context_document(result: object) -> dict[str, Any]:
    """Serialize the LLM-visible ask surface. No API keys."""

    diagnostic = getattr(result, "synthesis_diagnostic", None)
    return {
        "prepared_synthesis_messages": _jsonable(
            getattr(result, "prepared_synthesis_messages", None)
        ),
        "synthesis_messages": _jsonable(getattr(result, "synthesis_messages", None)),
        "citations": _jsonable(getattr(result, "citations", ()) or ()),
        "warnings": list(getattr(result, "warnings", ()) or ()),
        "provider_traces": _jsonable(getattr(result, "provider_traces", ()) or ()),
        "llm_stream_telemetry": _jsonable(
            getattr(result, "llm_stream_telemetry", {}) or {}
        ),
        "llm_provider": getattr(result, "llm_provider", None),
        "llm_fallback_reason": getattr(result, "llm_fallback_reason", None),
        "routed_modules": list(getattr(result, "routed_modules", ()) or ()),
        "wiki_rag_telemetry": _jsonable(getattr(result, "wiki_rag_telemetry", None)),
        "synthesis_diagnostic": _jsonable(diagnostic),
        "grounded_presenter": os.environ.get("WORKBENCH_GROUNDED_PRESENTER"),
    }


def maybe_persist_llm_context(
    store: Any, run_id: str, result: object
) -> Path | None:
    if not persist_enabled():
        return None
    text = json.dumps(llm_context_document(result), ensure_ascii=False, indent=2)
    store.add_artifact(
        run_id,
        LLM_CONTEXT_FILENAME,
        text,
        renderer="json",
        title="LLM 上下文（探针/审计）",
        visibility="internal",
    )
    return store.run_dir(run_id) / LLM_CONTEXT_FILENAME
