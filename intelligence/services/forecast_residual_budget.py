"""展望座位的残差预算：开口包齐才升 deep，连打同问句停机。

P1 量纲（审查钉死）：``ResearchPolicy.for_tier("deep")`` 的一对
``(max_steps, total_seconds)`` = 12×240s。禁止再拧每格剩余预算。
确定性 owner 题（涨停家数 / dated 事实）永不进本支。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from intelligence.services.repair_coordinator import BudgetGrant
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
)

FORECAST_RESIDUAL_QUESTION_TYPE = "market_forecast"
DO_NOT_LENGTHEN_QUESTION_TYPES = frozenset(
    {
        "external_market",
        "quick_fact",
        "dated_market_review",
        "market_watch",
        "watchlist_digest",
        "disclosure_scan",
    }
)
FORECAST_RESIDUAL_SPIN = "forecast_residual_duplicate_spin"


def forecast_opening_pack_ready(items: Iterable[object] | None) -> bool:
    """五日包已发卡（含 locked / unavailable）。旧 3 日双红个数不算齐。"""

    for item in items or ():
        title = str(getattr(item, "title", "") or "")
        detail = str(getattr(item, "detail", "") or "")
        if title.endswith("四袋") or title == "先验周量能序列":
            return True
        blob = f"{title} {detail}"
        if "status=locked" in blob or "复盘写入中" in blob:
            return True
        if "status=unavailable" in blob:
            return True
    return False


def should_promote_forecast_residual(
    question_type: str,
    opening_items: Iterable[object] | None,
) -> bool:
    question = str(question_type or "").strip()
    if question != FORECAST_RESIDUAL_QUESTION_TYPE:
        return False
    if question in DO_NOT_LENGTHEN_QUESTION_TYPES:
        return False
    return forecast_opening_pack_ready(opening_items)


def forecast_residual_halt_reason(
    *,
    question_type: str,
    research_tier: str,
    batch_errors: Iterable[str | None],
) -> str | None:
    """深档展望残差里第二次同问句：停机，禁止再要一轮。"""

    if str(question_type or "").strip() != FORECAST_RESIDUAL_QUESTION_TYPE:
        return None
    if str(research_tier or "").strip() != "deep":
        return None
    if any(str(error or "") == "duplicate_query" for error in batch_errors):
        return FORECAST_RESIDUAL_SPIN
    return None


def promote_forecast_residual(context: ResearchRunContext) -> ResearchRunContext:
    """把已有 standard 账本升到 deep 一对闸，不另开第二本 root ledger。"""

    deep = ResearchPolicy.for_tier("deep")
    if context.policy.tier == "deep" and context.contract.research_tier == "deep":
        return context

    root = context.root_budget
    if root is not None:
        episode_id = context.contract.task_id
        promotion_id = f"forecast-residual:{episode_id}:deep"
        if not root.promote_caps(
            episode_id=episode_id,
            promotion_id=promotion_id,
            hard_calls_cap=deep.max_steps,
            hard_seconds_cap=deep.total_seconds,
        ):
            return context
        target_seconds = max(0.0, deep.total_seconds - deep.synthesis_reserve)
        calls_granted = max(0, deep.max_steps - root.allocated_calls)
        seconds_granted = max(0.0, target_seconds - root.allocated_seconds)
        if calls_granted or seconds_granted:
            if calls_granted <= 0 or seconds_granted <= 0:
                return context
            granted = root.grant(
                BudgetGrant(
                    grant_id=f"grant-{promotion_id}",
                    episode_id=episode_id,
                    cycle=0,
                    calls_granted=calls_granted,
                    seconds_granted=seconds_granted,
                )
            )
            if not granted:
                return context

    deadline = ResearchDeadline.from_timeout(
        deep.total_seconds,
        synthesis_reserve=deep.synthesis_reserve,
    )
    return replace(
        context,
        contract=replace(context.contract, research_tier="deep"),
        policy=deep,
        deadline=deadline,
    )


def maybe_promote_forecast_residual(
    context: ResearchRunContext,
    *,
    question_type: str,
    opening_prefetch: Iterable[object] | None,
) -> ResearchRunContext:
    if not should_promote_forecast_residual(question_type, opening_prefetch):
        return context
    return promote_forecast_residual(context)
