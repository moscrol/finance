"""Adaptive quick/deep authority for one model-owned research plan.

只裁决「该做多深」。裁决落到预算合同上的动作（提 caps、铸 grant、换 policy）住在
``intelligence/runtime/tier_promotion.apply_mode_promotion``——领域层不碰账本。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, cast

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
    separable_branches: int = 0
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
            "separable_branches",
            _non_negative_int(self.separable_branches, "separable_branches"),
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
        if signals.separable_branches >= 1:
            conditions.append("separable_sub_research_branch")
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

    # 「升」的账本动作（提 caps / 铸 grant / 换 policy）在 ``runtime/tier_promotion``
    # ``apply_mode_promotion``：领域裁决、底座记账，本类不再持有账本。


__all__ = [
    "ComplexityFlag",
    "EffectiveMode",
    "ModeDecision",
    "ModeGovernor",
    "ModeSignals",
    "UserMode",
]
