"""诚实度交付层：休市 / 退役表 / 问句截止日不得交给模型自觉。

对应 2026-08-13 全量 28 题里 C2（春节涨停家数走 knowledge 车道、不说休市）、
C7（站在 07-21 却引用 08-13 快照）、C8（sector_marginal 被聊成「把表贴过来」）。
"""

from __future__ import annotations

from datetime import date

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.honesty_gates import (
    UNREADABLE,
    SectorAmountRow,
    StockDailyRow,
    ThemeHeatRow,
    bound_caliber_disclosure,
    calendar_disclosure,
    empty_caliber_disclosure,
    requested_information_cutoff,
    retired_table_disclosure,
    with_calendar_disclosure,
)
from intelligence.services.lane_generation import generate_lane_answer
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.turn_controller import decide_turn


def test_holiday_quick_fact_is_canned_without_llm() -> None:
    """C2：指定日期的单指标取值，日历已能判定休市，禁止再问模型。"""

    query = "2026-02-17 涨停家数多少"
    decision = decide_turn(query)

    def boom(_messages):
        raise AssertionError("holiday quick_fact must not call the LLM")

    answer = generate_lane_answer(query, decision, llm_complete=boom)

    assert decision.question_type == "quick_fact"
    assert calendar_disclosure(decision.task_frame)
    assert "休市" in answer.answer
    assert "2026-02-17" in answer.answer


def test_weekend_review_still_goes_to_research_not_canned_knowledge() -> None:
    """C1：路由仍是 research（不是 knowledge 车道），但休市日必须罐头短路。"""

    decision = decide_turn("2026-07-25 市场怎么样")
    assert decision.lane == "research"
    assert calendar_disclosure(decision.task_frame)


def test_weekend_market_review_is_canned_without_llm() -> None:
    """KC-18 / R15-C1：周六复盘直接答休市，禁止再进检索或问模型。"""

    query = "2026-07-25 市场怎么样"
    decision = decide_turn(query)

    def boom(_messages):
        raise AssertionError("weekend market review must not call the LLM")

    answer = generate_lane_answer(query, decision, llm_complete=boom)

    assert decision.lane == "research"
    assert "休市" in answer.answer
    assert "2026-07-25" in answer.answer
    assert "周六" in answer.answer


def test_weekday_market_review_is_not_canned() -> None:
    query = "2026-07-23 市场怎么样"
    decision = decide_turn(query)
    from intelligence.services.lane_generation import deterministic_lane_answer

    assert calendar_disclosure(decision.task_frame) is None
    assert deterministic_lane_answer(query, decision) is None


def test_retired_table_is_canned_without_llm() -> None:
    """C8：旧表名是确定性知识，不能让模型改口成「把表贴过来」。"""

    query = "查一下 sector_marginal 表里 07-23 的边际量"

    def boom(_messages):
        raise AssertionError("retired table must not call the LLM")

    answer = generate_lane_answer(query, decide_turn(query), llm_complete=boom)

    assert "表不存在" in answer.answer
    assert "fact_sector_daily" in answer.answer
    assert retired_table_disclosure(query)


def test_retired_table_does_not_false_positive_on_substring() -> None:
    assert retired_table_disclosure("板块边际量怎么看") is None
    assert retired_table_disclosure("advancers-chart 怎么用") is None


def test_empty_technical_snapshot_is_canned_without_llm(monkeypatch) -> None:
    """C3：目标口径 0 行必须声明空表，禁止换价格表，也禁止再问模型。"""

    monkeypatch.setattr(
        "intelligence.services.honesty_gates._count_table_rows",
        lambda _table: 0,
    )
    query = "2026-07-23 立新能源的技术面快照给我看一下"

    def boom(_messages):
        raise AssertionError("empty technical snapshot must not call the LLM")

    answer = generate_lane_answer(query, decide_turn(query), llm_complete=boom)

    assert "fact_stock_technical_snapshot" in answer.answer
    assert "空表" in answer.answer
    assert "0 行" in answer.answer
    assert "数据不可用" in answer.answer
    assert "表不存在" not in answer.answer
    assert "收盘" not in answer.answer


