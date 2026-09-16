"""Answer coverage and isolated nonfactual review, not live acceptance."""
from dataclasses import replace

import pytest

from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_semantic_verifier import recheck_material_public_delivery
from intelligence.services.material_grounding import ClaimSourceBinding
from intelligence.tests.material_judge_helpers import material_judge_report as reviewed
from intelligence.tests.test_e2_material_grounding import FACT, fact_claim, outcome, setup, verify

# Original c8 from run_20260916_211133_260447 at 01376610 (not a new sample).
UNBOUND_REPEAT = "比例12.5%是对材料内两个数字的直接算术结果，若两者口径或期间不一致，该比例需相应调整。"


def test_nonfactual_second_look_cannot_see_adjacent_calculation_or_catalogue():
    frame, context = setup()
    value = outcome(context)
    value = replace(value, draft=value.draft + "\n" + UNBOUND_REPEAT, bindings=(
        value.bindings[0], replace(value.bindings[1], claims=(ClaimSourceBinding(UNBOUND_REPEAT, "reasoning"),)),
    ))
    calls = []

    def judge(request):
        calls.append(request)
        if request.get("nonfactual_review"):
            assert "material_grounding" not in request and "material_delivery" not in request
            assert "material_outputs" not in request
            assert len(request["material_claims"]) == 1
            assert request["material_claims"][0]["text"] == UNBOUND_REPEAT
            assert FACT not in str(request)
            return reviewed(request, rejected=(request["sentences"][0]["index"],))
        return reviewed(request)

    result = verify(frame, context, value, judge)
    assert len(calls) == 2
    assert result.status != "completed" and UNBOUND_REPEAT not in result.public_answer
    assert result.material_nonfactual_checks
    assert len(result.to_dict()["material_review_calls"]) == 2


def test_nonfactual_second_look_outage_cannot_inherit_first_pass():
    frame, context = setup()
    text = "本答复只依据用户材料。"
    value = outcome(context)
    value = replace(value, draft=value.draft + "\n" + text, bindings=(
        value.bindings[0], replace(value.bindings[1], claims=(ClaimSourceBinding(text, "premise_declaration"),)),
    ))
    result = verify(frame, context, value, lambda request: {} if request.get("nonfactual_review") else reviewed(request))
    assert result.judge_status == "unavailable" and result.status != "completed"


def test_raw_facts_without_requested_result_reopen_answer_not_delete_facts():
    frame, context = setup()
    facts = "材料事实：甲收入100万元，新增订单20万元。"
    value = outcome(context, (fact_claim(context, facts),), text=facts)

    def judge(request):
        payload = reviewed(request)
        row = next(row for row in payload["material_output_checks"] if row["output_id"] == "answer_q1")
        row.update(answered=False, answer_sentence_indexes=[], reason="仅复述原始输入，没有回答所问的比例。")
        return payload

    result = verify(frame, context, value, judge)
    assert result.status == "partial" and result.judge_status == "rejected"
    assert "answer_q1" in result.verified.missing_outputs
    assert facts in result.public_answer
    assert result.material_output_checks[0]["answered"] is False


def test_projection_cannot_keep_completion_after_deleting_only_answer_witness():
    frame, context = setup()
    facts = "材料事实：甲收入100万元，新增订单20万元。"
    value = outcome(context, (fact_claim(context, facts), fact_claim(context)), text=facts + FACT)

    def judge(request):
        payload = reviewed(request)
        row = next(row for row in payload["material_output_checks"] if row["output_id"] == "answer_q1")
        row["answer_sentence_indexes"] = [next(s["index"] for s in request["sentences"] if s["text"] == FACT)]
        return payload

    good = verify(frame, context, value, judge)
    assert good.status == "completed"
    # A deletion stage also removes the deleted claim's binding. The remaining
    # raw facts are still structurally valid, but are no longer the answer.
    clean_bindings = (replace(good.verified.outcome.bindings[0], claims=(fact_claim(context, facts),)), good.verified.outcome.bindings[1])
    without_claim = replace(good, verified=replace(good.verified, outcome=replace(good.verified.outcome, bindings=clean_bindings)))
    projected = recheck_material_public_delivery(without_claim, projected=good.public_answer.replace(FACT, ""))
    assert projected.status == "partial" and "answer_q1" in projected.verified.missing_outputs
    assert facts in projected.public_answer
    assert recheck_material_public_delivery(projected, projected=good.public_answer).status == "partial"


def test_boundary_sentence_cannot_be_used_as_answer_witness():
    frame, context = setup()
    value = outcome(context)

    def judge(request):
        payload = reviewed(request)
        row = next(row for row in payload["material_output_checks"] if row["output_id"] == "answer_q1")
        row["answer_sentence_indexes"] = [request["sentences"][-1]["index"]]
        return payload

    result = verify(frame, context, value, judge)
    assert result.judge_status == "unavailable" and result.status != "completed"


