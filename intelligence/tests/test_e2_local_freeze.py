"""P3b: audited local runner ceiling; not complete entry/restore/IO acceptance."""
from dataclasses import replace
import json
import socket
import subprocess
from uuid import uuid4

import duckdb
import pytest

from intelligence.services import agent_research, episode_factory, episode_tools
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_scope import EpisodeScope, TOOL_ERROR
from intelligence.services.evidence_capabilities import EvidencePlan, EvidenceRequirement
from intelligence.services.material_permissions import LOCAL_READ_CAPABILITIES
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import ResearchContractError, ResearchTaskContract
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec, UnknownResearchTool


def local_frame(query="不要联网。今天市场怎么样？"):
    return understand_query(query).task_frame


def local_context(query="不要联网。今天市场怎么样？"):
    return build_episode_context(
        local_frame(query), task_id=f"local-read-{uuid4().hex}", capabilities=tuple(sorted(LOCAL_READ_CAPABILITIES)) + (
            "market_data", "financial_data", "news_search", "web_search", "kb_search", "evidence_search", "graph_lookup",
        ), today="2026-07-24", latest_data_date="2026-07-24", timeout=30, synthesis_reserve=0,
    )


def fail_external(*_args, **_kwargs):
    raise AssertionError("unexpected external or uncertified read")


def test_local_ceiling_rebuilds_optional_and_mandatory_requirements():
    context = local_context()
    contract = context.contract
    assert set(contract.allowed_capabilities) == LOCAL_READ_CAPABILITIES
    assert contract.material_contract.data_scope == "local_only"
    assert all(item.capability in contract.allowed_capabilities for item in contract.evidence_plan.requirements)
    assert set(contract.evidence_plan.mandatory_capabilities) <= LOCAL_READ_CAPABILITIES
    assert all(set(output.evidence_types) <= LOCAL_READ_CAPABILITIES for output in contract.required_outputs)
    assert ResearchTaskContract.from_dict(contract.to_dict()) == contract
    assert not {"prime_quote", "prime_news"} & {output.output_id for output in contract.required_outputs}


@pytest.mark.parametrize("mutation", ["capability", "optional", "output"])
def test_local_contract_rejects_permission_readdition_on_replace_and_restore(mutation):
    original = local_context().contract
    payload = original.to_dict()
    if mutation == "capability":
        changes = {"allowed_capabilities": (*original.allowed_capabilities, "market_data")}
        payload["allowed_capabilities"] = list(changes["allowed_capabilities"])
    elif mutation == "optional":
        plan = EvidencePlan(requirements=(EvidenceRequirement("external", "web_search", False),))
        changes = {"evidence_plan": plan}
        payload["evidence_plan"] = plan.to_dict()
    else:
        changes = {"required_outputs": (replace(original.required_outputs[0], evidence_types=("evidence_search",)),)}
        payload["required_outputs"][0]["evidence_types"] = ["evidence_search"]
    with pytest.raises(ResearchContractError, match="local_only"):
        replace(original, **changes)
    with pytest.raises(ResearchContractError, match="local_only"):
        ResearchTaskContract.from_dict(payload)


@pytest.mark.parametrize("effect", ["unknown", "external_or_mixed"])
def test_allowed_capability_is_not_enough_for_unknown_or_external_runner(effect):
    context = local_context()
    # Capability is allowed; the actual implementation is not certified.
    spec = ToolSpec(name="injected", capability="finance_query", description="test", cost="local", freshness="stable", runner=fail_external, io_effect=effect)
    registry = ResearchToolRegistry((spec,))
    events = []

    class Sink:
        def emit(self, kind, payload):
            events.append((kind, dict(payload)))

    scope = EpisodeScope(episode_id="local-read", user_id="test", context=context, registry=registry, event_sink=Sink())
    assert scope.allowed_tools() == ()
    assert scope.model_visible_definitions() == []
    assert not scope.authorize("injected").allowed
    # Even a caller holding the original unbound registry is denied by context.
    with pytest.raises(UnknownResearchTool, match="local_only"):
        registry.execute("injected", {"query": "x"}, context=context, step_id="s", scope=scope, tool_call_id="c")
    assert events[0][0] == TOOL_ERROR
    assert events[0][1]["stage"] == "authorize" and "local_only" in events[0][1]["reason"]
    assert scope.invoked_tools == set()


def test_registry_clones_preserve_ceiling_and_unknown_additions_are_not_visible():
    spec = ToolSpec(name="injected", capability="finance_query", description="test", cost="local", freshness="stable", runner=fail_external)
    registry = ResearchToolRegistry((), read_scope="local_only").with_specs(spec)
    assert registry.read_scope == registry.without("absent").read_scope == "local_only"
    assert registry.with_read_scope("full").read_scope == "local_only"
    assert registry.authorized_specs(("finance_query",)) == ()
    assert registry.with_read_scope("material_only").with_read_scope("full").read_scope == "material_only"


