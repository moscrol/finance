from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from intelligence.services.task_frame import TaskFrame
from intelligence.services.user_task import ResolvedValue, UserTask


def _frame(*, subject: str | None = None) -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场的主线是什么？",
        user_goal="判断当前市场主线",
        question_type="market_watch",
        subject=subject,
        subject_kind="theme" if subject else "unknown",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("用户未明确市场范围，按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_a_share_market",
        confidence=0.9,
    )


def test_user_task_preserves_raw_question_and_resolution_provenance() -> None:
    question = "  目前市场的主线是什么？  "
    task = UserTask(
        raw_question=question,
        conversation_context="  上一轮在讨论市场风格。  ",
        subjects=(),
        market_scope=ResolvedValue(" A股 ", "product_default"),
        time_window=None,
        assumptions=(" 按A股市场理解 ", "按A股市场理解"),
        ambiguities=(),
        user_premises=(),
        task_id=" task-1 ",
    )

    assert task.raw_question == question
    assert task.market_scope == ResolvedValue("A股", "product_default")
    assert task.assumptions == ("按A股市场理解",)
    assert task.to_dict()["task_id"] == "task-1"
    with pytest.raises(FrozenInstanceError):
        task.task_id = "changed"  # type: ignore[misc]


def test_from_task_frame_marks_a_share_default_without_inventing_subject() -> None:
    task = UserTask.from_task_frame(
        _frame(subject=None),
        {
            "conversation_context": "延续上一轮",
            "task_id": "turn-1",
            "time_window_source": "inferred",
        },
    )

    assert task.raw_question == "目前市场的主线是什么？"
    assert task.subjects == ()
    assert task.market_scope == ResolvedValue("A股", "product_default")
    assert task.time_window == {
        "value": "最近交易日",
        "source": "inferred",
    }


def test_task_frame_exposes_compatibility_projection() -> None:
    task = _frame(subject="液冷").to_user_task({"task_id": "compat-1"})

    assert isinstance(task, UserTask)
    assert task.task_id == "compat-1"
    assert task.subjects[0].value == "液冷"
    assert get_type_hints(TaskFrame.to_user_task)["return"] is UserTask


def test_user_task_rejects_unknown_resolution_source() -> None:
    with pytest.raises(ValueError, match="resolution source"):
        ResolvedValue("A股", "guessed")


def test_user_task_rejects_non_json_safe_time_window() -> None:
    with pytest.raises(ValueError, match="JSON-safe"):
        UserTask(
            raw_question="市场怎么看",
            conversation_context="",
            subjects=(),
            market_scope=None,
            time_window={"anchor": object()},
            assumptions=(),
            ambiguities=(),
            user_premises=(),
            task_id="task-unsafe",
        )
