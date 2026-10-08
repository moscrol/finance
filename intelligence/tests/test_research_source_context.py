"""Owner → registry → actual model projection, including non-fact roles."""

from dataclasses import replace
import json

import pytest

from intelligence.services import ask_blocks, episode_tools
from intelligence.services.reading_baseline import ReadingRule
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolRunResult, ToolSpec
from intelligence.services.owned_results import D4_SOURCE_DESCRIPTOR, compile_owned_results
from intelligence.tests.owned_result_support import frame_context


def _snapshot(status="available"):
    fact = ask_blocks.MainlineSectorFact(
        trade_date="2026-09-30", theme_code="T1", theme_name="主题甲",
        sector_ts_code="S1", sector_name="板块甲", sort_no=1,
        today_pct=1.2, limit_up_count=2, net_inflow_1d=None, amount=6_000_000,
        cycle_status=None, cycle_level=None, startup_date_small=None,
        high_status_label=None, near_breakout_label=None, sector_pct=1.2,
        diff_ratio=11.0, sector_amount=600.0, sw_l1=None,
        pct_source="sector_daily", amount_source="sector_daily",
    )
    facts = (fact, replace(fact, theme_code="T2", theme_name="主题乙")) if status == "available" else ()
    return ask_blocks.MainlineContextSnapshot(
        status=status, market_date="2026-09-30", snapshot_date="2026-09-30",
        requested_as_of="2026-09-30", total_rows=4, total_groups=2,
        groups=tuple(ask_blocks.MainlineGroupCoverage(name, 2, 1, 1, ())
                     for name in ("主题甲", "主题乙")),
        facts=facts,
        signals=tuple(ask_blocks.MainlinePriceVolumeSignal(
            trade_date=f.trade_date, theme_code=f.theme_code, sector_ts_code=f.sector_ts_code,
            sector_pct=f.sector_pct, diff_ratio=f.diff_ratio, sector_amount=f.sector_amount,
            strict_double_red=True, state="true", theme_name=f.theme_name,
            inputs_complete=True, missing_inputs=(),
        ) for f in facts),
        history_start="2026-09-10", history_end="2026-09-30",
        history=(ask_blocks.MainlineHistoryCoverage("主题甲", 3, "2026-09-21", "2026-09-30", 6, True),),
        guidance=(ReadingRule("R-METHOD", "读法", "方法正文并非行情事实", "原方法来源"),),
    )


def _project(run_result, *, context=None):
    context = context or frame_context()[1]
    registry = ResearchToolRegistry((ToolSpec(
        name="mainline_context", capability="mainline_context", description="主线",
        cost="local", freshness="current", runner=lambda _query, _ctx: run_result,
        io_effect="local_read",
    ),))
    observation = registry.execute("mainline_context", {"query": "主线"},
                                   context=context, step_id="source-context-step")
    projection = FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=observation.evidence, seen_prose=frozenset(),
    )
    return observation, projection, json.loads(projection.model_content)


@pytest.mark.parametrize("status,expected", [
    ("available", "success"), ("empty", "empty"), ("stale", "stale"), ("unavailable", "request_error"),
])
def test_d4_owner_context_reaches_registry_and_actual_model(status, expected):
    result = episode_tools.mainline_snapshot_tool_result(_snapshot(status))
    observation, projection, facing = _project(result)
    context = facing["source_context"]
    assert facing["status"] == context["result_status"] == observation.trace.status == expected
    assert context == observation.source_context == projection.audit_payload["source_context"]
    assert facing["query_basis"] == result.query_basis == observation.query_basis
    assert context["schema"] == "research_source_context_v1"
    assert context["execution_scope"]["row_unit"] == "theme_sector_records"
    assert context["execution_scope"]["preview_limit_per_group"] == 8
    assert context["qualifications"]["calendar_continuity"] == "unknown"
    assert context["qualifications"]["unique_stock_count"] == "unknown"
    assert context["qualifications"]["group_disjointness"] == "unknown"
    assert context["qualifications"]["index_contribution"] == "unknown"
    assert context["qualifications"]["capital_cause"] == "unknown"
    assert context["method_sources"] == [{"id": "R-METHOD", "source": "原方法来源", "role": "method_guidance"}]
    assert len(observation.evidence) == (2 if status == "available" else 0)
    assert all("R-METHOD" not in item.title for item in observation.evidence)


def test_d4_context_does_not_duplicate_values_or_change_owned_source_contract():
    result = episode_tools.mainline_snapshot_tool_result(_snapshot())
    observation, _, facing = _project(result)
    assert facing["query_basis"]["schema"] == D4_SOURCE_DESCRIPTOR["schema"]
    assert facing["query_basis"]["history"][0]["day_count"] == 3
    assert "distinct_observed_dates" in facing["source_context"]["metric_semantics"]["history.day_count"]
    assert "date_span" in facing["source_context"]["metric_semantics"]["history.first_date,last_date"]
    assert "sector_amount" not in facing["source_context"]["execution_scope"]
    assert "600.0" not in json.dumps(facing["source_context"])
    catalogue = compile_owned_results(observation, None)
    assert catalogue.blocks
    assert catalogue.ref_for(("2026-09-30", "T1", "S1"), "strict_double_red")


