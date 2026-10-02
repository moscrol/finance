"""The task compiler, not the terminal verifier, owns redundant output IDs.

No live provider is used. Full HTTP fixture replay lives in the separately pinned
review probe; these regressions exercise compilation and the real owner/verifier
projection, including rejected answers after normalization.
"""
from dataclasses import replace

import pytest

from intelligence.runtime.conversation_orchestrator import _specialized_owner_required_outputs
from intelligence.services.answer_model import AnswerSpec, Claim, ClaimStatus, EvidenceRef, resolve_answer_profile
from intelligence.services.query_understanding import QueryEnvelope
from intelligence.services.task_frame import TaskFrame, build_task_frame, derive_required_outputs, rebase_task_frame
from intelligence.services.task_fulfillment import evaluate_answer_spec_fulfillment
from intelligence.services.turn_controller import decide_turn
from intelligence.workbench_skills.contracts import SkillAnswerContract, SkillOutput


QUESTION = "那它有哪些主要风险，下一步该怎么验证？"


def _frame(outputs: tuple[str, ...]):
    return build_task_frame(
        QUESTION,
        QueryEnvelope(
            question_type="general_finance_qa", subject_kind="company", subject="测试公司",
            decision_goal=QUESTION, timeframe=None, matched_by="explicit", confidence=0.9,
            required_outputs=outputs,
        ),
    )


@pytest.mark.parametrize("extras", (
    ("direct_answer", "direct_assessment"),
    ("direct_assessment", "direct_answer"),
    ("direct_answer", "direct_assessment", "direct_answer"),
))
def test_build_compiles_one_direct_output_and_keeps_independent_requirements(extras):
    frame = _frame((*extras, "counterpoint", "verification_conditions", "customer_validation"))
    assert frame.required_outputs == (
        "evidence_boundary", "direct_assessment", "counterpoint",
        "verification_conditions", "customer_validation",
    )
    assert frame.raw_question == QUESTION
    assert frame.subject == "测试公司"


def test_rebase_deduplicates_outputs_reintroduced_by_inherited_intent():
    initial = _frame(())
    assert initial.required_outputs == ("direct_answer", "evidence_boundary")
    rebased = rebase_task_frame(
        initial, question_type="stock_deep_dive", subject="测试公司",
        required_outputs=(
            "direct_assessment", "supporting_evidence", "counterpoint",
            "direct_answer", "evidence_boundary", "verification_conditions",
        ),
    )
    assert rebased.required_outputs == (
        "direct_assessment", "supporting_evidence", "counterpoint",
        "evidence_boundary", "verification_conditions",
    )
    assert rebased.task_frame_hash != initial.task_frame_hash
    assert rebase_task_frame(
        rebased, question_type=rebased.question_type, subject=rebased.subject,
        required_outputs=rebased.required_outputs,
    ) == rebased


@pytest.mark.parametrize("question_type", ("general_finance_qa", "general_knowledge", "news_impact"))
def test_no_registered_target_does_not_drop_or_invent_direct_output(question_type):
    outputs = derive_required_outputs(question_type, QUESTION, extra=("direct_answer",))
    assert "direct_answer" in outputs
    assert "direct_assessment" not in outputs


def test_related_but_independent_outputs_are_not_global_aliases():
    extras = (
        "direct_definition", "evidence_boundary", "counterpoint", "current_baseline",
        "rebound_case", "decline_case", "scenario_tree", "invalidation_conditions",
    )
    outputs = derive_required_outputs("stock_deep_dive", QUESTION, extra=extras)
    assert set(extras).issubset(outputs)


@pytest.mark.parametrize("subject", ("英维克", "中际旭创"))
@pytest.mark.parametrize("question", (
    "那它的主要风险和下一步验证是什么？",
    QUESTION,
    "那它的风险呢？接下来怎么验证？",
))
def test_manual_followup_compiles_one_identity_before_owner_execution(subject, question):
    def unavailable(*_args, **_kwargs):
        return None, None, "offline provider unavailable"

    first = decide_turn(
        f"请个股深挖{subject}", skill_mode="manual", selected_skill_ids=("stock-deep-dive",),
        llm_complete=unavailable,
    )
    followup = decide_turn(
        question, previous_intent=first.turn_intent, previous_turn_id="prior-user-turn",
        skill_mode="manual", selected_skill_ids=("stock-deep-dive",), llm_complete=unavailable,
    )
    frame = followup.task_frame
    intent = followup.turn_intent
    assert frame is not None and intent is not None
    assert frame.raw_question == question
    assert frame.subject == subject
    assert frame.question_type == "stock_deep_dive"
    assert intent.answer_owner == "stock-deep-dive"
    assert intent.inherited_from_turn == "prior-user-turn"
    assert "direct_assessment" in frame.required_outputs
    assert "direct_answer" not in frame.required_outputs
    assert "evidence_boundary" in frame.required_outputs
    assert intent.required_outputs == frame.required_outputs
    assert intent.task_frame_hash == frame.task_frame_hash


