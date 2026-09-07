"""Continuous model/tool adapter for one non-publishing sub-research goal."""

from __future__ import annotations

from dataclasses import replace

from intelligence.runtime.agent_episode import (
    DEFAULT_LLM_TIMEOUT,
    ContinuousAgentEpisode,
)
from intelligence.services.agent_runtime import AgentModelClient
from intelligence.services.mode_governor import ModeSignals
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.runtime.sub_research import (
    BranchRequest,
    BranchResult,
    branch_batches_from_events,
    branch_invalid_actions_from_events,
)
from intelligence.services.task_frame import TaskFrame


class ContinuousSubResearchWorker:
    """Reuse the continuous episode loop but discard all branch answer prose."""

    def __init__(
        self,
        model: AgentModelClient,
        *,
        llm_timeout: float = DEFAULT_LLM_TIMEOUT,
    ) -> None:
        self._model = model
        self._llm_timeout = max(0.1, float(llm_timeout))

    def run(self, request: BranchRequest) -> BranchResult:
        frame = self._branch_frame(request)
        root_budget = request.context.root_budget
        if root_budget is None:
            raise ValueError("branch worker requires a child budget view")
        contract = replace(
            request.context.contract,
            task_id=root_budget.episode_id,
            question=request.goal,
            question_type="general_finance_qa",
            required_outputs=(),
            research_tier="quick",
            presentation_profile="general",
            task_frame_hash=frame.task_frame_hash,
        )
        context = replace(request.context, contract=contract)
        outcome = ContinuousAgentEpisode(
            self._model,
            llm_timeout=self._llm_timeout,
            is_cancelled=request.is_cancelled,
            # 子研究一律按 quick 裁决：注入件进 harness，Episode 不再转交。
            harness=FinanceResearchHarness(
                mode_signals=lambda _frame, _plan: ModeSignals(user_mode="quick"),
            ),
            sub_research_coordinator=None,
        ).run(
            task_frame=frame,
            context=context,
            registry=request.registry,
        )
        status = (
            outcome.status
            if outcome.status in {"completed", "partial"}
            else "failed"
        )
        # 分支 Episode 没接 event_sink，它的 durable 事件只活在 outcome 里；此前
        # 到这里就被丢掉，父臂只剩 branch_completed 的合计数。逐批派发账在这里
        # 从事件重算后随 BranchResult 带出去——事件本体仍不进父账本（父臂的
        # tool_result 审计底稿装不下三支分支的整条事件流）。
        return BranchResult(
            branch_id=request.branch_id,
            goal=request.goal,
            status=status,
            evidence=outcome.evidence,
            traces=outcome.traces,
            gaps=outcome.gaps,
            llm_calls=outcome.usage.llm_calls,
            tool_calls=outcome.usage.tool_calls,
            input_tokens=outcome.usage.input_tokens,
            output_tokens=outcome.usage.output_tokens,
            error=outcome.stop_reason if status == "failed" else "",
            stop_reason=outcome.stop_reason,
            batches=branch_batches_from_events(outcome.events),
            invalid_actions=branch_invalid_actions_from_events(outcome.events),
        )

    @staticmethod
    def _branch_frame(request: BranchRequest) -> TaskFrame:
        parent = request.task_frame
        return TaskFrame(
            raw_question=request.goal,
            user_goal=request.goal,
            question_type="general_finance_qa",
            subject=parent.subject,
            subject_kind=parent.subject_kind,
            market_scope=parent.market_scope,
            timeframe=parent.timeframe,
            required_outputs=(),
            assumptions=tuple(
                dict.fromkeys(
                    (*parent.assumptions, "分支只负责取证，不负责最终结论")
                )
            ),
            ambiguities=(),
            clarification_question=None,
            evidence_policy="general_finance_evidence",
            confidence=parent.confidence,
        )


__all__ = ["ContinuousSubResearchWorker"]
