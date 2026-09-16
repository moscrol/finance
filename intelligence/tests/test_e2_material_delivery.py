"""D5 structural delivery, not D6 material-fact support or live P7 acceptance.

All judges below are explicit offline doubles. Answered fixtures now use D6
material anchors; these tests still certify delivery, not semantic entailment.
"""
from dataclasses import replace
import json
from uuid import uuid4

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, OutputEvidenceBinding
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import build_episode_input, validate_episode_finish
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.material_grounding import ClaimSourceBinding, MaterialAnchor, claim_sentences
from intelligence.services.material_delivery import question_sections
from intelligence.services.query_understanding import understand_query
from intelligence.services.repair_coordinator import classify_repair_need
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_tool_registry import ResearchToolRegistry

GAP1 = "缺少甲的订单毛利率，无法计算新增利润。"
GAP2 = "缺少乙的订单毛利率，无法判断是否满足升级条件。"
BOUNDARY = "\n\n## 证据边界\n仅依据用户材料，不补充材料外事实。"


def setup_delivery(*, memo=False):
    q2 = ("请写一份不超过200字的研究备忘录。" if memo else "乙是否满足升级条件？")
    frame = understand_query(
        "只依据以下材料回答。\n\n「甲收入100，订单20；乙订单毛利率未知。」\n\n"
        f"1. 甲新增利润是多少？\n\n2. {q2}"
    ).task_frame
    context = build_episode_context(frame, task_id=f"d5-delivery-{uuid4().hex}")
    assert [q.question_id for q in context.contract.material_contract.questions] == ["q1", "q2"]
    return frame, context


def answered_binding(context, output_id, body):
    source = context.contract.material_grounding.materials[0]
    return OutputEvidenceBinding(output_id, (), claims=tuple(
        ClaimSourceBinding(text, "material_fact", (MaterialAnchor(source.material_id, source.text),))
        for text in claim_sentences(body)
    ))


