"""第 8 步样本量锁：校准方差已测，门槛不放宽。

来源：Step 1 收据 §6.1；2026-08-16 Arm A 校准收据（#68）pooled_variance=0.1375。

30×3 压不住 5pp。本模块只回答「n、r 锁多少」，不跑 Arm B，
不把 5pp 变成参数。

0.125 是草稿分支 ``feat/dsh-absorption-p0-seams`` 本地 4 提交里误标
「official 收据实测」的幽灵数，已标 dropped，禁止回流。
"""

from __future__ import annotations

import math

from intelligence.eval.arm_a_calibration import (
    THRESHOLD_PP,
    THRESHOLD_RATE,
    projected_ci_half_width,
    required_nr,
)

# [实测] 2026-08-16 official Arm A 校准收据 pooled_variance（#68）。
# 不是 0.125。0.125 推出 required_nr≈384 → 30×13=390，按真值不够。
MEASURED_POOLED_VARIANCE = 0.1375
DROPPED_DRAFT_VARIANCE = 0.125
PREFERRED_QUESTION_COUNT = 30
REPEAT_FLOOR = 3


def locked_repeats(
    variance: float = MEASURED_POOLED_VARIANCE,
    *,
    question_count: int = PREFERRED_QUESTION_COUNT,
) -> int:
    if variance < 0 or question_count <= 0:
        raise ValueError("variance and question_count must be valid")
    needed = required_nr(variance)
    repeats = max(REPEAT_FLOOR, math.ceil(needed / question_count))
    return repeats


def recommend_design(
    variance: float = MEASURED_POOLED_VARIANCE,
    *,
    question_count: int = PREFERRED_QUESTION_COUNT,
) -> dict[str, object]:
    repeats = locked_repeats(variance, question_count=question_count)
    nr = question_count * repeats
    half_width = projected_ci_half_width(
        variance, question_count=question_count, repeats=repeats
    )
    return {
        "question_count": question_count,
        "repeats": repeats,
        "nr": nr,
        "required_nr": required_nr(variance),
        "measured_variance": variance,
        "threshold_pp": THRESHOLD_PP,
        "ci95_half_width": half_width,
        "can_resolve_5pp": half_width < THRESHOLD_RATE,
        "live_ab_ran": False,
        "retain_dsh_runtime": False,
        "next_action": (
            "run_locked_window"
            if half_width < THRESHOLD_RATE
            else "increase_n_or_repeats_do_not_loosen_threshold"
        ),
    }


__all__ = [
    "DROPPED_DRAFT_VARIANCE",
    "MEASURED_POOLED_VARIANCE",
    "PREFERRED_QUESTION_COUNT",
    "REPEAT_FLOOR",
    "locked_repeats",
    "recommend_design",
]
