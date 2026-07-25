"""Continuous model/tool loop for one bounded financial research turn."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    EpisodeStatus,
    ModelToolCall,
    ModelTurn,
    public_agent_evidence,
)
from intelligence.services.episode_finalizer import (
    MIN_FINALIZATION_RECOVERY_SECONDS,
    EpisodeFinalizer,
)
from intelligence.services.episode_protocol import (
    build_episode_input,
    build_episode_instructions,
    expand_episode_snapshot_bindings,
    validate_episode_finish,
)
from intelligence.services.episode_tool_batch import (
    EpisodeToolBatchSession,
    ToolBatchExecutor,
    ToolBatchResult,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
)
from intelligence.services.task_frame import TaskFrame


DEFAULT_LLM_TIMEOUT = 20.0
MIN_PLANNING_TURN_SECONDS = 8.0


class _EpisodeLedger:
    def __init__(self, task_frame: TaskFrame) -> None:
        self._task_frame_hash = task_frame.task_frame_hash
        self.events: list[EpisodeEvent] = []
        self.add(
            "task",
            {
                "question": task_frame.raw_question,
                "task_frame": task_frame.to_dict(),
            },
        )

    def add(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        event_payload = dict(payload)
        event_payload["task_frame_hash"] = self._task_frame_hash
        event = EpisodeEvent(len(self.events) + 1, kind, event_payload)
        self.events.append(event)
        return event


@dataclass
class _EpisodeToolAccumulator:
    messages: list[dict[str, object]]
    ledger: _EpisodeLedger
    evidence: list[AgentEvidence] = field(default_factory=list)
    evidence_hashes: set[str] = field(default_factory=set)
    successful_tools: set[str] = field(default_factory=set)
    traces: list[ProviderTrace] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def consume(
        self,
        batch: ToolBatchResult,
        context: ResearchRunContext,
    ) -> int:
        invalid_actions = 0
        for result in batch.items:
            call = result.call
            self.ledger.add("tool_request", call.to_dict())

            if result.status == "rejected":
                invalid_actions += 1
                if result.error == "unknown_or_unauthorized_tool":
                    self.traces.append(
                        ProviderTrace(
                            provider="episode:tool_gate",
                            capability=call.name,
                            status="disabled",
                            detail=result.error,
                            parent_id=context.trace_parent_id,
                            step_id=result.step_id,
                        )
                    )
                self._append_tool_error(call, result.error)
                continue

            if result.status in {"error", "timeout"}:
                public_error = (
                    "tool_timeout" if result.status == "timeout" else "tool_exception"
                )
                self.traces.append(
                    ProviderTrace(
                        provider=f"agent:{call.name}",
                        capability=call.name,
                        status="request_error",
                        detail=public_error,
                        parent_id=context.trace_parent_id,
                        step_id=result.step_id,
                    )
                )
                self._append_tool_error(call, public_error)
                continue

            observation = result.observation
            if observation is None:
                raise RuntimeError(
                    "successful tool batch result requires an observation"
                )
            self.traces.append(observation.trace)
            self._extend_unique_gaps(observation.gaps)
            if observation.evidence:
                self.successful_tools.add(call.name)
            for item in observation.evidence:
                if item.content_hash in self.evidence_hashes:
                    continue
                self.evidence_hashes.add(item.content_hash)
                self.evidence.append(item)
            public_observation = {
                "ok": True,
                "tool": observation.tool,
                "query": observation.query,
                "observation": observation.observation,
                "evidence": [
                    public_agent_evidence(item) for item in observation.evidence
                ],
                "evidence_hashes": list(observation.evidence_hashes),
                "gaps": list(observation.gaps),
            }
            self.ledger.add("tool_result", public_observation)
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": json.dumps(public_observation, ensure_ascii=False),
                }
            )
        return invalid_actions

    def _append_tool_error(self, call: ModelToolCall, error: str) -> None:
        payload = {
            "ok": False,
            "tool": call.name,
            "error": error,
            "detail": "",
        }
        self.ledger.add("tool_error", payload)
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": call.call_id,
                "content": json.dumps(payload, ensure_ascii=False),
            }
        )

    def _extend_unique_gaps(self, values: tuple[str, ...]) -> None:
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in self.gaps:
                self.gaps.append(cleaned)


class ContinuousAgentEpisode:
    """Run a task without rebuilding the model's observable message history."""

    def __init__(
        self,
        model: AgentModelClient,
        *,
        llm_timeout: float = DEFAULT_LLM_TIMEOUT,
        tool_executor: ToolBatchExecutor | None = None,
        finalizer: EpisodeFinalizer | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._model = model
        self._llm_timeout = max(0.1, float(llm_timeout))
        self._tool_executor = (
            tool_executor if tool_executor is not None else ToolBatchExecutor()
        )
        self._finalizer = (
            finalizer
            if finalizer is not None
            else EpisodeFinalizer(model, llm_timeout=self._llm_timeout)
        )
        self._is_cancelled = is_cancelled or (lambda: False)

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome:
        tool_session = self._tool_executor.new_session()
        if (
            context.contract.task_frame_hash
            and context.contract.task_frame_hash != task_frame.task_frame_hash
        ):
            raise ValueError("research contract task frame hash mismatch")

        ledger = _EpisodeLedger(task_frame)
        llm_calls = 0
        tool_calls = 0
        invalid_actions = 0
        finish_failures = 0
        messages: list[dict[str, object]] = [
            {
                "role": "system",
                "content": build_episode_instructions(
                    task_frame,
                    context,
                    registry,
                ),
            },
            {
                "role": "user",
                "content": build_episode_input(task_frame, context),
            },
        ]
        accumulator = _EpisodeToolAccumulator(messages=messages, ledger=ledger)
        finalization_started = False
        for _round in range(1, context.policy.max_steps + 2):
            if self._is_cancelled():
                return self._cancelled_outcome(
                    task_frame=task_frame,
                    ledger=ledger,
                    accumulator=accumulator,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )
            planning_timeout = context.deadline.stage_timeout(self._llm_timeout)
            should_finalize = (
                finalization_started
                or tool_calls >= context.policy.max_steps
                or planning_timeout < MIN_PLANNING_TURN_SECONDS
                or _round > context.policy.max_steps
            )
            if should_finalize and not finalization_started:
                finalization_started = True
                if tool_calls >= context.policy.max_steps:
                    finalization_reason = "tool_budget_exhausted"
                elif planning_timeout < MIN_PLANNING_TURN_SECONDS:
                    finalization_reason = "retrieval_deadline_closed"
                else:
                    finalization_reason = "model_round_budget_exhausted"
                self._begin_finalization(
                    messages=messages,
                    ledger=ledger,
                    reason=finalization_reason,
                )

            timeout = (
                context.deadline.synthesis_timeout(self._llm_timeout)
                if finalization_started
                else planning_timeout
            )
            if timeout <= 0.001:
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="deadline_exhausted",
                    gap="研究截止时间已到，仍有必需输出未覆盖",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            try:
                definitions = self._available_tool_definitions(
                    tool_session=tool_session,
                    registry=registry,
                    context=context,
                )
                turn = self._model.complete(
                    messages=list(messages),
                    tools=[] if finalization_started else definitions,
                    timeout=timeout,
                )
            except Exception as exc:
                llm_calls += 1
                reason = f"model_exception:{type(exc).__name__}"
                ledger.add("model_error", {"reason": reason})
                if (
                    not finalization_started
                    and self._can_recover_finalization(
                        context=context,
                        evidence=accumulator.evidence,
                    )
                ):
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason="planning_model_unavailable",
                    )
                    continue
                if self._can_recover_finalization(
                    context=context,
                    evidence=accumulator.evidence,
                ):
                    return self._recover_finalization(
                        task_frame=task_frame,
                        context=context,
                        ledger=ledger,
                        accumulator=accumulator,
                        registry=registry,
                        failure_reason=reason,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="model_unavailable",
                    gap=reason,
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            llm_calls += turn.provider_attempts
            ledger.add("model_turn", turn.to_dict())
            if self._is_cancelled():
                return self._cancelled_outcome(
                    task_frame=task_frame,
                    ledger=ledger,
                    accumulator=accumulator,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )
            if turn.error:
                ledger.add("model_error", {"reason": turn.error})
                if (
                    not finalization_started
                    and self._can_recover_finalization(
                        context=context,
                        evidence=accumulator.evidence,
                    )
                ):
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason="planning_model_unavailable",
                    )
                    continue
                if self._can_recover_finalization(
                    context=context,
                    evidence=accumulator.evidence,
                ):
                    return self._recover_finalization(
                        task_frame=task_frame,
                        context=context,
                        ledger=ledger,
                        accumulator=accumulator,
                        registry=registry,
                        failure_reason=turn.error,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="model_unavailable",
                    gap=turn.error,
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            messages.append(self._assistant_message(turn))
            if turn.tool_calls:
                if finalization_started:
                    invalid_actions += len(turn.tool_calls)
                    reason = "tool_call_during_finalization"
                    ledger.add(
                        "invalid_action",
                        {"reason": reason},
                    )
                    if self._can_recover_finalization(
                        context=context,
                        evidence=accumulator.evidence,
                    ):
                        return self._recover_finalization(
                            task_frame=task_frame,
                            context=context,
                            ledger=ledger,
                            accumulator=accumulator,
                            registry=registry,
                            failure_reason=reason,
                            llm_calls=llm_calls,
                            tool_calls=tool_calls,
                            invalid_actions=invalid_actions,
                        )
                    return self._stopped_outcome(
                        task_frame=task_frame,
                        status="partial",
                        stop_reason="invalid_model_finish",
                        gap="最终合成阶段仍尝试调用工具",
                        ledger=ledger,
                        evidence=accumulator.evidence,
                        traces=accumulator.traces,
                        gaps=accumulator.gaps,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                batch = tool_session.execute(
                    turn.tool_calls,
                    registry=registry,
                    context=context,
                    remaining_slots=context.policy.max_steps - tool_calls,
                    is_cancelled=self._is_cancelled,
                )
                tool_calls += batch.executed_count
                invalid_actions += accumulator.consume(batch, context)
                self._append_tool_budget_state(
                    messages=messages,
                    remaining_slots=max(
                        0,
                        context.policy.max_steps - tool_calls,
                    ),
                )
                if self._snapshot_surface_satisfied(
                    registry=registry,
                    context=context,
                    successful_tools=accumulator.successful_tools,
                ):
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason="snapshot_surface_satisfied",
                    )
                continue

            try:
                finish = validate_episode_finish(
                    turn.content,
                    context=context,
                    evidence=tuple(accumulator.evidence),
                )
                status, draft = finish.status, finish.draft
                final_gaps, bindings = finish.gaps, finish.bindings
            except ValueError as exc:
                finish_failures += 1
                invalid_actions += 1
                reason = str(exc)
                ledger.add("invalid_action", {"reason": reason})
                if finish_failures == 1 and not finalization_started:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "上一条终止输出无效。请保留当前任务和全部观察，"
                                "不要重启研究；修复后只输出 FINAL_JSON。"
                                f"错误：{reason}"
                            ),
                        }
                    )
                    continue
                if self._can_recover_finalization(
                    context=context,
                    evidence=accumulator.evidence,
                ):
                    return self._recover_finalization(
                        task_frame=task_frame,
                        context=context,
                        ledger=ledger,
                        accumulator=accumulator,
                        registry=registry,
                        failure_reason=reason,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial",
                    stop_reason="invalid_model_finish",
                    gap="模型未能返回可验证的结构化终止结果",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            bindings = expand_episode_snapshot_bindings(
                bindings=bindings,
                evidence=tuple(accumulator.evidence),
                registry=registry,
            )
            self._extend_unique(accumulator.gaps, final_gaps)
            self._extend_unique(
                accumulator.gaps,
                tuple(item.gap for item in bindings),
            )
            ledger.add(
                "finish",
                {
                    "status": status,
                    "stop_reason": "model_finish",
                    "bindings": [item.to_dict() for item in bindings],
                    "gaps": list(final_gaps),
                },
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status=status,
                draft=draft,
                evidence=tuple(accumulator.evidence),
                traces=tuple(accumulator.traces),
                gaps=tuple(accumulator.gaps),
                stop_reason="model_finish",
                events=tuple(ledger.events),
                bindings=bindings,
                usage=AgentUsage(llm_calls, tool_calls, invalid_actions),
            )

        return self._stopped_outcome(
            task_frame=task_frame,
            status="partial",
            stop_reason="step_exhausted",
            gap="研究预算已耗尽，仍有必需输出未覆盖",
            ledger=ledger,
            evidence=accumulator.evidence,
            traces=accumulator.traces,
            gaps=accumulator.gaps,
            llm_calls=llm_calls,
            tool_calls=tool_calls,
            invalid_actions=invalid_actions,
        )

    @staticmethod
    def _available_tool_definitions(
        *,
        tool_session: EpisodeToolBatchSession,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
    ) -> list[dict[str, object]]:
        available = set(
            tool_session.available_tool_names(
                registry=registry,
                context=context,
            )
        )
        return [
            definition
            for definition in registry.tool_definitions(
                context.contract.allowed_capabilities
            )
            if isinstance(function := definition.get("function"), dict)
            and function.get("name") in available
        ]

    @staticmethod
    def _append_tool_budget_state(
        *,
        messages: list[dict[str, object]],
        remaining_slots: int,
    ) -> None:
        if not messages or messages[-1].get("role") != "tool":
            return
        content = messages[-1].get("content")
        if not isinstance(content, str):
            return
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return
        payload["runtime_budget"] = {
            "remaining_tool_calls": remaining_slots,
            "instruction": (
                "下一轮工具调用总数不得超过 remaining_tool_calls；"
                "只能调用当前菜单中仍可见的工具；证据足够时直接输出 FINAL_JSON。"
            ),
        }
        messages[-1]["content"] = json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _begin_finalization(
        *,
        messages: list[dict[str, object]],
        ledger: _EpisodeLedger,
        reason: str,
    ) -> None:
        ledger.add("finalization", {"reason": reason})
        messages.append(
            {
                "role": "user",
                "content": (
                    "研究阶段已关闭，不得再调用工具。请保留最初任务和全部"
                    "原始观察，立即基于已有 evidence_hashes 输出 FINAL_JSON；"
                    "证据不足的 required output 必须标 partial 并写明 gap。"
                    "不要逐条复述全部观察，只保留最关键依据；条件写相对变化，"
                    "不得新增证据中没有的数值阈值。若用户要求预测，只保留一个"
                    "明确标注的主观基准区间及其不确定性。每个保留的精确数字"
                    "必须把直接证据哈希放入对应 output binding，否则删去数字。"
                    "每条被正文使用的观察事实也必须把其直接证据哈希加入对应 "
                    "output binding；不得用同一次工具返回的另一条证据代替。"
                    "原因归因若没有同一时间窗口的 news_search 证据，不得用普通 "
                    "web_search 摘要补成已核验因果，应保留盘面事实并把原因写 gap。"
                    "为保证 FINAL_JSON 完整，draft 控制在 1000 汉字以内；这是传输预算，"
                    "不要求固定标题、段数或措辞。"
                    f"关闭原因：{reason}"
                ),
            }
        )

    @staticmethod
    def _snapshot_surface_satisfied(
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        successful_tools: set[str],
    ) -> bool:
        specs = registry.authorized_specs(
            context.contract.allowed_capabilities,
        )
        return bool(specs) and all(
            spec.query_scope == "episode" and spec.name in successful_tools
            for spec in specs
        )

    def _can_recover_finalization(
        self,
        *,
        context: ResearchRunContext,
        evidence: list[AgentEvidence],
    ) -> bool:
        return bool(evidence) and (
            context.deadline.synthesis_timeout(self._llm_timeout)
            >= MIN_FINALIZATION_RECOVERY_SECONDS
        )

    @staticmethod
    def _provider_attempts_from_exception(exc: Exception) -> int:
        value = getattr(exc, "provider_attempts", 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return 0
        return value

    def _recover_finalization(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        ledger: _EpisodeLedger,
        accumulator: _EpisodeToolAccumulator,
        registry: ResearchToolRegistry,
        failure_reason: str,
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
    ) -> AgentOutcome:
        """Attempt exactly one compact recovery and always return a terminal outcome."""

        if self._is_cancelled():
            return self._cancelled_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )
        ledger.add(
            "finalization_recovery_started",
            {"failure_reason": failure_reason},
        )
        try:
            turn = self._finalizer.recover(
                task_frame=task_frame,
                context=context,
                evidence=tuple(accumulator.evidence),
                gaps=tuple(accumulator.gaps),
                failure_reason=failure_reason,
            )
        except Exception as exc:
            llm_calls += self._provider_attempts_from_exception(exc)
            reason = f"finalization_recovery_exception:{type(exc).__name__}"
            ledger.add("model_error", {"reason": reason})
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复失败，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )

        llm_calls += turn.provider_attempts
        ledger.add(
            "model_turn",
            {"phase": "finalization_recovery", **turn.to_dict()},
        )
        if (
            context.deadline.synthesis_timeout(self._llm_timeout)
            < MIN_FINALIZATION_RECOVERY_SECONDS
        ):
            reason = "finalization_recovery_deadline_exhausted"
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复超出截止时间，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )
        if turn.error:
            ledger.add("model_error", {"reason": turn.error})
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=turn.error,
                public_gap="终局恢复失败，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )

        if turn.tool_calls:
            invalid_actions += len(turn.tool_calls)
            reason = "tool_call_during_finalization_recovery"
            ledger.add("invalid_action", {"reason": reason})
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复仍尝试调用工具，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )

        try:
            finish = validate_episode_finish(
                turn.content,
                context=context,
                evidence=tuple(accumulator.evidence),
            )
            status, draft = finish.status, finish.draft
            final_gaps, bindings = finish.gaps, finish.bindings
        except ValueError as exc:
            invalid_actions += 1
            reason = str(exc)
            ledger.add("invalid_action", {"reason": reason})
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复未能返回可验证的结构化结果",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )

        bindings = expand_episode_snapshot_bindings(
            bindings=bindings,
            evidence=tuple(accumulator.evidence),
            registry=registry,
        )
        self._extend_unique(accumulator.gaps, final_gaps)
        self._extend_unique(
            accumulator.gaps,
            tuple(item.gap for item in bindings),
        )
        ledger.add(
            "finalization_recovery_outcome",
            {"status": "recovered", "answer_status": status},
        )
        ledger.add(
            "finish",
            {
                "status": status,
                "stop_reason": "finalization_recovered",
                "bindings": [item.to_dict() for item in bindings],
                "gaps": list(final_gaps),
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft=draft,
            evidence=tuple(accumulator.evidence),
            traces=tuple(accumulator.traces),
            gaps=tuple(accumulator.gaps),
            stop_reason="finalization_recovered",
            events=tuple(ledger.events),
            bindings=bindings,
            usage=AgentUsage(llm_calls, tool_calls, invalid_actions),
        )

    def _cancelled_outcome(
        self,
        *,
        task_frame: TaskFrame,
        ledger: _EpisodeLedger,
        accumulator: _EpisodeToolAccumulator,
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
    ) -> AgentOutcome:
        return self._stopped_outcome(
            task_frame=task_frame,
            status="failed",
            stop_reason="cancelled",
            gap="本轮执行已取消",
            ledger=ledger,
            evidence=accumulator.evidence,
            traces=accumulator.traces,
            gaps=accumulator.gaps,
            llm_calls=llm_calls,
            tool_calls=tool_calls,
            invalid_actions=invalid_actions,
        )

    @staticmethod
    def _failed_recovery_outcome(
        *,
        task_frame: TaskFrame,
        ledger: _EpisodeLedger,
        accumulator: _EpisodeToolAccumulator,
        reason: str,
        public_gap: str,
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
    ) -> AgentOutcome:
        ledger.add(
            "finalization_recovery_outcome",
            {"status": "failed", "reason": reason},
        )
        return ContinuousAgentEpisode._stopped_outcome(
            task_frame=task_frame,
            status="partial",
            stop_reason="finalization_recovery_failed",
            gap=public_gap,
            ledger=ledger,
            evidence=accumulator.evidence,
            traces=accumulator.traces,
            gaps=accumulator.gaps,
            llm_calls=llm_calls,
            tool_calls=tool_calls,
            invalid_actions=invalid_actions,
        )

    @staticmethod
    def _assistant_message(turn: ModelTurn) -> dict[str, object]:
        message: dict[str, object] = {
            "role": "assistant",
            "content": turn.content,
        }
        if turn.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(
                            call.to_dict()["arguments"],
                            ensure_ascii=False,
                        ),
                    },
                }
                for call in turn.tool_calls
            ]
        return message

    @staticmethod
    def _extend_unique(target: list[str], values: tuple[str, ...]) -> None:
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in target:
                target.append(cleaned)

    @staticmethod
    def _stopped_outcome(
        *,
        task_frame: TaskFrame,
        status: EpisodeStatus,
        stop_reason: str,
        gap: str,
        ledger: _EpisodeLedger,
        evidence: list[AgentEvidence],
        traces: list[ProviderTrace],
        gaps: list[str],
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
    ) -> AgentOutcome:
        final_gaps = list(gaps)
        ContinuousAgentEpisode._extend_unique(final_gaps, (gap,))
        ledger.add(
            "finish",
            {
                "status": status,
                "stop_reason": stop_reason,
                "gaps": final_gaps,
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft="",
            evidence=tuple(evidence),
            traces=tuple(traces),
            gaps=tuple(final_gaps),
            stop_reason=stop_reason,
            events=tuple(ledger.events),
            bindings=(),
            usage=AgentUsage(llm_calls, tool_calls, invalid_actions),
        )

__all__ = [
    "ContinuousAgentEpisode",
    "DEFAULT_LLM_TIMEOUT",
    "MIN_PLANNING_TURN_SECONDS",
]
