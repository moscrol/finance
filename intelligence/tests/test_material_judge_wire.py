"""Wire-only deduplication must preserve every canonical review field."""
from copy import deepcopy
import json

import pytest

from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _judge_system_prompt,
    compact_judge_payload,
    dumps_judge_request,
)
from intelligence.services.research_contract import ResearchDeadline


def _request():
    claims = [
        {"claim_id": "c1", "sentence_index": 2, "output_id": "answer_q1",
         "text": "Revenue is 100.", "kind": "material_fact",
         "material_anchors": [{"material_id": "m1", "quote": "Revenue is 100."}]},
        {"claim_id": "c2", "sentence_index": 3, "output_id": "answer_q1",
         "text": "Compare the inputs.", "kind": "reasoning", "material_anchors": []},
        {"claim_id": "c3", "sentence_index": 4, "output_id": "answer_q1",
         "text": "The previous answer said 80.", "kind": "historical_assistant_statement",
         "material_anchors": [], "old_answer_coordinate": "old-1",
         "historical_quote": "Revenue is 80.", "basis": "assistant_judgment"},
        {"claim_id": "c4", "sentence_index": 6, "output_id": "evidence_boundary",
         "text": "Only the supplied premises are used.", "kind": "premise_declaration",
         "material_anchors": []},
    ]
    return {
        "question": "Review revenue and the previous answer.",
        "material_grounding": {"data_scope": "material_only", "materials": [
            {"material_id": "m1", "text": "Revenue is 100.", "source_message_id": "current"}],
            "historical_assistant_statements": [{"source_message_id": "old-1", "text": "Revenue is 80."}]},
        "sentences": [{"index": row["sentence_index"], "text": row["text"]} for row in claims],
        "material_claims": claims,
        "material_outputs": [{"output_id": "answer_q1", "state": "fulfilled",
                              "candidate_sentences": [{"index": 2, "text": "Revenue is 100."}]}],
        "output_bindings": [{"output_id": output, "evidence_ids": [], "gap": "", "claims": [
            {key: value for key, value in row.items() if key not in {"claim_id", "sentence_index", "output_id"}}
            for row in claims if row["output_id"] == output
        ]} for output in ("answer_q1", "evidence_boundary")],
        "material_delivery": {"history_unavailable": False},
    }


def _expand(wire):
    """Undo the two wire-only projections: claim_ids references and anchor ordinal labels."""
    expanded = deepcopy(wire)
    for row in expanded.get("material_claims", []):
        for anchor in row.get("material_anchors", []):
            anchor.pop("anchor_index", None)
    by_id = {row["claim_id"]: row for row in expanded["material_claims"]}
    for binding in expanded["output_bindings"]:
        if "claim_ids" in binding and "claims" not in binding:
            binding["claims"] = [
                {key: value for key, value in by_id[claim_id].items()
                 if key not in {"claim_id", "sentence_index", "output_id"}}
                for claim_id in binding.pop("claim_ids")
            ]
    return expanded


def test_wire_references_round_trip_without_losing_review_inputs():
    request = _request()
    original = deepcopy(request)
    wire = json.loads(dumps_judge_request(request))
    assert wire["output_bindings"][0]["claim_ids"] == ["c1", "c2", "c3"]
    assert wire["output_bindings"][1]["claim_ids"] == ["c4"]
    assert _expand(wire) == compact_judge_payload(request)
    assert request == original
    assert dumps_judge_request(wire) == dumps_judge_request(request)
    assert "claim_ids" in _judge_system_prompt(request)


@pytest.mark.parametrize("mutation", ["quote", "text", "kind", "order", "missing", "collision", "duplicate_id", "missing_id", "other_scope"])
def test_nonidentical_or_ambiguous_bindings_are_never_replaced(mutation):
    request = _request()
    binding = request["output_bindings"][0]
    if mutation == "quote":
        binding["claims"][0]["material_anchors"] = [{"material_id": "m2", "quote": "Revenue is 90."}]
    elif mutation in {"text", "kind"}:
        binding["claims"][0][mutation] = "different"
    elif mutation == "order":
        binding["claims"].reverse()
    elif mutation == "missing":
        binding["claims"].pop()
    elif mutation == "collision":
        binding["claim_ids"] = ["already-present"]
    elif mutation == "duplicate_id":
        request["material_claims"][1]["claim_id"] = "c1"
    elif mutation == "missing_id":
        request["material_claims"][1].pop("claim_id")
    else:
        request["material_grounding"]["data_scope"] = "full"
    wire = json.loads(dumps_judge_request(request))
    assert wire["output_bindings"][0] == compact_judge_payload(binding)
    if mutation not in {"duplicate_id", "missing_id"}:
        assert _expand(wire) == compact_judge_payload(request)


