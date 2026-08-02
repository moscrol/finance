"""Continuous model/tool adapter for one non-publishing sub-research goal."""

from __future__ import annotations

from dataclasses import replace

from intelligence.services.agent_episode import (
    DEFAULT_LLM_TIMEOUT,
    ContinuousAgentEpisode,
)
from intelligence.services.agent_runtime import AgentModelClient
from intelligence.services.mode_governor import ModeSignals
from intelligence.services.sub_research import (
    BranchRequest,
    BranchResult,
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
            mode_signals=lambda _frame, _plan: ModeSignals(user_mode="quick"),
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
