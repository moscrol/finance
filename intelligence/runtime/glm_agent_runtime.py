"""GLM/OpenAI-compatible adapter for the provider-neutral agent runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import time

from intelligence.services import llm_refine
from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    EpisodeEvent,
    ModelToolCall,
    ModelTurn,
    is_transient_model_error,
)
from intelligence.runtime.continuous_sub_research import ContinuousSubResearchWorker
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.cancel_signal import CancelSignal
from intelligence.services.draft_stream import DraftStreamDecoder
from intelligence.services.episode_session import CallbackEpisodeSession, EpisodeSession
from intelligence.services.mode_governor import ModeGovernor, ModeSignals
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_plan import ResearchPlan
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.runtime_handle import RuntimeHandle
from intelligence.runtime.sub_research import SubResearchCoordinator
from intelligence.services.task_frame import TaskFrame


ChatWithTools = Callable[..., tuple[dict | None, object | None, str]]
# 瞬态错误判据已上移到 services.agent_runtime（修复轮与 provider 链共用一份，
# 不另建第二份清单）。本模块内保留原私有名，调用点不动。
_is_transient_provider_error = is_transient_model_error
DEFAULT_GLM_LLM_TIMEOUT = 75.0
_GLM_SYNTHESIS_RESERVE = {
    "quick": 20.0,
    "standard": 75.0,
    "deep": 75.0,
    "max": 75.0,
}
_SYNTHESIS_HEAVY_QUESTION_TYPES = frozenset(
    {
        "market_cause",
    }
)
_BALANCED_SYNTHESIS_RESERVE = 60.0
_UNCONFIGURED_PROVIDER_REASON = "未配置 LLM key，无法完成模型调用"


class _DraftSink:
    """Turn one turn's raw content stream into visible ``draft`` prose.

    Owned per ``complete()`` call, never across turns.  The episode's first
    turn usually emits a PLAN object or nothing at all; letting its bytes
    accumulate in a shared decoder would spend the envelope-prefix budget
    before the final turn ever starts, and the decoder would disarm exactly
    when it was finally needed.
    """

    def __init__(self, emit: Callable[[str], None]) -> None:
        self._emit = emit
        self._decoder = DraftStreamDecoder()

    def feed(self, raw: str) -> None:
        text = self._decoder.feed(raw)
        if text:
            self._emit(text)

    def finish(self) -> None:
        text = self._decoder.flush()
        if text:
            self._emit(text)

    @property
    def emitted_chars(self) -> int:
        return self._decoder.emitted_chars


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
        on_draft_delta: Callable[[str], None] | None = None,
    ) -> None:
        self._model = model
        self._is_cancelled = is_cancelled or (lambda: False)
        self._on_draft_delta = on_draft_delta
        self._retry_single_real_provider = False
        if providers is not None:
            self._providers = tuple(providers)
            # 生产（api/app.py:226）会把已解析的 provider 链显式注入，但**不**注入
            # complete_fn——跑的仍是真适配器。重试资格的判据因此是「有没有用真
            # 适配器」，而不是「链是不是注入的」。
            #
            # 原来只有下面那条 detect_providers 分支置 True，于是生产路径的
            # _retry_single_real_provider 恒为 False：网关 round-robin 打到坏账号
            # 返 502 时一次都不重试，直接 model_unavailable。实测四次决证 run 全部
            # provider_attempts=1，就是这个闸门造成的。
            self._retry_single_real_provider = (
                complete_fn is None and len(self._providers) == 1
            )
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
        sink = _DraftSink(self._on_draft_delta) if self._on_draft_delta else None
        try:
            if self._providers is not None:
                return self._complete_provider_chain(
                    messages=messages,
                    tools=tools,
                    timeout=timeout,
                    sink=sink,
                )
            return self._complete_legacy(
                messages=messages,
                tools=tools,
                timeout=timeout,
                sink=sink,
            )
        finally:
            if sink is not None:
                sink.finish()

    def _stream_kwargs(self, sink: "_DraftSink | None") -> dict[str, object]:
        """Only add the streaming keywords when a sink is actually wired.

        Injected ``complete_fn`` doubles are fixed-arity across the test suite
        (``lambda **kwargs`` is not the norm), so an unconditional new keyword
        would break every one of them.  No sink means the call is byte-for-byte
        what it was before streaming existed.
        """

        if sink is None:
            return {}
        return {
            "on_content_delta": sink.feed,
            "is_cancelled": self._is_cancelled,
        }

    def _complete_legacy(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
        sink: "_DraftSink | None" = None,
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
                **self._stream_kwargs(sink),
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
        sink: "_DraftSink | None" = None,
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
        transient_retries_used = 0
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
                        **self._stream_kwargs(sink),
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
            if message is None and sink is not None and sink.emitted_chars:
                # 正文已经到用户屏幕上了。``chat_with_tools`` 内部的 provider 链
                # 已经因此停住（LLMStreamAlreadyEmitted），**外层这条链也必须停**
                # ——否则换一家 provider 重跑一遍，用户会看到答案被写第二遍。
                # 这是那道闸的第二半：闸开在传输层，重试意图在这一层。
                attempts += 1
                last_provider = provider
                last_reason = reason_text or "stream_already_emitted"
                trace.append(
                    _provider_trace_entry(
                        effective_provider,
                        status="failed",
                        reason=last_reason,
                    )
                )
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
                    and transient_retries_used < 3
                    and _is_transient_provider_error(reason_text)
                ):
                    # cockpit gateway round-robin 可能连续打到坏账号，
                    # 1 次重试不够。3 次上限仍远低于 LLM_TIMEOUT，不影响 deadline。
                    transient_retries_used += 1
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
        mode_governor: ModeGovernor | None = None,
        mode_signals: Callable[[TaskFrame, ResearchPlan], ModeSignals] | None = None,
        sub_research_coordinator: SubResearchCoordinator | None = None,
        event_sink: Callable[[EpisodeEvent], None] | None = None,
        on_draft_delta: Callable[[str], None] | None = None,
    ) -> None:
        if client is not None and (
            model is not None or providers is not None or complete_fn is not None
        ):
            raise ValueError(
                "injected client cannot be combined with model/provider adapter settings"
            )
        if client is not None and on_draft_delta is not None:
            # 注入 client 时流式归 client 自己配（生产就是这条：app.py 先建
            # client 再传进来）。两边都配会得到两个 sink 喂同一个出口，正文翻倍。
            raise ValueError(
                "injected client owns its own draft stream; pass on_draft_delta to it"
            )
        # 取消信号在这里一次类型化（INV-R4）：上游裸谓词来自 API 取消端点 / 定时器，
        # 原因记 user；子研究分支拿 child 信号，父取消传下去时原因记 parent。
        cancel_signal = CancelSignal.coerce(is_cancelled, cause="user")
        selected_client = client or GLMModelClient(
            model,
            providers=providers,
            complete_fn=complete_fn,
            is_cancelled=cancel_signal,
            on_draft_delta=on_draft_delta,
        )
        selected_coordinator = sub_research_coordinator or SubResearchCoordinator(
            ContinuousSubResearchWorker(
                selected_client,
                llm_timeout=llm_timeout,
            ),
            is_cancelled=cancel_signal.child(cause="parent"),
        )
        # RuntimeHandle 折叠的上游取消信号与 episode/coordinator 收到的是同一个
        # ——生命周期收据必须与实际执行看同一份事实，不能各订阅各的。
        self._upstream_cancelled = cancel_signal
        self._episode = ContinuousAgentEpisode(
            selected_client,
            llm_timeout=llm_timeout,
            finalizer=finalizer,
            is_cancelled=cancel_signal,
            # 深度裁决的注入件直接进 harness 构造器——Episode 上那层转交壳已删。
            harness=FinanceResearchHarness(
                mode_governor=mode_governor,
                mode_signals=mode_signals,
            ),
            sub_research_coordinator=selected_coordinator,
            event_sink=event_sink,
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
        # 生命周期状态机在会话构造点建立（spec §7.3，第 4 步 2/2）。
        # 身份沿用仓内约定：episode_id = contract.task_id，与 EpisodeScope 同源。
        handle = RuntimeHandle(
            episode_id=context.contract.task_id,
            task_frame_hash=(
                context.contract.task_frame_hash or task_frame.task_frame_hash
            ),
            upstream_cancelled=self._upstream_cancelled,
        )
        continuation = []
        handle.mark_started()
        # 初始 run 是 start() 同步派发的引导工作：取消先到时它就是要排空的
        # 那一个（episode 内层会立刻以 cancelled 终态返回，不派发任何工具），
        # 所以 allow_during_cancel——挡它不会更快，只会把诚实的 cancelled
        # outcome 换成一个异常。
        handle.begin_work("initial_run", allow_during_cancel=True)
        try:
            outcome = self._episode.run(
                task_frame=task_frame,
                context=context,
                registry=registry,
                _continuation_sink=continuation,
            )
        finally:
            handle.end_work("initial_run")
        if len(continuation) != 1:
            raise RuntimeError("episode continuation state was not captured")
        state = continuation[0]
        # 一个 Episode 一个 Scope：把 run() 入口构造的那个挂上收据（引用，
        # 不复制）。修复轮复用同一 continuation state，Scope 不会碎片化。
        handle.attach_scope(state.episode_scope)
        handle.mark_running()
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
            runtime_handle=handle,
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
    input_tokens, output_tokens = _message_token_usage(message)
    served_model = _message_served_model(message)

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
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                served_model=served_model,
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
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                served_model=served_model,
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
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    served_model=served_model,
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
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                served_model=served_model,
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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            served_model=served_model,
        ),
        "",
    )


def _message_served_model(message: Mapping[str, object]) -> str | None:
    """适配器信封里的 ``_served_model``：``""`` 是「provider 未回」，缺键是 ``None``。"""

    value = message.get("_served_model")
    return value.strip() if isinstance(value, str) else None


def _message_token_usage(message: Mapping[str, object]) -> tuple[int | None, int | None]:
    raw = message.get("_usage")
    if not isinstance(raw, Mapping):
        raw = message.get("usage")
    if not isinstance(raw, Mapping):
        return None, None

    def token_value(*names: str) -> int | None:
        for name in names:
            value = raw.get(name)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
        return None

    return (
        token_value("input_tokens", "prompt_tokens"),
        token_value("output_tokens", "completion_tokens"),
    )


def _provider_name(provider: object | None) -> str:
    if provider is None:
        return ""
    if isinstance(provider, str):
        return provider.strip()
    name = getattr(provider, "name", "")
    return name.strip() if isinstance(name, str) else ""


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
