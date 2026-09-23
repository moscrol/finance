"""Claim-first material finishes keep one authored copy of each sentence."""
from dataclasses import replace
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.episode_protocol import build_episode_input, build_episode_instructions, validate_episode_finish
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.material_grounding import claim_sentences
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
    format_rule = prompt["material_grounding"]["finish_format"]["rule"]
    assert "所有claims.text合计" in format_rule and "1000" in format_rule
    assert "不能省略子问、计算步骤或本句输入锚点" in format_rule
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


@pytest.mark.parametrize("marker", ["**", "*", "__", "_", "***", "~~", "`"])
def test_markdown_closers_stay_with_exact_claim_and_judge_sentence(marker):
    from intelligence.services.episode_semantic_verifier import _numbered_sentences

    _, context = setup()
    payload = claim_finish(context)
    text = marker + FACT + marker
    payload["bindings"][0]["claims"][0]["text"] = text
    parsed = validate_episode_finish(payload, context=context, evidence=())
    assert claim_sentences(text) == (text,)
    assert text in parsed.draft
    assert _numbered_sentences(parsed.draft)[1]["text"] == text


def test_markdown_does_not_merge_separate_sentences_or_steal_next_opener():
    assert claim_sentences("甲收入100万元。**订单20万元。**") == ("甲收入100万元。", "**订单20万元。**")
    assert claim_sentences("**收入100万元；订单20万元。**") == ("**收入100万元；", "订单20万元。**")
    _, context = setup()
    payload = claim_finish(context)
    payload["bindings"][0]["claims"][0]["text"] = "**收入100万元；订单20万元。**"
    with pytest.raises(ValueError, match="one sentence"):
        validate_episode_finish(payload, context=context, evidence=())


@pytest.mark.parametrize("location", ["claim", "top_gap", "binding_gap"])
def test_private_material_coordinates_are_recoverable_format_errors(location):
    _, context = setup()
    payload = claim_finish(context)
    source_id = context.contract.material_grounding.materials[0].material_id
    if location == "claim":
        payload["bindings"][1]["claims"][0]["text"] = f"仅依据材料（{source_id}）。"
    elif location == "top_gap":
        payload["gaps"] = [f"材料{source_id}缺少期间。"]
    else:
        payload["status"] = "partial"
        payload["bindings"][0].update(claims=[], gap=f"材料{source_id}缺少已确认金额。")
    with pytest.raises(ValueError) as error:
        validate_episode_finish(payload, context=context, evidence=())
    assert error.value.code == "private_material_reference" and error.value.kind.value == "format"


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


def test_multisentence_error_locates_claim_without_rewriting_payload():
    _, context = setup()
    payload = claim_finish(context)
    text = "计算采用订单除收入；材料未说明日期。"
    payload["bindings"][1]["claims"][0]["text"] = text
    with pytest.raises(ValueError) as error:
        validate_episode_finish(payload, context=context, evidence=())
    assert error.value.code == "bad_claim_binding"
    assert "evidence_boundary.claims[0]" in str(error.value)
    assert "2 sentences" in str(error.value)
    assert payload["bindings"][1]["claims"][0]["text"] == text


def test_multisentence_feedback_batches_locations_and_private_references_without_mutation():
    from copy import deepcopy

    _, context = setup()
    payload = claim_finish(context)
    source_id = context.contract.material_grounding.materials[0].material_id
    payload["bindings"][0]["claims"][0]["text"] = "收入100万元；订单20万元。"
    payload["bindings"][1]["claims"][0]["text"] = f"仅依据{source_id}。不引入外部事实。"
    saved = deepcopy(payload)
    with pytest.raises(ValueError) as error:
        validate_episode_finish(payload, context=context, evidence=())
    message = str(error.value)
    assert error.value.code == "bad_claim_binding"
    assert "answer_q1.claims[0] has 2 sentences" in message
    assert "evidence_boundary.claims[0] has 2 sentences" in message
    assert "private material references in evidence_boundary.claims[0]" in message
    assert source_id not in message and payload == saved


