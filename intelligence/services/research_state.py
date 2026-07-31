"""Turn-scoped cognitive state for generic research.

The state is deliberately separate from presentation objects.  It keeps the
question, hypotheses, evidence relationships and unresolved gaps in one place
so planner, tools, completion gates and the presenter do not each reconstruct
their own lossy view of the turn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any


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
    content_hash: str = ""


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
        self.required_output_evidence_types: dict[str, tuple[str, ...]] = {}
        self.required_output_required: dict[str, bool] = {}
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
        # 情景输出本身就是最小可审计假设集合。这样 planner/agent 不必再
        # 各自维护一份“反弹/下跌/失效”清单，证据关系统一回写到本状态。
        hypothesis_kinds = {
            "rebound_case": "scenario",
            "decline_case": "scenario",
            "invalidation": "falsifier",
            "relation_map": "relation",
            "counterpoint": "counterpoint",
            "cause_attribution": "causal",
            "causal_explanation": "causal",
            # 事件预测与盘面情景不同，但同样需要把每个可审计输出登记为
            # hypothesis，避免任意一条工具命中就让 finish=true 提前放行。
            "event_facts": "scenario",
            "event_transmission": "causal",
            "verification_window": "scenario",
            "falsification_window": "falsifier",
            "counter_evidence": "counterpoint",
            # 错误前提必须被专属证据支持、反驳或显式报 gap；
            # 不能因为“查到了任意网页”就宣告前提核验完成。
            "premise_check": "fact_check",
        }
        for item in getattr(contract, "required_outputs", ()):
            output_id = str(getattr(item, "output_id", ""))
            description = str(getattr(item, "description", ""))
            state.required_output_evidence_types[output_id] = tuple(
                str(value) for value in getattr(item, "evidence_types", ())
            )
            state.required_output_required[output_id] = bool(
                getattr(item, "required", True)
            )
            kind = hypothesis_kinds.get(output_id)
            if kind and state.required_output_required[output_id]:
                state.add_hypothesis(output_id, description, kind=kind)
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
            self.assessment = normalized[:1600]
            self.revision += 1

    def bind_hypothesis_evidence(
        self,
        hypothesis_id: str,
        evidence_ids: tuple[str, ...] | list[str],
        *,
        contradicts: bool = False,
    ) -> None:
        """Bind a deterministic conditional claim to the evidence it observes.

        This is used by deterministic fallback presenters (for example, a
        forecast's rebound/decline triggers).  It records that the conditional
        scenario is grounded in a measured signal; it does not assert that the
        scenario has happened or will happen.
        """

        hypothesis = self._hypothesis(hypothesis_id)
        if hypothesis is None:
            return
        target = (
            hypothesis.contradicting_evidence
            if contradicts
            else hypothesis.supporting_evidence
        )
        changed = False
        for evidence_id in evidence_ids:
            value = str(evidence_id).strip()
            if value and value not in target:
                target.append(value)
                changed = True
        if changed:
            self.revision += 1

    def set_stop_reason(self, reason: str) -> None:
        if reason.strip():
            self.stop_reason = reason.strip()

    def evaluate_completion(
        self,
        *,
        fulfilled_outputs: frozenset[str] = frozenset(),
    ) -> CompletionState:
        """``fulfilled_outputs`` 是契约层已确认交付的 output。

        gap 是只追加的：``add_gap`` 只会新增或原地更新，没有任何解除路径。于是一条
        早期的临时缺口（首轮检索落空、行情预取失败）会永久留在 blocking_gaps 里，
        coverage 再也回不到 fulfilled —— 哪怕它声称阻塞的那些 output 后来全部交付。
        往下传导就是 status=partial → business_status=gap →
        prepare_existing_answer 关掉 synthesize，整轮拿不到自然语言合成。实测本机
        79 条 run 里 68 条根本没有 composer 记录。

        「阻塞」的定义就是「有东西因它交付不了」。它列的 output 全都已经交付时，
        它已经不再阻塞任何东西，只是一条历史记录。只要还有一条没交付，它照旧阻塞。
        """

        evidence_ok = bool(self.evidence)
        has_causal_question = self.question_type in {
            "market_cause",
            "news_impact",
            "cause_attribution",
        } or any(
            output in {"cause_attribution", "causal_explanation"}
            for output in self.required_outputs
        )
        available_capabilities = {item.tool for item in self.evidence.values()}
        blocking_gaps = {
            output
            for gap in self.gaps
            if not (
                gap.blocks
                and set(gap.blocks) <= fulfilled_outputs
                # gap 点名了需要哪个能力时，那个能力必须真的到位才算解除。
                # 「结构化行情预取失败」阻塞 direct_assessment/supporting_evidence，
                # 光靠网页来源把这两项凑齐不等于缺陷已解决——它说的就是本轮没拿到
                # 结构化盘面真值。没点名能力的 gap 只能按 output 是否交付判断。
                and set(gap.suggested_capabilities) <= available_capabilities
            )
            for output in gap.blocks
        }
        uncovered_hypotheses = {
            hypothesis.hypothesis_id
            for hypothesis in self.hypotheses
            if not (
                hypothesis.supporting_evidence
                or hypothesis.contradicting_evidence
                or hypothesis.hypothesis_id in blocking_gaps
            )
        }
        has_assessment = bool(self.assessment.strip())
        factual = "fulfilled" if evidence_ok else "missing"
        if has_causal_question:
            mechanism_evidence = any(
                item.tool == "market_data" or item.supports
                for item in self.evidence.values()
            )
            # Current-window causal claims need dated external evidence.  An
            # undated web snippet remains a lead, not proof of this week's
            # trigger.
            from intelligence.services.evidence_window import is_time_aligned_evidence

            evidence_dates = []
            for item in self.evidence.values():
                if not item.source_date:
                    continue
                try:
                    evidence_dates.append(
                        date.fromisoformat(
                            str(item.source_date)[:10].replace("/", "-")
                        )
                    )
                except ValueError:
                    continue
            reference_date = max(evidence_dates, default=None)

            question_terms = tuple(
                token
                for token in re.findall(
                    r"[\u4e00-\u9fff]{2,6}|[A-Za-z0-9_.-]{3,}",
                    self.question,
                )
                if token not in {"主要原因", "为什么", "这一周", "市场", "行情"}
            )
            external_evidence = any(
                item.tool in {"news_search", "web_search"}
                and is_time_aligned_evidence(item, reference_date=reference_date)
                and (
                    not question_terms
                    or any(
                        token in f"{item.title} {item.detail}"
                        for token in question_terms
                    )
                    or any(
                        term in f"{item.title} {item.detail}"
                        for term in ("指数", "股市", "资金", "政策", "美股", "市场")
                    )
                )
                for item in self.evidence.values()
            )
            causal = (
                "partial"
                if "cause_attribution" in blocking_gaps or "causal_explanation" in blocking_gaps
                else "fulfilled"
                if has_assessment and mechanism_evidence and external_evidence
                else "partial"
                if mechanism_evidence
                else "missing"
            )
        else:
            causal = "fulfilled"
        coverage = (
            "missing"
            if (not has_assessment and self.required_outputs)
            or (
                bool(self.hypotheses)
                and uncovered_hypotheses == {
                    hypothesis.hypothesis_id for hypothesis in self.hypotheses
                }
            )
            else "partial"
            if blocking_gaps or uncovered_hypotheses
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
            "required_output_evidence_types": {
                key: list(value)
                for key, value in self.required_output_evidence_types.items()
            },
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
