"""V6 deadline 预算分臂 harness：读数口径 + 预注册判据 + 影子安装。

不打 8792，不造 live。缺字段必须报不可判，把缺席当 0 就是假绿。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.v6_deadline_budget_ab import (  # noqa: E402
    CANDIDATE1_PLANNING_FLOOR,
    PRODUCTION_PLANNING_FLOOR,
    aggregate_arm,
    answer_looks_degraded,
    compare_arms,
    inspect_episode,
    install_candidate1_shadow,
    restore_planning_floor,
)


def _episode(**overrides: object) -> dict:
    base: dict = {
        "outcome": {"draft": "x" * 100},
        "semantic_verifier": {"judge_status": "repaired"},
        "events": [
            {"kind": "tool_request", "payload": {}},
            {"kind": "tool_result", "payload": {}},
            {"kind": "model_turn", "payload": {"timeout_asked": 17.8}},
            {
                "kind": "finish",
                "payload": {
                    "stop_reason": "deadline_exhausted",
                    "carried_draft_chars": 0,
                },
            },
            {"kind": "repair_reentry", "payload": {"timeout_asked": 40.0}},
        ],
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged = dict(base[key])
            merged.update(value)
            base[key] = merged
        else:
            base[key] = value
    return base


def test_r10_shape_is_deadline_exhausted_carried_zero_with_repair() -> None:
    metrics = inspect_episode(_episode())
    assert metrics["reached_episode"] is True
    assert metrics["stop_reason"] == "deadline_exhausted"
    assert metrics["model_finish"] is False
    assert metrics["carried_positive"] is False
    assert metrics["used_repair"] is True
    assert metrics["answer_chars"] == 100
    assert metrics["judge_status"] == "repaired"


def test_model_finish_without_repair() -> None:
    metrics = inspect_episode(
        _episode(
            events=[
                {"kind": "tool_request", "payload": {}},
                {"kind": "tool_result", "payload": {}},
                {"kind": "model_turn", "payload": {}},
                {
                    "kind": "finish",
                    "payload": {
                        "stop_reason": "model_finish",
                        "carried_draft_chars": 812,
                    },
                },
            ]
        )
    )
    assert metrics["model_finish"] is True
    assert metrics["carried_positive"] is True
    assert metrics["used_repair"] is False


def test_missing_finish_is_unjudgeable_not_zero() -> None:
    metrics = inspect_episode(
        {
            "outcome": {},
            "semantic_verifier": {},
            "events": [{"kind": "prefetch", "payload": {}}],
        }
    )
    assert metrics["stop_reason_status"] == "unjudgeable"
    assert metrics["model_finish"] is None
    assert metrics["carried_status"] == "unjudgeable"
    assert metrics["carried_positive"] is None
    assert metrics["answer_status"] == "unjudgeable"
    assert metrics["judge_status_status"] == "unjudgeable"
    assert metrics["reached_episode"] is False


def test_prefetch_only_finalize_still_reaches_episode() -> None:
    """候选①可能零 tool_request：有 model_turn + finish 就算走到 episode。"""

    metrics = inspect_episode(
        {
            "outcome": {"draft": "短稿"},
            "semantic_verifier": {"judge_status": "passed"},
            "events": [
                {"kind": "prefetch", "payload": {}},
                {"kind": "model_turn", "payload": {}},
                {
                    "kind": "finish",
                    "payload": {
                        "stop_reason": "deadline_exhausted",
                        "carried_draft_chars": 355,
                    },
                },
            ],
        }
    )
    assert metrics["reached_episode"] is True
    assert metrics["tool_events"] == 0
    assert metrics["model_turns"] == 1
    assert metrics["carried_positive"] is True


def test_none_episode_is_not_reached() -> None:
    metrics = inspect_episode(None)
    assert metrics["reached_episode"] is False
    assert metrics["stop_reason_status"] == "unjudgeable"
    assert metrics["model_finish"] is None


def test_r1_urlerror_template_is_degraded() -> None:
    text = (
        "Grounded Presenter自然语言合成未通过门禁或不可用"
        "（LLM 合成失败（URLError），已降级为模板）"
    )
    assert answer_looks_degraded(text) is True
    assert answer_looks_degraded("CXO概念处于发酵期，依据本地主线数据。") is False


def test_compare_arms_refuses_n_below_fifty() -> None:
    control = aggregate_arm(
        [{"model_finish": True, "repair_status": "ok", "used_repair": False}]
        * 12
    )
    candidate = aggregate_arm(
        [{"model_finish": True, "repair_status": "ok", "used_repair": False}]
        * 12
    )
    verdict = compare_arms(control, candidate)
    assert verdict["verdict"] == "进行中/未达标样本量"
    assert "n≥50" in verdict["reason"]


def test_compare_arms_pass_when_lift_and_length_hold() -> None:
    control = aggregate_arm(
        [
            {
                "model_finish": False,
                "repair_status": "ok",
                "used_repair": True,
                "answer_chars": 800,
            }
        ]
        * 50
    )
    candidate = aggregate_arm(
        [
            {
                "model_finish": True,
                "repair_status": "ok",
                "used_repair": False,
                "answer_chars": 900,
            }
        ]
        * 40
        + [
            {
                "model_finish": False,
                "repair_status": "ok",
                "used_repair": True,
                "answer_chars": 900,
            }
        ]
        * 10
    )
    verdict = compare_arms(control, candidate)
    assert control["model_finish_rate"] == 0.0
    assert candidate["model_finish_rate"] == 0.8
    assert verdict["verdict"] == "达标"
    assert verdict["model_finish_lift_pp"] == pytest.approx(80.0)


def test_compare_arms_fail_when_length_drops() -> None:
    control = aggregate_arm(
        [{"model_finish": False, "answer_chars": 1000}] * 50
    )
    candidate = aggregate_arm(
        [{"model_finish": True, "answer_chars": 200}] * 50
    )
    verdict = compare_arms(control, candidate)
    assert verdict["verdict"] == "未达标"
    assert "答案长度下降" in verdict["reason"]


def test_aggregate_does_not_count_unjudgeable_as_zero_rate() -> None:
    rows = [
        {"model_finish": None, "carried_positive": None, "repair_status": "unjudgeable"},
        {"model_finish": True, "carried_positive": True, "repair_status": "ok", "used_repair": False},
    ]
    summary = aggregate_arm(rows)
    assert summary["n"] == 2
    assert summary["n_model_finish_judgeable"] == 1
    assert summary["model_finish_rate"] == 1.0


def test_candidate1_shadow_raises_planning_floor_and_restores() -> None:
    from intelligence.runtime import agent_episode as episode_mod

    assert episode_mod.MIN_PLANNING_TURN_SECONDS == PRODUCTION_PLANNING_FLOOR
    previous = install_candidate1_shadow()
    try:
        assert previous == PRODUCTION_PLANNING_FLOOR
        assert episode_mod.MIN_PLANNING_TURN_SECONDS == CANDIDATE1_PLANNING_FLOOR
    finally:
        restore_planning_floor(previous)
    assert episode_mod.MIN_PLANNING_TURN_SECONDS == PRODUCTION_PLANNING_FLOOR
