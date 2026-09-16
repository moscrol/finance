"""P0 T1/T3：截断可见、锚定日不被 LIMIT 丢掉、requested_time_range、成交额单位。

对应 `docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md` §7.1–7.4、§7.6。
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.finance_query import (
    _DATASETS,
    FinanceQuery,
    FinanceQueryAudit,
    FinanceQuerySpec,
    truncation_notice,
)
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.tool_result_budget import budget_tool_observation


def _lithium_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="2026-07-23 锂矿为什么涨",
        user_goal="判断锂矿当日上涨的主要驱动",
        question_type="theme_analysis",
        subject="锂矿",
        subject_kind="theme",
        market_scope="A股",
        timeframe="2026-07-23",
        required_outputs=("direct_assessment", "evidence_boundary"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )


def _sector_db(path: Path, rows: list[tuple[object, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        create table fact_sector_daily(
            trade_date date,
            sector_ts_code varchar,
            sector_name varchar,
            sw_l1 varchar,
            multi_period_resonance boolean,
            pct_chg double,
            amount double,
            diff_ratio double,
            strength double
        )
        """
    )
    connection.executemany(
        "insert into fact_sector_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.close()


def _registry(tmp_path: Path, *, task_id: str):
    frame = _lithium_frame()
    context = build_episode_context(
        frame,
        task_id=task_id,
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-23",
        latest_data_date="2026-07-23",
    )
    return build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    ), context


def test_truncation_notice_when_model_sets_own_limit(tmp_path: Path) -> None:
    """limit=25 且 applied_limit=25 且 row_count=25 时必须提示截断。

    修前 `normalized.limit > applied_limit` 把 25>25 判假，锂矿这种
    「模型自己写下限」永不提示。
    """

    db_path = tmp_path / "finance" / "db" / "market_feature_store.duckdb"
    _sector_db(
        db_path,
        [
            (
                "2026-07-23",
                f"88{index:04d}.TI",
                f"板块{index}",
                "有色",
                False,
                float(index),
                float(index * 10),
                float(index),
                float(index),
            )
            for index in range(25)
        ],
    )
    registry, context = _registry(tmp_path, task_id="truncation-own-limit")
    observation = registry.execute(
        "finance_query",
        {
            "dataset": "sector_daily",
            "metrics": ["return_pct", "amount"],
            "dimensions": ["trade_date", "sector_code", "sector_name"],
            "filters": [],
            "time_range": {"start": "2026-07-23", "end": "2026-07-23"},
            "group_by": [],
            "order_by": [{"field": "return_pct", "direction": "desc"}],
            "limit": 25,
        },
        context=context,
        step_id="truncation-own-limit:1",
    )

    assert observation.trace.result_count == 25
    assert "截断" in observation.observation
    assert "25" in observation.observation


def test_truncation_notice_survives_the_context_budget(tmp_path: Path) -> None:
    """截断提示必须活过 900 字符预算——不然它等于没发出。

    2026-08-30 实测 400 份 continuous-episode.json：这句提示出现 123 次、
    位置均值在全文 84% 处、**67 次被 ``tool_result_budget`` 吃掉**。也就是说
    「结果已按 N 条截断」这条通知，一半以上的时候自己被字符截断砍了，模型
    拿到删节版却不知道是删节版。「实际覆盖 X..Y」同样 123 次里丢 67 次，
    而时点与完整性正是该模块开头声明永不截断的红线。

    数据行在 ``evidence[]`` 里逐条另有副本（实测被砍片段 92% 有副本），
    这三条限定语没有——所以限定语必须排在前面，砍到的只会是有副本的那部分。

    钉不变量而非顺序：改成独立字段也该通过。变异测试：把 ``episode_tools``
    里的 ``"；".join((*notices, result.observation))`` 换回追加写法，本条必红。
    """

    db_path = tmp_path / "finance" / "db" / "market_feature_store.duckdb"
    _sector_db(
        db_path,
        [
            (
                "2026-07-23",
                f"88{index:04d}.TI",
                f"板块名称够长才撞得到字符预算{index}",
                "有色",
                False,
                float(index),
                float(index * 10),
                float(index),
                float(index),
            )
            for index in range(25)
        ],
    )
    registry, context = _registry(tmp_path, task_id="truncation-survives-budget")
    observation = registry.execute(
        "finance_query",
        {
            "dataset": "sector_daily",
            "metrics": ["return_pct", "amount"],
            "dimensions": ["trade_date", "sector_code", "sector_name"],
            "filters": [],
            "time_range": {"start": "2026-07-23", "end": "2026-07-23"},
            "group_by": [],
            "order_by": [{"field": "return_pct", "direction": "desc"}],
            "limit": 25,
        },
        context=context,
        step_id="truncation-survives-budget:1",
    )

    budgeted = budget_tool_observation({"observation": observation.observation})

    # 先证明这条观察确实撞了预算，否则下面两条断言只是空转。
    assert budgeted["context_budget"]["truncated"] is True
    assert "截断" in budgeted["observation"]
    assert "实际覆盖" in budgeted["observation"]


