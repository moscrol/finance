"""OpenAI Agents SDK adapter over the canonical finance runtime seam."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextvars import Context, copy_context
from dataclasses import dataclass
import json
from threading import Lock
from typing import Literal, Protocol

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    public_agent_evidence,
)
from intelligence.services.episode_protocol import (
    build_episode_input,
    build_episode_instructions,
    expand_episode_snapshot_bindings,
    validate_episode_finish,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
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
    return max(
        0.0,
        context.deadline.remaining() - _sdk_verifier_reserve(context),
    )


def _allows_evidence_free_completion(context: ResearchRunContext) -> bool:
    required = tuple(
        item for item in context.contract.required_outputs if item.required
    )
    return bool(required) and all(
        item.grounding_mode in {"user_premise", "model_reasoning"} for item in required
    )


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


def sdk_model_aclose(model: object) -> Callable[[], Awaitable[None]]:
    client = getattr(model, "_client", None)
    close = getattr(client, "close", None)
    if not callable(close):
        raise ValueError("SDK model does not expose an async client close hook")
    return close


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
    model: object | None = None
    model_settings: object | None = None
    model_factory: SdkModelFactory | None = None

    def __post_init__(self) -> None:
        if not self.instructions.strip() or not self.input.strip():
            raise ValueError("SDK request prompts must be non-empty")
        if self.max_turns < 1 or self.timeout <= 0:
            raise ValueError("SDK request budget must be positive")
        if self.backend not in {"sdk_glm", "sdk_gpt"}:
            raise ValueError("unsupported SDK backend")
        if not self.model_name.strip():
            raise ValueError("SDK model name must be non-empty")
        object.__setattr__(self, "tools", tuple(self.tools))


@dataclass(frozen=True)
class AgentsSdkResult:
    final_output: object
    llm_calls: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_attempts: int | None = None

    def __post_init__(self) -> None:
        for name in ("llm_calls", "input_tokens", "output_tokens", "provider_attempts"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


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
            return {
                str(key): visit(item)
                for key, item in value.items()
                if key != "uniqueItems"
            }
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
                timeout_seconds=request.timeout,
                timeout_behavior="error_as_result",
            )
        )

    model = request.model or request.model_name
    model_aclose: Callable[[], Awaitable[None]] | None = None
    if request.model_factory is not None:
        model, model_aclose = request.model_factory()

    agent = Agent(
        name="Foresight Finance Researcher",
        instructions=request.instructions,
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
        try:
            return await asyncio.wait_for(
                Runner.run(
                    agent,
                    request.input,
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
    return AgentsSdkResult(
        final_output=result.final_output,
        llm_calls=max(1, int(usage.requests)),
        input_tokens=int(usage.input_tokens),
        output_tokens=int(usage.output_tokens),
        provider_attempts=int(usage.requests),
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
    ) -> None:
        self._registry = registry
        self._context = context
        self._is_cancelled = is_cancelled
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

    def tools(self) -> tuple[AgentsSdkTool, ...]:
        return tuple(
            AgentsSdkTool(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
                invoke=lambda arguments, name=spec.name: self.invoke(name, arguments),
            )
            for spec in self._authorized.values()
        )

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
                f"{self._context.trace_parent_id}:sdk:tool:{request_event.sequence - 1}"
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
            spec = self._authorized[name]
            normalized = prepared.normalized_key
            self._seen_queries.add((name, normalized))
            self._executed_count += 1

        try:
            observation = self._contextvars.copy().run(
                self._registry.execute,
                name,
                prepared,
                context=self._context,
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
        if self._context.deadline.expired:
            return "deadline_exhausted"
        if self._context.deadline.stage_timeout(1.0) <= 0.001:
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
        if self._executed_count >= self._context.policy.max_steps:
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
            for item in observation.evidence:
                if item.content_hash in self._evidence_hashes:
                    continue
                self._evidence_hashes.add(item.content_hash)
                self._evidence.append(item)
            if spec.query_scope == "episode" and observation.evidence:
                self._successful_episode_tools.add(observation.tool)
            status = "success" if observation.evidence else "empty"
            payload: dict[str, object] = {
                "status": status,
                "tool": observation.tool,
                "query": observation.query,
                "observation": observation.observation,
                "evidence": [
                    public_agent_evidence(item) for item in observation.evidence
                ],
                "evidence_hashes": list(observation.evidence_hashes),
                "gaps": list(observation.gaps),
            }
            self._add_event("tool_result", payload)
            return payload

    def _add_event(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        event = EpisodeEvent(self._next_sequence, kind, payload)
        self._next_sequence += 1
        self._events.append(event)
        return event


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
        self._model_factory = model_factory
        self._is_cancelled = is_cancelled or (lambda: False)

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

    def _run_episode(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
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

        state = _AgentsRunState(
            registry=registry,
            context=context,
            is_cancelled=self._is_cancelled,
        )
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
            result = self._runner(request)
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

        snapshot = state.snapshot()
        recovered = False
        try:
            finish = validate_episode_finish(
                result.final_output,
                context=context,
                evidence=snapshot.evidence,
            )
        except ValueError:
            recovery_timeout = _sdk_runtime_timeout(context)
            if (
                snapshot.evidence or _allows_evidence_free_completion(context)
            ) and recovery_timeout >= 1.0:
                repair_request = AgentsSdkRequest(
                    instructions=(
                        build_episode_instructions(
                            task_frame,
                            context,
                            registry,
                        )
                        + "\n"
                        "研究阶段已经关闭，禁止调用任何工具。"
                        "只修复终止 JSON envelope，不得增加新事实。"
                        "evidence grounding 只能引用给定证据哈希；"
                        "user_premise/model_reasoning 必须按 grounding_mode 完成，"
                        "不得伪造证据哈希。缺失输出必须写 gap。"
                        "上方工具列表仅用于理解证据来源，本轮没有可调用工具。"
                    ),
                    input=json.dumps(
                        {
                            "task": json.loads(
                                build_episode_input(task_frame, context)
                            ),
                            "required_outputs": context.contract.to_dict()[
                                "required_outputs"
                            ],
                            "evidence": [
                                public_agent_evidence(item)
                                for item in snapshot.evidence
                            ],
                            "existing_gaps": list(snapshot.gaps),
                            "invalid_output": _repair_output_text(result.final_output),
                        },
                        ensure_ascii=False,
                    ),
                    tools=(),
                    max_turns=1,
                    timeout=recovery_timeout,
                    backend=self._backend,
                    model_name=self._model_name,
                    model=self._model,
                    model_settings=self._model_settings,
                    model_factory=self._model_factory,
                )
                try:
                    repair_result = self._runner(repair_request)
                except Exception:
                    return self._failure_from_snapshot(
                        task_frame=task_frame,
                        snapshot=snapshot,
                        stop_reason="sdk_invalid_finish",
                        gap="sdk_invalid_finish",
                        llm_calls=max(1, result.llm_calls) + 1,
                        result=result,
                    )
                result = _merge_sdk_results(result, repair_result)
                try:
                    finish = validate_episode_finish(
                        result.final_output,
                        context=context,
                        evidence=snapshot.evidence,
                    )
                    recovered = True
                except ValueError:
                    return self._failure_from_snapshot(
                        task_frame=task_frame,
                        snapshot=snapshot,
                        stop_reason="sdk_invalid_finish",
                        gap="sdk_invalid_finish",
                        llm_calls=max(1, result.llm_calls),
                        result=result,
                    )
            else:
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
        stop_reason = execution_gap or (
            "sdk_finalization_recovered" if recovered else "model_finish"
        )
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
            ),
        )

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


def _merge_sdk_results(
    initial: AgentsSdkResult,
    recovery: AgentsSdkResult,
) -> AgentsSdkResult:
    return AgentsSdkResult(
        final_output=recovery.final_output,
        llm_calls=initial.llm_calls + recovery.llm_calls,
        input_tokens=_sum_optional_counts(
            initial.input_tokens,
            recovery.input_tokens,
        ),
        output_tokens=_sum_optional_counts(
            initial.output_tokens,
            recovery.output_tokens,
        ),
        provider_attempts=_sum_optional_counts(
            initial.provider_attempts,
            recovery.provider_attempts,
        ),
    )


def _repair_output_text(value: object, *, max_chars: int = 16000) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:max_chars]


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
    "build_agents_model_settings",
    "build_glm_sdk_model",
    "build_glm_sdk_model_factory",
    "build_gpt_sdk_model",
    "sdk_model_aclose",
]
