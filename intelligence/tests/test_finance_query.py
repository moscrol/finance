from __future__ import annotations

from datetime import date
from pathlib import Path
from threading import Event
import time

import duckdb
import pytest

from intelligence.services.finance_query import (
    FINANCE_QUERY_PARAMETERS,
    FinanceQuery,
    FinanceQueryCancelled,
    FinanceQueryLimits,
    FinanceQueryLimitExceeded,
    FinanceQuerySpec,
    FinanceQueryTimedOut,
    FinanceQueryValidationError,
)
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)


@pytest.fixture
def market_db(tmp_path: Path) -> Path:
    path = tmp_path / "market.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            """
            create table fact_market_daily(
                trade_date date,
                market_stage varchar,
                total_amount double,
                sh_index_pct_chg double,
                limit_up integer,
                limit_down integer
            )
            """
        )
        connection.executemany(
            "insert into fact_market_daily values (?, ?, ?, ?, ?, ?)",
            [
                ("2026-07-21", "反弹阶段", 21000.0, 1.20, 80, 12),
                ("2026-07-24", "反弹阶段", 22000.0, -0.40, 52, 25),
                ("2026-07-25", "反弹阶段", 23000.0, 3.00, 110, 5),
                ("2026-07-24", "下跌阶段", 20500.0, -1.80, 20, 130),
            ],
        )
        connection.execute(
            """
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
        )
        connection.executemany(
            "insert into fact_sector_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-07-23", "S1", "电力", "公用事业", 2.0, 500.0, 12.0, 3.0, True),
                ("2026-07-24", "S1", "电力", "公用事业", 3.0, 700.0, 20.0, 4.0, True),
                ("2026-07-24", "S2", "银行", "银行", -1.0, 900.0, -5.0, -1.0, False),
            ],
        )
    finally:
        connection.close()
    return path


def _market_spec(**overrides: object) -> FinanceQuerySpec:
    arguments: dict[str, object] = {
        "dataset": "market_daily",
        "metrics": ["index_return_pct", "total_amount"],
        "dimensions": ["trade_date", "market_stage"],
        "filters": [
            {"field": "market_stage", "op": "eq", "value": "反弹阶段"}
        ],
        "time_range": {"start": "2026-07-20", "end": "2026-07-24"},
        "group_by": [],
        "order_by": [{"field": "trade_date", "direction": "asc"}],
        "limit": 20,
    }
    arguments.update(overrides)
    return FinanceQuerySpec.from_arguments(arguments)


def _cutoff() -> InformationCutoff:
    return InformationCutoff(date(2026, 7, 24), "requested")


