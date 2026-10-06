"""海外行情里的「复制旧值」要逐行标出来，不能被当作该日行情（2026-10-06）。

实测形状：上游回填把前一天的收盘与涨跌幅原样抄到后面几天，A 股对照日和外盘会话日却
照常往后走——道指 2026-07-15~07-24 十天同一个数。模型拿到这种行会写「隔夜美股收涨 0.29%」。
外盘休市时 A 股日对照到同一场会话、数相同是合法的，不能误标。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from intelligence.services import finance_query as fq
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline

_ROWS = [
    # trade_date, session_date, code, close, pct_chg
    ("2026-07-14", "2026-07-14", "DJI", 52508.27, 0.018),
    ("2026-07-15", "2026-07-15", "DJI", 52658.64, 0.286),
    ("2026-07-16", "2026-07-16", "DJI", 52658.64, 0.286),  # 复制旧值：会话日变了、数没变
    ("2026-07-17", "2026-07-17", "DJI", 52658.64, 0.286),  # 复制旧值
    ("2026-07-14", "2026-07-14", "HSI", 24340.73, 0.525),
    ("2026-07-15", "2026-07-14", "HSI", 24340.73, 0.525),  # 合法：港股休市，对照同一场会话
    ("2026-07-16", "2026-07-16", "HSI", 25008.60, 1.327),
    ("2026-07-17", "2026-07-17", "HSI", 24562.24, -1.785),
]


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "market_feature_store.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "create table fact_global_index_daily (trade_date date, source_trade_date date, code varchar, "
            "name varchar, market_group varchar, close double, pct_chg double)"
        )
        con.executemany(
            "insert into fact_global_index_daily values (?, ?, ?, '', '', ?, ?)",
            [(t, s, c, close, pct) for t, s, c, close, pct in _ROWS],
        )
    return path


def _run(db: Path, **overrides):
    arguments = {
        "dataset": "global_index_daily",
        "metrics": ["close", "return_pct"],
        "dimensions": ["trade_date", "session_date", "index_code"],
        "time_range": {"start": "2026-07-14", "end": "2026-07-17"},
        "order_by": [{"field": "trade_date", "direction": "asc"}],
        "limit": 50,
    }
    arguments.update(overrides)
    spec = fq.FinanceQuerySpec.from_arguments(arguments)
    return fq.FinanceQuery(db).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 7, 17), "requested"),
        deadline=ResearchDeadline.from_timeout(10),
    )


def test_cloned_rows_are_flagged_and_legal_holiday_repeats_are_not(db: Path) -> None:
    result = _run(db)

    flagged = [e for e in result.evidence if "疑似复制旧值" in e.detail]
    assert [(e.source_date, "DJI" in e.detail) for e in flagged] == [
        ("2026-07-16", True),
        ("2026-07-17", True),
    ]
    # 第一次出现的那天不标；港股休市对照同一场会话的重复也不标。
    assert not any("疑似复制旧值" in e.detail for e in result.evidence if "HSI" in e.detail)
    assert any("DJI@2026-07-16" in gap and "不可当作该日行情" in gap for gap in result.quality_gaps)
    # 只标注，不删行：被标的行仍然返回。
    assert len(result.evidence) == len(_ROWS)


def test_aggregated_results_get_a_window_level_warning(db: Path) -> None:
    result = _run(db, dimensions=["index_code"], group_by=["index_code"], order_by=[])

    assert any("请求窗口内有 2 个" in gap and "逐行复核" in gap for gap in result.quality_gaps)


def test_window_without_clones_stays_silent(db: Path) -> None:
    result = _run(db, filters=[{"field": "index_code", "op": "eq", "value": "HSI"}])

    assert not any("复制旧值" in gap for gap in result.quality_gaps)
    assert not any("疑似复制旧值" in e.detail for e in result.evidence)


def test_clone_check_never_looks_past_the_information_cutoff(db: Path) -> None:
    # 聚合口径才会把窗口内的复制数报出来；不给 end 时上界只剩截止日。
    spec = fq.FinanceQuerySpec.from_arguments({
        "dataset": "global_index_daily",
        "metrics": ["close"],
        "dimensions": ["index_code"],
        "group_by": ["index_code"],
        "time_range": {"start": "2026-07-14"},
        "limit": 50,
    })
    result = fq.FinanceQuery(db).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 7, 16), "requested"),
        deadline=ResearchDeadline.from_timeout(10),
    )
    window = [gap for gap in result.quality_gaps if "复制旧值" in gap]
    assert len(window) == 1
    assert "有 1 个" in window[0] and "DJI@2026-07-16" in window[0]
    assert "2026-07-17" not in window[0]


def test_only_overseas_datasets_carry_the_clone_check() -> None:
    carriers = {name for name, dataset in fq._DATASETS.items() if dataset.clone_key}
    assert carriers == {"global_index_daily", "global_stock_daily"}


def test_sector_daily_no_longer_offers_a_strength_that_was_never_filled() -> None:
    assert "strength" not in fq._DATASETS["sector_daily"].metrics
    # 有数的板块强度还在主线板块表里。
    assert "strength" in fq._DATASETS["mainline_sector_daily"].metrics
