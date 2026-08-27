"""替补观察 P1-b：题材+个股观察题在 Engine A 开口预取里拿到带标签替补池。

Spec: docs/superpowers/specs/2026-08-25-substitute-observation-probe-design.md §8 P1-b
落点修正：消费方是 asof_prefetch.collect_prefetch_items（Engine A 开口），
不是 run_strict_signal_pack——编排器只对 market_watch 调 bind_research_program。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from intelligence.services.asof_prefetch import collect_prefetch_items
from intelligence.services.market_watch_pack import PROBE_ROLE_OBSERVATION
from intelligence.services.query_understanding import (
    SIGNAL_SUBSTITUTE_OBSERVATION,
    surface_research_signals,
)
from intelligence.services.research_contract import (
    OPERATOR_SUBSTITUTE_OBSERVATION,
    compile_research_program,
)

Q_MONDAY = "站在spt视角下，你认为周一科技和医药板块的走势会怎么样，需要观察哪些个股的反馈"
Q_YSJS = "用spt的视角，分析下有色金属板块后续的走势，以及板块内有机会的个股有哪些"
Q_STAGE = "用spt的视角，回答下当前科技处于什么阶段，和之前哪一段的科技行情比较类似，个股怎么对标"
SUBSTITUTE_TITLE = "替补观察（出清/分歧观察，非机会）"


def _db(tmp_path: Path, *, med_dual_red: bool = False) -> Path:
    path = tmp_path / "prefetch.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_market_daily(trade_date date, market_stage varchar,"
        " stage_day integer, total_amount double, amount_vs_yesterday_pct double,"
        " volume_state varchar, limit_up integer, limit_down integer,"
        " sh_index_pct_chg double)"
    )
    con.execute(
        "insert into fact_market_daily values"
        " ('2026-07-22', '反弹', 2, 20000, -5, '缩量', 90, 1, 0.1),"
        " ('2026-07-23', '反弹', 3, 21949.97, -17.27, '缩量观望', 116, 2, 0.25),"
        " ('2026-07-24', '反弹', 4, 23000, 5, '放量', 120, 1, 0.9)"
    )
    con.execute(
        "create table fact_mainline_theme_daily(trade_date date,"
        " theme_name varchar, sector_count integer, min_sort integer)"
    )
    con.execute(
        "insert into fact_mainline_theme_daily values"
        " ('2026-07-23', '医药', 6, 1), ('2026-07-23', '有色金属', 5, 2),"
        " ('2026-07-24', '医药', 6, 1)"
    )
    con.execute(
        "create table fact_sector_daily(trade_date date, sector_name varchar,"
        " pct_chg double, diff_ratio double, amount double)"
    )
    med_row = (1.2, 12.0, 900.0) if med_dual_red else (-0.5, 3.0, 900.0)
    con.execute(
        "insert into fact_sector_daily values"
        " ('2026-07-23', '通信设备', 2.5, 15.0, 900),"
        f" ('2026-07-23', '医药商业', {med_row[0]}, {med_row[1]}, {med_row[2]}),"
        " ('2026-07-23', '有色金属冶炼', 1.5, 8.0, 800),"
        " ('2026-07-24', '稀土永磁', 3.0, 20.0, 999)"
    )
    con.execute(
        "create table fact_sector_stock_daily(trade_date date,"
        " sector_name varchar, stock_name varchar, stock_ts_code varchar,"
        " amount double, pct_chg double)"
    )
    con.execute(
        "insert into fact_sector_stock_daily values"
        " ('2026-07-23', '医药商业', '国药一致', '000028.SZ', 25.0, -0.8),"
        " ('2026-07-23', '医药商业', '上海医药', '601607.SH', 20.0, 0.3),"
        " ('2026-07-23', '有色金属冶炼', '紫金矿业', '601899.SH', 50.0, 2.0),"
        " ('2026-07-24', '稀土永磁', '北方稀土', '600111.SH', 60.0, 5.0)"
    )
    con.close()
    return path


def _collect(db: Path, question: str, *, as_of: date, qt: str = "general_finance_qa"):
    return collect_prefetch_items(
        question=question,
        question_type=qt,
        subject="",
        as_of=as_of,
        market_db_path=db,
    )


def _substitute_items(items) -> list:
    return [item for item in items if item.title == SUBSTITUTE_TITLE]


# ---------- 信号与编译器 ----------


def test_signal_fires_on_theme_stock_observation_asks() -> None:
    assert SIGNAL_SUBSTITUTE_OBSERVATION in surface_research_signals(Q_MONDAY)
    assert SIGNAL_SUBSTITUTE_OBSERVATION in surface_research_signals(Q_YSJS)
    # 无 板块/题材/主线/行业 词族：不触发（0-operator 契约债是另一单）
    assert SIGNAL_SUBSTITUTE_OBSERVATION not in surface_research_signals(Q_STAGE)
    assert SIGNAL_SUBSTITUTE_OBSERVATION not in surface_research_signals(
        "长电科技怎么看"
    )


def test_signal_gated_off_for_market_watch() -> None:
    watch_q = "今天市场怎么样，板块和个股有哪些机会"
    signals = surface_research_signals(watch_q)
    assert SIGNAL_SUBSTITUTE_OBSERVATION not in signals


def test_compiler_emits_substitute_operator() -> None:
    for q in (Q_MONDAY, Q_YSJS):
        program = compile_research_program(q, question_class="general_finance_qa")
        assert OPERATOR_SUBSTITUTE_OBSERVATION in program.operators
        assert any(
            slot.slot_id == "substitute_observation"
            for slot in program.required_fact_slots
        )
    stage = compile_research_program(Q_STAGE, question_class="general_finance_qa")
    assert OPERATOR_SUBSTITUTE_OBSERVATION not in stage.operators


# ---------- 预取消费 ----------


def test_prefetch_appends_labeled_pool(tmp_path: Path) -> None:
    items = _collect(_db(tmp_path), Q_MONDAY, as_of=date(2026, 7, 23))
    subs = _substitute_items(items)
    assert len(subs) == 1
    detail = subs[0].detail
    assert PROBE_ROLE_OBSERVATION in detail
    # 标签先于名单
    assert detail.index(PROBE_ROLE_OBSERVATION) < detail.index("国药一致")
    assert "医药商业" in detail
    assert "紫金矿业" in detail
    assert subs[0].source_date == "2026-07-23"


def test_prefetch_respects_as_of_cutoff(tmp_path: Path) -> None:
    # 库里 07-24 有更新的行，但问句截止 07-23：站立日不得越过 as_of
    items = _collect(_db(tmp_path), Q_MONDAY, as_of=date(2026, 7, 23))
    subs = _substitute_items(items)
    assert len(subs) == 1
    assert subs[0].source_date == "2026-07-23"
    assert "稀土永磁" not in subs[0].detail
    assert "北方稀土" not in subs[0].detail


def test_prefetch_silent_when_theme_covered_by_dual_red(tmp_path: Path) -> None:
    # 医药商业升双红后医药有匹配；有色金属仍无 → 仍出item但只含有色
    items = _collect(_db(tmp_path, med_dual_red=True), Q_MONDAY, as_of=date(2026, 7, 23))
    subs = _substitute_items(items)
    assert len(subs) == 1
    assert "国药一致" not in subs[0].detail
    assert "紫金矿业" in subs[0].detail


def test_prefetch_no_item_without_signal(tmp_path: Path) -> None:
    items = _collect(_db(tmp_path), "长电科技怎么看", as_of=date(2026, 7, 23))
    assert _substitute_items(items) == []


def test_prefetch_item_carries_content_hash(tmp_path: Path) -> None:
    items = _collect(_db(tmp_path), Q_YSJS, as_of=date(2026, 7, 23))
    subs = _substitute_items(items)
    assert len(subs) == 1
    evidence = subs[0].to_evidence()
    assert str(evidence.content_hash or "").strip()
