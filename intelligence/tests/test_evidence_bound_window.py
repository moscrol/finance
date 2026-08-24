"""启动日已在本轮证据里时，当天大盘查询不得被题型窗口闸门挡掉。

现场：run_20260824_125258_079058。theme_analysis + freshness=current。
主线表已给出 2026-05-11 / 06-29，再查这两天的 market_daily 被
historical_window_not_authorized_by_task 拒绝，模型改拿 08-21 顶「当天」。

窗口跟本轮证据日期走，不跟题型走。没有证据锚的历史窗口仍拒绝。
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.task_frame import TaskFrame


def _theme_start_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="医药板块什么时候启动的，当天市场的情况是怎么样的",
        user_goal="形成条件化判断",
        question_type="theme_analysis",
        subject="医药",
        subject_kind="theme",
        market_scope="A股",
        timeframe=None,
        required_outputs=("direct_assessment", "chain_mapping", "counterpoint"),
        assumptions=("用户未明确市场范围，按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.98,
    )


def _seed_db(finance_root: Path) -> None:
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        "create table fact_mainline_sector_daily("
        "trade_date date, theme_name varchar, sector_name varchar, "
        "cycle_status varchar, today_pct double, limit_up_count integer, "
        "strength double)"
    )
    connection.execute(
        "insert into fact_mainline_sector_daily values "
        "('2026-05-11', '医药', '创新药', '启动', 1.637, 3, 2758.2), "
        "('2026-08-21', '有色金属', '贵金属', '顺势', 4.64, 2, 4100.0)"
    )
    connection.execute(
        "create table fact_market_daily("
        "trade_date date, market_stage varchar, total_amount double, "
        "sh_index_close double, sh_index_pct_chg double)"
    )
    connection.execute(
        "insert into fact_market_daily values "
        "('2026-05-11', '主升', 35386.0, 4225.021, 1.078), "
        "('2026-08-21', '底部横盘阶段', 18791.51, 3905.2, 0.04)"
    )
    connection.close()


def _registry(tmp_path: Path, frame: TaskFrame, *, task_id: str):
    finance_root = tmp_path / "finance"
    _seed_db(finance_root)
    context = build_episode_context(
        frame,
        task_id=task_id,
        capabilities=("finance_query", "market_data"),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-08-24",
        latest_data_date="2026-08-21",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )
    return registry, context


def _query_start_day(registry, context) -> object:
    return registry.execute(
        "finance_query",
        {
            "dataset": "mainline_sector_daily",
            "dimensions": ["sector_name", "theme_name", "trade_date", "cycle_status"],
            "metrics": ["return_pct", "limit_up_count", "strength"],
            "filters": [
                {"field": "theme_name", "op": "contains", "value": "医药"}
            ],
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "asc"}],
            "limit": 25,
        },
        context=context,
        step_id="evidence-bound-window:sector",
    )


def _query_market_on(registry, context, start: str, end: str) -> object:
    return registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "dimensions": ["trade_date", "market_stage"],
            "metrics": ["total_amount", "index_close", "index_return_pct"],
            "filters": [],
            "time_range": {"start": start, "end": end},
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "desc"}],
            "limit": 5,
        },
        context=context,
        step_id=f"evidence-bound-window:market:{start}",
    )


def test_start_day_market_query_runs_after_mainline_evidence(tmp_path: Path) -> None:
    registry, context = _registry(
        tmp_path,
        _theme_start_frame(),
        task_id="evidence-bound-window-follow",
    )

    sector = _query_start_day(registry, context)
    assert sector.trace.status in {"ok", "success"}
    assert any(item.source_date == "2026-05-11" for item in sector.evidence)

    market = _query_market_on(registry, context, "2026-05-11", "2026-05-12")
    assert "historical_window_not_authorized_by_task" not in (market.trace.detail or "")
    assert market.trace.status == "success"
    assert any(item.source_date == "2026-05-11" for item in market.evidence)
    assert any("35386" in (item.detail or "") for item in market.evidence)


def test_unanchored_historical_market_query_still_rejected(tmp_path: Path) -> None:
    registry, context = _registry(
        tmp_path,
        _theme_start_frame(),
        task_id="evidence-bound-window-unanchored",
    )

    market = _query_market_on(registry, context, "2026-05-11", "2026-05-11")
    assert market.evidence == ()
    assert market.trace.status == "parse_error"
    assert "historical_window_not_authorized_by_task" in market.trace.detail


def test_other_historical_day_stays_blocked_after_unrelated_evidence(
    tmp_path: Path,
) -> None:
    registry, context = _registry(
        tmp_path,
        _theme_start_frame(),
        task_id="evidence-bound-window-other-day",
    )
    sector = _query_start_day(registry, context)
    assert any(item.source_date == "2026-05-11" for item in sector.evidence)

    market = _query_market_on(registry, context, "2025-06-30", "2025-06-30")
    assert market.evidence == ()
    assert "historical_window_not_authorized_by_task" in (market.trace.detail or "")