def outcome_for(context, *, all_gap=False, draft=None, status="partial"):
    evidence = AgentEvidence(
        tool="user_material", title="用户材料", detail="甲收入100，订单20。",
        source="user", content_hash="d5-synthetic-structural-evidence",
    )
    first = GAP1 if all_gap else "甲订单占收入20%；材料没有给出利润率，不能换算成利润。"
    draft = draft if draft is not None else f"## q1\n{first}\n\n## q2\n{GAP2}{BOUNDARY}"
    body = question_sections(draft).get("q1", (first,))[0]
    return AgentOutcome(
        task_frame_hash=context.contract.task_frame_hash,
        status=status,
        draft=draft,
        evidence=() if all_gap else (evidence,), traces=(), gaps=(),
        stop_reason="model_finish", usage=AgentUsage(),
        events=(EpisodeEvent(1, "task", {"task_frame_hash": context.contract.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding("answer_q1", (), gap=GAP1) if all_gap else answered_binding(context, "answer_q1", body),
            OutputEvidenceBinding("answer_q2", (), gap=GAP2),
            OutputEvidenceBinding("evidence_boundary", (), basis="user_premise"),
        ),
    )


def repair_need(verified):
    return classify_repair_need(verified.outcome, verified, rejected_claims=(), semantic_gap_outputs=())


def finish_for(outcome):
    return {"status": outcome.status, "draft": outcome.draft, "gaps": list(outcome.gaps),
            "bindings": [b.to_dict() for b in outcome.bindings]}


@pytest.mark.parametrize("all_gap", [False, True])
def test_legal_gap_is_addressed_but_never_completed_or_a_repair_target(all_gap):
    _, context = setup_delivery()
    outcome = outcome_for(context, all_gap=all_gap)
    finish = validate_episode_finish(finish_for(outcome), context=context, evidence=outcome.evidence)
    verified = verify_episode_outcome(context.contract, replace(outcome, draft=finish.draft, bindings=finish.bindings))
    statuses = {s.output_id: s.status for s in verified.completion.outputs}
    assert statuses["answer_q1"] == ("legal_gap" if all_gap else "fulfilled")
    assert statuses["answer_q2"] == "legal_gap"
    assert verified.verified_status == "partial"
    assert verified.missing_outputs == ()
    assert verified.issue_items == ()
    assert repair_need(verified).work_units == 0


@pytest.mark.parametrize("draft,gap", [
    (f"## q1\n{GAP1}{BOUNDARY}", GAP2),                         # missing question
    (f"## q1\n{GAP1}\n## q2\n{BOUNDARY}", GAP2),              # empty shell
    (f"## q1\n{GAP1}\n## q2\n材料不足，无法判断。{BOUNDARY}", "材料不足，无法判断。"),
    (f"## q1\n{GAP1}\n## q2\n乙满足升级条件。{BOUNDARY}", GAP2),  # private gap only
    (f"## q1\n{GAP1}\n## q2\n{GAP1}{BOUNDARY}", GAP2),       # wrong question's gap
    (f"## q1\n{GAP1}\n## q2\n{GAP2}\n## q2\n{GAP2}{BOUNDARY}", GAP2),  # duplicate
    (f"## q1\n{GAP1}\n```text\n## q2\n{GAP2}\n```{BOUNDARY}", GAP2),  # quoted answer
])
def test_missing_or_undisclosed_gap_stays_missing_and_repairable(draft, gap):
    _, context = setup_delivery()
    outcome = outcome_for(context, all_gap=True, draft=draft)
    outcome = replace(outcome, bindings=(outcome.bindings[0], replace(outcome.bindings[1], gap=gap), outcome.bindings[2]))
    verified = verify_episode_outcome(context.contract, outcome)
    assert "answer_q2" in verified.missing_outputs
    assert repair_need(verified).work_units >= 1
    with pytest.raises(ValueError):
        validate_episode_finish(finish_for(outcome), context=context, evidence=outcome.evidence)


def test_duplicate_binding_cannot_last_write_win_in_structural_verifier():
    _, context = setup_delivery()
    outcome = outcome_for(context, all_gap=True)
    with pytest.raises(ValueError, match="duplicate"):
        replace(outcome, bindings=(*outcome.bindings, outcome.bindings[1]))
    payload = finish_for(outcome)
    payload["bindings"].append(payload["bindings"][1])
    with pytest.raises(ValueError, match="duplicate"):
        validate_episode_finish(payload, context=context, evidence=())


def test_ordinary_full_contract_does_not_gain_legal_gap_release():
    _, context = setup_delivery()
    contract = replace(context.contract, material_contract=None)
    outcome = outcome_for(context, all_gap=True)
    verified = verify_episode_outcome(contract, outcome)
    assert set(verified.missing_outputs) == {"answer_q1", "answer_q2"}
    assert not any(s.status == "legal_gap" for s in verified.completion.outputs)


def test_ordinary_full_finish_notice_projection_is_byte_preserving():
    from intelligence.services.material_delivery import with_all_material_gaps_notice
    _, context = setup_delivery()
    ordinary = replace(context.contract, material_contract=None)
    text = "\n  普通答案，不要求材料题逐题格式。  \n"
    assert with_all_material_gaps_notice(ordinary, text, ()) == text


def test_all_answered_honest_runtime_partial_keeps_existing_semantic_completion():
    frame, context = setup_delivery()
    original = outcome_for(context)
    original = replace(original, draft=f"## q1\n甲订单占收入20%。\n## q2\n已按材料说明限制。{BOUNDARY}",
                       bindings=(answered_binding(context, "answer_q1", "甲订单占收入20%。"), answered_binding(context, "answer_q2", "已按材料说明限制。"), original.bindings[2]))
    # This offline judge approves an intentionally synthetic draft: no claim
    # of real-world accuracy, only the pre-existing partial->completed seam.
    result = SemanticEpisodeVerifier(judge_fn=lambda _: {"passed": True, "rejected_sentence_indexes": [], "issues": []}).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, original), deadline=ResearchDeadline.from_timeout(60),
    )
    assert result.judge_status == "passed" and result.status == "completed"
    assert result.repair_output_ids == ()


def test_completed_cannot_smuggle_a_legal_gap():
    _, context = setup_delivery()
    outcome = outcome_for(context, all_gap=True, status="completed")
    assert verify_episode_outcome(context.contract, outcome).verified_status == "partial"
    with pytest.raises(ValueError, match="required output lacks evidence"):
        validate_episode_finish(finish_for(outcome), context=context, evidence=())


@pytest.mark.parametrize("mutation", ["basis", "unknown_hash", "ambiguous_hash"])
def test_gap_does_not_bypass_integrity_gates(mutation):
    _, context = setup_delivery()
    outcome = outcome_for(context)
    binding = outcome.bindings[1]
    if mutation == "basis":
        binding = replace(binding, basis="user_premise")
    elif mutation == "unknown_hash":
        binding = replace(binding, evidence_hashes=("forged",))
    else:
        binding = replace(binding, evidence_hashes=(outcome.evidence[0].content_hash,))
        outcome = replace(outcome, evidence=(*outcome.evidence, outcome.evidence[0]))
    outcome = replace(outcome, bindings=(outcome.bindings[0], binding, outcome.bindings[2]))
    verified = verify_episode_outcome(context.contract, outcome)
    assert "answer_q2" in verified.missing_outputs
    calls = []
    def judge(request):
        calls.append(request)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}
    SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=setup_delivery()[0], structurally_verified=verified, deadline=ResearchDeadline.from_timeout(60),
    )
    assert not calls


