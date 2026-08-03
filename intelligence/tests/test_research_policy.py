from __future__ import annotations

from intelligence.services.conversation_orchestrator import _generic_research_deadline
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract
from intelligence.services.research_policy import (
    ResearchExecutionBudget,
    ResearchExecutionPolicy,
    grounded_deep,
)


def _generic_contract(tier: str) -> ResearchTaskContract:
    return ResearchTaskContract(
        task_id=f"test-{tier}",
        question="测试研究",
        subject=None,
        subject_kind=None,
        question_type="general",
        required_outputs=(
            RequiredOutput(
                output_id="direct_answer",
                description="直接回答",
                evidence_types=("kb_search",),
                required=False,
            ),
        ),
        allowed_capabilities=("kb_search",),
        research_tier=tier,
    )


def test_generic_short_tiers_keep_retrieval_window_with_grounded_root_reserve() -> None:
    root = ResearchDeadline.from_timeout(180, synthesis_reserve=100)

    quick = _generic_research_deadline(root, _generic_contract("quick"))
    standard = _generic_research_deadline(root, _generic_contract("standard"))
    deep = _generic_research_deadline(root, _generic_contract("deep"))

    assert quick.remaining() > 0
    assert quick.stage_timeout(30) >= 9
    assert standard.stage_timeout(90) >= 69
    assert deep.stage_timeout(240) >= 79
    assert deep.synthesis_reserve == 100

    default_root = ResearchDeadline.from_timeout(120, synthesis_reserve=20)
    default_deep = _generic_research_deadline(
        default_root,
        _generic_contract("deep"),
    )
    assert default_deep.synthesis_reserve == 48


def test_grounded_deep_profile_freezes_single_replay_budget_math() -> None:
    """A4 的单次冻结观测只能形成工程预算，不能冒充延迟分位数。"""

    assert grounded_deep.name == "grounded_deep"
    assert grounded_deep.root_seconds == 180
    assert grounded_deep.synthesis_reserve_seconds == 100
    assert grounded_deep.child_seconds == 115
    assert grounded_deep.composer_grant_seconds == 40
    assert grounded_deep.judge_reserve_seconds == 57
    assert grounded_deep.minimum_two_phase_entry_seconds == 97
    assert "single preregistered A4" in grounded_deep.measurement_basis
    assert "146.55s" in grounded_deep.measurement_basis
    assert "20%" in grounded_deep.measurement_basis
    assert "175.86s" in grounded_deep.measurement_basis
    assert "not p95" in grounded_deep.measurement_basis
    trace = ResearchExecutionBudget(
        ResearchExecutionPolicy(
            max_elapsed_seconds=grounded_deep.root_seconds,
            synthesis_reserve_seconds=grounded_deep.synthesis_reserve_seconds,
            grounded_budget_profile=grounded_deep,
        ),
        deadline=ResearchDeadline.from_timeout(
            grounded_deep.root_seconds,
            synthesis_reserve=grounded_deep.synthesis_reserve_seconds,
        ),
    ).to_trace()
    assert trace["synthesis_reserve_ms"] == 100_000
    assert trace["grounded_budget_profile"]["name"] == "grounded_deep"
    assert trace["grounded_budget_profile"]["child_seconds"] == 115


def test_research_budget_stops_after_configured_call_count() -> None:
    budget = ResearchExecutionBudget(
        ResearchExecutionPolicy(max_skill_calls=2, max_elapsed_seconds=60)
    )

    assert budget.can_start() is True
    budget.record(
        "first",
        input_summary="query",
        provider="registry",
        status="completed",
        elapsed_ms=10,
    )
    assert budget.can_start() is True
    budget.record(
        "second",
        input_summary="query",
        provider="registry",
        status="failed",
        elapsed_ms=20,
        failure_reason="empty",
    )

    assert budget.can_start() is False
    trace = budget.to_trace()
    assert trace["call_count"] == 2
    assert trace["attempt_count"] == 2
    assert trace["attempts"][1]["failure_reason"] == "empty"
    assert trace["max_retries_per_skill"] == 0


def test_research_budget_stops_when_elapsed_budget_is_exhausted() -> None:
    budget = ResearchExecutionBudget(
        ResearchExecutionPolicy(max_skill_calls=3, max_elapsed_seconds=0)
    )

    assert budget.can_start() is False


def test_stage_remaining_excludes_synthesis_reserve() -> None:
    """前置 skill 可用秒数必须扣掉合成保留段。

    回归：owner skill 曾用 remaining_seconds 取预算，慢/失败的 skill 会吃光
    整轮时间，让 answer_synthesis 只剩 0ms 而降级 llm_unavailable_template_answer。
    """
    budget = ResearchExecutionBudget(
        ResearchExecutionPolicy(max_skill_calls=3, max_elapsed_seconds=120),
        deadline=ResearchDeadline.from_timeout(120, synthesis_reserve=20),
    )

    assert budget.remaining_seconds > budget.stage_remaining_seconds
    gap = budget.remaining_seconds - budget.stage_remaining_seconds
    assert 19.0 <= gap <= 21.0


def test_stage_budget_is_zero_when_reserve_covers_whole_window() -> None:
    """预留段 >= 剩余窗口时，前置阶段可用秒数为 0，但仍允许启动去拿部分结果。

    钳制发生在调用处（allowed_seconds），skill 会立刻超时而非吃掉预留段。
    """
    budget = ResearchExecutionBudget(
        ResearchExecutionPolicy(max_skill_calls=3, max_elapsed_seconds=0.1),
        deadline=ResearchDeadline.from_timeout(0.1, synthesis_reserve=20),
    )

    assert budget.stage_remaining_seconds == 0
    assert budget.can_start() is True
