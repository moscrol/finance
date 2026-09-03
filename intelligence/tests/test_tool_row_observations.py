"""工具行（finance_query）证据卡必须携带结构化观察值。

失败形状（生产实锤 run_20260821_152044_472523，8792@dfc25221）：
预取锚空表后，模型靠 finance_query 拿回 25 行真数据写出全对草稿，
判官按错位投影把含真数字的句子整段删掉——因为工具行没有
``observations``，第 2~5 刀的「删句连坐检测 / 槽补回 / 数值门禁」
全都看不见这些有收据的数。

本文件锁：带收据的工具行与预取行同权——
「公开稿数字 ⊆ 桌上的行 ∪ 有收据的工具行」（spec §6.2 口径）。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from intelligence.services.agent_research import grounded_values_in_text
from intelligence.services.finance_query import (
    FinanceQuery,
    FinanceQuerySpec,
)
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)

_SECTOR_DDL = """
create table fact_sector_daily(
    trade_date date,
    sector_ts_code varchar,
    sector_name varchar,
    sw_l1 varchar,
    pct_chg double,
    amount double,
    diff_ratio double,
    strength double,
    multi_period_resonance boolean
)
"""

_SECTOR_STOCK_DDL = """
create table fact_sector_stock_daily(
    trade_date date,
    sector_ts_code varchar,
    sector_name varchar,
    stock_ts_code varchar,
    stock_name varchar,
    sw_industry varchar,
    high_status varchar,
    price double,
    pct_chg double,
    pct_chg_5d double,
    pct_chg_10d double,
    pct_chg_20d double,
    amount double,
    fund_flow_1d double,
    fund_flow_5d double,
    float_mcap_yi double
)
"""

_MARKET_DDL = """
create table fact_market_daily(
    trade_date date,
    market_stage varchar,
    total_amount double,
    sh_index_pct_chg double,
    limit_up integer,
    limit_down integer
)
"""


@pytest.fixture
def observation_db(tmp_path: Path) -> Path:
    path = tmp_path / "market.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute(_SECTOR_DDL)
        connection.executemany(
            "insert into fact_sector_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                # 干净单轨：CXO概念（本 run 被删弧线的原型）
                (
                    "2026-08-19", "C1", "CXO概念", "医药生物",
                    -3.9, 515.23, 7.63, 1.0, False,
                ),
                (
                    "2026-08-20", "C1", "CXO概念", "医药生物",
                    5.26, 773.84, 50.19, 4.0, True,
                ),
                # 撞名双轨：PCB 同日两代码，pct/amount 矛盾、diff_ratio 相同
                # （Gate 1 实测形状：885959.TI vs 990026.FP）
                (
                    "2026-08-07", "885959.TI", "PCB", "电子",
                    8.71, 1295.16, 23.06, 3.0, True,
                ),
                (
                    "2026-08-07", "990026.FP", "PCB", "电子",
                    4.74, 3432.59, 23.06, 3.0, True,
                ),
            ],
        )
        connection.execute(_SECTOR_STOCK_DDL)
        connection.executemany(
            "insert into fact_sector_stock_daily values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-08-20", "C1", "CXO概念", "603259.SH", "药明康德",
                    "医药生物", None, 100.0, 2.38, 5.0, 8.0, 12.0,
                    145.89, 1.0, 2.0, 2900.0,
                ),
            ],
        )
        connection.execute(_MARKET_DDL)
        connection.execute(
            "insert into fact_market_daily values "
            "('2026-08-20', '反弹阶段', 23000.0, 1.2, 80, 12)"
        )
    finally:
        connection.close()
    return path


def _cutoff() -> InformationCutoff:
    return InformationCutoff(date(2026, 8, 20), "requested")


def _run(db: Path, **overrides: object):
    arguments: dict[str, object] = {
        "dataset": "sector_daily",
        "metrics": ["return_pct", "amount", "marginal_volume_pct"],
        "dimensions": ["trade_date", "sector_name"],
        "filters": [],
        "time_range": {"start": "2026-08-01", "end": "2026-08-20"},
        "group_by": [],
        "order_by": [{"field": "trade_date", "direction": "asc"}],
        "limit": 20,
    }
    arguments.update(overrides)
    return FinanceQuery(db).run(
        FinanceQuerySpec.from_arguments(arguments),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )


def test_sector_daily_rows_carry_structured_observations(
    observation_db: Path,
) -> None:
    result = _run(
        observation_db,
        filters=[{"field": "sector_name", "op": "eq", "value": "CXO概念"}],
    )

    by_date = {item.source_date: item for item in result.evidence}
    got = {
        (obs.subject, obs.as_of, obs.metric, obs.value)
        for obs in by_date["2026-08-20"].observations
    }
    assert got == {
        ("CXO概念", "2026-08-20", "pct_chg", 5.26),
        ("CXO概念", "2026-08-20", "amount", 773.84),
        ("CXO概念", "2026-08-20", "diff_ratio", 50.19),
    }
    # 观察值指标名在底层列名空间（与预取观察值同一空间），不是查询层别名。
    metrics = {obs.metric for item in result.evidence for obs in item.observations}
    assert "return_pct" not in metrics and "marginal_volume_pct" not in metrics


def test_grounded_gate_sees_tool_row_numbers(observation_db: Path) -> None:
    """删句连坐检测（第 2 刀入口）无需任何改动即可认出工具行的数。"""

    result = _run(
        observation_db,
        filters=[{"field": "sector_name", "op": "eq", "value": "CXO概念"}],
    )

    hits = grounded_values_in_text(
        "8-19 板块跌 3.9%、成交 515.23 亿，8-20 放量至 773.84 亿。",
        result.evidence,
    )
    got = {(obs.as_of, obs.metric, obs.value) for obs in hits}
    assert ("2026-08-19", "amount", 515.23) in got
    assert ("2026-08-20", "amount", 773.84) in got


def test_conflicting_same_day_rows_suppress_only_the_contested_cell(
    observation_db: Path,
) -> None:
    """同 (主体, 日期, 指标) 矛盾值不产观察值——与预取第 7 刀同规则。

    把矛盾当事实投递，是钙钛矿 run_20260821_114642 质量下降链的第一次
    分叉；值相同的重复格（此处 diff_ratio）无害，照常产出。
    """

    result = _run(
        observation_db,
        time_range={"start": "2026-08-01", "end": "2026-08-10"},
        filters=[{"field": "sector_name", "op": "eq", "value": "PCB"}],
    )

    assert len(result.evidence) == 2
    for item in result.evidence:
        cells = {(obs.metric, obs.value) for obs in item.observations}
        assert ("pct_chg", 8.71) not in cells
        assert ("pct_chg", 4.74) not in cells
        assert ("amount", 1295.16) not in cells
        assert ("amount", 3432.59) not in cells
        assert ("diff_ratio", 23.06) in cells


def test_sector_stock_rows_use_stock_as_subject(observation_db: Path) -> None:
    result = _run(
        observation_db,
        dataset="sector_stock_daily",
        metrics=["return_pct", "amount"],
        dimensions=["trade_date", "sector_name", "stock_name"],
        filters=[{"field": "stock_name", "op": "eq", "value": "药明康德"}],
        time_range={"start": "2026-08-20", "end": "2026-08-20"},
    )

    (item,) = result.evidence
    got = {(obs.subject, obs.metric, obs.value) for obs in item.observations}
    assert got == {
        ("药明康德", "pct_chg", 2.38),
        ("药明康德", "amount", 145.89),
    }


def test_rows_without_subject_dimension_emit_no_observations(
    observation_db: Path,
) -> None:
    """聚合掉主体维度后 fail closed：宁可不产，不产没有主体的数。"""

    result = _run(
        observation_db,
        metrics=["amount"],
        dimensions=["trade_date"],
        group_by=["trade_date"],
    )

    assert result.evidence
    for item in result.evidence:
        assert item.observations == ()


def test_market_daily_rows_use_whole_market_as_subject(observation_db: Path) -> None:
    """全市单行与预取同权：主体是「全市场」，成交额必须进槽。

    未挂观察值时，判官删句会把已绑定的成交额从公开稿抹掉（E1 现场形状）。
    """
    result = _run(
        observation_db,
        dataset="market_daily",
        metrics=["total_amount", "index_return_pct"],
        dimensions=["trade_date", "market_stage"],
        time_range={"start": "2026-08-20", "end": "2026-08-20"},
    )

    (item,) = result.evidence
    got = {(obs.subject, obs.as_of, obs.metric, obs.value) for obs in item.observations}
    assert got == {("全市场", "2026-08-20", "total_amount", 23000.0)}
    # 指数涨跌幅未登记进全市槽；没有主体的指标仍不产。
    assert all(obs.metric != "sh_index_pct_chg" for obs in item.observations)
