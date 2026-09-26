"""History provenance, comparison slots, and research-only binding contracts."""

from dataclasses import asdict, replace
import json

import pytest

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


@pytest.mark.parametrize("mutation", [
    "qualified", "decision", "operation", "missing", "row_hash", "dictionary",
    "operation_type", "locator", "query_key",
])
def test_history_verifier_qualification(mutation):
    result = _hashed_result(_payload([_row(0)]))
    card = next(item for item in result.evidence if item.history_provenance and item.history_provenance.row_index == 0)
    variants = {
        "qualified": card,
        "decision": replace(card, history_provenance=replace(card.history_provenance, decision_eligible=True)),
        "operation": replace(card, history_provenance=replace(card.history_provenance, operation="inspect_history")),
        "missing": replace(card, history_provenance=None),
        "row_hash": replace(card, history_provenance=replace(card.history_provenance, row_hash="f" * 16)),
        "dictionary": replace(card, history_provenance={"operation": "find_analogues"}),
        "operation_type": replace(card, history_provenance=replace(card.history_provenance, operation=["find_analogues"])),
        "locator": replace(card, internal_locator="other/" + REF.split("/", 1)[1]),
        "query_key": replace(card, independent_key="another-query"),
    }
    candidate = variants[mutation]
    if mutation in {"decision", "operation"}:
        # These failures must come from qualification, not a stale digest.
        candidate = replace(candidate, content_hash=evidence_content_hash(candidate))
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

    verified = verify_episode_outcome(contract, outcome(candidate))
    rejected = any(item.code == IssueCode.HISTORY_OPERATION_UNSUPPORTED for item in verified.issue_items)
    assert rejected is (mutation != "qualified")
    assert verified.completion.outputs[0].status == ("fulfilled" if mutation == "qualified" else "missing")


def test_split_card_only_carries_its_own_visible_observations():
    row = _row(0)
    row["features"].update({f"feature_{i}": 1000 + i for i in range(20)})
    result = _hashed_result(_payload([row]))
    cards = [card for card in result.evidence if card.history_provenance.row_index == 0]
    assert len(cards) > 1
    recovered = {}
    for card in cards:
        detail = json.loads(card.detail)
        visible = detail.get("features", {})
        assert {obs.metric: obs.value for obs in card.observations} == visible
        recovered.update(visible)
    assert recovered == row["features"]


def test_persisted_key_order_does_not_change_chunk_boundaries():
    row = _row(0)
    row["features"].update({f"feature_{i}": 1000 + i for i in range(20)})
    original = _payload([row])
    original["feature_definitions"] = {
        name: {"rule": name, "unit": "percent", "version": "v1"}
        for name in ("z-last", "a-first")
    }
    original["comparison"] = {f"metric_{i}": "x" * 30 for i in range(20)}
    original["universe"] = {"window_days": 2, "entity_codes": ["A.0"], "start": "2025-08-01"}
    stored = json.loads(json.dumps(original, sort_keys=True))
    before = _hashed_result(original)
    after = _hashed_result(stored)
    assert [card.content_hash for card in before.evidence] == [card.content_hash for card in after.evidence]
    assert [card.observations for card in before.evidence] == [card.observations for card in after.evidence]


def test_history_source_survives_strict_json_reconstruction():
    from intelligence.services.prior_evidence import _original_atom

    card = _hashed_result(_payload([_row(0)])).evidence[-1]
    raw = json.loads(json.dumps(asdict(card)))
    assert _original_atom(raw) == card
    assert _original_atom(raw).history_provenance == card.history_provenance
    # Reference and metadata cards have no integer row coordinate; they must
    # survive the same strict path rather than silently losing provenance.
    payload = _payload([_row(0)])
    payload["reference"] = _row(99)
    for item in _hashed_result(payload).evidence:
        assert _original_atom(json.loads(json.dumps(asdict(item)))) == item


@pytest.mark.parametrize("changes", [
    {"row_index": True}, {"row_index": -1}, {"row_hash": "forged"},
    {"result_ref": "../history-query-" + "a" * 64 + ".json"},
    {"result_ref": "run/history-query-invalid.json"},
    {"purpose": ""}, {"research_only": "true"}, {"decision_eligible": 0},
])
def test_history_metadata_shape_is_strict_even_with_updated_hash(changes):
    from intelligence.services.prior_evidence import _original_atom

    card = _hashed_result(_payload([_row(0)])).evidence[-1]
    changed = replace(card, history_provenance=replace(card.history_provenance, **changes))
    changed = replace(changed, content_hash=evidence_content_hash(changed))
    raw = json.loads(json.dumps(asdict(changed)))
    with pytest.raises(ValueError, match="invalid historical"):
        _original_atom(raw)