def test_empty_caliber_disclosure_is_injectable() -> None:
    query = "2026-07-23 立新能源的技术面快照给我看一下"
    hit = empty_caliber_disclosure(query, row_count=0)
    assert hit is not None and "0 行" in hit
    assert empty_caliber_disclosure(query, row_count=12) is None
    assert empty_caliber_disclosure("立新能源怎么看", row_count=0) is None


def test_empty_caliber_fail_open_when_db_unreadable(monkeypatch) -> None:
    monkeypatch.setattr(
        "intelligence.services.honesty_gates._count_table_rows",
        lambda _table: None,
    )
    from intelligence.services.lane_generation import deterministic_lane_answer

    query = "2026-07-23 立新能源的技术面快照给我看一下"
    assert empty_caliber_disclosure(query) is None
    canned = deterministic_lane_answer(query, decide_turn(query))
    assert canned is None or "fact_stock_technical_snapshot" not in canned


def test_standing_date_becomes_requested_cutoff() -> None:
    """C7：问句站立日必须成为 cutoff，不能落成运行时今天。"""

    query = "站在 2026-07-21 收盘，给出对 07-22 的研判"
    cutoff = requested_information_cutoff(query, today="2026-08-13")
    assert cutoff == InformationCutoff(date(2026, 7, 21), "requested")

    decision = decide_turn(query)
    context = build_episode_context(
        decision.task_frame,
        task_id="c7-standing-cutoff",
        today="2026-08-13",
        latest_data_date="2026-08-13",
    )
    assert context.information_cutoff == InformationCutoff(
        date(2026, 7, 21),
        "requested",
    )


def test_date_range_does_not_steal_cutoff_from_window_start() -> None:
    """「1 日至 5 日」不是站立日，cutoff 必须仍是运行时今天。"""

    query = "2026年7月1日至5日A股下跌的主要原因是什么"
    assert requested_information_cutoff(query, today="2026-07-27") is None

    decision = decide_turn(query)
    context = build_episode_context(
        decision.task_frame,
        task_id="range-not-standing",
        today="2026-07-27",
        latest_data_date="2026-07-24",
    )
    assert context.information_cutoff.source == "runtime_default"
    assert context.information_cutoff.as_of_date == date(2026, 7, 27)


def test_undated_question_keeps_runtime_cutoff() -> None:
    cutoff = requested_information_cutoff("液冷怎么看", today="2026-08-13")
    assert cutoff is None

    decision = decide_turn("液冷怎么看")
    context = build_episode_context(
        decision.task_frame,
        task_id="undated-runtime-cutoff",
        today="2026-08-13",
    )
    assert context.information_cutoff == InformationCutoff(
        date(2026, 8, 13),
        "runtime_default",
    )


def test_fermentation_end_date_becomes_requested_cutoff() -> None:
    query = "锂矿从7月初发酵到 2026-07-23，逐步涨幅、成交额和环比怎么走"
    cutoff = requested_information_cutoff(query, today="2026-08-20")
    assert cutoff == InformationCutoff(date(2026, 7, 23), "requested")


def test_leading_iso_date_becomes_requested_cutoff() -> None:
    query = "2026-07-23 电网设备为什么涨"
    cutoff = requested_information_cutoff(query, today="2026-08-20")
    assert cutoff == InformationCutoff(date(2026, 7, 23), "requested")


def test_calendar_disclosure_still_prepends_when_model_omits_it() -> None:
    decision = decide_turn("2026-02-17 涨停家数多少")
    answer = with_calendar_disclosure("未知。材料没有给出数值。", decision.task_frame)
    assert answer.startswith("2026-02-17")
    assert "休市" in answer.split("\n", 1)[0]


@pytest.mark.parametrize(
    "query",
    (
        "2026-02-17 涨停家数多少",
        "2026-07-25 市场怎么样",
        "查一下 sector_marginal 表里 07-23 的边际量",
    ),
)
def test_honesty_canned_answers_do_not_need_retrieval(query: str) -> None:
    """罐头答案必须在检索前就能判定，否则 C2 仍会先空跑 2 分钟。"""

    from intelligence.services.lane_generation import deterministic_lane_answer

    decision = decide_turn(query)
    assert deterministic_lane_answer(query, decision)


