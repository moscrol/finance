"""P1 展望残差预算：座位对且开口包齐才升 deep；连打同问句停机。"""

from __future__ import annotations

from intelligence.runtime.continuous_turn_adapter import (
    ContinuousTurnAdapter,
    DETERMINISTIC_OWNER_TYPES,
)
from intelligence.runtime.turn_control_core import TurnControlResult
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.task_frame import TaskFrame
from intelligence.runtime.tier_promotion import maybe_promote_forecast_residual
from intelligence.services.forecast_residual_budget import (
    DO_NOT_LENGTHEN_QUESTION_TYPES,
    forecast_opening_pack_ready,
    forecast_residual_halt_reason,
    should_promote_forecast_residual,
)
from intelligence.services.repair_coordinator import max_repair_cycles_for_tier
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
    RequiredOutput,
    root_budget_for_policy,
)
from datetime import date
from uuid import uuid4


def _pack_item() -> AgentEvidence:
    return AgentEvidence(
        tool="market_data",
        title="2026-08-20 四袋",
        detail="主线 创新药",
        source="weekly_watch_pack",
        source_date="2026-08-20",
        content_hash="week-pack-hash",
    )


def _old_dual_red_item() -> AgentEvidence:
    return AgentEvidence(
        tool="market_data",
        title="近3日双红个数",
        detail="75 / 21 / 0",
        source="asof_prefetch",
        content_hash="old-dual-red",
    )


def _standard_context(*, task_id: str) -> ResearchRunContext:
    policy = ResearchPolicy.for_tier("standard")
    contract = ResearchTaskContract(
        task_id=task_id,
        question="写一下本周行情的展望",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_forecast",
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "针对预测窗口的直接判断",
                ("market_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data",),
        research_tier="standard",
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(
            policy.total_seconds,
            synthesis_reserve=policy.synthesis_reserve,
        ),
        policy=policy,
        trace_parent_id=task_id,
        information_cutoff=InformationCutoff(date(2026, 8, 24), "requested"),
        root_budget=root_budget_for_policy(policy, episode_id=task_id),
    )


def test_quick_tier_bytes_stay_frozen() -> None:
    quick = ResearchPolicy.for_tier("quick")
    assert (quick.tier, quick.max_steps, quick.total_seconds, quick.synthesis_reserve) == (
        "quick",
        3,
        30.0,
        20.0,
    )
    assert max_repair_cycles_for_tier("quick") == 1


def test_do_not_lengthen_matches_deterministic_owner_set() -> None:
    assert DO_NOT_LENGTHEN_QUESTION_TYPES == DETERMINISTIC_OWNER_TYPES


def test_opening_pack_ready_requires_weekly_bag_not_old_dual_red() -> None:
    assert forecast_opening_pack_ready((_pack_item(),)) is True
    assert forecast_opening_pack_ready(
        (
            AgentEvidence(
                tool="market_data",
                title="先验周量能序列",
                detail="量比 81.19",
                source="weekly_watch_pack",
                content_hash="energy",
            ),
        )
    ) is True
    assert forecast_opening_pack_ready(
        (
            AgentEvidence(
                tool="market_data",
                title="先验周盘面",
                detail="status=locked 复盘写入中，请稍后",
                source="weekly_watch_pack",
                content_hash="locked",
            ),
        )
    ) is True
    assert forecast_opening_pack_ready((_old_dual_red_item(),)) is False
    assert forecast_opening_pack_ready(()) is False


def test_promote_only_when_seat_and_opening_ready() -> None:
    assert should_promote_forecast_residual("market_forecast", (_pack_item(),)) is True
    assert should_promote_forecast_residual("market_forecast", ()) is False
    assert should_promote_forecast_residual(
        "market_forecast",
        (_old_dual_red_item(),),
    ) is False
    assert should_promote_forecast_residual(
        "general_finance_qa",
        (_pack_item(),),
    ) is False
    for question_type in sorted(DO_NOT_LENGTHEN_QUESTION_TYPES):
        assert should_promote_forecast_residual(question_type, (_pack_item(),)) is False


