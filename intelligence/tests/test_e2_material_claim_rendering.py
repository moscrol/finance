"""Claim-first material finishes keep one authored copy of each sentence."""
from dataclasses import replace
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.episode_protocol import build_episode_input, build_episode_instructions, validate_episode_finish
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_e2_material_grounding import FACT, finish, outcome, setup


def claim_finish(context):
    payload = finish(outcome(context))
    payload.update(draft="", render_from_claims=True)
    payload["bindings"][1]["claims"] = [{
        "text": "结论仅在用户材料前提内成立。", "kind": "premise_declaration",
    }]
    return payload


def test_writer_receives_parseable_claim_template_with_exact_frozen_basis():
    frame, context = setup()
    registry = ResearchToolRegistry(())
    prompt = json.loads(build_episode_input(frame, context, registry))
    template = json.loads(prompt["material_grounding"]["finish_format"]["wire_template"])
    assert template["draft"] == "" and template["render_from_claims"] is True
    assert {b["output_id"]: b["basis"] for b in template["bindings"]} == {
        spec.output_id: spec.grounding_mode for spec in context.contract.required_outputs if spec.required
    }
    claims = {b["output_id"]: b["claims"] for b in claim_finish(context)["bindings"]}
    for binding in template["bindings"]:
        binding["claims"] = claims[binding["output_id"]]
    assert validate_episode_finish(template, context=context, evidence=()).draft
    assert "wire_template" in build_episode_instructions(frame, context, registry)


def test_claim_first_finish_renders_exact_sentences_and_retains_sources():
    _, context = setup()
    payload = claim_finish(context)
    parsed = validate_episode_finish(payload, context=context, evidence=())
    assert parsed.draft == "## q1\n" + FACT + "\n\n## 证据边界\n结论仅在用户材料前提内成立。"
    assert parsed.bindings[0].claims == outcome(context).bindings[0].claims
    assert payload["draft"] == ""


@pytest.mark.parametrize("mutation", ["quote", "multisentence", "dual_draft", "duplicate", "unknown_output", "empty_binding", "gap_and_claims", "string_flag"])
def test_claim_first_does_not_bypass_validation(mutation):
    _, context = setup()
    payload = claim_finish(context)
    binding = payload["bindings"][0]
    if mutation == "quote":
        binding["claims"][0]["material_anchors"][0]["quote"] = "不存在的原文"
    elif mutation == "multisentence":
        binding["claims"][0]["text"] = "收入100万元；订单20万元。"
    elif mutation == "dual_draft":
        payload["draft"] = "另一份正文。"
    elif mutation == "duplicate":
        payload["bindings"].append(dict(binding))
    elif mutation == "unknown_output":
        binding["output_id"] = "invented"
    elif mutation == "empty_binding":
        binding["claims"] = []
    elif mutation == "gap_and_claims":
        binding["gap"] = "缺少收入，无法计算。"
    else:
        payload["render_from_claims"] = "true"
    with pytest.raises(ValueError):
        validate_episode_finish(payload, context=context, evidence=())


@pytest.mark.parametrize("scope", ["local_only", "full", None, "clarification"])
def test_claim_first_requires_settled_material_only_contract(scope):
    _, context = setup()
    material = context.contract.material_contract
    if scope is None:
        material = None
    elif scope == "clarification":
        material = replace(material, classification="boundary_uncertain", uncertain_reasons=("范围待确认",))
    else:
        material = replace(material, data_scope=scope)
    context = replace(context, contract=replace(context.contract, material_contract=material))
    with pytest.raises(ValueError):
        validate_episode_finish(claim_finish(context), context=context, evidence=())


def test_claim_first_gap_remains_public_and_partial():
    _, context = setup()
    payload = claim_finish(context)
    payload["status"] = "partial"
    binding = payload["bindings"][0]
    binding.update(claims=[], gap="缺少已确认收入金额，无法计算已确认收入占比。")
    parsed = validate_episode_finish(payload, context=context, evidence=())
    assert binding["gap"] in parsed.draft and parsed.status == "partial"
    assert parsed.bindings[0].gap and not parsed.bindings[0].claims


def test_real_episode_accepts_claim_first_without_tool_or_format_retry():
    frame, context = setup()
    calls = []

    class Writer:
        def complete(self, *, messages, tools, timeout):
            calls.append(messages)
            assert not tools
            return ModelTurn(json.dumps(claim_finish(context), ensure_ascii=False), (), "offline", "")

    result = ContinuousAgentEpisode(Writer()).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert result.status == "completed" and FACT in result.draft
    assert len(calls) == 1 and not result.evidence


@pytest.mark.parametrize("length,valid", [(200, True), (201, False)])
def test_claim_rendering_does_not_bypass_memo_limit(length, valid):
    from intelligence.tests.test_e2_material_delivery import setup_delivery, outcome_for, finish_for

    _, context = setup_delivery(memo=True)
    payload = finish_for(outcome_for(context, all_gap=True))
    payload.update(draft="", render_from_claims=True)
    payload["bindings"][1].update(gap="", claims=[{"text": "研" * length, "kind": "reasoning"}])
    payload["bindings"][2]["claims"] = [{"text": "仅依据用户材料。", "kind": "premise_declaration"}]
    if valid:
        assert validate_episode_finish(payload, context=context, evidence=()).status == "partial"
    else:
        with pytest.raises(ValueError):
            validate_episode_finish(payload, context=context, evidence=())


def test_claim_rendering_keeps_wrong_quote_as_terminal_integrity_rejection():
    _, context = setup()
    payload = claim_finish(context)
    payload["bindings"][0]["claims"][0]["material_anchors"][0]["quote"] = "不在材料内"
    with pytest.raises(ValueError) as error:
        validate_episode_finish(payload, context=context, evidence=())
    assert error.value.code == "material_source_violation" and error.value.kind.value == "integrity"
