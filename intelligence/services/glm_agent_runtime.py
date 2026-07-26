"""GLM/OpenAI-compatible adapter for the provider-neutral agent runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import time

from intelligence.services import llm_refine
from intelligence.services.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    ModelToolCall,
    ModelTurn,
)
from intelligence.services.episode_finalizer import EpisodeFinalizer
from intelligence.services.episode_session import CallbackEpisodeSession, EpisodeSession
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame


ChatWithTools = Callable[..., tuple[dict | None, object | None, str]]
_TRANSIENT_PROVIDER_ERRORS = (
    "TimeoutError",
    "RemoteDisconnected",
    "URLError",
)
DEFAULT_GLM_LLM_TIMEOUT = 75.0
_GLM_SYNTHESIS_RESERVE = {
    "quick": 20.0,
    "standard": 75.0,
    "deep": 75.0,
}
_SYNTHESIS_HEAVY_QUESTION_TYPES = frozenset(
    {
        "market_cause",
        "market_watch",
    }
)
_BALANCED_SYNTHESIS_RESERVE = 60.0
_UNCONFIGURED_PROVIDER_REASON = "未配置 LLM key，无法完成模型调用"


class GLMModelClient:
    """Translate provider-neutral responses into a stable model turn.

    ``GLMModelClient`` is retained as the compatibility name used by the
    existing episode runtime.  The adapter itself is provider-neutral: when
    callers inject ``providers`` it owns one explicit, ordered chain and
    scopes each call with :func:`llm_refine.provider_override`.  The legacy
    injected-callback path remains available for older callers that already
    provide their own adapter function; the real default adapter always uses
    the resolved chain once.
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        providers: tuple[llm_refine.LLMProvider, ...] | None = None,
        complete_fn: ChatWithTools | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._model = model
        self._is_cancelled = is_cancelled or (lambda: False)
        self._retry_single_real_provider = False
        if providers is not None:
            self._providers = tuple(providers)
        elif complete_fn is None:
            # The real adapter already has provider fallback logic. Resolve
            # that chain here so each physical call is scoped and counted once
            # rather than repeating the whole internal chain on outer retry.
            self._providers = tuple(llm_refine.detect_providers(model))
            self._retry_single_real_provider = len(self._providers) == 1
        else:
            # Explicit compatibility callbacks retain the historical singleton
            # adapter semantics, including its bounded transient retry.
            self._providers = None
        self._complete = complete_fn or llm_refine.chat_with_tools

    def complete(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
    ) -> ModelTurn:
        if self._providers is not None:
            return self._complete_provider_chain(
                messages=messages,
                tools=tools,
                timeout=timeout,
            )
        return self._complete_legacy(
            messages=messages,
            tools=tools,
            timeout=timeout,
        )

    def _complete_legacy(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
    ) -> ModelTurn:
        """Preserve pre-chain behavior for compatibility callers."""

        configured_timeout = max(0.0, float(timeout))
        expires_at = time.monotonic() + configured_timeout
        message: dict | None = None
        provider: object | None = None
        reason = "model deadline exhausted"
        attempts = 0
        trace: list[dict[str, object]] = []
        for attempt in range(2):
            if self._is_cancelled():
                reason = "cancelled"
                break
            remaining = (
                configured_timeout
                if attempt == 0
                else max(0.0, expires_at - time.monotonic())
            )
            if remaining <= 0.001:
                break
            message, provider, reason = self._complete(
                messages=messages,
                tools=tools,
                model_override=self._model,
                timeout=remaining,
                temperature=0.0,
                tool_choice="auto",
                disable_thinking=True,
            )
            if message is None and _is_call_budget_rejection(reason):
                # The legacy adapter can reject at its public entry before
                # provider detection or HTTP. Keep usage and trace physical.
                break
            attempts += 1
            parsed_turn: ModelTurn | None = None
            parse_error = ""
            if self._is_cancelled():
                reason = "cancelled"
                message = None
                trace.append(
                    _provider_trace_entry(
                        provider,
                        status="failed",
                        reason=reason,
                    )
                )
                break
            if message is None:
                trace.append(
                    _provider_trace_entry(
                        provider,
                        status="failed",
                        reason=str(reason or ""),
                    )
                )
            else:
                parsed_turn, parse_error = _turn_from_message(
                    message,
                    _provider_name(provider),
                    attempts,
                    reject_empty=False,
                )
                trace.append(
                    _provider_trace_entry(
                        provider,
                        status="failed" if parse_error else "success",
                        reason=parse_error,
                    )
                )
            if (
                message is not None
                or attempt == 1
                or not _is_transient_provider_error(reason)
            ):
                break
        provider_name = _provider_name(provider)
        if message is None:
            return self._with_provider_trace(
                ModelTurn(
                    "",
                    (),
                    provider_name,
                    str(reason or "model_unavailable"),
                    provider_attempts=attempts,
                ),
                tuple(trace),
            )
        if parsed_turn is None:
            parsed_turn, _error = _turn_from_message(
                message,
                provider_name,
                attempts,
                reject_empty=False,
            )
        return self._with_provider_trace(parsed_turn, tuple(trace))

    def _complete_provider_chain(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
    ) -> ModelTurn:
        """Run one adapter attempt per injected provider in deterministic order."""

        configured_timeout = max(0.0, float(timeout))
        expires_at = time.monotonic() + configured_timeout
        attempts = 0
        trace: list[dict[str, object]] = []
        last_provider: object | None = None
        last_reason = "model deadline exhausted"

        if not self._providers:
            return self._with_provider_trace(
                ModelTurn(
                    "",
                    (),
                    "",
                    _UNCONFIGURED_PROVIDER_REASON,
                    provider_attempts=0,
                ),
                (),
            )

        providers = self._providers or ()
        provider_index = 0
        single_retry_used = False
        while provider_index < len(providers):
            if self._is_cancelled():
                last_reason = "cancelled"
                break
            provider = providers[provider_index]
            remaining = max(0.0, expires_at - time.monotonic())
            if remaining <= 0.001:
                break
            message: dict | None
            returned_provider: object | None
            reason: object
            try:
                # The override is intentionally scoped to this one adapter
                # call. ``chat_with_tools`` remains the sole HTTP/fallback
                # implementation and keeps its existing accounting behavior.
                with llm_refine.provider_override(provider):
                    message, returned_provider, reason = self._complete(
                        messages=messages,
                        tools=tools,
                        model_override=self._model,
                        timeout=remaining,
                        temperature=0.0,
                        tool_choice="auto",
                        disable_thinking=True,
                    )
            except llm_refine.LLMCallBudgetExceeded as exc:
                last_reason = str(exc)
                break
            except Exception as exc:  # pragma: no cover - defensive seam
                message, returned_provider, reason = (
                    None,
                    provider,
                    f"LLM 调用失败（{type(exc).__name__}）",
                )

            effective_provider = returned_provider or provider
            provider_name = _provider_name(effective_provider) or _provider_name(
                provider
            )
            reason_text = str(reason or "")
            if message is None and _is_call_budget_rejection(reason_text):
                # ``chat_with_tools`` rejected this invocation before its HTTP
                # boundary, so it is not a physical provider attempt.
                last_reason = reason_text
                break
            attempts += 1
            last_provider = provider
            if self._is_cancelled():
                last_reason = "cancelled"
                trace.append(
                    _provider_trace_entry(
                        effective_provider,
                        status="failed",
                        reason=last_reason,
                    )
                )
                break
            if message is None:
                trace.append(
                    _provider_trace_entry(
                        effective_provider,
                        status="failed",
                        reason=reason_text or "model_unavailable",
                    )
                )
                last_reason = reason_text or "model_unavailable"
                if (
                    self._retry_single_real_provider
                    and not single_retry_used
                    and _is_transient_provider_error(reason_text)
                ):
                    single_retry_used = True
                    continue
                provider_index += 1
                continue

            turn, parse_error = _turn_from_message(
                message,
                provider_name,
                attempts,
            )
            if parse_error:
                trace.append(
                    _provider_trace_entry(
                        effective_provider,
                        status="failed",
                        reason=parse_error,
                    )
                )
                last_reason = parse_error
                provider_index += 1
                continue

            trace.append(
                _provider_trace_entry(
                    effective_provider,
                    status="success",
                    reason="",
                )
            )
            return self._with_provider_trace(turn, tuple(trace))

        return self._with_provider_trace(
            ModelTurn(
                "",
                (),
                _provider_name(last_provider),
                last_reason,
                provider_attempts=attempts,
            ),
            tuple(trace),
        )

    def _with_provider_trace(
        self,
        turn: ModelTurn,
        trace: tuple[dict[str, object], ...],
    ) -> ModelTurn:
        # ``ModelTurn`` is a frozen public value object. Keep adapter details
        # private and out of ``to_dict()`` while making them available to the
        # runtime/episode diagnostics when needed.
        object.__setattr__(turn, "_provider_trace", trace)
        return turn