def test_empty_claims_and_future_binding_fields_are_preserved():
    request = _request()
    request["output_bindings"].append({"output_id": "answer_q2", "claims": [], "gap": "Input unavailable."})
    request["output_bindings"][0]["future_field"] = {"count": 0, "flag": False}
    wire = json.loads(dumps_judge_request(request))
    assert wire["output_bindings"][-1] == request["output_bindings"][-1]
    assert wire["output_bindings"][0]["future_field"] == {"count": 0, "flag": False}
    assert _expand(wire) == compact_judge_payload(request)


@pytest.mark.parametrize("independent", [False, True])
def test_real_judge_dispatch_projects_wire_but_keeps_canonical_request(monkeypatch, independent):
    from intelligence.services import llm_refine
    from intelligence.services.agent_runtime import ModelTurn

    request = _request()
    original = deepcopy(request)
    calls = []

    def capture(messages, **kwargs):
        calls.append(deepcopy(messages))
        return "{}"

    class Model:
        def complete(self, **kwargs):
            return ModelTurn(capture(**kwargs), (), "offline", "")

    provider = llm_refine.LLMProvider("offline", "test-key", "https://example.invalid", "offline")
    monkeypatch.setattr(llm_refine, "judge_provider_chain", lambda: (provider,) if independent else ())
    monkeypatch.setattr(llm_refine, "complete", lambda messages, **kwargs: (capture(messages, **kwargs), provider, ""))
    reviewer = SemanticEpisodeVerifier(primary_judge=Model())
    reviewer._run_judge_once(request, ResearchDeadline.from_timeout(150))
    assert len(calls) == 1
    wire = json.loads(calls[0][1]["content"])
    assert "claims" not in wire["output_bindings"][0]
    assert _expand(wire) == compact_judge_payload(request)
    assert request == original


def test_wire_labels_each_claims_own_anchor_ordinals_without_relaxing_the_check():
    """L8 live 2026-09-26: 44/47 flash checks copied sentence_index into anchor_indexes."""
    from intelligence.services.material_claim_review import CLAIM_CHECK_RULE, reconcile_claim_checks

    request = _request()
    request["material_claims"][0]["material_anchors"].append({"material_id": "m1", "quote": "Revenue"})
    original = deepcopy(request)
    wire = json.loads(dumps_judge_request(request))
    anchors = {row["claim_id"]: row.get("material_anchors", []) for row in wire["material_claims"]}
    assert [anchor["anchor_index"] for anchor in anchors["c1"]] == [1, 2]
    assert all(not rows for claim, rows in anchors.items() if claim != "c1")
    assert request == original and "anchor_index" not in json.dumps(request)
    assert dumps_judge_request(wire) == dumps_judge_request(request)
    assert "anchor_index" in CLAIM_CHECK_RULE and "sentence_index" in CLAIM_CHECK_RULE

    def report(indexes):
        checks = [{"claim_id": "c1", "supported": True, "reason": "quote matches", "support_kind": "bound_material",
                   "anchor_indexes": indexes}]
        checks += [{"claim_id": row["claim_id"], "supported": True, "reason": "declared premise",
                    "support_kind": "nonfactual", "anchor_indexes": []} for row in request["material_claims"][1:2]]
        return {"passed": True, "rejected_sentence_indexes": [], "issues": [], "material_claim_checks": checks}

    claims = request["material_claims"][:2]
    assert reconcile_claim_checks(report([1]), claims) is not None
    # The label is guidance only: a sentence index outside the claim's own anchors stays refused.
    assert reconcile_claim_checks(report([claims[0]["sentence_index"] + 1]), claims) is None
