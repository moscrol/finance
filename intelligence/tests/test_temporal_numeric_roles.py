"""Offline regressions: numeric roles must not silently move market reads."""
from datetime import date
from uuid import uuid4
import socket

import duckdb
import pytest

from intelligence.services.temporal_contract import compile_temporal_contract, market_review_requested_date, yearless_date_matches

TODAY = date(2026, 10, 8)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline regression attempted network access")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


QUANTITIES = [
    "当前市场主线是什么？我现在仓位 1/3 合适吗",
    "当前市场主线是什么？持仓2/3合适吗",
    "估值处于历史1/3分位，主线怎么看",
    "看5/10/20日均线判断市场",
    "看5/10日均线判断市场",
    "仓位从1/3到2/3，当前主线如何",
    "当前胜率1/2是否足够",
    "这个数1/3是什么意思",
    "半仓 1/2", "3/10 分位", "2/3 的利润", "止损设在 1/3 处",
]


@pytest.mark.parametrize("query", QUANTITIES)
def test_quantities_do_not_establish_calendar_authority(query):
    contract = compile_temporal_contract(query, today=TODAY)
    assert contract.market_target is None
    assert contract.information_cutoff is None
    assert not contract.errors
    assert market_review_requested_date(query, today=TODAY) is None


@pytest.mark.parametrize("query", [
    "复盘9/30的A股", "回看9.30", "9/30", "9/30的市场",
    "9.30的复盘数据你怎么解读", "那9.30呢", "9/30涨家数多少",
    "9/30 收盘", "9/30的连板梯队",
    "股价在9月30日涨到2.5元，复盘当日",
    "仓位1/3，复盘9/30的市场", "复盘9/30的市场，仓位1/3",
])
def test_explicit_calendar_roles_survive_numeric_noise(query):
    contract = compile_temporal_contract(query, today=TODAY)
    assert contract.market_target.end == "2026-09-30"
    assert not contract.errors


def test_ranges_comparisons_cutoffs_and_followup_inheritance():
    previous = compile_temporal_contract("复盘9/28至9/30，只用截至当日的信息", today=TODAY)
    # A range cannot authorize singular 当日; use the explicitly scoped endpoint.
    assert previous.errors
    previous = compile_temporal_contract("复盘9/28至9/30，只用截至区间结束日的信息", today=TODAY)
    assert previous.market_target.start == "2026-09-28"
    assert previous.market_target.end == previous.information_cutoff == "2026-09-30"
    next_turn = compile_temporal_contract("那么仓位1/3合适吗", today=TODAY, continuing=True, previous=previous)
    assert next_turn.market_target == previous.market_target
    assert next_turn.information_cutoff == previous.information_cutoff
    assert [m.group() for m in yearless_date_matches("比较9/23和9/24的主线")] == ["9/23", "9/24"]
    contract = compile_temporal_contract("复盘9/30，只用截至10/7的信息，仓位1/3", today=TODAY)
    assert contract.market_target.end == "2026-09-30"
    assert contract.information_cutoff == "2026-10-07"


@pytest.mark.parametrize("query", QUANTITIES[:5])
def test_real_context_registry_and_model_projection_use_latest_not_fraction(tmp_path, monkeypatch, query):
    from pathlib import Path
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_tools import build_episode_registry
    from intelligence.services.query_resolution import QueryResolution
    from intelligence.services.query_understanding import understand_query
    from intelligence.services.turn_controller import decide_turn
    from intelligence.services.research_harness import FinanceResearchHarness

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    class Resolver:
        def resolve(self, text):
            return QueryResolution(understand_query(text), None)
    decision = decide_turn(query, resolver=Resolver(), today=TODAY,
                           llm_complete=lambda *a, **kw: (None, None, "disabled"))
    assert decision.task_frame is not None
    context = build_episode_context(decision.task_frame, task_id=str(uuid4()), capabilities=("mainline_context",),
                                    today=TODAY.isoformat(), latest_data_date="2026-10-07")
    root = tmp_path / "finance"
    db = root / "db/market_feature_store.duckdb"
    db.parent.mkdir(parents=True)
    with duckdb.connect(str(db)) as con:
        con.execute((Path(__file__).parents[2] / "market_feature_store/schema.sql").read_text())
        for day, theme, amount in [("2026-01-03", "错误旧日哨兵", 13), ("2026-10-07", "合法最新主线", 1007)]:
            con.execute("insert into fact_market_daily (trade_date,total_amount) values (?,?)", [day, amount])
            con.execute("insert into fact_mainline_sector_daily (trade_date,theme_code,theme_name,sector_ts_code,sector_name,sort_no,today_pct,amount) values (?,?,?,'S1',?,1,2,?)", [day, theme, theme, theme, amount * 10000])
            con.execute("insert into fact_sector_daily_generation (trade_date,sector_universe_snapshot_id,sector_ts_code,sector_name,pct_chg,amount) values (?,'legacy','S1',?,2,?)", [day, theme, amount])
    registry = build_episode_registry(decision.task_frame, context, finance_root=root, knowledge_wiki=tmp_path / "wiki", l3_runner=None)
    observation = registry.execute("mainline_context", {}, context=context, step_id="numeric-role:1")
    projection = FinanceResearchHarness().project_tool_result(observation, evidence_so_far=observation.evidence, seen_prose=set())
    assert observation.trace.status == "success"
    assert observation.query_basis["snapshot_date"] == "2026-10-07"
    assert {item.source_date for item in observation.evidence} == {"2026-10-07"}
    assert "合法最新主线" in projection.model_content
    assert "错误旧日哨兵" not in projection.model_content
    assert all(item.freshness != "current" for item in observation.evidence)


