"""Bounded recovery uses owned calculation inputs, never fabricated evidence."""

from dataclasses import replace
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.premise_financial_calculation import CALCULATION_MARKER
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_agent_episode import ScriptedModel
from intelligence.tests.test_premise_calculation import context_for, frame_for
from intelligence.tests.test_premise_financial_calculation import ARITHMETIC


def finish(context, draft, *, hashes=()):
    return ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": draft,
                "gaps": [],
                "bindings": [
                    {
                        "output_id": item.output_id,
                        "basis": item.grounding_mode,
                        "evidence_hashes": list(hashes),
                        "gap": "",
                    }
                    for item in context.contract.required_outputs
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def run_recovery(draft, *, hashes=()):
    frame = frame_for(ARITHMETIC)
    context = context_for(frame)
    bad = ModelTurn("not a JSON object", (), "scripted", "")
    model = ScriptedModel([bad, bad, finish(context, draft, hashes=hashes)])
    result = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=ResearchToolRegistry(()),
    )
    return context, model, result


def test_empty_evidence_calculation_recovers_once_with_owned_materials():
    context, model, result = run_recovery(
        CALCULATION_MARKER + "\n仍不足以判断股票便宜。"
    )
    assert len(model.calls) == 3
    assert result.status == "completed"
    assert result.stop_reason == "finalization_recovered"
    assert result.evidence == ()
    assert result.usage.tool_calls == 0
    assert result.usage.invalid_actions == 2
    assert context.contract.premise_calculation.table in result.draft
    call = model.calls[-1]
    assert call["tools"] == []
    payload = json.loads(call["messages"][-1]["content"])
    assert payload["evidence"] == []
    assert (
        payload["domain_materials"]["calculation_delivery"]
        == context.contract.premise_calculation.model_payload()
    )
    assert "not a JSON object" not in json.dumps(payload)
    assert (
        sum(event.kind == "finalization_recovery_started" for event in result.events)
        == 1
    )


@pytest.mark.parametrize(
    "draft,hashes",
    [
        (CALCULATION_MARKER + "\n静态市盈率22.5倍。", ()),
        (CALCULATION_MARKER, ("E999",)),
    ],
)
def test_recovery_does_not_relax_calculation_or_evidence_admission(draft, hashes):
    _, model, result = run_recovery(draft, hashes=hashes)
    assert len(model.calls) == 3
    assert result.status != "completed"
    assert result.stop_reason != "finalization_recovered"
    assert result.evidence == ()
    assert (
        sum(event.kind == "finalization_recovery_started" for event in result.events)
        == 1
    )
    assert "22.5倍" not in result.draft


def test_non_calculation_and_ambiguous_inputs_do_not_supply_recovery_materials():
    context = context_for(frame_for(ARITHMETIC))
    harness = FinanceResearchHarness()
    assert harness.finalization_materials(context=context)
    ordinary = replace(
        context, contract=replace(context.contract, premise_calculation=None)
    )
    assert harness.finalization_materials(context=ordinary) == {}
    incomplete = context_for(
        frame_for(ARITHMETIC.replace("归母净利润9亿元", "归母净利润九亿元"))
    )
    assert incomplete.contract.premise_calculation.issues
    assert harness.finalization_materials(context=incomplete) == {}


def test_owned_calculation_does_not_extend_expired_deadline():
    context = context_for(frame_for(ARITHMETIC))
    episode = ContinuousAgentEpisode(ScriptedModel([]))
    assert episode._can_recover_finalization(context=context, evidence=[])
    expired = replace(context, deadline=ResearchDeadline.from_timeout(0))
    assert not episode._can_recover_finalization(context=expired, evidence=[])


def test_fact_grounded_required_output_cannot_be_recovered_from_premises():
    context = context_for(frame_for(ARITHMETIC))
    outputs = tuple(
        replace(item, grounding_mode="evidence")
        for item in context.contract.required_outputs
    )
    context = replace(
        context, contract=replace(context.contract, required_outputs=outputs)
    )
    assert FinanceResearchHarness().finalization_materials(context=context) == {}