@pytest.mark.parametrize("all_gap", [False, True])
def test_material_partial_is_actually_judged_and_preserves_public_question_gaps(all_gap):
    frame, context = setup_delivery()
    outcome = outcome_for(context, all_gap=all_gap)
    verified = verify_episode_outcome(context.contract, outcome)
    calls = []
    def judge(request):
        calls.append(request)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(60),
    )
    assert len(calls) == 1  # not a fabricated 'passed' or 'not applicable'
    assert result.judge_status == "passed"
    assert result.status == "partial"
    assert GAP2 in result.public_answer
    assert result.gap_output_ids == ()
    assert result.to_dict()["pending_rejudge"] is False
    if all_gap:
        assert result.public_answer.startswith("仅凭本轮材料，以下各题均暂不能得出结论")
    assert calls[0]["material_delivery"]["question_states"]["q2"] == "legal_gap"
    from intelligence.services.episode_semantic_verifier import _judge_system_prompt
    prompt = _judge_system_prompt(calls[0])
    assert "缺失声明" in prompt and "不得因元陈述" in prompt


def test_all_answered_can_complete_without_counting_boundary_as_a_question():
    _, context = setup_delivery()
    outcome = outcome_for(context, status="completed")
    outcome = replace(outcome, draft=f"## q1\n甲订单占收入20%。\n## q2\n无法确定是否升级；毛利率未知。{BOUNDARY}",
                      bindings=(answered_binding(context, "answer_q1", "甲订单占收入20%。"), answered_binding(context, "answer_q2", "无法确定是否升级；毛利率未知。"), outcome.bindings[2]))
    # Structural only: the judge is responsible for whether this actually answers q1.
    validate_episode_finish(finish_for(outcome), context=context, evidence=outcome.evidence)
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.verified_status == "completed"


@pytest.mark.parametrize("length,valid", [(200, True), (201, False)])
def test_explicit_memo_limit_applies_to_its_own_original_question_slot(length, valid):
    _, context = setup_delivery(memo=True)
    outcome = outcome_for(context, draft=f"## q1\n甲订单占收入20%。\n## q2\n{'研' * length}{BOUNDARY}", status="completed")
    outcome = replace(outcome, bindings=(outcome.bindings[0], answered_binding(context, "answer_q2", "研" * length), outcome.bindings[2]))
    assert [x.output_id for x in context.contract.required_outputs] == ["answer_q1", "answer_q2", "evidence_boundary"]
    if valid:
        validate_episode_finish(finish_for(outcome), context=context, evidence=outcome.evidence)
    else:
        with pytest.raises(ValueError):
            validate_episode_finish(finish_for(outcome), context=context, evidence=outcome.evidence)
        assert "answer_q2" in verify_episode_outcome(context.contract, outcome).missing_outputs


@pytest.mark.parametrize("all_gap", [False, True])
def test_adapter_settles_gaps_without_resume_or_old_ranking_requirements(all_gap):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession

    frame, context = setup_delivery()
    initial = outcome_for(context, all_gap=all_gap)
    calls, resumes = [], []

    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                resumes.append(goal)
                raise AssertionError("a disclosed gap must not resume research")
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=initial, resume_callback=resume)

    def judge(request):
        calls.append(request)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert result.status == "partial", result.private_artifact
    assert len(calls) == 1 and not resumes
    assert result.private_artifact["repair_attempts"] == result.private_artifact["backfill_turns"] == 0
    assert GAP2 in result.answer
    assert GAP2 in result.open_gaps  # the question text is not the missing input


def test_legal_gap_closes_repair_ledger_without_claiming_evidence_coverage():
    from intelligence.runtime.continuous_turn_adapter import _empty_repair_snapshot, _repair_snapshot
    from intelligence.services.evidence_ledger import EvidenceLedger
    _, context = setup_delivery()
    outcome = outcome_for(context, all_gap=True)
    ledger = EvidenceLedger()
    for name in _empty_repair_snapshot(context).open_gaps:
        ledger.open_gap(name)
    snapshot = _repair_snapshot(outcome, verify_episode_outcome(context.contract, outcome), context, ledger=ledger)
    assert snapshot.open_gaps == ()
    assert snapshot.covered_outputs == ()


def test_material_question_missing_cannot_be_downgraded_to_optional_for_no_tools():
    from intelligence.services.mandatory_satisfiability import apply_unreachable_downgrade
    from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
    _, context = setup_delivery()
    goal = RepairGoal(context.contract.task_id, "repair-gap", 1, ("answer_q2",), (), (), (), CoverageDelta(0, 0, 0), 0, 20)
    contract, prompt_goal = apply_unreachable_downgrade(context.contract, goal)
    assert contract == context.contract
    assert prompt_goal.missing_answer_elements == ("answer_q2",)


