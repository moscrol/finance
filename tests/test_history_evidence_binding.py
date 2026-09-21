"""History provenance, comparison slots, and research-only binding contracts."""

from dataclasses import replace

from intelligence.services.agent_research import evidence_content_hash
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
    public_agent_evidence,
)
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_issues import IssueCode
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.episode_semantic_verifier import (
    _bound_evidence_quantities,
    _project_semantic_evidence,
)
from intelligence.services.historical_research.episode import _result
from intelligence.services.historical_research.intent import HistoryIntent
from intelligence.services.research_contract import (
    InformationCutoff,
    RequiredOutput,
    ResearchTaskContract,
)
from intelligence.services.task_frame import TaskFrame


REF = "run-history-review/history-query-" + "a" * 64 + ".json"


def _history_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="以前有没有类似？请比较相似点、差异和不能类比的地方",
        user_goal="比较历史类比",
        question_type="comparison_analog",
        subject="AI行情",
        subject_kind="theme",
        market_scope="A股",
        timeframe="2026-08-01至2026-09-01",
        required_outputs=(
            "direct_assessment",
            "counterpoint",
            "evidence_boundary",
        ),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="comparable_multi_source_evidence",
        confidence=0.9,
        history_intent=HistoryIntent(
            purpose="historical_comparison",
            requested_start=None,
            requested_end=None,
            scope="historical_research",
            strict_window=False,
        ),
    )


def _payload(rows, *, offset=0):
    return {
        "query_id": "history-query-stable",
        "operation": "find_analogues",
        "purpose": "historical_comparison",
        "status": "research_only",
        "research_only": True,
        "decision_eligible": False,
        "promotion_eligible": False,
        "total_matched": 225,
        "returned_count": 25,
        "truncated": offset + len(rows) < 225,
        "offset": offset,
        "preview": rows,
        "rows": list(rows),
    }


def _row(index: int):
    return {
        "entity_code": f"A.{index}",
        "entity_name": f"候选{index}",
        "start": "2025-08-01",
        "end": "2025-08-28",
        "features": {"return_pct": 12.6 + index},
        "feature_coverage": {"return_pct": {"status": "complete"}},
    }


def _hashed_result(payload, *, offset=0):
    result = _result(payload, result_ref=REF, offset=offset)
    evidence = tuple(
        replace(item, content_hash=evidence_content_hash(item))
        for item in result.evidence
    )
    return replace(result, evidence=evidence)


def test_history_evidence_carries_structured_identity_and_stable_row_hash():
    first = _hashed_result(_payload([_row(0), _row(1)]))
    repeated = _hashed_result(_payload([_row(0), _row(1)]))
    page = _hashed_result(_payload([_row(1)], offset=1), offset=1)

    first_rows = {
        item.history_provenance.row_index: item
        for item in first.evidence
        if item.history_provenance is not None
        and isinstance(item.history_provenance.row_index, int)
    }
    repeated_rows = {
        item.history_provenance.row_index: item
        for item in repeated.evidence
        if item.history_provenance is not None
        and isinstance(item.history_provenance.row_index, int)
    }
    page_row = next(
        item for item in page.evidence
        if item.history_provenance is not None
        and item.history_provenance.row_index == 1
    )

    assert set(first_rows) == {0, 1}
    assert first_rows[0].history_provenance.query_id == "history-query-stable"
    assert first_rows[0].history_provenance.operation == "find_analogues"
    assert first_rows[0].history_provenance.purpose == "historical_comparison"
    assert first_rows[0].history_provenance.result_ref == REF
    assert first_rows[0].history_provenance.research_only is True
    assert first_rows[0].history_provenance.decision_eligible is False
    assert first_rows[0].history_provenance.row_hash
    assert first_rows[0].history_provenance.row_identity
    assert first_rows[0].history_provenance.row_hash == repeated_rows[0].history_provenance.row_hash
    assert first_rows[1].history_provenance.row_identity == page_row.history_provenance.row_identity
    assert first_rows[1].content_hash == page_row.content_hash