def test_truncation_notice_reports_covered_range(tmp_path: Path) -> None:
    db_path = tmp_path / "finance" / "db" / "market_feature_store.duckdb"
    rows = []
    start = date(2026, 7, 10)
    for offset in range(14):
        day = start + timedelta(days=offset)
        for replica in (0, 1):
            rows.append(
                (
                    day.isoformat(),
                    f"88{offset:02d}{replica}.TI",
                    f"板块{offset}-{replica}",
                    "有色",
                    False,
                    float(offset),
                    100.0 + offset,
                    1.0,
                    1.0,
                )
            )
    _sector_db(db_path, rows)
    registry, context = _registry(tmp_path, task_id="truncation-covered-range")
    observation = registry.execute(
        "finance_query",
        {
            "dataset": "sector_daily",
            "metrics": ["return_pct", "amount"],
            "dimensions": ["trade_date", "sector_code", "sector_name"],
            "filters": [],
            "time_range": {"start": "2026-07-10", "end": "2026-07-23"},
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "asc"}],
            "limit": 25,
        },
        context=context,
        step_id="truncation-covered-range:1",
    )

    dates = sorted(
        {item.source_date for item in observation.evidence if item.source_date}
    )
    assert dates
    covered = f"{dates[0]}..{dates[-1]}" if dates[0] != dates[-1] else dates[0]
    assert covered in observation.observation
    assert "截断" in observation.observation


def test_anchor_date_not_dropped_by_limit(tmp_path: Path) -> None:
    """窗口 07-10→07-23、每日 2 行、limit 25、按交易日升序：必须含 07-23。"""

    db_path = tmp_path / "market.duckdb"
    rows = []
    start = date(2026, 7, 10)
    for offset in range(14):
        day = start + timedelta(days=offset)
        for replica in (0, 1):
            rows.append(
                (
                    day.isoformat(),
                    f"88{offset:02d}{replica}.TI",
                    f"板块{offset}-{replica}",
                    "有色",
                    False,
                    float(offset),
                    100.0,
                    1.0,
                    1.0,
                )
            )
    _sector_db(db_path, rows)
    result = FinanceQuery(db_path).run(
        FinanceQuerySpec.from_arguments(
            {
                "dataset": "sector_daily",
                "metrics": ["return_pct", "amount"],
                "dimensions": ["trade_date", "sector_code", "sector_name"],
                "filters": [],
                "time_range": {"start": "2026-07-10", "end": "2026-07-23"},
                "group_by": [],
                "order_by": [{"field": "trade_date", "direction": "asc"}],
                "limit": 25,
            }
        ),
        information_cutoff=InformationCutoff(date(2026, 7, 23), "requested"),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    dates = {item.source_date for item in result.evidence if item.source_date}
    assert "2026-07-23" in dates
    assert result.audit.row_count == 25


def test_requested_time_range_lands_in_trace(tmp_path: Path) -> None:
    db_path = tmp_path / "finance" / "db" / "market_feature_store.duckdb"
    _sector_db(
        db_path,
        [
            (
                "2026-07-23",
                "880001.TI",
                "锂矿",
                "有色",
                False,
                4.4,
                628.5,
                10.0,
                1.0,
            )
        ],
    )
    registry, context = _registry(tmp_path, task_id="requested-time-range")
    observation = registry.execute(
        "finance_query",
        {
            "dataset": "sector_daily",
            "metrics": ["return_pct", "amount"],
            "dimensions": ["trade_date", "sector_name"],
            "filters": [],
            "time_range": {"start": "2026-07-10", "end": "2026-07-23"},
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "asc"}],
            "limit": 25,
        },
        context=context,
        step_id="requested-time-range:1",
    )

    payload = observation.trace.to_dict()
    requested = payload.get("requested_time_range")
    assert requested == {"start": "2026-07-10", "end": "2026-07-23"}
    # requested_date 是 cutoff/today 口径，不能拿来当「问了哪段」。
    assert payload.get("requested_date") != requested


