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
        "event_daily": "fact_event_daily",
        "regulation_pool_daily": "fact_regulation_pool_daily",
        "regulation_event_daily": "fact_regulation_event_daily",
        "historical_mapping": "fact_historical_mapping",
    }
    for name, table in expected.items():
        assert name in _DATASETS, name
        assert _DATASETS[name].table == table
    event = _DATASETS["event_daily"]
    assert event.allow_future_time_range is True
    assert event.cutoff_column == "updated_at"
    assert event.coverage


def test_event_daily_allows_scheduled_dates_beyond_cutoff(tmp_path: Path) -> None:
    """事件发生日可以晚于信息截止日；信息时点打在 updated_at。

    2026-08-23：周日问下周大事，cutoff 是上一个 A 股交易日。若不把
    time_field 和信息日拆开，time_range 直接被拒，库里的英伟达/Jackson
    Hole 永远查不到。
    """
    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table fact_event_daily(
                event_date date, event_id varchar, title varchar, content varchar,
                importance integer, event_type varchar, source_types varchar,
                sectors varchar, is_future boolean, source varchar,
                updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_event_daily values (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    "2026-08-21", "e-past", "国常会", "", 5, None, None, None,
                    False, "fupanhui", "2026-08-21 15:00:00",
                ),
                (
                    "2026-08-26", "e-nvda", "英伟达2026Q2财报", "", 5, None,
                    None, None, True, "fupanhui", "2026-08-21 15:43:00",
                ),
                (
                    "2026-08-27", "e-jh", "杰克逊霍尔全球央行年会",
                    "美联储主席讲话", 6, None, None, None, True, "fupanhui",
                    "2026-08-21 15:43:00",
                ),
                (
                    "2026-08-28", "e-late", "事后才知道的事件", "", 9, None,
                    None, None, True, "fupanhui", "2026-08-24 10:00:00",
                ),
            ],
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "event_daily",
            "metrics": ["importance"],
            "dimensions": ["event_date", "title", "is_future"],
            "time_range": {"start": "2026-08-24", "end": "2026-08-28"},
            "order_by": [{"field": "event_date", "direction": "asc"}],
            "limit": 20,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 8, 21), "requested"),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    titles = [row["title"] for row in result.rows]
    assert titles == ["英伟达2026Q2财报", "杰克逊霍尔全球央行年会"]
    assert result.served_date == "2026-08-21"
    assert {item.source_date for item in result.evidence} == {"2026-08-21"}


