"""Adaptive quick/deep authority for one model-owned research plan."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Literal, cast

from intelligence.services.repair_coordinator import BudgetGrant
from intelligence.services.research_contract import ResearchPolicy, ResearchRunContext
from intelligence.services.research_plan import ResearchPlan


UserMode = Literal["auto", "quick", "deep"]
EffectiveMode = Literal["quick", "deep"]
ComplexityFlag = Literal[
    "causal_attribution",
    "valuation",
    "counterfactual",
    "historical_analogy",
    "supply_chain_mapping",
]
ResearchTier = Literal["standard", "deep"]

_USER_MODES = frozenset({"auto", "quick", "deep"})
_COMPLEXITY_FLAGS = frozenset(
    {
        "causal_attribution",
        "valuation",
        "counterfactual",
        "historical_analogy",
        "supply_chain_mapping",
    }
)


def _non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _clean_domains(values: object) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise ValueError("evidence_domains must be an array")
    cleaned = tuple(dict.fromkeys(str(item or "").strip() for item in values))
    if any(not item for item in cleaned):
        raise ValueError("evidence_domains must contain non-empty strings")
    return cleaned


@dataclass(frozen=True)
class ModeSignals:
    user_mode: UserMode = "auto"
    independent_entities: int = 0
    evidence_domains: tuple[str, ...] = ()
    complexity_flags: tuple[ComplexityFlag, ...] = ()
    uncovered_answer_elements: int = 0
    dependencies_available: bool = True
    deep_deadline_available: bool = True

    def __post_init__(self) -> None:
        if self.user_mode not in _USER_MODES:
            raise ValueError("user_mode must be auto, quick, or deep")
        object.__setattr__(
            self,
            "independent_entities",
            _non_negative_int(self.independent_entities, "independent_entities"),
        )
        object.__setattr__(
            self,
            "uncovered_answer_elements",
            _non_negative_int(
                self.uncovered_answer_elements,
                "uncovered_answer_elements",
            ),
        )
        object.__setattr__(
            self,
            "evidence_domains",
            _clean_domains(self.evidence_domains),
        )
        flags = tuple(dict.fromkeys(str(item or "").strip() for item in self.complexity_flags))
        if any(flag not in _COMPLEXITY_FLAGS for flag in flags):
            raise ValueError("unsupported complexity flag")
        object.__setattr__(self, "complexity_flags", flags)
        if not isinstance(self.dependencies_available, bool):
            raise ValueError("dependencies_available must be boolean")
        if not isinstance(self.deep_deadline_available, bool):
            raise ValueError("deep_deadline_available must be boolean")


@dataclass(frozen=True)
class ModeDecision:
    requested_mode: EffectiveMode
    effective_mode: EffectiveMode
    approved: bool
    reason: str
    observable_conditions: tuple[str, ...]
    research_tier: ResearchTier
    tool_call_cap: int
    target_seconds: float
    max_repair_cycles: int
    max_branches: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["observable_conditions"] = list(self.observable_conditions)
        return payload


def _quick_decision(
    *,
    requested_mode: EffectiveMode,
    reason: str,
    conditions: tuple[str, ...] = (),
) -> ModeDecision:
    return ModeDecision(
        requested_mode=requested_mode,
        effective_mode="quick",
        approved=False,
        reason=reason,
        observable_conditions=conditions,
        research_tier="standard",
        tool_call_cap=8,
        target_seconds=90.0,
        max_repair_cycles=1,
        max_branches=0,
    )


def _deep_decision(
    *,
    requested_mode: EffectiveMode,
    reason: str,
    conditions: tuple[str, ...],
) -> ModeDecision:
    return ModeDecision(
        requested_mode=requested_mode,
        effective_mode="deep",
        approved=True,
        reason=reason,
        observable_conditions=conditions,
        research_tier="deep",
        tool_call_cap=24,
        target_seconds=240.0,
        max_repair_cycles=3,
        max_branches=3,
    )


class ModeGovernor:
    """Approve model-requested depth from observable, code-owned signals."""

    def decide(self, plan: ResearchPlan, signals: ModeSignals) -> ModeDecision:
        if not isinstance(plan, ResearchPlan):
            raise TypeError("plan must be ResearchPlan")
        if not isinstance(signals, ModeSignals):
            raise TypeError("signals must be ModeSignals")

        requested = cast(
            EffectiveMode,
            "deep" if signals.user_mode == "deep" else plan.requested_mode,
        )
        conditions: list[str] = []
        if signals.independent_entities >= 2:
            conditions.append("multiple_independent_entities")
        if len(signals.evidence_domains) >= 2:
            conditions.append("multiple_evidence_domains")
        conditions.extend(
            f"complexity:{flag}" for flag in signals.complexity_flags
        )
        if signals.uncovered_answer_elements >= 1:
            conditions.append("material_uncovered_answer_element")
        observable = tuple(conditions)

        if signals.user_mode == "quick":
            return _quick_decision(
                requested_mode=requested,
                reason="user_selected_quick",
                conditions=observable,
            )
        if requested == "quick":
            return _quick_decision(
                requested_mode=requested,
                reason="model_requested_quick",
                conditions=observable,
            )
        if not signals.dependencies_available:
            return _quick_decision(
                requested_mode=requested,
                reason="deep_dependencies_unavailable",
                conditions=observable,
            )
        if not signals.deep_deadline_available:
            return _quick_decision(
                requested_mode=requested,
                reason="deep_deadline_unavailable",
                conditions=observable,
            )
        if signals.user_mode == "deep":
            return _deep_decision(
                requested_mode=requested,
                reason="user_selected_deep",
                conditions=("explicit_user_deep", *observable),
            )
        if not observable:
            return _quick_decision(
                requested_mode=requested,
                reason="no_observable_deep_condition",
            )
        return _deep_decision(
            requested_mode=requested,
            reason="observable_complexity_approved",
            conditions=observable,
        )

    def apply(
        self,
        context: ResearchRunContext,
        decision: ModeDecision,
    ) -> ResearchRunContext:
        """Apply one approved deep promotion to the existing episode authority."""

        if not isinstance(context, ResearchRunContext):
            raise TypeError("context must be ResearchRunContext")
        if not isinstance(decision, ModeDecision):
            raise TypeError("decision must be ModeDecision")
        if not decision.approved or decision.effective_mode != "deep":
            return context
        if decision.tool_call_cap > 24 or decision.target_seconds > 240.0:
            raise ValueError("deep decision exceeds product cap")
        root = context.root_budget
        if root is None:
            raise ValueError("deep promotion requires one root budget ledger")

        episode_id = context.contract.task_id
        promotion_id = f"mode-promotion:{episode_id}:deep"
        allocated_calls = root.allocated_calls
        allocated_seconds = root.allocated_seconds
        if not root.promote_caps(
            episode_id=episode_id,
            promotion_id=promotion_id,
            hard_calls_cap=decision.tool_call_cap,
            hard_seconds_cap=decision.target_seconds,
        ):
            raise ValueError("root budget refused deep promotion")

        deep_policy = ResearchPolicy.for_tier("deep")
        target_allocated_seconds = max(
            0.0,
            decision.target_seconds - deep_policy.synthesis_reserve,
        )
        calls_granted = max(0, decision.tool_call_cap - allocated_calls)
        seconds_granted = max(0.0, target_allocated_seconds - allocated_seconds)
        if calls_granted or seconds_granted:
            if calls_granted <= 0 or seconds_granted <= 0:
                raise ValueError("deep budget allocation is internally inconsistent")
            grant = BudgetGrant(
                grant_id=f"grant-{promotion_id}",
                episode_id=episode_id,
                cycle=0,
                calls_granted=calls_granted,
                seconds_granted=seconds_granted,
            )
            if not root.grant(grant):
                raise ValueError("root budget refused deep allocation")

        deadline_extension = max(
            0.0,
            decision.target_seconds - context.policy.total_seconds,
        )
        promoted_deadline = replace(
            context.deadline,
            expires_at=context.deadline.expires_at + deadline_extension,
            synthesis_reserve=deep_policy.synthesis_reserve,
        )
        if context.policy.tier == "deep" and deadline_extension == 0.0:
            promoted_deadline = context.deadline
        return replace(
            context,
            policy=deep_policy,
            deadline=promoted_deadline,
        )


__all__ = [
    "ComplexityFlag",
    "EffectiveMode",
    "ModeDecision",
    "ModeGovernor",
    "ModeSignals",
    "UserMode",
]
