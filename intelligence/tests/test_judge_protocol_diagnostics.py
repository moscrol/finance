"""Protocol receipts explain rejection without changing acceptance or public output."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from intelligence.services import llm_refine
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, _judge_protocol_failure
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.material_grounding import ClaimSourceBinding
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.material_judge_helpers import material_judge_report
from intelligence.tests.test_episode_semantic_verifier import _structural
from intelligence.tests.test_e2_material_grounding import outcome, setup


@pytest.mark.parametrize("mutation,code", [
    ("wrong_tool", "tool_name"),
    ("two_calls", "tool_call_count"),
    ("extra_key", "report_keys"),
    ("missing_key", "report_keys"),
    ("passed_type", "passed_type"),
    ("index_type", "rejected_indexes_type"),
    ("index_bounds", "sentence_index_bounds"),
    ("issue_type", "issues_type"),
    ("inconsistent", "verdict_consistency"),
    ("bad_json", "invalid_json"),
    ("not_object", "report_type"),
])
def test_primary_rejection_keeps_private_response_without_retry_or_release(monkeypatch, mutation, code):
    frame, structural = _structural("市场当前偏弱。")
    payload = {"passed": True, "rejected_sentence_indexes": [], "issues": []}
    if mutation == "extra_key":
        payload["private-test-marker"] = "must not publish"
    elif mutation == "missing_key":
        payload.pop("issues")
    elif mutation == "passed_type":
        payload["passed"] = "true"
    elif mutation == "index_type":
        payload["rejected_sentence_indexes"] = [True]
    elif mutation == "index_bounds":
        payload["rejected_sentence_indexes"] = [999]
    elif mutation == "issue_type":
        payload["issues"] = "private-test-marker"
    elif mutation == "inconsistent":
        payload["passed"] = False
    tool = ModelToolCall("private-test-marker", "wrong" if mutation == "wrong_tool" else "submit_grounding_report", payload)
    turn = ModelTurn("private-test-marker", (tool, tool) if mutation == "two_calls" else (tool,), "offline")
    if mutation in {"bad_json", "not_object"}:
        turn = ModelTurn("private-test-marker" if mutation == "bad_json" else "[]", (), "offline")
    calls = []

    class Judge:
        def complete(self, **kwargs):
            calls.append(kwargs)
            return turn

    monkeypatch.setattr(llm_refine, "judge_provider_chain", lambda: ())
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=Judge()).verify(
        frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(30),
    )
    assert len(calls) == 1 and result.judge_status == "unavailable"
    assert result.status != "completed" and "市场当前偏弱" not in result.public_answer
    receipt = result.to_dict()["judge_protocol_failure"]
    assert receipt["reason_codes"] == [code]
    assert json.loads(receipt["response_json"]) == turn.to_dict()
    assert receipt["response_sha256"] == hashlib.sha256(receipt["response_json"].encode()).hexdigest()
    assert receipt["response_truncated"] is False
    assert "private-test-marker" not in result.public_answer
    assert "private-test-marker" not in str(result.issues)


def test_receipt_bounds_raw_response_and_hashes_full_serialization():
    turn = ModelTurn("x" * 70000, (), "offline")
    receipt = _judge_protocol_failure(turn, ["invalid_json"])
    raw = json.dumps(turn.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert receipt["response_json"] == raw[:65536]
    assert receipt["response_chars"] == len(raw)
    assert receipt["response_truncated"] is True
    assert receipt["response_sha256"] == hashlib.sha256(raw.encode()).hexdigest()


@pytest.mark.parametrize("stage", ["material_claim_checks", "material_output_checks"])
def test_material_receipt_identifies_failed_validation_without_accepting_it(stage):
    frame, context = setup()
    structural = verify_episode_outcome(context.contract, outcome(context))
    from intelligence.services.episode_semantic_verifier import _numbered_sentences

    request = SemanticEpisodeVerifier()._judge_request(frame, structural, _numbered_sentences(structural.outcome.draft))
    payload = material_judge_report(request)
    saved = deepcopy(payload)
    payload[stage].pop()
    reasons = []
    assert SemanticEpisodeVerifier._parse_report(
        payload, len(request["sentences"]), material_claims=request["material_claims"],
        material_outputs=request["material_outputs"], diagnostics=reasons,
    ) is None
    assert reasons == [stage]
    reasons.clear()
    assert SemanticEpisodeVerifier._parse_report(
        saved, len(request["sentences"]), material_claims=request["material_claims"],
        material_outputs=request["material_outputs"], diagnostics=reasons,
    ) is not None
    assert reasons == []


def test_nonfactual_tool_failure_survives_stage_wrapping(monkeypatch):
    frame, context = setup()
    value = outcome(context)
    value = replace(value, bindings=(value.bindings[0], replace(value.bindings[1], claims=(
        ClaimSourceBinding("结论仅在用户材料前提内成立。", "premise_declaration"),
    ))))
    structural = verify_episode_outcome(context.contract, value)
    calls = []

    class Judge:
        def complete(self, *, messages, **kwargs):
            request = json.loads(messages[-1]["content"])
            calls.append(request)
            payload = material_judge_report(request)
            if request.get("nonfactual_review"):
                payload["material_claim_checks"].pop()
            return ModelTurn("", (ModelToolCall("report", "submit_grounding_report", payload),), "offline")

    monkeypatch.setattr(llm_refine, "judge_provider_chain", lambda: ())
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=Judge()).verify(
        frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(60),
    )
    assert len(calls) == 2 and calls[-1]["nonfactual_review"] is True
    assert result.status != "completed" and result.judge_status == "unavailable"
    receipt = result.to_dict()["judge_protocol_failure"]
    assert receipt["reason_codes"] == ["material_claim_checks"]
    stages = result.to_dict()["material_review_calls"]
    assert stages[-1]["stage"] == "nonfactual_review" and stages[-1]["protocol_failure"] == receipt
    assert stages[0]["protocol_failure"] is None
