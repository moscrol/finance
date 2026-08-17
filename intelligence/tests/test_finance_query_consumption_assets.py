"""零消费表接通语义层：竞价 / 研报目录 / 事件日历 / 个股技术特征。

接法照 2026-08-13 龙虎榜先例——注册 ``_DATASETS`` 即 agent 可查。
本文件只测公开 seam：``FinanceQuery.run``、参数面 enum、limit/time_range。
研报 JSON 标签列用 ``report_type`` 过滤，不走 ``contains``（FINANCEWORKS-2）。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from intelligence.paths import default_paths
from intelligence.services.finance_query import (
    FINANCE_QUERY_PARAMETERS,
    FinanceQuery,
    FinanceQuerySpec,
    _DATASETS,
)
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)

_NEW_DATASETS = {
    "auction_stock_daily": "fact_auction_stock_daily",
    "research_report_catalog": "fact_research_report_catalog",
    "event_daily": "fact_event_daily",
    "stock_technical_daily": "feature_stock_technical_daily",
}

def _resolve_live_db() -> Path:
    candidates = (
        default_paths().finance_root / "db" / "market_feature_store.duckdb",
        Path.home() / "finance-workspace-private" / "db" / "market_feature_store.duckdb",
    )
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


_LIVE_DB = _resolve_live_db()


def _cutoff() -> InformationCutoff:
    return InformationCutoff(date(2026, 8, 17), "requested")


def _run(db_path: Path, arguments: dict[str, object]):
    return FinanceQuery(db_path).run(
        FinanceQuerySpec.from_arguments(arguments),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )


def _auction_db(tmp_path: Path) -> Path:
    path = tmp_path / "auction.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            create table fact_auction_stock_daily(
                trade_date date, panel_key varchar, panel_label varchar,
                stock_ts_code varchar, stock_name varchar,
                auction_pct double, pct_chg double,
                auction_amount double, day_amount double,
                limit_seq integer, leader_plate varchar
            )
            """
        )
        con.executemany(
            "insert into fact_auction_stock_daily values (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    "2026-08-14", "zt", "昨日涨停", "300862.SZ", "蓝盾光电",
                    14.18, 19.99, 4.42, 34.95, 4, "股权",
                ),
                (
                    "2026-08-14", "db", "1日前断板", "000001.SZ", "平安银行",
                    1.0, 2.0, 0.5, 10.0, 0, "银行",
                ),
            ],
        )
    finally:
        con.close()
    return path


def _catalog_db(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            create table fact_research_report_catalog(
                report_id integer, title varchar, report_date date,
                report_type varchar, is_hot boolean,
                sector_tags varchar, concept_tags varchar, stock_count integer
            )
            """
        )
        con.executemany(
            "insert into fact_research_report_catalog values (?,?,?,?,?,?,?,?)",
            [
                (
                    1,
                    "腾讯 Q2 算力租赁报告",
                    "2026-08-13",
                    "report",
                    False,
                    '["算力租赁", "数据中心"]',
                    "[]",
                    22,
                ),
                (
                    2,
                    "行业周报",
                    "2026-08-13",
                    "industry",
                    True,
                    '["银行"]',
                    "[]",
                    3,
                ),
            ],
        )
    finally:
        con.close()
    return path


def _event_db(tmp_path: Path) -> Path:
    path = tmp_path / "event.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            create table fact_event_daily(
                event_date date, event_id varchar, title varchar,
                importance integer, event_type varchar, sectors varchar,
                is_future boolean
            )
            """
        )
        con.executemany(
            "insert into fact_event_daily values (?,?,?,?,?,?,?)",
            [
                (
                    "2026-08-17", "e1", "2026中国固态电池技术大会",
                    6, "会议", "[]", True,
                ),
                (
                    "2026-08-10", "e2", "已发生的数据发布",
                    4, "数据发布", "[]", False,
                ),
            ],
        )
    finally:
        con.close()
    return path


