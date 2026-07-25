"""Build one bounded continuous-agent run context from a canonical TaskFrame.

This is a composition seam, not another router. It never reinterprets the
question and never imports private helpers from the legacy orchestrator.
"""

from __future__ import annotations

from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
    resolve_evidence_plan,
    runtime_capabilities_for_frame,
)
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    DEFAULT_RESEARCH_CAPABILITIES,
)
from intelligence.services.task_frame import TaskFrame


_OUTPUT_DESCRIPTIONS: dict[str, str] = {
    "direct_assessment": "直接回答用户问题并说明判断强度",
    "direct_answer": "直接回答用户问题",
    "direct_definition": "解释用户所问概念",
    "current_baseline": "说明最新可用市场基线与数据日期",
    "duration_assessment": "判断反弹可能持续的时间窗口",
    "continuation_conditions": "列出判断继续成立的可核验条件",
    "invalidation_conditions": "列出判断失效或降级的条件",
    "evidence_boundary": "说明证据覆盖范围、数据日期与缺口",
    "technical_levels": "给出结构化行情支持的技术区间或关键位",
    "data_date": "标明行情数据截止日期",
    "valuation_assessment": ("基于当前市场锚点说明估值方法、关键假设与当前估值判断"),
    "financial_business_anchor": "给出至少一项逐季财务或业务兑现硬数据锚点",
    "scenario_range": "给出明确方法与假设边界的估值情景区间",
    "causal_chain": "解释时间对齐的原因、传导链和盘面印证",
    "counterpoint": "提供主要反证或竞争性解释",
    "supporting_evidence": "列出与结论直接相关的支持证据",
    "risk_signals": "列出风险信号与观察条件",
    "market_summary": "概括目标市场窗口的结构化表现",
    "mainline_structure": "判断当前市场主线及其强弱结构",
    "scenario_paths": "给出条件化情景路径",
}

_VALUATION_REQUIRED_OUTPUTS = (
    "valuation_assessment",
    "financial_business_anchor",
    "scenario_range",
    "evidence_boundary",
    "invalidation_conditions",
)

_PRESENTATION_PROFILES: dict[str, str] = {
    "market_forecast": "market_scenarios",
    "market_cause": "market_causal",
    "market_technical": "market_technical",
    "market_watch": "market_watch",
    "valuation_estimate": "company_valuation",
    "stock_deep_dive": "stock_research",
    "comparison": "comparison",
    "comparison_analog": "comparison",
}


def _authorized_capabilities(
    frame: TaskFrame,
    capabilities: tuple[str, ...] | None,
) -> tuple[str, ...]:
    projected = (
        runtime_capabilities_for_frame(frame)
        if capabilities is None
        else tuple(
            dict.fromkeys(
                str(item).strip() for item in capabilities if str(item).strip()
            )
        )
    )
    allowed_names = set(DEFAULT_RESEARCH_CAPABILITIES)
    unknown = tuple(item for item in projected if item not in allowed_names)
    if unknown:
        raise ValueError("unknown runtime capability: " + ",".join(sorted(unknown)))
    return projected


def _episode_evidence_plan(frame: TaskFrame) -> EvidencePlan:
    plan = resolve_evidence_plan(
        frame.raw_question,
        question_type=frame.question_type,
        freshness="current",
    )
    if frame.question_type == "market_cause":
        return EvidencePlan(
            profile="time_aligned_market_causal",
            requirements=(
                EvidenceRequirement(
                    "MARKET_CAUSE_WINDOW",
                    "market_data",
                    True,
                    "current",
                    "指定市场窗口的结构化表现",
                ),
                EvidenceRequirement(
                    "MARKET_CAUSE_NEWS",
                    "news_search",
                    True,
                    "current",
                    "与市场窗口时间对齐的原因证据",
                ),
                EvidenceRequirement(
                    "MARKET_CAUSE_WEB",
                    "web_search",
                    False,
                    "current",
                    "明确标注为外部观点的竞争性解释",
                ),
            ),
            freshness="current",
        )
    if frame.question_type != "valuation_estimate":
        return plan
    requirements = tuple(
        item for item in plan.requirements if item.capability != "market_data"
    )
    return EvidencePlan(
        profile="valuation_current_anchor",
        requirements=(
            EvidenceRequirement(
                "VALUATION_MARKET",
                "market_data",
                True,
                "current",
                "当前价格、交易日与可比估值锚点",
            ),
            EvidenceRequirement(
                "VALUATION_FINANCIAL",
                "financial_data",
                True,
                "current",
                "逐季营收、利润或盈利质量硬数据锚点",
            ),
            *requirements,
        ),
        freshness="current",
    )


