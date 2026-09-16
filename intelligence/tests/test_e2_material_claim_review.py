"""Per-claim semantic receipts cannot borrow adjacent sentences' anchors."""
from dataclasses import replace
import json

import pytest

from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, _judge_report_tools
from intelligence.services.agent_runtime import ModelTurn, ModelToolCall
from intelligence.services.material_grounding import ClaimSourceBinding, MaterialAnchor
from intelligence.tests.test_e2_material_grounding import FACT, fact_claim, outcome, setup, verify


from intelligence.tests.material_judge_helpers import material_judge_report as reviewed


def request_for(context):
    return {"material_claims": [{"claim_id": "c1", "sentence_index": 2}], "sentences": [{"index": 1}, {"index": 2}]}


@pytest.mark.parametrize("mutation", ["missing", "empty", "duplicate", "unknown", "bool_id", "string_bool", "empty_reason"])
def test_material_judge_missing_or_malformed_receipt_cannot_pass(mutation):
    request = request_for(None)
    payload = reviewed(request)
    row = payload["material_claim_checks"][0]
    if mutation == "missing":
        payload.pop("material_claim_checks")
    elif mutation == "empty":
        payload["material_claim_checks"] = []
    elif mutation == "duplicate":
        payload["material_claim_checks"].append(dict(row))
    elif mutation == "unknown":
        row["claim_id"] = "c2"
    elif mutation == "bool_id":
        row["claim_id"] = True
    elif mutation == "string_bool":
        row["supported"] = "true"
    else:
        row["reason"] = " "
    assert SemanticEpisodeVerifier._parse_report(payload, 2, material_claims=request["material_claims"]) is None


def test_claim_pass_requires_explicit_support_kind_and_anchor_receipt():
    request = request_for(None)
    payload = {"passed": True, "rejected_sentence_indexes": [], "issues": [],
               "material_claim_checks": [{"claim_id": "c1", "supported": True, "reason": "该句已有材料支持。"}]}
    assert SemanticEpisodeVerifier._parse_report(payload, 2, material_claims=request["material_claims"]) is None


@pytest.mark.parametrize("indexes", [[], [1], [True], [0], [-1], ["1"]])
def test_judge_cannot_invent_anchors_for_a_claim_with_empty_anchors(indexes):
    request = request_for(None)
    payload = reviewed(request)
    payload["material_claim_checks"][0].update(support_kind="bound_material", anchor_indexes=indexes)
    assert SemanticEpisodeVerifier._parse_report(payload, 2, material_claims=request["material_claims"]) is None


def test_material_support_receipt_validates_against_this_claim_not_the_catalogue():
    request = request_for(None)
    request["material_claims"][0].update(kind="material_fact", material_anchors=[{"material_id": "m1", "quote": "输入"}])
    payload = reviewed(request)
    payload["material_claim_checks"][0].update(support_kind="bound_material", anchor_indexes=[1])
    assert SemanticEpisodeVerifier._parse_report(payload, 2, material_claims=request["material_claims"]).passed
    payload["material_claim_checks"][0]["anchor_indexes"] = [2]
    assert SemanticEpisodeVerifier._parse_report(payload, 2, material_claims=request["material_claims"]) is None
    payload["material_claim_checks"][0].update(support_kind="nonfactual", anchor_indexes=[])
    assert SemanticEpisodeVerifier._parse_report(payload, 2, material_claims=request["material_claims"]) is None


def test_per_claim_rejection_overrides_global_pass():
    request = request_for(None)
    payload = reviewed(request)
    payload["material_claim_checks"][0].update(supported=False, reason="只有问句，没有计算输入。")
    result = SemanticEpisodeVerifier._parse_report(payload, 2, material_claims=request["material_claims"])
    assert result and not result.passed and result.rejected_sentence_indexes == (2,)
    assert any("只有问句" in issue for issue in result.issues)


