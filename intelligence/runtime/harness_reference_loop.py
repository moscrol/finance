"""HarnessReferenceLoop：只调 ``ResearchHarness`` 的最小研究 loop（含一轮修复）。

spec：``docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`` §9 P2'；
修复轮：``docs/superpowers/specs/2026-09-02-repair-policy-state-machine.md`` §5 第 5 条。

--------------------------------------------------------------------------
它回答什么
--------------------------------------------------------------------------

「run 层可替换」不能停在设计图上。本类是第二条 loop：**一行领域逻辑都不写**，
prompt / PLAN 识别 / 工具结果投影 / 停机判定 / 终局准入 / 对模型说的话 / 修复轮
的不可达裁决与「修完算不算数」，全部问 ``ResearchHarness``；自己只做底座的事——
调模型、经 ``ToolBatchExecutor`` 派工具、数槛、记事件。

它不是第三条生产 backend（不进 ``RUNTIME_BACKEND_NAMES``，与 ``dsh_stub_runtime``
同一条纪律）。它的价值是可判定：``test_harness_reference_loop.py`` 用同一个脚本化
模型、同一份注册表并跑本类与 ``ContinuousAgentEpisode``，断言首轮消息、工具定义、
工具消息（去掉底座预算注入那一个键）、终局 outcome 一致；修复轮同样并跑，断言模型
看到的 REPAIR_GOAL / 收口指令字节相同、修复 outcome 一致。一致 = 领域门确实在
harness 里；不一致 = 还有领域逻辑焊在 ``ContinuousAgentEpisode`` 里没抽出来。

--------------------------------------------------------------------------
与 ContinuousAgentEpisode 的差（全是底座策略，不是领域）
--------------------------------------------------------------------------

- 无预算状态注入（``runtime_budget``）、无首轮向 reserve 借窗、无 root ledger 结算、
  无 ``repair_reentry`` 时钟账；超时一律 ``llm_timeout``。
- 修复轮：跑一轮（开场 → 可选一批工具 → 收口 → 终局准入 → 裁决），无瞬态重试、
  无 ``_recover_finalization`` / ``EpisodeFinalizer``（那是第二台状态机）。工具开不开
  只看「底座批了重开 或 研究窗未关」（与 Episode 同口径），不做 bounded_stage 算术。
- 深度裁决经 ``harness.govern_mode``（与 Episode 同一份），但本 loop 没有子研究
  协调器（``can_branch=False``），所以无子研究分支；无 opening prefetch。空池回退经
  ``harness.fallback_after_empty_batch``（与 Episode 同一份、同一位置），本 loop 只派、只记。
- 事件是 durable 子集（task / plan / model_turn / tool_request / tool_result /
  tool_error / finalization / invalid_action / repair_goal / finish），不带派发计时。

这些差都在 spec §4 里标为「底座」或 P2；任何一条被证明其实是领域，就该搬进 harness。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
import json

from intelligence.runtime.episode_tool_batch import (
    EpisodeToolBatchSession,
    ToolBatchExecutor,
    ToolBatchResult,
    timeout_detail_for_model,
)
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    EpisodeStatus,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_harness import (
    FinanceResearchHarness,
    RepairGoal,
    ResearchHarness,
)
from intelligence.services.research_plan import (
    PlanParseResult,
    ResearchPlan,
    plan_to_public_dict,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame

DEFAULT_LLM_TIMEOUT = 20.0
# 与 agent_episode.MAX_PLAN_TURNS 同值。刻意不 import：本类的独立性就是它的全部价值，
# 两个常量若漂开，测试会先红。
MAX_PLAN_TURNS = 2

__all__ = ["HarnessReferenceLoop", "ReferenceLoopState"]


class _Ledger:
    def __init__(self) -> None:
        self.events: list[EpisodeEvent] = []

    def add(self, kind: str, payload: dict[str, object]) -> None:
        self.events.append(EpisodeEvent(len(self.events) + 1, kind, payload))


@dataclass
class ReferenceLoopState:
    """一集跑完后留给修复轮的东西：同一段模型历史、同一批证据、同一个工具会话。

    与 ``agent_episode._EpisodeContinuationState`` 同一角色。``run`` 通过
    ``_continuation_sink`` 交出来，``resume`` 接着用；容器就地增长，``context`` /
    ``plan`` / ``seen_prose`` 在变化时回写。
    """

    task_frame: TaskFrame
    context: ResearchRunContext
    registry: ResearchToolRegistry
    session: EpisodeToolBatchSession
    ledger: _Ledger
    messages: list[dict[str, object]]
    evidence: list[AgentEvidence]
    evidence_hashes: set[str]
    successful_tools: set[str]
    traces: list[ProviderTrace]
    gaps: list[str]
    seen_prose: set[str]
    plan: ResearchPlan | None = None


class HarnessReferenceLoop:
    """只调 harness + registry 的最小 loop：一集研究 + 一轮修复。"""

    def __init__(
        self,
        model: AgentModelClient,
        *,
        harness: ResearchHarness | None = None,
        llm_timeout: float = DEFAULT_LLM_TIMEOUT,
        tool_executor: ToolBatchExecutor | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._model = model
        self._harness: ResearchHarness = (
            harness if harness is not None else FinanceResearchHarness()
        )
        self._llm_timeout = max(0.1, float(llm_timeout))
        self._tool_executor = (
            tool_executor if tool_executor is not None else ToolBatchExecutor()
        )
        self._is_cancelled = is_cancelled or (lambda: False)

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        _continuation_sink: list[ReferenceLoopState] | None = None,
    ) -> AgentOutcome:
        harness = self._harness
        ledger = _Ledger()
        ledger.add(
            "task",
            {
                "question": task_frame.raw_question,
                "task_frame": task_frame.to_dict(),
                "task_frame_hash": task_frame.task_frame_hash,
            },
        )
        system, user = harness.assemble_prompt(task_frame, context, registry)
        state = ReferenceLoopState(
            task_frame=task_frame,
            context=context,
            registry=registry,
            session=self._tool_executor.new_session(),
            ledger=ledger,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            evidence=[],
            evidence_hashes=set(),
            successful_tools=set(),
            traces=[],
            gaps=[],
            seen_prose=set(),
        )
        if _continuation_sink is not None:
            _continuation_sink.append(state)
        messages = state.messages
        evidence = state.evidence
        gaps = state.gaps

        plan: ResearchPlan | None = None
        plan_turns = 0
        plan_failures = 0
        finish_failures = 0
        llm_calls = 0
        tool_calls = 0
        invalid_actions = 0
        finalization_started = False
        mode_decided = False
        max_slots = max(1, int(context.policy.max_steps))

        def stop(
            status: EpisodeStatus, stop_reason: str, gap: str
        ) -> AgentOutcome:
            final_gaps = list(gaps)
            if gap and gap not in final_gaps:
                final_gaps.append(gap)
            ledger.add(
                "finish",
                {"status": status, "stop_reason": stop_reason, "gaps": final_gaps},
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status=status,
                draft="",
                evidence=tuple(evidence),
                traces=tuple(state.traces),
                gaps=tuple(final_gaps),
                stop_reason=stop_reason,
                events=tuple(ledger.events),
                bindings=(),
                usage=AgentUsage(
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                ),
                plan=plan,
            )

        def begin_finalization(reason: str) -> None:
            nonlocal finalization_started
            finalization_started = True
            ledger.add("finalization", {"reason": reason})
            messages.append(
                {
                    "role": "user",
                    "content": harness.steering_message(
                        "begin_finalization", detail=reason
                    ),
                }
            )

        for _round in range(max_slots + MAX_PLAN_TURNS + 4):
            if self._is_cancelled():
                return stop("failed", "cancelled", "本轮执行已取消")
            remaining_slots = max_slots - tool_calls
            if not finalization_started and remaining_slots <= 0:
                begin_finalization("tool_budget_exhausted")

            definitions = (
                []
                if finalization_started
                else self._available_tool_definitions(
                    session=state.session, registry=registry, context=context
                )
            )
            try:
                turn = self._model.complete(
                    messages=list(messages),
                    tools=definitions,
                    timeout=self._llm_timeout,
                )
            except Exception as exc:
                llm_calls += 1
                reason = f"model_exception:{type(exc).__name__}"
                ledger.add("model_error", {"reason": reason})
                return stop(
                    "partial" if evidence else "failed", "model_unavailable", reason
                )
            llm_calls += turn.provider_attempts
            ledger.add("model_turn", turn.to_dict())
            if turn.error:
                ledger.add("model_error", {"reason": turn.error})
                return stop(
                    "partial" if evidence else "failed", "model_unavailable", turn.error
                )
            messages.append(_assistant_message(turn))

            pending_mode_message: str | None = None
            if not finalization_started:
                plan_result = harness.interpret_plan(
                    turn.content,
                    previous_plan=plan,
                    task_id=context.contract.task_id,
                )
                if plan_result.plan is not None:
                    if not turn.tool_calls and plan_turns >= MAX_PLAN_TURNS:
                        plan_result = PlanParseResult(
                            None, "PLAN revision allowance exhausted"
                        )
                    else:
                        plan = plan_result.plan
                        state.plan = plan
                        ledger.add(
                            "plan",
                            {
                                "plan": plan_to_public_dict(plan),
                                "task_frame_hash": task_frame.task_frame_hash,
                            },
                        )
                        if not mode_decided:
                            # 深度裁决归 harness；本 loop 没有子研究协调器，如实报 False。
                            governance = harness.govern_mode(
                                task_frame=task_frame,
                                plan=plan,
                                context=context,
                                can_branch=False,
                            )
                            context = governance.context
                            state.context = context
                            max_slots = max(1, int(context.policy.max_steps))
                            ledger.add("mode_decision", governance.decision.to_dict())
                            pending_mode_message = governance.message
                            mode_decided = True
                        if not turn.tool_calls:
                            plan_turns += 1
                            if pending_mode_message is not None:
                                messages.append(
                                    {"role": "user", "content": pending_mode_message}
                                )
                            continue
                if plan_result.error:
                    plan_failures += 1
                    invalid_actions += 1
                    ledger.add("invalid_action", {"reason": plan_result.error})
                    if plan_failures == 1:
                        messages.append(
                            {
                                "role": "user",
                                "content": harness.steering_message(
                                    "invalid_plan", detail=plan_result.error
                                ),
                            }
                        )
                        continue

            if turn.tool_calls:
                if finalization_started:
                    invalid_actions += len(turn.tool_calls)
                    ledger.add(
                        "invalid_action", {"reason": "tool_call_during_finalization"}
                    )
                    return stop(
                        "partial", "invalid_model_finish", "最终合成阶段仍尝试调用工具"
                    )
                batch = state.session.execute(
                    turn.tool_calls,
                    registry=registry,
                    context=context,
                    remaining_slots=remaining_slots,
                    is_cancelled=self._is_cancelled,
                )
                tool_calls += batch.executed_count
                invalid_actions += self._ingest_batch(state, batch)
                halt = harness.halt_after_tool_batch(
                    context=context,
                    batch_errors=tuple(item.error for item in batch.items),
                )
                if halt and not finalization_started:
                    begin_finalization(halt)
                # 空池回退：领域说要不要替模型补一枪，底座判付不付得起、派出去、记账。
                # 与 Episode 同位——停机判定之后、深度消息之前。
                fallback_slots = max_slots - tool_calls
                if fallback_slots > 0:
                    fallback = harness.fallback_after_empty_batch(
                        batch.items,
                        context=context,
                        registry=registry,
                        authorized_tools=self._authorized_tools(
                            session=state.session, registry=registry, context=context
                        ),
                        events=ledger.events,
                        in_repair=False,
                    )
                    if fallback is not None:
                        fallback_batch = state.session.execute(
                            (fallback.call,),
                            registry=registry,
                            context=context,
                            remaining_slots=fallback_slots,
                            is_cancelled=self._is_cancelled,
                        )
                        tool_calls += fallback_batch.executed_count
                        invalid_actions += self._ingest_batch(
                            state,
                            fallback_batch,
                            request_extras={
                                fallback.call.call_id: fallback.request_extras
                            },
                        )
                if pending_mode_message is not None:
                    messages.append({"role": "user", "content": pending_mode_message})
                if not finalization_started and harness.retrieval_complete(
                    context=context,
                    registry=registry,
                    successful_tools=state.successful_tools,
                ):
                    begin_finalization("snapshot_surface_satisfied")
                continue

            admission = harness.admit_finish(
                turn.content,
                context=context,
                evidence=tuple(evidence),
                registry=registry,
            )
            if not admission.accepted:
                finish_failures += 1
                invalid_actions += 1
                response = admission.response
                assert response is not None
                ledger.add(
                    "invalid_action",
                    {
                        "reason": admission.reason,
                        "code": admission.rejection["rejection_code"],
                        "kind": admission.kind,
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
                            "content": harness.steering_message(
                                "invalid_finish", detail=admission.reason
                            ),
                        }
                    )
                    continue
                return stop(
                    "partial", response.stop_reason, "模型未能返回可验证的结构化终止结果"
                )
            assert admission.status is not None
            ledger.add(
                "finish",
                {
                    "status": admission.status,
                    "stop_reason": "model_finish",
                    "bindings": [item.to_dict() for item in admission.bindings],
                    "gaps": list(admission.gaps),
                    "caveat_slips": admission.caveat_slips,
                    **admission.rejection,
                },
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status=admission.status,
                draft=admission.draft,
                evidence=tuple(evidence),
                traces=tuple(state.traces),
                gaps=admission.gaps,
                stop_reason="model_finish",
                events=tuple(ledger.events),
                bindings=admission.bindings,
                usage=AgentUsage(
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                ),
                plan=plan,
            )

        return stop("partial", "step_exhausted", "研究预算已耗尽，仍有必需输出未覆盖")

    def resume(
        self,
        state: ReferenceLoopState,
        previous: AgentOutcome,
        goal: RepairGoal,
    ) -> AgentOutcome:
        """在同一段模型历史上跑一轮修复：开场 → 可选一批工具 → 收口 → 准入 → 裁决。

        领域的五件事全问 harness：哪些格不可达（``downgrade_unreachable``）、开场怎么说
        （``repair_goal_message``）、工具跑完怎么收口（``steering_message("repair_finalize")``）、
        终局能不能发（``admit_finish``）、修完算不算数（``admit_repair_result``）。
        底座只管：工具开不开、派工具、记事件、失败时结转上一轮的稿。
        """

        harness = self._harness
        ledger = state.ledger
        messages = state.messages
        evidence = state.evidence
        context = state.context
        task_frame = state.task_frame
        registry = state.registry
        llm_calls = previous.usage.llm_calls
        tool_calls = previous.usage.tool_calls
        invalid_actions = previous.usage.invalid_actions

        goal_payload = goal.to_dict()
        downgrade = harness.downgrade_unreachable(goal, contract=context.contract)
        if downgrade.unreachable:
            goal_payload["unreachable_without_tools"] = list(downgrade.unreachable)
        ledger.add("repair_goal", goal_payload)
        if downgrade.contract is not context.contract:
            context = replace(context, contract=downgrade.contract)
            state.context = context
        # 底座策略（与 Episode 同）：工具开不开只看研究窗——底座批了重开、或窗还没关。
        # 额度为 0 时窗仍算开着，模型若真调工具，由批次执行器按 remaining_slots 拒掉。
        tools_open = goal.reopen_tools or not context.deadline.expired
        messages.append(
            {
                "role": "user",
                "content": harness.repair_goal_message(
                    downgrade.goal, tools_open=tools_open
                ),
            }
        )

        def stop(
            stop_reason: str,
            gap: str,
            *,
            draft: str = "",
            bindings: tuple[OutputEvidenceBinding, ...] = (),
            **extra: object,
        ) -> AgentOutcome:
            final_gaps = list(state.gaps)
            if gap and gap not in final_gaps:
                final_gaps.append(gap)
            status: EpisodeStatus = "partial" if evidence else "failed"
            ledger.add(
                "finish",
                {"status": status, "stop_reason": stop_reason, "gaps": final_gaps, **extra},
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status=status,
                # 修复不得倒退：这一轮死了，上一轮的答案并没有因此失效。
                draft=draft or previous.draft,
                evidence=tuple(evidence),
                traces=tuple(state.traces),
                gaps=tuple(final_gaps),
                stop_reason=stop_reason,
                events=tuple(ledger.events),
                bindings=bindings or previous.bindings,
                usage=AgentUsage(
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                ),
                plan=state.plan,
            )

        def complete(tools: list[dict[str, object]]) -> ModelTurn | AgentOutcome:
            nonlocal llm_calls
            try:
                turn = self._model.complete(
                    messages=list(messages), tools=tools, timeout=self._llm_timeout
                )
            except Exception as exc:
                llm_calls += 1
                reason = f"model_exception:{type(exc).__name__}"
                ledger.add("model_error", {"reason": reason})
                return stop("repair_model_unavailable", reason)
            llm_calls += turn.provider_attempts
            ledger.add("model_turn", turn.to_dict())
            messages.append(_assistant_message(turn))
            if turn.error:
                ledger.add("model_error", {"reason": turn.error})
                return stop("repair_model_unavailable", turn.error)
            return turn

        definitions = (
            self._available_tool_definitions(
                session=state.session, registry=registry, context=context
            )
            if tools_open
            else []
        )
        turn = complete(definitions)
        if isinstance(turn, AgentOutcome):
            return turn

        performed_tool_action = False
        if turn.tool_calls and tools_open:
            batch = state.session.execute(
                turn.tool_calls,
                registry=registry,
                context=context,
                remaining_slots=goal.remaining_calls,
                is_cancelled=self._is_cancelled,
            )
            tool_calls += batch.executed_count
            performed_tool_action = batch.executed_count > 0
            invalid_actions += self._ingest_batch(state, batch)
            messages.append(
                {
                    "role": "user",
                    "content": harness.steering_message("repair_finalize", detail=""),
                }
            )
            turn = complete([])
            if isinstance(turn, AgentOutcome):
                return turn
        if turn.tool_calls:
            invalid_actions += len(turn.tool_calls)
            ledger.add(
                "invalid_action",
                {
                    "reason": "修复终止阶段仍尝试调用工具",
                    "disposition": "invalid_repair_finish",
                },
            )
            return stop("invalid_repair_finish", "修复终止阶段仍尝试调用工具")

        admission = harness.admit_finish(
            turn.content, context=context, evidence=tuple(evidence), registry=registry
        )
        if not admission.accepted:
            invalid_actions += 1
            ledger.add(
                "invalid_action",
                {
                    "reason": admission.rejection["rejection_reason"],
                    "code": admission.rejection["rejection_code"],
                    "disposition": "invalid_repair_finish",
                },
            )
            return stop(
                "invalid_repair_finish",
                "修复轮未返回可验证的 FINAL_JSON",
                **admission.rejection,
            )
        verdict = harness.admit_repair_result(
            admission=admission,
            previous=previous,
            performed_tool_action=performed_tool_action,
        )
        stop_reason = "repair_model_finish" if verdict.progressed else "repair_model_stop"
        ledger.add(
            "finish",
            {
                "status": verdict.status,
                "stop_reason": stop_reason,
                "bindings": [item.to_dict() for item in admission.bindings],
                "gaps": list(verdict.gaps),
                "caveat_slips": admission.caveat_slips,
                **admission.rejection,
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=verdict.status,
            draft=admission.draft,
            evidence=tuple(evidence),
            traces=tuple(state.traces),
            gaps=verdict.gaps,
            stop_reason=stop_reason,
            events=tuple(ledger.events),
            bindings=admission.bindings,
            usage=AgentUsage(
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            ),
            plan=state.plan,
        )

    def _ingest_batch(
        self,
        state: ReferenceLoopState,
        batch: ToolBatchResult,
        *,
        request_extras: dict[str, dict[str, object]] | None = None,
    ) -> int:
        """一批工具结果进证据 / 事件 / 消息。返回本批的 invalid_actions 增量。

        成功的观察：证据去重合并 → 问 harness 审计留什么、模型看什么。失败的：问
        harness 模型看什么。两条都是 ``run`` 与 ``resume`` 共用的底座管线。
        ``request_extras`` 是领域要盖在某条 ``tool_request`` 上的标记（空池回退）。
        """

        harness = self._harness
        extras_by_id = request_extras or {}
        invalid_actions = 0
        for result in batch.items:
            call = result.call
            state.ledger.add(
                "tool_request",
                {**call.to_dict(), **(extras_by_id.get(call.call_id) or {})},
            )
            if result.status in {"rejected", "error", "timeout"}:
                if result.status == "rejected":
                    invalid_actions += 1
                    error, detail = result.error, result.detail
                elif result.status == "timeout":
                    error, detail = "tool_timeout", timeout_detail_for_model(result)
                else:
                    error, detail = "tool_exception", result.detail or result.error
                payload = harness.project_tool_error(
                    tool=call.name, error=error, detail=detail
                )
                state.ledger.add("tool_error", {**payload, "call_id": call.call_id})
                state.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.call_id,
                        "content": json.dumps(payload, ensure_ascii=False),
                    }
                )
                continue
            observation = result.observation
            if observation is None:
                raise RuntimeError(
                    "successful tool batch result requires an observation"
                )
            state.traces.append(observation.trace)
            for value in observation.gaps:
                cleaned = str(value or "").strip()
                if cleaned and cleaned not in state.gaps:
                    state.gaps.append(cleaned)
            if observation.evidence:
                state.successful_tools.add(call.name)
            for item in observation.evidence:
                if item.content_hash in state.evidence_hashes:
                    continue
                state.evidence_hashes.add(item.content_hash)
                state.evidence.append(item)
            projection = harness.project_tool_result(
                observation,
                evidence_so_far=tuple(state.evidence),
                seen_prose=state.seen_prose,
            )
            state.seen_prose = set(projection.seen_prose)
            state.ledger.add(
                "tool_result",
                {**projection.audit_payload, "call_id": call.call_id},
            )
            state.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": projection.model_content,
                }
            )
        return invalid_actions

    @staticmethod
    def _authorized_tools(
        *,
        session: EpisodeToolBatchSession,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
    ) -> frozenset[str]:
        """此刻真能派的工具集（会话可用 ∪ 契约授权），与 Episode 递给 harness 的同一口径。"""

        return frozenset(
            session.available_tool_names(registry=registry, context=context)
        ) | frozenset(context.contract.allowed_capabilities)

    @staticmethod
    def _available_tool_definitions(
        *,
        session: EpisodeToolBatchSession,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
    ) -> list[dict[str, object]]:
        available = set(session.available_tool_names(registry=registry, context=context))
        return [
            definition
            for definition in registry.tool_definitions(
                context.contract.allowed_capabilities
            )
            if isinstance(function := definition.get("function"), dict)
            and function.get("name") in available
        ]


def _assistant_message(turn: ModelTurn) -> dict[str, object]:
    message: dict[str, object] = {"role": "assistant", "content": turn.content}
    if turn.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(
                        call.to_dict()["arguments"], ensure_ascii=False
                    ),
                },
            }
            for call in turn.tool_calls
        ]
    return message