def _technical_db(tmp_path: Path, *, extra_rows: int = 0) -> Path:
    path = tmp_path / "technical.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            create table feature_stock_technical_daily(
                trade_date date, stock_ts_code varchar, stock_name varchar,
                close double, ma26 double, std26 double,
                up_value double, deviation_pct double
            )
            """
        )
        rows = [
            (
                "2026-08-17", "601566.SH", "九牧王",
                8.51, 8.2238, 0.3321, 8.4775, 0.38,
            ),
            (
                "2026-08-17", "601609.SH", "金田股份",
                11.71, 10.1412, 0.498, 10.5216, 11.29,
            ),
            (
                "2026-08-14", "601566.SH", "九牧王",
                8.10, 8.10, 0.30, 8.30, -2.4,
            ),
        ]
        for index in range(extra_rows):
            rows.append(
                (
                    "2026-08-17",
                    f"{600000 + index:06d}.SH",
                    f"填充{index}",
                    10.0 + index,
                    9.0,
                    0.5,
                    9.4,
                    1.0,
                )
            )
        con.executemany(
            "insert into feature_stock_technical_daily values (?,?,?,?,?,?,?,?)",
            rows,
        )
    finally:
        con.close()
    return path


def test_consumption_assets_registered_as_datasets() -> None:
    """入库 ≠ 可消费：四张零消费表必须注册进 finance_query。"""

    for name, table in _NEW_DATASETS.items():
        assert name in _DATASETS, name
        assert _DATASETS[name].table == table
    event = _DATASETS["event_daily"]
    assert "is_future" in event.label or "未来催化" in event.label


def test_consumption_assets_visible_on_parameter_surface() -> None:
    datasets = FINANCE_QUERY_PARAMETERS["properties"]["dataset"]["enum"]
    for name in _NEW_DATASETS:
        assert name in datasets, name


def test_auction_stock_query_returns_rows_and_filters_panel(tmp_path: Path) -> None:
    result = _run(
        _auction_db(tmp_path),
        {
            "dataset": "auction_stock_daily",
            "metrics": ["auction_pct", "auction_amount"],
            "dimensions": ["trade_date", "panel_key", "stock_name"],
            "filters": [{"field": "panel_key", "op": "eq", "value": "zt"}],
            "time_range": {"start": "2026-08-14", "end": "2026-08-14"},
            "limit": 10,
        },
    )
    assert [row["stock_name"] for row in result.rows] == ["蓝盾光电"]
    assert result.rows[0]["panel_key"] == "zt"
    assert result.rows[0]["auction_pct"] == 14.18


def test_research_catalog_query_filters_report_type_not_json_contains(
    tmp_path: Path,
) -> None:
    """标签列是 JSON 字符串：过滤走 report_type，避开 contains/ESCAPE。"""

    result = _run(
        _catalog_db(tmp_path),
        {
            "dataset": "research_report_catalog",
            "metrics": ["stock_count"],
            "dimensions": ["report_date", "report_type", "title", "sector_tags"],
            "filters": [{"field": "report_type", "op": "eq", "value": "report"}],
            "time_range": {"start": "2026-08-13", "end": "2026-08-13"},
            "limit": 10,
        },
    )
    assert len(result.rows) == 1
    assert result.rows[0]["title"] == "腾讯 Q2 算力租赁报告"
    assert result.rows[0]["stock_count"] == 22
    assert "算力租赁" in str(result.rows[0]["sector_tags"])


def test_event_daily_query_filters_future_catalysts(tmp_path: Path) -> None:
    result = _run(
        _event_db(tmp_path),
        {
            "dataset": "event_daily",
            "metrics": ["importance"],
            "dimensions": ["event_date", "title", "is_future"],
            "filters": [{"field": "is_future", "op": "eq", "value": True}],
            "time_range": {"start": "2026-08-01", "end": "2026-08-17"},
            "limit": 10,
        },
    )
    assert [row["title"] for row in result.rows] == ["2026中国固态电池技术大会"]
    assert result.rows[0]["is_future"] is True
    assert result.rows[0]["importance"] == 6


def test_stock_technical_query_filters_stock_code(tmp_path: Path) -> None:
    result = _run(
        _technical_db(tmp_path),
        {
            "dataset": "stock_technical_daily",
            "metrics": ["close", "deviation_pct"],
            "dimensions": ["trade_date", "stock_code", "stock_name"],
            "filters": [{"field": "stock_code", "op": "eq", "value": "601566.SH"}],
            "time_range": {"start": "2026-08-17", "end": "2026-08-17"},
            "limit": 10,
        },
    )
    assert len(result.rows) == 1
    assert result.rows[0]["stock_name"] == "九牧王"
    assert result.rows[0]["close"] == 8.51


def test_stock_technical_limit_caps_without_time_range(tmp_path: Path) -> None:
    """200 万行表的护栏：无 time_range 也必须带 LIMIT，不能全表扫。"""

    result = _run(
        _technical_db(tmp_path, extra_rows=40),
        {
            "dataset": "stock_technical_daily",
            "metrics": ["close"],
            "dimensions": ["trade_date", "stock_code"],
            "limit": 5,
        },
    )
    assert len(result.rows) == 5
    assert result.audit.applied_limit == 5
    assert result.audit.row_count == 5
    assert "LIMIT" in result.audit.physical_sql.upper()


def test_stock_technical_time_range_excludes_other_days(tmp_path: Path) -> None:
    result = _run(
        _technical_db(tmp_path),
        {
            "dataset": "stock_technical_daily",
            "metrics": ["close"],
            "dimensions": ["trade_date", "stock_code"],
            "filters": [{"field": "stock_code", "op": "eq", "value": "601566.SH"}],
            "time_range": {"start": "2026-08-17", "end": "2026-08-17"},
            "limit": 10,
        },
    )
    assert [row["trade_date"] for row in result.rows] == ["2026-08-17"]


@pytest.mark.skipif(not _LIVE_DB.exists(), reason="需要本地 market_feature_store.duckdb")
def test_stock_technical_live_db_respects_limit_and_time_range() -> None:
    """真库 200 万行：limit + 单日 time_range 必须秒级返回，且不超过 limit。"""

    result = FinanceQuery(_LIVE_DB).run(
        FinanceQuerySpec.from_arguments(
            {
                "dataset": "stock_technical_daily",
                "metrics": ["close", "deviation_pct"],
                "dimensions": ["trade_date", "stock_code"],
                "time_range": {"start": "2026-08-17", "end": "2026-08-17"},
                "limit": 5,
            }
        ),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(8.0),
    )
    assert 0 < len(result.rows) <= 5
    assert result.audit.applied_limit == 5
    assert result.audit.elapsed_seconds < 2.0
    unbounded = FinanceQuery(_LIVE_DB).run(
        FinanceQuerySpec.from_arguments(
            {
                "dataset": "stock_technical_daily",
                "metrics": ["close"],
                "dimensions": ["trade_date", "stock_code"],
                "limit": 5,
            }
        ),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(8.0),
    )
    assert len(unbounded.rows) == 5
    assert unbounded.audit.elapsed_seconds < 2.0
    assert "LIMIT" in unbounded.audit.physical_sql.upper()
