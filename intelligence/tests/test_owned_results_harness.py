"""The actual shared projection, acknowledgement and finish admission seams."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest

from intelligence.services.episode_protocol import finish_json_schema
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.research_tool_registry import ToolRunResult, ToolSpec
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.owned_results import OwnedResultError
from intelligence.tests.owned_result_support import frame_context, source_fixture, finish_payload


def test_actual_projection_ack_and_same_finish_keep_false_plus_free_analysis():
    source = source_fixture()
    _, context = frame_context()
    harness = FinanceResearchHarness()
    projection = harness.project_tool_result(source, evidence_so_far=source.evidence, seen_prose=set())
    facing = json.loads(projection.model_content)
    assert facing["query_basis"] == source.query_basis
    view = facing["owned_results"]
    part = next(item for item in view["parts"] if "医药生物主题中的免疫治疗" in item["text"])
    assert "不满足严格双红" in part["text"]
    assert "source_digest" not in projection.model_content and "draft_sha256" not in projection.model_content
    assert "answer_parts" in finish_json_schema()["properties"]
    payload = finish_payload([{"result_ref": part["result_ref"]}, "这是后续待验证的研判。"])
    before = harness.admit_finish(payload, context=context, evidence=source.evidence, registry=ResearchToolRegistry(()))
    assert not before.accepted  # Projection alone grants no authority.
    harness.acknowledge_tool_result(source, projection, context=context)
    admission = harness.admit_finish(payload, context=context, evidence=source.evidence, registry=ResearchToolRegistry(()))
    assert admission.accepted, admission.reason
    assert admission.owned_answer is not None
    assert admission.owned_answer["free_blocks"] == 1
    assert "不满足严格双红" in admission.draft
    assert admission.draft.endswith("这是后续待验证的研判。")


def _delivered():
    source, harness = source_fixture(), FinanceResearchHarness()
    _, context = frame_context()
    projection = harness.project_tool_result(source, evidence_so_far=source.evidence, seen_prose=set())
    harness.acknowledge_tool_result(source, projection, context=context)
    ref = next(p["result_ref"] for p in json.loads(projection.model_content)["owned_results"]["parts"]
               if "医药生物主题中的免疫治疗" in p["text"])
    return source, context, harness, ref


@pytest.mark.parametrize("change", [
    lambda p: p.update(draft="second draft"),
    lambda p: p.update(render_from_claims=True),
    lambda p: p.update(owned_answer={"draft_sha256": "forged"}),
    lambda p: p["answer_parts"][0].update(value=True),
    lambda p: p["bindings"][0].update(evidence_hashes=["E999"]),
    lambda p: p.update(bindings=[]),
])
def test_parts_keep_the_original_contract_checks_and_one_body_generator(change):
    source, context, harness, ref = _delivered()
    payload = finish_payload([{"result_ref": ref}])
    change(payload)
    result = harness.admit_finish(payload, context=context, evidence=source.evidence, registry=ResearchToolRegistry(()))
    assert not result.accepted
    assert result.owned_answer is None


def test_context_permissions_are_rechecked_and_sources_do_not_follow_another_run():
    source, context, harness, ref = _delivered()
    payload = finish_payload([{"result_ref": ref}])
    for changed in (
        replace(context, information_cutoff=InformationCutoff(date(2026, 9, 29), "requested")),
        replace(context, contract=replace(context.contract, allowed_capabilities=())),
        replace(context, contract=replace(context.contract, task_id="another-run")),
    ):
        assert not harness.admit_finish(payload, context=changed, evidence=source.evidence,
                                        registry=ResearchToolRegistry(())).accepted
    # An alleged same source with changed inputs cannot replace its delivered identity.
    basis = deepcopy(source.query_basis)
    row = next(r for r in basis["price_volume_signals"] if r["sector_ts_code"] == "990080.FP")
    row.update(sector_amount=501, strict_double_red=True)
    changed = replace(source, query_basis=basis)
    projection = harness.project_tool_result(changed, evidence_so_far=source.evidence, seen_prose=set())
    with pytest.raises(OwnedResultError, match="same_source_input_conflict"):
        harness.acknowledge_tool_result(changed, projection, context=context)
    assert harness.admit_finish(payload, context=context, evidence=source.evidence,
                                registry=ResearchToolRegistry(())).accepted


def test_real_registry_temporal_filter_cannot_regrant_raw_signals_in_projection_or_ack():
    source = source_fixture()
    _, context = frame_context()
    context = replace(context, information_cutoff=InformationCutoff(date(2026, 9, 29), "requested"))

    def runner(_query, _tool_context):
        return ToolRunResult(evidence=source.evidence, observation=source.observation,
                             trace=source.trace, dataset=source.dataset, query_basis=source.query_basis)

    registry = ResearchToolRegistry((ToolSpec(
        "mainline_context", "mainline_context", "同日板块行情", "local", "current", runner,
        io_effect="local_read",
    ),))
    filtered = registry.execute("mainline_context", {"query": "同日行情"}, context=context, step_id="filtered")
    assert not filtered.evidence
    assert not filtered.query_basis
    harness = FinanceResearchHarness()
    projection = harness.project_tool_result(filtered, evidence_so_far=(), seen_prose=set())
    assert "owned_results" not in json.loads(projection.model_content)
    harness.acknowledge_tool_result(filtered, projection, context=context)
    assert not context._owned_result_sources


def test_legacy_none_and_literal_newlines_keep_their_bytes():
    source, context, harness, ref = _delivered()
    old = finish_payload(draft="免疫治疗同样双红确认。")
    with_none = {**old, "answer_parts": None}
    a = harness.admit_finish(old, context=context, evidence=source.evidence, registry=ResearchToolRegistry(()))
    b = harness.admit_finish(with_none, context=context, evidence=source.evidence, registry=ResearchToolRegistry(()))
    assert a == b and a.draft == old["draft"] and a.owned_answer is None
    parts = finish_payload([{"result_ref": ref}, "下一段\\n自由分析。"])
    result = harness.admit_finish(parts, context=context, evidence=source.evidence, registry=ResearchToolRegistry(()))
    assert result.accepted and result.draft.endswith("下一段\n自由分析。")
    from hashlib import sha256
    assert result.owned_answer["draft_sha256"] == sha256(result.draft.encode()).hexdigest()


def test_closed_part_schema_is_optional_and_cannot_accept_author_values():
    schema = finish_json_schema()
    assert "answer_parts" not in schema["required"]
    part = schema["properties"]["answer_parts"]["items"]["anyOf"][1]
    assert part["additionalProperties"] is False and set(part["properties"]) == {"result_ref"}


def test_material_author_schema_is_unchanged_and_parts_cannot_bypass_its_body_owner():
    from intelligence.services.conversation_materials import ConversationMaterials, HistoricalAssistantStatement
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.material_answer_authoring import material_author_schema
    from intelligence.services.turn_controller import decide_turn

    frame = decide_turn("不重新查询。请复述你上一条的判断。", conversation_materials=ConversationMaterials(
        assistant_statements=(HistoricalAssistantStatement("assistant-old", "上一条收盘价为68.78元。"),),
    )).task_frame
    context = build_episode_context(frame, task_id="owned-material-control")
    assert finish_json_schema(context.contract) == material_author_schema(context.contract)
    assert "answer_parts" not in finish_json_schema(context.contract)["properties"]
    result = FinanceResearchHarness().admit_finish(finish_payload(["自由文字"]), context=context,
                                                 evidence=(), registry=ResearchToolRegistry(()))
    assert not result.accepted and "material authoring" in result.reason
