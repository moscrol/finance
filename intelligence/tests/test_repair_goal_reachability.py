"""修复目标可达性：不可能的目标不该空转。离线锁。

生产实锤 run_20260821_114642_385979：修复轮被要求补两个 evidence 口径的
必填格（direct_assessment / counterpoint），同时 remaining_calls=0、
reopen_tools=false——禁止取证。空转 40 秒后残稿发布。

三筛（harness-reference/PLAYBOOK.md）：该限制拦修复者的取证能力，
失效时答案残缺（变笨），且模型越强越挡路（它本可以取证补齐）。
本刀不放宽限制、不加预算，只把「不可能」显式化。
"""

from __future__ import annotations

from intelligence.services.repair_coordinator import (
    CoverageDelta,
    RepairGoal,
    unreachable_repair_goal,
)

EVIDENCE_IDS = frozenset({"direct_assessment", "counterpoint", "chain_mapping"})


def _goal(**kw) -> RepairGoal:
    base = dict(
        episode_id="run_x",
        repair_goal_id="repair-run_x-1-abc",
        cycle=1,
        missing_answer_elements=("direct_assessment", "counterpoint"),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=(),
        evidence_progress=CoverageDelta(new_evidence=0, narrowed_gaps=0, newly_supported_outputs=0),
        remaining_calls=0,
        remaining_seconds=40.0,
    )
    base.update(kw)
    return RepairGoal(**base)


def test_evidence_slots_without_tools_are_unreachable() -> None:
    """生产那次的形状：evidence 格 + 0 次调用 + 不重开工具 = 不可能。"""

    goal = _goal()
    assert goal.reopen_tools is False
    assert unreachable_repair_goal(goal, evidence_output_ids=EVIDENCE_IDS) == (
        "direct_assessment",
        "counterpoint",
    )


def test_reopened_tools_make_the_goal_reachable() -> None:
    """允许重开取证就不算不可能——本函数不替它判会不会成功。"""

    goal = _goal(reopen_tools=True)
    assert unreachable_repair_goal(goal, evidence_output_ids=EVIDENCE_IDS) == ()


def test_remaining_calls_make_the_goal_reachable() -> None:
    """还有工具调用额度也不算不可能。"""

    goal = _goal(remaining_calls=2)
    assert unreachable_repair_goal(goal, evidence_output_ids=EVIDENCE_IDS) == ()


def test_model_reasoning_slots_are_not_unreachable() -> None:
    """前瞻假设槽本来就不需要新证据，不得被判成不可能。

    误判它会让所有前瞻题的修复被跳过——那是把保下限做成了封上限。
    """

    goal = _goal(missing_answer_elements=("scenario_paths",))
    assert unreachable_repair_goal(goal, evidence_output_ids=EVIDENCE_IDS) == ()


def test_no_missing_elements_is_not_unreachable() -> None:
    goal = _goal(missing_answer_elements=())
    assert unreachable_repair_goal(goal, evidence_output_ids=EVIDENCE_IDS) == ()