@pytest.mark.parametrize("query", [
    "不要联网。今天市场怎么样？",
    "只用本地已有资料，判断中际旭创最近是否存在已确认的重大风险；没有查到的部分请单独列出。",
])
@pytest.mark.parametrize("source_state", ["current", "missing", "empty", "stale"])
def test_audited_local_queries_run_against_only_temporary_sources(tmp_path, monkeypatch, source_state, query):
    finance = tmp_path / "finance"
    db = finance / "db" / "market_feature_store.duckdb"
    db.parent.mkdir(parents=True)
    con = duckdb.connect(str(db))
    try:
        con.execute("create table fact_market_daily(trade_date date, market_stage varchar, total_amount double, sh_index_pct_chg double)")
        con.execute("create table fact_mainline_theme_daily(trade_date date, theme_name varchar, sector_count integer, min_sort integer)")
        con.execute("""create table fact_mainline_sector_daily(
            trade_date date, theme_code varchar, theme_name varchar, sector_ts_code varchar, sector_name varchar,
            sort_no integer, today_pct double, limit_up_count integer, net_inflow_1d double, amount double,
            cycle_status varchar, cycle_level varchar, startup_date_small date, high_status_label varchar,
            near_breakout_label varchar)""")
        con.execute("""create table fact_sector_daily(
            trade_date date,sector_ts_code varchar,sw_l1 varchar,pct_chg double,diff_ratio double,amount double)""")
        if source_state != "empty":
            source_date = "2026-07-23" if source_state == "stale" else "2026-07-24"
            con.execute("insert into fact_market_daily values (?, '反弹阶段', 22000, 1.2)", [source_date])
            con.execute("insert into fact_mainline_theme_daily values (?, '临时主线', 2, 1)", [source_date])
            con.execute("insert into fact_mainline_sector_daily (trade_date,theme_code,theme_name,sector_ts_code,sector_name) "
                        "values (?, 'LOCAL', '临时主线', 'S1', '临时板块')", [source_date])
    finally:
        con.close()
    if source_state == "missing":
        db.unlink()
    wiki = tmp_path / "wiki"
    relations = wiki / "relations"
    relations.mkdir(parents=True)
    (relations / "evidence_index.json").write_text(json.dumps({"items": [{
        "target": "甲公司", "evidence": "临时公告确认订单20", "source": "临时公告", "source_date": "2026-07-24",
    }]}, ensure_ascii=False))
    users = tmp_path / "users"
    users.mkdir()
    (users / "judgments.jsonl").write_text(json.dumps({
        "ts": "2026-07-23T10:00:00", "memo": "甲公司要看订单兑现", "stocks": ["甲公司"], "themes": [],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    # Count attempts as well as throwing: production fallbacks may swallow errors.
    attempts = []

    def deny_io(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError("unexpected network/subprocess IO")

    monkeypatch.setattr(socket.socket, "connect", deny_io)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_io)
    monkeypatch.setattr(socket, "getaddrinfo", deny_io)
    monkeypatch.setattr(subprocess, "Popen", deny_io)
    # Neither path serves the retained local tools; don't touch host KB/security roots.
    monkeypatch.setattr(episode_tools.entity_anchor, "resolve_entity_anchor", fail_external)
    monkeypatch.setattr(agent_research, "build_default_tools", fail_external)
    monkeypatch.setattr(episode_tools.kb_rag, "retrieve", fail_external)
    monkeypatch.setattr(episode_tools.l3_evidence, "lookup_l3_company", fail_external)
    monkeypatch.setattr(episode_tools.valuation_estimate, "fetch_eastmoney_snapshot", fail_external)
    monkeypatch.setattr(episode_tools.external_market, "resolve_overnight_leaders", fail_external)
    monkeypatch.setattr(episode_tools.evidence_search, "default_semantic_judge", fail_external)
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", fail_external)
    monkeypatch.setattr(episode_tools, "_calc_loader_for", fail_external)
    frame, context = local_frame(query), local_context(query)
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=finance, knowledge_wiki=wiki, memory_users_root=users,
        l3_runner=fail_external, sub_research_runner=fail_external, derived_calculation_runner=fail_external,
    )
    assert registry.read_scope == "local_only"
    assert set(registry.names()) == LOCAL_READ_CAPABILITIES
    assert all(spec.io_effect == "local_read" for spec in registry.authorized_specs())
    assert registry.opening_prefetch == () and registry.calc_loader is None
    arguments = {
        "dataset": "market_daily", "metrics": ["index_return_pct", "total_amount"],
        "dimensions": ["trade_date", "market_stage"],
        "time_range": {"start": "2026-07-24", "end": "2026-07-24"}, "limit": 5,
    }
    if source_state == "missing":
        # Existing engine contract: missing read-only DB raises, never fetches a substitute.
        with pytest.raises(duckdb.IOException, match="database does not exist"):
            registry.execute("finance_query", arguments, context=context, step_id="local-query")
        assert not db.exists()
    else:
        result = registry.execute("finance_query", arguments, context=context, step_id="local-query")
        if source_state == "current":
            assert result.evidence and result.evidence[0].tool == "finance_query"
            assert "22000" in result.observation
        else:
            assert result.evidence == ()
            assert result.gaps
    indexed = registry.execute("evidence_lookup", "甲公司", context=context, step_id="local-index")
    assert indexed.evidence and "临时公告确认订单20" in indexed.evidence[0].detail
    mainline = registry.execute("mainline_context", {}, context=context, step_id="local-mainline")
    if source_state == "current":
        assert mainline.evidence and "临时主线" in mainline.evidence[0].detail
    else:
        assert mainline.evidence == ()
    memory = registry.execute("memory_lookup", "甲公司", context=context, step_id="local-memory")
    assert memory.evidence and "甲公司要看订单兑现" in memory.observation
    assert all(item.evidence_tier == "user_memory" for item in memory.evidence)
    assert all(str(users) in item.internal_locator for item in memory.evidence)
    assert attempts == []


def test_local_prefetch_direct_call_is_not_an_unclassified_bypass(tmp_path, monkeypatch):
    from intelligence.services import asof_prefetch
    monkeypatch.setattr(asof_prefetch, "collect_prefetch_items", fail_external)
    assert episode_tools._opening_prefetch_evidence(local_frame(), local_context(), tmp_path / "absent.duckdb") == ()


@pytest.mark.parametrize("read_scope", ["local_only", "material_only"])
def test_restricted_constructor_and_clones_drop_unclassified_prefetch_and_loader(read_scope):
    evidence = agent_research.AgentEvidence(tool="web_search", title="old", detail="external", source="web")
    registry = ResearchToolRegistry((), opening_prefetch=(evidence,), calc_loader=fail_external, read_scope=read_scope)
    for derived in (registry, registry.with_specs(), registry.without("absent"), registry.with_read_scope("full")):
        assert derived.read_scope == read_scope
        assert derived.opening_prefetch == ()
        assert derived.calc_loader is None


def test_local_factory_does_not_run_unclassified_static_precheck(monkeypatch):
    monkeypatch.setattr(episode_factory, "apply_static_chain_mapping_precheck", fail_external)
    frame = understand_query("不要联网。低空经济产业链有哪些公司？").task_frame
    context = build_episode_context(frame, task_id="local-static", knowledge=object())
    assert context.contract.material_contract.data_scope == "local_only"


def test_local_history_adds_only_audited_readers_not_case_writer(tmp_path, monkeypatch):
    from intelligence.services.material_permissions import LOCAL_EVIDENCE_PRODUCERS
    frame = understand_query("不要联网。这一波农业是怎么走出来的？").task_frame
    assert frame.history_intent is not None
    context = build_episode_context(frame, task_id="local-history", today="2026-07-24")
    registry = episode_tools.build_episode_registry(frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki")
    assert "finance_query" in registry.names()
    assert "history_query" in registry.names()
    assert "save_history_research" not in registry.names()
    assert all({LOCAL_EVIDENCE_PRODUCERS.get(p, p) for p in output.evidence_types} <= set(context.contract.allowed_capabilities) for output in context.contract.required_outputs)
    # Evidence producer aliases do not grant new capabilities or unknown IO.
    assert context.history_intent == frame.history_intent
    assert ResearchTaskContract.from_dict(context.contract.to_dict()) == context.contract


@pytest.mark.parametrize("effect", ["unknown", "external_or_mixed"])
def test_registry_ceiling_denies_replacement_even_with_full_context_before_argument_parsing(effect):
    full = build_episode_context(
        understand_query("今天市场怎么样？").task_frame, task_id="full-context", capabilities=("finance_query",),
    )
    original = ToolSpec(name="finance_query", capability="finance_query", description="local", cost="local", freshness="stable", runner=fail_external, io_effect="local_read")
    registry = ResearchToolRegistry((original,), read_scope="local_only").with_specs(
        replace(original, io_effect=effect, parse_arguments=fail_external)
    ).without("absent").with_read_scope("full")
    scope = EpisodeScope(episode_id="full-context", user_id="test", context=full, registry=registry)
    assert not scope.authorize("finance_query").allowed
    assert scope.model_visible_definitions() == []
    with pytest.raises(UnknownResearchTool, match="local_only"):
        registry.execute("finance_query", {}, context=full, step_id="denied")


def test_invalid_io_effect_and_read_scope_are_rejected():
    with pytest.raises(ValueError, match="IO effect"):
        ToolSpec(name="bad", capability="finance_query", description="test", cost="local", freshness="stable", runner=fail_external, io_effect="probably_local")
    with pytest.raises(ValueError, match="read scope"):
        ResearchToolRegistry((), read_scope="probably_local")
