"""时间长河两种查询形状的契约测试：横扫与纵扫。

纵扫的核心风险是**门永远说「不可区分」**——那样它看起来很严谨，其实什么都没判。
所以这里有一对对照：阳性（真值必为强信号）必须 `supported`，阴性（随机队列）
必须 `not_distinguishable`。少了阳性那一半，这套门禁没被证伪过。
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from intelligence.services.river_query import (
    MIN_N,
    cohort_compare,
    find_dislocation,
    normalize_stage,
    scan_cross_section,
)

DB = Path("db/market_feature_store.duckdb")
AS_OF = "2026-09-02"

pytestmark = pytest.mark.skipif(not DB.exists(), reason="需要真库 db/market_feature_store.duckdb")


@pytest.fixture(scope="module")
def all_dates() -> list[str]:
    import duckdb

    con = duckdb.connect(str(DB), read_only=True)
    try:
        return [
            str(r[0])
            for r in con.execute(
                "SELECT CAST(trade_date AS DATE) FROM fact_market_daily ORDER BY trade_date"
            ).fetchall()
        ]
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# 纵扫：统计门
# --------------------------------------------------------------------------- #
def test_阳性对照_真值为强信号的队列必须判_supported() -> None:
    """把「主升」那些天整体当队列：占比 100% vs 基准 12.8%，判不出来就是门坏了。"""
    import duckdb

    con = duckdb.connect(str(DB), read_only=True)
    try:
        days = [
            str(r[0])
            for r in con.execute(
                "SELECT CAST(trade_date AS DATE) FROM fact_market_daily "
                "WHERE market_stage LIKE '主升%' ORDER BY trade_date"
            ).fetchall()
        ]
    finally:
        con.close()
    assert len(days) >= MIN_N, "阳性对照样本不足，本用例证不了任何事"
    rep = cohort_compare(days)
    supported = [c for c in rep.cells if c.verdict == "supported"]
    assert supported, f"阳性对照没判出 supported：{[(c.value, c.verdict) for c in rep.cells]}"
    assert supported[0].value == "主升"
    assert supported[0].rate == 1.0


def test_阴性对照_随机队列必须判_not_distinguishable(all_dates: list[str]) -> None:
    """随机抽样的真值必为噪声。这里同时量出了门的假阳性底噪：应当为 0。"""
    rng = random.Random(20260905)
    false_positives = 0
    for _ in range(5):
        rep = cohort_compare(sorted(rng.sample(all_dates, 37)))
        false_positives += sum(1 for c in rep.cells if c.verdict in {"supported", "refuted"})
    assert false_positives == 0, f"随机队列刷出了 {false_positives} 个结论，BH 校正没兜住"


def test_队列小于_MIN_N_时不出率(all_dates: list[str]) -> None:
    rep = cohort_compare(all_dates[:5])
    assert rep.cohort_size == 5
    assert {c.verdict for c in rep.cells} == {"insufficient_n"}
    assert any("MIN_N" in note for note in rep.notes)


def test_市场阶段两套写法必须先归一() -> None:
    """「顶部横盘阶段」与「顶部横盘」不归一，一个阶段会被劈成两格、样本减半。"""
    assert normalize_stage("顶部横盘阶段") == normalize_stage("顶部横盘") == "顶部横盘"
    assert normalize_stage("下跌阶段") == normalize_stage("下跌") == "下跌"
    assert normalize_stage(None) == "未知"


def test_归一确实合并了库里真实存在的两套写法(all_dates: list[str]) -> None:
    """阳性对照：库里必须真的同时存在带「阶段」和不带的写法，否则上一条用例是空转。"""
    import duckdb

    con = duckdb.connect(str(DB), read_only=True)
    try:
        raw = {str(r[0]) for r in con.execute("SELECT DISTINCT market_stage FROM fact_market_daily").fetchall()}
    finally:
        con.close()
    both = {s for s in raw if s and not s.endswith("阶段") and f"{s}阶段" in raw}
    assert both, f"库里已经没有两套写法了——G-05 若已归一，请删掉 normalize_stage 补丁。当前取值：{sorted(raw)}"
    rep = cohort_compare(all_dates)
    values = [c.value for c in rep.cells]
    assert len(values) == len(set(values)), "归一后仍有重复格，说明补丁没生效"


# --------------------------------------------------------------------------- #
# 横扫：跨维错位
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def cross_section() -> list:
    return scan_cross_section(AS_OF)


def test_舆论排序用近_90_日而不是累计(cross_section: list) -> None:
    """累计数被 2026-01 那次回填批次污染（469 份里 249 份），用它排序会把
    「一年前被喊过很多」读成「现在催化多」。

    阳性对照：横截面里必须真的存在「累计高、近 90 日为 0」的板块，
    且它们**不得**出现在筛选结果里——没有这样的样本，本用例什么都没证明。
    """
    stale = [r for r in cross_section if r.coverage_cumulative >= 10 and r.coverage_90d == 0]
    assert stale, "横截面里没有「累计高、近期零」的板块，本用例触达不到它要守的分支"
    picked = {r.entity_name for r in find_dislocation(AS_OF, min_coverage_90d=3)}
    assert not (picked & {r.entity_name for r in stale})


def test_零覆盖不参与舆论分位(cross_section: list) -> None:
    """0 份研报不是「舆论最冷」，是没有数据——补成 0 分位会造出假错位。"""
    zeros = [r for r in cross_section if r.coverage_90d == 0]
    assert zeros, "本日全部板块都有近期覆盖？前提失效"
    assert all(r.opinion_pctile is None for r in zeros)
    assert all(r.dislocation is None for r in zeros)


def test_筛选结果满足两个显式阈值() -> None:
    rows = find_dislocation(AS_OF, min_coverage_90d=3, max_market_pctile=0.4)
    assert rows, f"{AS_OF} 没有命中——若数据变了请换日期，不要放宽阈值让它变绿"
    for r in rows:
        assert r.coverage_90d >= 3
        assert r.market_pctile is not None and r.market_pctile <= 0.4


def test_横扫幂等() -> None:
    a = [r.to_dict() for r in scan_cross_section(AS_OF)]
    b = [r.to_dict() for r in scan_cross_section(AS_OF)]
    assert a == b