def test_missing_material_question_enters_tool_closed_expression_repair():
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession

    frame, context = setup_delivery()
    complete = outcome_for(context, all_gap=True)
    initial = replace(complete, draft=f"## q1\n{GAP1}{BOUNDARY}", bindings=(complete.bindings[0], complete.bindings[2]))
    assert repair_need(verify_episode_outcome(context.contract, initial)).shape.contract_rewrite
    resumes = []
    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                resumes.append(goal)
                assert not goal.reopen_tools and goal.remaining_calls == 0
                assert goal.missing_answer_elements == ("answer_q2",)
                return replace(complete, events=(*previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=initial, resume_callback=resume)

    result = ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=lambda _: {"passed": True, "rejected_sentence_indexes": [], "issues": []}),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert len(resumes) == 1, result.private_artifact
    assert result.status == "partial"
    assert result.private_artifact["semantic_verifier"]["repair_output_ids"] == []
    assert GAP2 in result.answer


def test_deletion_rechecks_a_previously_legal_gap_even_when_section_heading_remains():
    from intelligence.services.episode_output_substance import lost_required_output_substance
    frame, context = setup_delivery()
    before = outcome_for(context, all_gap=True)
    after = before.draft.replace(GAP2, "")
    assert lost_required_output_substance(context.contract, before.draft, after) == ("answer_q2",)
    verified = verify_episode_outcome(context.contract, replace(before, draft=after))
    assert verified.missing_outputs == ("answer_q2",)
    calls = []
    result = SemanticEpisodeVerifier(judge_fn=lambda request: calls.append(request)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(60),
    )
    assert not calls
    # Withholding an unjudged draft is not a writer omission. It must keep
    # q2's existing obligation, not invent a rewrite of q1 while awaiting review.
    assert result.repair_output_ids == ("answer_q2",)
    assert GAP1 not in result.public_answer


def test_material_partial_never_fabricates_a_successful_judge_on_outage():
    frame, context = setup_delivery()
    outcome = outcome_for(context, all_gap=True)
    def unavailable(_):
        raise ValueError("offline judge intentionally unavailable")
    result = SemanticEpisodeVerifier(judge_fn=unavailable).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, outcome), deadline=ResearchDeadline.from_timeout(60),
    )
    assert result.judge_status == "unavailable"
    assert result.to_dict()["pending_rejudge"] is True
    assert result.status != "completed"


@pytest.mark.parametrize("mutation", ["omitted", "optional", "duplicate"])
def test_frozen_material_contract_cannot_lose_a_question_obligation(mutation):
    from intelligence.services.research_contract import ResearchTaskContract
    _, context = setup_delivery()
    outputs = context.contract.required_outputs
    if mutation == "omitted":
        outputs = (outputs[0], outputs[2])
    elif mutation == "optional":
        outputs = (outputs[0], replace(outputs[1], required=False), outputs[2])
    else:
        outputs = (*outputs, outputs[1])
    with pytest.raises(ValueError):
        replace(context.contract, required_outputs=outputs)
    payload = context.contract.to_dict()
    if mutation == "omitted":
        del payload["required_outputs"][1]
    elif mutation == "optional":
        payload["required_outputs"][1]["required"] = False
    else:
        payload["required_outputs"].append(payload["required_outputs"][1])
    with pytest.raises(ValueError):
        ResearchTaskContract.from_dict(payload)


def test_original_t2_t3_only_the_explicit_t3_q8_is_a_memo():
    from pathlib import Path
    from intelligence.services.conversation_materials import collect_material_turn_history
    from intelligence.services.conversation_store import Message
    from intelligence.services.material_delivery import material_question_outputs
    from intelligence.services.turn_controller import decide_turn

    root = Path(__file__).resolve().parents[2] / "docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok"
    t2 = (root / "t2-question.txt").read_text()
    t3 = (root / "t3-question.txt").read_text()
    history = collect_material_turn_history((Message("t2", "conv", "user", t2, "2026-09-16", "completed"),))
    frame2 = decide_turn(t2).task_frame
    frame3 = decide_turn(t3, conversation_materials=history).task_frame  # no repeated prohibition
    specs2 = material_question_outputs(build_episode_context(frame2, task_id=f"t2-{uuid4().hex}").contract)
    specs3 = material_question_outputs(build_episode_context(frame3, task_id=f"t3-{uuid4().hex}").contract)
    assert len(specs2) == len(specs3) == 8
    assert all(x.delivery_kind == "answer" and x.max_chars is None for x in specs2)
    assert [x.question_id for x in specs3 if x.delivery_kind == "memo"] == ["q8"]
    assert specs3[-1].output_id == "answer_q8" and specs3[-1].max_chars == 200
    # Disclosure review needs prior USER materials, not the previous answer
    # masquerading as supporting evidence. This is context delivery, not D6.
    context3 = build_episode_context(frame3, task_id=f"t3-judge-{uuid4().hex}")
    base = outcome_for(context3, all_gap=True)
    request = SemanticEpisodeVerifier()._judge_request(frame3, verify_episode_outcome(context3.contract, base), [])
    supplied = request["material_delivery"]["prior_user_materials"]
    assert [row["material_id"] for row in supplied] == [item.ref.material_id for item in history.items]
    assert all(row["source_message_id"] == "t2" for row in supplied)
    assert all(row["text"] == item.text for row, item in zip(supplied, history.items, strict=True))


