"""子单 B 第 1 刀：预取行出结构化数值，供必填格填数。离线锁，不打生产库。

三筛自审（`harness-reference/PLAYBOOK.md` §约束三筛）：
- 拦输入：固定「槽里的数字从哪来」，不规定模型怎么写句子 → 保下限
- 失效变错：取错数 = 吐假行情，必须硬
- 模型变强不挡路：本地当期数字不在权重里，再强的模型也需要投递

因此本文件锁的是**取数口径**，不锁措辞、不锁段数。
`observation_value` 缺数必须返 None（结构缺口），**不许静默近似**——
静默近似会让「没有数据」和「数据是这个」在下游长得一样。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from intelligence.services.asof_prefetch import (
    collect_prefetch_items,
    observation_value,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

pytestmark = pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")

# Gate 1 现场：同日两个板块名，数字差一倍（母子集，非互斥口径）
PCB_QUERY = "PCB概念这波是怎么发酵到 2026-08-07 的，涨幅、成交额和成交额环比"
AS_OF = date(2026, 8, 7)

ROWS = [
    # (trade_date, sector_name, pct_chg, diff_ratio, amount)
    ("2026-08-06", "PCB概念", 1.20, 11.0, 3300.00),
    ("2026-08-07", "PCB概念", 4.74, 23.72, 3432.59),
    ("2026-08-06", "PCB", 2.10, 12.0, 1200.00),
    ("2026-08-07", "PCB", 8.71, 23.06, 1295.16),
]


def _sector_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_sector_daily ("
        "trade_date date, sector_name varchar, "
        "pct_chg double, diff_ratio double, amount double)"
    )
    con.executemany("insert into fact_sector_daily values (?, ?, ?, ?, ?)", ROWS)
    con.close()
    return path


def _items(tmp_path: Path):
    db = _sector_db(tmp_path / "sector.duckdb")
    return collect_prefetch_items(
        question=PCB_QUERY,
        question_type="theme_research",
        subject="PCB",
        as_of=AS_OF,
        market_db_path=db,
    )


def test_timeline_item_exposes_structured_observations(tmp_path: Path) -> None:
    """数字必须以结构化形式随预取行返回，不能只埋在 detail 文本里。

    埋在文本里 = 下游只能回头解析自由文本，那是本仓明令的反模式。
    """

    items = _items(tmp_path)
    timeline = [item for item in items if "时间轴" in item.title]
    assert timeline, "发酵题应产出板块时间轴预取行"
    observations = timeline[0].observations
    assert observations, "时间轴预取行必须带结构化观察值"
    metrics = {obs.metric for obs in observations}
    assert {"pct_chg", "amount", "diff_ratio"} <= metrics


TRUTH = {  # 同日两个板块名的真值，用来验「槽没混口径」
    "PCB": {"pct_chg": 8.71, "amount": 1295.16},
    "PCB概念": {"pct_chg": 4.74, "amount": 3432.59},
}


def test_slot_numbers_come_from_the_anchored_sector_only(tmp_path: Path) -> None:
    """槽只装**锚定那一个**板块的数，绝不把两个口径混进同一批观察值。

    这是子单 B 的本职契约，与「锚得对不对」无关（那是 #288 子单 C 的事）：
    锚错了槽会忠实地投递错口径，但**永远不会同时投递两套**。
    两套同日数字并存正是 Gate 1 第二层翻车的形状。
    """

    items = _items(tmp_path)
    timeline = [item for item in items if "时间轴" in item.title][0]
    anchored = {obs.subject for obs in timeline.observations}
    assert len(anchored) == 1, f"槽混了多个板块口径：{anchored}"

    sector = anchored.pop()
    expected = TRUTH[sector]
    assert observation_value(
        items, trade_date="2026-08-07", metric="pct_chg"
    ) == pytest.approx(expected["pct_chg"])
    assert observation_value(
        items, trade_date="2026-08-07", metric="amount"
    ) == pytest.approx(expected["amount"])


def test_long_name_anchor_yields_question_caliber(tmp_path: Path) -> None:
    """锚到问句点名的长名时，槽给的是 4.74/3432.59，不是短名的 8.71/1295.16。

    这里显式传 ``subject='PCB概念'`` 把锚固定住，只验槽这一段；
    「短 subject 该不该被问句里的长名顶掉」由 #288 的
    ``test_asof_prefetch_dual_red`` 负责，不在本文件重复。
    """

    db = _sector_db(tmp_path / "sector.duckdb")
    items = collect_prefetch_items(
        question=PCB_QUERY,
        question_type="theme_research",
        subject="PCB概念",
        as_of=AS_OF,
        market_db_path=db,
    )
    assert observation_value(
        items, trade_date="2026-08-07", metric="pct_chg"
    ) == pytest.approx(4.74)
    assert observation_value(
        items, trade_date="2026-08-07", metric="amount"
    ) == pytest.approx(3432.59)


def test_missing_row_returns_none_not_nearest(tmp_path: Path) -> None:
    """缺数返 None = 结构缺口。禁止回退到邻近交易日或另一板块。

    这条是「保下限」的锁：静默近似会让「没有数据」和「数据是这个」
    在下游长得完全一样，覆盖率审计永远发现不了。
    """

    items = _items(tmp_path)
    assert observation_value(items, trade_date="2026-08-05", metric="pct_chg") is None
    assert observation_value(items, trade_date="2026-08-07", metric="turnover") is None


def test_observation_value_does_not_touch_answer_text(tmp_path: Path) -> None:
    """取数原语只回答「真值是多少」，不持有、不改写任何稿件文本。

    这条锁的是「不封上限」：一旦它能改写正文，就会长成判官整段删的同形物
    （#288 / Gate 1 第三层：真话和编造绑同一段，一刀切下去真话陪葬）。
    """

    items = _items(tmp_path)
    value = observation_value(items, trade_date="2026-08-07", metric="pct_chg")
    assert isinstance(value, float)
    # 返回标量而非 (文本, 值)：结构上就没有改写正文的入口
    assert not isinstance(value, tuple)