def test_legacy_and_unknown_source_context_do_not_gain_qualifications():
    source = episode_tools.mainline_snapshot_tool_result(_snapshot())
    legacy = ToolRunResult(source.evidence, "5天连续、唯一家数：伪装散文", source.trace)
    observation, _, facing = _project(legacy)
    assert observation.source_context == {}
    assert "source_context" not in facing
    unknown = replace(legacy, source_context={"schema": "unknown", "qualifications": {"unique_stock_count": "verified"}})
    assert _project(unknown)[0].source_context == {}


def test_future_context_is_quarantined_with_its_basis_and_facts():
    from datetime import date
    from intelligence.services.research_contract import InformationCutoff

    context = replace(frame_context()[1], information_cutoff=InformationCutoff(date(2026, 9, 29), "requested"))
    result = episode_tools.mainline_snapshot_tool_result(_snapshot())
    observation, projection, facing = _project(result, context=context)
    assert observation.trace.status == facing["status"] == "future_of_cutoff"
    assert observation.evidence == ()
    assert "source_context" not in facing and "query_basis" not in facing
    assert observation.telemetry["temporal_withheld"]["source_context"] == result.source_context
    assert "R-METHOD" not in projection.model_content


def test_opening_roles_reach_actual_episode_client_without_promoting_priors():
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelTurn
    from intelligence.services.user_task import MethodCandidate

    frame, context = frame_context()
    frame = replace(frame, method_candidates=(MethodCandidate("条件", "未来结果", "环境", ("反例",)),))
    context = replace(context, conversation_context="用户此前的条件看法", perspective_context="观点侧重",
                      stance_pack="个人先验")
    context = replace(context, contract=replace(context.contract, task_frame_hash=frame.task_frame_hash))
    registry = ResearchToolRegistry(())

    class CaptureClient:
        messages = ()

        def complete(self, *, messages, tools, timeout):
            self.messages = tuple(dict(message) for message in messages)
            return ModelTurn(json.dumps({
                "status": "partial", "draft": "尚未查证当前市场事实。", "gaps": ["未取得事实证据"],
                "bindings": [{"output_id": "direct_assessment", "evidence_hashes": [],
                              "basis": "evidence", "gap": "未取得事实证据"}],
            }, ensure_ascii=False), ())

    client = CaptureClient()
    outcome = ContinuousAgentEpisode(client).run(task_frame=frame, context=context, registry=registry)
    payload = json.loads(next(message["content"] for message in client.messages if message["role"] == "user"))
    roles = payload["input_roles"]
    assert roles["task_frame"] == "user_request"
    assert roles["task_frame.method_candidates"] == "unverified_method_candidates"
    assert roles["research_contract.evidence_plan"] == "retrieval_requirements"
    assert roles["conversation_context"] == "conversation_and_user_prior"
    assert roles["reading_baseline"] == "domain_method_guidance"
    assert roles["perspective_context"] == "viewpoint"
    assert roles["stance_pack"] == "personal_prior"
    assert payload["task_frame"]["method_candidates"][0]["status"] == "candidate_unverified"
    assert outcome.evidence == ()


@pytest.mark.parametrize("status", ["partial", "stale", "request_error", "private_unknown_provider_status"])
def test_context_does_not_turn_invalid_or_partial_d4_into_owned_facts(status):
    result = episode_tools.mainline_snapshot_tool_result(_snapshot())
    result = replace(result, trace=replace(result.trace, status=status))
    observation, _, facing = _project(result)
    assert "owned_results" not in facing
    assert facing["source_context"]["qualifications"]["unique_stock_count"] == "unknown"
    assert "private_unknown_provider_status" not in json.dumps(facing)
    if status == "private_unknown_provider_status":
        assert facing["status"] == facing["source_context"]["result_status"] == "unknown_provider_status"
        assert observation.evidence == ()


def test_source_context_cannot_promote_material_or_methods_into_l4_facts():
    result = episode_tools.mainline_snapshot_tool_result(_snapshot())
    result = replace(result, evidence=tuple(replace(item, evidence_tier="user_material")
                                          for item in result.evidence))
    observation, _, facing = _project(result)
    assert all(item.evidence_tier == "user_material" for item in observation.evidence)
    assert "owned_results" not in facing
    assert facing["source_context"]["method_sources"][0]["role"] == "method_guidance"
    assert facing["source_context"]["qualifications"]["calendar_continuity"] == "unknown"