@pytest.mark.parametrize("heading", ["## q2", "### Q2", "2. ", "第2题：", "**Q2**", "【q2】"])
def test_question_number_variants_do_not_renumber_the_original(heading):
    _, context = setup_delivery()
    # Numbered paragraphs form their own peer list; an unlabelled inner list
    # under ## q1 is not allowed to steal q2's original identity.
    first_heading = "1." if heading == "2. " else ("### q1" if heading.startswith("###") else "## q1")
    text = f"{first_heading}\n{GAP1}\n{heading}\n{GAP2}{BOUNDARY}"
    outcome = outcome_for(context, all_gap=True, draft=text)
    assert verify_episode_outcome(context.contract, outcome).missing_outputs == ()


def test_nested_numbered_case_is_not_a_second_question_section():
    _, context = setup_delivery()
    outcome = outcome_for(context, all_gap=True,
                          draft=f"## q1\n{GAP1}\n1. 案例说明。\n2. 另一案例说明。\n## q2\n{GAP2}{BOUNDARY}")
    assert verify_episode_outcome(context.contract, outcome).missing_outputs == ()


def test_sanitization_that_removes_a_gap_reopens_that_question():
    frame, context = setup_delivery()
    outcome = outcome_for(context)
    gap = "缺少 d5-synthetic-structural-evidence 毛利率，无法计算新增利润。"
    outcome = replace(outcome, draft=f"## q1\n甲订单占收入20%。\n## q2\n{gap}{BOUNDARY}",
                      bindings=(answered_binding(context, "answer_q1", "甲订单占收入20%。"), replace(outcome.bindings[1], gap=gap), outcome.bindings[2]))
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.missing_outputs == ()
    result = SemanticEpisodeVerifier(judge_fn=lambda _: {"passed": True, "rejected_sentence_indexes": [], "issues": []}).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(60),
    )
    assert "answer_q2" in result.repair_output_ids
    assert "d5-synthetic-structural-evidence" not in result.public_answer
    assert not result.public_answer.startswith("仅凭本轮材料，以下各题均暂不能得出结论")


def test_gap_hash_caveat_cannot_escape_memo_limit_after_normalization():
    _, context = setup_delivery(memo=True)
    outcome = outcome_for(context, draft=f"## q1\n甲订单占收入20%。\n## q2\n{'研' * 201}{BOUNDARY}")
    outcome = replace(outcome, bindings=(outcome.bindings[0], replace(outcome.bindings[1], evidence_hashes=(outcome.evidence[0].content_hash,)), outcome.bindings[2]))
    with pytest.raises(ValueError):
        validate_episode_finish(finish_for(outcome), context=context, evidence=outcome.evidence)


def test_old_ranking_and_track_templates_do_not_reopen_material_question_gaps():
    from intelligence.runtime.continuous_turn_adapter import _with_track_contract_gaps
    from intelligence.services.track_contract import merge_track_missing_outputs
    from intelligence.services.ranking_contract import merge_ranking_missing_outputs

    _, context = setup_delivery()
    for kind, text in [("theme_stock_priority", "比较甲和乙谁更受益，排序并逐题回答"), ("theme_track", "继续跟踪商业航天")]:
        changed = replace(context, contract=replace(context.contract, question_type=kind, question=text))
        outcome = outcome_for(changed, all_gap=True)
        verified = verify_episode_outcome(changed.contract, outcome)
        # Ensure this is a real template trigger rather than an idle stub.
        legacy = merge_track_missing_outputs((), outcome.draft, query=text, question_type=kind)
        legacy = merge_ranking_missing_outputs(legacy, outcome.draft, query=text, question_type=kind)
        assert legacy
        assert _with_track_contract_gaps(verified, changed).missing_outputs == ()


