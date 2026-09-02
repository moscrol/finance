"""HarnessReferenceLoop：只调 ``ResearchHarness`` 八方法的最小研究 loop。

spec：``docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`` §9 P2'。

--------------------------------------------------------------------------
它回答什么
--------------------------------------------------------------------------

「run 层可替换」不能停在设计图上。本类是第二条 loop：**一行领域逻辑都不写**，
prompt / PLAN 识别 / 工具结果投影 / 停机判定 / 终局准入 / 对模型说的话，全部问
``ResearchHarness``；自己只做底座的事——调模型、经 ``ToolBatchExecutor`` 派工具、
数槛、记事件。

它不是第三条生产 backend（不进 ``RUNTIME_BACKEND_NAMES``，与 ``dsh_stub_runtime``
同一条纪律）。它的价值是可判定：``test_harness_reference_loop.py`` 用同一个脚本化
模型、同一份注册表并跑本类与 ``ContinuousAgentEpisode``，断言首轮消息、工具定义、
工具消息（去掉底座预算注入那一个键）、终局 outcome 一致。一致 = 领域门确实在
harness 里；不一致 = 还有领域逻辑焊在 ``ContinuousAgentEpisode`` 里没抽出来。

--------------------------------------------------------------------------
与 ContinuousAgentEpisode 的差（全是底座策略，不是领域）
--------------------------------------------------------------------------

- 无预算状态注入（``runtime_budget``）、无首轮向 reserve 借窗、无 root ledger 结算；
  超时一律 ``llm_timeout``。
- 无修复协调（``RepairGoal`` / ``_recover_finalization`` / ``EpisodeFinalizer``）：
  终局被驳回只回灌一次，再不过就停。
- 深度裁决经 ``harness.govern_mode``（与 Episode 同一份），但本 loop 没有子研究
  协调器（``can_branch=False``），所以无子研究分支；无空池回退、无 opening prefetch。
- 事件是 durable 子集（task / plan / model_turn / tool_request / tool_result /
  tool_error / finalization / invalid_action / finish），不带派发计时。

这些差都在 spec §4 里标为「底座」或 P2；任何一条被证明其实是领域，就该搬进 harness。
"""

from __future__ import annotations

from collections.abc import Callable
import json

from intelligence.runtime.episode_tool_batch import (
    EpisodeToolBatchSession,
    ToolBatchExecutor,
)
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    EpisodeStatus,
    ModelTurn,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_harness import (
    FinanceResearchHarness,
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

__all__ = ["HarnessReferenceLoop"]


class _Ledger:
    def __init__(self) -> None:
        self.events: list[EpisodeEvent] = []

    def add(self, kind: str, payload: dict[str, object]) -> None:
        self.events.append(EpisodeEvent(len(self.events) + 1, kind, payload))


class HarnessReferenceLoop:
    """只调 harness 八方法 + registry 的最小 loop。"""

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
        messages: list[dict[str, object]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        session = self._tool_executor.new_session()

        evidence: list[AgentEvidence] = []
        evidence_hashes: set[str] = set()
        successful_tools: set[str] = set()
        traces: list[ProviderTrace] = []
        gaps: list[str] = []
        seen_prose: set[str] = set()
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
                traces=tuple(traces),
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
                    session=session, registry=registry, context=context
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
                batch = session.execute(
                    turn.tool_calls,
                    registry=registry,
                    context=context,
                    remaining_slots=remaining_slots,
                    is_cancelled=self._is_cancelled,
                )
                tool_calls += batch.executed_count
                for result in batch.items:
                    call = result.call
                    ledger.add("tool_request", call.to_dict())
                    if result.status in {"rejected", "error", "timeout"}:
                        if result.status == "rejected":
                            invalid_actions += 1
                            error, detail = result.error, result.detail
                        elif result.status == "timeout":
                            error, detail = "tool_timeout", ""
                        else:
                            error, detail = "tool_exception", result.detail or result.error
                        payload = harness.project_tool_error(
                            tool=call.name, error=error, detail=detail
                        )
                        ledger.add("tool_error", {**payload, "call_id": call.call_id})
                        messages.append(
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
                    traces.append(observation.trace)
                    for value in observation.gaps:
                        cleaned = str(value or "").strip()
                        if cleaned and cleaned not in gaps:
                            gaps.append(cleaned)
                    if observation.evidence:
                        successful_tools.add(call.name)
                    for item in observation.evidence:
                        if item.content_hash in evidence_hashes:
                            continue
                        evidence_hashes.add(item.content_hash)
                        evidence.append(item)
                    projection = harness.project_tool_result(
                        observation,
                        evidence_so_far=tuple(evidence),
                        seen_prose=seen_prose,
                    )
                    seen_prose = set(projection.seen_prose)
                    ledger.add(
                        "tool_result",
                        {**projection.audit_payload, "call_id": call.call_id},
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.call_id,
                            "content": projection.model_content,
                        }
                    )
                if pending_mode_message is not None:
                    messages.append({"role": "user", "content": pending_mode_message})
                halt = harness.halt_after_tool_batch(
                    context=context,
                    batch_errors=tuple(item.error for item in batch.items),
                )
                if halt and not finalization_started:
                    begin_finalization(halt)
                elif not finalization_started and harness.retrieval_complete(
                    context=context,
                    registry=registry,
                    successful_tools=successful_tools,
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
                traces=tuple(traces),
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
