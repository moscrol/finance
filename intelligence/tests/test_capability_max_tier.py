"""「能力 max」档与三个部署开关（用户 2026-09-06 决策：先找能力上限，再按超限加约束）。

09-06 生产探针（``run_20260906_235449_478128``，sol@57244，standard 档）的形状是本文件
每条测试的出处：sol 首轮一次点 6 个工具，``MAX_BATCH_TOOL_CALLS=4`` 把 2 个打成
``tool_budget_exhausted``；第二轮 ``web_search`` 只授 8.7s 超时；第三轮 ``would_grant=0``，
模型交 ``partial``、四条 gap 全是「缺公告 / 缺新闻 / 缺一手复核」——它知道该查什么，是不让查。

本文件钉四件事，每件都有「关掉开关就回到旧形状」的对照，不是同义反复：

1. ``max`` 档：40 步 / 600s / reserve 60，账本硬顶 60 / 600，契约认这个档位（09-07 二改：分支读数后 32/48 → 40/60）。
2. 起步在 max 的 run，PLAN 批 deep 时账本动作是空操作——否则 600s 会被「升」成 240s。
3. ``WORKBENCH_TOOL_AUTHORIZATION=all``：要检索的题拿全部工具；不要检索的题仍是空授权。
4. ``WORKBENCH_TOOL_MENU_HIDE=off``：不再按 ``min_window_seconds`` 藏工具；每批帽在 max 档抬到 8。

出口硬层（``admit_finish`` / 判官 / 来源分档）不在本文件——它们一字未动，由既有测试守着。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest

from intelligence.api import app
from intelligence.runtime import episode_tool_batch
from intelligence.runtime.agent_episode import MAX_EPISODE_TOOL_CALLS
from intelligence.runtime.episode_tool_batch import (
    MAX_BATCH_TOOL_CALLS,
    MAX_GLOBAL_TOOL_WORKERS,
    TOOL_MENU_HIDE_ENV,
    ToolBatchExecutor,
    batch_call_cap,
)
from intelligence.runtime.tier_promotion import (
    apply_mode_promotion,
    promote_forecast_residual,
)
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.evidence_capabilities import (
    TOOL_AUTHORIZATION_ENV,
    _RUNTIME_CAPABILITY_FLOOR,
    runtime_capabilities_for_frame,
)
from intelligence.services.mode_governor import ModeDecision
from intelligence.services.repair_coordinator import max_repair_cycles_for_tier
from intelligence.services.research_contract import (
    PRODUCT_MAX_SECONDS,
    PRODUCT_MAX_TOOL_CALLS,
    RESEARCH_TIERS,
    InformationCutoff,
    ResearchContractError,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
    release_root_budget,
    root_budget_for_policy,
)
from intelligence.services.research_tool_registry import (
    DEFAULT_RESEARCH_CAPABILITIES,
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame, task_frame_requires_retrieval


# ---------------------------------------------------------------------------
# 1. max 档本体
# ---------------------------------------------------------------------------


def test_max_tier_policy_ledger_and_contract_agree() -> None:
    policy = ResearchPolicy.for_tier("max")
    assert (policy.tier, policy.max_steps, policy.total_seconds, policy.synthesis_reserve) == (
        "max",
        40,
        PRODUCT_MAX_SECONDS,
        60.0,
    )
    # 既有三档一个数字不变：max 是加一档，不是改 deep。
    deep = ResearchPolicy.for_tier("deep")
    assert (deep.max_steps, deep.total_seconds, deep.synthesis_reserve) == (12, 240.0, 48.0)
    assert ResearchPolicy.for_tier("standard").total_seconds == 90.0

    episode_id = f"max-tier-{uuid4().hex[:12]}"
    ledger = root_budget_for_policy(policy, episode_id=episode_id)
    try:
        assert ledger.initial_calls == 40
        assert ledger.hard_calls_cap == PRODUCT_MAX_TOOL_CALLS == 60
        assert ledger.initial_seconds == 540.0
        assert ledger.hard_seconds_cap == PRODUCT_MAX_SECONDS == 600.0
    finally:
        release_root_budget(episode_id)

    assert "max" in RESEARCH_TIERS
    assert max_repair_cycles_for_tier("max") == max_repair_cycles_for_tier("deep") == 3
    # loop 侧的回合上限跟产品硬顶走，不然 48 的账本在这里被静默剪回 24。
    assert MAX_EPISODE_TOOL_CALLS == PRODUCT_MAX_TOOL_CALLS


def _contract(*, research_tier: str, task_id: str) -> ResearchTaskContract:
    return ResearchTaskContract(
        task_id=task_id,
        question="长电科技怎么看",
        subject="长电科技",
        subject_kind="company",
        question_type="stock_deep_dive",
        required_outputs=(),
        allowed_capabilities=("finance_query", "kb_search"),
        research_tier=research_tier,
    )


def test_contract_accepts_max_and_still_rejects_unknown_tiers() -> None:
    _contract(research_tier="max", task_id="contract-max")
    with pytest.raises(ResearchContractError, match="未知研究档位"):
        _contract(research_tier="unbounded", task_id="contract-unbounded")


# ---------------------------------------------------------------------------
# 2. 起步在 max 时，「升 deep」不能变成降档
# ---------------------------------------------------------------------------


def _context_for(tier: str) -> ResearchRunContext:
    policy = ResearchPolicy.for_tier(tier)
    episode_id = f"{tier}-promotion-{uuid4().hex[:12]}"
    return ResearchRunContext(
        contract=_contract(research_tier=tier, task_id=episode_id),
        deadline=ResearchDeadline.from_timeout(
            policy.total_seconds, synthesis_reserve=policy.synthesis_reserve
        ),
        policy=policy,
        trace_parent_id=episode_id,
        information_cutoff=InformationCutoff(date(2026, 9, 6), "requested"),
        root_budget=root_budget_for_policy(policy, episode_id=episode_id),
    )


def _approved_deep() -> ModeDecision:
    return ModeDecision(
        requested_mode="deep",
        effective_mode="deep",
        approved=True,
        reason="observable_complexity_approved",
        observable_conditions=("multiple_evidence_domains",),
        research_tier="deep",
        tool_call_cap=24,
        target_seconds=240.0,
        max_repair_cycles=3,
        max_branches=3,
    )


def test_deep_decision_on_a_max_run_is_a_ledger_no_op() -> None:
    context = _context_for("max")
    root = context.root_budget
    assert root is not None
    try:
        promoted = apply_mode_promotion(context, _approved_deep())
        assert promoted is context
        assert promoted.policy.tier == "max"
        assert promoted.policy.total_seconds == 600.0 and promoted.policy.max_steps == 40
        assert root.hard_calls_cap == 60 and root.hard_seconds_cap == 600.0
        assert root.allocated_calls == 40
    finally:
        release_root_budget(context.contract.task_id)


def test_deep_decision_on_a_standard_run_still_promotes() -> None:
    """对照：同一个裁决在 standard 起步的 run 上仍然升——空操作只针对已在 deep 之上的。"""

    context = _context_for("standard")
    try:
        promoted = apply_mode_promotion(context, _approved_deep())
        assert promoted is not context
        assert promoted.policy.tier == "deep"
        assert context.root_budget is not None
        assert context.root_budget.hard_calls_cap == 24
    finally:
        release_root_budget(context.contract.task_id)


def test_forecast_residual_promotion_leaves_a_max_run_alone() -> None:
    context = _context_for("max")
    try:
        assert promote_forecast_residual(context) is context
    finally:
        release_root_budget(context.contract.task_id)


# ---------------------------------------------------------------------------
# 3. 起步档位与全工具授权两个 env 门
# ---------------------------------------------------------------------------


def test_research_tier_env_defaults_to_standard_and_only_accepts_known_tiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(app._RESEARCH_TIER_ENV, raising=False)
    assert app._research_tier_from_env() == "standard"
    monkeypatch.setenv(app._RESEARCH_TIER_ENV, "max")
    assert app._research_tier_from_env() == "max"
    monkeypatch.setenv(app._RESEARCH_TIER_ENV, " DEEP ")
    assert app._research_tier_from_env() == "deep"
    # 拼错的 env 回落 standard，不抛也不静默放大。
    monkeypatch.setenv(app._RESEARCH_TIER_ENV, "unbounded")
    assert app._research_tier_from_env() == "standard"


def _deep_dive_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="长电科技怎么看",
        user_goal="判断一家公司的基本面与近期变化",
        question_type="stock_deep_dive",
        subject="长电科技",
        subject_kind="company",
        market_scope="A股",
        timeframe=None,
        required_outputs=("direct_assessment", "supporting_evidence"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_multi_layer_evidence",
        confidence=0.9,
    )


def _method_frame() -> TaskFrame:
    """不需要检索的题：evidence_policy=model_reasoning（task_frame_requires_retrieval 判 False），
    question_type=methodology_discussion（episode_factory._is_evidence_free_task 清空授权）。"""

    return TaskFrame(
        raw_question="应该如何判断一个题材处于发酵期还是退潮期",
        user_goal="讨论判读方法",
        question_type="methodology_discussion",
        subject=None,
        subject_kind=None,
        market_scope=None,
        timeframe=None,
        required_outputs=("method",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="model_reasoning",
        confidence=0.9,
    )


def test_all_tools_env_authorizes_the_whole_registry_for_retrieval_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _deep_dive_frame()
    assert task_frame_requires_retrieval(frame) is True

    monkeypatch.delenv(TOOL_AUTHORIZATION_ENV, raising=False)
    strategy_floor = runtime_capabilities_for_frame(frame)
    assert set(strategy_floor) >= set(_RUNTIME_CAPABILITY_FLOOR["company_multi_layer_evidence"])
    assert set(strategy_floor) < set(DEFAULT_RESEARCH_CAPABILITIES)

    monkeypatch.setenv(TOOL_AUTHORIZATION_ENV, "all")
    assert runtime_capabilities_for_frame(frame) == tuple(DEFAULT_RESEARCH_CAPABILITIES)

    # 除 all 之外的值不是别名，仍走策略表。
    monkeypatch.setenv(TOOL_AUTHORIZATION_ENV, "everything")
    assert runtime_capabilities_for_frame(frame) == strategy_floor


def test_all_tools_env_does_not_leak_market_tools_into_method_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """方法论题的空授权是防泄漏的正确性规则，不是预算规则，不随开关放开。"""

    frame = _method_frame()
    assert task_frame_requires_retrieval(frame) is False
    monkeypatch.setenv(TOOL_AUTHORIZATION_ENV, "all")
    # 第一层：投影函数对不需要检索的题仍给空。
    assert runtime_capabilities_for_frame(frame) == ()
    # 第二层：组装成契约后授权也是空——即便调用方硬塞了一份能力名单。
    context = build_episode_context(
        frame,
        task_id=f"method-{uuid4().hex[:8]}",
        capabilities=tuple(DEFAULT_RESEARCH_CAPABILITIES),
        today="2026-09-06",
    )
    assert context.contract.allowed_capabilities == ()


def test_llm_call_fuse_scales_with_the_deployment_tier_without_touching_the_rest_of_the_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """09-07 04:11 读数：max 形状 + 两次 sub_research（5 支分支 28 次模型调用）烧穿 40 的保险丝，
    最后被拒的是判官 → judge unavailable、答案降级。max 档 120；其它档与 profile 其余字段不变。"""

    from intelligence.services.research_contract import (
        DEFAULT_LLM_CALL_FUSE,
        llm_call_fuse_for_tier,
    )

    assert llm_call_fuse_for_tier("max") == 120
    for tier in ("quick", "standard", "deep", None, "bogus"):
        assert llm_call_fuse_for_tier(tier) == DEFAULT_LLM_CALL_FUSE == 40

    monkeypatch.delenv(app._RESEARCH_TIER_ENV, raising=False)
    baseline = app._deployment_execution_policy()
    assert baseline.max_llm_calls == 40
    monkeypatch.setenv(app._RESEARCH_TIER_ENV, "max")
    maximal = app._deployment_execution_policy()
    assert maximal.max_llm_calls == 120
    # 只抬保险丝：墙钟、合成保留、grounded profile 一个不动。
    assert (maximal.max_elapsed_seconds, maximal.synthesis_reserve_seconds) == (
        baseline.max_elapsed_seconds,
        baseline.synthesis_reserve_seconds,
    )
    assert maximal.grounded_budget_profile == baseline.grounded_budget_profile


# ---------------------------------------------------------------------------
# 4. 菜单不藏 + 每批帽
# ---------------------------------------------------------------------------


def _evidence_result(name: str, query: str):  # pragma: no cover - runner never invoked
    raise AssertionError(f"{name} should not run in a menu test ({query})")


def _menu_registry() -> ResearchToolRegistry:
    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="fast local snapshot",
                cost="local",
                freshness="current",
                runner=_evidence_result,
            ),
            ToolSpec(
                name="kb_search",
                capability="kb_search",
                description="rag search",
                cost="local",
                freshness="stable",
                runner=_evidence_result,
                min_window_seconds=20.0,
            ),
        )
    )


def _narrow_window_context() -> ResearchRunContext:
    """总窗 30 / reserve 15 → 本轮工具窗 15s，小于 kb_search 申报的 20s。"""

    base = _context_for("standard")
    release_root_budget(base.contract.task_id)
    return replace(
        base,
        contract=replace(base.contract, allowed_capabilities=("market_data", "kb_search")),
        deadline=ResearchDeadline.from_timeout(30.0, synthesis_reserve=15.0),
        policy=ResearchPolicy("quick", 4, 30.0, 15.0),
        root_budget=None,
    )


def test_menu_hide_env_off_shows_every_authorized_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _narrow_window_context()
    session = ToolBatchExecutor().new_session()

    monkeypatch.delenv(TOOL_MENU_HIDE_ENV, raising=False)
    default_menu = session.menu(registry=_menu_registry(), context=context)
    assert default_menu.hidden == (("kb_search", 20.0),)

    monkeypatch.setenv(TOOL_MENU_HIDE_ENV, "off")
    open_menu = session.menu(registry=_menu_registry(), context=context)
    assert open_menu.visible == ("kb_search", "market_data")
    assert open_menu.hidden == ()
    # 关的只是可见性裁决；would_grant 这条算术不变。
    assert abs(open_menu.would_grant - default_menu.would_grant) < 0.05


def test_batch_call_cap_is_eight_only_for_max_tier() -> None:
    assert batch_call_cap(None) == MAX_BATCH_TOOL_CALLS == 4
    for tier in ("quick", "standard", "deep"):
        assert batch_call_cap(ResearchPolicy.for_tier(tier)) == MAX_BATCH_TOOL_CALLS
    assert batch_call_cap(ResearchPolicy.for_tier("max")) == MAX_GLOBAL_TOOL_WORKERS == 8


def test_select_honours_the_per_batch_cap() -> None:
    """09-06 探针：6 个候选、standard 帽 4 → 2 个 tool_budget_exhausted；max 帽 8 → 6 个全派。"""

    candidates = [object() for _ in range(6)]
    select = episode_tool_batch.EpisodeToolBatchSession._select
    assert len(select(candidates, remaining_slots=32)) == 4  # type: ignore[arg-type]
    assert len(select(candidates, remaining_slots=32, per_batch_cap=8)) == 6  # type: ignore[arg-type]
    # 剩余槛仍是上界：帽再大也不能超账本。
    assert len(select(candidates, remaining_slots=3, per_batch_cap=8)) == 3  # type: ignore[arg-type]