@pytest.mark.parametrize("body", ["乙是否满足升级条件？", "### 未决事项", "待补", "> 缺少乙的订单毛利率，无法判断是否满足升级条件。"])
def test_question_copy_subheading_placeholder_or_quoted_gap_is_not_an_answer(body):
    _, context = setup_delivery()
    outcome = outcome_for(context, all_gap=True, draft=f"## q1\n{GAP1}\n## q2\n{body}{BOUNDARY}")
    assert "answer_q2" in verify_episode_outcome(context.contract, outcome).missing_outputs
    with pytest.raises(ValueError):
        validate_episode_finish(finish_for(outcome), context=context, evidence=())


def test_memo_overflow_cannot_hide_in_a_quote():
    _, context = setup_delivery(memo=True)
    outcome = outcome_for(context, draft=f"## q1\n甲订单占收入20%。\n## q2\n{GAP2}\n> {'研' * 201}{BOUNDARY}")
    assert "answer_q2" in verify_episode_outcome(context.contract, outcome).missing_outputs
    with pytest.raises(ValueError):
        validate_episode_finish(finish_for(outcome), context=context, evidence=outcome.evidence)


@pytest.mark.parametrize("seconds,allowed,permitted", [(20, True, True), (0.5, True, False), (20, False, False)])
def test_input_only_rewrite_does_not_forge_evidence_or_escape_budget(seconds, allowed, permitted):
    from intelligence.runtime.repair_budget import grant_for_delivery_repair
    from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
    from intelligence.services.research_contract import InMemoryRootBudgetLedger
    goal = RepairGoal("budget-d5", "bounded-rewrite", 1, ("answer_q2",), (), (), (), CoverageDelta(0, 0, 0), 0, seconds)
    ledger = InMemoryRootBudgetLedger(episode_id="budget-d5", initial_calls=0, hard_calls_cap=0, initial_seconds=0, hard_seconds_cap=seconds)
    ordinary = grant_for_delivery_repair(goal, root_budget=ledger, cycle_allowed=allowed, evidence_count=0)
    assert ordinary is None
    grant = grant_for_delivery_repair(goal, root_budget=ledger, cycle_allowed=allowed, evidence_count=0, input_only_rewrite=True)
    assert (grant is not None) is permitted
    if grant is not None:
        assert grant.calls_granted == 0 and 0 < grant.seconds_granted <= seconds
        assert grant_for_delivery_repair(goal, root_budget=ledger, cycle_allowed=allowed, evidence_count=0, input_only_rewrite=True) is None


@pytest.mark.parametrize("meta_prefix", ["", "原文未覆盖，"])
def test_judge_rejection_revokes_a_structurally_legal_gap(meta_prefix):
    frame, context = setup_delivery()
    gap = meta_prefix + GAP2
    original = outcome_for(context, all_gap=True)
    original = replace(original, draft=original.draft.replace(GAP2, gap),
                       bindings=(original.bindings[0], replace(original.bindings[1], gap=gap), original.bindings[2]))
    verified = verify_episode_outcome(context.contract, original)
    assert verified.missing_outputs == ()
    def judge(request):
        indexes = [row["index"] for row in request["sentences"] if "缺少乙" in row["text"]]
        assert len(indexes) == 1
        return {"passed": False, "rejected_sentence_indexes": indexes,
                "issues": [f"第{indexes[0]}句：缺失声明与材料不符。"]}
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(60),
    )
    assert result.judge_status == "rejected"
    assert result.repair_output_ids == ("answer_q2",)
    assert result.verified.missing_outputs == ("answer_q2",)
    assert {s.output_id: s.status for s in result.verified.completion.outputs}["answer_q2"] == "missing"
    assert gap not in result.public_answer
    assert GAP1 in result.public_answer
    assert not result.public_answer.startswith("仅凭本轮材料，以下各题均暂不能得出结论")
    assert result.sentence_verdicts[0]["decision"] == "deleted"
    assert repair_need(result.verified).shape.input_only_rewrite


def test_gap_rejection_mapping_uses_position_not_same_text_in_another_question():
    frame, context = setup_delivery()
    original = outcome_for(context, all_gap=True)
    original = replace(original, draft=f"## q1\n补充说明。\n{GAP1}\n## q2\n补充说明。\n{GAP2}{BOUNDARY}")
    def judge(request):
        indexes = [row["index"] for row in request["sentences"] if row["text"] == "补充说明。"]
        assert len(indexes) == 2
        return {"passed": False, "rejected_sentence_indexes": [indexes[1]],
                "issues": [f"第{indexes[1]}句：缺项判断无依据。"]}
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, original), deadline=ResearchDeadline.from_timeout(60),
    )
    assert result.verified.missing_outputs == ("answer_q2",)
    assert {s.output_id: s.status for s in result.verified.completion.outputs}["answer_q1"] == "legal_gap"