def _write_event_daily(path: Path, rows: list[tuple[object, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            create table fact_event_daily(
                event_date date, event_id varchar, title varchar, content varchar,
                importance integer, event_type varchar, source_types varchar,
                sectors varchar, is_future boolean, source varchar,
                updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_event_daily values (?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
    finally:
        con.close()


def test_event_daily_shared_last_touch_after_cutoff_returns_empty(
    tmp_path: Path,
) -> None:
    """生产形态：future 行每次 sync 都把 updated_at 刷成同一次墙钟。

    补跑若落在比 cutoff 更晚的日历日，整窗 0 行，长得像「稀疏表本来没有」。
    """
    db_path = tmp_path / "market_feature_store.duckdb"
    _write_event_daily(
        db_path,
        [
            (
                "2026-08-26", "e-nvda", "英伟达2026Q2财报", "", 5, None,
                None, None, True, "fupanhui", "2026-08-22 03:43:00",
            ),
            (
                "2026-08-27", "e-jh", "杰克逊霍尔全球央行年会", "", 6, None,
                None, None, True, "fupanhui", "2026-08-22 03:43:00",
            ),
        ],
    )
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "event_daily",
            "metrics": ["importance"],
            "dimensions": ["event_date", "title"],
            "time_range": {"start": "2026-08-24", "end": "2026-08-28"},
            "limit": 20,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 8, 21), "requested"),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    assert result.rows == ()


def test_event_daily_survives_registry_future_dated_filter(tmp_path: Path) -> None:
    """产品路径：registry fetch 的 filter_future_dated 不得把发生日当信息日。"""
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_tools import build_episode_registry
    from intelligence.services.task_frame import TaskFrame

    db_path = tmp_path / "finance" / "db" / "market_feature_store.duckdb"
    _write_event_daily(
        db_path,
        [
            (
                "2026-08-26", "e-nvda", "英伟达2026Q2财报", "", 5, None,
                None, None, True, "fupanhui", "2026-08-21 15:43:00",
            ),
            (
                "2026-08-27", "e-jh", "杰克逊霍尔全球央行年会", "", 6, None,
                None, None, True, "fupanhui", "2026-08-21 15:43:00",
            ),
            (
                "2026-08-28", "e-late", "事后才知道的事件", "", 9, None,
                None, None, True, "fupanhui", "2026-08-24 10:00:00",
            ),
        ],
    )
    frame = TaskFrame(
        raw_question="周末发酵了什么新闻？下周（8月24日-8月28日）有什么大事？",
        user_goal="盘点周末消息与下周日程",
        question_type="general_finance_qa",
        subject="下周大事",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="8月",
        required_outputs=("direct_answer", "evidence_boundary"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.4,
    )
    context = build_episode_context(
        frame,
        task_id="event-daily-registry-path",
        capabilities=("finance_query",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-08-23",
        latest_data_date="2026-08-21",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )
    assert "event_daily" in registry.resolve("finance_query").description
    observation = registry.execute(
        "finance_query",
        {
            "dataset": "event_daily",
            "metrics": ["importance"],
            "dimensions": ["event_date", "title", "is_future"],
            "time_range": {"start": "2026-08-24", "end": "2026-08-28"},
            "order_by": [{"field": "event_date", "direction": "asc"}],
            "limit": 20,
        },
        context=context,
        step_id="event-daily-registry-path:1",
    )
    titles = [item.title for item in observation.evidence]
    details = " ".join(item.detail for item in observation.evidence)
    assert observation.trace.status != "future_of_cutoff"
    assert "晚于问句日" not in observation.observation
    assert "晚于问句日" not in "".join(titles)
    assert "英伟达2026Q2财报" in details
    assert "杰克逊霍尔全球央行年会" in details
    assert "事后才知道的事件" not in details
    assert {item.source_date for item in observation.evidence} == {"2026-08-21"}


def test_market_daily_still_rejects_time_range_past_cutoff(market_db: Path) -> None:
    """日历的未来窗不得演变成行情表也能查未来交易日。"""
    with pytest.raises(FinanceQueryValidationError, match="information cutoff"):
        FinanceQuery(market_db).run(
            _market_spec(time_range={"start": "2026-07-20", "end": "2026-07-30"}),
            information_cutoff=_cutoff(),
            deadline=ResearchDeadline.from_timeout(2.0),
        )


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


def test_auction_panel_cap_is_declared_in_coverage() -> None:
    """竞价看板每面板每日只收 top10——这是全表最容易被误用的地方。

    实测 2026-08-18：`zt` 面板 10 行，而前一日真实涨停 106 只。模型若拿本表回答
    「昨天多少只涨停」会少一个数量级，而字段校验一声不吭（`limit_seq`/`pct_chg`
    都是这张表的合法列）。所以上限和「该问谁」必须在 coverage 里，模型下单前可见。
    """

    from intelligence.services.finance_query import _DATASETS

    assert "auction_stock_daily" in _DATASETS
    definition = _DATASETS["auction_stock_daily"]
    assert definition.table == "fact_auction_stock_daily"
    assert definition.population == "subset"
    assert "top 10" in definition.coverage
    # 必须指出正确的替代口径，否则模型只知道「不能用」不知道「该用谁」
    assert "market_daily.limit_up" in definition.coverage


def test_sw_l1_is_full_universe_with_dated_incompleteness() -> None:
    """申万一级的宇宙是 31 个行业，近端已齐；残缺是时间问题，不是结构子集。

    两道失败形状不能共用 population=subset：那面会让 catalog 把近端合法排名
    说成「子集内部名次」，事后 advisory 再把模型推向 stock_daily / 龙虎榜。
    分界日必须是机器可读的 incomplete_before，不能只活在散文里。
    """

    from intelligence.services.finance_query import _DATASETS

    assert "sw_l1_daily" in _DATASETS
    definition = _DATASETS["sw_l1_daily"]
    assert definition.table == "fact_sw_l1_daily"
    assert definition.population == "full"
    assert definition.incomplete_before == date(2026, 6, 5)
    assert "2026-06-05" in definition.coverage, "分界日要写进 coverage，模型下单前就得看见"
    # 概念板块加总会大于全市，不能当行业成交额的替代路径
    assert "维度聚合" not in definition.coverage
    # 低可用率字段不开放为指标：一个几乎恒空的 metric 与空 dataset 是同一种病
    assert "fupanhui_ratio" not in definition.metrics
    assert "amount_ma120_ratio" not in definition.metrics
    # 成交额也不开放：库里那列不是「亿」（写入侧未换算，实测比值≈100 即百万元），
    # 而语义层八处成交额统一「亿」。放进来就得放宽 test_amount_metric_labels_carry_unit——
    # 那是改门禁迁就代码。这条钉住「宁可少一个指标，不混两种口径」。
    assert "amount" not in definition.metrics


def test_sw_l1_query_binds_and_executes(tmp_path: Path) -> None:
    """行业 dataset 端到端：某日按涨幅排行业。"""
    import duckdb

    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table fact_sw_l1_daily(
                trade_date date, sw_l1_code varchar, sw_l1 varchar,
                close double, pre_close double, pct_chg double, amount double,
                fupanhui_ratio double, source varchar, updated_at timestamp,
                amount_ma120 double, amount_ma120_ratio double
            )
            """
        )
        con.executemany(
            "insert into fact_sw_l1_daily values (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("2026-07-24", "801950", "煤炭", 3000.0, 2932.0, 2.30, 16605.0,
                 None, "akshare", None, None, None),
                ("2026-07-24", "801780", "银行", 5000.0, 4937.0, 1.27, 31856.0,
                 None, "akshare", None, None, None),
            ],
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "sw_l1_daily",
            "metrics": ["return_pct"],
            "dimensions": ["sw_l1"],
            "time_range": {"start": "2026-07-24", "end": "2026-07-24"},
            "order_by": [{"field": "return_pct", "direction": "desc"}],
            "limit": 10,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    assert [row["sw_l1"] for row in result.rows] == ["煤炭", "银行"]
    assert result.rows[0]["return_pct"] == 2.30


def test_sw_l1_rejects_amount_metric() -> None:
    """amount 在全局枚举里（个股/板块成交额），但本表不能要。"""

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "sw_l1_daily",
            "metrics": ["amount"],
            "dimensions": ["sw_l1"],
            "time_range": {"start": "2026-08-24", "end": "2026-08-24"},
        }
    )
    with pytest.raises(FinanceQueryValidationError, match="unknown field: amount"):
        FinanceQuery("/nonexistent.duckdb").run(
            spec,
            information_cutoff=_cutoff(),
            deadline=ResearchDeadline.from_timeout(2.0),
        )


def _sw_l1_rank_spec(**time_range: str) -> FinanceQuerySpec:
    payload: dict[str, object] = {
        "dataset": "sw_l1_daily",
        "metrics": ["return_pct"],
        "dimensions": ["sw_l1"],
        "order_by": [{"field": "return_pct", "direction": "desc"}],
        "limit": 5,
    }
    if time_range:
        payload["time_range"] = time_range
    return FinanceQuerySpec.from_arguments(payload)


def test_sw_l1_advisory_is_silent_on_complete_window() -> None:
    """06-05 起 31/31，按涨幅排行业是该宇宙的合法全集排名，不该喊去个股表。"""
    from intelligence.services.finance_query import coverage_advisory

    advisory = coverage_advisory(
        _sw_l1_rank_spec(start="2026-08-24", end="2026-08-24")
    )
    assert advisory == ""


def test_sw_l1_advisory_warns_on_incomplete_window_without_wrong_grain() -> None:
    """残缺窗上排序必须出声，且不能把模型推向个股/概念板块。"""
    from intelligence.services.finance_query import coverage_advisory

    advisory = coverage_advisory(
        _sw_l1_rank_spec(start="2026-03-10", end="2026-03-10")
    )
    assert "2026-06-05" in advisory
    assert "stock_daily" not in advisory
    assert "sector_daily" not in advisory
    assert "dragon_tiger_daily" not in advisory


def test_sw_l1_advisory_fail_closed_without_time_range() -> None:
    """没给日期就不知道落在哪一段——认不出来就警告，不能静默当全集。"""
    from intelligence.services.finance_query import coverage_advisory

    advisory = coverage_advisory(_sw_l1_rank_spec())
    assert "2026-06-05" in advisory
    assert "stock_daily" not in advisory


def test_regulation_pool_is_subset_and_hides_fraction_returns() -> None:
    """安全池是子集；涨幅列是小数不是百分数，开放会被读成 0.51%。"""
    from intelligence.services.finance_query import _DATASETS

    definition = _DATASETS["regulation_pool_daily"]
    assert definition.table == "fact_regulation_pool_daily"
    assert definition.population == "subset"
    assert definition.time_field == "effective_date"
    assert definition.cutoff_column is None
    assert "return_pct" not in definition.metrics
    assert "pct_chg_10d" not in definition.metrics
    assert "pct_chg_30d" not in definition.metrics
    assert "close" not in definition.metrics
    assert "小数" in definition.coverage
    assert "并非逐日相等" in definition.coverage


def test_regulation_pool_rejects_return_pct() -> None:
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "regulation_pool_daily",
            "metrics": ["return_pct"],
            "dimensions": ["stock_name"],
            "time_range": {"start": "2026-08-24", "end": "2026-08-24"},
        }
    )
    with pytest.raises(FinanceQueryValidationError, match="unknown field: return_pct"):
        FinanceQuery("/nonexistent.duckdb").run(
            spec,
            information_cutoff=InformationCutoff(date(2026, 8, 24), "requested"),
            deadline=ResearchDeadline.from_timeout(2.0),
        )


def test_regulation_pool_query_lists_safe_names(tmp_path: Path) -> None:
    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table fact_regulation_pool_daily(
                effective_date date, stock_ts_code varchar, stock_name varchar,
                pool_status varchar, close double, pct_chg_10d double,
                safe_space_10d double, safe_days_10d integer,
                pct_chg_30d double, safe_space_30d double,
                source varchar, updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_regulation_pool_daily values (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("2026-08-24", "603188.SH", "华民股份", "safe", 9.6, 0.507,
                 0.30, 1, 0.92, 0.2, "fupanhui", None),
                ("2026-08-24", "002412.SZ", "汉森制药", "safe", 11.21, 0.550,
                 0.27, 2, 0.84, 0.1, "fupanhui", None),
            ],
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "regulation_pool_daily",
            "metrics": ["safe_days_10d"],
            "dimensions": ["stock_name", "pool_status"],
            "time_range": {"start": "2026-08-24", "end": "2026-08-24"},
            "order_by": [{"field": "safe_days_10d", "direction": "desc"}],
            "limit": 10,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 8, 24), "requested"),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    assert [row["stock_name"] for row in result.rows] == ["汉森制药", "华民股份"]
    assert {item.source_date for item in result.evidence} == {"2026-08-24"}


def test_regulation_pool_advisory_stays_on_unique_rank_field() -> None:
    """按池内独有字段排序，不得改写成个股涨幅榜。"""
    from intelligence.services.finance_query import coverage_advisory

    advisory = coverage_advisory(
        FinanceQuerySpec.from_arguments(
            {
                "dataset": "regulation_pool_daily",
                "metrics": ["safe_days_10d"],
                "dimensions": ["stock_name"],
                "order_by": [{"field": "safe_days_10d", "direction": "desc"}],
                "limit": 10,
            }
        )
    )
    assert "stock_daily" not in advisory
    assert "dragon_tiger_daily" not in advisory


def test_regulation_event_uses_snapshot_axis_not_end_date() -> None:
    """end_date 89% 在未来；当时间轴会让整批被判成晚于问句日。"""
    from intelligence.services.finance_query import _DATASETS

    definition = _DATASETS["regulation_event_daily"]
    assert definition.table == "fact_regulation_event_daily"
    assert definition.time_field == "effective_date"
    assert definition.allow_future_time_range is False
    assert definition.cutoff_column is None
    assert definition.fields["end_date"].role == "dimension"
    assert definition.fields["start_date"].role == "dimension"
    assert "end_date" in definition.coverage
    assert "days_remaining" in definition.metrics


def test_regulation_event_future_end_does_not_become_source_date(
    tmp_path: Path,
) -> None:
    """快照日是信息日。end_date 在未来不得流进 evidence.source_date。"""
    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table fact_regulation_event_daily(
                effective_date date, stock_ts_code varchar, stock_name varchar,
                start_date date, end_date date, days_remaining_trading integer,
                status_type varchar, event_type varchar, event_types varchar,
                leader_plate varchar, source varchar, updated_at timestamp
            )
            """
        )
        con.execute(
            "insert into fact_regulation_event_daily values (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "2026-08-24", "002422.SZ", "一鸣食品",
                "2026-08-19", "2026-09-01", 7,
                "normal", "severe_abnormal_volatility", None,
                "大消费", "fupanhui", None,
            ),
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "regulation_event_daily",
            "metrics": ["days_remaining"],
            "dimensions": ["stock_name", "start_date", "end_date"],
            "time_range": {"start": "2026-08-24", "end": "2026-08-24"},
            "limit": 10,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 8, 24), "requested"),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    assert [row["stock_name"] for row in result.rows] == ["一鸣食品"]
    assert result.rows[0]["end_date"] == "2026-09-01"
    assert {item.source_date for item in result.evidence} == {"2026-08-24"}


def test_historical_mapping_aliases_source_date_as_as_of() -> None:
    """表列 source_date 与证据层 source_date 同名不同义，靠别名隔离，不靠换列。"""
    from intelligence.services.finance_query import _DATASETS

    definition = _DATASETS["historical_mapping"]
    assert definition.table == "fact_historical_mapping"
    assert definition.time_field == "as_of"
    assert definition.fields["as_of"].column == "source_date"
    assert definition.fields["similar_date"].column == "similar_date"
    assert definition.time_field != "similar_date"
    assert definition.population == "full"
    assert definition.cutoff_column is None
    assert "接口空" in definition.coverage
    assert "回填" in definition.coverage
    assert "每日固定 2" not in definition.coverage
    assert "碰巧对齐" not in definition.coverage


def test_historical_mapping_cutoff_uses_as_of_not_similar_date(
    tmp_path: Path,
) -> None:
    """若把 similar_date 当时间轴，后来才算出的映射会漏进更早的问句。"""
    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table fact_historical_mapping(
                source_date date, similar_date date, similarity double,
                external_cycle varchar, cycle_day integer, summary varchar,
                source varchar, updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_historical_mapping values (?,?,?,?,?,?,?,?)",
            [
                ("2026-08-18", "2024-01-15", 90.0, "底部横盘阶段", 5,
                 "早", "fupanhui", None),
                ("2026-08-24", "2024-01-10", 91.0, "底部横盘阶段", 12,
                 "晚", "fupanhui", None),
            ],
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "historical_mapping",
            "metrics": ["similarity"],
            "dimensions": ["as_of", "similar_date", "summary"],
            "order_by": [{"field": "similarity", "direction": "desc"}],
            "limit": 10,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 8, 20), "requested"),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    assert [row["as_of"] for row in result.rows] == ["2026-08-18"]
    assert [row["similar_date"] for row in result.rows] == ["2024-01-15"]
    assert {item.source_date for item in result.evidence} == {"2026-08-18"}


def test_historical_mapping_rejects_future_as_of() -> None:
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "historical_mapping",
            "metrics": ["similarity"],
            "dimensions": ["similar_date"],
            "time_range": {"start": "2026-08-24", "end": "2026-08-24"},
        }
    )
    with pytest.raises(FinanceQueryValidationError, match="information cutoff"):
        FinanceQuery("/nonexistent.duckdb").run(
            spec,
            information_cutoff=InformationCutoff(date(2026, 8, 10), "requested"),
            deadline=ResearchDeadline.from_timeout(2.0),
        )


