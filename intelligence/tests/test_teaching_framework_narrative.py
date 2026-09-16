"""消息面（第十六段）：卖方观点事件 → 市场级叙事读数。窗口是「T 开盘时可知的隔夜叙事」，源未开始 / 断更是缺口不是 0。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from intelligence.services.teaching_framework.narrative import (
    BRIEFING_FIELDS, NARRATIVE_FIELDS, briefing_daily, load_briefing_tier_events, load_opinion_events, narrative_daily,
)

# 交易日：周一 01-05 … 周五 01-09，周一 01-12 … 周三 01-14；周末 01-10 / 01-11 有报告，归到周一 01-12。
CAL = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14"]


def _ev(report_date, concept, hardness="中性陈述", stance="中性", ingested=None):
    return {"report_date": report_date, "ingested_at": ingested or report_date, "concept": concept, "hardness": hardness, "stance": stance}


EVENTS = [
    _ev("2026-01-05", "CPO"), _ev("2026-01-05", "CPO", "硬证据", "看多"), _ev("2026-01-05", "PCB"),
    _ev("2026-01-06", "CPO"), _ev("2026-01-06", "固态电池", "软推演", "看多", ingested="2026-01-08"),
    _ev("2026-01-09", "CPO"), _ev("2026-01-10", "光模块"), _ev("2026-01-11", "PCB", "硬证据"),
    _ev("2026-01-12", "CPO"),
]


def test_window_is_the_overnight_narrative_and_weekend_reports_belong_to_monday():
    daily = narrative_daily(EVENTS, CAL, rps5_names={"2026-01-12": ["光模块", "PCB", "电子布", "CPO"], "2026-01-13": ["电子布"]})
    # 01-05 是第一天、也不晚于最早报告日 → 缺口，不是 0。
    assert daily[date(2026, 1, 5)]["gap"] == "narrative_before_source"
    # 01-06 的窗口 = 01-05 的报告（3 条，CPO ×2 + PCB）：两个概念都在 01-05 首次出现 → 新概念占比 100%。
    d6 = daily[date(2026, 1, 6)]
    assert (d6["narrative_events"], d6["narrative_concepts"], d6["narrative_new_concepts"]) == (3, 2, 2)
    assert d6["narrative_new_concept_share_pct"] == 100.0 and round(d6["narrative_hard_share_pct"], 2) == 33.33 and round(d6["narrative_bull_share_pct"], 2) == 33.33
    assert round(d6["narrative_top3_share_pct"], 1) == 100.0 and d6["recorded_at"] == "2026-01-05" and d6["narrative_events_ratio_ma20_pct"] is None
    # 01-07 的窗口 = 01-06 的报告：CPO 复炒、固态电池新 → 新概念 1/2；recorded_at 取入库最晚的那条（01-08，滞后）。
    d7 = daily[date(2026, 1, 7)]
    assert d7["narrative_events"] == 2 and d7["narrative_new_concepts"] == 1 and d7["narrative_new_concept_share_pct"] == 50.0 and d7["recorded_at"] == "2026-01-08"
    # 01-08 的窗口 = 01-07 的报告：没有 → 0 条是真的 0（源活着），不是缺口。
    d8 = daily[date(2026, 1, 8)]
    assert d8["narrative_events"] == 0 and d8["narrative_hard_share_pct"] is None and "gap" not in d8
    # 周一 01-12 的窗口 = 周五 01-09 + 周六 01-10 + 周日 01-11 的报告（CPO、光模块、PCB）：光模块首次出现。
    d12 = daily[date(2026, 1, 12)]
    assert d12["narrative_events"] == 3 and d12["narrative_new_concepts"] == 1
    # 叙事覆盖率：01-12 的赚钱效应四个板块里，过去 5 个日历日（01-07 → 01-11）有报告提过的是 光模块、PCB、CPO → 75%；电子布没有。
    assert d12["narrative_cover_rps5_pct"] == 75.0
    # 01-13 的赚钱效应只有电子布，叙事里从没出现 → 0%（不是缺口）。
    assert daily[date(2026, 1, 13)]["narrative_cover_rps5_pct"] == 0.0
    assert set(NARRATIVE_FIELDS) <= set(d12)


def test_stale_source_is_a_gap_not_zero():
    cal = CAL + ["2026-01-15", "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22"]
    daily = narrative_daily(EVENTS, cal, stale_after_days=7)
    # 最新报告 01-12：01-19 距它 7 天仍算活着，01-20 起断更。
    assert "gap" not in daily[date(2026, 1, 19)] and daily[date(2026, 1, 19)]["narrative_events"] == 0
    assert daily[date(2026, 1, 20)] == {"gap": "narrative_stale", "latest_report_date": date(2026, 1, 12)}


def test_missing_events_file_is_an_empty_source(tmp_path: Path):
    assert load_opinion_events(tmp_path) == []
    assert load_briefing_tier_events(tmp_path) == []
    assert narrative_daily([], CAL) == {}
    assert briefing_daily([], CAL) == {}


def _brief(available_from, tier, *, dims=2, links=(), theme="主题", recorded=None, market_confirmed=False):
    return {
        "available_from": available_from, "recorded_at": recorded or available_from, "tier": tier, "dimensions": dims,
        "market_confirmed": market_confirmed, "wikilinks": list(links), "theme": theme, "source_file": f"wiki/briefings/{available_from}.md",
    }


# 晨汇：材料日 01-05（周一）→ 01-06 可知；材料日 01-09（周五）→ 01-10 可知 → 落到周一 01-12；01-12 另有一份三维交叉（盘前，当日可知）。
BRIEFS = [
    _brief("2026-01-06", 1, links=["CPO"], recorded="2026-01-30"), _brief("2026-01-06", 2, links=["PCB"], recorded="2026-01-30"),
    _brief("2026-01-06", 2, theme="固态电池", recorded="2026-01-30"), _brief("2026-01-06", 3, recorded="2026-01-30"),
    _brief("2026-01-10", 2, links=["光模块"], recorded="2026-01-11"),
    _brief("2026-01-12", 1, dims=3, links=["CPO"], market_confirmed=True, recorded="2026-01-12"),
    _brief("2026-01-12", 1, dims=3, links=["锂电"], market_confirmed=False, recorded="2026-01-12"),
    _brief("2026-01-12", 3, dims=3, recorded="2026-01-12"),
]


def test_briefing_lands_on_the_first_trading_day_it_is_knowable_and_two_dimension_tier1_is_not_market_confirmed():
    daily = briefing_daily(BRIEFS, CAL, rps5_names={"2026-01-06": ["CPO", "固态电池", "电子布"], "2026-01-12": ["光模块", "电子布"]})
    # 01-05 早于第一份晨汇可知日 → 缺口，不是 0。
    assert daily[date(2026, 1, 5)] == {"gap": "briefing_before_source", "earliest_available_from": date(2026, 1, 6)}
    d6 = daily[date(2026, 1, 6)]
    assert (d6["briefing_tier1_items"], d6["briefing_tier2_items"], d6["briefing_tier3_items"]) == (1, 2, 1)
    # 二维晨汇：盘面共振不可知 → None（不是 0）；维度 2。
    assert d6["briefing_market_confirmed"] is None and d6["briefing_dimensions"] == 2
    # 机器版对照：Tier 1 / 2 三条里 CPO（双链）与 固态电池（标题）在当日赚钱效应板块里 → 2/3；回填批次写成滞后 24 天。
    assert round(d6["briefing_hit_rps5_pct"], 2) == 66.67 and d6["briefing_lag_days"] == 24 and d6["recorded_at"] == "2026-01-30"
    # 01-07 … 01-09 在起点与最新一期之间、当日没有晨汇 → 缺口 briefing_absent_day。
    assert daily[date(2026, 1, 7)] == {"gap": "briefing_absent_day"} and daily[date(2026, 1, 9)] == {"gap": "briefing_absent_day"}
    # 周一 01-12：周末可知的那份（Tier 2 光模块）与当日盘前的三维交叉合在一起；维度取 3，盘面共振只数 Tier 1 里真带盘面的那条。
    d12 = daily[date(2026, 1, 12)]
    assert (d12["briefing_tier1_items"], d12["briefing_tier2_items"], d12["briefing_tier3_items"]) == (2, 1, 1)
    assert d12["briefing_dimensions"] == 3 and d12["briefing_market_confirmed"] == 1
    # Tier 1 / 2 三条里只有 光模块 在当日赚钱效应板块里 → 1/3；写成不晚于可知日 → 滞后 0。
    assert round(d12["briefing_hit_rps5_pct"], 2) == 33.33 and d12["briefing_lag_days"] == 0
    # 没有赚钱效应板块名的日子，对照那一格是 None。
    assert set(BRIEFING_FIELDS) <= set(d12)


def test_stale_briefing_source_is_a_gap_not_zero():
    cal = CAL + ["2026-01-15", "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21"]
    daily = briefing_daily(BRIEFS, cal, stale_after_days=7)
    # 最新可知日 01-12：01-19 距它 7 天仍算活着（只是当日没有晨汇），01-20 起断更。
    assert daily[date(2026, 1, 19)] == {"gap": "briefing_absent_day"}
    assert daily[date(2026, 1, 20)] == {"gap": "briefing_stale", "latest_available_from": date(2026, 1, 12)}