def _required_output_ids(frame: TaskFrame) -> tuple[str, ...]:
    if frame.question_type != "valuation_estimate":
        return frame.required_outputs
    return tuple(dict.fromkeys((*frame.required_outputs, *_VALUATION_REQUIRED_OUTPUTS)))


def _required_output_evidence_types(
    output_id: str,
    capabilities: tuple[str, ...],
) -> tuple[str, ...]:
    if output_id == "financial_business_anchor":
        return tuple(
            capability
            for capability in (
                "financial_data",
                "l3_lookup",
                "evidence_lookup",
                "kb_search",
            )
            if capability in capabilities
        )
    return capabilities


def _grounding_mode(frame: TaskFrame) -> str:
    """Project question semantics into the output grounding contract."""

    if frame.question_type == "methodology_discussion" or "method" in frame.required_outputs:
        return "model_reasoning"
    if frame.user_goal.startswith("判断反事实条件"):
        return "user_premise"
    return "evidence"


def build_episode_context(
    frame: TaskFrame,
    *,
    task_id: str,
    capabilities: tuple[str, ...] | None = None,
    tier: str = "standard",
    timeout: float | None = None,
    synthesis_reserve: float | None = None,
    trace_parent_id: str | None = None,
    today: str | None = None,
    latest_data_date: str | None = None,
    conversation_context: str = "",
) -> ResearchRunContext:
    """Freeze control output into one immutable research run contract."""

    grounding_mode = _grounding_mode(frame)
    evidence_plan = _episode_evidence_plan(frame)
    authorized = list(_authorized_capabilities(frame, capabilities))
    if grounding_mode in {"model_reasoning", "user_premise"}:
        # These contracts ask the model to reason over a method or an explicit
        # user-supplied premise.  Retrieving current-world evidence adds cost
        # and can contaminate the hypothetical without strengthening it.
        evidence_plan = EvidencePlan(
            profile=grounding_mode,
            requirements=(),
            freshness="stable",
        )
        authorized = []
    known = set(DEFAULT_RESEARCH_CAPABILITIES)
    for capability in evidence_plan.mandatory_capabilities:
        if capability not in known:
            raise ValueError(f"unknown runtime capability: {capability}")
        if capability not in authorized:
            authorized.append(capability)
    capability_tuple = tuple(authorized)

    base_policy = ResearchPolicy.for_tier(tier)
    effective_timeout = base_policy.total_seconds
    if timeout is not None:
        effective_timeout = min(
            base_policy.total_seconds,
            max(0.0, float(timeout)),
        )
    requested_reserve = (
        base_policy.synthesis_reserve
        if synthesis_reserve is None
        else max(0.0, float(synthesis_reserve))
    )
    reserve = min(requested_reserve, effective_timeout)
    policy = ResearchPolicy(
        base_policy.tier,
        base_policy.max_steps,
        base_policy.total_seconds,
        reserve,
    )

    contract = ResearchTaskContract(
        task_id=task_id,
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=tuple(
            RequiredOutput(
                output_id=output_id,
                description=_OUTPUT_DESCRIPTIONS.get(output_id, output_id),
                evidence_types=_required_output_evidence_types(
                    output_id,
                    capability_tuple,
                ),
                required=True,
                grounding_mode=grounding_mode,
            )
            for output_id in _required_output_ids(frame)
        ),
        allowed_capabilities=capability_tuple,
        research_tier=policy.tier,
        presentation_profile=_PRESENTATION_PROFILES.get(
            frame.question_type,
            "general",
        ),
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=evidence_plan,
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(
            effective_timeout,
            synthesis_reserve=reserve,
        ),
        policy=policy,
        trace_parent_id=trace_parent_id or task_id,
        today=today,
        latest_data_date=latest_data_date,
        conversation_context=str(conversation_context or "").strip(),
    )


__all__ = ["build_episode_context"]
