"""D4 public scope at the grounded model boundary; no network or financial-quality claim."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from intelligence.services import answer_model, ask_blocks, ask_synthesis, episode_tools, llm_refine
from intelligence.services.ask_types import AskOptions, PreparedAnswer
from intelligence.tests import test_history_d4_joint_consumers as joint_consumers
from intelligence.tests.test_river_history_consumption import CUTOFF, QUESTION, _offline_ask

# Reuse the same sealed temporary producers and the strict no-network witness.
# Module aliases avoid importing a name that pytest fixture parameters shadow.
joint_db = joint_consumers.joint_db
offline = joint_consumers.offline


def _result_and_basis(db, tmp_path, monkeypatch, enabled=("D4",)):
    result = _offline_ask(db, tmp_path, monkeypatch, enabled=enabled)
    snapshot = ask_blocks.mainline_context_snapshot(QUESTION, None, db, as_of=CUTOFF.isoformat())
    return result, episode_tools.mainline_snapshot_tool_result(snapshot).query_basis


def _capture_grounded(result, monkeypatch):
    calls = []

    def capture(messages, **_kwargs):
        calls.append(deepcopy(messages))
        return None, "offline D4 scope boundary stop; no financial answer"

    monkeypatch.setattr(llm_refine, "synthesize_messages", capture)
    monkeypatch.setattr(llm_refine, "synthesize_messages_stream", capture)
    ask_synthesis.synthesize_prepared_answer(PreparedAnswer(
        options=AskOptions(query=QUESTION, compose=True, grounded_presenter=True,
                           daily_agent_grounded_presenter=True, shadow_grounded_composer=False),
        result=result,
    ))
    return calls


def _basis_rows(text):
    return [json.loads(line)["query_basis"] for line in text.splitlines()
            if line.startswith('{"query_basis":')]


def test_grounded_d4_first_request_keeps_complete_public_query_basis(joint_db, tmp_path, monkeypatch):
    result, basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    calls = _capture_grounded(result, monkeypatch)
    assert calls, "D4-only fixture fits the existing registry budget"
    prompt = "\n".join(message["content"] for message in calls[0])
    assert _basis_rows(prompt) == [{"D4": basis}], "grounded composer lost the typed D4 execution scope"
    assert {r["sector_ts_code"]: r["strict_double_red"] for r in basis["price_volume_signals"]} == {
        "S0": False, "S1": True, "S2": None,
    }
    assert "FUTURE_D4_SENTINEL" not in prompt
    assert all("strict_double_red" not in claim.text for claim in result.answer_spec.verified_facts)


def test_joint_admission_never_calls_with_missing_or_over_budget_scope(joint_db, tmp_path, monkeypatch):
    result, basis = _result_and_basis(joint_db, tmp_path, monkeypatch, enabled=("D4", "D10"))
    original = result.answer_spec.to_dict()
    calls = _capture_grounded(result, monkeypatch)
    full = answer_model.grounded_claim_registry_block(result.answer_spec)
    assert _basis_rows(full) == [{"D4": basis}]
    rows = [json.loads(line) for line in full.splitlines()]
    context = next(line for line in full.splitlines() if line.startswith('{"query_basis":'))
    history = next(row for row in rows if row.get("claim_id") == "data:D10:context")
    history_line = next(line for line in full.splitlines() if json.loads(line).get("claim_id") == history["claim_id"])
    support_lines = [line for line in full.splitlines() if json.loads(line).get("claim_id", "").startswith("data:D4:row:")]
    required_floor = len(context) + len(history_line) + min(map(len, support_lines)) + 2
    if required_floor > 12_000:
        assert calls == [], "over-budget complete context must be rejected before model invocation"
        assert result.grounded_composer_shadow.status == "ineligible_evidence"
        assert result.grounded_composer_shadow.failure_reason == "required_context_exceeds_registry_budget"
    else:
        assert calls
        registry = ask_synthesis._grounded_registry_for_synthesis(result.answer_spec, QUESTION)
        assert len(registry) <= 12_000
        assert _basis_rows(registry) == [{"D4": basis}]
        assert _basis_rows("\n".join(m["content"] for m in calls[0])) == [{"D4": basis}]
    assert result.answer_spec.to_dict() == original, "model-only scope must not rewrite the public fact ledger"


def test_fitting_joint_registry_keeps_scope_and_whole_inference(joint_db, tmp_path, monkeypatch):
    result, basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    block = '## 合成历史比较 [D10]\n{"population":"independent_candidates"}\n边界：推断，不可嫁接。'
    history = ask_synthesis._claims_from_data_block(block, "D10", "历史", "合成")[0]
    result.answer_spec = replace(result.answer_spec, candidate_facts=(*result.answer_spec.candidate_facts, history))
    registry = ask_synthesis._grounded_registry_for_synthesis(result.answer_spec, QUESTION)
    assert len(registry) <= 12_000
    assert _basis_rows(registry) == [{"D4": basis}]
    row = next(json.loads(line) for line in registry.splitlines() if json.loads(line).get("claim_id") == history.claim_id)
    assert row["text"] == history.text and row["claim_type"] == "inference"
    assert history not in result.answer_spec.verified_facts
    calls = _capture_grounded(result, monkeypatch)
    assert calls and registry in "\n".join(m["content"] for m in calls[0])


def test_grounded_repair_and_judge_receive_the_same_scope(joint_db, tmp_path, monkeypatch):
    result, basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    calls = []

    def capture(messages, **_kwargs):
        calls.append(deepcopy(messages))
        return None, "offline repair boundary stop"

    monkeypatch.setattr(llm_refine, "synthesize_messages", capture)
    missing = SimpleNamespace(missing_required=(SimpleNamespace(output_id="direct_assessment", gap="未覆盖"),))
    assert ask_synthesis.repair_unfulfilled_answer(
        question=QUESTION, answer_text="已有合成回答", answer_spec=result.answer_spec,
        verdict=missing, required_outputs=(), timeout=120,
    ) is None
    assert len(calls) == 1
    assert _basis_rows("\n".join(m["content"] for m in calls[0])) == [{"D4": basis}]
    registry = ask_synthesis._grounded_registry_for_synthesis(result.answer_spec, QUESTION)
    judge = llm_refine.build_grounding_judge_messages(QUESTION, "待审合成回答", registry)
    assert _basis_rows("\n".join(m["content"] for m in judge)) == [{"D4": basis}]


def test_source_scope_is_atomic_and_charged_to_the_same_budget(joint_db, tmp_path, monkeypatch):
    result, basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    spec = replace(result.answer_spec, summary=(), company_table=(), candidate_facts=(),
                   counter_evidence=(), gaps=(), triggers=(), verified_facts=result.answer_spec.verified_facts[:1])
    full = answer_model.grounded_claim_registry_block(spec)
    assert _basis_rows(full) == [{"D4": basis}]
    exact = answer_model.grounded_claim_registry_block(spec, max_chars=len(full), require_support=True)
    assert exact == full
    with pytest.raises(ValueError, match="budget"):
        answer_model.grounded_claim_registry_block(spec, max_chars=len(full)-1, require_support=True)
    assert answer_model.answer_spec_for_registry(spec, exact).verified_facts == spec.verified_facts


def test_metadata_does_not_reduce_the_disclosed_omitted_claim_count(joint_db, tmp_path, monkeypatch):
    result, basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    spec = replace(result.answer_spec, summary=(), company_table=(), candidate_facts=(),
                   counter_evidence=(), gaps=(), triggers=())
    full_lines = answer_model.grounded_claim_registry_block(spec).splitlines()
    scope = next(line for line in full_lines if "query_basis" in json.loads(line))
    fact_lines = [line for line in full_lines if "claim_id" in json.loads(line)]
    budget = len(scope) + min(map(len, fact_lines)) + 180
    registry = answer_model.grounded_claim_registry_block(spec, max_chars=budget, require_support=True)
    rows = [json.loads(line) for line in registry.splitlines()]
    delivered = [row for row in rows if "claim_id" in row]
    assert 0 < len(delivered) < len(fact_lines)
    assert _basis_rows(registry) == [{"D4": basis}]
    assert len(registry) <= budget
    assert f"另有 {len(fact_lines)-len(delivered)} 条 claim" in rows[-1]["note"]


def test_scope_alone_cannot_admit_available_facts(joint_db, tmp_path, monkeypatch):
    result, _basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    full = answer_model.grounded_claim_registry_block(result.answer_spec)
    scope = next(line for line in full.splitlines() if "query_basis" in json.loads(line))
    with pytest.raises(ValueError, match="budget"):
        answer_model.grounded_claim_registry_block(result.answer_spec, max_chars=len(scope))


@pytest.mark.parametrize("headroom", [0, 16])
def test_generic_registry_notice_preserves_last_fact_with_scope(
    joint_db, tmp_path, monkeypatch, headroom,
):
    """Replay's default registry must keep a fact, not just scope and a note."""
    result, basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    spec = replace(result.answer_spec, summary=(), company_table=(), candidate_facts=(),
                   counter_evidence=(), gaps=(), triggers=())
    original = spec.to_dict()
    full_lines = answer_model.grounded_claim_registry_block(spec).splitlines()
    scope = next(line for line in full_lines if "query_basis" in json.loads(line))
    facts = [line for line in full_lines if "claim_id" in json.loads(line)]
    assert len(facts) > 1
    budget = len(scope) + 1 + min(map(len, facts)) + headroom

    # Public defaults match the frozen-grounded replay consumer.
    registry = answer_model.grounded_claim_registry_block(spec, max_chars=budget)
    rows = [json.loads(line) for line in registry.splitlines()]
    delivered = [row for row in rows if "claim_id" in row]

    assert len(delivered) == 1, "omission metadata displaced the last delivered fact"
    assert _basis_rows(registry) == [{"D4": basis}]
    assert not any("note" in row for row in rows), "the exact fact window has no room for a note"
    assert len(registry) <= budget
    assert len(answer_model.answer_spec_for_registry(spec, registry).verified_facts) == 1
    assert spec.to_dict() == original