def test_multisentence_feedback_is_bounded_and_reports_remaining_errors():
    from copy import deepcopy

    _, context = setup()
    payload = claim_finish(context)
    claim = deepcopy(payload["bindings"][0]["claims"][0])
    claim["text"] = "收入100万元；订单20万元。"
    payload["bindings"][0]["claims"] = [deepcopy(claim) for _ in range(20)]
    with pytest.raises(ValueError) as error:
        validate_episode_finish(payload, context=context, evidence=())
    message = str(error.value)
    assert "claims[15]" in message and "claims[16]" not in message
    assert "4 further invalid claims" in message


@pytest.mark.parametrize("reference_loop", [False, True])
def test_one_format_retry_receives_all_claim_locations_and_preserves_bindings(reference_loop):
    from copy import deepcopy
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop

    frame, context = setup()
    good = claim_finish(context)
    bad = deepcopy(good)
    bad["bindings"][0]["claims"][0]["text"] = "收入100万元；订单20万元。"
    bad["bindings"][1]["claims"][0]["text"] = "仅依据用户材料。结论限于材料。"
    calls = []

    class Writer:
        def complete(self, *, messages, tools, timeout):
            calls.append(deepcopy(messages))
            if len(calls) == 2:
                feedback = str(messages)
                assert "answer_q1.claims[0]" in feedback and "evidence_boundary.claims[0]" in feedback
            return ModelTurn(json.dumps(bad if len(calls) == 1 else good, ensure_ascii=False), (), "offline")

    loop = HarnessReferenceLoop(Writer()) if reference_loop else ContinuousAgentEpisode(Writer())
    result = loop.run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert len(calls) == 2 and result.status == "completed" and result.usage.tool_calls == 0
    assert result.bindings[0].claims == outcome(context).bindings[0].claims


@pytest.mark.parametrize("reference_loop", [False, True])
def test_last_format_error_reaches_repair_writer_without_extra_attempt(reference_loop):
    from copy import deepcopy
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
    from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal

    frame, context = setup()
    good = claim_finish(context)
    bad = deepcopy(good)
    bad["bindings"][1]["claims"][0]["text"] = "计算采用订单除收入；材料未说明日期。"
    calls = []

    class Writer:
        def complete(self, *, messages, tools, timeout):
            calls.append(deepcopy(messages))
            text = "not JSON" if len(calls) == 1 else json.dumps(bad if len(calls) == 2 else good, ensure_ascii=False)
            return ModelTurn(text, (), "offline", "")

    loop = HarnessReferenceLoop(Writer()) if reference_loop else ContinuousAgentEpisode(Writer())
    states = []
    first = loop.run(task_frame=frame, context=context, registry=ResearchToolRegistry(()), _continuation_sink=states)
    assert len(calls) == 2 and first.status == "partial"
    goal = RepairGoal(context.contract.task_id, "repair-format-context", 1, ("answer_q1", "evidence_boundary"),
                      (), (), (), CoverageDelta(0, 0, 0), 0, 20)
    result = loop.resume(states[0], first, goal)
    assert len(calls) == 3 and result.status == "completed"
    feedback = [message["content"] for message in calls[2] if message["role"] == "user" and "one sentence" in message["content"]]
    assert len(feedback) == 1
    assert "evidence_boundary.claims[0]" in feedback[0]
    # 第二次失败在本集只落账、不再多花一次模型调用；它到修复轮才交给作者。
    injected = [event for event in first.events
                if event.kind == "model_input" and event.payload.get("source") == "steering_invalid_finish"]
    assert len(injected) == 1 and "one sentence" not in injected[0].payload["content"]
    assert any(event.kind == "invalid_action" and "evidence_boundary.claims[0]" in event.payload["reason"]
               for event in first.events)
    carried = [event for event in result.events
               if event.kind == "model_input" and event.payload.get("source") == "repair_last_rejection"]
    assert len(carried) == 1 and carried[0].payload["content"] == feedback[0]
    assert result.usage.tool_calls == 0


