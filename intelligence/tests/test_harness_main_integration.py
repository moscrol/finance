"""Mainline routing/material contracts composed with P1a/P1b, without live models."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from intelligence.services.episode_protocol import (
    EpisodeFinishRejection, build_episode_input, validate_episode_finish,
)
from intelligence.services.request_interpretation import TaskInterpretation
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import derive_required_outputs
from intelligence.services.turn_controller import TurnDecision, _rebase_frame_for_decision
from intelligence.tests.test_material_answer_authoring import history_setup, legacy_finish
from intelligence.tests.test_output_provenance import _frame


@pytest.mark.parametrize("origin,merged", [
    ("user_request", ()), ("method", ("method", "user_request")),
])
def test_quick_fact_rebase_retires_hints_but_preserves_current_user_obligations(origin, merged):
    user = RequiredOutput("counterpoint", "本轮明确要求", origin=origin, merged_origins=merged)
    hint = RequiredOutput("retired_hint", "非用户义务", required=False, origin="heuristic")
    frame = replace(
        _frame("counterpoint", "retired_hint", requirements=(user, hint)),
        raw_question="长电科技最新交易日的收盘价是多少？",
    )
    result = _rebase_frame_for_decision(frame, TurnDecision(
        lane="research", question_type="quick_fact", needs_retrieval=True,
        needs_memory=False, needs_template=False,
    ))
    assert result.required_outputs == (*derive_required_outputs("quick_fact", frame.raw_question), "counterpoint")
    assert result.output_requirements == (user,)
    assert result.material_contract is frame.material_contract
    assert result.raw_question == frame.raw_question


@pytest.mark.parametrize("new_type", ["quick_fact", "concept_definition"])
def test_route_change_rebases_outputs_and_metadata_from_the_same_current_turn(new_type):
    current_requirement = RequiredOutput("current_appendix", "本轮要求", origin="user_request")
    current = _frame("current_appendix", requirements=(current_requirement,))
    previous_hint = RequiredOutput("old_hint", "旧路由建议", required=False, origin="heuristic")
    inherited = replace(
        current, question_type="stock_deep_dive", subject="已确认主体",
        required_outputs=("current_appendix", "old_hint"),
        output_requirements=(current_requirement, previous_hint),
    )
    result = _rebase_frame_for_decision(
        inherited, TurnDecision(
            lane="research", question_type=new_type, needs_retrieval=True,
            needs_memory=False, needs_template=False,
        ), current_turn_frame=current,
    )
    assert result.subject == inherited.subject
    assert result.output_requirement("current_appendix") == current_requirement
    assert "current_appendix" in result.required_outputs
    assert "old_hint" not in result.required_outputs
    assert result.output_requirements == (current_requirement,)


@pytest.mark.parametrize("output_id", ["track_ttl", "ranking_matrix", "unrecognized_appendix"])
def test_frozen_material_binding_names_never_grant_template_repair_exemptions(output_id):
    _, context = history_setup()
    value = legacy_finish(context)
    # Keep all valid claims/draft, change only a binding identity after rendering.
    draft = validate_episode_finish(value, context=context, evidence=()).draft
    value.update(render_from_claims=False, draft=draft)
    value["bindings"][0]["output_id"] = output_id
    saved = deepcopy(value)
    with pytest.raises(EpisodeFinishRejection) as error:
        validate_episode_finish(value, context=context, evidence=())
    assert error.value.code == "unknown_output"
    assert error.value.kind.value == "integrity"
    assert value == saved


def test_material_compact_input_retains_frozen_request_and_interpretation():
    frame, context = history_setup()
    context = replace(context, interpretation=TaskInterpretation(
        context.root_request.to_dict()["request_ref"], 1, "回答完整原题", "只修订目标说明",
    ))
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    assert payload["material_grounding"]["finish_format"]["format"] == "material_claims_v1"
    assert payload["root_request"] == json.loads(json.dumps(context.root_request.to_dict()))
    assert payload["interpretation"] == context.interpretation.to_dict()
    assert payload["research_contract"]["allowed_capabilities"] == []
