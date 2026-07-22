"""Thin control seam for strangling the legacy turn orchestrator.

The core deliberately does not execute tools or answer questions.  It projects
one canonical :class:`TaskFrame` and a terminal/execution policy from the
existing turn decision.  The legacy decision function is injected so this
module can be introduced beside the old path without changing its public API.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import TYPE_CHECKING, Callable, Literal

from intelligence.services.evidence_capabilities import (
    runtime_capabilities_for_frame,
)
from intelligence.services.research_contract import TurnIntent
from intelligence.services.task_frame import (
    TaskFrame,
    build_task_frame,
    task_frame_requires_retrieval,
)

if TYPE_CHECKING:
    from intelligence.services.turn_controller import TurnDecision

TerminalKind = Literal["research", "non_research", "clarification"]
LegacyDecide = Callable[..., "TurnDecision"]


@dataclass(frozen=True)
class TurnControlResult:
    """The small, stable boundary consumed by a future AgentEpisode."""

    task_frame: TaskFrame
    execution_route: str
    terminal_kind: TerminalKind
    needs_retrieval: bool
    capabilities: tuple[str, ...]
    contract_required: bool
    turn_intent: TurnIntent | None = None
    clarification_questions: tuple[str, ...] = ()


class TurnControlCore:
    """Project legacy routing into one model-owned control boundary.

    This is intentionally an adapter, not a second router.  A later episode
    runner can replace ``legacy_decide`` while callers retain this contract.
    """

    def __init__(self, legacy_decide: LegacyDecide | None = None) -> None:
        if legacy_decide is None:
            from intelligence.services.turn_controller import decide_turn

            legacy_decide = decide_turn
        self._legacy_decide = legacy_decide

    def control(
        self,
        query: str,
        *,
        context: str = "",
        previous_frame: TaskFrame | None = None,
        previous_intent: TurnIntent | None = None,
        previous_turn_id: str | None = None,
        llm_complete=None,
    ) -> TurnControlResult:
        decision = self._call_legacy(
            query,
            context=context,
            previous_intent=previous_intent,
            previous_turn_id=previous_turn_id,
            llm_complete=llm_complete,
        )
        frame = self._frame_for(decision, query, previous_frame)
        clarification_questions = tuple(decision.clarification_questions)
        if not clarification_questions and frame.clarification_question:
            clarification_questions = (frame.clarification_question,)

        if decision.lane == "clarify" or clarification_questions:
            terminal_kind: TerminalKind = "clarification"
        elif not task_frame_requires_retrieval(frame):
            terminal_kind = "non_research"
        else:
            terminal_kind = "research"

        contract_required = terminal_kind == "research"
        if terminal_kind == "research":
            needs_retrieval = True
            capabilities = runtime_capabilities_for_frame(frame)
            execution_route = frame.question_type
        else:
            needs_retrieval = False
            capabilities = ()
            execution_route = (
                "clarify" if terminal_kind == "clarification" else decision.lane
            )
        return TurnControlResult(
            task_frame=frame,
            execution_route=execution_route,
            terminal_kind=terminal_kind,
            needs_retrieval=needs_retrieval,
            capabilities=capabilities,
            contract_required=contract_required,
            turn_intent=decision.turn_intent,
            clarification_questions=clarification_questions,
        )

    def _call_legacy(self, query: str, **kwargs: object) -> TurnDecision:
        """Call an adapter without hiding TypeError raised inside it.

        The old controller has a wide keyword surface while test doubles and
        future episode adapters may intentionally accept only a subset.  Use
        signature inspection to trim unsupported keywords; catching TypeError
        around the invocation would also swallow a real controller bug and
        silently replace it with a second, different call.
        """

        try:
            signature = inspect.signature(self._legacy_decide)
        except (TypeError, ValueError):
            return self._legacy_decide(query, **kwargs)
        parameters = signature.parameters
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if accepts_kwargs:
            accepted = kwargs
        else:
            accepted = {
                name: value for name, value in kwargs.items() if name in parameters
            }
        return self._legacy_decide(query, **accepted)

    @staticmethod
    def _frame_for(
        decision: TurnDecision,
        query: str,
        previous_frame: TaskFrame | None,
    ) -> TaskFrame:
        if decision.task_frame is not None:
            return decision.task_frame
        if decision.turn_intent is not None:
            pending = TaskFrame.from_dict(decision.turn_intent.pending_task_frame)
            if pending is not None:
                return pending
        if decision.question_type is not None:
            return TurnControlCore._frame_from_decision(decision, query)
        if previous_frame is not None:
            return previous_frame
        return TurnControlCore._frame_from_decision(decision, query)

    @staticmethod
    def _frame_from_decision(decision: TurnDecision, query: str) -> TaskFrame:
        """Project validated adapter metadata without interpreting the query twice."""

        from intelligence.services.query_understanding import QueryEnvelope

        question_type = decision.question_type or "general_finance_qa"
        if question_type in {
            "market_watch",
            "dated_market_review",
            "market_forecast",
            "market_cause",
            "market_technical",
        }:
            subject_kind = "market_pattern"
        elif question_type == "external_market":
            subject_kind = "external_market"
        elif question_type in {"theme_analysis", "theme_track"}:
            subject_kind = "theme"
        elif question_type in {
            "stock_deep_dive",
            "valuation_estimate",
            "financial_analysis",
            "trade_advice",
        }:
            subject_kind = "company"
        else:
            subject_kind = "unknown"
        envelope = QueryEnvelope(
            question_type=question_type,
            subject_kind=subject_kind,
            subject=decision.subject,
            decision_goal="形成与用户原问题一致的直接回答",
            timeframe=decision.timeframe,
            matched_by="explicit" if decision.subject is not None else "generic",
            confidence=decision.confidence,
        )
        return build_task_frame(query, envelope)
