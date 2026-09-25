"""Fail-open recorder for tool-hunger events.

Hunger means the model asked for a capability the closed registry could not
serve. Events are observation only: they must never change the bytes returned
to the model, and a sink/disk failure must never raise into the tool path.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

HUNGER_FILENAME = "tool_hunger.jsonl"
EVENT_UNKNOWN_TOOL = "unknown_tool"
EVENT_FINANCE_QUERY_REJECTED = "finance_query_rejected"
EVENT_CAPABILITY_DENIED = "capability_denied"
_EVENT_TYPES = frozenset(
    {
        EVENT_UNKNOWN_TOOL,
        EVENT_FINANCE_QUERY_REJECTED,
        EVENT_CAPABILITY_DENIED,
    }
)

_SINK: ContextVar[HungerSink | None] = ContextVar("tool_hunger_sink", default=None)
_RUN_ID: ContextVar[str] = ContextVar("tool_hunger_run_id", default="")


class HungerSink(Protocol):
    def record(self, event: Mapping[str, Any]) -> None:
        """Persist one hunger event. May raise; callers swallow it."""


class JsonlHungerSink:
    """Append-only JSONL next to a run directory. Created on first record."""

    def __init__(self, path: Path, *, run_id: str = "") -> None:
        self.path = Path(path)
        self.run_id = str(run_id or "")
        self._lock = Lock()

    def record(self, event: Mapping[str, Any]) -> None:
        payload = dict(event)
        if self.run_id and not str(payload.get("run_id") or "").strip():
            payload["run_id"] = self.run_id
        line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)


@contextmanager
def hunger_context(sink: HungerSink, *, run_id: str = "") -> Iterator[HungerSink]:
    sink_token = _SINK.set(sink)
    run_token = _RUN_ID.set(str(run_id or ""))
    try:
        yield sink
    finally:
        _reset(sink_token, run_token)


@contextmanager
def bind_run_hunger(run_dir: Path, *, run_id: str = "") -> Iterator[HungerSink | None]:
    """Attach a JSONL sink to ``run_dir / tool_hunger.jsonl``. Fail-open."""

    try:
        sink: HungerSink | None = JsonlHungerSink(
            Path(run_dir) / HUNGER_FILENAME,
            run_id=run_id,
        )
        sink_token: Token[HungerSink | None] | None = _SINK.set(sink)
        run_token: Token[str] | None = _RUN_ID.set(str(run_id or ""))
    except Exception:
        yield None
        return
    try:
        yield sink
    finally:
        _reset(sink_token, run_token)


def _reset(
    sink_token: Token[HungerSink | None] | None,
    run_token: Token[str] | None,
) -> None:
    try:
        if sink_token is not None:
            _SINK.reset(sink_token)
    except Exception:
        pass
    try:
        if run_token is not None:
            _RUN_ID.reset(run_token)
    except Exception:
        pass


def record_hunger(**fields: Any) -> None:
    """Write one event. Swallows every Exception from the sink or encoding."""

    try:
        event_type = str(fields.get("event_type") or "").strip()
        if event_type not in _EVENT_TYPES:
            return
        event: dict[str, Any] = {
            "event_type": event_type,
            "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "run_id": str(fields.get("run_id") or _RUN_ID.get() or ""),
            "lane": str(fields.get("lane") or ""),
            "requested_name": str(fields.get("requested_name") or ""),
        }
        for key in (
            "arg_keys",
            "dataset",
            "metrics",
            "dimensions",
            "filters",
            "failure_code",
            "capability",
            "reason",
        ):
            if key in fields and fields[key] not in (None, ""):
                event[key] = fields[key]
        sink = _SINK.get()
        if sink is None:
            return
        sink.record(event)
    except Exception:
        return


def arg_keys(arguments: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(arguments, Mapping):
        return []
    return [str(key) for key in arguments]


def record_unknown_tool(
    name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    lane: str,
) -> None:
    record_hunger(
        event_type=EVENT_UNKNOWN_TOOL,
        requested_name=str(name or ""),
        arg_keys=arg_keys(arguments),
        lane=lane,
    )


def record_capability_denied(
    name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    capability: str | None,
    reason: str = "",
    lane: str = "episode",
) -> None:
    record_hunger(
        event_type=EVENT_CAPABILITY_DENIED,
        requested_name=str(name or ""),
        arg_keys=arg_keys(arguments),
        capability=capability,
        reason=reason,
        lane=lane,
    )


def record_finance_query_rejected(
    spec: Any,
    failure_code: str,
    *,
    lane: str = "episode",
) -> None:
    filters = []
    for item in getattr(spec, "filters", ()) or ():
        field = str(getattr(item, "field", "") or "")
        op = str(getattr(item, "op", "") or "")
        if field:
            filters.append({"field": field, "op": op})
    dataset = str(getattr(spec, "dataset", "") or "")
    record_hunger(
        event_type=EVENT_FINANCE_QUERY_REJECTED,
        requested_name=dataset,
        dataset=dataset,
        metrics=list(getattr(spec, "metrics", ()) or ()),
        dimensions=list(getattr(spec, "dimensions", ()) or ()),
        filters=filters,
        failure_code=str(failure_code or ""),
        lane=lane,
    )


def classify_unauthorized(registry: Any, name: str) -> tuple[str, str | None, str]:
    """Return (event_type, capability, reason) without changing wire errors."""

    from intelligence.services.research_tool_registry import UnknownResearchTool

    try:
        spec = registry.resolve(name)
    except UnknownResearchTool:
        return EVENT_UNKNOWN_TOOL, None, "工具未注册"
    except Exception:
        return EVENT_UNKNOWN_TOOL, None, "工具未注册"
    capability = getattr(spec, "capability", None)
    return (
        EVENT_CAPABILITY_DENIED,
        str(capability) if capability else None,
        f"能力未授权：{capability}" if capability else "能力未授权",
    )


__all__ = [
    "EVENT_CAPABILITY_DENIED",
    "EVENT_FINANCE_QUERY_REJECTED",
    "EVENT_UNKNOWN_TOOL",
    "HUNGER_FILENAME",
    "HungerSink",
    "JsonlHungerSink",
    "arg_keys",
    "bind_run_hunger",
    "classify_unauthorized",
    "hunger_context",
    "record_capability_denied",
    "record_finance_query_rejected",
    "record_hunger",
    "record_unknown_tool",
]