def test_unnumbered_material_answer_also_needs_coverage_receipt():
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.query_understanding import understand_query

    frame = understand_query("只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？").task_frame
    context = build_episode_context(frame, task_id="unnumbered-answer-coverage")
    value = outcome(context)
    value = replace(value, draft=value.draft.removeprefix("## q1\n"), bindings=(
        OutputEvidenceBinding("direct_answer", (), claims=value.bindings[0].claims), value.bindings[1],
    ))
    seen = []

    def judge(request):
        seen.append(request)
        payload = reviewed(request)
        payload.pop("material_output_checks", None)
        return payload

    result = verify(frame, context, value, judge)
    assert seen and seen[0]["material_outputs"][0]["output_id"] == "direct_answer"
    assert result.status != "completed" and result.judge_status == "unavailable"


@pytest.mark.parametrize("mutation", ["missing", "empty", "duplicate", "foreign", "bool_index", "no_witness", "false_with_witness", "extra", "empty_reason"])
def test_malformed_output_receipt_is_unavailable(mutation):
    frame, context = setup()

    def judge(request):
        payload = reviewed(request)
        rows = payload["material_output_checks"]
        row = rows[0]
        if mutation == "missing":
            payload.pop("material_output_checks")
        elif mutation == "empty":
            rows.clear()
        elif mutation == "duplicate":
            rows.append(dict(row))
        elif mutation == "foreign":
            row["output_id"] = "foreign"
        elif mutation == "bool_index":
            row["answer_sentence_indexes"] = [True]
        elif mutation == "no_witness":
            row["answer_sentence_indexes"] = []
        elif mutation == "false_with_witness":
            row["answered"] = False
        elif mutation == "extra":
            row["unknown"] = True
        else:
            row["reason"] = " "
        return payload

    result = verify(frame, context, outcome(context), judge)
    assert result.status != "completed" and result.judge_status == "unavailable"


def test_isolated_review_uses_remaining_original_absolute_window(monkeypatch):
    from intelligence.services import episode_semantic_verifier as module

    frame, context = setup()
    text = "本答复只依据用户材料。"
    value = outcome(context)
    value = replace(value, draft=value.draft + "\n" + text, bindings=(
        value.bindings[0], replace(value.bindings[1], claims=(ClaimSourceBinding(text, "premise_declaration"),)),
    ))
    seen = []
    original = module.SemanticEpisodeVerifier._run_judge_once

    def record(self, request, deadline):
        seen.append(deadline.expires_at)
        return original(self, request, deadline)

    monkeypatch.setattr(module.SemanticEpisodeVerifier, "_run_judge_once", record)
    result = verify(frame, context, value, reviewed)
    assert result.status == "completed"
    assert len(seen) == 2 and seen[0] == seen[1]


@pytest.mark.parametrize("numbered", [True, False])
@pytest.mark.parametrize("repair_succeeds", [True, False])
def test_answer_coverage_reaches_real_adapter_and_input_only_repair(numbered, repair_succeeds):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.agent_runtime import EpisodeEvent
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.episode_session import CallbackEpisodeSession
    from intelligence.services.query_understanding import understand_query
    from intelligence.services.research_tool_registry import ResearchToolRegistry

    frame, context = setup()
    output_id = "answer_q1"
    if not numbered:
        frame = understand_query("只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？").task_frame
        context = build_episode_context(frame, task_id="coverage-adapter")
        output_id = "direct_answer"
    facts = "材料事实：甲收入100万元，新增订单20万元。"
    bad = outcome(context, (fact_claim(context, facts),), text=facts)
    good = outcome(context)
    if not numbered:
        def unnumber(value):
            return replace(value, draft=value.draft.removeprefix("## q1\n"), bindings=(
                replace(value.bindings[0], output_id=output_id), value.bindings[1],
            ))
        bad, good = unnumber(bad), unnumber(good)
    resumes = []

    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                resumes.append(goal)
                assert goal.missing_answer_elements == (output_id,)
                assert goal.remaining_calls == 0 and not goal.reopen_tools
                return replace(good if repair_succeeds else bad, events=(*previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=bad, resume_callback=resume)

    def judge(request):
        payload = reviewed(request)
        if not any(row["text"] == FACT for row in request["sentences"]):
            payload["material_output_checks"][0].update(answered=False, answer_sentence_indexes=[], reason="只有原始事实，未回答占比。")
        return payload

    result = ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert resumes
    assert (result.status == "completed") is repair_succeeds
    if repair_succeeds:
        assert FACT in result.answer
    else:
        assert facts in result.answer and FACT not in result.answer
        assert output_id in result.private_artifact["semantic_verifier"]["repair_output_ids"]
