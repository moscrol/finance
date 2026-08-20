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
        connection.execute(
            """
            create table fact_stock_high_daily(
                trade_date date,
                stock_ts_code varchar,
                stock_name varchar,
                primary_high_period varchar,
                primary_high_label varchar,
                is_new boolean,
                price double,
                pct_chg double,
                pct_chg_10d double,
                amount double,
                market_cap double,
                fund_today double,
                limit_status varchar,
                limit_times integer,
                sw_l1 varchar,
                sw_l2 varchar,
                plate varchar
            )
            """
        )
        connection.executemany(
            "insert into fact_stock_high_daily values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-07-21", "600001.SH", "甲股", "1y", "一年新高",
                    True, 10.0, 5.0, 12.0, 8.0, 100.0, 0.5,
                    "涨停", 2, "电子", "半导体", "半导体",
                ),
                (
                    "2026-07-21", "600002.SH", "乙股", "20d", "20日新高",
                    True, 20.0, 3.0, 8.0, 6.0, 80.0, 0.2,
                    None, 0, "电子", "半导体", "存储芯片",
                ),
                (
                    "2026-07-24", "600003.SH", "丙股", "3y", "三年新高",
                    True, 30.0, 9.9, 25.0, 12.0, 200.0, 1.1,
                    "涨停", 3, "通信", "光模块", "CPO",
                ),
            ],
        )
        connection.execute(
            """
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
        )
        connection.executemany(
            "insert into fact_sector_stock_daily values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-07-21", "S3", "芯片", "600001.SH", "甲股", "电子",
                    "20d", 10.0, 5.0, 6.0, 12.0, 20.0, 8.0, 0.5, 1.0, 50.0,
                ),
                (
                    "2026-07-21", "S3", "芯片", "600009.SH", "丁股", "电子",
                    None, 15.0, 1.0, 2.0, 3.0, 4.0, 30.0, 0.1, 0.2, 90.0,
                ),
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


def test_stock_high_dataset_answers_new_high_structure_directly() -> None:
    """新高家数结构的 canonical 表必须注册在 finance_query 里。

    2026-08-13 A10 实测：该表未注册时，模型只能借道 sector_stock_daily.high_status
    间接拼，被 NULL 主导的分组误导后错误宣告「数据缺口」——数据其实在。
    """
    from intelligence.services.finance_query import _DATASETS

    dataset = _DATASETS["stock_high_daily"]
    assert dataset.table == "fact_stock_high_daily"
    assert "high_period" in dataset.dimensions
    assert "sw_l1" in dataset.dimensions


def test_fupanhui_assets_registered_as_datasets() -> None:
    """入库 ≠ 可消费：复盘会公开资产必须注册进 finance_query 才能被 agent 查到。"""
    from intelligence.services.finance_query import _DATASETS

    expected = {
        "dragon_summary_daily": "fact_dragon_summary_daily",
        "dragon_seat_daily": "fact_dragon_seat_daily",
        "dragon_tiger_daily": "fact_dragon_tiger_daily",
        "core_stock_daily": "fact_core_stock_daily",
        "leader_height_daily": "fact_leader_height_daily",
        "global_index_daily": "fact_global_index_daily",
    }
    for name, table in expected.items():
        assert name in _DATASETS, name
        assert _DATASETS[name].table == table


def test_theme_limit_heat_and_empty_snapshot_are_registered() -> None:
    """A5 要能查题材热度表；C3 空快照也必须作为可查询口径存在。"""
    from intelligence.services.finance_query import _DATASETS

    heat = _DATASETS["theme_limit_heat_daily"]
    assert heat.table == "fact_theme_limit_heat_daily"
    assert "limit_up_count" in heat.metrics
    snapshot = _DATASETS["stock_technical_snapshot"]
    assert snapshot.table == "fact_stock_technical_snapshot"
    assert "deviation_pct" in snapshot.metrics


def test_dragon_seat_query_binds_and_executes(tmp_path: Path) -> None:
    """席位 dataset 端到端：谁买了某股，按净买入排序。"""
    import duckdb

    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table fact_dragon_seat_daily(
                trade_date date, stock_ts_code varchar, stock_name varchar,
                side varchar, seat_no integer, exalter varchar, seat_type varchar,
                hm_name varchar, buy double, sell double, buy_rate double,
                sell_rate double, net_buy double, source varchar, updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_dragon_seat_daily values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("2026-07-24", "600001.SH", "甲股", "buy", 1, "宁波营业部", "游资",
                 "宁波帮", 1.73, 0.0, 11.6, 0.0, 1.73, "s", None),
                ("2026-07-24", "600001.SH", "甲股", "buy", 2, "机构专用", "机构",
                 None, 0.75, 0.25, 5.0, 1.7, 0.50, "s", None),
            ],
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "dragon_seat_daily",
            "metrics": ["net_buy"],
            "dimensions": ["seat_name", "seat_type"],
            "filters": [{"field": "side", "op": "eq", "value": "buy"}],
            "time_range": {"start": "2026-07-24", "end": "2026-07-24"},
            "order_by": [{"field": "net_buy", "direction": "desc"}],
            "limit": 10,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    assert [row["seat_name"] for row in result.rows] == ["宁波营业部", "机构专用"]
    assert result.rows[0]["net_buy"] == 1.73


def test_stock_high_query_groups_by_period(market_db: Path) -> None:
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "stock_high_daily",
            "metrics": ["amount"],
            "dimensions": ["high_period"],
            "time_range": {"start": "2026-07-21", "end": "2026-07-21"},
            "group_by": ["high_period"],
            "order_by": [{"field": "amount", "direction": "desc"}],
            "limit": 10,
        }
    )

    result = FinanceQuery(market_db).run(
        spec,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert {row["high_period"] for row in result.rows} == {"1y", "20d"}
    # 07-24 的丙股被 time_range 排除
    assert all("3y" != row["high_period"] for row in result.rows)


def test_null_high_status_renders_as_fact_not_unknown(market_db: Path) -> None:
    """high_status 的 NULL 是「非新高」这个事实，不是数据缺失。

    渲染成「未知」会让模型把多数个股不是新高误读成数据没回填
    （2026-08-13 A10：GROUP BY high_status 按成交额降序，NULL 组天然最大，
    top25 全「未知」→ 模型错误宣告数据缺口）。
    """
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "sector_stock_daily",
            "metrics": ["amount"],
            "dimensions": ["trade_date", "stock_name", "high_status"],
            "time_range": {"start": "2026-07-21", "end": "2026-07-21"},
            "limit": 10,
        }
    )

    result = FinanceQuery(market_db).run(
        spec,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert "新高状态=非新高" in result.observation
    assert "新高状态=未知" not in result.observation
    # 有值的行照常显示
    assert "新高状态=20d" in result.observation


def test_null_display_defaults_to_unknown_for_other_fields(market_db: Path) -> None:
    """null_label 只改声明了业务语义的字段；其他字段 NULL 仍显示「未知」。"""
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "stock_high_daily",
            "metrics": ["price"],
            "dimensions": ["trade_date", "stock_name", "limit_status"],
            "time_range": {"start": "2026-07-21", "end": "2026-07-21"},
            "limit": 10,
        }
    )

    result = FinanceQuery(market_db).run(
        spec,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    # limit_status 声明了 null_label="非涨停"
    assert "涨停状态=非涨停" in result.observation
    assert "涨停状态=涨停" in result.observation


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
    # time_range + 日期升序 + LIMIT 1：取数倒序保住窗口末端（07-24），不是窗口起点。
    assert item.independent_key == "duckdb:market_daily:2026-07-24"
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


class TestSchemaExamplesAreRunnable:
    """写进参数描述的每个例子，都必须真的能通过校验。

    ai-agent-book ch4 §工具描述的艺术要求参数描述用**具体的例子**代替抽象规范
    （族 A 官方 custom-tools 同样示范 `.describe("… e.g. kilometers")`，A×C 跨族
    一致）。但一个**跑不通的例子比没有例子更糟**——它把错误模式直接教给模型。

    2026-08-12 写这批描述时，靠人眼审查连漏两次：
      ① order_by 多字段例子用了 rank+amount，实跑报 `order field must be
         selected: rank` —— 排序字段必须先出现在 metrics/dimensions 里，
         这条约束只写在 _compile_query 里，看 schema 完全看不出来
      ② 改完又用 rank 配 sector_daily，实跑报 `unknown field: rank` ——
         rank 只存在于 mainline_theme_daily。**我自己踩了一遍跨 dataset 混用**

    所以这条门禁是必需的：例子的正确性不能靠写的人细心。

    ``examples`` 同时充当「例子的真本源」：每条既要跑通，也要逐字出现在对应
    描述里。少了后半条，测试和描述会各自漂移，而漂移时两边都发绿。
    """

    # (属性名, 完整可执行查询, 该查询里必须逐字出现在描述中的片段)
    examples = [
        (
            "time_range",
            {
                "dataset": "market_daily",
                "metrics": ["total_amount", "limit_up"],
                "dimensions": ["trade_date"],
                "time_range": {"start": "2026-07-23", "end": "2026-07-23"},
            },
            '{"start": "2026-07-23", "end": "2026-07-23"}',
        ),
        (
            "filters",
            {
                "dataset": "sector_daily",
                "metrics": ["amount"],
                "dimensions": ["sector_name"],
                "filters": [{"field": "return_pct", "op": "gt", "value": 0}],
            },
            '[{"field": "return_pct", "op": "gt", "value": 0}]',
        ),
        (
            "filters",
            {
                "dataset": "sector_daily",
                "metrics": ["amount"],
                "dimensions": ["sector_name"],
                "filters": [
                    {
                        "field": "sector_name",
                        "op": "in",
                        "value": ["电网设备", "光伏设备"],
                    }
                ],
            },
            '"value": ["电网设备", "光伏设备"]',
        ),
        (
            "order_by",
            {
                "dataset": "sector_daily",
                "metrics": ["strength"],
                "dimensions": ["sector_name"],
                "order_by": [{"field": "strength", "direction": "desc"}],
            },
            '[{"field": "strength", "direction": "desc"}]',
        ),
        (
            "order_by",
            {
                "dataset": "sector_daily",
                "metrics": ["strength", "amount"],
                "dimensions": ["sector_name"],
                "order_by": [
                    {"field": "strength", "direction": "desc"},
                    {"field": "amount", "direction": "desc"},
                ],
            },
            '{"field": "amount", "direction": "desc"}',
        ),
        (
            "group_by",
            {
                "dataset": "sector_daily",
                "metrics": ["amount"],
                "dimensions": ["sector_name"],
                "group_by": ["sector_name"],
            },
            '["sector_name"]',
        ),
    ]

    @pytest.mark.parametrize("prop,query,snippet", examples)
    def test_example_passes_the_real_validation_chain(
        self, prop: str, query: dict, snippet: str
    ) -> None:
        """走生产同一条链，停在编译（纯 SQL 构造，不需要 DB）。"""
        from intelligence.services.finance_query import _compile_query, normalize_spec
        from intelligence.services.research_contract import InformationCutoff

        spec = FinanceQuerySpec.from_arguments(query)
        normalized, _ = normalize_spec(spec)

        _compile_query(
            normalized,
            information_cutoff=InformationCutoff(date(2026, 7, 23), "requested"),
            max_rows=25,
        )

    @pytest.mark.parametrize("prop,query,snippet", examples)
    def test_example_actually_appears_in_the_description(
        self, prop: str, query: dict, snippet: str
    ) -> None:
        """跑得通但没写进描述，等于没给模型看——两边都要成立才算数。"""
        description = FINANCE_QUERY_PARAMETERS["properties"][prop]["description"]

        assert snippet in description

    def test_order_by_description_states_the_array_shape(self) -> None:
        """2026-08-12 实测的头号错法：13 次调用 9 次把 order_by 写成单个对象。

        schema 本来就写着 "type": "array"——**光有类型挡不住**。
        """
        description = FINANCE_QUERY_PARAMETERS["properties"]["order_by"]["description"]

        assert "数组" in description
        assert "只排一个字段也要用方括号" in description

    def test_order_by_description_states_the_selection_constraint(self) -> None:
        """排序字段必须已在 metrics/dimensions 里（_compile_query 的隐藏约束）。"""
        description = FINANCE_QUERY_PARAMETERS["properties"]["order_by"]["description"]

        assert "必须已经出现在 metrics 或 dimensions" in description

    def test_time_range_description_carries_an_iso_example(self) -> None:
        """解析是 date.fromisoformat(value[:10])，ISO 是唯一可靠写法。

        ch4 §3 点名这类隐式约定（「时间戳到底是秒还是毫秒」）靠例子最容易传达。
        """
        properties = FINANCE_QUERY_PARAMETERS["properties"]["time_range"]["properties"]

        for endpoint in ("start", "end"):
            assert "2026-07-23" in properties[endpoint]["description"]


def test_dataset_catalog_covers_every_dataset() -> None:
    """schema 里的目录必须逐张覆盖注册表，否则手抄的那份会悄悄漂。

    钉的是「生成」这件事本身：新增 dataset 却忘了写 coverage，这条会红。
    """
    from intelligence.services.finance_query import (
        _DATASETS,
        FINANCE_QUERY_PARAMETERS,
    )

    description = FINANCE_QUERY_PARAMETERS["properties"]["dataset"]["description"]
    for name, definition in _DATASETS.items():
        assert f"- {name}（" in description, f"{name} 不在 schema 目录里"
        assert definition.coverage, f"{name} 没写 coverage"


def test_coverage_advisory_fires_on_the_real_a5_query() -> None:
    """A5 现场那条逐字复刻：子集表上按 limit_up_count 取 top15。

    参数取自 2026-08-18 纯尺子跑的 episode 账本，不是构造的。
    """
    from intelligence.services.finance_query import (
        FinanceQuerySpec,
        Order,
        coverage_advisory,
    )

    advisory = coverage_advisory(
        FinanceQuerySpec(
            dataset="mainline_sector_daily",
            dimensions=("theme_name", "sector_name"),
            metrics=("limit_up_count", "return_pct", "strength"),
            order_by=(Order("limit_up_count", "desc"),),
            limit=15,
        )
    )
    assert "theme_limit_heat_daily" in advisory
    # 只对排序字段提示：return_pct 六张表都有，列出来会把真信号淹掉。
    assert "return_pct" not in advisory


def test_coverage_advisory_is_silent_on_legitimate_subset_use() -> None:
    """取某个具体标的在子集表里的值是正当用法，不排序就不该出声。

    反向断言：没有这条，提示会挂在每一次子集查询上变成噪声。
    """
    from intelligence.services.finance_query import (
        FinanceQuerySpec,
        QueryFilter,
        coverage_advisory,
    )

    assert (
        coverage_advisory(
            FinanceQuerySpec(
                dataset="mainline_sector_daily",
                dimensions=("sector_name",),
                metrics=("limit_up_count",),
                filters=(QueryFilter("sector_name", "eq", "储能"),),
            )
        )
        == ""
    )


def test_coverage_advisory_is_silent_on_full_population_dataset() -> None:
    from intelligence.services.finance_query import (
        FinanceQuerySpec,
        Order,
        coverage_advisory,
    )

    assert (
        coverage_advisory(
            FinanceQuerySpec(
                dataset="theme_limit_heat_daily",
                dimensions=("sector_name",),
                metrics=("limit_up_count",),
                order_by=(Order("limit_up_count", "desc"),),
                limit=10,
            )
        )
        == ""
    )