def test_promote_applies_deep_pair_not_three_knobs() -> None:
    context = _standard_context(task_id=f"forecast-residual-promote-{uuid4().hex}")
    promoted = maybe_promote_forecast_residual(
        context,
        question_type="market_forecast",
        opening_prefetch=(_pack_item(),),
    )
    deep = ResearchPolicy.for_tier("deep")
    assert promoted.policy == deep
    assert promoted.contract.research_tier == "deep"
    assert (promoted.policy.max_steps, promoted.policy.total_seconds) == (12, 240.0)
    assert promoted.deadline.remaining() > 1.0
    unchanged = maybe_promote_forecast_residual(
        context,
        question_type="market_watch",
        opening_prefetch=(_pack_item(),),
    )
    assert unchanged.policy.tier == "standard"
    assert unchanged.policy.max_steps == 6
    assert unchanged.policy.total_seconds == 90.0


def test_halt_only_on_deep_forecast_duplicate_spin() -> None:
    assert (
        forecast_residual_halt_reason(
            question_type="market_forecast",
            research_tier="deep",
            batch_errors=("duplicate_query",),
        )
        == "forecast_residual_duplicate_spin"
    )
    assert (
        forecast_residual_halt_reason(
            question_type="market_forecast",
            research_tier="standard",
            batch_errors=("duplicate_query",),
        )
        is None
    )
    assert (
        forecast_residual_halt_reason(
            question_type="theme_analysis",
            research_tier="deep",
            batch_errors=("duplicate_query",),
        )
        is None
    )
    assert (
        forecast_residual_halt_reason(
            question_type="market_forecast",
            research_tier="deep",
            batch_errors=("tool_timeout",),
        )
        is None
    )


def test_standard_context_without_pack_is_byte_stable() -> None:
    context = _standard_context(task_id=f"forecast-residual-no-pack-{uuid4().hex}")
    same = maybe_promote_forecast_residual(
        context,
        question_type="market_forecast",
        opening_prefetch=(),
    )
    assert same is context
    assert same.policy == ResearchPolicy.for_tier("standard")


def _forecast_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="写一下本周行情的展望",
        user_goal="判断本周行情",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="本周",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def test_adapter_promotes_only_after_opening_pack() -> None:
    frame = _forecast_frame()
    control = TurnControlResult(
        task_frame=frame,
        execution_route=frame.question_type,
        terminal_kind="research",
        needs_retrieval=True,
        capabilities=("market_data",),
        contract_required=True,
    )
    captured: dict[str, object] = {}

    class Registry:
        opening_prefetch = (_pack_item(),)

    class Runtime:
        def run(self, *, task_frame, context, registry):
            del task_frame, registry
            captured["tier"] = context.policy.tier
            captured["steps"] = context.policy.max_steps
            captured["seconds"] = context.policy.total_seconds
            captured["remaining"] = context.deadline.remaining()
            return AgentOutcome(
                task_frame_hash=frame.task_frame_hash,
                status="completed",
                draft="本周缩量，主线仍在药。",
                evidence=(),
                traces=(),
                gaps=(),
                stop_reason="model_finish",
                events=(
                    EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
                ),
                bindings=(),
                usage=AgentUsage(llm_calls=1, tool_calls=0),
            )

    class Semantic:
        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer="本周缩量，主线仍在药。",
                judge_status="passed",
            )

    ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=build_episode_context,
        registry_factory=lambda *_args, **_kwargs: Registry(),
        timeout=90.0,
    ).handle(frame=frame, control=control)

    assert captured["tier"] == "deep"
    assert captured["steps"] == 12
    assert captured["seconds"] == 240.0
    assert float(captured["remaining"]) > 1.0

    empty_captured: dict[str, object] = {}

    class EmptyRegistry:
        opening_prefetch = ()

    class EmptyRuntime:
        def run(self, *, task_frame, context, registry):
            del task_frame, registry
            empty_captured["tier"] = context.policy.tier
            empty_captured["steps"] = context.policy.max_steps
            return AgentOutcome(
                task_frame_hash=frame.task_frame_hash,
                status="completed",
                draft="缺口。",
                evidence=(),
                traces=(),
                gaps=(),
                stop_reason="model_finish",
                events=(
                    EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
                ),
                bindings=(),
                usage=AgentUsage(llm_calls=1, tool_calls=0),
            )

    ContinuousTurnAdapter(
        runtime=EmptyRuntime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=build_episode_context,
        registry_factory=lambda *_args, **_kwargs: EmptyRegistry(),
        timeout=90.0,
    ).handle(frame=frame, control=control)

    assert empty_captured["tier"] == "standard"
    assert empty_captured["steps"] == 6