class GLMAgentRuntime:
    """Phase-one composition root; provider logic stays outside the episode."""

    def __init__(
        self,
        model: str | None = None,
        *,
        providers: tuple[llm_refine.LLMProvider, ...] | None = None,
        complete_fn: ChatWithTools | None = None,
        llm_timeout: float = DEFAULT_GLM_LLM_TIMEOUT,
        client: AgentModelClient | None = None,
        finalizer: EpisodeFinalizer | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        if client is not None and (
            model is not None or providers is not None or complete_fn is not None
        ):
            raise ValueError(
                "injected client cannot be combined with model/provider adapter settings"
            )
        selected_client = client or GLMModelClient(
            model,
            providers=providers,
            complete_fn=complete_fn,
            is_cancelled=is_cancelled,
        )
        self._episode = ContinuousAgentEpisode(
            selected_client,
            llm_timeout=llm_timeout,
            finalizer=finalizer,
            is_cancelled=is_cancelled,
        )

    @staticmethod
    def synthesis_reserve_for_tier(tier: str) -> float:
        normalized = str(tier or "").strip().lower()
        return _GLM_SYNTHESIS_RESERVE.get(
            normalized,
            _GLM_SYNTHESIS_RESERVE["standard"],
        )

    @staticmethod
    def synthesis_reserve_for_task(
        *,
        tier: str,
        question_type: str,
    ) -> float:
        """Allocate one fixed total budget by task shape, never by model choice."""

        tier_reserve = GLMAgentRuntime.synthesis_reserve_for_tier(tier)
        if str(tier or "").strip().lower() == "quick":
            return tier_reserve
        normalized_type = str(question_type or "").strip().lower()
        if normalized_type in _SYNTHESIS_HEAVY_QUESTION_TYPES:
            return tier_reserve
        return min(tier_reserve, _BALANCED_SYNTHESIS_RESERVE)

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

    def start(
        self,
        task_frame: TaskFrame,
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> EpisodeSession:
        continuation = []
        outcome = self._episode.run(
            task_frame=task_frame,
            context=context,
            registry=registry,
            _continuation_sink=continuation,
        )
        if len(continuation) != 1:
            raise RuntimeError("episode continuation state was not captured")
        state = continuation[0]
        return CallbackEpisodeSession(
            episode_id=context.contract.task_id,
            outcome=outcome,
            resume_callback=lambda previous, goal: self._episode.resume(
                state,
                previous,
                goal,
            ),
            evidence_ledger=state.evidence_ledger,
            initial_evidence_snapshot=state.initial_evidence_snapshot,
        )


def _provider_trace_entry(
    provider: object | None,
    *,
    status: str,
    reason: str,
) -> dict[str, object]:
    """Build a private, secret-free adapter-attempt record."""

    return {
        "provider": _provider_name(provider),
        "status": status,
        "reason": reason,
    }


def _turn_from_message(
    message: object,
    provider_name: str,
    attempts: int,
    *,
    reject_empty: bool = True,
) -> tuple[ModelTurn, str]:
    """Validate and convert an adapter envelope without leaking raw payloads."""

    if not isinstance(message, dict):
        return (
            ModelTurn(
                "",
                (),
                provider_name,
                "invalid_model_message",
                provider_attempts=attempts,
            ),
            "invalid_model_message",
        )

    raw_content = message.get("content")
    if raw_content is None:
        content = ""
    elif isinstance(raw_content, str):
        content = raw_content
    else:
        return (
            ModelTurn(
                "",
                (),
                provider_name,
                "invalid_model_content",
                provider_attempts=attempts,
            ),
            "invalid_model_content",
        )

    raw_calls = message.get("tool_calls")
    if raw_calls is None:
        raw_calls = []
    elif not isinstance(raw_calls, list):
        return (
            ModelTurn(
                content,
                (),
                provider_name,
                "invalid_tool_calls",
                provider_attempts=attempts,
            ),
            "invalid_tool_calls",
        )
    calls: list[ModelToolCall] = []
    for raw_call in raw_calls:
        parsed, error = _parse_tool_call(raw_call)
        if error:
            return (
                ModelTurn(
                    content,
                    (),
                    provider_name,
                    error,
                    provider_attempts=attempts,
                ),
                error,
            )
        if parsed is not None:
            calls.append(parsed)
    if reject_empty and not calls and not content.strip():
        return (
            ModelTurn(
                "",
                (),
                provider_name,
                "empty_model_response",
                provider_attempts=attempts,
            ),
            "empty_model_response",
        )
    return (
        ModelTurn(
            content,
            tuple(calls),
            provider_name,
            "",
            provider_attempts=attempts,
        ),
        "",
    )


def _provider_name(provider: object | None) -> str:
    if provider is None:
        return ""
    if isinstance(provider, str):
        return provider.strip()
    name = getattr(provider, "name", "")
    return name.strip() if isinstance(name, str) else ""


def _is_transient_provider_error(reason: object) -> bool:
    return isinstance(reason, str) and any(
        marker in reason for marker in _TRANSIENT_PROVIDER_ERRORS
    )


def _is_call_budget_rejection(reason: object) -> bool:
    return isinstance(reason, str) and "LLM 调用预算耗尽" in reason


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
