"""路由组合一致性对账门禁（R-20260828-08）。

背景：R-20260828-05（F1）的事故形状是几张以 question_type 为键的手写名单
组合矛盾——quick_fact 被 ``DETERMINISTIC_OWNER_TYPES`` 拒进 episode、
episode 侧 ``_FAST_PATH_TYPES`` 却仍把它划给评测确定性臂、回落的 legacy
合同又没有 finance_query。每张名单各自「看起来对」，组合起来是静默死路，
而且没有任何门禁能看见这种矛盾。

本文件把名单之间的关系钉成机器检查（与 test_forecast_residual_budget 里
``DO_NOT_LENGTHEN_QUESTION_TYPES == DETERMINISTIC_OWNER_TYPES`` 的既有
「跨层不 import、用等式测试钉」手法同族，推广到全部 question_type 名单）：

- 成员合法性：任何名单出现表外题型 = 拼写漂移或僵尸成员，立刻红；
- 拒接/快路径互斥：``handle`` 先拒接后快路径，交集 = 快路径死码；
- 评测臂 ⊆ 生产非 episode 集：F1 型「生产改了、评测臂没跟上」在此红；
- 快路径名单 == runner 支持集：「名单说可以、执行者说不认识」在此红；
- episode 合同标配 finance_query / evidence_search：F1 修复靠这条生效
  （quick_fact 进 episode 自然获得 finance_query），防回退。

已知偏差（本门禁不掩盖，记录在案）：market_watch / watchlist_digest /
disclosure_scan 生产被 adapter 拒接走 legacy，但评测分臂名单未包含它们，
A/B 评测仍按 episode 臂跑——测的是生产不走的路。收敛它会改变 benchmark
基线读数，留待基线换代时处理，不在本门禁范围。
"""

from __future__ import annotations

import pytest

from intelligence.runtime.continuous_turn_adapter import (
    CONTINUOUS_FAST_PATH_TYPES,
    DETERMINISTIC_OWNER_TYPES,
)
from intelligence.services.answer_orchestrator import QUESTION_GENERAL
from intelligence.services.episode_factory import _authorized_capabilities
from intelligence.services.episode_tools import (
    FAST_PATH_RUNNER_SUPPORTED_TYPES,
    _FAST_PATH_TYPES,
)
from intelligence.services.evidence_capabilities import (
    _COMPANY_SUBJECT_QUESTION_TYPES,
)
from intelligence.services.forecast_residual_budget import (
    DO_NOT_LENGTHEN_QUESTION_TYPES,
)
from intelligence.services.route_table import ROUTE_TABLE
from intelligence.services.task_frame import _POLICY_BY_QUESTION_TYPE, TaskFrame

ROUTE_TABLE_QUESTION_TYPES = frozenset(
    row.question_type for row in ROUTE_TABLE if row.question_type is not None
)
# general_finance_qa 是 legacy 分类器的兜底题型（answer_orchestrator），
# 不在路由表里但真实存在于生产 frame。除它之外不承认任何表外题型。
KNOWN_QUESTION_TYPES = ROUTE_TABLE_QUESTION_TYPES | {QUESTION_GENERAL}

# 全仓以 question_type 为键的手写名单。新增名单必须登记到这里，
# 否则它的成员漂移没有任何检查覆盖。
_ROSTERS: dict[str, frozenset[str]] = {
    "continuous_turn_adapter.DETERMINISTIC_OWNER_TYPES": frozenset(
        DETERMINISTIC_OWNER_TYPES
    ),
    "continuous_turn_adapter.CONTINUOUS_FAST_PATH_TYPES": frozenset(
        CONTINUOUS_FAST_PATH_TYPES
    ),
    "episode_tools._FAST_PATH_TYPES": frozenset(_FAST_PATH_TYPES),
    "episode_tools.FAST_PATH_RUNNER_SUPPORTED_TYPES": frozenset(
        FAST_PATH_RUNNER_SUPPORTED_TYPES
    ),
    "forecast_residual_budget.DO_NOT_LENGTHEN_QUESTION_TYPES": frozenset(
        DO_NOT_LENGTHEN_QUESTION_TYPES
    ),
    "evidence_capabilities._COMPANY_SUBJECT_QUESTION_TYPES": frozenset(
        _COMPANY_SUBJECT_QUESTION_TYPES
    ),
    "task_frame._POLICY_BY_QUESTION_TYPE": frozenset(_POLICY_BY_QUESTION_TYPE),
}


