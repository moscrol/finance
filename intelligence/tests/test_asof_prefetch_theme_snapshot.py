"""theme_analysis 确定性预取：精确板块名 → 当日板块行 + 成员表（R-20260828-02）。

四臂 D5（`R-20260827-09` refuted 升格）：模型自选查询从不使用精确板块名
（`contains "核"` 撒网 / 成交额 top8），判据要的板块数值与成员映射永远缺供数。
本组钉离线锁死：解析复用 resolve_prefetch_sector（问句内精确长名 > subject），
解析不到 fail closed，不做宽松臆配。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from intelligence.services.asof_prefetch import (
    _theme_sector_snapshot_items,
    collect_prefetch_items,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

pytestmark = pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")

FUSION = "可控核聚变"
AS_OF = date(2026, 6, 11)


def _theme_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_sector_daily ("
        "trade_date date, sector_name varchar, "
        "pct_chg double, diff_ratio double, amount double)"
    )
    con.executemany(
        "insert into fact_sector_daily values (?, ?, ?, ?, ?)",
        [
            ("2026-06-10", FUSION, -1.2, -3.0, 980.5),
            ("2026-06-11", FUSION, 0.41, 5.0, 1134.9),
            # 干扰板块：主体被拓宽成「核电与可控核聚变」时 contains "核" 会撒到它
            ("2026-06-11", "核电", 1.8, 2.0, 660.0),
        ],
    )
    con.execute(
        "create table fact_sector_stock_daily ("
        "trade_date date, sector_name varchar, stock_name varchar, "
        "pct_chg double, amount double, pct_chg_5d double)"
    )
    con.executemany(
        "insert into fact_sector_stock_daily values (?, ?, ?, ?, ?, ?)",
        [
            ("2026-06-11", FUSION, "联创光电", 3.1, 25.6, 8.0),
            ("2026-06-11", FUSION, "永鼎股份", 2.2, 18.3, 5.5),
            ("2026-06-11", FUSION, "西部超导", 1.5, 12.1, 4.2),
            ("2026-06-11", FUSION, "国光电气", -0.8, 9.7, 1.1),
            ("2026-06-11", "核电", "中国核电", 2.0, 30.0, 3.0),
        ],
    )
    con.close()
    return path


def _connect(path: Path):
    return duckdb.connect(str(path), read_only=True)


def test_exact_name_in_question_beats_broadened_subject(tmp_path: Path) -> None:
    """D5 回归钉：subject 被拓宽成「核电与可控核聚变」，问句内精确名必须胜出。"""
    db = _theme_db(tmp_path / "theme.duckdb")
    con = _connect(db)
    try:
        items = _theme_sector_snapshot_items(
            con,
            "2026-06-11 可控核聚变",
            "核电与可控核聚变",
            AS_OF,
        )
    finally:
        con.close()

    assert len(items) == 2
    daily, members = items
    assert FUSION in daily.title
    assert "0.41" in daily.detail and "1134.9" in daily.detail
    assert "核电 " not in daily.detail  # 不得撒网到干扰板块
    obs_metrics = {(o.subject, o.metric): o.value for o in daily.observations}
    assert obs_metrics[(FUSION, "pct_chg")] == pytest.approx(0.41)
    assert obs_metrics[(FUSION, "amount")] == pytest.approx(1134.9)
    assert FUSION in members.title
    for name in ("联创光电", "永鼎股份", "西部超导", "国光电气"):
        assert name in members.detail
    assert "中国核电" not in members.detail


def test_unresolved_subject_fails_closed_with_note(tmp_path: Path) -> None:
    """解析不到板块 → 单条提示项，禁止宽松臆配出任何数值行。"""
    db = _theme_db(tmp_path / "theme.duckdb")
    con = _connect(db)
    try:
        items = _theme_sector_snapshot_items(
            con,
            "2026-06-11 室温超导量子引力",
            "室温超导量子引力",
            AS_OF,
        )
    finally:
        con.close()

    assert len(items) == 1
    assert "未锚定" in items[0].title
    assert "精确板块名" in items[0].detail


def test_ferment_sector_exclusion_keeps_members(tmp_path: Path) -> None:
    """发酵分支已交付同板块时间轴时：板块行让位、成员表仍交付（新增供数面）。"""
    db = _theme_db(tmp_path / "theme.duckdb")
    con = _connect(db)
    try:
        items = _theme_sector_snapshot_items(
            con,
            "2026-06-11 可控核聚变",
            FUSION,
            AS_OF,
            exclude_sector=FUSION,
        )
    finally:
        con.close()

    assert len(items) == 1
    assert "成员" in items[0].title
    assert "联创光电" in items[0].detail


def test_dispatch_only_for_theme_analysis(tmp_path: Path) -> None:
    """collect_prefetch_items 只对 theme_analysis 启用本预取。"""
    db = _theme_db(tmp_path / "theme.duckdb")

    theme_items = collect_prefetch_items(
        question="2026-06-11 可控核聚变",
        question_type="theme_analysis",
        subject="核电与可控核聚变",
        as_of=AS_OF,
        market_db_path=db,
    )
    other_items = collect_prefetch_items(
        question="2026-06-11 可控核聚变",
        question_type="stock_price",
        subject=FUSION,
        as_of=AS_OF,
        market_db_path=db,
    )

    assert any(FUSION in item.title and "成员" in item.title for item in theme_items)
    assert any("1134.9" in item.detail for item in theme_items)
    assert not any("成员" in item.title for item in other_items)


def test_members_use_latest_trade_date_on_or_before_as_of(tmp_path: Path) -> None:
    """as_of 非交易日时取 ≤as_of 最近一日，且板块行与成员表同日。"""
    db = _theme_db(tmp_path / "theme.duckdb")
    con = _connect(db)
    try:
        items = _theme_sector_snapshot_items(
            con,
            "2026-06-14 可控核聚变",
            FUSION,
            date(2026, 6, 14),
        )
    finally:
        con.close()

    assert len(items) == 2
    assert "2026-06-11" in items[0].detail
    assert "2026-06-11" in items[1].title or "2026-06-11" in items[1].detail