def test_query_filters_rows_and_enforces_information_cutoff(market_db: Path) -> None:
    result = FinanceQuery(market_db).run(
        _market_spec(),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert [row["trade_date"] for row in result.rows] == [
        "2026-07-21",
        "2026-07-24",
    ]
    assert [row["index_return_pct"] for row in result.rows] == [1.2, -0.4]
    assert [item.source_date for item in result.evidence] == [
        "2026-07-21",
        "2026-07-24",
    ]
    assert "2026-07-25" not in result.observation
    assert result.served_date == "2026-07-24"


def test_market_query_accepts_provider_natural_count_alias(market_db: Path) -> None:
    result = FinanceQuery(market_db).run(
        _market_spec(metrics=["limit_up_count"], dimensions=["trade_date"]),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert [row["limit_up"] for row in result.rows] == [80, 52]


def test_filter_values_are_bound_parameters_not_sql(market_db: Path) -> None:
    spec = _market_spec(
        filters=[
            {
                "field": "market_stage",
                "op": "eq",
                "value": "反弹阶段' OR 1=1 --",
            }
        ]
    )

    result = FinanceQuery(market_db).run(
        spec,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert result.rows == ()
    assert "OR 1=1" not in result.audit.physical_sql


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"dataset": "secret_table"}, "unknown dataset"),
        ({"metrics": ["physical_column"]}, "unknown field"),
        (
            {
                "filters": [
                    {"field": "market_stage", "op": "sql", "value": "x"}
                ]
            },
            "unsupported operator",
        ),
        (
            {"order_by": [{"field": "limit_up", "direction": "desc"}]},
            "order field must be selected",
        ),
    ],
)
def test_invalid_semantics_fail_before_database_access(
    tmp_path: Path,
    override: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(FinanceQueryValidationError, match=match):
        FinanceQuery(tmp_path / "missing.duckdb").run(
            _market_spec(**override),
            information_cutoff=_cutoff(),
            deadline=ResearchDeadline.from_timeout(2.0),
        )


def test_time_range_cannot_cross_information_cutoff(market_db: Path) -> None:
    with pytest.raises(FinanceQueryValidationError, match="information cutoff"):
        FinanceQuery(market_db).run(
            _market_spec(
                time_range={"start": "2026-07-20", "end": "2026-07-25"}
            ),
            information_cutoff=_cutoff(),
            deadline=ResearchDeadline.from_timeout(2.0),
        )


def test_group_by_uses_registered_aggregation_semantics(market_db: Path) -> None:
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "sector_daily",
            "metrics": ["amount", "return_pct"],
            "dimensions": ["sector_name"],
            "filters": [],
            "time_range": {"start": "2026-07-23", "end": "2026-07-24"},
            "group_by": ["sector_name"],
            "order_by": [{"field": "amount", "direction": "desc"}],
            "limit": 10,
        }
    )

    result = FinanceQuery(market_db).run(
        spec,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert result.rows == (
        {
            "sector_name": "电力",
            "amount": 1200.0,
            "return_pct": 2.5,
        },
        {"sector_name": "银行", "amount": 900.0, "return_pct": -1.0},
    )
    assert result.evidence[0].source_date == "2026-07-24"


def test_evidence_has_semantic_lineage_without_public_physical_schema(
    market_db: Path,
) -> None:
    result = FinanceQuery(market_db).run(
        _market_spec(limit=1),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    item = result.evidence[0]
    assert item.tool == "finance_query"
    assert item.evidence_tier == "L4_structured"
    assert item.source == "本地结构化数据 · 市场日频总览"
    assert item.independent_key == "duckdb:market_daily:2026-07-21"
    assert item.internal_locator.startswith("finance-query:")
    assert item.content_hash
    assert "fact_market_daily" not in item.detail
    assert "fact_market_daily" not in result.observation
    assert "fact_market_daily" in result.audit.physical_sql


def test_hard_row_cap_clamps_model_limit(market_db: Path) -> None:
    result = FinanceQuery(
        market_db,
        limits=FinanceQueryLimits(max_rows=1, max_bytes=100_000, timeout=2.0),
    ).run(
        _market_spec(limit=200),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert len(result.rows) == 1
    assert result.audit.applied_limit == 1


def test_byte_cap_fails_closed(market_db: Path) -> None:
    with pytest.raises(FinanceQueryLimitExceeded, match="byte limit"):
        FinanceQuery(
            market_db,
            limits=FinanceQueryLimits(max_rows=20, max_bytes=10, timeout=2.0),
        ).run(
            _market_spec(),
            information_cutoff=_cutoff(),
            deadline=ResearchDeadline.from_timeout(2.0),
        )


def test_cancelled_query_never_opens_database(tmp_path: Path) -> None:
    opened = False

    def connect(*_args, **_kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("connection should not open")

    with pytest.raises(FinanceQueryCancelled):
        FinanceQuery(tmp_path / "missing.duckdb", connect=connect).run(
            _market_spec(),
            information_cutoff=_cutoff(),
            deadline=ResearchDeadline.from_timeout(2.0),
            is_cancelled=lambda: True,
        )
    assert opened is False


def test_timeout_interrupts_connection() -> None:
    interrupted = Event()

    class BlockingConnection:
        description = ()

        def execute(self, _sql, _parameters):
            assert interrupted.wait(timeout=1.0)
            raise RuntimeError("interrupted")

        def interrupt(self) -> None:
            interrupted.set()

        def close(self) -> None:
            return None

    def connect(_path: str, *, read_only: bool):
        assert read_only is True
        return BlockingConnection()

    started = time.monotonic()
    with pytest.raises(FinanceQueryTimedOut):
        FinanceQuery(
            Path("unused.duckdb"),
            connect=connect,
            limits=FinanceQueryLimits(max_rows=20, max_bytes=10_000, timeout=0.03),
        ).run(
            _market_spec(),
            information_cutoff=_cutoff(),
            deadline=ResearchDeadline.from_timeout(2.0),
        )
    assert interrupted.is_set()
    assert time.monotonic() - started < 0.5


def test_public_schema_is_a_provider_compatible_semantic_object() -> None:
    assert FINANCE_QUERY_PARAMETERS["type"] == "object"
    assert "oneOf" not in FINANCE_QUERY_PARAMETERS
    properties = FINANCE_QUERY_PARAMETERS["properties"]
    datasets = properties["dataset"]["enum"]
    assert "market_daily" in datasets
    assert all(not str(name).startswith("fact_") for name in datasets)
    assert set(FINANCE_QUERY_PARAMETERS["required"]) == {
        "dataset",
        "metrics",
        "dimensions",
    }
    assert "filters" not in FINANCE_QUERY_PARAMETERS["required"]
    assert "time_range" not in FINANCE_QUERY_PARAMETERS["required"]

    minimal = FinanceQuerySpec.from_arguments(
        {
            "dataset": "market_daily",
            "metrics": ["index_return_pct"],
            "dimensions": ["trade_date"],
        }
    )
    assert minimal.dataset == "market_daily"
    assert minimal.filters == ()
    assert minimal.time_range is None