def test_material_global_pass_without_claim_checks_is_unavailable_not_completed():
    frame, context = setup()
    result = verify(frame, context, outcome(context), lambda request: {
        "passed": True, "rejected_sentence_indexes": [], "issues": [],
    })
    assert result.status != "completed" and result.judge_status == "unavailable"


@pytest.mark.parametrize("kind", ["material_fact", "reasoning", "premise_declaration"])
def test_calculation_cannot_borrow_inputs_from_adjacent_fact_even_in_same_binding(kind):
    frame, context = setup()
    premise = "材料给出收入100万元、新增订单20万元。"
    question = next(m for m in context.contract.material_grounding.materials if "订单占收入比例是多少？" in m.text)
    unsupported = ClaimSourceBinding(FACT, kind, (MaterialAnchor(question.material_id, "订单占收入比例是多少？"),))
    value = outcome(context, (fact_claim(context, premise), unsupported), text=premise + FACT)
    calls = []

    def judge(request):
        calls.append(request)
        rows = request["material_claims"]
        calc = next(row for row in rows if row["text"] == FACT)
        assert [a["quote"] for a in calc["material_anchors"]] == ["订单占收入比例是多少？"]
        assert all("100" not in a["quote"] and "20" not in a["quote"] for a in calc["material_anchors"])
        payload = reviewed(request)
        check = next(c for c in payload["material_claim_checks"] if c["claim_id"] == calc["claim_id"])
        check.update(supported=False, reason="该句只引用问句，缺少分子和分母；邻句的输入不能补位。")
        return payload

    result = verify(frame, context, value, judge)
    assert calls and result.judge_status == "rejected" and result.status != "completed"
    assert FACT not in result.public_answer and premise in result.public_answer


@pytest.mark.parametrize("style", ["keywords", "named"])
def test_material_review_payload_reaches_all_supported_judge_callback_styles(style):
    frame, context = setup()
    seen = []

    def keywords(**request):
        seen.append(request)
        return reviewed(request)

    def named(*, material_claims, material_grounding, sentences):
        request = {"material_claims": material_claims, "material_grounding": material_grounding, "sentences": sentences}
        seen.append(request)
        return reviewed(request)

    result = verify(frame, context, outcome(context), keywords if style == "keywords" else named)
    assert result.status == "completed" and seen[0]["material_claims"]
    assert seen[0]["material_grounding"]["data_scope"] == "material_only"


@pytest.mark.parametrize("case_index", range(4))
def test_control_probe_cases_are_validated_and_require_specific_verdict(case_index):
    from scripts.material_claim_support_probe import CASES, probe_case

    case = CASES[case_index]

    def judge(request):
        rejected = () if case[3] else tuple(row["sentence_index"] for row in request["material_claims"] if row["output_id"] == "evidence_boundary")
        return reviewed(request, rejected=rejected)

    assert probe_case(case, judge)["expectation_matched"]
    if not case[3]:
        assert not probe_case(case, lambda _request: "malformed")["expectation_matched"]


def test_control_probe_requires_explicit_live_opt_in():
    from scripts.material_claim_support_probe import main

    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_complete_material_receipt_allows_correct_calculation():
    frame, context = setup()
    result = verify(frame, context, outcome(context), reviewed)
    assert result.status == "completed" and result.judge_status == "passed"
    checks = result.to_dict()["material_claim_checks"]
    assert checks[0]["text"] == FACT and checks[0]["supported"] is True
    assert checks[0]["material_anchors"] and checks[0]["reason"]


