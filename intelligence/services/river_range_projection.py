"""区间投影正门：一个调用拿到「这一段怎么走过来的」的上下文投影（09-06 spec §4.5）。

分工：纯函数投影在 ``river_projection.project_window``（不读盘）；本模块是**取数编排**——
``window()`` → 标准派生集 → 投影。存在的理由是把一条容易漏的知识封装起来：
``window()`` 默认只挂 ``cumulative``，``transition`` / ``streak`` 要显式调 ``river_derive``；
没有正门，每个消费方都得自己知道这一点，漏了的那个消费方拿到的区间投影只有累计量、
没有「哪天变的」——恰好丢掉区间唯一要答的东西，而且不报错。

**标准派生集是确定性固定的**（回放可复算，§3「换模型能重算」）：

- ``cumulative``：``window()`` 自带（包 ``range_aggregate`` 正门，§4.4）
- ``transition:market_stage``：阶段哪天切的——事件日切片的主要来源
- ``streak:dual_red_strict`` / ``streak:volume_surge``：连续双红 / 放量的连续段

``first_event`` 不进标准集：哪轨哪类算「首现」没有无争议默认（stage 天天有，首现=第一天，
无信息量；有信息量的是稀疏对象，按问法挑），消费方需要时显式传 ``extra_derived``。
``signature`` 需要 ``build_daily_vectors`` 的逐日向量（再查一次库），同样按需显式加。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from intelligence.services import river_derive
from intelligence.services.river import RiverObject
from intelligence.services.river_projection import ContextProjection, SelectionRule, project_window
from intelligence.services.river_window_contract import RiverWindow, window

STANDARD_TRANSITION_LABELS = ("market_stage",)
STANDARD_STREAK_LABELS = ("dual_red_strict", "volume_surge")


def standard_derived(win: RiverWindow) -> tuple[RiverObject, ...]:
    """窗口自带的派生对象 + 标准派生集。顺序确定（先窗口自带，再按标签表序），回放可复算。"""
    out: list[RiverObject] = list(win.derived)
    for label in STANDARD_TRANSITION_LABELS:
        out.append(river_derive.derive_transitions(win, label))
    for label in STANDARD_STREAK_LABELS:
        out.append(river_derive.derive_streak(win, label))
    return tuple(out)


def project_range(
    start: str,
    end: str,
    entity: str,
    *,
    task: str,
    knowledge_cutoff: str | None = None,
    framework_version: str | None = None,
    budget: int | None = None,
    rules: dict[str, SelectionRule] | None = None,
    extra_derived: tuple[RiverObject, ...] = (),
    require_strict: bool = False,
    allow_hindsight: bool = False,
    db_path: str | Path | None = None,
    checkpoints_path: str | Path | None = None,
) -> ContextProjection:
    """``[start, end]`` 上 ``entity`` 的区间上下文投影（读库；纯函数部分见 ``project_window``）。

    ``extra_derived`` 追加在标准集之后（如显式派生的 ``first_event`` / ``signature``）；
    它参与投影与 ``projection_hash``，所以调用方要保证自己传的对象同样确定性可复算。
    """
    win = window(
        start,
        end,
        entity,
        knowledge_cutoff=knowledge_cutoff,
        require_strict=require_strict,
        allow_hindsight=allow_hindsight,
        db_path=db_path,
        checkpoints_path=checkpoints_path,
    )
    win = replace(win, derived=standard_derived(win) + tuple(extra_derived))
    return project_window(
        win.to_dict(),
        framework_version=framework_version,
        task=task,
        budget=budget,
        rules=rules,
    )


def projection_inputs_of(cp: ContextProjection) -> dict[str, Any]:
    """登记台账用的六元组（09-06 spec §4.5：登记 ``projection_hash`` 必须保证六元组可复原）。

    ``projection_hash`` 是单向的——重算验证需要完整输入。把这份 dict 随判断一起落台账
    （``register_checkpoint(projection_inputs=...)``），回放时 ``project_range`` 按它复算、
    比对哈希。``budget`` 里的 ``limit`` 就是当时的预算参数。
    """
    return {
        "source_ref": dict(cp.source_ref),
        "framework_version": cp.framework_version,
        "task": cp.task,
        "budget": cp.budget.get("limit"),
        "projection_version": cp.projection_version,
        "label_version": cp.label_version,
    }


__all__ = [
    "STANDARD_TRANSITION_LABELS",
    "STANDARD_STREAK_LABELS",
    "standard_derived",
    "project_range",
    "projection_inputs_of",
]