def test_history_observations_reach_judge_only_after_slot_binding():
    result = _hashed_result(_payload([_row(0)]))
    scope = next(
        item for item in result.evidence
        if item.history_provenance is not None
        and item.history_provenance.row_index is None
        and any(obs.metric == "total_matched" for obs in item.observations)
    )
    assert any(obs.value == 225 for obs in scope.observations)
    assert any(obs.value == 25 for obs in scope.observations)

    unbound = AgentOutcome(
        task_frame_hash="history-binding",
        status="completed",
        draft="召回225个，预览25个。",
        evidence=result.evidence,
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "history-binding"}),),
        bindings=(),
        usage=AgentUsage(),
    )
    # Quantity preservation intentionally stays broader than the judge registry:
    # the deterministic lost-observation guard may see a real value before the
    # model has declared a slot binding, but semantic judging must not.
    assert {"225", "25"}.issubset(_bound_evidence_quantities(unbound))
    _bindings, unbound_registry, _telemetry = _project_semantic_evidence(unbound)
    assert unbound_registry == []

    bound = replace(
        unbound,
        bindings=(
            OutputEvidenceBinding(
                "analog_similarities", (scope.content_hash,)
            ),
        ),
    )
    assert {"225", "25"}.issubset(_bound_evidence_quantities(bound))
    _bindings, registry, _telemetry = _project_semantic_evidence(bound)
    projected = next(row for row in registry if row["evidence_id"] == "E1")
    assert projected["research_only"] is True
    assert projected["decision_eligible"] is False
    assert projected["history_provenance"]["result_ref"] == REF
    assert any(obs["metric"] == "total_matched" for obs in projected["observations"])
    assert "observations" not in public_agent_evidence(scope)
    assert "history_provenance" not in public_agent_evidence(scope)
    assert bound.to_dict()["evidence"][0]["observations"]
    assert bound.to_dict()["evidence"][0]["history_provenance"]["result_ref"] == REF


def test_history_verifier_rejects_forced_decision_qualification_and_wrong_operation():
    result = _hashed_result(_payload([_row(0)]))
    card = next(item for item in result.evidence if item.history_provenance and item.history_provenance.row_index == 0)
    forced = replace(
        card,
        history_provenance=replace(card.history_provenance, decision_eligible=True),
    )
    wrong = replace(
        card,
        history_provenance=replace(card.history_provenance, operation="inspect_history"),
    )
    contract = ResearchTaskContract(
        task_id="history-negative",
        question="历史类比",
        subject="AI行情",
        subject_kind="theme",
        question_type="comparison_analog",
        required_outputs=(
            RequiredOutput(
                "analog_similarities",
                "相似点",
                ("history_query",),
                allowed_history_operations=("find_analogues",),
            ),
        ),
        allowed_capabilities=("finance_query",),
        task_frame_hash="history-negative",
    )

    def outcome(evidence):
        return AgentOutcome(
            task_frame_hash="history-negative",
            status="completed",
            draft="相似点",
            evidence=(evidence,),
            traces=(),
            gaps=(),
            stop_reason="model_finish",
            events=(EpisodeEvent(1, "task", {"task_frame_hash": "history-negative"}),),
            bindings=(OutputEvidenceBinding("analog_similarities", (evidence.content_hash,)),),
            usage=AgentUsage(),
        )

    for candidate in (forced, wrong):
        verified = verify_episode_outcome(contract, outcome(candidate))
        assert any(item.code == IssueCode.HISTORY_OPERATION_UNSUPPORTED for item in verified.issue_items)
        assert verified.completion.outputs[0].status == "missing"


def test_comparison_contract_maps_slots_to_history_operations_and_keeps_hypotheses_reasoning():
    context = build_episode_context(
        _history_frame(),
        task_id="history-comparison-contract",
        capabilities=("finance_query", "evidence_lookup", "web_search"),
        information_cutoff=InformationCutoff.runtime_default(),
    )
    outputs = {item.output_id: item for item in context.contract.required_outputs}

    assert {
        "comparison_dimensions",
        "comparison_assumptions",
        "analog_similarities",
        "key_differences",
        "limits_of_analogy",
        "counterpoint",
        "evidence_boundary",
    }.issubset(outputs)
    assert set(outputs["analog_similarities"].allowed_history_operations) == {"find_analogues"}
    assert set(outputs["key_differences"].allowed_history_operations) == {
        "find_analogues",
        "compare_cases",
    }
    assert set(outputs["limits_of_analogy"].allowed_history_operations) == {
        "find_analogues",
        "compare_cases",
    }
    assert outputs["comparison_assumptions"].grounding_mode == "model_reasoning"
    assert outputs["comparison_assumptions"].evidence_types == ()