@pytest.mark.parametrize("reference_loop", [False, True])
def test_second_repair_cycle_does_not_resend_the_rejection_it_already_delivered(reference_loop):
    """尾次拒收只补发一次：第一轮修复已用 repair_last_rejection 送达，第二轮不得再发。

    research_tier=max 允许三轮修复，adapter 带累积账本再进 resume()；此前扫描器只认
    steering_invalid_finish 为送达，第二轮会把作者早已改对的那条格式错误再发一遍。
    """
    from copy import deepcopy
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
    from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal

    frame, context = setup()
    good = claim_finish(context)
    bad = deepcopy(good)
    bad["bindings"][1]["claims"][0]["text"] = "计算采用订单除收入；材料未说明日期。"
    calls = []

    class Writer:
        def complete(self, *, messages, tools, timeout):
            calls.append(deepcopy(messages))
            text = "not JSON" if len(calls) == 1 else json.dumps(bad if len(calls) == 2 else good, ensure_ascii=False)
            return ModelTurn(text, (), "offline", "")

    def goal(cycle):
        return RepairGoal(context.contract.task_id, f"repair-format-cycle-{cycle}", cycle,
                          ("answer_q1", "evidence_boundary"), (), (), (), CoverageDelta(0, 0, 0), 0, 20)

    loop = HarnessReferenceLoop(Writer()) if reference_loop else ContinuousAgentEpisode(Writer())
    states = []
    first = loop.run(task_frame=frame, context=context, registry=ResearchToolRegistry(()), _continuation_sink=states)
    assert first.status == "partial" and len(calls) == 2
    second = loop.resume(states[0], first, goal(1))
    assert second.status == "completed" and len(calls) == 3
    third = loop.resume(states[0], second, goal(2))
    assert len(calls) == 4
    carried = [event for event in third.events
               if event.kind == "model_input" and event.payload.get("source") == "repair_last_rejection"]
    assert len(carried) == 1
    # 第二轮开场作者读到的历史里，那条格式错误仍只有第一轮送达的那一份。
    heard = [message["content"] for message in calls[3] if message["role"] == "user" and "one sentence" in message["content"]]
    assert len(heard) == 1


@pytest.mark.parametrize("reference_loop", [False, True])
def test_repair_round_restates_the_frozen_wire_format_it_still_demands(reference_loop):
    """修复轮是最后一次机会，成稿格式必须随修复目标一起给到作者。

    真实 run_20260917_004950_254515：判官理由送达了，作者改对了内容，却在修复稿里
    把两句塞进一条 claim，`invalid_repair_finish` 直接终局。修复轮消息此前只讲缺什么，
    不重述它仍然要求的 wire 形状。
    """
    from copy import deepcopy
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
    from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal

    frame, context = setup()
    opening = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    frozen = opening["material_grounding"]["finish_format"]
    calls = []

    class Writer:
        def complete(self, *, messages, tools, timeout):
            calls.append(deepcopy(messages))
            payload = claim_finish(context)
            if len(calls) == 1:
                payload["bindings"][1]["claims"] = []
                payload["bindings"][1]["gap"] = "材料未给日期。"
                payload["status"] = "partial"
            return ModelTurn(json.dumps(payload, ensure_ascii=False), (), "offline", "")

    loop = HarnessReferenceLoop(Writer()) if reference_loop else ContinuousAgentEpisode(Writer())
    states = []
    first = loop.run(task_frame=frame, context=context, registry=ResearchToolRegistry(()), _continuation_sink=states)
    goal = RepairGoal(context.contract.task_id, "repair-format-context", 1, ("evidence_boundary",),
                      (), (), (), CoverageDelta(0, 0, 0), 0, 20)
    result = loop.resume(states[0], first, goal)
    assert result.status == "completed" and len(calls) == 2
    repair = [event.payload["content"] for event in result.events
              if event.kind == "model_input" and event.payload.get("source") == "repair_goal"]
    assert len(repair) == 1
    restated = json.loads(repair[0]).get("finish_format")
    # 同一份冻结模板，逐字节相同：修复轮不得另起一套说法。
    assert restated == frozen
    assert "所有claims.text合计" in restated["rule"]
    assert "不能省略子问、计算步骤或本句输入锚点" in restated["rule"]
    assert "先找齐本句使用的原始输入" in restated["rule"]
    assert "数字、计算、事实比较或事实前提" in restated["rule"]
    assert "同一主体、指标、单位及各自期间" in restated["rule"]


def test_claim_rendering_keeps_wrong_quote_as_terminal_integrity_rejection():
    _, context = setup()
    payload = claim_finish(context)
    payload["bindings"][0]["claims"][0]["material_anchors"][0]["quote"] = "不在材料内"
    with pytest.raises(ValueError) as error:
        validate_episode_finish(payload, context=context, evidence=())
    assert error.value.code == "material_source_violation" and error.value.kind.value == "integrity"
