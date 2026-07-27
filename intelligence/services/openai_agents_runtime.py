"""OpenAI Agents SDK adapter over the canonical finance runtime seam."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextvars import Context, copy_context
from dataclasses import InitVar, dataclass, replace
import json
from threading import Lock
from time import monotonic
from typing import Literal, Protocol

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    public_agent_evidence,
)
from intelligence.services.evidence_ledger import (
    EvidenceLedger,
)
from intelligence.services.episode_session import (
    CallbackEpisodeSession,
    EpisodeSession,
    EpisodeSessionError,
)
from intelligence.services.episode_protocol import (
    build_episode_input,
    build_episode_instructions,
    expand_episode_snapshot_bindings,
    validate_episode_finish,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.repair_coordinator import RepairGoal
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchRunContext,
)
from intelligence.services.research_tool_registry import (
    InvalidResearchToolArguments,
    PreparedToolArguments,
    ResearchToolRegistry,
    ToolObservation,
    ToolSpec,
    copy_tool_parameters,
)
from intelligence.services.task_frame import TaskFrame


SdkBackend = Literal["sdk_glm", "sdk_gpt"]
SdkModelFactory = Callable[
    [],
    tuple[object, Callable[[], Awaitable[None]]],
]
_PARTIAL_EXECUTION_GAPS = frozenset(
    {"cancelled", "deadline_exhausted", "tool_budget_exhausted"}
)
_SDK_MAX_VERIFIER_RESERVE_SECONDS = 20.0
_SDK_MIN_VERIFIER_RESERVE_SECONDS = 2.0
_SDK_STAGE_CLOSED = "research_stage_closed"
_SDK_STAGE_CLOSED_INSTRUCTION = "研究取证阶段已结束，请使用已有信息完成终止回答。"
_ROOT_BUDGET_CALL_RESERVATION_SECONDS = 1e-9


class _OpaqueProviderContinuation:
    """Keep provider history out of repr/dataclass/JSON projections."""

    __slots__ = ("_value",)

    def __init__(self, value: object | None) -> None:
        self._value = value

    @property
    def value(self) -> object | None:
        return self._value

    def __repr__(self) -> str:
        return "<_OpaqueProviderContinuation>"


def _sdk_verifier_reserve(context: ResearchRunContext) -> float:
    synthesis_reserve = max(0.0, context.deadline.synthesis_reserve)
    if synthesis_reserve <= 0.0:
        return 0.0
    return min(
        synthesis_reserve,
        _SDK_MAX_VERIFIER_RESERVE_SECONDS,
        max(_SDK_MIN_VERIFIER_RESERVE_SECONDS, synthesis_reserve / 3.0),
    )


def _sdk_runtime_timeout(context: ResearchRunContext) -> float:
    timeout = max(
        0.0,
        context.deadline.remaining() - _sdk_verifier_reserve(context),
    )
    if context.root_budget is not None:
        timeout = min(
            timeout,
            max(0.0, float(context.root_budget.remaining_seconds)),
        )
    return timeout


def build_glm_sdk_model(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
) -> object:
    """Build the SDK Chat Completions adapter for GLM without ambient proxies."""

    import httpx
    from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        http_client=httpx.AsyncClient(trust_env=False),
    )
    return OpenAIChatCompletionsModel(model=model, openai_client=client)


def build_gpt_sdk_model(model: str = "gpt-5.6-sol") -> str:
    cleaned = str(model or "").strip()
    if not cleaned:
        raise ValueError("GPT SDK model name must be non-empty")
    return cleaned


def build_gpt_sdk_model_factory(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
) -> SdkModelFactory:
    """Build an explicit Responses adapter for OpenAI or a trusted gateway."""

    def factory() -> tuple[object, Callable[[], Awaitable[None]]]:
        import httpx
        from agents.models.openai_responses import OpenAIResponsesModel
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            http_client=httpx.AsyncClient(trust_env=False),
        )
        sdk_model = OpenAIResponsesModel(model=model, openai_client=client)
        return sdk_model, client.close

    return factory


def build_agents_model_settings(backend: SdkBackend) -> object:
    from agents import ModelSettings

    if backend == "sdk_glm":
        return ModelSettings(
            temperature=0.0,
            parallel_tool_calls=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
    if backend == "sdk_gpt":
        from openai.types.shared import Reasoning

        return ModelSettings(
            parallel_tool_calls=False,
            reasoning=Reasoning(effort="high"),
            verbosity="medium",
            store=False,
        )
    raise ValueError("unsupported SDK backend")


def build_agents_delivery_model_settings(backend: SdkBackend) -> object:
    """Use a cheaper reasoning profile once tools are closed and facts are frozen."""

    if backend == "sdk_glm":
        return build_agents_model_settings(backend)
    if backend == "sdk_gpt":
        from agents import ModelSettings
        from openai.types.shared import Reasoning

        return ModelSettings(
            parallel_tool_calls=False,
            reasoning=Reasoning(effort="low"),
            verbosity="medium",
            store=False,
        )
    raise ValueError("unsupported SDK backend")


def sdk_model_aclose(model: object) -> Callable[[], Awaitable[None]]:
    client = getattr(model, "_client", None)
    close = getattr(client, "close", None)
    if not callable(close):
        raise ValueError("SDK model does not expose an async client close hook")
    return close


def _single_function_call_per_response(model: object) -> object:
    """Project a provider response to one local function call per model turn.

    Some OpenAI-compatible gateways ignore ``parallel_tool_calls=False`` and
    return a batch of function calls anyway.  The Agents SDK's
    ``max_function_tool_concurrency=1`` only serializes that batch; it does not
    stop the second call from executing before the model observes the first
    result.  Wrap the GPT model at the provider boundary so the SDK sees only
    the first function call and naturally starts a new model turn afterwards.
    """

    from agents import Model, ModelResponse

    if not isinstance(model, Model):
        return model

    class SingleFunctionCallModel(Model):
        def __init__(self, delegate: Model) -> None:
            self._delegate = delegate
            self.batched_tool_calls_dropped = 0

        async def get_response(self, *args, **kwargs) -> ModelResponse:
            response = await self._delegate.get_response(*args, **kwargs)
            projected: list[object] = []
            function_call_seen = False
            dropped = False
            for item in response.output:
                if getattr(item, "type", None) == "function_call":
                    if function_call_seen:
                        dropped = True
                        self.batched_tool_calls_dropped += 1
                        continue
                    function_call_seen = True
                projected.append(item)
            if not dropped:
                return response
            return ModelResponse(
                output=projected,
                usage=response.usage,
                response_id=response.response_id,
                request_id=response.request_id,
            )

        def stream_response(self, *args, **kwargs):
            return self._delegate.stream_response(*args, **kwargs)

        def get_retry_advice(self, *args, **kwargs):
            return self._delegate.get_retry_advice(*args, **kwargs)

        async def _cleanup_on_run_end(self, owner: object) -> None:
            await self._delegate._cleanup_on_run_end(owner)

        async def close(self) -> None:
            await self._delegate.close()

    return SingleFunctionCallModel(model)


def build_glm_sdk_model_factory(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
) -> SdkModelFactory:
    def factory() -> tuple[object, Callable[[], Awaitable[None]]]:
        sdk_model = build_glm_sdk_model(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
        )
        return sdk_model, sdk_model_aclose(sdk_model)

    return factory


@dataclass(frozen=True)
class AgentsSdkTool:
    name: str
    description: str
    parameters: Mapping[str, object]
    invoke: Callable[[Mapping[str, object] | str], dict[str, object]]

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.description.strip():
            raise ValueError("SDK tool identity must be non-empty")
        object.__setattr__(
            self,
            "parameters",
            copy_tool_parameters(self.parameters),
        )


@dataclass(frozen=True)
class AgentsSdkRequest:
    instructions: str
    input: str
    tools: tuple[AgentsSdkTool, ...]
    max_turns: int
    timeout: float
    backend: SdkBackend
    model_name: str
    tool_timeout: float | None = None
    model: object | None = None
    model_settings: object | None = None
    model_factory: SdkModelFactory | None = None
    continuation_input: InitVar[object | None] = None

    def __post_init__(self, continuation_input: object | None) -> None:
        if not self.instructions.strip() or not self.input.strip():
            raise ValueError("SDK request prompts must be non-empty")
        if self.max_turns < 1 or self.timeout <= 0:
            raise ValueError("SDK request budget must be positive")
        if self.backend not in {"sdk_glm", "sdk_gpt"}:
            raise ValueError("unsupported SDK backend")
        if not self.model_name.strip():
            raise ValueError("SDK model name must be non-empty")
        if self.tool_timeout is not None and (
            self.tool_timeout <= 0 or self.tool_timeout > self.timeout
        ):
            raise ValueError("SDK tool timeout must fit within request timeout")
        object.__setattr__(self, "tools", tuple(self.tools))
        # Provider-owned history deliberately is not a dataclass field: repr(),
        # asdict(), public events, and JSON projections cannot accidentally
        # serialize the SDK continuation.
        object.__setattr__(
            self,
            "_provider_continuation",
            _OpaqueProviderContinuation(continuation_input),
        )

    @property
    def _continuation_input(self) -> object | None:
        return self._provider_continuation.value


@dataclass(frozen=True)
class AgentsSdkResult:
    final_output: object
    llm_calls: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_attempts: int | None = None
    batched_tool_calls_dropped: int = 0
    continuation_input: InitVar[object | None] = None

    def __post_init__(self, continuation_input: object | None) -> None:
        for name in (
            "llm_calls",
            "input_tokens",
            "output_tokens",
            "provider_attempts",
            "batched_tool_calls_dropped",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        object.__setattr__(
            self,
            "_provider_continuation",
            _OpaqueProviderContinuation(continuation_input),
        )

    @property
    def _continuation_input(self) -> object | None:
        return self._provider_continuation.value


class AgentsSdkRunner(Protocol):
    def __call__(self, request: AgentsSdkRequest) -> AgentsSdkResult: ...


def _provider_tool_schema(
    schema: Mapping[str, object],
    *,
    backend: SdkBackend,
) -> dict[str, object]:
    projected = copy_tool_parameters(schema)
    if backend != "sdk_gpt":
        return projected

    def visit(value: object) -> object:
        if isinstance(value, Mapping):
            projected = {
                str(key): visit(item)
                for key, item in value.items()
                if key != "uniqueItems"
            }
            # The local semantic schema deliberately leaves polymorphic scalar
            # values open (for example finance_query.filters.value). The
            # current OpenAI-compatible gateway rejects a schema node that has
            # descriptive metadata but no ``type``. Keep the domain schema
            # unchanged and give this provider a conservative string surface;
            # local argument validation remains authoritative after the call.
            if set(projected) == {"description"}:
                projected["type"] = "string"
            return projected
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    result = visit(projected)
    if not isinstance(result, dict):
        raise ValueError("tool schema projection must remain an object")
    return result


def _run_openai_agents_sdk(request: AgentsSdkRequest) -> AgentsSdkResult:
    from agents import (
        Agent,
        FunctionTool,
        RunConfig,
        Runner,
        set_trace_provider,
    )
    from agents.run_config import ToolExecutionConfig
    from agents.tracing.provider import DefaultTraceProvider

    # RunConfig alone is evaluated after the SDK initializes its default trace
    # exporter. Install a disabled provider with no processors first so a
    # private finance run never constructs an exporter or reads proxy settings.
    trace_provider = DefaultTraceProvider()
    trace_provider.set_disabled(True)
    set_trace_provider(trace_provider)

    function_tools: list[FunctionTool] = []
    for sdk_tool in request.tools:

        async def invoke_tool(
            _tool_context: object,
            arguments: str,
            *,
            tool: AgentsSdkTool = sdk_tool,
        ) -> str:
            try:
                value = json.loads(arguments)
            except json.JSONDecodeError:
                value = None
            arguments_object = value if isinstance(value, dict) else {}
            result = await asyncio.to_thread(tool.invoke, arguments_object)
            return json.dumps(result, ensure_ascii=False)

        function_tools.append(
            FunctionTool(
                name=sdk_tool.name,
                description=sdk_tool.description,
                params_json_schema=_provider_tool_schema(
                    sdk_tool.parameters,
                    backend=request.backend,
                ),
                on_invoke_tool=invoke_tool,
                strict_json_schema=True,
                timeout_seconds=request.tool_timeout or request.timeout,
                timeout_behavior="error_as_result",
            )
        )

    model = request.model or request.model_name
    model_aclose: Callable[[], Awaitable[None]] | None = None
    if request.model_factory is not None:
        model, model_aclose = request.model_factory()
    if request.backend == "sdk_gpt":
        model = _single_function_call_per_response(model)

    agent_instructions = request.instructions
    if request.backend == "sdk_gpt":
        agent_instructions += (
            "\nSDK 回合协议：每次模型响应最多调用一个工具。调用后立即停止，"
            "等待该工具的原始观察返回，再决定下一步；不要在同一响应中预先排队多个工具调用。"
        )
    agent = Agent(
        name="Foresight Finance Researcher",
        instructions=agent_instructions,
        tools=function_tools,
        model=model,
        model_settings=request.model_settings,
    )
    run_config = RunConfig(
        tracing_disabled=True,
        trace_include_sensitive_data=False,
        workflow_name="Foresight finance episode",
        tool_execution=ToolExecutionConfig(max_function_tool_concurrency=1),
    )

    async def execute() -> object:
        provider_input: object = request.input
        continuation_input = request._continuation_input
        if continuation_input is not None:
            if not isinstance(continuation_input, (list, tuple)):
                raise TypeError("SDK continuation input must be a provider input list")
            provider_input = [
                *continuation_input,
                {"role": "user", "content": request.input},
            ]
        try:
            return await asyncio.wait_for(
                Runner.run(
                    agent,
                    provider_input,
                    context=request,
                    max_turns=request.max_turns,
                    run_config=run_config,
                ),
                timeout=request.timeout,
            )
        finally:
            if model_aclose is not None:
                await model_aclose()

    try:
        result = asyncio.run(execute())
    except asyncio.TimeoutError as exc:
        raise TimeoutError("OpenAI Agents SDK run exceeded deadline") from exc
    usage = result.context_wrapper.usage
    to_input_list = getattr(result, "to_input_list", None)
    continuation_input = to_input_list() if callable(to_input_list) else None
    return AgentsSdkResult(
        final_output=result.final_output,
        llm_calls=max(1, int(usage.requests)),
        input_tokens=int(usage.input_tokens),
        output_tokens=int(usage.output_tokens),
        provider_attempts=int(usage.requests),
        batched_tool_calls_dropped=int(
            getattr(model, "batched_tool_calls_dropped", 0)
        ),
        continuation_input=continuation_input,
    )


@dataclass(frozen=True)
class _SdkSnapshot:
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    events: tuple[EpisodeEvent, ...]
    gaps: tuple[str, ...]
    executed_count: int
    duplicate_queries: int


class _AgentsRunState:
    def __init__(
        self,
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        is_cancelled: Callable[[], bool],
        event_sink: Callable[[EpisodeEvent], None] | None = None,
    ) -> None:
        self._registry = registry
        self._context = context
        self._active_context = context
        self._is_cancelled = is_cancelled
        self._event_sink = event_sink
        self._authorized = {
            spec.name: spec
            for spec in registry.authorized_specs(context.contract.allowed_capabilities)
        }
        self._contextvars: Context = copy_context()
        self._lock = Lock()
        self._seen_queries: set[tuple[str, str]] = set()
        self._successful_episode_tools: set[str] = set()
        self._evidence: list[AgentEvidence] = []
        self._evidence_hashes: set[str] = set()
        self._traces: list[ProviderTrace] = []
        self._events: list[EpisodeEvent] = []
        self._gaps: list[str] = []
        self._executed_count = 0
        self._duplicate_queries = 0
        self._next_sequence = 2
        self._tools_open = True
        self._continuation_call_limit: int | None = None
        self._continuation_executed_start = 0
        self.evidence_ledger = EvidenceLedger(
            information_cutoff=context.information_cutoff.as_of_date,
        )
        for required in context.contract.required_outputs:
            if required.required and required.grounding_mode == "evidence":
                self.evidence_ledger.open_gap(required.output_id)
        self.initial_evidence_snapshot = self.evidence_ledger.snapshot()

    def tools(self) -> tuple[AgentsSdkTool, ...]:
        if not self._tools_open:
            return ()
        return tuple(
            AgentsSdkTool(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
                invoke=lambda arguments, name=spec.name: self.invoke(name, arguments),
            )
            for spec in self._authorized.values()
        )

    def begin_continuation(
        self,
        *,
        context: ResearchRunContext,
        next_sequence: int,
        tools_open: bool,
        call_limit: int,
    ) -> tuple[int, int]:
        """Reuse the episode ledgers while bounding one repair segment."""

        with self._lock:
            self._active_context = context
            self._next_sequence = next_sequence
            self._tools_open = bool(tools_open and call_limit > 0)
            self._continuation_call_limit = max(0, int(call_limit))
            self._continuation_executed_start = self._executed_count
            return len(self._events), len(self._gaps)

    def prepare_next_sequence(self, sequence: int) -> None:
        with self._lock:
            self._next_sequence = max(self._next_sequence, int(sequence))

    def invoke(
        self,
        name: str,
        raw_arguments: Mapping[str, object] | str,
    ) -> dict[str, object]:
        with self._lock:
            try:
                prepared = self._registry.prepare(name, raw_arguments)
            except (InvalidResearchToolArguments, ValueError) as exc:
                error = (
                    exc.code
                    if isinstance(exc, InvalidResearchToolArguments)
                    else "unknown_or_unauthorized_tool"
                )
                self._add_event("tool_error", {"tool": name, "error": error})
                return {"status": "rejected", "tool": name, "error": error}
            request_event = self._add_event(
                "tool_request",
                {"tool": name, "query": prepared.display_query},
            )
            step_id = (
                f"{self._active_context.trace_parent_id}:sdk:tool:"
                f"{request_event.sequence - 1}"
            )
            rejected = self._reservation_error(name, prepared)
            if rejected is not None:
                if rejected == _SDK_STAGE_CLOSED:
                    self._add_event(
                        "tool_closed",
                        {"tool": name, "reason": rejected},
                    )
                    return {
                        "status": "closed",
                        "tool": name,
                        "error": rejected,
                        "instruction": _SDK_STAGE_CLOSED_INSTRUCTION,
                    }
                if rejected not in self._gaps:
                    self._gaps.append(rejected)
                self._add_event("tool_error", {"tool": name, "error": rejected})
                return {"status": "rejected", "tool": name, "error": rejected}
            root_budget = self._active_context.root_budget
            if root_budget is not None:
                try:
                    root_budget.consume_call(
                        seconds=_ROOT_BUDGET_CALL_RESERVATION_SECONDS,
                    )
                except ValueError:
                    rejected = "tool_budget_exhausted"
                    if rejected not in self._gaps:
                        self._gaps.append(rejected)
                    self._add_event(
                        "tool_error",
                        {"tool": name, "error": rejected},
                    )
                    return {
                        "status": "rejected",
                        "tool": name,
                        "error": rejected,
                    }
            spec = self._authorized[name]
            normalized = prepared.normalized_key
            self._seen_queries.add((name, normalized))
            self._executed_count += 1

        try:
            observation = self._contextvars.copy().run(
                self._registry.execute,
                name,
                prepared,
                context=self._active_context,
                step_id=step_id,
                is_cancelled=self._is_cancelled,
            )
        except Exception:
            trace = ProviderTrace(
                provider=f"sdk:{name}",
                capability=name,
                status="request_error",
                detail="tool_exception",
                parent_id=self._context.trace_parent_id,
                step_id=step_id,
            )
            with self._lock:
                self._traces.append(trace)
                self._add_event(
                    "tool_error",
                    {"tool": name, "error": "tool_exception"},
                )
            return {"status": "error", "tool": name, "error": "tool_exception"}
        return self._publish_observation(spec, observation)

    def snapshot(self) -> _SdkSnapshot:
        with self._lock:
            return _SdkSnapshot(
                evidence=tuple(self._evidence),
                traces=tuple(self._traces),
                events=tuple(self._events),
                gaps=tuple(self._gaps),
                executed_count=self._executed_count,
                duplicate_queries=self._duplicate_queries,
            )

    def _reservation_error(
        self,
        name: str,
        prepared: PreparedToolArguments,
    ) -> str | None:
        if self._is_cancelled():
            return "cancelled"
        if not self._tools_open:
            return _SDK_STAGE_CLOSED
        if self._active_context.deadline.expired:
            return "deadline_exhausted"
        if self._active_context.deadline.stage_timeout(1.0) <= 0.001:
            return _SDK_STAGE_CLOSED
        spec = self._authorized.get(name)
        if spec is None:
            return "unknown_or_unauthorized_tool"
        key = (name, prepared.normalized_key)
        if key in self._seen_queries:
            self._duplicate_queries += 1
            return "duplicate_query"
        if spec.query_scope == "episode" and name in self._successful_episode_tools:
            return "episode_snapshot_already_collected"
        if self._continuation_call_limit is not None and (
            self._executed_count - self._continuation_executed_start
            >= self._continuation_call_limit
        ):
            return "tool_budget_exhausted"
        root_budget = self._active_context.root_budget
        if root_budget is not None and root_budget.remaining_calls <= 0:
            return "tool_budget_exhausted"
        if root_budget is None and self._executed_count >= self._context.policy.max_steps:
            return "tool_budget_exhausted"
        return None

    def _publish_observation(
        self,
        spec: ToolSpec,
        observation: ToolObservation,
    ) -> dict[str, object]:
        with self._lock:
            if self._is_cancelled():
                self._add_event(
                    "tool_error",
                    {"tool": observation.tool, "error": "cancelled"},
                )
                return {
                    "status": "rejected",
                    "tool": observation.tool,
                    "error": "cancelled",
                }
            self._traces.append(observation.trace)
            for gap in observation.gaps:
                cleaned = gap.strip()
                if cleaned and cleaned not in self._gaps:
                    self._gaps.append(cleaned)
            new_evidence: list[AgentEvidence] = []
            for item in observation.evidence:
                if item.content_hash in self._evidence_hashes:
                    continue
                self._evidence_hashes.add(item.content_hash)
                self._evidence.append(item)
                new_evidence.append(item)
                self.evidence_ledger.append(item)
            if spec.query_scope == "episode" and observation.evidence:
                self._successful_episode_tools.add(observation.tool)
            if new_evidence:
                status = "success"
                public_observation = observation.observation
            elif observation.evidence:
                status = "duplicate_evidence"
                public_observation = (
                    "本次查询未增加新证据；返回内容与本轮已有证据重复，"
                    "请改变证据类型或基于现有证据完成回答。"
                )
            else:
                status = "empty"
                public_observation = observation.observation
            payload: dict[str, object] = {
                "status": status,
                "tool": observation.tool,
                "query": observation.query,
                "observation": public_observation,
                "evidence": [
                    public_agent_evidence(item) for item in new_evidence
                ],
                "evidence_hashes": [item.content_hash for item in new_evidence],
                "gaps": list(observation.gaps),
            }
            self._add_event("tool_result", payload)
            return payload

    def _add_event(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        event = EpisodeEvent(self._next_sequence, kind, payload)
        self._next_sequence += 1
        self._events.append(event)
        if self._event_sink is not None:
            self._event_sink(event)
        return event


class _SdkContinuationState:
    __slots__ = (
        "task_frame",
        "context",
        "registry",
        "run_state",
        "_provider_continuation",
    )

    def __init__(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        run_state: _AgentsRunState,
        continuation_input: object | None,
    ) -> None:
        self.task_frame = task_frame
        self.context = context
        self.registry = registry
        self.run_state = run_state
        self._provider_continuation = _OpaqueProviderContinuation(
            continuation_input
        )

    @property
    def continuation_input(self) -> object | None:
        return self._provider_continuation.value

    @continuation_input.setter
    def continuation_input(self, value: object | None) -> None:
        self._provider_continuation = _OpaqueProviderContinuation(value)

    def __repr__(self) -> str:
        return "<_SdkContinuationState provider_history=<opaque>>"


class OpenAIAgentsRuntime:
    """Run one finance task with an SDK-managed model/tool loop."""

    def __init__(
        self,
        *,
        runner: AgentsSdkRunner | None = None,
        backend: SdkBackend,
        model_name: str,
        model: object | None = None,
        model_settings: object | None = None,
        model_factory: SdkModelFactory | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        event_sink: Callable[[EpisodeEvent], None] | None = None,
    ) -> None:
        if backend not in {"sdk_glm", "sdk_gpt"}:
            raise ValueError("unsupported SDK backend")
        if not str(model_name or "").strip():
            raise ValueError("SDK model name must be non-empty")
        if (
            runner is None
            and backend == "sdk_glm"
            and model is None
            and model_factory is None
        ):
            raise ValueError(
                "sdk_glm default runner requires an explicit model adapter"
            )
        self._runner = runner or _run_openai_agents_sdk
        self._backend = backend
        self._model_name = model_name.strip()
        self._model = model
        self._model_settings = model_settings or build_agents_model_settings(backend)
        self._delivery_model_settings = (
            build_agents_delivery_model_settings(backend)
            if backend == "sdk_gpt" and model_settings is None
            else self._model_settings
        )
        self._model_factory = model_factory
        self._is_cancelled = is_cancelled or (lambda: False)
        self._event_sink = event_sink

    def _publish_event(self, event: EpisodeEvent) -> None:
        if self._event_sink is None or self._is_cancelled():
            return
        try:
            self._event_sink(event)
        except Exception:
            # Progress is observability, never an alternate execution owner.
            # A broken UI/SSE sink must not abort financial research.
            pass

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome:
        return self._run_episode(
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
        continuation: list[_SdkContinuationState] = []
        outcome = self._run_episode(
            task_frame=task_frame,
            context=context,
            registry=registry,
            continuation_sink=continuation,
        )
        if not continuation:
            fallback_state = _AgentsRunState(
                registry=registry,
                context=context,
                is_cancelled=self._is_cancelled,
                event_sink=self._publish_event,
            )
            continuation.append(
                _SdkContinuationState(
                    task_frame=task_frame,
                    context=context,
                    registry=registry,
                    run_state=fallback_state,
                    continuation_input=None,
                )
            )
        if len(continuation) != 1:
            raise RuntimeError("SDK episode continuation state was not captured")
        state = continuation[0]
        return CallbackEpisodeSession(
            episode_id=context.contract.task_id,
            outcome=outcome,
            resume_callback=lambda previous, goal: self._resume_episode(
                state,
                previous,
                goal,
            ),
            evidence_ledger=state.run_state.evidence_ledger,
            initial_evidence_snapshot=state.run_state.initial_evidence_snapshot,
        )

    def _run_episode(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        continuation_sink: list[_SdkContinuationState] | None = None,
    ) -> AgentOutcome:
        if (
            context.contract.task_frame_hash
            and context.contract.task_frame_hash != task_frame.task_frame_hash
        ):
            raise ValueError("research contract task frame hash mismatch")
        if self._is_cancelled():
            return _failed_outcome(
                task_frame,
                stop_reason="cancelled",
                gap="本轮执行已取消",
            )

        self._publish_event(
            EpisodeEvent(
                1,
                "task",
                {
                    "question": task_frame.raw_question,
                    "task_frame": task_frame.to_dict(),
                    "task_frame_hash": task_frame.task_frame_hash,
                },
            )
        )

        state = _AgentsRunState(
            registry=registry,
            context=context,
            is_cancelled=self._is_cancelled,
            event_sink=self._publish_event,
        )
        continuation_state: _SdkContinuationState | None = None
        if continuation_sink is not None:
            continuation_state = _SdkContinuationState(
                task_frame=task_frame,
                context=context,
                registry=registry,
                run_state=state,
                continuation_input=None,
            )
            continuation_sink.append(continuation_state)
        runtime_timeout = _sdk_runtime_timeout(context)
        if runtime_timeout <= 0.001:
            return self._failure_from_state(
                task_frame=task_frame,
                state=state,
                stop_reason="sdk_runtime_budget_exhausted",
                gap="sdk_runtime_budget_exhausted",
                llm_calls=0,
            )
        request = AgentsSdkRequest(
            instructions=build_episode_instructions(task_frame, context, registry),
            input=build_episode_input(task_frame, context),
            tools=state.tools(),
            max_turns=max(2, context.policy.max_steps + 2),
            timeout=runtime_timeout,
            backend=self._backend,
            model_name=self._model_name,
            model=self._model,
            model_settings=self._model_settings,
            model_factory=self._model_factory,
        )
        try:
            result = self._call_runner(request, context=context)
        except TimeoutError:
            return self._failure_from_state(
                task_frame=task_frame,
                state=state,
                stop_reason="sdk_timeout",
                gap="sdk_timeout",
                llm_calls=1,
            )
        except Exception as exc:
            stop_reason = _sdk_run_error_kind(exc)
            return self._failure_from_state(
                task_frame=task_frame,
                state=state,
                stop_reason=stop_reason,
                gap=stop_reason,
                llm_calls=1,
            )
        if continuation_state is not None:
            continuation_state.continuation_input = result._continuation_input

        snapshot = state.snapshot()
        try:
            finish = validate_episode_finish(
                result.final_output,
                context=context,
                evidence=snapshot.evidence,
            )
        except ValueError:
            # Invalid delivery is a verifier gap, not a private SDK retry.  The
            # adapter owns the one shared RepairGoal cycle pool for every gap.
            return self._failure_from_snapshot(
                task_frame=task_frame,
                snapshot=snapshot,
                stop_reason="sdk_invalid_finish",
                gap="sdk_invalid_finish",
                llm_calls=max(1, result.llm_calls),
                result=result,
            )

        bindings = expand_episode_snapshot_bindings(
            bindings=finish.bindings,
            evidence=snapshot.evidence,
            registry=registry,
        )
        gaps = tuple(dict.fromkeys((*snapshot.gaps, *finish.gaps)))
        execution_gap = next(
            (gap for gap in snapshot.gaps if gap in _PARTIAL_EXECUTION_GAPS),
            None,
        )
        status = (
            "partial"
            if finish.status == "completed" and execution_gap is not None
            else finish.status
        )
        stop_reason = execution_gap or "model_finish"
        events = self._events(
            task_frame=task_frame,
            snapshot=snapshot,
            result=result,
            status=status,
            stop_reason=stop_reason,
            gaps=gaps,
        )
        outcome = AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft=finish.draft,
            evidence=snapshot.evidence,
            traces=snapshot.traces,
            gaps=gaps,
            stop_reason=stop_reason,
            events=events,
            bindings=bindings,
            usage=AgentUsage(
                llm_calls=result.llm_calls,
                tool_calls=snapshot.executed_count,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            ),
        )
        state.prepare_next_sequence(len(outcome.events) + 1)
        return outcome

    def _resume_episode(
        self,
        state: _SdkContinuationState,
        previous: AgentOutcome,
        goal: RepairGoal,
    ) -> AgentOutcome:
        context = state.context
        root_budget = context.root_budget
        available_calls = max(0, int(goal.remaining_calls))
        available_seconds = max(0.0, float(goal.remaining_seconds))
        if root_budget is not None:
            available_calls = min(
                available_calls,
                max(0, int(root_budget.remaining_calls)),
            )
            available_seconds = min(
                available_seconds,
                max(0.0, float(root_budget.remaining_seconds)),
            )
        if available_seconds <= 0.001:
            raise EpisodeSessionError("repair continuation budget is exhausted")
        effective_goal = replace(
            goal,
            remaining_calls=available_calls,
            remaining_seconds=available_seconds,
        )

        # A repair grant can outlive the original research window for wording
        # or evidence-binding fixes. It must never reopen research tools once
        # that original window has closed.
        repair_deadline = ResearchDeadline.from_timeout(available_seconds)
        repair_tool_deadline = context.deadline.bounded_stage(available_seconds)
        repair_tool_context = replace(context, deadline=repair_tool_deadline)
        research_tool_timeout = repair_tool_deadline.remaining()
        original_tools_open = (
            research_tool_timeout > 0.001 and available_calls > 0
        )
        if state.continuation_input is None and original_tools_open:
            raise EpisodeSessionError(
                "SDK provider continuation is required to reopen research tools"
            )
        repair_context = replace(context, deadline=repair_deadline)
        prefix = previous.events
        repair_goal_event = EpisodeEvent(
            len(prefix) + 1,
            "repair_goal",
            _bounded_repair_goal(effective_goal),
        )
        repair_reentry_event = EpisodeEvent(
            len(prefix) + 2,
            "repair_reentry",
            {
                "episode_id": goal.episode_id,
                "repair_goal_id": goal.repair_goal_id,
                "cycle": goal.cycle,
                "continuation_mode": (
                    "provider_history"
                    if state.continuation_input is not None
                    else "canonical_snapshot"
                ),
            },
        )
        self._publish_event(repair_goal_event)
        self._publish_event(repair_reentry_event)
        state_event_start, state_gap_start = state.run_state.begin_continuation(
            # Intersect the grant with the original absolute research-stage
            # deadline. Re-wrapping a remaining duration would extend the
            # window while the provider prepares the continuation request.
            context=repair_tool_context,
            next_sequence=len(prefix) + 3,
            tools_open=original_tools_open,
            call_limit=available_calls,
        )
        tools = state.run_state.tools()
        repair_snapshot = state.run_state.snapshot()
        repair_input: dict[str, object] = {
            "kind": "REPAIR_GOAL",
            **_bounded_repair_goal(effective_goal),
        }
        if state.continuation_input is None:
            repair_input.update(
                {
                    "task": json.loads(
                        build_episode_input(
                            state.task_frame,
                            repair_context,
                        )
                    ),
                    "evidence": [
                        public_agent_evidence(item)
                        for item in repair_snapshot.evidence
                    ],
                    "existing_draft": previous.draft,
                    "existing_bindings": [
                        binding.to_dict() for binding in previous.bindings
                    ],
                    "existing_gaps": list(previous.gaps),
                }
            )
        request = AgentsSdkRequest(
            instructions=(
                build_episode_instructions(
                    state.task_frame,
                    repair_context,
                    state.registry,
                )
                + "\n这是同一 episode 的 verifier 修复轮。保留全部原始观察、"
                "查询去重账本和任务身份；只补 RepairGoal 指定缺口，不得重启研究。"
                + (
                    ""
                    if tools
                    else "研究工具已关闭；只允许基于已有观察修复措辞或证据绑定。"
                )
                + (
                    ""
                    if state.continuation_input is not None
                    else "上轮因有界超时未返回 provider history；本轮给出的 canonical "
                    "snapshot 是同一 episode 的权威状态，只能据此完成交付，不得重启研究。"
                )
            ),
            input=json.dumps(repair_input, ensure_ascii=False),
            tools=tools,
            max_turns=max(1, available_calls + 1) if tools else 1,
            timeout=min(available_seconds, 30.0) if not tools else available_seconds,
            backend=self._backend,
            model_name=self._model_name,
            tool_timeout=research_tool_timeout if tools else None,
            model=self._model,
            model_settings=(
                self._model_settings if tools else self._delivery_model_settings
            ),
            model_factory=self._model_factory,
            continuation_input=state.continuation_input,
        )
        try:
            result = self._call_runner(request, context=context)
        except TimeoutError:
            result = None
            run_error = "sdk_timeout"
        except Exception as exc:
            result = None
            run_error = _sdk_run_error_kind(exc)
        else:
            run_error = ""
        snapshot = state.run_state.snapshot()
        appended: list[EpisodeEvent] = [repair_goal_event, repair_reentry_event]
        appended.extend(snapshot.events[state_event_start:])
        model_turn_event = EpisodeEvent(
            len(prefix) + len(appended) + 1,
            "model_turn",
            {
                "phase": "repair",
                "runtime": self._backend,
                "repair_goal_id": goal.repair_goal_id,
                "cycle": goal.cycle,
                "provider_attempts": (
                    result.provider_attempts if result is not None else None
                ),
                "error": run_error,
            },
        )
        appended.append(model_turn_event)
        self._publish_event(model_turn_event)
        if result is None:
            gaps = tuple(dict.fromkeys((*previous.gaps, run_error)))
            appended.extend(
                self._continuation_terminal_events(
                    sequence=len(prefix) + len(appended) + 1,
                    result=None,
                    status="partial" if snapshot.evidence else "failed",
                    stop_reason=run_error,
                    gaps=gaps,
                    snapshot=snapshot,
                )
            )
            return AgentOutcome(
                task_frame_hash=previous.task_frame_hash,
                status="partial" if snapshot.evidence else "failed",
                draft=previous.draft,
                evidence=snapshot.evidence,
                traces=snapshot.traces,
                gaps=gaps,
                stop_reason=run_error,
                events=(*prefix, *appended),
                bindings=previous.bindings,
                usage=AgentUsage(
                    llm_calls=previous.usage.llm_calls + 1,
                    tool_calls=snapshot.executed_count,
                    invalid_actions=previous.usage.invalid_actions + 1,
                    input_tokens=previous.usage.input_tokens,
                    output_tokens=previous.usage.output_tokens,
                ),
                plan=previous.plan,
            )

        try:
            finish = validate_episode_finish(
                result.final_output,
                context=repair_context,
                evidence=snapshot.evidence,
            )
        except ValueError:
            finish = None
        if finish is None:
            status = "partial" if snapshot.evidence else "failed"
            stop_reason = "sdk_invalid_repair_finish"
            gaps = tuple(dict.fromkeys((*previous.gaps, stop_reason)))
            draft = previous.draft
            bindings = previous.bindings
            invalid_actions = previous.usage.invalid_actions + 1
        else:
            execution_gap = next(
                (
                    gap
                    for gap in snapshot.gaps[state_gap_start:]
                    if gap in _PARTIAL_EXECUTION_GAPS
                ),
                None,
            )
            status = (
                "partial"
                if finish.status == "completed" and execution_gap is not None
                else finish.status
            )
            stop_reason = execution_gap or "repair_model_finish"
            gaps = tuple(
                dict.fromkeys((*previous.gaps, *snapshot.gaps, *finish.gaps))
            )
            draft = finish.draft
            bindings = expand_episode_snapshot_bindings(
                bindings=finish.bindings,
                evidence=snapshot.evidence,
                registry=state.registry,
            )
            invalid_actions = previous.usage.invalid_actions
        appended.extend(
            self._continuation_terminal_events(
                sequence=len(prefix) + len(appended) + 1,
                result=result,
                status=status,
                stop_reason=stop_reason,
                gaps=gaps,
                snapshot=snapshot,
            )
        )
        outcome = AgentOutcome(
            task_frame_hash=previous.task_frame_hash,
            status=status,
            draft=draft,
            evidence=snapshot.evidence,
            traces=snapshot.traces,
            gaps=gaps,
            stop_reason=stop_reason,
            events=(*prefix, *appended),
            bindings=bindings,
            usage=AgentUsage(
                llm_calls=previous.usage.llm_calls + result.llm_calls,
                tool_calls=snapshot.executed_count,
                invalid_actions=invalid_actions,
                input_tokens=_sum_optional_counts(
                    previous.usage.input_tokens,
                    result.input_tokens,
                ),
                output_tokens=_sum_optional_counts(
                    previous.usage.output_tokens,
                    result.output_tokens,
                ),
            ),
            plan=previous.plan,
        )
        state.continuation_input = result._continuation_input
        state.run_state.prepare_next_sequence(len(outcome.events) + 1)
        return outcome

    def _call_runner(
        self,
        request: AgentsSdkRequest,
        *,
        context: ResearchRunContext,
    ) -> AgentsSdkResult:
        started = monotonic()
        try:
            result = self._runner(request)
        except Exception:
            _consume_root_seconds(context, monotonic() - started)
            raise
        if not _consume_root_seconds(context, monotonic() - started):
            raise TimeoutError("SDK root budget exhausted")
        return result

    def _continuation_terminal_events(
        self,
        *,
        sequence: int,
        result: AgentsSdkResult | None,
        status: str,
        stop_reason: str,
        gaps: tuple[str, ...],
        snapshot: _SdkSnapshot,
    ) -> tuple[EpisodeEvent, EpisodeEvent]:
        events = (
            EpisodeEvent(
                sequence,
                "runtime_result",
                {
                    "runtime": self._backend,
                    "model": self._model_name,
                    "input_tokens": result.input_tokens if result else None,
                    "output_tokens": result.output_tokens if result else None,
                    "provider_attempts": (
                        result.provider_attempts if result else None
                    ),
                    "duplicate_queries": snapshot.duplicate_queries,
                    "batched_tool_calls_dropped": (
                        result.batched_tool_calls_dropped if result else 0
                    ),
                },
            ),
            EpisodeEvent(
                sequence + 1,
                "finish",
                {"status": status, "stop_reason": stop_reason, "gaps": list(gaps)},
            ),
        )
        for event in events:
            self._publish_event(event)
        return events

    def _failure_from_state(
        self,
        *,
        task_frame: TaskFrame,
        state: _AgentsRunState,
        stop_reason: str,
        gap: str,
        llm_calls: int,
    ) -> AgentOutcome:
        return self._failure_from_snapshot(
            task_frame=task_frame,
            snapshot=state.snapshot(),
            stop_reason=stop_reason,
            gap=gap,
            llm_calls=llm_calls,
            result=None,
        )

    def _failure_from_snapshot(
        self,
        *,
        task_frame: TaskFrame,
        snapshot: _SdkSnapshot,
        stop_reason: str,
        gap: str,
        llm_calls: int,
        result: AgentsSdkResult | None,
    ) -> AgentOutcome:
        gaps = tuple(dict.fromkeys((*snapshot.gaps, gap)))
        status = "partial" if snapshot.evidence else "failed"
        events = self._events(
            task_frame=task_frame,
            snapshot=snapshot,
            result=result,
            status=status,
            stop_reason=stop_reason,
            gaps=gaps,
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft="",
            evidence=snapshot.evidence,
            traces=snapshot.traces,
            gaps=gaps,
            stop_reason=stop_reason,
            events=events,
            bindings=(),
            usage=AgentUsage(
                llm_calls=llm_calls,
                tool_calls=snapshot.executed_count,
                invalid_actions=1,
                input_tokens=result.input_tokens if result else None,
                output_tokens=result.output_tokens if result else None,
            ),
        )

    def _events(
        self,
        *,
        task_frame: TaskFrame,
        snapshot: _SdkSnapshot,
        result: AgentsSdkResult | None,
        status: str,
        stop_reason: str,
        gaps: tuple[str, ...],
    ) -> tuple[EpisodeEvent, ...]:
        events = [
            EpisodeEvent(
                1,
                "task",
                {
                    "question": task_frame.raw_question,
                    "task_frame": task_frame.to_dict(),
                    "task_frame_hash": task_frame.task_frame_hash,
                },
            ),
            *snapshot.events,
        ]
        events.append(
            EpisodeEvent(
                len(events) + 1,
                "runtime_result",
                {
                    "runtime": self._backend,
                    "model": self._model_name,
                    "input_tokens": result.input_tokens if result else None,
                    "output_tokens": result.output_tokens if result else None,
                    "provider_attempts": result.provider_attempts if result else None,
                    "duplicate_queries": snapshot.duplicate_queries,
                    "batched_tool_calls_dropped": (
                        result.batched_tool_calls_dropped if result else 0
                    ),
                },
            )
        )
        events.append(
            EpisodeEvent(
                len(events) + 1,
                "finish",
                {"status": status, "stop_reason": stop_reason, "gaps": list(gaps)},
            )
        )
        self._publish_event(events[-2])
        self._publish_event(events[-1])
        return tuple(events)


def _failed_outcome(
    task_frame: TaskFrame,
    *,
    stop_reason: str,
    gap: str,
) -> AgentOutcome:
    return AgentOutcome(
        task_frame_hash=task_frame.task_frame_hash,
        status="failed",
        draft="",
        evidence=(),
        traces=(),
        gaps=(gap,),
        stop_reason=stop_reason,
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": task_frame.task_frame_hash},
            ),
        ),
        bindings=(),
        usage=AgentUsage(),
    )


def _bounded_repair_goal(goal: RepairGoal) -> dict[str, object]:
    def strings(values: tuple[str, ...]) -> list[str]:
        return [str(value)[:500] for value in values[:20]]

    return {
        "episode_id": goal.episode_id,
        "repair_goal_id": goal.repair_goal_id,
        "cycle": goal.cycle,
        "missing_answer_elements": strings(goal.missing_answer_elements),
        "unsupported_claims": strings(goal.unsupported_claims),
        "missing_evidence_modes": strings(goal.missing_evidence_modes),
        "attempted_actions": strings(goal.attempted_actions),
        "evidence_progress": {
            "new_evidence": goal.evidence_progress.new_evidence,
            "narrowed_gaps": goal.evidence_progress.narrowed_gaps,
            "newly_supported_outputs": (
                goal.evidence_progress.newly_supported_outputs
            ),
        },
        "remaining_calls": max(0, int(goal.remaining_calls)),
        "remaining_seconds": max(0.0, float(goal.remaining_seconds)),
    }


def _consume_root_seconds(context: ResearchRunContext, seconds: float) -> bool:
    root_budget = context.root_budget
    if root_budget is None:
        return True
    try:
        root_budget.consume_seconds(seconds=max(0.0, float(seconds)))
    except ValueError:
        remaining = max(0.0, float(root_budget.remaining_seconds))
        if remaining > 0.0:
            root_budget.consume_seconds(seconds=remaining)
        return False
    return True


def _sum_optional_counts(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)


def _sdk_run_error_kind(exc: Exception) -> str:
    normalized = " ".join(str(exc).lower().split())
    if (
        any(
            marker in normalized
            for marker in ("auth_unavailable", "authentication", "invalid_api_key")
        )
        or "status code: 401" in normalized
    ):
        return "sdk_auth_unavailable"
    if any(
        marker in normalized
        for marker in ("rate_limit", "rate limit", "status code: 429")
    ):
        return "sdk_rate_limited"
    if any(
        marker in normalized
        for marker in ("upstream_error", "service unavailable", "status code: 503")
    ):
        return "sdk_upstream_unavailable"
    if any(
        marker in normalized
        for marker in ("connection error", "connecterror", "connection refused")
    ):
        return "sdk_transport_unavailable"
    try:
        from agents.exceptions import MaxTurnsExceeded
    except ImportError:
        return "sdk_dependency_missing"
    if isinstance(exc, MaxTurnsExceeded):
        return "sdk_turn_limit"
    return "sdk_run_failed"


__all__ = [
    "AgentsSdkRequest",
    "AgentsSdkResult",
    "AgentsSdkRunner",
    "AgentsSdkTool",
    "OpenAIAgentsRuntime",
    "SdkBackend",
    "SdkModelFactory",
    "build_agents_delivery_model_settings",
    "build_agents_model_settings",
    "build_glm_sdk_model",
    "build_glm_sdk_model_factory",
    "build_gpt_sdk_model",
    "sdk_model_aclose",
]