def test_material_rejection_does_not_renumber_peer_question_paragraphs():
    frame, context = setup_delivery()
    original = outcome_for(context, all_gap=True, draft=f"1.\n{GAP1}\n2.\n{GAP2}{BOUNDARY}")
    def judge(request):
        return {"passed": False, "rejected_sentence_indexes": [1], "issues": ["第1句：该题标题不当。"]}
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, original), deadline=ResearchDeadline.from_timeout(60),
    )
    assert "2." in result.public_answer
    assert result.verified.missing_outputs == ("answer_q1",)


def test_withheld_public_projection_cannot_retain_a_deleted_gap_status():
    frame, context = setup_delivery()
    original = outcome_for(context)
    gap = "缺少 d5-synthetic-structural-evidence 毛利率，无法计算新增利润。"
    original = replace(original, draft=original.draft.replace(GAP2, gap),
                       bindings=(original.bindings[0], replace(original.bindings[1], gap=gap), original.bindings[2]))
    verified = verify_episode_outcome(context.contract, original)
    verifier = SemanticEpisodeVerifier()
    result = verifier._emit_withheld_repair(
        frame, source=verified, rejected_sentence_indexes=(1,), judge_issues=(),
        correlated_judge=False, call=None, collapsed=True,
    )
    assert "answer_q2" in result.repair_output_ids
    assert "answer_q2" in result.verified.missing_outputs
    assert "d5-synthetic-structural-evidence" not in result.public_answer


def test_adapter_last_sanitizer_reopens_question_before_repair_and_never_publishes_settled(monkeypatch):
    from intelligence.runtime import continuous_turn_adapter as adapter_module
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession
    frame, context = setup_delivery()
    original = outcome_for(context, all_gap=True)
    resumes = []
    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                resumes.append(goal)
                assert goal.missing_answer_elements == ("answer_q2",)
                assert not goal.reopen_tools and goal.remaining_calls == 0
                return replace(original, events=(*previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=original, resume_callback=resume)
    sanitizer = adapter_module._safe_public_text
    monkeypatch.setattr(adapter_module, "_safe_public_text", lambda value, **kwargs: sanitizer(value, **kwargs).replace(GAP2, ""))
    result = adapter_module.ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=lambda _: {"passed": True, "rejected_sentence_indexes": [], "issues": []}),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert len(resumes) == 1, result.private_artifact
    assert "answer_q2" in result.private_artifact["semantic_verifier"]["repair_output_ids"]
    assert result.status != "completed"
    assert GAP2 not in result.answer
    assert not result.answer.startswith("仅凭本轮材料，以下各题均暂不能得出结论")