@pytest.mark.parametrize(("query", "expected"), [
    ("10/8 复盘", "2026-10-08"), ("3/10日的龙虎榜", "2026-03-10"),
    ("10月8日", "2026-10-08"),
])
def test_review_specific_legal_short_dates(query, expected):
    assert compile_temporal_contract(query, today=TODAY).market_target.end == expected


@pytest.mark.parametrize(("query", "dates"), [
    ("今天和 9/30 比", ("2026-10-08", "2026-09-30")),
    ("9/29 和 9/30 对比", ("2026-09-29", "2026-09-30")),
    ("9/29 和 9/30 的涨停对比", ("2026-09-29", "2026-09-30")),
])
def test_discrete_date_comparison_clarifies_before_retrieval(query, dates):
    from intelligence.services.turn_controller import decide_turn
    contract = compile_temporal_contract(query, today=TODAY)
    assert contract.market_target is None
    assert contract.errors and all(day in contract.errors[0] for day in dates)
    assert market_review_requested_date(query, today=TODAY) is None
    class ForbiddenResolver:
        def resolve(self, _):
            pytest.fail("comparison must clarify before retrieval/resolver")
    decision = decide_turn(query, today=TODAY, resolver=ForbiddenResolver())
    assert decision.lane == "clarify"
    assert decision.capabilities == ()


@pytest.mark.parametrize("explicit_history", [False, True])
def test_bad_current_label_cannot_use_parsed_target_as_freshness_authority(tmp_path, monkeypatch, explicit_history):
    from intelligence.services.agent_research import AgentEvidence
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.services.query_resolution import QueryResolution
    from intelligence.services.query_understanding import understand_query
    from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolRunResult, ToolSpec
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.services.turn_controller import decide_turn

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    class Resolver:
        def resolve(self, text):
            return QueryResolution(understand_query(text), None)
    query = "复盘2026年1月3日的A股，只用截至当日的信息" if explicit_history else "当前市场主线是什么"
    decision = decide_turn(query, resolver=Resolver(), today=TODAY,
                           llm_complete=lambda *a, **kw: (None, None, "disabled"))
    context = build_episode_context(decision.task_frame, task_id=str(uuid4()), capabilities=("mainline_context",),
                                    today=TODAY.isoformat(), latest_data_date="2026-10-07")
    # Deliberately inject a provider bug independently of date parsing.
    card = AgentEvidence(tool="mainline_context", title="合成历史事实", detail="01-03源值",
                         source="fixture", source_date="2026-01-03", freshness="current")
    registry = ResearchToolRegistry((ToolSpec("mainline_context", "mainline_context", "fixture", "local", "current",
        lambda *_: ToolRunResult((card,), "合成记录", ProviderTrace("fixture", "mainline_context", "success", source_trade_date="2026-01-03"))),))
    observed = registry.execute("mainline_context", {"query": query}, context=context, step_id="freshness:1")
    assert observed.evidence and observed.evidence[0].source_date == "2026-01-03"
    assert observed.evidence[0].freshness == "historical"
    projected = FinanceResearchHarness().project_tool_result(observed, evidence_so_far=observed.evidence, seen_prose=set())
    assert '"freshness": "current"' not in projected.model_content


def test_long_linked_date_list_does_not_recurse():
    text = "比较" + "和".join(["9/30"] * 1200) + "的主线"
    assert len(yearless_date_matches(text)) == 1200
