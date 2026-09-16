"""Freeze the M6 recovery shape without depending on a live model or database."""

from dataclasses import replace
import json

from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.historical_research.features import FEATURES, FEATURE_VERSION
from intelligence.services.historical_research.intent import HistoryIntent
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.tests.test_episode_finalizer import RecordingModel, _context, _frame


def _m6_evidence():
    """Public history values/card order from run_20260909_023642_220318.

    Non-history prose is replaced by neutral sentinels; tool counts and the
    decisive original ordinals E23..E30 stay fixed, including 19 daily rows.
    """
    result = []

    def add(tool, detail, query=""):
        if isinstance(detail, dict):
            detail = json.dumps(detail, ensure_ascii=False, separators=(",", ":"))
        result.append(AgentEvidence(
            tool=tool, title=f"frozen M6 observation {len(result) + 1}",
            detail=detail, source="frozen-public-observation",
            source_date="2024-09-30", independent_key=query,
            content_hash=f"m6-{len(result) + 1}",
        ))

    def header(operation, count, query):
        add("history_query", {"operation": operation, "total_matched": count, "returned_count": count, "research_only": True}, query)
        add("history_query", {"result_ref": f"original-run/history-query-{query}.json"}, query)
        add("history_query", {"pit_grade": "hindsight_reconstruction", "null": "未知或不可计算，非0"}, query)
        for feature in ("return_pct", "amount_ratio", "market_relative_return_pct"):
            add("history_query", {"feature": feature, "rule": FEATURES[feature]["rule"], "unit": FEATURES[feature]["unit"], "version": FEATURE_VERSION}, query)

    header("inspect_history", 0, "initial-empty-inspect")
    for tool, count in (("l3_lookup", 2), ("financial_data", 14)):
        for index in range(count):
            add(tool, f"other original observation {index}")
    header("compute_history", 1, "complete-compute")
    identity = {"sample": 0, "entity_code": "000713.SZ", "start": "2024-09-02", "end": "2024-09-30"}
    add("history_query", {**identity, "entity_name": "国投丰乐", "features": {"return_pct": 20.02259445939234, "amount_ratio": 4.720220515849577}, "status": {"return_pct": "complete", "amount_ratio": "complete"}}, "complete-compute")
    add("history_query", {**identity, "features": {"market_relative_return_pct": None}, "status": {"market_relative_return_pct": "missing"}}, "complete-compute")
    for tool, count in (("finance_query", 19), ("evidence_search", 12), ("web_search", 14), ("news_search", 6), ("web_search", 10), ("web_fetch", 10), ("web_search", 5)):
        for index in range(count):
            add(tool, f"other original observation {index}")
    assert len(result) == 106
    return tuple(result)


def test_frozen_m6_recovery_retains_real_compute_missing_metric_and_definitions():
    frame = replace(_frame(), raw_question="事后复盘国投丰乐2024年9月2日至9月30日走势", subject="国投丰乐", subject_kind="company", history_intent=HistoryIntent("retrospective_discovery"))
    context = replace(_context(frame), history_intent=frame.history_intent)
    evidence = _m6_evidence()
    priority = FinanceResearchHarness().recovery_evidence_priority(context=context, evidence=evidence)
    model = RecordingModel(ModelTurn("{}", (), "recording", ""))
    EpisodeFinalizer(model).recover(
        task_frame=frame, context=context, evidence=evidence,
        gaps=("feature:market_relative_return_pct:missing",),
        failure_reason="provider_error", evidence_priority=priority,
    )
    payload = json.loads(model.calls[0]["messages"][1]["content"])
    rows = payload["evidence"]
    assert len(rows) == 12
    assert {row["tool"] for row in rows} == {row.tool for row in evidence}
    by_id = {row["evidence_id"]: row for row in rows}
    values = json.loads(by_id["E29"]["detail"])
    missing = json.loads(by_id["E30"]["detail"])
    assert values["features"]["return_pct"] == 20.02259445939234
    assert values["features"]["amount_ratio"] == 4.720220515849577
    assert missing["features"]["market_relative_return_pct"] is None
    assert missing["status"]["market_relative_return_pct"] == "missing"
    for ordinal, feature in ((26, "return_pct"), (27, "amount_ratio"), (28, "market_relative_return_pct")):
        definition = json.loads(by_id[f"E{ordinal}"]["detail"])
        assert definition["feature"] == feature
        assert definition["rule"] == FEATURES[feature]["rule"]
    assert payload["gaps"] == ["feature:market_relative_return_pct:missing"]
    selection = payload["evidence_selection"]
    assert selection["available"] == 106 and selection["omitted"] == 94
    assert selection["by_tool"]["finance_query"]["available"] == 19
    assert "不等于数据缺失" in selection["instruction"]
    assert [row.content_hash for row in evidence] == [f"m6-{i}" for i in range(1, 107)]


def test_plain_finance_context_keeps_the_existing_empty_priority_contract():
    frame = _frame()
    assert FinanceResearchHarness().recovery_evidence_priority(context=_context(frame), evidence=_m6_evidence()) == ()


def test_episode_provider_failure_passes_harness_priority_to_real_finalizer():
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.research_tool_registry import ToolRunResult
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.tests.test_agent_episode import ScriptedModel, _context as episode_context, _market_registry, _tool_turn

    frame = replace(_frame(), history_intent=HistoryIntent("retrospective_discovery"))
    context = replace(episode_context(frame, max_steps=1), history_intent=frame.history_intent)

    def runner(_query, _tool_context):
        return ToolRunResult(evidence=_m6_evidence(), observation="frozen M6 observations", trace=ProviderTrace(provider="fixture", capability="market_data", status="success"))

    model = ScriptedModel([
        _tool_turn("frozen M6"),
        ModelTurn("", (), "scripted", "provider unavailable"),
        ModelTurn(json.dumps({"status": "partial", "draft": "恢复阶段只保留有限证据投影。", "gaps": ["无法恢复全部观察"], "bindings": [{"output_id": "direct_assessment", "evidence_hashes": [], "basis": "evidence", "gap": "无法恢复全部观察"}]}, ensure_ascii=False), (), "scripted", ""),
    ])
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=_market_registry(runner))
    assert any(event.kind == "finalization_recovery_started" for event in outcome.events)
    recovery = next(call for call in model.calls if call["tools"] == [] and len(call["messages"]) == 2)
    payload = json.loads(recovery["messages"][1]["content"])
    selected = {row["evidence_id"] for row in payload["evidence"]}
    assert {"E26", "E27", "E28", "E29", "E30"} <= selected
    assert len(payload["evidence"]) == 12
    assert len(outcome.evidence) == 106
