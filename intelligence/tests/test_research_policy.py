from __future__ import annotations

from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_policy import (
    ResearchExecutionBudget,
    ResearchExecutionPolicy,
)


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
