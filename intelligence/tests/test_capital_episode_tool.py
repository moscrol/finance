"""真实 Episode 装配/派发：资金工具的授权、日期和证据边界。"""
from dataclasses import replace
from datetime import date, timedelta
from uuid import uuid4

import duckdb
import pytest
import subprocess

from intelligence.services import episode_tools, l3_evidence, market_capital as capital
from intelligence.services.evidence_capabilities import runtime_capabilities_for_frame
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.material_contract import compile_material_contract
from intelligence.services.research_contract import release_root_budget
from intelligence.services.research_tool_registry import UnknownResearchTool
from intelligence.services.task_frame import TaskFrame, classify_top_level_regions


def frame(question="贵州茅台两融和大宗解禁情况"):
    return TaskFrame(
        raw_question=question, user_goal="核实个股资金事实", question_type="stock_deep_dive",
        subject="贵州茅台", subject_kind="company", market_scope="A股", timeframe="当前",
        required_outputs=("direct_assessment",), assumptions=(), ambiguities=(),
        clarification_question=None, evidence_policy="company_multi_layer_evidence", confidence=1.0,
    )


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "finance"
    (root / "db").mkdir(parents=True)
    con = duckdb.connect(str(root / "db/market_feature_store.duckdb"))
    con.execute("create table fact_stock_daily (trade_date date, stock_ts_code varchar, stock_name varchar)")
    con.execute("insert into fact_stock_daily values (?, '600519.SH', '贵州茅台')", [date.today()])
    con.close()
    ids = []
    def build(task=None, capabilities=None, **kwargs):
        task = task or frame()
        task_id = f"capital-test-{uuid4()}"
        ids.append(task_id)
        ctx = build_episode_context(task, task_id=task_id, timeout=30, today=date.today().isoformat(),
                                    capabilities=capabilities)
        registry = episode_tools.build_episode_registry(task, ctx, finance_root=root,
            knowledge_wiki=tmp_path / "wiki", l3_runner=None, **kwargs)
        return registry, ctx
    yield build
    for task_id in ids:
        release_root_budget(task_id)


def test_capability_projects_from_real_intent_without_new_question_type(monkeypatch):
    monkeypatch.delenv("WORKBENCH_TOOL_AUTHORIZATION", raising=False)
    assert "capital_data" in runtime_capabilities_for_frame(frame())
    assert "capital_data" not in runtime_capabilities_for_frame(frame("贵州茅台护城河"))
    concept = replace(frame("融资融券是什么意思"), question_type="concept_definition",
                      evidence_policy="general", required_outputs=("direct_definition",))
    assert "capital_data" not in runtime_capabilities_for_frame(concept)


def test_authorized_tool_executes_shared_fetcher_and_has_real_rows_only(setup, monkeypatch):
    monkeypatch.setattr(capital, "fetch_margin_rows", lambda *a, **k: [
        capital.MarginRow(date.today().isoformat(), 170.59, 1.15, None),
    ])
    registry, ctx = setup()
    spec = registry.resolve("capital_data")
    assert spec.io_effect == "external_or_mixed"
    assert "不是公司公告" in spec.contract
    result = registry.execute("capital_data", {"query": "600519 两融"}, context=ctx, step_id="test")
    assert result.trace.status == "success"
    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.source_date == date.today().isoformat()
    assert evidence.evidence_tier == "L2_structured"
    assert evidence.observations[0].value == 170.59
    assert evidence.observations[0].subject == "600519.SH"
    assert "None" not in evidence.detail
    assert evidence.content_hash


def test_empty_or_failure_produces_no_evidence(setup, monkeypatch):
    monkeypatch.setattr(capital, "fetch_unlock_rows", lambda *a, **k: [])
    registry, ctx = setup()
    result = registry.execute("capital_data", {"query": "600519 解禁"}, context=ctx, step_id="test")
    assert result.trace.status == "empty"
    assert not result.evidence
    assert result.gaps
    def fail(*args, **kwargs):
        raise capital.CapitalFetchError("request_error", "不能判断是否有记录")
    monkeypatch.setattr(capital, "fetch_unlock_rows", fail)
    result = registry.execute("capital_data", {"query": "600519 解禁"}, context=ctx, step_id="test2")
    assert result.trace.status == "request_error"
    assert not result.evidence
    assert "不能判断" in result.observation


def test_future_schedule_date_is_not_information_date(setup, monkeypatch):
    event_day = (date.today() + timedelta(days=10)).isoformat()
    monkeypatch.setattr(capital, "fetch_unlock_rows", lambda *a, **k: [
        capital.UnlockRow(event_day, "定向增发机构配售股份", 22999.19, 21.23),
    ])
    registry, ctx = setup()
    result = registry.execute("capital_data", {"query": "600519 解禁"}, context=ctx, step_id="test")
    assert result.trace.status == "success"
    assert len(result.evidence) == 1
    assert result.evidence[0].source_date == date.today().isoformat()
    assert event_day in result.evidence[0].detail
    assert "非披露日" in result.evidence[0].detail


