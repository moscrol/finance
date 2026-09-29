"""Quote correction must not admit a bad source or buy a new research budget."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.episode_protocol import validate_episode_finish
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_material_answer_authoring import compact_finish, history_setup, legacy_finish


def payload(context, protocol, source):
    value = compact_finish() if protocol == "compact" else legacy_finish(context)
    row = 0 if source == "history" else 1
    claim = value["answers" if protocol == "compact" else "bindings"][row]["claims"][0]
    if protocol == "compact":
        claim["sources"][0]["quote"] = "不存在的摘录，不得原样回显"
    elif source == "history":
        claim["historical_quote"] = "不存在的摘录，不得原样回显"
    else:
        claim["material_anchors"][0]["quote"] = "不存在的摘录，不得原样回显"
    return value


class Writer:
    def __init__(self, turns):
        self.turns = turns
        self.calls = []

    def complete(self, *, messages, tools, timeout):
        assert tools == [] and timeout > 0
        self.calls.append(deepcopy(messages))
        return ModelTurn(json.dumps(self.turns[min(len(self.calls), len(self.turns)) - 1], ensure_ascii=False), (), "offline")


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
@pytest.mark.parametrize("protocol", ["compact", "legacy"])
@pytest.mark.parametrize("source", ["history", "material"])
def test_known_source_quote_correction_revalidates_same_contract(loop, protocol, source):
    frame, context = history_setup()
    original = context.contract.to_dict()
    policy, deadline = context.policy, context.deadline
    good = compact_finish() if protocol == "compact" else legacy_finish(context)
    bad = payload(context, protocol, source)
    saved = deepcopy(bad)
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "material_quote_mismatch"
    assert "不存在的摘录" not in str(error.value)
    assert "逐字复制连续片段" in str(error.value)
    assert "claims[0]" in str(error.value)
    writer = Writer([bad, good])
    result = loop(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    expected = validate_episode_finish(good, context=context, evidence=())
    assert result.status == "completed" and result.draft == expected.draft
    assert result.bindings == expected.bindings
    assert len(writer.calls) == result.usage.llm_calls == 2
    assert result.usage.tool_calls == 0 and result.evidence == ()
    assert result.usage.invalid_actions == 1
    assert "逐字复制连续片段" in writer.calls[1][-1]["content"]
    assert context.contract.to_dict() == original
    assert context.policy is policy and context.deadline is deadline and bad == saved
    invalid = [e.payload for e in result.events if e.kind == "invalid_action"]
    assert [item["code"] for item in invalid] == ["material_quote_mismatch"]


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
@pytest.mark.parametrize("protocol", ["compact", "legacy"])
def test_repeated_quote_errors_are_bounded_and_never_published(loop, protocol):
    frame, context = history_setup()
    bad = payload(context, protocol, "history")
    writer = Writer([bad])
    result = loop(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert result.status != "completed"
    # Existing no-tool finalization may follow the one in-loop correction.
    assert 1 < len(writer.calls) <= 3
    assert result.usage.tool_calls == 0 and result.bindings == ()
    assert "68.78" not in result.draft
    assert all(e.payload.get("rejection_code") != "none" for e in result.events if e.kind == "finish")


@pytest.mark.parametrize("protocol", ["compact", "legacy"])
@pytest.mark.parametrize("mutation", ["unknown_material", "wrong_class", "unknown_history", "outside_scope"])
def test_quote_error_cannot_mask_source_integrity_violation(protocol, mutation):
    frame, context = history_setup()
    bad = payload(context, protocol, "history")
    rows = bad["answers" if protocol == "compact" else "bindings"]
    # Put the identity violation after the known-source typo to exercise ordering.
    claim = rows[1]["claims"][0]
    if protocol == "compact":
        if mutation == "outside_scope":
            claim["sources"][0]["ref"] = "E9"
        elif mutation == "unknown_history":
            claim.update(kind="historical_assistant_statement", sources=[{"ref": "H999", "quote": "无"}])
        else:
            claim["sources"][0]["ref"] = "M999" if mutation == "unknown_material" else "H1"
    else:
        if mutation == "outside_scope":
            rows[1]["evidence_hashes"] = ["a" * 64]
        elif mutation == "unknown_history":
            rows[1]["claims"] = [{"text": claim["text"], "kind": "historical_assistant_statement",
                                  "basis": "assistant_judgment", "old_answer_coordinate": "unknown",
                                  "historical_quote": "无"}]
        else:
            claim["material_anchors"][0]["material_id"] = "unknown" if mutation == "unknown_material" else "assistant-old"
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "material_source_violation" and error.value.kind.value == "integrity"
    writer = Writer([bad])
    result = ContinuousAgentEpisode(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert len(writer.calls) == 1 and result.status != "completed"
    assert result.usage.tool_calls == 0


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
def test_quote_repair_does_not_ignore_cancellation(loop):
    frame, context = history_setup()
    writer = Writer([payload(context, "compact", "material")])
    result = loop(writer, is_cancelled=lambda: bool(writer.calls)).run(
        task_frame=frame, context=context, registry=ResearchToolRegistry(()),
    )
    assert len(writer.calls) == 1 and result.stop_reason == "cancelled"
    assert result.usage.tool_calls == 0


@pytest.mark.parametrize("protocol", ["compact", "legacy"])
def test_production_quote_repair_cannot_extend_absolute_deadline(monkeypatch, protocol):
    frame, context = history_setup()
    now = [100.0]
    monkeypatch.setattr("intelligence.services.research_contract.time.monotonic", lambda: now[0])
    context = replace(context, deadline=ResearchDeadline(110.0))
    good = compact_finish() if protocol == "compact" else legacy_finish(context)

    class SlowWriter(Writer):
        def complete(self, **kwargs):
            turn = super().complete(**kwargs)
            now[0] = 111.0
            return turn

    writer = SlowWriter([payload(context, protocol, "material"), good])
    result = ContinuousAgentEpisode(writer).run(
        task_frame=frame, context=context, registry=ResearchToolRegistry(()),
    )
    assert len(writer.calls) == 1 and result.status != "completed"
    assert result.usage.tool_calls == 0 and result.bindings == ()
    assert context.deadline.expires_at == 110.0


@pytest.mark.parametrize("protocol", ["compact", "legacy"])
def test_read_side_still_rejects_known_source_with_wrong_quote(protocol):
    from intelligence.services.agent_runtime import OutputEvidenceBinding
    from intelligence.services.material_answer_authoring import compile_material_author_finish
    from intelligence.services.material_grounding import (
        ClaimSourceBinding, binding_source_errors, claim_binding_error, historical_claim_texts,
    )

    _, context = history_setup()
    raw = compile_material_author_finish(payload(context, protocol, "history"), context.contract)
    binding = OutputEvidenceBinding(
        output_id="direct_answer", evidence_hashes=(),
        claims=tuple(ClaimSourceBinding.from_dict(c) for c in raw["bindings"][0]["claims"]),
    )
    draft = binding.claims[0].text
    assert claim_binding_error(context.contract, binding.claims[0], draft)
    assert binding_source_errors(context.contract, binding, draft, ())
    assert historical_claim_texts(context.contract, (binding,), draft) == frozenset()


@pytest.mark.parametrize("protocol", ["compact", "legacy"])
def test_quote_error_cannot_mask_unknown_anchor_in_same_claim(protocol):
    _, context = history_setup()
    bad = payload(context, protocol, "material")
    claim = bad["answers" if protocol == "compact" else "bindings"][1]["claims"][0]
    if protocol == "compact":
        claim["sources"].append({"ref": "M999", "quote": "无"})
    else:
        claim["material_anchors"].append({"material_id": "unknown", "quote": "无"})
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "material_source_violation" and error.value.kind.value == "integrity"


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("mutation", ["unknown_ordinal", "basis_and_unknown_material", "basis_and_wrong_scope"])
def test_whole_finish_source_integrity_precedes_recoverable_binding_errors(loop, reverse, mutation):
    frame, context = history_setup()
    bad = payload(context, "legacy", "history")
    if mutation == "unknown_ordinal":
        bad["bindings"][1]["evidence_hashes"] = ["E9"]
    else:
        # A valid quote plus an early basis slip must not mask a later bad source
        # either. Identity, not binding order, decides whether repair is allowed.
        bad = legacy_finish(context)
        bad["bindings"][0]["basis"] = "model_reasoning"
        if mutation == "basis_and_unknown_material":
            bad["bindings"][1]["claims"][0]["material_anchors"][0]["material_id"] = "unknown"
        else:
            bad["bindings"][1]["evidence_hashes"] = ["a" * 64]
    if reverse:
        bad["bindings"].reverse()
    saved = deepcopy(bad)
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "material_source_violation" and error.value.kind.value == "integrity"
    assert "不存在的摘录" not in str(error.value)
    writer = Writer([bad, legacy_finish(context)])
    result = loop(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert len(writer.calls) == 1 and result.status != "completed"
    assert result.usage.tool_calls == 0 and result.bindings == ()
    assert bad == saved


def test_quote_feedback_lists_multiple_locations_with_bounded_size():
    _, context = history_setup()
    bad = payload(context, "compact", "material")
    bad["answers"][1]["claims"] *= 20
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "material_quote_mismatch"
    assert "claims[0]" in str(error.value) and "claims[15]" in str(error.value)
    assert "claims[16]" not in str(error.value) and "4 further quote mismatches" in str(error.value)
    assert "不存在的摘录" not in str(error.value)


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("source_error", ["forged_material", "quote_mismatch"])
@pytest.mark.parametrize("empty_ref", [None, "", " "])
def test_unresolved_ordinal_cannot_create_empty_binding_that_masks_source_error(loop, reverse, source_error, empty_ref):
    frame, context = history_setup()
    good = legacy_finish(context)
    bad = deepcopy(good)
    bad.update(render_from_claims=False, draft=validate_episode_finish(good, context=context, evidence=()).draft)
    bad["bindings"][0].update(claims=[], evidence_hashes=["E9"] + ([empty_ref] if empty_ref is not None else []))
    anchor = bad["bindings"][1]["claims"][0]["material_anchors"][0]
    if source_error == "forged_material":
        anchor["material_id"] = "forged-material"
    else:
        anchor["quote"] = "不存在的摘录，不得原样回显"
    if reverse:
        bad["bindings"].reverse()
    saved = deepcopy(bad)
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "material_source_violation"
    assert error.value.kind.value == "integrity"
    writer = Writer([bad, good])
    result = loop(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert len(writer.calls) == 1 and result.status != "completed" and result.bindings == ()
    assert result.usage.tool_calls == 0 and bad == saved


@pytest.mark.parametrize("scope", ["material_only", "local_only"])
def test_standalone_unresolved_ordinal_keeps_typed_rejection_without_fabricating_gap(scope):
    _, context = history_setup()
    bad = legacy_finish(context)
    draft = validate_episode_finish(bad, context=context, evidence=()).draft
    context = replace(context, contract=replace(
        context.contract, material_contract=replace(context.contract.material_contract, data_scope=scope),
    ))
    bad.update(render_from_claims=False, draft=draft)
    bad["bindings"][0].update(claims=[], evidence_hashes=["E9"])
    saved = deepcopy(bad)
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "unknown_evidence_ref" and error.value.kind.value == "format"
    assert bad == saved


def multiple_history_excerpts():
    bad = compact_finish()
    bad["answers"][0]["claims"][0]["sources"].append({"ref": "H1", "quote": "日期为2026-09-24"})
    return bad


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
def test_multiple_excerpts_of_same_history_message_can_be_rewritten_in_existing_budget(loop):
    frame, context = history_setup()
    bad, good = multiple_history_excerpts(), compact_finish()
    saved = deepcopy(bad)
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "historical_excerpt_shape" and error.value.kind.value == "format"
    assert "拆" in str(error.value) and "2026-09-24" not in str(error.value)
    writer = Writer([bad, good])
    result = loop(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    expected = validate_episode_finish(good, context=context, evidence=())
    assert len(writer.calls) == 2 and result.status == "completed"
    assert result.bindings == expected.bindings and result.draft == expected.draft
    assert result.usage.tool_calls == 0 and result.usage.invalid_actions == 1 and bad == saved


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("mutation", ["unknown_history", "wrong_class", "later_unknown_material", "unbound_fact", "different_history"])
def test_multiple_history_excerpts_do_not_hide_forged_or_mixed_source_identities(reverse, mutation):
    from intelligence.services.conversation_materials import HistoricalAssistantStatement

    _, context = history_setup()
    bad = multiple_history_excerpts()
    claim = bad["answers"][0]["claims"][0]
    if mutation == "different_history":
        catalogue = context.contract.material_grounding
        context = replace(context, contract=replace(context.contract, material_grounding=replace(
            catalogue, historical_assistant_statements=(*catalogue.historical_assistant_statements,
                HistoricalAssistantStatement("another-old-answer", "日期为2026-09-24")),
        )))
        claim["sources"][1]["ref"] = "H2"
    elif mutation == "later_unknown_material":
        bad["answers"][1]["claims"][0]["sources"][0]["ref"] = "M999"
    elif mutation == "unbound_fact":
        bad["answers"][1]["claims"][0].update(kind="material_fact", sources=[])
    else:
        claim["sources"][1]["ref"] = "H999" if mutation == "unknown_history" else "M1"
    if reverse:
        bad["answers"].reverse()
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "material_source_violation" and error.value.kind.value == "integrity"


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
def test_repeated_same_history_excerpt_shape_never_publishes_or_extends_budget(loop):
    frame, context = history_setup()
    writer = Writer([multiple_history_excerpts()])
    result = loop(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert 1 < len(writer.calls) <= 3
    assert result.status != "completed" and result.bindings == () and result.usage.tool_calls == 0


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
def test_same_history_excerpt_shape_respects_cancellation(loop):
    frame, context = history_setup()
    writer = Writer([multiple_history_excerpts(), compact_finish()])
    result = loop(writer, is_cancelled=lambda: bool(writer.calls)).run(
        task_frame=frame, context=context, registry=ResearchToolRegistry(()),
    )
    assert len(writer.calls) == 1 and result.stop_reason == "cancelled" and result.usage.tool_calls == 0


def test_same_history_excerpt_shape_cannot_extend_deadline(monkeypatch):
    frame, context = history_setup()
    now = [100.0]
    monkeypatch.setattr("intelligence.services.research_contract.time.monotonic", lambda: now[0])
    context = replace(context, deadline=ResearchDeadline(110.0))

    class SlowWriter(Writer):
        def complete(self, **kwargs):
            turn = super().complete(**kwargs)
            now[0] = 111.0
            return turn

    writer = SlowWriter([multiple_history_excerpts(), compact_finish()])
    result = ContinuousAgentEpisode(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert len(writer.calls) == 1 and result.status != "completed" and result.bindings == ()
    assert result.usage.tool_calls == 0 and context.deadline.expires_at == 110.0