def test_amount_metric_labels_carry_unit() -> None:
    """§1.3-C：八处成交额口径一致，金额类带「亿」。"""

    amount_labels = []
    for dataset_name, dataset in _DATASETS.items():
        for field_name, field in dataset.metrics.items():
            if field_name in {"amount", "total_amount"} or field.label in {
                "成交额",
                "成交额亿",
                "市场成交额",
            }:
                amount_labels.append((dataset_name, field_name, field.label))

    assert amount_labels
    missing_unit = [
        item for item in amount_labels if "亿" not in item[2]
    ]
    assert missing_unit == []
    unique = {label for _dataset, _field, label in amount_labels}
    # 个股/板块成交额统一「成交额亿」；全市总量可以是「市场成交额亿」。
    assert unique <= {"成交额亿", "市场成交额亿"}


def test_truncation_notice_names_uncovered_prefix() -> None:
    """T1b 之后 LIMIT 切的是窗口前端：提示必须写出请求窗口和未覆盖侧。"""

    audit = FinanceQueryAudit(
        dataset="sector_daily",
        physical_sql="SELECT 1",
        bound_parameters=(),
        sql_fingerprint="x",
        applied_limit=25,
        row_count=25,
        output_bytes=100,
        elapsed_seconds=0.01,
        requested_time_range=("2026-07-10", "2026-07-23"),
    )
    notice = truncation_notice(audit, covered_range="2026-07-17..2026-07-23")
    assert notice is not None
    assert "截断" in notice
    assert "请求窗口 2026-07-10..2026-07-23" in notice
    assert "窗口前端未覆盖" in notice
    assert "2026-07-17" in notice
    assert "不要靠调大 limit" in notice
    assert "窗口末端未覆盖" not in notice


def test_lithium_req10_keeps_named_anchor_day(tmp_path: Path) -> None:
    """复现 run_20260820_160509_857370 REQ 10：锂矿+盐湖提锂、一日多行、升序 25。

    修前 ASC+LIMIT 停在 07-22；T1b 必须保住 07-23 的「锂矿」行，且提示覆盖到当天。
    """

    days = (
        "2026-07-10",
        "2026-07-13",
        "2026-07-14",
        "2026-07-15",
        "2026-07-16",
        "2026-07-17",
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
    )
    rows: list[tuple[object, ...]] = []
    for index, day in enumerate(days):
        rows.append(
            (
                day,
                f"8801{index:02d}.TI",
                "锂矿",
                "有色",
                False,
                4.4 if day == "2026-07-23" else -1.0,
                628.5 if day == "2026-07-23" else 500.0 + index,
                11.73 if day == "2026-07-23" else 1.0,
                1.0,
            )
        )
        for replica in (0, 1):
            rows.append(
                (
                    day,
                    f"8802{index:02d}{replica}.TI",
                    "盐湖提锂",
                    "有色",
                    False,
                    1.0,
                    400.0 + replica,
                    1.0,
                    1.0,
                )
            )
    db_path = tmp_path / "finance" / "db" / "market_feature_store.duckdb"
    _sector_db(db_path, rows)
    registry, context = _registry(tmp_path, task_id="lithium-req10")
    observation = registry.execute(
        "finance_query",
        {
            "dataset": "sector_daily",
            "dimensions": ["trade_date", "sector_name"],
            "metrics": ["return_pct", "amount"],
            "filters": [
                {
                    "field": "sector_name",
                    "op": "in",
                    "value": ["锂矿", "盐湖提锂"],
                }
            ],
            "time_range": {"start": "2026-07-10", "end": "2026-07-23"},
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "asc"}],
            "limit": 25,
        },
        context=context,
        step_id="lithium-req10:1",
    )

    lithium_dates = {
        item.source_date
        for item in observation.evidence
        if item.source_date and "锂矿" in f"{item.title} {item.detail}"
    }
    assert "2026-07-23" in lithium_dates
    assert "4.4" in observation.observation or "4.40" in observation.observation
    assert "628.5" in observation.observation
    assert "截断" in observation.observation
    assert "2026-07-23" in observation.observation
    assert observation.trace.requested_time_range == ("2026-07-10", "2026-07-23")