def test_ranking_quick_fact_authorizes_finance_query_on_requested_date() -> None:
    """R-20260828-05 F1：排名取值题进 episode 时必须授权 finance_query，cutoff 是问句日。

    旧路径 generic_owner 取的是站立日 market_data，不是结构化 finance_query。
    """

    from intelligence.services.evidence_capabilities import runtime_capabilities_for_frame
    from intelligence.services.lane_generation import deterministic_lane_answer

    query = "2026-08-19 全市场成交额排第三的板块是哪个，成交额多少"
    decision = decide_turn(query)
    assert decision.question_type == "quick_fact"
    assert deterministic_lane_answer(query, decision) is None
    context = build_episode_context(
        decision.task_frame,
        task_id="r05-ranking-finance-query",
        capabilities=runtime_capabilities_for_frame(decision.task_frame),
        today="2026-08-28",
        latest_data_date="2026-08-27",
    )
    assert "finance_query" in context.contract.allowed_capabilities
    assert context.information_cutoff == InformationCutoff(
        date(2026, 8, 19),
        "requested",
    )


def test_week_range_ending_on_saturday_is_not_canned() -> None:
    """R4 / R-20260828-05：区间终点休市不能整题 canned，否则周内峰值被吞。

    08-22 确实无行情，假设仍注入（供检索后前置），但 canned 必须是 None，
    让编排走进取数面。单日休市题（C1/C2）仍由上一测钉死。
    """

    from intelligence.services.lane_generation import deterministic_lane_answer

    query = "2026-08-18 到 2026-08-22 这一周，全市场哪天成交额最高，是多少"
    decision = decide_turn(query)

    assert decision.needs_retrieval is True
    assert calendar_disclosure(decision.task_frame)
    assert "2026-08-22" in (calendar_disclosure(decision.task_frame) or "")
    assert deterministic_lane_answer(query, decision) is None


def test_mlcc_sector_amount_flags_unit_anomaly_without_llm(monkeypatch) -> None:
    """C4：板块成交额必须取出 fact_sector_daily 原值并质疑单位，禁止换全市口径。"""

    query = "2026-07-21 MLCC 板块成交额多少"
    row = SectorAmountRow(
        sector_name="MLCC",
        trade_date="2026-07-21",
        amount=6112588.6,
        median_amount=405.0,
    )
    canned = bound_caliber_disclosure(query, sector_row=row)
    assert canned is not None
    assert "6112588.6" in canned
    assert "fact_sector_daily" in canned
    assert "单位异常" in canned
    assert "611万亿" not in canned
    assert "6112588亿" not in canned

    monkeypatch.setattr(
        "intelligence.services.lane_generation.bound_caliber_disclosure",
        lambda q, **_kwargs: bound_caliber_disclosure(q, sector_row=row),
    )

    def boom(_messages):
        raise AssertionError("sector unit-anomaly must not call the LLM")

    answer = generate_lane_answer(query, decide_turn(query), llm_complete=boom)
    assert "6112588.6" in answer.answer
    assert "fact_sector_daily" in answer.answer


def test_citywide_amount_is_not_sector_caliber_canned() -> None:
    query = "2026-07-21 全市成交额多少"
    assert bound_caliber_disclosure(
        query,
        sector_row=SectorAmountRow(
            sector_name="全市",
            trade_date="2026-07-21",
            amount=29569.03,
            median_amount=405.0,
        ),
    ) is None


def test_normal_sector_amount_reports_raw_without_anomaly() -> None:
    query = "2026-07-21 电子 板块成交额多少"
    canned = bound_caliber_disclosure(
        query,
        sector_row=SectorAmountRow(
            sector_name="电子",
            trade_date="2026-07-21",
            amount=380.2,
            median_amount=405.0,
        ),
    )
    assert canned is not None
    assert "380.2" in canned
    assert "fact_sector_daily" in canned
    assert "单位" not in canned


def test_sector_amount_fail_open_when_unreadable() -> None:
    query = "2026-07-21 MLCC 板块成交额多少"
    assert bound_caliber_disclosure(query, sector_row=UNREADABLE) is None


