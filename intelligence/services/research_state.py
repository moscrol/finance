"""Turn-scoped cognitive state for generic research.

The state is deliberately separate from presentation objects.  It keeps the
question, hypotheses, evidence relationships and unresolved gaps in one place
so planner, tools, completion gates and the presenter do not each reconstruct
their own lossy view of the turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class EvidenceObservation:
    evidence_id: str
    tool: str
    title: str
    detail: str
    source: str
    source_date: str | None = None
    evidence_tier: str = ""
    supports: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    independent_key: str = ""
    freshness: str = "unknown"


@dataclass
class HypothesisState:
    hypothesis_id: str
    statement: str
    kind: str = "explanation"
    status: str = "open"
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResearchGap:
    gap_id: str
    description: str
    blocks: tuple[str, ...] = ()
    suggested_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompletionState:
    factual_grounding: str
    causal_adequacy: str
    task_coverage: str
    status: str

    def to_dict(self) -> dict[str, str]:
        return {
            "factual_grounding": self.factual_grounding,
            "causal_adequacy": self.causal_adequacy,
            "task_coverage": self.task_coverage,
            "status": self.status,
        }


class ResearchState:
    """Mutable, serializable state shared by one generic research turn."""

    def __init__(
        self,
        *,
        question: str,
        subject: str | None,
        question_type: str,
        timeframe: str | None = None,
        required_outputs: tuple[str, ...] = (),
        presentation_profile: str = "general",
    ) -> None:
        self.question = question
        self.subject = subject
        self.question_type = question_type
        self.timeframe = timeframe
        self.required_outputs = tuple(required_outputs)
        self.presentation_profile = presentation_profile
        self.hypotheses: list[HypothesisState] = []
        self.evidence: dict[str, EvidenceObservation] = {}
        self.gaps: list[ResearchGap] = []
        self.assessment: str = ""
        self.stop_reason: str = ""
        self.revision: int = 0
        self.budget: dict[str, float | int] = {}

    @classmethod
    def from_contract(cls, contract: Any) -> "ResearchState":
        outputs = tuple(
            str(getattr(item, "output_id", item))
            for item in getattr(contract, "required_outputs", ())
        )
        state = cls(
            question=str(getattr(contract, "question", "")),
            subject=getattr(contract, "subject", None),
            question_type=str(getattr(contract, "question_type", "general_finance_qa")),
            timeframe=getattr(contract, "timeframe", None),
            required_outputs=outputs,
            presentation_profile=str(getattr(contract, "presentation_profile", "general")),
        )
        state.budget = {
            "max_steps": int(getattr(getattr(contract, "policy", None), "max_steps", 0) or 0),
        }
        return state

    def add_hypothesis(self, hypothesis_id: str, statement: str, *, kind: str = "explanation") -> None:
        if not hypothesis_id.strip() or not statement.strip():
            return
        existing = next(
            (item for item in self.hypotheses if item.hypothesis_id == hypothesis_id),
            None,
        )
        if existing is None:
            self.hypotheses.append(HypothesisState(hypothesis_id, statement, kind))
            self.revision += 1
            return
        if existing.statement != statement or existing.kind != kind:
            existing.statement = statement
            existing.kind = kind
            self.revision += 1

    def add_evidence(self, observation: EvidenceObservation) -> bool:
        if not observation.evidence_id.strip():
            return False
        changed = self.evidence.get(observation.evidence_id) != observation
        self.evidence[observation.evidence_id] = observation
        for hypothesis_id in observation.supports:
            hypothesis = self._hypothesis(hypothesis_id)
            if hypothesis is not None and observation.evidence_id not in hypothesis.supporting_evidence:
                hypothesis.supporting_evidence.append(observation.evidence_id)
                changed = True
        for hypothesis_id in observation.contradicts:
            hypothesis = self._hypothesis(hypothesis_id)
            if hypothesis is not None and observation.evidence_id not in hypothesis.contradicting_evidence:
                hypothesis.contradicting_evidence.append(observation.evidence_id)
                changed = True
        if changed:
            self.revision += 1
        return changed

    def add_gap(
        self,
        gap_id: str,
        description: str,
        *,
        blocks: tuple[str, ...] = (),
        suggested_capabilities: tuple[str, ...] = (),
    ) -> None:
        if not gap_id.strip() or not description.strip():
            return
        value = ResearchGap(gap_id, description, tuple(blocks), tuple(suggested_capabilities))
        for index, current in enumerate(self.gaps):
            if current.gap_id == gap_id:
                if current != value:
                    self.gaps[index] = value
                    self.revision += 1
                return
        self.gaps.append(value)
        self.revision += 1

    def set_assessment(self, assessment: str) -> None:
        normalized = assessment.strip()
        if normalized and normalized != self.assessment:
            self.assessment = normalized[:1200]
            self.revision += 1

    def set_stop_reason(self, reason: str) -> None:
        if reason.strip():
            self.stop_reason = reason.strip()

    def evaluate_completion(self) -> CompletionState:
        evidence_ok = bool(self.evidence)
        has_causal_question = self.question_type in {
            "market_cause",
            "news_impact",
            "cause_attribution",
        } or any(
            output in {"cause_attribution", "causal_explanation"}
            for output in self.required_outputs
        )
        blocking_gaps = {
            output
            for gap in self.gaps
            for output in gap.blocks
        }
        has_assessment = bool(self.assessment.strip())
        factual = "fulfilled" if evidence_ok else "missing"
        if has_causal_question:
            mechanism_evidence = any(
                item.supports
                or item.tool in {"market_data", "news_search", "web_search"}
                for item in self.evidence.values()
            )
            causal = (
                "partial"
                if "cause_attribution" in blocking_gaps or "causal_explanation" in blocking_gaps
                else "fulfilled"
                if has_assessment and mechanism_evidence
                else "missing"
            )
        else:
            causal = "fulfilled"
        coverage = (
            "missing"
            if not has_assessment and self.required_outputs
            else "partial"
            if blocking_gaps
            else "fulfilled"
        )
        status = "completed" if factual == causal == coverage == "fulfilled" else "partial"
        return CompletionState(factual, causal, coverage, status)

    def summary_for_agent(self, *, max_evidence: int = 8) -> str:
        hypotheses = "；".join(
            f"{item.hypothesis_id}:{item.statement}"
            f"(支持={','.join(item.supporting_evidence) or '无'};"
            f"反驳={','.join(item.contradicting_evidence) or '无'})"
            for item in self.hypotheses
        ) or "（尚未形成候选假设）"
        evidence = "；".join(
            f"{item.evidence_id} {item.tool}: {item.title} — {item.detail[:180]}"
            for item in list(self.evidence.values())[-max_evidence:]
        ) or "（尚未取得证据）"
        gaps = "；".join(
            f"{gap.gap_id}: {gap.description}"
            for gap in self.gaps
        ) or "（无已登记缺口）"
        completion = self.evaluate_completion().to_dict()
        return (
            f"问题边界：{self.question}\n"
            f"候选假设：{hypotheses}\n"
            f"证据（支持/反驳关系）：{evidence}\n"
            f"未解决缺口：{gaps}\n"
            f"完成状态：{completion}\n"
            f"状态修订号：{self.revision}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "subject": self.subject,
            "question_type": self.question_type,
            "timeframe": self.timeframe,
            "required_outputs": list(self.required_outputs),
            "presentation_profile": self.presentation_profile,
            "hypotheses": [
                {
                    "hypothesis_id": item.hypothesis_id,
                    "statement": item.statement,
                    "kind": item.kind,
                    "status": item.status,
                    "supporting_evidence": list(item.supporting_evidence),
                    "contradicting_evidence": list(item.contradicting_evidence),
                }
                for item in self.hypotheses
            ],
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "tool": item.tool,
                    "title": item.title,
                    "detail": item.detail,
                    "source": item.source,
                    "source_date": item.source_date,
                    "evidence_tier": item.evidence_tier,
                    "supports": list(item.supports),
                    "contradicts": list(item.contradicts),
                    "independent_key": item.independent_key,
                    "freshness": item.freshness,
                }
                for item in self.evidence.values()
            ],
            "gaps": [
                {
                    "gap_id": gap.gap_id,
                    "description": gap.description,
                    "blocks": list(gap.blocks),
                    "suggested_capabilities": list(gap.suggested_capabilities),
                }
                for gap in self.gaps
            ],
            "assessment": self.assessment,
            "stop_reason": self.stop_reason,
            "revision": self.revision,
            "completion": self.evaluate_completion().to_dict(),
            "budget": dict(self.budget),
        }

    def _hypothesis(self, hypothesis_id: str) -> HypothesisState | None:
        return next(
            (item for item in self.hypotheses if item.hypothesis_id == hypothesis_id),
            None,
        )


def state_from_contract(contract: Any) -> ResearchState:
    """Small public adapter kept here to avoid callers depending on constructors."""

    return ResearchState.from_contract(contract)
