"""Thin control seam for strangling the legacy turn orchestrator.

The core deliberately does not execute tools or answer questions.  It projects
one canonical :class:`TaskFrame` and a terminal/execution policy from the
existing turn decision.  The legacy decision function is injected so this
module can be introduced beside the old path without changing its public API.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import inspect
from typing import TYPE_CHECKING, Callable, Literal

from intelligence.services.evidence_capabilities import (
    runtime_capabilities_for_frame,
)
from intelligence.services.material_permissions import restrict_read_capabilities
from intelligence.services.research_contract import TurnIntent
from intelligence.services.task_frame import (
    TaskFrame,
    build_task_frame,
    rebase_task_frame,
    task_frame_requires_retrieval,
)

if TYPE_CHECKING:
    from intelligence.services.prior_evidence import PriorTurnEvidence
    from intelligence.services.turn_controller import TurnDecision

TerminalKind = Literal["research", "non_research", "clarification"]
LegacyDecide = Callable[..., "TurnDecision"]

_LEGACY_CAPABILITY_TO_RUNTIME: dict[str, str] = {
    "memory": "kb_search",
    "market_quote": "market_data",
    "market_news": "news_search",
    "web_search": "web_search",
    "web_fetch": "web_search",
    "graph": "graph_lookup",
    "filings": "l3_lookup",
    "financials": "evidence_lookup",
    "market_data": "market_data",
    "mainline_context": "mainline_context",
    "kb_search": "kb_search",
    "graph_lookup": "graph_lookup",
    "evidence_lookup": "evidence_lookup",
    "news_search": "news_search",
    "l3_lookup": "l3_lookup",
}


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
    # Prompt-only history: useful for reference resolution, never evidence.
    conversation_context: str = ""
    # Prompt-only KOL perspective constraints (perspective_lab runtime prompt);
    # never evidence.  Empty string means neutral: legacy behavior byte-for-byte.
    perspective_context: str = ""
    # 个性化接合核。编排器在 project 之后 replace 写入；默认 None，旧测试逐字节。
    stance_pack: object | None = None
    # Prompt-only retrieval stage sequence from the owner workflow (via
    # ResearchPlan).  R-20260827-09: the plan used to stop at the trace and the
    # episode never saw it.  Empty tuple means "no owner stages": byte-for-byte
    # legacy behavior.  Never evidence.
    retrieval_stages: tuple[str, ...] = ()
    prior_evidence: PriorTurnEvidence | None = None


def project_turn_decision(
    decision: TurnDecision,
    *,
    task_frame: TaskFrame,
    turn_intent: TurnIntent | None = None,
    conversation_context: str = "",
    perspective_context: str = "",
    retrieval_stages: tuple[str, ...] = (),
) -> TurnControlResult:
    """Project one already-made decision without invoking understanding again."""

    clarification_questions = tuple(decision.clarification_questions)
    if not clarification_questions and task_frame.clarification_question:
        clarification_questions = (task_frame.clarification_question,)

    material = task_frame.material_contract
    material_only = bool(material and material.data_scope == "material_only")
    premise_calculation = bool(material and material.premise_calculation)
    needs_retrieval = not material_only and (
        decision.needs_retrieval or task_frame_requires_retrieval(task_frame)
    )
    if decision.lane == "clarify" or clarification_questions or (
        material is not None and material.needs_clarification
    ):
        terminal_kind: TerminalKind = "clarification"
    elif premise_calculation:
        # A calculation needs the verified Episode delivery, but no fact retrieval.
        terminal_kind = "research"
    elif material_only or needs_retrieval:
        # Evaluating frozen inputs needs the research delivery contract, not new reads.
        terminal_kind = "research"
    else:
        terminal_kind = "non_research"

    if terminal_kind == "research":
        frame_capabilities = runtime_capabilities_for_frame(task_frame)
        mapped_legacy_capabilities = tuple(
            runtime_name
            for capability in decision.capabilities
            if (runtime_name := _LEGACY_CAPABILITY_TO_RUNTIME.get(capability))
        )
        # The immutable TaskFrame owns evidence policy. Legacy aliases are a
        # compatibility fallback only when that policy has no runtime plan;
        # otherwise unioning them silently expands the model's tool surface.
        capabilities = restrict_read_capabilities(
            frame_capabilities
            if frame_capabilities
            else tuple(dict.fromkeys(mapped_legacy_capabilities)),
            material.data_scope if material is not None else None,
        )
        execution_route = task_frame.question_type
    else:
        capabilities = ()
        execution_route = (
            "clarify" if terminal_kind == "clarification" else decision.lane
        )
    return TurnControlResult(
        task_frame=task_frame,
        execution_route=execution_route,
        terminal_kind=terminal_kind,
        # Frozen inputs and premise calculations both deliver through the research
        # contract without new reads: neither may re-open retrieval here.
        needs_retrieval=(
            terminal_kind == "research" and needs_retrieval and not premise_calculation
        ),
        capabilities=capabilities,
        contract_required=terminal_kind == "research",
        turn_intent=turn_intent if turn_intent is not None else decision.turn_intent,
        clarification_questions=clarification_questions,
        conversation_context=str(conversation_context or "").strip(),
        perspective_context=str(perspective_context or "").strip(),
        retrieval_stages=tuple(retrieval_stages or ()),
    )


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
        frame = self._frame_for(decision, query, previous_frame, context=context)
        return project_turn_decision(
            decision,
            task_frame=frame,
            turn_intent=decision.turn_intent,
            conversation_context=context,
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
        *,
        context: str = "",
    ) -> TaskFrame:
        if decision.task_frame is not None:
            return decision.task_frame
        if decision.turn_intent is not None:
            pending = TaskFrame.from_dict(decision.turn_intent.pending_task_frame)
            if pending is not None:
                return pending
            return TurnControlCore._frame_from_intent(
                decision.turn_intent,
                query,
                confidence=decision.confidence,
                context=context,
            )
        if decision.question_type is not None:
            return TurnControlCore._frame_from_decision(decision, query, context=context)
        if previous_frame is not None:
            return previous_frame
        return TurnControlCore._frame_from_decision(decision, query, context=context)

    @staticmethod
    def _frame_from_decision(
        decision: TurnDecision,
        query: str,
        *,
        context: str = "",
    ) -> TaskFrame:
        """Project validated adapter metadata without interpreting the query twice."""

        from intelligence.services.query_understanding import QueryEnvelope

        question_type = decision.question_type or "general_finance_qa"
        subject_kind = TurnControlCore._subject_kind_for(question_type)
        envelope = QueryEnvelope(
            question_type=question_type,
            subject_kind=subject_kind,
            subject=decision.subject,
            decision_goal="形成与用户原问题一致的直接回答",
            timeframe=decision.timeframe,
            matched_by="explicit" if decision.subject is not None else "generic",
            confidence=decision.confidence,
        )
        # B05-1：对话块已知才传（None 保持旧调用方语义——不做材料绑定也不追问）。
        return build_task_frame(
            query, envelope, conversation_context=context if context else None
        )

    @staticmethod
    def _frame_from_intent(
        intent: TurnIntent,
        query: str,
        *,
        confidence: float,
        context: str = "",
    ) -> TaskFrame:
        from intelligence.services.query_understanding import QueryEnvelope

        subject_kind = TurnControlCore._subject_kind_for(
            intent.question_type,
            answer_owner=intent.answer_owner,
        )
        envelope = QueryEnvelope(
            question_type=intent.question_type,
            subject_kind=subject_kind,
            subject=intent.primary_subject,
            decision_goal="继续已验证的用户研究任务",
            timeframe=intent.timeframe,
            matched_by="explicit" if intent.primary_subject is not None else "generic",
            confidence=confidence,
            required_outputs=intent.required_outputs,
        )
        frame = build_task_frame(
            query, envelope, conversation_context=context if context else None
        )
        if frame.history_intent is None and intent.history_intent is not None:
            frame = replace(frame, history_intent=intent.history_intent)
        return rebase_task_frame(
            frame,
            question_type=intent.question_type,
            subject=intent.primary_subject,
            subject_kind=subject_kind,
            timeframe=intent.timeframe,
            required_outputs=intent.required_outputs,
        )

    @staticmethod
    def _subject_kind_for(
        question_type: str,
        *,
        answer_owner: str | None = None,
    ) -> str:
        if question_type in {
            "market_watch",
            "dated_market_review",
            "market_forecast",
            "market_cause",
            "market_technical",
        }:
            return "market_pattern"
        if question_type == "external_market":
            return "external_market"
        if (
            question_type in {"theme_analysis", "theme_track"}
            or answer_owner == "theme-research"
        ):
            return "theme"
        if question_type in {
            "stock_deep_dive",
            "valuation_estimate",
            "financial_analysis",
            "trade_advice",
        }:
            return "company"
        return "unknown"