@pytest.mark.parametrize("missing", ["", "{}", '{"D1":{}}', "null"])
def test_typed_d4_without_source_scope_is_rejected_before_call(joint_db, tmp_path, monkeypatch, missing):
    result, _basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    result.answer_spec = replace(result.answer_spec, model_query_basis_json=missing)
    calls = _capture_grounded(result, monkeypatch)
    assert calls == []
    assert result.grounded_composer_shadow.status == "ineligible_evidence"
    assert result.grounded_composer_shadow.failure_reason == "source_query_basis_contract_invalid"


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "change_false", "change_null", "invent_source", "false_to_zero", "true_to_one", "null_to_false"])
def test_registry_projection_rejects_missing_or_modified_scope(joint_db, tmp_path, monkeypatch, mutation):
    result, _basis = _result_and_basis(joint_db, tmp_path, monkeypatch)
    registry = ask_synthesis._grounded_registry_for_synthesis(result.answer_spec, QUESTION)
    rows = [json.loads(line) for line in registry.splitlines()]
    metadata = next(row for row in rows if "query_basis" in row)
    if mutation == "drop":
        rows.remove(metadata)
    elif mutation == "duplicate":
        rows.append(deepcopy(metadata))
    elif mutation == "invent_source":
        metadata["query_basis"]["invented"] = {}
    else:
        signals = metadata["query_basis"]["D4"]["price_volume_signals"]
        target, value = {
            "change_false": ("S0", True), "change_null": ("S2", True),
            "false_to_zero": ("S0", 0), "true_to_one": ("S1", 1), "null_to_false": ("S2", False),
        }[mutation]
        next(row for row in signals if row["sector_ts_code"] == target)["strict_double_red"] = value
    changed = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with pytest.raises(ValueError, match="query basis"):
        answer_model.answer_spec_for_registry(result.answer_spec, changed)