def test_historical_mapping_aliased_time_keeps_window_end(tmp_path: Path) -> None:
    """time_field 是语义别名时，T1b 仍须保住窗口末端，不能按物理列名反查失败后静默关掉。"""
    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table fact_historical_mapping(
                source_date date, similar_date date, similarity double,
                external_cycle varchar, cycle_day integer, summary varchar,
                source varchar, updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_historical_mapping values (?,?,?,?,?,?,?,?)",
            [
                (day, "2024-01-10", 80.0 + index, None, None, f"d{index}",
                 "fupanhui", None)
                for index, day in enumerate(
                    ("2026-08-18", "2026-08-19", "2026-08-20",
                     "2026-08-21", "2026-08-24")
                )
            ],
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "historical_mapping",
            "metrics": ["similarity"],
            "dimensions": ["as_of"],
            "time_range": {"start": "2026-08-18", "end": "2026-08-24"},
            "order_by": [{"field": "as_of", "direction": "asc"}],
            "limit": 2,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 8, 24), "requested"),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    assert [row["as_of"] for row in result.rows] == ["2026-08-21", "2026-08-24"]


def test_historical_mapping_max_date_resolves_aliased_time_field(
    tmp_path: Path,
) -> None:
    """筛子集停在更早时，全集 max 探针必须认得 as_of，不能因物理列对不上返回 None。"""
    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table fact_historical_mapping(
                source_date date, similar_date date, similarity double,
                external_cycle varchar, cycle_day integer, summary varchar,
                source varchar, updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_historical_mapping values (?,?,?,?,?,?,?,?)",
            [
                ("2026-08-18", "2024-01-15", 90.0, None, None, "早",
                 "fupanhui", None),
                ("2026-08-24", "2024-01-10", 91.0, None, None, "晚",
                 "fupanhui", None),
            ],
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "historical_mapping",
            "metrics": ["similarity"],
            "dimensions": ["as_of", "similar_date"],
            "filters": [
                {"field": "similar_date", "op": "eq", "value": "2024-01-15"}
            ],
            "limit": 10,
        }
    )
    engine = FinanceQuery(db_path)
    cutoff = InformationCutoff(date(2026, 8, 24), "requested")
    deadline = ResearchDeadline.from_timeout(2.0)
    filtered = engine.run(
        spec, information_cutoff=cutoff, deadline=deadline
    )
    assert filtered.served_date == "2026-08-18"
    assert engine.dataset_max_date(
        spec, information_cutoff=cutoff, deadline=deadline
    ) == "2026-08-24"


