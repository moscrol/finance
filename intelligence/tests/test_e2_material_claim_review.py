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


def test_complete_material_receipt_allows_correct_calculation():
    frame, context = setup()
    result = verify(frame, context, outcome(context), reviewed)
    assert result.status == "completed" and result.judge_status == "passed"
    checks = result.to_dict()["material_claim_checks"]
    assert checks[0]["text"] == FACT and checks[0]["supported"] is True
    assert checks[0]["material_anchors"] and checks[0]["reason"]


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
