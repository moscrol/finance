"""换手率推算值 turnover_est（2026-10-06）。

fact_stock_daily.turnover 是供应商原值，2025-10 至 2026-08 几乎全空（主力源 mootdx 不给换手率），
模型问换手率只会拿到「字段缺值」。推算式 成交量(手)×收盘÷流通市值(亿)÷1e4 与东财等原值对账
多数误差在 2% 以内，所以单列成 turnover_est 提供：不并进原值列（逐行分不出来源），
股票挂多个板块时不能因 join 变成多行，缺料时为空而不是报错。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from intelligence.services import finance_query as fq
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline

_DAY = "2026-09-18"


def _make_db(path: Path, *, with_volume: bool = True, with_mcap: bool = True) -> Path:
    with duckdb.connect(str(path)) as con:
        volume = ", volume double" if with_volume else ""
        con.execute(
            "create table fact_stock_daily (trade_date date, stock_ts_code varchar, stock_name varchar, "
            f"close double, pre_close double, pct_chg double, amount double, turnover double{volume})"
        )
        rows = [
            # 代码, 名称, 收盘, 成交额亿, 原值换手率, 成交量手
            ("688038.SH", "甲", 18.91, 0.2588, None, 13767.0),  # 原值缺，可推算
            ("688109.SH", "乙", 74.5, 0.771, 1.32, 10376.0),  # 原值在，推算值单列
            ("000001.SZ", "丙", 10.0, 1.0, None, None),  # 缺成交量
            ("000002.SZ", "丁", 10.0, 1.0, None, 5000.0),  # 缺流通市值
        ]
        for code, name, close, amount, turnover, vol in rows:
            values = [_DAY, code, name, close, None, 0.5, amount, turnover] + ([vol] if with_volume else [])
            con.execute(f"insert into fact_stock_daily values ({', '.join('?' * len(values))})", values)
        mcap = ", float_mcap_yi double" if with_mcap else ""
        con.execute(
            f"create table fact_sector_stock_daily (trade_date date, sector_ts_code varchar, stock_ts_code varchar{mcap})"
        )
        members = [("S1", "688038.SH", 22.01), ("S2", "688038.SH", 22.01), ("S1", "688109.SH", 58.74)]
        for sector, code, value in members:
            values = [_DAY, sector, code] + ([value] if with_mcap else [])
            con.execute(f"insert into fact_sector_stock_daily values ({', '.join('?' * len(values))})", values)
    return path


def _run(db: Path, **arguments):
    spec = fq.FinanceQuerySpec.from_arguments({
        "dataset": "stock_daily",
        "dimensions": ["trade_date", "stock_code"],
        "time_range": {"start": _DAY, "end": _DAY},
        "limit": 50,
        **arguments,
    })
    return fq.FinanceQuery(db).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
        deadline=ResearchDeadline.from_timeout(10),
    )


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return _make_db(tmp_path / "market_feature_store.duckdb")


def test_estimate_fills_where_supplier_turnover_is_missing_without_mixing_columns(db: Path) -> None:
    result = _run(db, metrics=["turnover", "turnover_est"])
    by_code = {row["stock_code"]: row for row in result.rows}

    # 一只股票挂两个板块，也只能是一行。
    assert sorted(by_code) == ["000001.SZ", "000002.SZ", "688038.SH", "688109.SH"]
    assert len(result.rows) == 4
    assert by_code["688038.SH"]["turnover"] is None
    assert by_code["688038.SH"]["turnover_est"] == pytest.approx(13767 * 18.91 / 22.01 / 1e4)
    # 原值在时两列各是各的：推算值不被原值顶替，原值也不被推算值改写。
    assert by_code["688109.SH"]["turnover"] == pytest.approx(1.32)
    assert by_code["688109.SH"]["turnover_est"] == pytest.approx(10376 * 74.5 / 58.74 / 1e4)
    # 缺成交量或缺流通市值：为空，不补零。
    assert by_code["000001.SZ"]["turnover_est"] is None
    assert by_code["000002.SZ"]["turnover_est"] is None
    assert any("turnover_est" in gap for gap in result.quality_gaps)


def test_ranking_by_the_estimate_uses_the_estimate(db: Path) -> None:
    result = _run(
        db,
        metrics=["turnover_est"],
        order_by=[{"field": "turnover_est", "direction": "desc"}],
        filters=[{"field": "stock_code", "op": "in", "value": ["688038.SH", "688109.SH"]}],
    )

    assert [row["stock_code"] for row in result.rows] == ["688109.SH", "688038.SH"]


@pytest.mark.parametrize(
    ("with_volume", "with_mcap"),
    [(False, True), (True, False)],
    ids=["no-volume-column", "no-float-mcap-column"],
)
def test_missing_inputs_leave_the_estimate_empty_instead_of_failing(
    tmp_path: Path, with_volume: bool, with_mcap: bool,
) -> None:
    db = _make_db(tmp_path / "partial.duckdb", with_volume=with_volume, with_mcap=with_mcap)

    result = _run(db, metrics=["turnover_est"])

    assert len(result.rows) == 4
    assert all(row["turnover_est"] is None for row in result.rows)


def test_queries_that_do_not_ask_for_the_estimate_never_touch_the_sector_table(tmp_path: Path) -> None:
    path = tmp_path / "stock-only.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("create table fact_stock_daily (trade_date date, stock_ts_code varchar, close double)")
        con.execute("insert into fact_stock_daily values (?, '688038.SH', 18.91)", [_DAY])

    result = _run(path, metrics=["close"])

    assert [row["close"] for row in result.rows] == [18.91]
