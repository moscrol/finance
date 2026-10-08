"""Audited local history readers execute with IO tripwires and temporary sources."""

from dataclasses import replace
from datetime import date
import json
import socket
import subprocess

import duckdb
import pytest

from intelligence.services import agent_research, episode_tools
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.historical_research.episode import HistorySession
from intelligence.services.historical_research.intent import HistoryIntent
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec, UnknownResearchTool
from intelligence.services.run_store import RunStore
from intelligence.services.provider_observability import ProviderTrace
from intelligence.tests.test_historical_research_episode import _history_root


def test_local_history_execution_pagination_and_scope_without_external_attempts(tmp_path, monkeypatch):
    path = _history_root(tmp_path)
    with duckdb.connect(str(path)) as con:
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN market_stage TEXT")
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN market_stage_source TEXT")
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN market_stage_confidence DOUBLE")
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN cycle_stage TEXT")
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN cycle_stage_source TEXT")
        con.execute("UPDATE fact_market_daily SET market_stage='下降阶段', market_stage_source='local:test', market_stage_confidence=0.9")
        con.execute("INSERT INTO fact_market_daily (trade_date, sh_index_pct_chg, market_stage) VALUES ('2026-08-05',99,'未来阶段')")
        con.execute("CREATE TABLE fact_mainline_theme_daily(trade_date DATE, theme_name TEXT, sector_count INT, min_sort INT)")
        con.execute("INSERT INTO fact_mainline_theme_daily VALUES ('2026-08-04','窗内主线',2,1),('2026-08-05','未来主线',9,1)")
        con.execute("ALTER TABLE fact_sector_daily ADD COLUMN sw_l1 TEXT")
        con.execute("""CREATE TABLE fact_mainline_sector_daily(
            trade_date DATE, theme_code TEXT, theme_name TEXT, sector_ts_code TEXT, sector_name TEXT,
            sort_no INT, today_pct DOUBLE, limit_up_count INT, net_inflow_1d DOUBLE, amount DOUBLE,
            cycle_status TEXT, cycle_level TEXT, startup_date_small DATE, high_status_label TEXT,
            near_breakout_label TEXT)""")
        con.execute("INSERT INTO fact_mainline_sector_daily (trade_date,theme_code,theme_name,sector_ts_code,sector_name) "
                    "VALUES ('2026-08-04','IN','窗内主线','A.FP','农业'),('2026-08-05','OUT','未来主线','OUT','未来板块')")
    before = path.read_bytes()
    question = "不要联网。以2026-08-04为信息截止日，只研究2026-08-03至2026-08-04这波农业怎么走出来的。"
    frame = understand_query(question).task_frame
    store = RunStore("alice", root=tmp_path / "runs")
    run = store.create_run(question, "ask", session_id="same-conversation")
    session = HistorySession(store, run.run_id, "same-conversation")
    context = build_episode_context(frame, task_id=run.run_id, today="2026-08-05", latest_data_date="2026-08-05", capabilities=("finance_query", "mainline_context"))
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("unclassified network/subprocess attempt")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(agent_research, "build_default_tools", forbidden)
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", forbidden)
    monkeypatch.setattr(episode_tools, "_calc_loader_for", forbidden)
    monkeypatch.setattr(episode_tools.entity_anchor, "resolve_entity_anchor", forbidden)
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki",
        history_session=session,
    )
    assert {"history_query", "read_history_result"} <= set(registry.names())
    assert "save_history_research" not in registry.names()
    assert registry.opening_prefetch == () and registry.calc_loader is None
    query = dict(operation="inspect_history", start="2026-08-03", end="2026-08-04", entity_kind="market", entity_codes=["000001.SH"], preview_limit=1)
    result = registry.execute("history_query", query, context=context, step_id="query")
    ref = result.telemetry["result_ref"]
    assert len(session.read(ref)["rows"]) == 2
    page = registry.execute("read_history_result", dict(result_ref=ref, offset=1, limit=1), context=context, step_id="page")
    assert any("2026-08-04" in item.detail for item in page.evidence)
    assert "未来阶段" not in json.dumps(session.read(ref), ensure_ascii=False)
    observed = registry.execute("finance_query", dict(
        dataset="market_daily", dimensions=["trade_date", "market_stage", "market_stage_source", "cycle_stage", "cycle_stage_source"],
        metrics=["index_return_pct", "market_stage_confidence"], time_range=dict(start="2026-08-04", end="2026-08-04"), limit=5,
    ), context=context, step_id="facts")
    assert "local:test" in observed.observation and "未来阶段" not in observed.observation
    mainline = registry.execute("mainline_context", {}, context=context, step_id="mainline")
    from intelligence.services.research_harness import FinanceResearchHarness

    public = FinanceResearchHarness().project_tool_result(mainline, evidence_so_far=mainline.evidence,
                                                         seen_prose=set()).model_content
    assert "窗内主线" in public and "未来主线" not in public
    for item in (*observed.evidence, *mainline.evidence):
        assert item.source_date <= "2026-08-04"
    with pytest.raises(ValueError, match="outside_authorized_scope"):
        registry.execute("history_query", dict(query, end="2026-08-05"), context=context, step_id="outside")
    with pytest.raises(UnknownResearchTool):
        registry.execute("save_history_research", {}, context=context, step_id="write-denied")
    other = store.create_run(question, "ask", session_id="other-conversation")
    with pytest.raises(ValueError, match="outside this conversation"):
        HistorySession(store, other.run_id, "other-conversation").read(ref)
    assert path.read_bytes() == before
    assert attempts == []