def test_judge_outage_does_not_turn_settled_questions_into_rewrite_work():
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession
    frame, context = setup_delivery()
    original = outcome_for(context, all_gap=True)
    resumes, requests = [], []
    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                resumes.append(goal)
                return replace(original, events=(*previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=original, resume_callback=resume)
    def judge(request):
        requests.append(request)
        raise ValueError("offline outage")
    result = ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert len(requests) == 1 and resumes == [], result.private_artifact
    assert result.private_artifact["semantic_verifier"]["pending_rejudge"] is True
    assert result.private_artifact["semantic_verifier"]["repair_output_ids"] == []
    assert result.status not in {"completed", "partial"}


def test_judge_rejected_gap_can_rewrite_without_tools_or_stale_revocation():
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession
    frame, context = setup_delivery()
    bad_gap = "缺少乙订单金额，无法判断升级条件。"
    good = outcome_for(context, all_gap=True)
    bad = replace(good, draft=good.draft.replace(GAP2, bad_gap),
                  bindings=(good.bindings[0], replace(good.bindings[1], gap=bad_gap), good.bindings[2]))
    resumes, requests = [], []
    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                resumes.append(goal)
                assert goal.missing_answer_elements == ("answer_q2",)
                assert goal.remaining_calls == 0 and not goal.reopen_tools
                return replace(good, events=(*previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=bad, resume_callback=resume)
    def judge(request):
        requests.append(request)
        rejected = [row["index"] for row in request["sentences"] if bad_gap in row["text"]]
        return {"passed": not rejected, "rejected_sentence_indexes": rejected,
                "issues": [f"第{index}句：材料已经给了金额。" for index in rejected]}
    result = ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert len(resumes) == 1 and len(requests) == 2, result.private_artifact
    assert result.status == "partial" and GAP2 in result.answer
    assert result.private_artifact["semantic_verifier"]["repair_output_ids"] == []


def test_dynamic_model_input_delivers_question_identity_gap_and_explicit_memo_rules():
    frame, context = setup_delivery(memo=True)
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    delivery = payload["material_delivery"]
    assert [(x["question_id"], x["output_id"]) for x in delivery["questions"]] == [("q1", "answer_q1"), ("q2", "answer_q2")]
    assert delivery["questions"][0]["delivery_kind"] == "answer"
    assert delivery["questions"][1]["delivery_kind"] == "memo"
    assert delivery["questions"][1]["max_chars"] == 200
    assert "legal_gap" in delivery["rules"] and "partial" in delivery["rules"]


# ── 2026-09-16 删保护变异后补的反例：四个仍绿的门各自要有一条独立承重的断言 ──


def test_question_copy_with_evidence_binding_is_still_not_an_answer():
    """带证据绑定的题正文只复述题干：不能靠邻近的「缺口须公开」检查兜底（那条只看带 gap 的题）。"""
    _, context = setup_delivery()
    outcome = outcome_for(context, draft=f"## q1\n甲新增利润是多少？\n\n## q2\n{GAP2}{BOUNDARY}")
    verified = verify_episode_outcome(context.contract, outcome)
    assert "answer_q1" in verified.missing_outputs
    assert {s.output_id: s.status for s in verified.completion.outputs}["answer_q1"] == "missing"
    with pytest.raises(ValueError):
        validate_episode_finish(finish_for(outcome), context=context, evidence=outcome.evidence)


def test_material_settlement_blocks_on_integrity_issue_or_mandatory_gap():
    """结清判定自己必须看 issue / mandatory；missing 被槽位状态吸收，这两项没有别的门。"""
    from intelligence.services.episode_issues import Issue, IssueCode
    from intelligence.services.episode_semantic_verifier import _material_questions_settled
    _, context = setup_delivery()
    verified = verify_episode_outcome(context.contract, outcome_for(context, all_gap=True))
    assert verified.missing_outputs == () and _material_questions_settled(verified)
    with_issue = replace(verified, issue_items=(Issue(IssueCode.REQUIRED_OUTPUT_GAP, "answer_q2", "synthetic"),))
    assert not _material_questions_settled(with_issue)
    with_capability = replace(verified, mandatory_missing_capabilities=("synthetic_capability",))
    assert not _material_questions_settled(with_capability)


def test_adapter_final_projection_downgrade_reaches_the_turn_status(monkeypatch):
    """最终投影（日历披露 / 公开告示）之后复验降级，公开 status 必须跟着降，不能沿用复验前的 completed。"""
    from intelligence.runtime import continuous_turn_adapter as adapter_module
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession
    frame, context = setup_delivery()
    original = outcome_for(context, status="completed")
    original = replace(original, draft=f"## q1\n甲订单占收入20%。\n## q2\n已按材料说明限制。{BOUNDARY}",
                       bindings=(answered_binding(context, "answer_q1", "甲订单占收入20%。"), answered_binding(context, "answer_q2", "已按材料说明限制。"), original.bindings[2]))
    resumes = []
    class Runtime:
        def start(self, _frame, *, context, registry):
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=original,
                                          resume_callback=lambda previous, goal: (resumes.append(goal), previous)[1])
    # 站在「最后一步公开变换」的位置：让它复制出第二个 q2 段，复验必须把 q2 打回并降级。
    monkeypatch.setattr(adapter_module, "_with_calendar_disclosure", lambda answer, frame: f"{answer}\n\n## q2\n（重复段）")
    result = adapter_module.ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=lambda _: {"passed": True, "rejected_sentence_indexes": [], "issues": []}),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert resumes == []
    assert "answer_q2" in result.private_artifact["semantic_verifier"]["repair_output_ids"]
    assert result.status == "partial"


def test_material_rejection_with_unmatched_sentence_coordinates_fails_closed():
    """判过的句子在稿里找不到坐标时，所有合法缺口一律重开，不猜归属。"""
    from intelligence.services import answer_model
    from intelligence.services.episode_semantic_verifier import _JudgeCall
    _, context = setup_delivery()
    verified = verify_episode_outcome(context.contract, outcome_for(context, all_gap=True))
    assert {s.status for s in verified.completion.outputs if s.output_id.startswith("answer_")} == {"legal_gap"}
    call = _JudgeCall(report=answer_model.GroundingJudgeReport(False, (0,), ("第0句：与材料不符。",)),
                      unavailable=False, correlated=False)
    result = SemanticEpisodeVerifier()._reject_material_gaps(
        verified, [{"index": 0, "text": "这句话不在被判的稿里。"}], call,
    )
    assert result is not None and result.judge_status == "rejected"
    # D6 cannot attribute a rejected sentence with broken coordinates to a clean
    # scope declaration either: all required owners must be re-established.
    assert set(result.verified.missing_outputs) == {"answer_q1", "answer_q2", "evidence_boundary"}
