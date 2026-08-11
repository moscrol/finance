"""Continuous model/tool loop for one bounded financial research turn."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
import json
import os
from time import monotonic

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
from intelligence.runtime.episode_finalizer import (
    MIN_FINALIZATION_RECOVERY_SECONDS,
    EpisodeFinalizer,
)
from intelligence.services.evidence_ledger import EvidenceLedger, EvidenceLedgerSnapshot
from intelligence.services.episode_protocol import (
    build_episode_input,
    build_episode_instructions,
    expand_episode_snapshot_bindings,
    rejection_response,
    validate_episode_finish,
)
from intelligence.runtime.episode_tool_batch import (
    EpisodeToolBatchSession,
    ToolBatchExecutor,
    ToolBatchResult,
)
from intelligence.services.mode_governor import (
    ModeDecision,
    ModeGovernor,
    ModeSignals,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.repair_coordinator import RepairGoal
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchRunContext,
)
from intelligence.services.research_plan import (
    PlanParseResult,
    ResearchPlan,
    parse_plan_candidate,
    plan_to_public_dict,
    validate_plan_revision,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
)
from intelligence.runtime.sub_research import (
    SubResearchCoordinator,
    SubResearchResult,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.tool_result_budget import budget_tool_observation


DEFAULT_LLM_TIMEOUT = 20.0
MIN_PLANNING_TURN_SECONDS = 8.0
# 一次最终合成至少需要的秒数。首轮可以向 ``synthesis_reserve`` **借**超出这个
# 地板的部分（见 ``_opening_planning_timeout``）：reserve 的正当用途是保证
# "已查到的证据"还能被合成，但首轮一条证据都没有，保护对象不存在。地板取
# ``EpisodeFinalizer`` 的默认超时（20s），即"够跑一次合成"的口径——借走的只是
# reserve 里超出一次合成所需的余量，不是整段。
MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS = 20.0


def budget_status_enabled() -> bool:
    """Whether each planning turn is told how much budget is left.

    Default **off**.  This changes what the model sees on every turn, so it
    ships as an experiment arm the seam ladder can measure rather than as a
    silent behaviour change in production — and the receipt records which arm
    produced it, so nobody has to guess later.
    """

    return str(os.environ.get("ASK_EPISODE_BUDGET_STATUS") or "").strip().lower() == "on"
# Planning is model-owned state, but it must still have a finite allowance so
# a model cannot keep revising a plan forever without reaching research or
# finalization.  The allowance is separate from max_steps, which is the
# finance-tool budget.
MAX_PLAN_TURNS = 2
# The loop must be able to represent the largest governed mode without giving
# quick runs that budget. Actual execution remains bounded by the current root
# ledger and deadline.
MAX_EPISODE_TOOL_CALLS = 24


def _token_usage_from_events(
    events: list[EpisodeEvent] | tuple[EpisodeEvent, ...],
) -> tuple[int | None, int | None]:
    input_total = 0
    output_total = 0
    input_observed = False
    output_observed = False
    for event in events:
        if event.kind not in {"model_turn", "branch_completed"}:
            continue
        input_value = event.payload.get("input_tokens")
        output_value = event.payload.get("output_tokens")
        if isinstance(input_value, int) and not isinstance(input_value, bool):
            input_total += max(0, input_value)
            input_observed = True
        if isinstance(output_value, int) and not isinstance(output_value, bool):
            output_total += max(0, output_value)
            output_observed = True
    return (
        input_total if input_observed else None,
        output_total if output_observed else None,
    )


def _agent_usage(
    ledger: "_EpisodeLedger",
    *,
    llm_calls: int,
    tool_calls: int,
    invalid_actions: int,
) -> AgentUsage:
    input_tokens, output_tokens = _token_usage_from_events(ledger.events)
    return AgentUsage(
        llm_calls=llm_calls,
        tool_calls=tool_calls,
        invalid_actions=invalid_actions,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _default_mode_signals(
    task_frame: TaskFrame,
    plan: ResearchPlan,
) -> ModeSignals:
    user_task = task_frame.to_user_task()
    return ModeSignals(
        independent_entities=len(user_task.subjects),
        separable_branches=len(plan.branch_goals),
        evidence_domains=plan.evidence_needs,
        uncovered_answer_elements=len(plan.open_gaps),
    )


def _consume_root_seconds(context: ResearchRunContext, seconds: float) -> bool:
    ledger = context.root_budget
    if ledger is None:
        return True
    try:
        ledger.consume_seconds(seconds=max(0.0, float(seconds)))
    except ValueError:
        return False
    return True


class _EpisodeLedger:
    def __init__(
        self,
        task_frame: TaskFrame,
        *,
        event_sink: Callable[[EpisodeEvent], None] | None = None,
    ) -> None:
        self._task_frame_hash = task_frame.task_frame_hash
        self._event_sink = event_sink
        self.events: list[EpisodeEvent] = []
        self.plan: ResearchPlan | None = None
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
        # 事件发生的挂钟时刻。相邻两条事件的时间差就是上一步的耗时——所以不需要
        # 给每一步单独开 span，就能算出「哪一步吃掉了时钟」。
        #
        # 放进 payload 而不是给 EpisodeEvent 加字段：``task_frame_hash`` 已经是
        # 同样的做法，而 EpisodeEvent 是 services 层的冻结 dataclass，被所有
        # runtime 共用，加字段的爆炸半径大得多。
        event_payload["at"] = datetime.now().astimezone().isoformat(timespec="milliseconds")
        event = EpisodeEvent(len(self.events) + 1, kind, event_payload)
        self.events.append(event)
        if self._event_sink is not None:
            try:
                self._event_sink(event)
            except Exception:
                # Progress is observability, never an alternate execution
                # owner. A broken UI sink must not abort financial research.
                pass
        return event

    def record_plan(self, plan: ResearchPlan) -> EpisodeEvent:
        self.plan = plan
        return self.add("plan", plan_to_public_dict(plan))

    def record_runtime_result(self) -> None:
        input_tokens, output_tokens = _token_usage_from_events(self.events)
        if input_tokens is None and output_tokens is None:
            return
        self.add(
            "runtime_result",
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )


@dataclass
class _EpisodeToolAccumulator:
    messages: list[dict[str, object]]
    ledger: _EpisodeLedger
    evidence_ledger: EvidenceLedger
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
                self.evidence_ledger.append(item)
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
            # 审计留档拿全量，模型上下文拿预算后的副本。同一份 payload 分流到
            # 两个 sink，所以截断只发生在喂模型这一侧——ledger 仍是完整证据。
            self.ledger.add("tool_result", public_observation)
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": json.dumps(
                        budget_tool_observation(public_observation),
                        ensure_ascii=False,
                    ),
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

    def consume_sub_research(self, result: SubResearchResult) -> None:
        self.traces.extend(result.traces)
        for branch in result.branches:
            self._extend_unique_gaps(
                tuple(f"{branch.goal}: {gap}" for gap in branch.gaps)
            )
            for item in branch.evidence:
                if item.content_hash in self.evidence_hashes:
                    continue
                self.evidence_hashes.add(item.content_hash)
                self.evidence.append(item)


@dataclass
class _EpisodeContinuationState:
    task_frame: TaskFrame
    context: ResearchRunContext
    registry: ResearchToolRegistry
    tool_session: EpisodeToolBatchSession
    messages: list[dict[str, object]]
    ledger: _EpisodeLedger
    accumulator: _EpisodeToolAccumulator
    evidence_ledger: EvidenceLedger
    initial_evidence_snapshot: EvidenceLedgerSnapshot


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
        mode_governor: ModeGovernor | None = None,
        mode_signals: Callable[[TaskFrame, ResearchPlan], ModeSignals] | None = None,
        sub_research_coordinator: SubResearchCoordinator | None = None,
        event_sink: Callable[[EpisodeEvent], None] | None = None,
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
        self._mode_governor = mode_governor or ModeGovernor()
        self._mode_signals = mode_signals or _default_mode_signals
        self._sub_research_coordinator = sub_research_coordinator
        self._event_sink = event_sink

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        _continuation_sink: list[_EpisodeContinuationState] | None = None,
    ) -> AgentOutcome:
        tool_session = self._tool_executor.new_session()
        if (
            context.contract.task_frame_hash
            and context.contract.task_frame_hash != task_frame.task_frame_hash
        ):
            raise ValueError("research contract task frame hash mismatch")

        ledger = _EpisodeLedger(task_frame, event_sink=self._event_sink)
        llm_calls = 0
        tool_calls = 0
        invalid_actions = 0
        finish_failures = 0
        plan_failures = 0
        plan_turns = 0
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
        evidence_ledger = EvidenceLedger(
            information_cutoff=context.information_cutoff.as_of_date,
        )
        for required in context.contract.required_outputs:
            if required.required and required.grounding_mode == "evidence":
                evidence_ledger.open_gap(required.output_id)
        initial_evidence_snapshot = evidence_ledger.snapshot()
        accumulator = _EpisodeToolAccumulator(
            messages=messages,
            ledger=ledger,
            evidence_ledger=evidence_ledger,
        )
        continuation_state: _EpisodeContinuationState | None = None
        if _continuation_sink is not None:
            continuation_state = _EpisodeContinuationState(
                task_frame=task_frame,
                context=context,
                registry=registry,
                tool_session=tool_session,
                messages=messages,
                ledger=ledger,
                accumulator=accumulator,
                evidence_ledger=evidence_ledger,
                initial_evidence_snapshot=initial_evidence_snapshot,
            )
            _continuation_sink.append(continuation_state)
        finalization_started = False
        mode_decided = False
        # max_steps counts finance-tool calls. Valid PLAN-only turns are
        # added on top of that bounded research budget.
        for _round in range(
            1,
            MAX_EPISODE_TOOL_CALLS + MAX_PLAN_TURNS + 2,
        ):
            if self._is_cancelled():
                return self._cancelled_outcome(
                    task_frame=task_frame,
                    ledger=ledger,
                    accumulator=accumulator,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )
            # 首轮向 reserve 借超出「一次合成」的余量：那时一条证据都没有，
            # reserve 保护的对象还不存在，而预扣会让唯一能启动检索的调用饿死。
            is_opening_call = llm_calls == 0 and not accumulator.evidence
            planning_timeout = (
                self._opening_planning_timeout(context)
                if is_opening_call
                else context.deadline.stage_timeout(self._llm_timeout)
            )
            remaining_tool_slots = self._remaining_tool_slots(
                context=context,
                tool_calls=tool_calls,
            )
            should_finalize = (
                finalization_started
                or remaining_tool_slots <= 0
                or planning_timeout < MIN_PLANNING_TURN_SECONDS
                or (_round - plan_turns) > self._model_round_budget(context)
            )
            if should_finalize and not finalization_started:
                finalization_started = True
                if remaining_tool_slots <= 0:
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

            model_started = monotonic()
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
                budget_remaining = _consume_root_seconds(
                    context,
                    max(0.0, monotonic() - model_started),
                )
                llm_calls += 1
                if not budget_remaining:
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

            model_elapsed = max(0.0, monotonic() - model_started)
            llm_calls += turn.provider_attempts
            ledger.add("model_turn", turn.to_dict())
            if not _consume_root_seconds(context, model_elapsed):
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
            # Once finalization starts, PLAN is no longer a valid model
            # response.  Let the existing terminal validator/recovery path
            # handle it as an invalid finish instead of accepting it and
            # silently skipping the recovery state machine.
            plan_result = (
                parse_plan_candidate(turn.content)
                if not finalization_started
                else PlanParseResult(None, "")
            )
            pending_mode_message: ModeDecision | None = None
            pending_branch_result: SubResearchResult | None = None
            if plan_result.plan is not None:
                try:
                    if ledger.plan is not None:
                        validate_plan_revision(
                            ledger.plan,
                            plan_result.plan,
                            original_task_id=context.contract.task_id,
                            current_task_id=context.contract.task_id,
                        )
                except ValueError as exc:
                    plan_result = PlanParseResult(None, str(exc))
                else:
                    if not turn.tool_calls:
                        if plan_turns >= MAX_PLAN_TURNS:
                            plan_result = PlanParseResult(
                                None,
                                "PLAN revision allowance exhausted",
                            )
                        else:
                            plan_turns += 1
                            ledger.record_plan(plan_result.plan)
                            if not mode_decided:
                                context, pending_mode_message = self._decide_mode(
                                    task_frame=task_frame,
                                    plan=plan_result.plan,
                                    context=context,
                                    ledger=ledger,
                                    continuation_state=continuation_state,
                                )
                                mode_decided = True
                            pending_branch_result = self._run_sub_research(
                                task_frame=task_frame,
                                plan=plan_result.plan,
                                decision=pending_mode_message,
                                context=context,
                                registry=registry,
                                ledger=ledger,
                                evidence_ledger=evidence_ledger,
                            )
                            if pending_branch_result is not None:
                                accumulator.consume_sub_research(
                                    pending_branch_result
                                )
                                llm_calls += pending_branch_result.llm_calls
                                tool_calls += pending_branch_result.tool_calls
                            if pending_mode_message is not None:
                                self._append_mode_decision_message(
                                    messages=messages,
                                    decision=pending_mode_message,
                                )
                            if pending_branch_result is not None:
                                self._append_sub_research_message(
                                    messages=messages,
                                    result=pending_branch_result,
                                )
                            continue
                    else:
                        ledger.record_plan(plan_result.plan)
                        if not mode_decided:
                            context, pending_mode_message = self._decide_mode(
                                task_frame=task_frame,
                                plan=plan_result.plan,
                                context=context,
                                ledger=ledger,
                                continuation_state=continuation_state,
                            )
                            mode_decided = True
                        pending_branch_result = self._run_sub_research(
                            task_frame=task_frame,
                            plan=plan_result.plan,
                            decision=pending_mode_message,
                            context=context,
                            registry=registry,
                            ledger=ledger,
                            evidence_ledger=evidence_ledger,
                        )
                        if pending_branch_result is not None:
                            accumulator.consume_sub_research(pending_branch_result)
                            llm_calls += pending_branch_result.llm_calls
                            tool_calls += pending_branch_result.tool_calls
            if plan_result.error:
                plan_failures += 1
                invalid_actions += 1
                ledger.add("invalid_action", {"reason": plan_result.error})
                if plan_failures == 1:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "上一条 PLAN 无效。请保留最初任务与当前 episode，"
                                "只修复为闭合的 PLAN JSON，或直接调用已授权工具；"
                                "PLAN 不能授权工具、预算、证据或完成状态。"
                                f"错误：{plan_result.error}"
                            ),
                        }
                    )
                    continue
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
                batch_started = monotonic()
                batch = tool_session.execute(
                    turn.tool_calls,
                    registry=registry,
                    context=context,
                    remaining_slots=self._remaining_tool_slots(
                        context=context,
                        tool_calls=tool_calls,
                    ),
                    is_cancelled=self._is_cancelled,
                )
                batch_elapsed = max(0.0, monotonic() - batch_started)
                tool_calls += batch.executed_count
                invalid_actions += accumulator.consume(batch, context)
                if context.root_budget is not None and batch.executed_count:
                    seconds_per_call = max(
                        batch_elapsed / batch.executed_count,
                        1e-6,
                    )
                    for _ in range(batch.executed_count):
                        context.root_budget.consume_call(seconds=seconds_per_call)
                self._append_tool_budget_state(
                    messages=messages,
                    remaining_seconds=(
                        context.deadline.remaining()
                        if budget_status_enabled()
                        else None
                    ),
                    total_seconds=(
                        float(context.policy.total_seconds)
                        if budget_status_enabled()
                        else None
                    ),
                    remaining_slots=max(
                        0,
                        self._remaining_tool_slots(
                            context=context,
                            tool_calls=tool_calls,
                        ),
                    ),
                )
                if pending_mode_message is not None:
                    self._append_mode_decision_message(
                        messages=messages,
                        decision=pending_mode_message,
                    )
                if pending_branch_result is not None:
                    self._append_sub_research_message(
                        messages=messages,
                        result=pending_branch_result,
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
                response = rejection_response(exc)
                # 病因与类别进收据：此前只留一句自由文本 reason，事后无法按类
                # 归并，`synthesis_health` 那 59% 「口径未知」就是从这里开始的。
                ledger.add(
                    "invalid_action",
                    {
                        "reason": reason,
                        "code": getattr(exc, "code", "unclassified"),
                        "kind": getattr(
                            getattr(exc, "kind", None), "value", "unclassified"
                        ),
                        "disposition": response.stop_reason,
                    },
                )
                if (
                    response.reinject
                    and finish_failures == 1
                    and not finalization_started
                ):
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
                if response.allow_recovery and self._can_recover_finalization(
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
            current_gaps = self._finish_gaps(final_gaps, bindings)
            ledger.record_runtime_result()
            ledger.add(
                "finish",
                {
                    "status": status,
                    "stop_reason": "model_finish",
                    "bindings": [item.to_dict() for item in bindings],
                    "gaps": list(current_gaps),
                },
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status=status,
                draft=draft,
                evidence=tuple(accumulator.evidence),
                traces=tuple(accumulator.traces),
                gaps=current_gaps,
                stop_reason="model_finish",
                events=tuple(ledger.events),
                bindings=bindings,
                usage=_agent_usage(
                    ledger,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                ),
                plan=ledger.plan,
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

    def resume(
        self,
        state: _EpisodeContinuationState,
        previous: AgentOutcome,
        goal: RepairGoal,
    ) -> AgentOutcome:
        """Continue one captured provider history for a verifier repair goal."""

        context = state.context
        ledger = state.ledger
        accumulator = state.accumulator
        messages = state.messages
        tool_session = state.tool_session
        registry = state.registry
        task_frame = state.task_frame
        repair_seconds = max(0.0, float(goal.remaining_seconds))
        if context.root_budget is not None:
            repair_seconds = min(
                repair_seconds,
                max(0.0, float(context.root_budget.remaining_seconds)),
            )
        repair_deadline = ResearchDeadline.from_timeout(repair_seconds)
        repair_context = replace(context, deadline=repair_deadline)
        repair_tool_deadline = context.deadline.bounded_stage(repair_seconds)
        repair_tool_context = replace(context, deadline=repair_tool_deadline)
        research_tools_open = not repair_tool_deadline.expired
        ledger.add("repair_goal", goal.to_dict())
        # 修复轮的时钟账，记在动手之前。
        #
        # 这三个数是 judge 那次诊断里 ``timeout_asked`` 的同位物：judge 看着像元凶，
        # 实际 asked 已经塌到 6.67/3.33/2.07 秒——是被前面耗光的，不是配置给小了。
        # 修复轮同样是 ``min(configured, remaining)``，而 ``repair_deadline`` 的
        # ``synthesis_reserve`` 是 0，拿到的就是纯残余时钟。没有这三个数，收据里只剩
        # 一个 TimeoutError，分不清「时钟被前面吃光」还是「provider 这次真慢」。
        repair_timeout_asked = repair_deadline.stage_timeout(self._llm_timeout)
        ledger.add(
            "repair_reentry",
            {
                "episode_id": goal.episode_id,
                "repair_goal_id": goal.repair_goal_id,
                "cycle": goal.cycle,
                "granted_seconds": repair_seconds,
                "timeout_asked": repair_timeout_asked,
                "timeout_configured": float(self._llm_timeout),
                "research_tools_open": research_tools_open,
                # 这一轮拿什么去冒险：失败时它会被原样结转，不再归零。
                "previous_draft_chars": len(previous.draft),
            },
        )
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "kind": "REPAIR_GOAL",
                        **goal.to_dict(),
                        "instruction": (
                            "保留最初任务、全部原始观察和当前工具账本。"
                            + (
                                "自主选择一个新的、未重复的动作补齐缺口；"
                                if research_tools_open
                                else "研究工具已关闭，只能基于已有观察修复措辞或证据绑定；"
                            )
                            + "不得重启研究或改写用户问题。"
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        )
        llm_calls = previous.usage.llm_calls
        tool_calls = previous.usage.tool_calls
        invalid_actions = previous.usage.invalid_actions
        timeout = repair_timeout_asked
        if timeout <= 0.001:
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="repair_deadline_exhausted",
                gap="修复阶段截止时间已到",
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
            )
        definitions = (
            self._available_tool_definitions(
                tool_session=tool_session,
                registry=registry,
                context=repair_tool_context,
            )
            if research_tools_open
            else []
        )
        model_started = monotonic()
        turn = self._model.complete(
            messages=list(messages),
            tools=definitions,
            timeout=timeout,
        )
        model_elapsed = max(0.0, monotonic() - model_started)
        llm_calls += turn.provider_attempts
        ledger.add("model_turn", {"phase": "repair", **turn.to_dict()})
        messages.append(self._assistant_message(turn))
        performed_tool_action = False
        if not _consume_root_seconds(repair_context, model_elapsed):
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="repair_deadline_exhausted",
                gap="修复阶段截止时间已到",
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
            )
        if turn.error:
            ledger.add("model_error", {"reason": turn.error})
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="repair_model_unavailable",
                gap=turn.error,
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
            )
        if turn.tool_calls:
            batch_started = monotonic()
            batch = tool_session.execute(
                turn.tool_calls,
                registry=registry,
                # Tool calls remain bound to the original absolute research
                # deadline. The repair deadline only governs model wording
                # and binding work after retrieval closes.
                context=repair_tool_context,
                remaining_slots=min(
                    goal.remaining_calls,
                    (
                        int(context.root_budget.remaining_calls)
                        if context.root_budget is not None
                        else goal.remaining_calls
                    ),
                ),
                is_cancelled=self._is_cancelled,
            )
            batch_elapsed = max(0.0, monotonic() - batch_started)
            tool_calls += batch.executed_count
            performed_tool_action = batch.executed_count > 0
            invalid_actions += accumulator.consume(batch, repair_context)
            if repair_context.root_budget is not None and batch.executed_count:
                seconds_per_call = max(
                    batch_elapsed / batch.executed_count,
                    1e-6,
                )
                for _ in range(batch.executed_count):
                    repair_context.root_budget.consume_call(seconds=seconds_per_call)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "修复动作已执行。不得再调用工具；请基于同一 episode 的"
                        "全部观察输出 FINAL_JSON，未补齐项继续明确写 gap。"
                    ),
                }
            )
            final_timeout = repair_deadline.synthesis_timeout(self._llm_timeout)
            if final_timeout <= 0.001:
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="repair_deadline_exhausted",
                    gap="修复阶段截止时间已到",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                    carried_draft=previous.draft,
                    carried_bindings=previous.bindings,
                )
            final_started = monotonic()
            final_turn = self._model.complete(
                messages=list(messages),
                tools=[],
                timeout=final_timeout,
            )
            final_elapsed = max(0.0, monotonic() - final_started)
            llm_calls += final_turn.provider_attempts
            ledger.add("model_turn", {"phase": "repair_finalize", **final_turn.to_dict()})
            messages.append(self._assistant_message(final_turn))
            if not _consume_root_seconds(repair_context, final_elapsed):
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="repair_deadline_exhausted",
                    gap="修复阶段截止时间已到",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                    carried_draft=previous.draft,
                    carried_bindings=previous.bindings,
                )
            turn = final_turn
        if turn.error or turn.tool_calls:
            invalid_actions += len(turn.tool_calls)
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="invalid_repair_finish",
                gap=turn.error or "修复终止阶段仍尝试调用工具",
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
            )
        try:
            finish = validate_episode_finish(
                turn.content,
                context=context,
                evidence=tuple(accumulator.evidence),
            )
        except ValueError as exc:
            invalid_actions += 1
            ledger.add("invalid_action", {"reason": str(exc)})
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="invalid_repair_finish",
                gap="修复轮未返回可验证的 FINAL_JSON",
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
            )
        bindings = expand_episode_snapshot_bindings(
            bindings=finish.bindings,
            evidence=tuple(accumulator.evidence),
            registry=registry,
        )
        revised_without_tool = (
            finish.draft.strip() != previous.draft.strip()
            or bindings != previous.bindings
        )
        completed_without_tool = (
            not performed_tool_action
            and finish.status == "completed"
            and revised_without_tool
        )
        effective_status = (
            finish.status
            if performed_tool_action or completed_without_tool
            else "partial"
        )
        current_gaps = self._finish_gaps(finish.gaps, bindings)
        if not performed_tool_action and not completed_without_tool and not current_gaps:
            current_gaps = ("修复轮未执行新的取证动作，缺口仍未补齐",)
        repair_progressed = performed_tool_action or completed_without_tool
        ledger.record_runtime_result()
        ledger.add(
            "finish",
            {
                "status": effective_status,
                "stop_reason": (
                    "repair_model_finish"
                    if repair_progressed
                    else "repair_model_stop"
                ),
                "bindings": [item.to_dict() for item in bindings],
                "gaps": list(current_gaps),
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=effective_status,
            draft=finish.draft,
            evidence=tuple(accumulator.evidence),
            traces=tuple(accumulator.traces),
            gaps=current_gaps,
            stop_reason=(
                "repair_model_finish" if repair_progressed else "repair_model_stop"
            ),
            events=tuple(ledger.events),
            bindings=bindings,
            usage=_agent_usage(
                ledger,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            ),
            plan=ledger.plan,
        )

    @staticmethod
    def _remaining_tool_slots(
        *,
        context: ResearchRunContext,
        tool_calls: int,
    ) -> int:
        policy_remaining = max(0, context.policy.max_steps - tool_calls)
        root_budget = context.root_budget
        if root_budget is None:
            return policy_remaining
        return max(0, int(root_budget.remaining_calls))

    @staticmethod
    def _model_round_budget(context: ResearchRunContext) -> int:
        root_budget = context.root_budget
        if root_budget is None:
            return max(1, int(context.policy.max_steps))
        return max(1, min(MAX_EPISODE_TOOL_CALLS, root_budget.hard_calls_cap))

    def _opening_planning_timeout(self, context: ResearchRunContext) -> float:
        """首轮窗口 = 常规切法 + 向 ``synthesis_reserve`` 借来的**余量**。

        借的只是 reserve 里超出「跑一次合成」所需的部分
        （``MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS``），不是整段——所以
        「到点还能交出有依据的答案」这条不变量依然成立。

        为什么首轮该借：reserve 的正当用途是保护**已查到的证据**不被写到一半
        砍掉，但首次调用时一条证据都没有，保护对象还不存在。而首轮失败是全损的
        ——那些秒数照样花掉，省下的 reserve 一秒都没用上，最终只能吐模板。

        ［实测 2026-08-08 生产 8792］turn=120s / standard / theme_analysis：
            effective = min(90, 120 − 40)   = 80
            reserve   = min(60, 80 × 2/3)   = 53.33   (episode_factory:360)
            首轮      = min(75, 80 − 53.33) = 26.67s  ← 低于 provider P50 28s
        三个 run 均 ``TimeoutError`` → 零 binding → 235B 模板答案（sha256 相同）。
        借入后：26.67 + (53.33 − 20) = 60s ≥ P95 50s。

        注意档位表**不参与**这条路径：``effective = min(tier_total, 80)``，
        80 恒为较小者，所以把 standard 从 90 调到 300 首轮一秒不变（已用探针
        验证）。��也是为什么"重标定档位表"救不了首轮。

        上界仍是 ``self._llm_timeout``（生产 75s，由 provider 特性定），与
        ``expires_at``（总共能跑多久）解耦。

        ``synthesis_reserve`` 用 ``getattr`` 读：``context.deadline`` 是鸭子类型
        注入点，测试替身只实现所需子集。上一版把新方法加在 ``ResearchDeadline``
        上，替身立刻 ``AttributeError``——这里只用替身已有的接口。
        """

        baseline = context.deadline.stage_timeout(self._llm_timeout)
        reserve = float(getattr(context.deadline, "synthesis_reserve", 0.0) or 0.0)
        borrowable = max(0.0, reserve - MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS)
        if borrowable <= 0.0:
            return baseline
        return max(0.0, min(float(self._llm_timeout), baseline + borrowable))

    def _decide_mode(
        self,
        *,
        task_frame: TaskFrame,
        plan: ResearchPlan,
        context: ResearchRunContext,
        ledger: _EpisodeLedger,
        continuation_state: _EpisodeContinuationState | None,
    ) -> tuple[ResearchRunContext, ModeDecision]:
        signals = self._mode_signals(task_frame, plan)
        if not isinstance(signals, ModeSignals):
            raise TypeError("mode_signals must return ModeSignals")
        if context.root_budget is None and signals.dependencies_available:
            signals = replace(signals, dependencies_available=False)
        if (
            plan.branch_goals
            and self._sub_research_coordinator is None
            and signals.dependencies_available
        ):
            signals = replace(signals, dependencies_available=False)
        decision = self._mode_governor.decide(plan, signals)
        promoted = self._mode_governor.apply(context, decision)
        ledger.add("mode_decision", decision.to_dict())
        if continuation_state is not None:
            continuation_state.context = promoted
        return promoted, decision

    def _run_sub_research(
        self,
        *,
        task_frame: TaskFrame,
        plan: ResearchPlan,
        decision: ModeDecision | None,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        ledger: _EpisodeLedger,
        evidence_ledger: EvidenceLedger,
    ) -> SubResearchResult | None:
        coordinator = self._sub_research_coordinator
        if (
            coordinator is None
            or decision is None
            or decision.effective_mode != "deep"
            or not plan.branch_goals
        ):
            return None
        for index, goal in enumerate(plan.branch_goals, start=1):
            ledger.add(
                "branch_started",
                {"branch_id": f"branch-{index}", "goal": goal},
            )
        result = coordinator.run(
            goals=plan.branch_goals,
            task_frame=task_frame,
            context=context,
            registry=registry,
            evidence_sink_factory=evidence_ledger.branch_sink,
        )
        completed_ids: set[str] = set()
        for branch in result.branches:
            completed_ids.add(branch.branch_id)
            ledger.add(
                (
                    "branch_completed"
                    if branch.status in {"completed", "partial"}
                    else "branch_failed"
                ),
                {
                    "branch_id": branch.branch_id,
                    "goal": branch.goal,
                    "status": branch.status,
                    "evidence_count": len(branch.evidence),
                    "gap_count": len(branch.gaps),
                    "llm_calls": branch.llm_calls,
                    "tool_calls": branch.tool_calls,
                    "input_tokens": branch.input_tokens,
                    "output_tokens": branch.output_tokens,
                },
            )
        for index, goal in enumerate(plan.branch_goals, start=1):
            branch_id = f"branch-{index}"
            if branch_id not in completed_ids:
                ledger.add(
                    "branch_failed",
                    {
                        "branch_id": branch_id,
                        "goal": goal,
                        "status": "failed",
                        "reason": result.refused_reason or "branch_not_executed",
                    },
                )
        return result

    @staticmethod
    def _append_mode_decision_message(
        *,
        messages: list[dict[str, object]],
        decision: ModeDecision,
    ) -> None:
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "kind": "MODE_DECISION",
                        **decision.to_dict(),
                        "instruction": (
                            "研究深度与总预算已由运行时裁决。保留原计划，"
                            "继续自主选择查询、工具顺序和停止时点；"
                            "不得把预算或内部裁决文本写入最终答案。"
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        )

    @staticmethod
    def _append_sub_research_message(
        *,
        messages: list[dict[str, object]],
        result: SubResearchResult,
    ) -> None:
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "kind": "SUB_RESEARCH_RESULTS",
                        "branches": [
                            {
                                "branch_id": branch.branch_id,
                                "goal": branch.goal,
                                "status": branch.status,
                                "evidence": [
                                    public_agent_evidence(item)
                                    for item in branch.evidence
                                ],
                                "gaps": list(branch.gaps),
                            }
                            for branch in result.branches
                        ],
                        "refused_reason": result.refused_reason,
                        "instruction": (
                            "这些是只读分支返回的公开证据观察，不是最终答案。"
                            "主 episode 仍需自行比较证据、处理冲突并决定停止；"
                            "不得把分支状态或内部标识写入公开答案。"
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
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
        remaining_seconds: float | None = None,
        total_seconds: float | None = None,
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
        budget: dict[str, object] = {
            "remaining_tool_calls": remaining_slots,
            "instruction": (
                "下一轮工具调用总数不得超过 remaining_tool_calls；"
                "只能调用当前菜单中仍可见的工具；证据足够时直接输出 FINAL_JSON。"
            ),
        }
        # Steps were already exposed here; *time* was not.  Google's
        # "Budget-Aware Tool-Use Enables Effective Agent Scaling" (2025) found
        # that granting more budget does not improve results on its own — an
        # agent without a sense of its remaining fraction keeps exploring
        # shallowly and saturates early.  Observed here on 2026-08-09: once the
        # S3 question was corrected the model went from 3 tool calls to 6 and
        # then died on `repair_deadline_exhausted`, with no way to know it was
        # nearly out of time.
        #
        # Extending this payload rather than adding a second status message is
        # deliberate: two independently-computed budget channels is the
        # "预算单一权威" violation this repo has already been bitten by.  The
        # model reads one place for one answer.
        if remaining_seconds is not None and total_seconds and total_seconds > 0:
            fraction = max(0.0, min(1.0, remaining_seconds / total_seconds))
            budget["remaining_seconds"] = round(max(0.0, remaining_seconds), 1)
            budget["remaining_fraction"] = round(fraction, 2)
            budget["instruction"] = (
                str(budget["instruction"])
                + "剩余时间充裕时可广泛探索；remaining_fraction 低于 0.3 时"
                "收敛到最有把握的方向，宁可少查也要留出写结论的时间。"
            )
        payload["runtime_budget"] = budget
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
        recovery_started = monotonic()
        try:
            turn = self._finalizer.recover(
                task_frame=task_frame,
                context=context,
                evidence=tuple(accumulator.evidence),
                gaps=tuple(accumulator.gaps),
                failure_reason=failure_reason,
            )
        except Exception as exc:
            budget_remaining = _consume_root_seconds(
                context,
                max(0.0, monotonic() - recovery_started),
            )
            llm_calls += self._provider_attempts_from_exception(exc)
            if not budget_remaining:
                return self._failed_recovery_outcome(
                    task_frame=task_frame,
                    ledger=ledger,
                    accumulator=accumulator,
                    reason="finalization_recovery_deadline_exhausted",
                    public_gap="终局恢复超出截止时间，无法生成可验证回答",
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )
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

        recovery_elapsed = max(0.0, monotonic() - recovery_started)
        llm_calls += turn.provider_attempts
        ledger.add(
            "model_turn",
            {"phase": "finalization_recovery", **turn.to_dict()},
        )
        if not _consume_root_seconds(context, recovery_elapsed):
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
        current_gaps = self._finish_gaps(final_gaps, bindings)
        ledger.add(
            "finalization_recovery_outcome",
            {"status": "recovered", "answer_status": status},
        )
        ledger.record_runtime_result()
        ledger.add(
            "finish",
            {
                "status": status,
                "stop_reason": "finalization_recovered",
                "bindings": [item.to_dict() for item in bindings],
                "gaps": list(current_gaps),
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft=draft,
            evidence=tuple(accumulator.evidence),
            traces=tuple(accumulator.traces),
            gaps=current_gaps,
            stop_reason="finalization_recovered",
            events=tuple(ledger.events),
            bindings=bindings,
            usage=_agent_usage(
                ledger,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            ),
            plan=ledger.plan,
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
    def _finish_gaps(
        declared_gaps: tuple[str, ...],
        bindings: tuple[OutputEvidenceBinding, ...],
    ) -> tuple[str, ...]:
        """Project only currently unresolved gaps; history stays in events."""

        values = (*declared_gaps, *(item.gap for item in bindings))
        return tuple(
            dict.fromkeys(
                cleaned
                for value in values
                if (cleaned := str(value or "").strip())
            )
        )

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
        carried_draft: str = "",
        carried_bindings: tuple[OutputEvidenceBinding, ...] = (),
    ) -> AgentOutcome:
        """Stop this episode, optionally carrying an earlier answer forward.

        ``run()`` 停在这里时没有更早的答案可留，两个 carried 参数保持空——
        行为与本参数加入前逐字相同。

        ``resume()`` 不一样：修复轮进来时上一轮**已经**有草稿和绑定了。修复是
        fix-forward，不是重跑；provider 在修复轮超时并不能让上一轮的答案失效。
        默认空会把「partial 但有答案」降级成「什么都没有」，比不修更差——
        2026-08-10 生产线四个 case 的 ``draft_chars=0`` 就是这么来的
        （trajectory 里 ``finalization -> finish`` 明明走过）。
        """

        final_gaps = list(gaps)
        ContinuousAgentEpisode._extend_unique(final_gaps, (gap,))
        ledger.record_runtime_result()
        ledger.add(
            "finish",
            {
                "status": status,
                "stop_reason": stop_reason,
                "gaps": final_gaps,
                # 留档结转了多长的草稿：收据里的 draft_chars 取的是最终 outcome，
                # 没有这一行就分不清「从没生成过」和「生成了但修复轮丢了」。
                "carried_draft_chars": len(carried_draft),
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft=carried_draft,
            evidence=tuple(evidence),
            traces=tuple(traces),
            gaps=tuple(final_gaps),
            stop_reason=stop_reason,
            events=tuple(ledger.events),
            bindings=carried_bindings,
            usage=_agent_usage(
                ledger,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            ),
            plan=ledger.plan,
        )

__all__ = [
    "ContinuousAgentEpisode",
    "DEFAULT_LLM_TIMEOUT",
    "MIN_PLANNING_TURN_SECONDS",
]