@pytest.mark.parametrize("source_date", ["2026-08-05", "2026-08-02", None])
def test_non_history_tool_cannot_return_forbidden_history_facts(source_date):
    frame = understand_query("不要联网。只研究2026-08-03至2026-08-04这波农业怎么走出来的").task_frame
    context = build_episode_context(frame, task_id=f"filter-{source_date}", today="2026-08-05")

    def runner(*_):
        return ([agent_research.AgentEvidence(tool="finance_query", title="forbidden-title", detail="forbidden-body", source="fixture", source_date=source_date)],
                "forbidden-observation", ProviderTrace(provider="test", capability="finance_query", status="success"))

    registry = ResearchToolRegistry((ToolSpec(name="finance_query", capability="finance_query", description="test", cost="local", freshness="historical", runner=runner, io_effect="local_read"),))
    result = registry.execute("finance_query", "x", context=context, step_id="filter")
    assert not result.evidence
    assert "forbidden" not in result.observation
    assert result.gaps


@pytest.mark.parametrize("mode", ["mixed", "empty", "above_scope"])
def test_scope_filters_prose_and_unknown_dates_as_well_as_evidence(mode):
    frame = understand_query("不要联网。只研究2026-08-03至2026-08-04这波农业怎么走出来的").task_frame
    context = build_episode_context(frame, task_id=f"prose-filter-{mode}", today="2026-08-05")
    if mode == "above_scope":
        # Do not depend on the factory also clamping the cutoff to the scope end.
        context = replace(context, information_cutoff=InformationCutoff(date(2026, 8, 5), "requested"))
    dates = ["2026-08-04", "2026-08-05", None] if mode == "mixed" else [] if mode == "empty" else ["2026-08-05"]

    def runner(*_):
        evidence = [agent_research.AgentEvidence(tool="finance_query", title="allowed" if d == "2026-08-04" else "forbidden", detail="allowed-body" if d == "2026-08-04" else "forbidden-body", source="fixture", source_date=d) for d in dates]
        return evidence, "forbidden-prose", ProviderTrace(provider="test", capability="finance_query", status="success", source_trade_date="2026-08-05")

    registry = ResearchToolRegistry((ToolSpec(name="finance_query", capability="finance_query", description="test", cost="local", freshness="historical", runner=runner, io_effect="local_read"),))
    result = registry.execute("finance_query", "x", context=context, step_id="filter")
    assert "forbidden" not in result.observation
    assert len(result.evidence) == (1 if mode == "mixed" else 0)
    assert result.gaps


def test_cutoff_rejects_query_even_inside_authorized_dates(tmp_path):
    from intelligence.services.historical_research.query import HistoryQuery, HistoryQuerySpec

    path = _history_root(tmp_path)
    spec = HistoryQuerySpec.from_arguments(dict(operation="inspect_history", start="2026-08-03", end="2026-08-04"))
    # Authorisation end and knowledge date are independent; minimum wins.
    assert HistoryIntent("retrospective_discovery", "2026-08-01", "2026-08-31", strict_window=True).requested_end == "2026-08-31"
    with pytest.raises(ValueError, match="cutoff"):
        HistoryQuery(path).run(spec, information_cutoff=InformationCutoff(date(2026, 8, 3), "requested"), deadline=ResearchDeadline.from_timeout(5))
