"""Replace the unconnected finance_harness prototype with regressions on real seams.

Synthetic inputs only. These prove contract enforcement, not natural-model
research quality, provider truth, or deployment. Positive controls distinguish
empty retrieval, partial evidence and genuine success from business failure.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date
import json
from pathlib import Path

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services import derived_calculation as dc
from intelligence.services import derived_calculation_artifacts as artifacts
from intelligence.services import judgment_maintenance as jm
from intelligence.services.agent_research import AgentEvidence, AgentToolContext, StructuredObservation
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.memory_gate import MemoryCandidate, MemoryGate, promotion_metadata
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.tests.test_episode_semantic_verifier import _structural
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff, RequiredOutput, ResearchDeadline, ResearchPolicy,
    ResearchRunContext, ResearchTaskContract,
)
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import (
    InvalidResearchToolArguments, ResearchToolRegistry, ToolObservation,
    ToolDiagnostic, ToolRunResult, ToolSpec, parse_derived_calculation_arguments,
)
from intelligence.services.task_frame import TaskFrame


def _evidence(identity="fixture"):
    return AgentEvidence(
        tool="market_data", title="合成市场快照", detail="上涨家数增加。",
        source="fixture", source_date="2026-07-01", content_hash=identity,
    )


def _result(status, *, evidence=()):
    return ToolRunResult(
        evidence=evidence, observation="合成工具返回",
        trace=ProviderTrace(provider="fixture", capability="market_data", status=status),
        gaps=("保留原始缺口",),
    )


def _observation(result):
    return ToolObservation(
        tool="market_data", query="synthetic", evidence=result.evidence,
        observation=result.observation, trace=result.trace, gaps=result.gaps,
        evidence_hashes=tuple(item.content_hash for item in result.evidence),
    )


@pytest.mark.parametrize("status", [
    "error", "timeout", "permission_denied", "bad_param", "request_error",
    "parse_error", "disabled", "not_attempted", "fallback_failed", "proxy_unavailable",
    "failed", "skipped", "unexpected_provider_status",
])
def test_failed_business_result_cannot_supply_evidence_or_look_successful(status):
    result = _result(status, evidence=(_evidence(),))
    projection = FinanceResearchHarness().project_tool_result(
        _observation(result), evidence_so_far=result.evidence, seen_prose=set(),
    )
    payload = json.loads(projection.model_content)
    assert result.evidence == ()
    assert payload["ok"] is False
    assert payload["error"] == (
        "unknown_provider_status" if status == "unexpected_provider_status" else status
    )
    assert payload["evidence"] == []
    assert "保留原始缺口" in payload["gaps"]
    assert projection.audit_payload["ok"] is False


@pytest.mark.parametrize("status", ["success", "ok", "partial", "empty", "stale", "fallback_success", "future_of_cutoff"])
def test_result_status_survives_model_budget_without_equating_empty_to_failure(status):
    result = _result(status, evidence=() if status == "empty" else (_evidence(),))
    projection = FinanceResearchHarness().project_tool_result(
        _observation(result), evidence_so_far=result.evidence, seen_prose=set(),
    )
    payload = json.loads(projection.model_content)
    assert payload["ok"] is True  # execution, not factual support or freshness
    assert payload["status"] == status
    assert "error" not in payload
    assert len(payload["evidence"]) == (0 if status == "empty" else 1)
    assert payload["gaps"] == ["保留原始缺口"]


def test_contradictory_empty_result_does_not_become_positive_evidence():
    result = _result("empty", evidence=(_evidence(),))
    assert result.evidence == ()
    assert len(result.gaps) > 1


def test_failed_payload_retains_trusted_diagnostic_without_leaking_provider_text():
    _, context = _frame_context()
    diagnostic = ToolDiagnostic("bad_param", "请改写字段后重试。")
    result = ToolRunResult(
        evidence=(_evidence(),), observation="untrusted-result-body",
        trace=ProviderTrace("fixture", "market_data", "private-provider-status", detail="private-detail"),
        gaps=("保留原始缺口",), diagnostics=(diagnostic,), telemetry={"private": "private-telemetry"},
    )
    registry = ResearchToolRegistry((ToolSpec(
        name="market_data", capability="market_data", description="fixture",
        cost="local", freshness="current", runner=lambda *_: result,
    ),))
    observation = registry.execute("market_data", "synthetic", context=context, step_id="failed")
    projected = FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=(), seen_prose=set(),
    )
    model = json.loads(projected.model_content)
    assert model["ok"] is False and model["status"] == "unknown_provider_status"
    assert model["evidence"] == [] and observation.evidence_hashes == ()
    assert diagnostic.render() in model["observation"]
    assert "保留原始缺口" in model["gaps"]
    assert all(marker not in projected.model_content for marker in (
        "private-provider-status", "untrusted-result-body", "private-detail", "private-telemetry",
    ))
    assert observation.trace.detail == "private-detail"
    assert projected.audit_payload["telemetry"] == {"private": "private-telemetry"}


@pytest.mark.parametrize("arity", [3, 4])
def test_legacy_runner_adapter_uses_the_same_evidence_admission_gate(arity):
    _, context = _frame_context()
    raw = ((_evidence(),), "不能采信的事实", ProviderTrace("fixture", "market_data", "timeout"))
    if arity == 4:
        raw = (*raw, ("保留原始缺口",))
    registry = ResearchToolRegistry((ToolSpec(
        name="market_data", capability="market_data", description="fixture",
        cost="local", freshness="current", runner=lambda *_: raw,
    ),))
    observation = registry.execute("market_data", "synthetic", context=context, step_id="legacy")
    assert observation.evidence == () and observation.evidence_hashes == ()
    assert observation.result_status_fields() == {"ok": False, "error": "timeout", "status": "timeout"}
    assert "不能采信的事实" not in observation.observation
    if arity == 4:
        assert "保留原始缺口" in observation.gaps


def test_registry_rejects_untyped_failure_payload_instead_of_treating_it_as_evidence():
    spec = ToolSpec(
        name="market_data", capability="market_data", description="fixture",
        cost="local", freshness="current", runner=lambda *_: {"ok": False, "error": "denied"},
    )
    with pytest.raises(TypeError, match="ToolRunResult"):
        spec.runner("fixture", AgentToolContext(ResearchDeadline.from_timeout(5)))


def _frame_context():
    frame = TaskFrame(
        raw_question="截至2026-07-01，市场结构有什么变化？", user_goal="判断市场结构",
        question_type="market_forecast", subject="A股市场", subject_kind="market_pattern",
        market_scope="A股", timeframe="2026-07-01", required_outputs=("direct_assessment",),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy="current_market_scenarios", confidence=0.95,
    )
    contract = ResearchTaskContract(
        task_id="slice-regression", question=frame.raw_question, subject=frame.subject,
        subject_kind=frame.subject_kind, question_type=frame.question_type,
        required_outputs=(RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),),
        allowed_capabilities=("market_data",), task_frame_hash=frame.task_frame_hash,
    )
    context = ResearchRunContext(
        contract=contract, deadline=ResearchDeadline.from_timeout(30),
        policy=ResearchPolicy("quick", 4, 30, 0), trace_parent_id=contract.task_id,
        information_cutoff=InformationCutoff(date(2026, 7, 1), "requested"),
    )
    return frame, context


@pytest.mark.parametrize("failure", ["timeout", "permission_denied", "unexpected_provider_status"])
def test_real_episode_retains_prior_evidence_but_cannot_cite_failed_result(failure):
    frame, context = _frame_context()
    seen = []
    finish = json.dumps({
        "status": "partial", "draft": "上涨家数增加，但增量证据尚未取得。",
        "gaps": ["增量证据缺失"],
        "bindings": [{"output_id": "direct_assessment", "evidence_hashes": ["E1"]}],
    }, ensure_ascii=False)
    turns = iter([
        ModelTurn("", (ModelToolCall("c1", "market_data", {"query": "baseline"}),), "scripted", ""),
        ModelTurn("", (ModelToolCall("c2", "market_data", {"query": "increment"}),), "scripted", ""),
        ModelTurn(finish, (), "scripted", ""),
    ])
    class Model:
        def complete(self, *, messages, tools, timeout):
            seen.extend(json.loads(m["content"]) for m in messages if m.get("role") == "tool")
            return next(turns)

    registry = ResearchToolRegistry((ToolSpec(
        name="market_data", capability="market_data", description="fixture",
        cost="local", freshness="current", io_effect="local_read",
        runner=lambda query, _: _result(
            "success" if query == "baseline" else failure,
            evidence=(_evidence("baseline" if query == "baseline" else "failed-evidence"),),
        ),
    ),))
    outcome = ContinuousAgentEpisode(Model()).run(task_frame=frame, context=context, registry=registry)
    assert outcome.stop_reason == "model_finish"
    assert [e.content_hash for e in outcome.evidence] == ["baseline"]
    assert outcome.bindings[0].evidence_hashes == ("baseline",)
    assert any(p["ok"] is False and p["evidence"] == [] for p in seen)
    results = [event.payload for event in outcome.events if event.kind == "tool_result"]
    assert [item["ok"] for item in results] == [True, False]
    assert "保留原始缺口" in results[1]["gaps"]
    assert outcome.gaps == ("增量证据缺失",)  # final gap is not every historical failed query


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("form", ["plain", "nested", "summary", "table", "chart", "params"])
def test_nonfinite_result_is_rejected_before_success_admission(value, form):
    results = {
        "plain": {"value": value},
        "nested": {"safe": 1, "inputs": [{"value": value}]},
        "summary": {"schema": artifacts.RESULT_SCHEMA_V1, "summary": {"value": value}},
        "table": {"schema": artifacts.RESULT_SCHEMA_V1, "tables": [
            {"name": "ratio", "columns": ["value"], "rows": [[value]]},
        ]},
        "chart": {"schema": artifacts.RESULT_SCHEMA_V1, "charts": [
            {"name": "ratio", "x": ["period"], "series": {"value": [value]}},
        ]},
        "params": {"schema": artifacts.RESULT_SCHEMA_V1, "summary": {"safe": 1}, "params": {"v": value}},
    }
    errors = artifacts.result_contract_errors(results[form])
    assert "result_not_finite_json" in errors
    specific = {"summary": "summary_non_scalar", "table": "table_non_scalar", "chart": "chart_series_invalid"}
    if form in specific:
        assert errors[0] == specific[form]  # new checks must not mask stable codes


@pytest.mark.parametrize("expression", ["float('nan')", "float('inf')", "-float('inf')"])
def test_actual_calculator_cannot_publish_nonfinite_legacy_result(expression):
    outcome = dc.run_derived_calculation(
        script=f"emit({{'value': {expression}}})", purpose="synthetic ratio",
        evidence=(_evidence(),),
    )
    assert isinstance(outcome, dc.CalculationError)
    assert outcome.code == dc.ERROR_INVALID_RESULT
    result = dc.to_tool_result(outcome)
    assert not result.evidence and result.trace.status == "error"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_calculation_parameter_rejected_at_tool_boundary(value):
    with pytest.raises(InvalidResearchToolArguments):
        parse_derived_calculation_arguments({
            "script": "emit({'value': 1})", "purpose": "fixture", "params": {"nested": [value]},
        })


@pytest.mark.parametrize("location", ["params", "evidence", "prior_inputs"])
def test_nonfinite_inputs_rejected_before_sandbox_even_if_script_ignores_them(monkeypatch, location):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("invalid inputs must be rejected before executing a script")
    monkeypatch.setattr(dc.calculation_sandbox, "run_script", forbidden)
    inputs = (_evidence(),)
    kwargs = {}
    if location == "params":
        kwargs["params"] = {"nested": [float("nan")]}
    elif location == "evidence":
        inputs = (replace(inputs[0], observations=(StructuredObservation("fixture", "2026-07-01", "v", float("inf")),)),)
    else:
        kwargs["prior_inputs"] = ({"hash": "prior", "observations": [{"value": -float("inf")}]},)
    outcome = dc.run_derived_calculation(
        script="emit({'value': 1})", purpose="synthetic", evidence=inputs, **kwargs,
    )
    assert isinstance(outcome, dc.CalculationError)
    assert outcome.code == dc.ERROR_INVALID_INPUT
    assert not dc.to_tool_result(outcome).evidence


@pytest.mark.parametrize("form", ["plain", "v1"])
def test_finite_json_and_explicit_missing_values_remain_usable(form):
    result = {"value": 0, "missing": None, "consistent": False}
    if form == "v1":
        result = {"schema": artifacts.RESULT_SCHEMA_V1, "summary": result, "params": {"nested": [0.5, None]}}
    assert artifacts.result_contract_errors(result) == ()
    args, _ = parse_derived_calculation_arguments({
        "script": "emit({'value': 0})", "purpose": "fixture", "params": {"nested": [0.5, None]},
    })
    assert json.loads(args)["params"] == {"nested": [0.5, None]}


@pytest.mark.parametrize("form", ["plain", "summary", "params"])
def test_nonjson_result_returns_stable_codes_without_private_repr(form):
    class PrivateValue:
        def __repr__(self):
            return "private-value-marker"
    value = PrivateValue()
    result = {"value": value}
    if form == "summary":
        result = {"schema": artifacts.RESULT_SCHEMA_V1, "summary": {"value": value}}
    elif form == "params":
        result = {"schema": artifacts.RESULT_SCHEMA_V1, "summary": {"value": 1}, "params": {"v": value}}
    errors = artifacts.result_contract_errors(result)
    assert "result_not_json" in errors
    assert "private-value-marker" not in str(errors)
    if form == "summary":
        assert errors[0] == "summary_non_scalar"


def test_equal_ratios_keep_different_input_provenance():
    calculations = [dc.run_derived_calculation(
        script="emit({'value': PARAMS['numerator'] / PARAMS['denominator']})",
        purpose="synthetic ratio", evidence=(_evidence(),),
        params={"numerator": n, "denominator": d},
    ) for n, d in [(1, 2), (100, 200)]]
    assert all(isinstance(item, dc.DerivedCalculation) for item in calculations)
    first, second = calculations
    assert first.result == second.result == {"value": 0.5}
    assert first.calc_id != second.calc_id
    assert first.params == {"numerator": 1, "denominator": 2}
    assert second.params == {"numerator": 100, "denominator": 200}
    assert first.input_evidence_hashes == second.input_evidence_hashes == ("fixture",)


def test_candidate_mutation_cannot_bypass_existing_memory_gate():
    candidate = MemoryCandidate("synthetic-candidate", "model_judgment", "未经复核的判断")
    with pytest.raises(FrozenInstanceError):
        candidate.kind = "user_preference"
    decision = MemoryGate().decide(candidate, checkpoints=(), verdicts=(), corrections=())
    assert not decision.eligible
    with pytest.raises(ValueError, match="not eligible"):
        promotion_metadata(decision, candidate.content)
    # Merely copying a candidate into a promotable kind grants no provenance.
    copied = replace(candidate, kind="user_preference")
    assert not MemoryGate().decide(copied, checkpoints=(), verdicts=(), corrections=()).eligible


@pytest.mark.parametrize("unsupported", ["乙公司营业收入同比增长10%。", "甲公司营业收入同比增长99%。"])
def test_existing_semantic_seam_receives_sources_and_rechecks_only_repaired_draft(unsupported):
    # A scripted judge is an oracle for wiring, not proof of natural judgment.
    supported = "甲公司营业收入同比增长10%。"
    frame, structural = _structural(supported + unsupported, detail=supported)
    assert structural.verified_status == "completed"  # identity is not entailment
    before = structural.outcome.to_dict()
    requests = []

    def judge(request):
        requests.append(request)
        if len(requests) == 1:
            return {
                "passed": False, "rejected_sentence_indexes": [2], "issues": ["第2句超出证据"],
                "reason_codes": [{"sentence_index": 2, "code": "fact_beyond_evidence"}],
            }
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(5),
    )
    assert len(requests) == 2
    assert supported in json.dumps(requests[0]["evidence_registry"], ensure_ascii=False)
    assert requests[1]["evidence_registry"] == requests[0]["evidence_registry"]
    assert all(unsupported not in row["text"] for row in requests[1]["sentences"])
    assert unsupported not in result.public_answer and supported in result.public_answer
    assert structural.outcome.to_dict() == before


def test_existing_semantic_seam_does_not_keyword_reject_a_negated_inference():
    draft = "毛利率回升并不意味着绝对定价权。"
    frame, structural = _structural(draft, detail="毛利率回升。")
    requests = []

    def judge(request):
        requests.append(request)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(5),
    )
    assert requests[0]["sentences"] == [{"index": 1, "text": draft}]
    assert draft in result.public_answer


@pytest.mark.parametrize("case", ["empty", "future", "changed"])
def test_existing_maintenance_does_not_call_missing_or_changed_evidence_support(case):
    fixture = Path(__file__).parent / "fixtures/research_evolution/01/complete/input.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    versions = payload["evidence_versions"]
    if case == "empty":
        versions = []
    elif case == "future":
        versions = [dict(v, recorded_at="2099-01-01T00:00:00+08:00") for v in versions]
    report = jm.assess(
        owner_user_id=payload["owner_user_id"], as_of=payload["as_of"],
        knowledge_cutoff=payload["knowledge_cutoff"], bindings=payload["bindings"],
        evidence_versions=versions, condition_observations=[], policy=payload["policy"],
        generated_at=payload["generated_at"],
    )
    live = [item for item in report.items if item.status != "superseded"]
    assert live
    if case in {"empty", "future"}:
        assert all(item.epistemic_state == "unknown" for item in live)
        assert report.gaps
    else:
        assert any(item.epistemic_state == "requires_review" for item in live)
    assert all(item.epistemic_state != "supported" for item in live)
