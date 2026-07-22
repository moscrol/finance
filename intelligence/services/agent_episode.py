"""Continuous model/tool loop for one bounded financial research turn."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import cast

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    EpisodeStatus,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
    public_agent_evidence,
)
from intelligence.services.episode_finalizer import (
    MIN_FINALIZATION_RECOVERY_SECONDS,
    EpisodeFinalizer,
)
from intelligence.services.episode_tool_batch import ToolBatchExecutor, ToolBatchResult
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
)
from intelligence.services.task_frame import TaskFrame


DEFAULT_LLM_TIMEOUT = 20.0
MIN_PLANNING_TURN_SECONDS = 8.0
_FINISH_STATUSES = frozenset({"completed", "partial"})
_FINAL_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S | re.I)


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
                "content": self._system_prompt(task_frame, context, registry),
            },
            {
                "role": "user",
                "content": self._task_prompt(task_frame, context),
            },
        ]
        accumulator = _EpisodeToolAccumulator(messages=messages, ledger=ledger)
        definitions = registry.tool_definitions(context.contract.allowed_capabilities)
        finalization_started = False
        for _round in range(1, context.policy.max_steps + 2):
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
                ledger.add(
                    "finalization",
                    {"reason": finalization_reason},
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "研究阶段已关闭，不得再调用工具。请保留最初任务和全部"
                            "原始观察，立即基于已有 evidence_hashes 输出 FINAL_JSON；"
                            "证据不足的 required output 必须标 partial 并写明 gap。"
                            f"关闭原因：{finalization_reason}"
                        ),
                    }
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
                turn = self._model.complete(
                    messages=list(messages),
                    tools=[] if finalization_started else definitions,
                    timeout=timeout,
                )
            except Exception as exc:
                llm_calls += 1
                reason = f"model_exception:{type(exc).__name__}"
                ledger.add("model_error", {"reason": reason})
                if self._can_recover_finalization(
                    context=context,
                    evidence=accumulator.evidence,
                ):
                    return self._recover_finalization(
                        task_frame=task_frame,
                        context=context,
                        ledger=ledger,
                        accumulator=accumulator,
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
            if turn.error:
                ledger.add("model_error", {"reason": turn.error})
                if self._can_recover_finalization(
                    context=context,
                    evidence=accumulator.evidence,
                ):
                    return self._recover_finalization(
                        task_frame=task_frame,
                        context=context,
                        ledger=ledger,
                        accumulator=accumulator,
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
                )
                tool_calls += batch.executed_count
                invalid_actions += accumulator.consume(batch, context)
                continue

            try:
                status, draft, final_gaps, bindings = self._parse_finish(
                    turn.content,
                    context=context,
                    evidence_hashes=accumulator.evidence_hashes,
                )
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

    def _recover_finalization(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        ledger: _EpisodeLedger,
        accumulator: _EpisodeToolAccumulator,
        failure_reason: str,
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
    ) -> AgentOutcome:
        """Attempt exactly one compact recovery and always return a terminal outcome."""

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
            llm_calls += 1
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
            status, draft, final_gaps, bindings = self._parse_finish(
                turn.content,
                context=context,
                evidence_hashes=accumulator.evidence_hashes,
            )
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
    def _system_prompt(
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> str:
        return (
            "你是连续运行的金融研究 Agent。始终回答最初的不可变任务；每次看到"
            "工具原始观察后，自主决定继续查、改写查询或停止。只能调用本轮提供的"
            "只读工具，不能臆造工具结果。事实判断必须绑定工具返回的 evidence_hashes；"
            "缺数据要写 gap。不要套固定标题、行数或段落模板。终止时不要调用工具，"
            "只输出一个 JSON 对象："
            '{"status":"completed|partial","draft":"自然语言回答",'
            '"gaps":["..."],"bindings":[{"output_id":"...",'
            '"evidence_hashes":["..."],"gap":""}]}。'
            "binding.gap 只在该 required output 无法回答时填写；"
            "若 output 已由 evidence_hashes 支持并完成，binding.gap 必须为空，"
            "限制条件写入顶层 gaps 或 draft。"
            "completed 必须覆盖所有 required outputs；partial 必须明确缺口。\n"
            f"任务哈希：{task_frame.task_frame_hash}\n"
            f"可用工具：\n{registry.prompt_block(context.contract.allowed_capabilities)}"
        )

    @staticmethod
    def _task_prompt(
        task_frame: TaskFrame,
        context: ResearchRunContext,
    ) -> str:
        return json.dumps(
            {
                "task_frame": task_frame.to_dict(),
                "research_contract": context.contract.to_dict(),
                "today": context.today,
                "latest_data_date": context.latest_data_date,
                "date_rule": (
                    "today 不是行情日期；市场事实服从 latest_data_date 和证据日期"
                ),
            },
            ensure_ascii=False,
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
    def _parse_finish(
        content: str,
        *,
        context: ResearchRunContext,
        evidence_hashes: set[str],
    ) -> tuple[
        EpisodeStatus,
        str,
        tuple[str, ...],
        tuple[OutputEvidenceBinding, ...],
    ]:
        value = _parse_json_object(content)
        if value is None:
            raise ValueError("finish must be one JSON object")
        status = value.get("status")
        if status not in _FINISH_STATUSES:
            raise ValueError("finish status must be completed or partial")
        draft = value.get("draft")
        if not isinstance(draft, str):
            raise ValueError("finish draft must be a string")
        if status == "completed" and not draft.strip():
            raise ValueError("completed finish draft must be non-empty")
        raw_gaps = value.get("gaps", [])
        if not isinstance(raw_gaps, list) or any(
            not isinstance(item, str) for item in raw_gaps
        ):
            raise ValueError("finish gaps must be a string list")
        gaps = tuple(dict.fromkeys(item.strip() for item in raw_gaps if item.strip()))
        raw_bindings = value.get("bindings")
        if not isinstance(raw_bindings, list):
            raise ValueError("finish bindings must be a list")
        bindings: list[OutputEvidenceBinding] = []
        allowed_outputs = {item.output_id for item in context.contract.required_outputs}
        for raw in raw_bindings:
            if not isinstance(raw, dict):
                raise ValueError("each finish binding must be an object")
            raw_hashes = raw.get("evidence_hashes", [])
            if not isinstance(raw_hashes, list):
                raise ValueError("binding evidence_hashes must be a list")
            binding = OutputEvidenceBinding(
                output_id=str(raw.get("output_id") or ""),
                evidence_hashes=tuple(raw_hashes),
                gap=str(raw.get("gap") or ""),
            )
            if binding.output_id not in allowed_outputs:
                raise ValueError(f"unknown required output: {binding.output_id}")
            unknown = set(binding.evidence_hashes) - evidence_hashes
            if unknown:
                raise ValueError(
                    "binding contains unknown evidence hash: "
                    + ",".join(sorted(unknown))
                )
            bindings.append(binding)

        if len({item.output_id for item in bindings}) != len(bindings):
            raise ValueError("duplicate output binding")
        if status == "completed":
            binding_map = {item.output_id: item for item in bindings}
            missing = [
                required.output_id
                for required in context.contract.required_outputs
                if required.required
                and (
                    required.output_id not in binding_map
                    or not binding_map[required.output_id].evidence_hashes
                )
            ]
            if missing:
                raise ValueError("required output lacks evidence: " + ",".join(missing))
        return cast(EpisodeStatus, status), draft, gaps, tuple(bindings)

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


def _parse_json_object(content: str) -> dict[str, object] | None:
    text = str(content or "").strip()
    fenced = _FINAL_JSON_RE.fullmatch(text)
    if fenced is not None:
        text = fenced.group(1)
    if not text.startswith("{") or not text.endswith("}"):
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = _recover_finish_with_raw_draft(text)
    return value if isinstance(value, dict) else None


def _recover_finish_with_raw_draft(text: str) -> dict[str, object] | None:
    """Recover only the fixed finish envelope when GLM leaves draft raw.

    The prose field may contain literal newlines or quotes.  The structural
    tail remains strict JSON and is still validated by ``_parse_finish``.
    """

    prefix = re.match(
        r'^\{\s*"status"\s*:\s*"(completed|partial)"\s*,\s*'
        r'"draft"\s*:\s*"',
        text,
    )
    if prefix is None:
        return None
    separators = list(re.finditer(r'"\s*,\s*(?="gaps"\s*:)', text))
    if not separators:
        return None
    separator = separators[-1]
    if separator.start() < prefix.end():
        return None
    try:
        tail = json.loads("{" + text[separator.end() :])
    except json.JSONDecodeError:
        return None
    if not isinstance(tail, dict) or set(tail) != {"gaps", "bindings"}:
        return None
    return {
        "status": prefix.group(1),
        "draft": text[prefix.end() : separator.start()],
        "gaps": tail["gaps"],
        "bindings": tail["bindings"],
    }


__all__ = [
    "ContinuousAgentEpisode",
    "DEFAULT_LLM_TIMEOUT",
    "MIN_PLANNING_TURN_SECONDS",
]