def test_two_day_identical_close_flags_contradiction(monkeypatch) -> None:
    """C5：两日 close/涨幅完全相同必须指出口径内部不一致。"""

    query = "立新能源 2026-07-20 和 07-21 分别涨了多少、收盘价多少"
    rows = (
        StockDailyRow("立新能源", "2026-07-20", 10.01, 10.0),
        StockDailyRow("立新能源", "2026-07-21", 10.01, 10.0),
    )
    canned = bound_caliber_disclosure(query, stock_rows=rows)
    assert canned is not None
    assert "10.01" in canned
    assert "fact_stock_daily" in canned
    assert "不一致" in canned

    monkeypatch.setattr(
        "intelligence.services.lane_generation.bound_caliber_disclosure",
        lambda q, **_kwargs: bound_caliber_disclosure(q, stock_rows=rows),
    )

    def boom(_messages):
        raise AssertionError("copied stock rows must not call the LLM")

    answer = generate_lane_answer(query, decide_turn(query), llm_complete=boom)
    assert "不一致" in answer.answer


def test_two_day_query_strips_runner_date_prefix(monkeypatch) -> None:
    """Phase 2 runner 会把 case.date 前缀到题面；C5 不能把日期当成股票名。"""

    query = "2026-07-21 立新能源 2026-07-20 和 07-21 分别涨了多少、收盘价多少"
    rows = (
        StockDailyRow("立新能源", "2026-07-20", 10.01, 10.0),
        StockDailyRow("立新能源", "2026-07-21", 10.01, 10.0),
    )
    canned = bound_caliber_disclosure(query, stock_rows=rows)
    assert canned is not None
    assert "立新能源" in canned
    assert "不一致" in canned

    monkeypatch.setattr(
        "intelligence.services.lane_generation.bound_caliber_disclosure",
        lambda q, **_kwargs: bound_caliber_disclosure(q, stock_rows=rows),
    )

    def boom(_messages):
        raise AssertionError("prefixed C5 query must still be canned")

    answer = generate_lane_answer(query, decide_turn(query), llm_complete=boom)
    assert "不一致" in answer.answer
    query = "立新能源 2026-07-20 和 07-21 分别涨了多少、收盘价多少"
    canned = bound_caliber_disclosure(
        query,
        stock_rows=(
            StockDailyRow("立新能源", "2026-07-20", 9.10, 10.0),
            StockDailyRow("立新能源", "2026-07-21", 10.01, 10.0),
        ),
    )
    assert canned is not None
    assert "9.1" in canned or "9.10" in canned
    assert "10.01" in canned
    assert "不一致" not in canned


def test_stock_judgment_query_is_not_canned() -> None:
    assert bound_caliber_disclosure("立新能源怎么看") is None
    assert bound_caliber_disclosure("茅台现在股价多少") is None


def test_theme_limit_heat_uses_theme_caliber_not_mainline(monkeypatch) -> None:
    """A5：涨停集中必须来自 fact_theme_limit_heat_daily，不能借道主线表。"""

    query = "2026-07-23 涨停集中在哪些题材"
    rows = (
        ThemeHeatRow("储能", 40, "2026-07-23"),
        ThemeHeatRow("风电", 29, "2026-07-23"),
        ThemeHeatRow("电网设备", 18, "2026-07-23"),
        ThemeHeatRow("光伏概念", 15, "2026-07-23"),
    )
    canned = bound_caliber_disclosure(query, heat_rows=rows)
    assert canned is not None
    assert "fact_theme_limit_heat_daily" in canned
    assert "储能 40" in canned
    assert "风电 29" in canned
    assert "主线" not in canned

    monkeypatch.setattr(
        "intelligence.services.lane_generation.bound_caliber_disclosure",
        lambda q, **_kwargs: bound_caliber_disclosure(q, heat_rows=rows),
    )

    def boom(_messages):
        raise AssertionError("theme heat must not call the LLM")

    answer = generate_lane_answer(query, decide_turn(query), llm_complete=boom)
    assert "储能 40" in answer.answer


def test_limit_up_count_without_theme_is_not_heat_canned() -> None:
    assert bound_caliber_disclosure("2026-02-17 涨停家数多少") is None
    assert bound_caliber_disclosure("2026-07-23 今天市场怎么样") is None


def test_theme_heat_fail_open_when_unreadable() -> None:
    assert (
        bound_caliber_disclosure(
            "2026-07-23 涨停集中在哪些题材",
            heat_rows=UNREADABLE,
        )
        is None
    )