@pytest.mark.parametrize("roster_name", sorted(_ROSTERS))
def test_question_type_rosters_stay_within_known_types(roster_name: str) -> None:
    """名单成员必须是已声明的题型：表外成员 = 拼写漂移或僵尸，直接红。"""

    unknown = _ROSTERS[roster_name] - KNOWN_QUESTION_TYPES
    assert not unknown, (
        f"{roster_name} 含未声明的 question_type：{sorted(unknown)}。"
        "要么是拼写漂移，要么该题型未在 route_table 登记——"
        "先补路由行（或确认它属于 legacy 兜底），再进名单。"
    )


def test_route_table_types_all_have_evidence_policy() -> None:
    """路由表每个题型都要有 evidence_policy 映射。

    缺映射的题型在 runtime_capabilities_for_frame 里拿不到专属
    capability floor，会静默滑进通用 fallback——F1 那种「进错路后
    工具不齐」的前半截。
    """

    missing = ROUTE_TABLE_QUESTION_TYPES - frozenset(_POLICY_BY_QUESTION_TYPE)
    assert not missing, (
        f"route_table 题型缺 evidence_policy 映射：{sorted(missing)}"
    )


def test_declined_types_and_fast_path_are_disjoint() -> None:
    """adapter.handle 先按 DETERMINISTIC_OWNER_TYPES 拒接、后判快路径。

    两张名单出现交集时，交集题型永远到不了快路径分支——快路径成死码，
    而两张名单各自看都「没错」。
    """

    overlap = frozenset(DETERMINISTIC_OWNER_TYPES) & frozenset(
        CONTINUOUS_FAST_PATH_TYPES
    )
    assert not overlap, (
        f"以下题型同时被拒接名单与快路径名单认领：{sorted(overlap)}；"
        "拒接优先，快路径分支不可达。"
    )


def test_eval_arm_roster_is_subset_of_non_episode_types() -> None:
    """评测确定性臂只能包含生产不进 episode 的题型（F1 型漂移门禁）。

    生产不进 episode = 被 adapter 拒接（DETERMINISTIC_OWNER_TYPES）或走
    episode 前快路径（CONTINUOUS_FAST_PATH_TYPES）。把生产会送进 episode
    的题型留在评测确定性臂里，评测就在测一条生产不存在的空壳路径：
    R-20260828-05 把 quick_fact 移出拒接名单后，评测臂一度没跟上，
    quick_fact 在 A/B 里仍拿「尚未接入」占位——本断言让这种漂移当场红。
    """

    non_episode = frozenset(DETERMINISTIC_OWNER_TYPES) | frozenset(
        CONTINUOUS_FAST_PATH_TYPES
    )
    leaked = frozenset(_FAST_PATH_TYPES) - non_episode
    assert not leaked, (
        f"评测确定性臂包含生产会进 episode 的题型：{sorted(leaked)}；"
        "生产路由（拒接名单/快路径名单）变更后，评测分臂名单必须同步。"
    )


def test_fast_path_roster_is_runner_supported_set() -> None:
    """快路径名单与 runner 支持集必须是同一个对象/同一集合。

    ``run_deterministic_fast_path`` 对支持集之外的题型返回「尚未接入」
    partial；名单比支持集大时，多出来的题型拿到的是静默空壳而不是答案。
    """

    assert frozenset(CONTINUOUS_FAST_PATH_TYPES) == frozenset(
        FAST_PATH_RUNNER_SUPPORTED_TYPES
    ), (
        "CONTINUOUS_FAST_PATH_TYPES 与 FAST_PATH_RUNNER_SUPPORTED_TYPES 漂移："
        "名单认领了 runner 不会执行的题型（或反之）。"
    )


def _quick_fact_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="2026-08-27 涨幅排名第三的板块是哪个",
        user_goal="取一个确定的排名事实",
        question_type="quick_fact",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="2026-08-27",
        required_outputs=("fact_value",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy=_POLICY_BY_QUESTION_TYPE["quick_fact"],
        confidence=0.95,
    )


def test_episode_contract_always_authorizes_model_owned_reads() -> None:
    """episode 合同标配 finance_query / evidence_search（F1 生效机制）。

    R-20260828-05 让 quick_fact 进 episode 的前提，是 episode 合同无条件
    并入 _MODEL_OWNED_READ_CAPABILITIES——结构化取值题到 finance_query 的
    唯一供数路径。有人给这条合并加条件或删成员时，这里先红。
    """

    capabilities = _authorized_capabilities(_quick_fact_frame(), None)
    assert "finance_query" in capabilities, (
        "quick_fact 的 episode 合同缺 finance_query——排名/过滤/区间取值"
        "将退回无结构化供数的路径（R-20260828-05 F1 的原始失败形状）。"
    )
    assert "evidence_search" in capabilities