@pytest.mark.parametrize("mutation", [
    "absent", "null", "extra", "missing_key", "row_hash", "locator", "query_key", "tool",
])
def test_history_reconstruction_does_not_drop_or_rebind_identity(mutation):
    from intelligence.services.prior_evidence import _original_atom

    card = _hashed_result(_payload([_row(0)])).evidence[-1]
    raw = json.loads(json.dumps(asdict(card)))
    if mutation == "absent":
        raw.pop("history_provenance")
    elif mutation == "null":
        raw["history_provenance"] = None
    elif mutation == "extra":
        raw["history_provenance"]["unknown"] = True
    elif mutation == "missing_key":
        raw["history_provenance"].pop("promotion_eligible")
    elif mutation == "row_hash":
        raw["history_provenance"]["row_hash"] = "f" * 16
    elif mutation == "locator":
        raw["internal_locator"] = "other/" + REF.split("/", 1)[1]
    elif mutation == "query_key":
        raw["independent_key"] = "another-query"
    else:
        raw["tool"] = ["history_query"]
    with pytest.raises(ValueError):
        _original_atom(raw)


def test_same_source_row_keeps_hash_across_query_and_reader_tools(tmp_path):
    from intelligence.tests.test_historical_research_episode import _registry

    registry, context, session = _registry(tmp_path)
    query = registry.execute("history_query", {
        "operation": "compute_history", "start": "2026-08-03", "end": "2026-08-04",
        "entity_codes": ["A.FP"], "features": ["return_pct", "amount_ratio"],
    }, context=context, step_id="query")
    ref = query.telemetry["result_ref"]
    original = session.read(ref)
    read = registry.execute("read_history_result", {"result_ref": ref, "offset": 0, "limit": 1},
                            context=context, step_id="read")
    def row_cards(result):
        return [item for item in result.evidence if item.history_provenance.row_index == 0]
    assert row_cards(query)
    assert [item.content_hash for item in row_cards(query)] == [item.content_hash for item in row_cards(read)]
    assert [item.history_provenance for item in row_cards(query)] == [item.history_provenance for item in row_cards(read)]
    assert session.read(ref) == original
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.services.prior_evidence import _original_atom

    ledger = EvidenceLedger()
    assert len(ledger.append(row_cards(query))) == len(row_cards(query))
    assert ledger.append(row_cards(read)) == ()
    for item in row_cards(read):
        assert _original_atom(json.loads(json.dumps(asdict(item)))) == item


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
    # 相似点仍只能由真做过的类比检索支撑。差异与适用边界则可以立在同窗排名
    # 与启动到峰值路径上：原先的四算子白名单使 rank_history/trace_history 无处可引，
    # 模型即使做对也会在终局被 BLOCK（见 tests/test_history_operation_eligibility.py）。
    assert set(outputs["analog_similarities"].allowed_history_operations) == {"find_analogues"}
    assert set(outputs["key_differences"].allowed_history_operations) == {
        "find_analogues",
        "compare_cases",
        "rank_history",
        "trace_history",
    }
    assert set(outputs["limits_of_analogy"].allowed_history_operations) == {
        "find_analogues",
        "compare_cases",
        "rank_history",
        "trace_history",
    }
    assert outputs["comparison_assumptions"].grounding_mode == "model_reasoning"
    assert outputs["comparison_assumptions"].evidence_types == ()


def test_chunked_row_has_distinct_public_citations_and_stable_overlapping_page():
    from intelligence.runtime.continuous_turn_adapter import _public_citation_projection

    row = _row(1)
    row["features"].update({f"feature_{index}": index for index in range(20)})
    first = _hashed_result(_payload([_row(0), row]))
    page = _hashed_result(_payload([row], offset=1), offset=1)
    cards = tuple(
        card for card in first.evidence if card.history_provenance.row_index == 1
    )
    page_cards = tuple(
        card for card in page.evidence if card.history_provenance.row_index == 1
    )
    assert len(cards) > 1
    assert [card.content_hash for card in cards] == [card.content_hash for card in page_cards]
    outcome = AgentOutcome(
        task_frame_hash="history-chunks", status="completed", draft="历史观察",
        evidence=cards, traces=(), gaps=(), stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "history-chunks"}),),
        bindings=(OutputEvidenceBinding("direct_assessment", tuple(card.content_hash for card in cards)),),
        usage=AgentUsage(),
    )
    citations = _public_citation_projection(
        outcome, frozenset(), allowed_output_ids=frozenset({"direct_assessment"})
    )
    assert len(citations) == len(cards)