@pytest.mark.parametrize("question, subject, question_type, inherited", (
    ("换个公司，个股深挖中际旭创", "中际旭创", "stock_deep_dive", None),
    ("再看一下最新财报", "英维克", "financial_analysis", "prior"),
))
def test_followup_task_or_subject_switch_still_recomputes_its_own_contract(
    question, subject, question_type, inherited,
):
    def unavailable(*_args, **_kwargs):
        return None, None, "offline unavailable"

    first = decide_turn("请个股深挖英维克", llm_complete=unavailable)
    decision = decide_turn(
        question, previous_intent=first.turn_intent, previous_turn_id="prior",
        llm_complete=unavailable,
    )
    assert decision.subject == subject
    assert decision.question_type == question_type
    assert decision.turn_intent.inherited_from_turn == inherited
    if question_type == "financial_analysis":
        assert decision.task_frame.required_outputs == (
            "financial_assessment", "metric_evidence", "counterpoint",
        )


def test_explicit_current_requirement_is_not_replaced_by_old_direct_slot():
    initial = _frame(())
    initial = replace(initial, raw_question="那它什么时候算失效")
    rebased = rebase_task_frame(
        initial, question_type="stock_deep_dive", subject="测试公司",
        required_outputs=("direct_assessment", "direct_answer", "counterpoint"),
    )
    assert rebased.required_outputs == ("invalidation_conditions", "supporting_evidence")


def test_serialized_legacy_frame_is_not_silently_migrated_or_rehashed():
    legacy = replace(_frame(()), required_outputs=("direct_answer", "direct_assessment"))
    restored = TaskFrame.from_dict(legacy.to_dict())
    assert restored == legacy
    assert restored.task_frame_hash == legacy.task_frame_hash


def _answer(frame):
    direct = Claim(
        claim_id="summary:company", text="测试公司的交付风险取决于客户验收进度。",
        claim_type="summary", theme="测试公司", evidence_ids=("G1",), status=ClaimStatus.INFERRED,
    )
    boundary = Claim(
        claim_id="gap:company", text="证据边界：尚未取得客户验收结果，不能确认交付兑现。",
        claim_type="evidence_gap", theme="测试公司", evidence_ids=(), status=ClaimStatus.MISSING,
    )
    spec = AnswerSpec(
        research_spec=resolve_answer_profile(QUESTION, profile="general"),
        summary=(direct,), verified_facts=(), company_table=(), counter_evidence=(),
        gaps=(boundary,), triggers=(), next_actions=(),
        sources=(EvidenceRef(
            evidence_id="G1", source="公司披露", detail="测试公司客户验收进度与交付风险",
            source_date="2026-07-21", freshness="current",
        ),), system_notices=(),
    )
    contract = SkillAnswerContract(
        retrieval_plan=(), output_contract=frame.required_outputs, answer_spec=spec,
        required_outputs=frame.required_outputs, task_frame_hash=frame.task_frame_hash,
        question_type=frame.question_type,
    )
    output = SkillOutput(
        skill_id="stock-deep-dive", modules=[], citations=[], warnings=[],
        as_of=None, raw_result_ref=None, answer_contract=contract,
    )
    return spec, output, direct.text + "\n" + boundary.text


@pytest.mark.parametrize("damage", ("none", "no_claim", "no_source", "no_prose", "no_boundary"))
def test_canonical_owner_gate_still_requires_claim_source_public_prose_and_boundary(damage):
    frame = _frame(("direct_assessment",))
    spec, output, text = _answer(frame)
    if damage == "no_claim":
        spec = replace(spec, summary=())
    elif damage == "no_source":
        spec = replace(spec, sources=())
    elif damage == "no_prose":
        text = ""
    elif damage == "no_boundary":
        spec = replace(spec, gaps=())
        text = spec.summary[0].text
    required = _specialized_owner_required_outputs(output, frame)
    assert tuple(item.output_id for item in required) == frame.required_outputs
    verdict = evaluate_answer_spec_fulfillment(
        question=QUESTION, required_outputs=required, answer_text=text, answer_spec=spec,
    )
    if damage == "none":
        assert verdict.status == "complete"
    else:
        assert verdict.status != "complete"
        missing_output = "evidence_boundary" if damage == "no_boundary" else "direct_assessment"
        assert next(item for item in verdict.items if item.output_id == missing_output).status != "fulfilled"


def test_boundary_only_prose_must_not_stand_in_for_the_direct_answer():
    # Known baseline defect, intentionally RED: token overlap is not coverage.
    # Do not waive this independent semantic counterexample to sign an ID repair.
    frame = _frame(("direct_assessment",))
    spec, output, _text = _answer(frame)
    verdict = evaluate_answer_spec_fulfillment(
        question=QUESTION, required_outputs=_specialized_owner_required_outputs(output, frame),
        answer_text=spec.gaps[0].text, answer_spec=spec,
    )
    assert next(item for item in verdict.items if item.output_id == "direct_assessment").status != "fulfilled"


def test_owner_cannot_remove_independent_requirement_or_add_its_own_gate():
    frame = _frame(("direct_assessment", "customer_validation"))
    spec, output, text = _answer(frame)
    assert output.answer_contract is not None
    output = replace(output, answer_contract=replace(
        output.answer_contract, required_outputs=("direct_assessment", "owner_invented"),
    ))
    required = _specialized_owner_required_outputs(output, frame)
    assert tuple(item.output_id for item in required) == frame.required_outputs
    verdict = evaluate_answer_spec_fulfillment(
        question=QUESTION, required_outputs=required, answer_text=text, answer_spec=spec,
    )
    assert verdict.status != "complete"
    assert next(item for item in verdict.items if item.output_id == "customer_validation").status == "missing"
    assert "owner_invented" not in {item.output_id for item in verdict.items}
