"""GLM/OpenAI-compatible adapter for the provider-neutral agent runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json

from intelligence.services import llm_refine
from intelligence.services.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import (
    AgentOutcome,
    ModelToolCall,
    ModelTurn,
)
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame


ChatWithTools = Callable[..., tuple[dict | None, object | None, str]]


class GLMModelClient:
    """Translate one OpenAI-compatible response into a stable model turn."""

    def __init__(
        self,
        model: str | None = None,
        *,
        complete_fn: ChatWithTools | None = None,
    ) -> None:
        self._model = model
        self._complete = complete_fn or llm_refine.chat_with_tools

    def complete(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
    ) -> ModelTurn:
        message, provider, reason = self._complete(
            messages=messages,
            tools=tools,
            model_override=self._model,
            timeout=timeout,
            temperature=0.0,
            tool_choice="auto",
        )
        provider_name = _provider_name(provider)
        if message is None:
            return ModelTurn(
                "",
                (),
                provider_name,
                str(reason or "model_unavailable"),
            )
        if not isinstance(message, dict):
            return ModelTurn("", (), provider_name, "invalid_model_message")

        raw_content = message.get("content")
        if raw_content is None:
            content = ""
        elif isinstance(raw_content, str):
            content = raw_content
        else:
            return ModelTurn("", (), provider_name, "invalid_model_content")

        raw_calls = message.get("tool_calls") or []
        if not isinstance(raw_calls, list):
            return ModelTurn(content, (), provider_name, "invalid_tool_calls")
        calls: list[ModelToolCall] = []
        for raw_call in raw_calls:
            parsed, error = _parse_tool_call(raw_call)
            if error:
                return ModelTurn(content, (), provider_name, error)
            if parsed is not None:
                calls.append(parsed)
        return ModelTurn(content, tuple(calls), provider_name, "")


class GLMAgentRuntime:
    """Phase-one composition root; provider logic stays outside the episode."""

    def __init__(
        self,
        model: str | None = None,
        *,
        complete_fn: ChatWithTools | None = None,
        llm_timeout: float = 20.0,
    ) -> None:
        client = GLMModelClient(model, complete_fn=complete_fn)
        self._episode = ContinuousAgentEpisode(
            client,
            llm_timeout=llm_timeout,
        )

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome:
        return self._episode.run(
            task_frame=task_frame,
            context=context,
            registry=registry,
        )


def _provider_name(provider: object | None) -> str:
    if provider is None:
        return ""
    if isinstance(provider, str):
        return provider.strip()
    name = getattr(provider, "name", "")
    return name.strip() if isinstance(name, str) else ""


def _parse_tool_call(
    value: object,
) -> tuple[ModelToolCall | None, str]:
    if not isinstance(value, Mapping):
        return None, "invalid_tool_call"
    call_id = value.get("id")
    function = value.get("function")
    stable_id = call_id.strip() if isinstance(call_id, str) else ""
    if not stable_id or not isinstance(function, Mapping):
        return None, f"invalid_tool_call:{stable_id or 'unknown'}"
    name = function.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, f"invalid_tool_name:{stable_id}"
    raw_arguments = function.get("arguments", {})
    if isinstance(raw_arguments, str):
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return None, f"invalid_tool_arguments:{stable_id}"
    elif isinstance(raw_arguments, Mapping):
        arguments = dict(raw_arguments)
    else:
        return None, f"invalid_tool_arguments:{stable_id}"
    if not isinstance(arguments, dict):
        return None, f"invalid_tool_arguments:{stable_id}"
    try:
        return ModelToolCall(stable_id, name, arguments), ""
    except ValueError:
        return None, f"invalid_tool_arguments:{stable_id}"


__all__ = ["GLMAgentRuntime", "GLMModelClient"]