def test_stock_technical_registered_as_dataset() -> None:
    """UP 线/偏离度：203 万行日更资产，此前入库但语义层查不到。"""
    from intelligence.services.finance_query import _DATASETS

    assert "stock_technical_daily" in _DATASETS
    definition = _DATASETS["stock_technical_daily"]
    assert definition.table == "feature_stock_technical_daily"
    # population=full 但有 ~0.4% 缺行（不满 26 日的新股/停牌股），coverage 必须讲明
    # 「缺行 ≠ 没偏离」，否则模型会把算不出读成没偏离。
    assert definition.population == "full"
    assert "缺行" in definition.coverage


def test_stock_technical_query_filters_by_deviation(tmp_path: Path) -> None:
    """端到端：筛出站上 UP 线的个股（filter 作用在 metric 上）。"""
    import duckdb

    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            create table feature_stock_technical_daily(
                trade_date date, stock_ts_code varchar, stock_name varchar,
                close double, ma26 double, std26 double, up_value double,
                deviation_pct double, calculated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into feature_stock_technical_daily values (?,?,?,?,?,?,?,?,?)",
            [
                # UP = ma26 + 0.764*std26；甲站上、乙低于
                ("2026-07-24", "600001.SH", "甲股", 12.0, 10.0, 1.0, 10.764, 11.48, None),
                ("2026-07-24", "600002.SH", "乙股", 9.0, 10.0, 1.0, 10.764, -16.39, None),
            ],
        )
    finally:
        con.close()

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "stock_technical_daily",
            "metrics": ["deviation_pct", "up_value"],
            "dimensions": ["stock_name"],
            "filters": [{"field": "deviation_pct", "op": "gt", "value": 0}],
            "time_range": {"start": "2026-07-24", "end": "2026-07-24"},
            "order_by": [{"field": "deviation_pct", "direction": "desc"}],
            "limit": 10,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )
    assert [row["stock_name"] for row in result.rows] == ["甲股"]
    assert result.rows[0]["deviation_pct"] == 11.48


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


def test_coverage_advisory_does_not_redirect_generic_return_pct() -> None:
    """return_pct 出现在多张全集表上，按字段名找超集会指向错误粒度。

    竞价看板按当日涨幅排序是「这批被选进看板的票今天怎么走」，不是「全市个股排名」。
    指向 stock_daily / 龙虎榜等于换了一个问题。
    """
    from intelligence.services.finance_query import (
        FinanceQuerySpec,
        Order,
        coverage_advisory,
    )

    advisory = coverage_advisory(
        FinanceQuerySpec(
            dataset="auction_stock_daily",
            dimensions=("stock_name", "panel"),
            metrics=("return_pct",),
            order_by=(Order("return_pct", "desc"),),
            limit=10,
        )
    )
    assert "stock_daily" not in advisory
    assert "dragon_tiger_daily" not in advisory
    assert "global_index_daily" not in advisory


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
