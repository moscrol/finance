"""Eval-only per-request catalog view. Not installed in production factories."""

from dataclasses import dataclass
from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class Entry:
    name: str
    capability: str
    cost: str
    freshness: str
    description: str
    contract: str = ""
    parameters: Mapping[str, object] | None = None


def full_catalog(entries: Sequence[Entry]) -> str:
    return "\n".join(
        f"- {s.name}（{s.capability}，{s.cost}，{s.freshness}）：{s.description}"
        + (f"\n  · {s.contract}" if s.contract else "")
        for s in entries
    )


@dataclass(frozen=True)
class Projection:
    payload: Mapping[str, object]
    applied: bool
    reason: str
    catalog_bytes_saved: int = 0


def project_catalog(payload, entries, tools, *, enabled=False):
    """Build an ephemeral request view, never a replacement for stored history.

    Entries must come from the trusted, context-authorized registry, not a model
    reply. ``tools`` is the exact array attached to this request. Any uncertainty
    retains the original full presentation. This does NOT authorize execution,
    expand capabilities, or certify that this is a useful model optimization.
    """
    import json
    import re

    def unchanged(reason):
        return Projection(payload, False, reason)

    def canonical(schema):
        return json.dumps(schema, ensure_ascii=False, sort_keys=True, allow_nan=False)

    if enabled is not True:
        return unchanged("disabled")
    if (
        not isinstance(payload, Mapping)
        or not isinstance(entries, (list, tuple))
        or not entries
    ):
        return unchanged("unsupported_payload")
    if any(not isinstance(e, Entry) for e in entries):
        return unchanged("unsupported_entries")
    if any(
        not all(
            isinstance(value, str)
            for value in (
                e.name,
                e.capability,
                e.cost,
                e.freshness,
                e.description,
                e.contract,
            )
        )
        for e in entries
    ):
        return unchanged("unsupported_entries")
    names = [e.name for e in entries]
    if len(set(names)) != len(names) or any(
        not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", n) for n in names
    ):
        return unchanged("ambiguous_names")
    original = full_catalog(entries)
    if payload.get("available_tools") != original:
        return unchanged("catalog_mismatch")
    if not isinstance(tools, (list, tuple)):
        return unchanged("unsupported_tools")
    definitions = {}
    for tool in tools:
        if not isinstance(tool, Mapping) or tool.get("type") != "function":
            return unchanged("unsupported_tools")
        function = tool.get("function")
        if not isinstance(function, Mapping) or not isinstance(
            function.get("name"), str
        ):
            return unchanged("unsupported_tools")
        if function["name"] in definitions:
            return unchanged("ambiguous_names")
        definitions[function["name"]] = function
    if set(definitions) != set(names):
        return unchanged("different_tool_set")
    for entry in entries:
        function = definitions[entry.name]
        description = entry.description + (
            "\n" + entry.contract if entry.contract else ""
        )
        if function.get("description") != description:
            return unchanged("description_mismatch")
        parameters = function.get("parameters")
        if not isinstance(parameters, Mapping) or not isinstance(
            entry.parameters, Mapping
        ):
            return unchanged("parameters_unverified")
        try:
            if canonical(parameters) != canonical(entry.parameters):
                return unchanged("parameters_mismatch")
        except (TypeError, ValueError):
            return unchanged("parameters_unverified")
    compact = "工具用途、限制和参数见本次请求随附的完整工具定义。\n" + "\n".join(
        f"- {e.name}（{e.capability}，{e.cost}，{e.freshness}）" for e in entries
    )
    saved = len(original.encode("utf-8")) - len(compact.encode("utf-8"))
    if saved <= 0:
        return unchanged("no_byte_saving")
    view = dict(payload)
    view["available_tools"] = compact
    return Projection(view, True, "matching_full_definitions", saved)


def entries_for_context(registry, context):
    """Snapshot only the registry's authorized, read-scope-bound metadata."""
    from intelligence.services.research_tool_registry import copy_tool_parameters

    return tuple(
        Entry(
            s.name,
            s.capability,
            s.cost,
            s.freshness,
            s.description,
            s.contract,
            copy_tool_parameters(s.parameters),
        )
        for s in registry.for_context(context).authorized_specs(
            context.contract.allowed_capabilities
        )
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


class CatalogRequestClient:
    """EVAL ONLY complete() decorator, explicitly off unless enabled.

    The loop's original-history verifier does not certify this request view.
    When enabled a synchronous receipt sink is mandatory and must durably save
    original/sent requests BEFORE the one delegate call; a sink error prevents
    the call. Real provider-wire receipts must still be independently compared.
    Never install silently in production factories or use as a thin-ReAct loop.
    """

    def __init__(self, delegate, entries, *, enabled=False, record=None):
        if enabled is True and not callable(record):
            raise ValueError("enabled projection requires a durable receipt sink")
        self._delegate = delegate
        self._entries = tuple(entries)
        self._enabled = enabled is True
        self._record = record

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    def complete(self, *, messages, tools, timeout):
        if not self._enabled:
            return self._delegate.complete(
                messages=messages, tools=tools, timeout=timeout
            )
        from copy import deepcopy
        import hashlib
        import json

        view = messages
        reason = "unsupported_initial_message"
        saved = 0
        if (
            len(messages) > 1
            and isinstance(messages[1], dict)
            and messages[1].get("role") == "user"
            and isinstance(messages[1].get("content"), str)
        ):
            content = messages[1]["content"]
            leading = len(content) - len(content.lstrip())
            try:
                payload, end = json.JSONDecoder(
                    object_pairs_hook=_unique_object
                ).raw_decode(content, leading)
            except (ValueError, TypeError):
                reason = "unsupported_initial_json"
            else:
                projection = project_catalog(
                    payload, self._entries, tools, enabled=True
                )
                reason = projection.reason
                if projection.applied:
                    old = (
                        json.dumps("available_tools")
                        + ": "
                        + json.dumps(payload["available_tools"], ensure_ascii=False)
                    )
                    new = (
                        json.dumps("available_tools")
                        + ": "
                        + json.dumps(
                            projection.payload["available_tools"], ensure_ascii=False
                        )
                    )
                    # Exact replacement only, no reserializing other payload fields;
                    # appended history context and whitespace remain byte-identical.
                    prefix, suffix = content[:end], content[end:]
                    if prefix.count(old) == 1:
                        view = list(messages)
                        view[1] = {
                            **messages[1],
                            "content": prefix.replace(old, new, 1) + suffix,
                        }
                        saved = projection.catalog_bytes_saved
                    else:
                        reason = "unsupported_serialization"
        original = {"messages": messages, "tools": tools, "timeout": timeout}
        sent = {"messages": view, "tools": tools, "timeout": timeout}

        def digest(value):
            data = json.dumps(
                value, ensure_ascii=False, sort_keys=True, allow_nan=False
            ).encode()
            return hashlib.sha256(data).hexdigest()

        receipt = {
            "kind": "catalog_request_view",
            "applied": view is not messages,
            "reason": reason,
            "catalog_bytes_saved": saved,
            "original_sha256": digest(original),
            "sent_sha256": digest(sent),
            "original_request": original,
            "sent_request": sent,
        }
        self._record(deepcopy(receipt))
        return self._delegate.complete(messages=view, tools=tools, timeout=timeout)
