"""升档（standard → deep）的账本动作：提 caps、铸 delta grant、换 policy / 延 deadline。

从两处 ``services`` 模块搬来，逐字未改算术：

- ``apply_mode_promotion`` ← ``services/mode_governor.ModeGovernor.apply``（PLAN 后深度
  裁决批准 deep）。
- ``promote_forecast_residual`` / ``maybe_promote_forecast_residual`` ←
  ``services/forecast_residual_budget``（展望座位开口包齐时升 deep）。

为什么搬：`2026-09-02-repair-policy-state-machine.md` §3.3 M5 判定「持有 ``RootBudgetLedger``
并铸额度」是预算算术、属底座，修复线的五个 ``grant_for_*`` 据此进了 ``runtime/repair_budget``。
升档是同一条纪律剩下的两处——领域层（``services/``）直接调 ``root.promote_caps()`` /
``root.grant()``，与 M5 是同一种错层。搬完之后 ``services/`` 里再没有账本写入
（棘轮：``test_root_budget_invariants``）。

分工不变：**领域裁决、底座记账。** ``ModeGovernor.decide`` /
``should_promote_forecast_residual`` 回答「该不该升」（读 PLAN / 信号 / 座位 / 开口包），
本模块只消费那个结论，不自己判。``FinanceResearchHarness.govern_mode`` 从此只出裁决与
给模型的话；loop 拿到 ``decision`` 后调 ``apply_mode_promotion`` 把它落到 context 上——
与修复轮「领域申请、底座授予」同形。

两处升档故意**不合并**：``apply_mode_promotion`` 对不一致的账本状态抛 ``ValueError``、
延长既有 deadline、不改 contract；``promote_forecast_residual`` 对任何拒绝静默原样返回、
重建 deadline、把 ``contract.research_tier`` 一并翻成 deep。这些是既有行为，本次零改动。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from intelligence.services.forecast_residual_budget import (
    should_promote_forecast_residual,
)
from intelligence.services.mode_governor import ModeDecision
from intelligence.services.repair_coordinator import BudgetGrant
from intelligence.services.research_contract import (
    PRODUCT_MAX_SECONDS,
    PRODUCT_MAX_TOOL_CALLS,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
)


def _already_at_or_above_deep(context: ResearchRunContext) -> bool:
    """当前档位的墙钟与步数都不低于 deep 时，升 deep 只会把账本改小。

    max 档（2026-09-06）从一开始就在 deep 之上；PLAN 裁决仍可能「批 deep」，这时
    账本动作必须是空操作——否则 ``replace(context, policy=deep_policy)`` 会把
    600s / 32 步换成 240s / 12 步，升档变降档。裁决本身（含 ``max_branches``）不受影响，
    子研究照常起。
    """

    deep = ResearchPolicy.for_tier("deep")
    return (
        context.policy.total_seconds >= deep.total_seconds
        and context.policy.max_steps >= deep.max_steps
    )


def apply_mode_promotion(
    context: ResearchRunContext,
    decision: ModeDecision,
) -> ResearchRunContext:
    """把一次已批准的 deep 裁决落到既有 episode 授权上（原 ``ModeGovernor.apply``）。

    未批准 / 非 deep 原样返回。批准了但账本拒绝、或 caps 超产品上限，抛 ``ValueError``
    ——这是在 PLAN 之后、动手之前，宁可停下也不带着错账跑。
    """

    if not isinstance(context, ResearchRunContext):
        raise TypeError("context must be ResearchRunContext")
    if not isinstance(decision, ModeDecision):
        raise TypeError("decision must be ModeDecision")
    if not decision.approved or decision.effective_mode != "deep":
        return context
    if (
        decision.tool_call_cap > PRODUCT_MAX_TOOL_CALLS
        or decision.target_seconds > PRODUCT_MAX_SECONDS
    ):
        raise ValueError("deep decision exceeds product cap")
    if _already_at_or_above_deep(context):
        return context
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


def promote_forecast_residual(context: ResearchRunContext) -> ResearchRunContext:
    """把已有 standard 账本升到 deep 一对闸，不另开第二本 root ledger。"""

    deep = ResearchPolicy.for_tier("deep")
    if context.policy.tier == "deep" and context.contract.research_tier == "deep":
        return context
    if _already_at_or_above_deep(context):
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
    """领域判定（座位对且开口包齐）→ 底座动作。判定不成立原样返回同一个对象。"""

    if not should_promote_forecast_residual(question_type, opening_prefetch):
        return context
    return promote_forecast_residual(context)


__all__ = [
    "apply_mode_promotion",
    "maybe_promote_forecast_residual",
    "promote_forecast_residual",
]