def test_declaration_repeating_numbers_cannot_borrow_prior_claim_support():
    from intelligence.services.episode_semantic_verifier import _judge_system_prompt

    frame, context = setup()
    text = "本答案仅依据材料中的收入100万元和新增订单20万元。"
    question = context.contract.material_grounding.materials[-1]
    claim = ClaimSourceBinding(text, "premise_declaration", (MaterialAnchor(question.material_id, question.text),))
    value = outcome(context)
    value = replace(value, draft=value.draft + "\n" + text, bindings=(
        value.bindings[0], replace(value.bindings[1], claims=(claim,)),
    ))
    calls = []

    def judge(request):
        calls.append(request)
        payload = reviewed(request)
        row = next(row for row in request["material_claims"] if row["text"] == text)
        check = next(check for check in payload["material_claim_checks"] if check["claim_id"] == row["claim_id"])
        check.update(supported=False, reason="声明中重复的收入和订单也是事实，该句仅引问句不能支持这些数字。")
        return payload

    result = verify(frame, context, value, judge)
    assert calls and "重复" in _judge_system_prompt(calls[0])
    assert text not in result.public_answer and result.status == "partial"
    assert "evidence_boundary" in result.verified.missing_outputs
    assert any(check["text"] == text and not check["supported"] for check in result.material_claim_checks)


def test_final_public_projection_filters_private_material_ids_and_reopens_lost_slot():
    from intelligence.services.episode_semantic_verifier import recheck_material_public_delivery

    frame, context = setup()
    good = verify(frame, context, outcome(context), reviewed)
    source_id = context.contract.material_grounding.materials[0].material_id
    projected = good.public_answer.replace(FACT, FACT[:-1] + f"（{source_id}）。")
    result = recheck_material_public_delivery(good, projected=projected)
    assert source_id not in result.public_answer
    assert result.status == "partial" and "answer_q1" in result.verified.missing_outputs


def test_judge_outage_also_filters_known_material_coordinates():
    from intelligence.services.episode_semantic_verifier import recheck_material_public_delivery

    frame, context = setup()
    result = verify(frame, context, outcome(context), lambda request: {})
    source_id = context.contract.material_grounding.materials[0].material_id
    result = recheck_material_public_delivery(result, projected=f"材料{source_id}尚未审核。")
    assert result.judge_status == "unavailable" and source_id not in result.public_answer


def test_public_projection_does_not_filter_arbitrary_id_like_user_data():
    frame, context = setup()
    text = "记录编号为m-0123456789。"
    value = outcome(context, (fact_claim(context, text),), text=text)
    result = verify(frame, context, value, reviewed)
    assert text in result.public_answer


def test_ordinary_judge_contract_does_not_gain_material_fields():
    payload = {"passed": True, "rejected_sentence_indexes": [], "issues": []}
    assert SemanticEpisodeVerifier._parse_report(payload, 1).passed
    assert SemanticEpisodeVerifier._parse_report({**payload, "material_claim_checks": []}, 1) is None


def test_identical_sentences_in_two_questions_keep_position_identity():
    from intelligence.tests.test_e2_material_delivery import setup_delivery, outcome_for, answered_binding, BOUNDARY

    frame, context = setup_delivery()
    value = outcome_for(context)
    text = "材料没有给出利润率。"
    value = replace(value, draft=f"## q1\n{text}\n## q2\n{text}{BOUNDARY}", bindings=(
        answered_binding(context, "answer_q1", text), answered_binding(context, "answer_q2", text), value.bindings[2],
    ))
    calls = []
    verify(frame, context, value, lambda request: (calls.append(request), reviewed(request))[1])
    rows = calls[0]["material_claims"]
    assert [(row["output_id"], row["sentence_index"]) for row in rows] == [("answer_q1", 2), ("answer_q2", 4)]


def test_related_judge_tool_schema_and_parser_enforce_same_claim_checks():
    request = request_for(None)
    schema = _judge_report_tools(request)[0]["function"]["parameters"]
    assert "material_claim_checks" in schema["required"]
    assert "material_claim_checks" not in _judge_report_tools({})[0]["function"]["parameters"]["properties"]
    payload = reviewed(request)
    turn = ModelTurn("", (ModelToolCall("call1", "submit_grounding_report", payload),), "offline", "")
    report = SemanticEpisodeVerifier._parse_tool_report(turn, 2, material_claims=request["material_claims"])
    assert report and report.passed and report.to_dict()["material_claim_checks"]
    payload.pop("material_claim_checks")
    assert SemanticEpisodeVerifier._parse_report(json.dumps(payload), 2, material_claims=request["material_claims"]) is None