@pytest.mark.parametrize("suffix", [
    "当时已知的解禁情况", "的解禁安排，不要用当前日程回填",
    "彼时的解禁安排，而非目前日程",
])
def test_explicit_history_is_not_unresolved_by_reference_words(setup, monkeypatch, suffix):
    def forbidden(*args, **kwargs):
        pytest.fail("historical unlock must not fetch current schedule")
    monkeypatch.setattr(capital, "fetch_unlock_rows", forbidden)
    registry, ctx = setup(frame(f"截至2025-08-01贵州茅台{suffix}"))
    result = registry.execute("capital_data", {"query": "600519 截至2025-08-01 解禁"},
                              context=ctx, step_id="explicit-history")
    assert result.trace.status == "not_attempted"
    assert result.trace.reason_code == "historical_snapshot_unavailable"
    assert "YYYY-MM-DD" not in result.observation
    assert not result.evidence


@pytest.mark.parametrize("relative", ["昨天", "前日", "上周", "去年", "3天前"])
def test_relative_date_with_unrelated_iso_date_still_refuses(setup, monkeypatch, relative):
    def forbidden(*args, **kwargs):
        pytest.fail("an unrelated explicit date may not erase a relative boundary")
    monkeypatch.setattr(capital, "fetch_unlock_rows", forbidden)
    registry, ctx = setup(frame(f"截至{relative}贵州茅台解禁安排，比较2025-08-01的情况"))
    result = registry.execute("capital_data", {"query": "600519 解禁"},
                              context=ctx, step_id="unresolved-relative")
    assert result.trace.reason_code == "historical_date_unresolved"
    assert not result.evidence


def test_historical_question_cannot_be_relaxed_by_current_tool_query(setup, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("historical unlock must not fetch current schedule")
    monkeypatch.setattr(capital, "fetch_unlock_rows", forbidden)
    registry, ctx = setup(frame("截至2025-08-01贵州茅台解禁情况"))
    result = registry.execute("capital_data", {"query": f"600519 截至{date.today()}解禁"}, context=ctx, step_id="test")
    assert result.trace.status == "not_attempted"
    assert result.trace.reason_code == "historical_snapshot_unavailable"
    assert not result.evidence


@pytest.mark.parametrize("when", ["截至昨天", "上周", "截至去年", "当时", "截至2025年8月"])
def test_ambiguous_historical_request_cannot_be_rewritten_to_today(setup, monkeypatch, when):
    def forbidden(*args, **kwargs):
        pytest.fail("unresolved historical boundary may not fetch")
    monkeypatch.setattr(capital, "fetch_unlock_rows", forbidden)
    registry, ctx = setup(frame(f"{when}贵州茅台解禁情况"))
    result = registry.execute("capital_data", {"query": f"600519 截至{date.today()}解禁"},
                              context=ctx, step_id="test")
    assert result.trace.status == "not_attempted"
    assert result.trace.reason_code == "historical_date_unresolved"
    assert "YYYY-MM-DD" in result.observation
    assert not result.evidence


def test_unrecognized_slice_is_gap_without_network(setup, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("wrong slice may not fetch")
    monkeypatch.setattr(capital, "fetch_margin_rows", forbidden)
    registry, ctx = setup()
    result = registry.execute("capital_data", {"query": "贵州茅台十大股东"}, context=ctx, step_id="test")
    assert not result.evidence
    assert "股东名单" in result.observation


def test_not_registered_without_authorization_or_sealed_external_permission(setup):
    registry, _ctx = setup(capabilities=("kb_search",))
    with pytest.raises(UnknownResearchTool):
        registry.resolve("capital_data")
    registry, _ctx = setup(fixture_policy=episode_tools.SealedFixturePolicy())
    with pytest.raises(UnknownResearchTool):
        registry.resolve("capital_data")


def test_official_l3_error_reaches_registry_trace_and_not_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(l3_evidence.subprocess, "run", lambda *a, **k:
        subprocess.CompletedProcess([], 0, "[fetch] query failed: HTTP Error 403: Forbidden\n[]", ""))
    monkeypatch.setenv("FINANCE_L3_CACHE_TTL_SECONDS", "0")
    task_id = f"l3-status-test-{uuid4()}"
    task = frame("贵州茅台公告")
    ctx = build_episode_context(task, task_id=task_id, timeout=30, today=date.today().isoformat(),
                                capabilities=("l3_lookup",))
    try:
        registry = episode_tools.build_episode_registry(task, ctx, finance_root=tmp_path,
                                                        knowledge_wiki=tmp_path / "wiki")
        result = registry.execute("l3_lookup", {"query": "600519"}, context=ctx, step_id="l3-test")
        assert result.trace.status == "request_error"
        assert not result.evidence
        assert "403" in result.observation
        assert "不能据此断言" in result.observation
    finally:
        release_root_budget(task_id)


def test_local_only_cannot_expose_capital_provider(setup):
    task = frame("不要联网。贵州茅台两融情况")
    contract = compile_material_contract(classify_top_level_regions(task.raw_question))
    assert contract is not None and contract.data_scope == "local_only"
    registry, ctx = setup(replace(task, material_contract=contract))
    assert "capital_data" not in ctx.contract.allowed_capabilities
    assert "capital_data" not in [s.name for s in registry.authorized_specs()]
