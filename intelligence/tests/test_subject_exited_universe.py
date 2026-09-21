"""「主体退出集合」与「管道陈旧」必须分开（R-20260816-22）。

2026-09-21 用户更新口径：数据日期不齐仍交付，并标实际日期。

- DuckDB 硬事实（行情/成交/涨停）→ 不把旧值冒充今日值；
- 知识库/图谱（`kb_search` / `graph_lookup`）→ 关注逻辑的生命周期变化，
  本就不过这道门（现状即符合，本文件不涉及）；
- 第三种情形：数据集整体已到 floor、被筛子集停在更早 → **该主体退出了集合**，
  属行业生命周期观察，必须交付。

守的实例：`fact_mainline_sector_daily` 有到 2026-08-14 的行，而「AI算力」最后
一天是 08-07（08-10 起主线只剩有色金属/医药/消费零售）。「算力掉出主线」正是
「发酵/共识/透支」要的信号，当过期数据丢掉等于丢掉答案。

本文件只断言两种情形被区分：整表落后不能冒称主体退出；两者的已有数据均可交付。
"""

from __future__ import annotations

from datetime import date

import pytest

from intelligence.services.episode_tools import _subject_exited_universe

_FLOOR = date(2026, 8, 14)


# ------------------------------------------------ 情形一：主体退出（须放行）

def test_subject_exited_when_dataset_is_current_but_slice_is_not() -> None:
    """数据集已到 floor、被筛子集停在更早 → 退出，不是陈旧。"""

    assert _subject_exited_universe(
        served_date="2026-08-07",
        dataset_max_date="2026-08-14",
        floor=_FLOOR,
    )


def test_subject_exited_holds_when_dataset_is_ahead_of_floor() -> None:
    """数据集比 floor 还新时同样成立——判据看的是数据集与子集的关系。"""

    assert _subject_exited_universe(
        served_date="2026-08-07",
        dataset_max_date="2026-08-20",
        floor=_FLOOR,
    )


# ------------------------------------------------ 情形二：整表落后（不能宣称主体退出）

def test_pipeline_stale_is_not_an_exit() -> None:
    """数据集整体也停在更早 → 只知管道落后，不能据此宣称主体退出。"""

    assert not _subject_exited_universe(
        served_date="2026-08-07",
        dataset_max_date="2026-08-07",
        floor=_FLOOR,
    )


def test_pipeline_stale_when_dataset_max_just_below_floor() -> None:
    """差一天也是陈旧——边界不能靠「差不多」放过去。"""

    assert not _subject_exited_universe(
        served_date="2026-08-07",
        dataset_max_date="2026-08-13",
        floor=_FLOOR,
    )


# ------------------------------------------------ fail-closed

@pytest.mark.parametrize(
    ("served", "dataset_max"),
    [
        ("2026-08-07", None),   # 探针失败/未跑
        (None, "2026-08-14"),   # 被筛结果无日期
        (None, None),
        ("2026-08-07", "not-a-date"),
        ("not-a-date", "2026-08-14"),
    ],
)
def test_unknown_readings_fall_back_to_stale(
    served: str | None, dataset_max: str | None
) -> None:
    """读数缺失或畸形时不颁发主体退出的证明；不撤销已有数据的交付。"""

    assert not _subject_exited_universe(
        served_date=served, dataset_max_date=dataset_max, floor=_FLOOR
    )


def test_slice_not_earlier_than_dataset_is_not_an_exit() -> None:
    """子集与数据集同期 → 没有退出这回事。"""

    assert not _subject_exited_universe(
        served_date="2026-08-14",
        dataset_max_date="2026-08-14",
        floor=_FLOOR,
    )


# ------------------------------------------------ 两情形必须真的被分开

def test_two_situations_are_actually_discriminated() -> None:
    """同一个 `served_date`，只因数据集 max 不同就得出相反结论。

    这条是本文件的核心判据：把两个夹具的判据合并成一个（例如只看 served 与
    floor、或直接放宽 floor），本条必红。单独断言任一情形都挡不住那种假修复。
    """

    served = "2026-08-07"
    exited = _subject_exited_universe(
        served_date=served, dataset_max_date="2026-08-14", floor=_FLOOR
    )
    stale = _subject_exited_universe(
        served_date=served, dataset_max_date="2026-08-07", floor=_FLOOR
    )
    assert exited is True
    assert stale is False
    assert exited != stale, "两种情形没被分开——判据退化成只看 served 了"
