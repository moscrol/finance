"""The author contract compiles a body without admitting its evidence or status."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date
from hashlib import sha256
import json

from jsonschema import Draft202012Validator
import pytest

from intelligence.services.episode_protocol import finish_json_schema, validate_episode_finish
from intelligence.services.finish_authoring import (
    FinishAuthoringError, compile_finish_authoring, finish_author_contract,
)
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.owned_result_support import finish_payload, frame_context, source_fixture
from intelligence.tests.test_material_answer_authoring import compact_finish, history_setup, legacy_finish

def test_ordinary_contract_and_free_parts_compile_without_an_ownership_grant():
    _, context = frame_context()
    author = finish_author_contract(context)
    assert author.model_payload["format"] == "ordinary_answer_parts_v1"
    template = json.loads(author.model_payload["wire_template"])
    assert template["draft"] == "" and template["answer_parts"] == []
    assert "format" not in template
    compiled = compile_finish_authoring({
        "status": "partial", "draft": "", "answer_parts": ["原正文。"],
        "gaps": ["仍缺明确数据。"], "bindings": [],
    }, context=context)
    assert compiled.envelope["draft"] == "原正文。"
    assert compiled.envelope["status"] == "partial"
    assert tuple(compiled.envelope["gaps"]) == ("仍缺明确数据。",)
    assert compiled.owned_answer is None and not compiled.claim_origins


def test_context_free_schema_keeps_its_exact_original_bytes():
    encoded = json.dumps(finish_json_schema(), ensure_ascii=False, separators=(",", ":")).encode()
    assert sha256(encoded).hexdigest() == "b7c73b5802b936f0b0d678d8fc42f221e42a7261d1d2f94559a72cd92c390cd7"
    _, context = frame_context()
    assert finish_json_schema(context.contract) == finish_json_schema()
    assert finish_json_schema(context=context) == finish_author_contract(context).schema_payload()


@pytest.mark.parametrize("body", [
    {"draft": "", "answer_parts": []},
    {"draft": "", "answer_parts": ["自由正文。"]},
    {"draft": "", "answer_parts": [{"result_ref": "opaque-ref"}], "render_from_claims": False},
    {"draft": "原正文。"},
    {"draft": "原正文。", "answer_parts": None},
    {"draft": "原正文。", "answer_parts": None, "render_from_claims": False},
    {"draft": "", "render_from_claims": True},
    {"draft": "", "answer_parts": None, "render_from_claims": True},
])
def test_closed_live_schema_accepts_one_body_owner_and_legacy_none(body):
    _, context = frame_context()
    validator = Draft202012Validator(finish_author_contract(context).schema_payload())
    validator.validate({"status": "partial", "gaps": [], "bindings": [], **body})


@pytest.mark.parametrize("body", [
    {"draft": "第二正文。", "answer_parts": ["正文。"]},
    {"draft": "", "answer_parts": [], "render_from_claims": True},
    {"draft": "第二正文。", "render_from_claims": True},
    {"draft": "", "answer_parts": "正文。"},
    {"draft": "", "answer_parts": [{"result_ref": "ref", "value": True}]},
    {"draft": "", "answer_parts": [{"result_ref": "ref", "text": "作者改写。"}]},
    {"draft": "", "answer_parts": [{"result_ref": 1}]},
    {"draft": "", "answer_parts": [], "format": "ordinary_answer_parts_v1"},
    {"draft": "", "answer_parts": [], "owned_answer": {}},
    {"draft": "", "answer_parts": [], "render_from_claims": None},
])
def test_closed_live_schema_rejects_mixed_or_author_owned_fields(body):
    _, context = frame_context()
    validator = Draft202012Validator(finish_author_contract(context).schema_payload())
    assert not validator.is_valid({"status": "partial", "gaps": [], "bindings": [], **body})


def _projected():
    source, harness = source_fixture(), FinanceResearchHarness()
    _, context = frame_context()
    projection = harness.project_tool_result(source, evidence_so_far=source.evidence, seen_prose=set())
    view = json.loads(projection.model_content)["owned_results"]["parts"]
    return source, context, harness, projection, view


def _delivered():
    source, context, harness, projection, view = _projected()
    harness.acknowledge_tool_result(source, projection, context=context)
    return source, context, harness, view


def test_schema_and_display_copies_do_not_grant_refs_before_actual_ack():
    source, context, harness, projection, view = _projected()
    author = finish_author_contract(context)
    assert not context._owned_result_sources
    payload = finish_payload([{"result_ref": view[0]["result_ref"]}], source=source)
    with pytest.raises(FinishAuthoringError, match="unknown_result_ref"):
        compile_finish_authoring(payload, context=context)
    copy = author.schema_payload()
    copy["oneOf"].clear()
    assert len(author.schema_payload()["oneOf"]) == 3
    author.prompt_payload()["format"] = "a-display-copy"
    harness.acknowledge_tool_result(source, projection, context=context)
    compiled = compile_finish_authoring(payload, context=context)
    assert compiled.envelope["draft"] == view[0]["text"]
    assert compiled.owned_answer["qualification"] == "owned"
    assert author.model_payload["format"] == "ordinary_answer_parts_v1"


def test_author_and_compiled_products_are_detached_and_deeply_immutable():
    source, context, _, view = _delivered()
    author = finish_author_contract(context)
    with pytest.raises(TypeError):
        author.json_schema["properties"]["draft"]["type"] = "null"
    with pytest.raises(TypeError):
        author.model_payload["format"] = "forged"
    with pytest.raises(FrozenInstanceError):
        author.model_payload = {}
    raw = finish_payload([{"result_ref": view[0]["result_ref"]}, "后续分析。"], source=source)
    original = deepcopy(raw)
    compiled = compile_finish_authoring(raw, context=context)
    assert raw == original
    raw["bindings"][0]["evidence_hashes"].clear()
    raw["answer_parts"][0]["result_ref"] = "forged"
    with pytest.raises(TypeError):
        compiled.envelope["answer_parts"][0]["result_ref"] = "forged"
    with pytest.raises(TypeError):
        compiled.owned_answer["owned_blocks"][0]["text"] = "forged"
    body_copy = compiled.envelope_payload()
    body_copy["bindings"][0]["evidence_hashes"].clear()
    receipt_copy = compiled.owned_answer_payload()
    receipt_copy["parts"].clear()
    assert compiled.envelope_payload()["bindings"] == original["bindings"]
    assert compiled.owned_answer_payload()["parts"] == original["answer_parts"]


def test_ref_subset_order_and_zero_selection_preserve_the_authors_choices():
    source, context, _, view = _delivered()
    selected = [view[-1], view[0]]
    raw = finish_payload([{"result_ref": p["result_ref"]} for p in selected], source=source)
    compiled = compile_finish_authoring(raw, context=context)
    assert compiled.envelope["draft"] == "\n\n".join(p["text"] for p in selected)
    assert [p["result_ref"] for p in compiled.owned_answer["owned_blocks"]] == [p["result_ref"] for p in selected]
    for parts, expected in (([], ""), (["自由正文。"], "自由正文。")):
        compiled = compile_finish_authoring({
            "status": "partial", "draft": "", "answer_parts": parts, "gaps": [], "bindings": [],
        }, context=context)
        assert compiled.envelope["draft"] == expected and compiled.owned_answer is None


@pytest.mark.parametrize("changed,reason", [
    (lambda c: replace(c, contract=replace(c.contract, allowed_capabilities=())), "source_not_authorized"),
    (lambda c: replace(c, information_cutoff=InformationCutoff(date(2026, 9, 29), "requested")), "source_after_cutoff"),
    (lambda c: replace(c, trace_parent_id="another-owner"), "unknown_result_ref"),
    (lambda c: replace(c, _owned_result_sources=[]), "unknown_result_ref"),
])
def test_compilation_rechecks_current_context_instead_of_the_old_author_description(changed, reason):
    source, context, _, view = _delivered()
    author = finish_author_contract(context)
    payload = finish_payload([{"result_ref": view[0]["result_ref"]}], source=source)
    assert compile_finish_authoring(payload, context=context).owned_answer is not None
    with pytest.raises(FinishAuthoringError, match=reason):
        compile_finish_authoring(payload, context=changed(context))
    assert author.model_payload["format"] == "ordinary_answer_parts_v1"


@pytest.mark.parametrize("mutate,reason", [
    (lambda b: b.update(schema="unsupported"), "unknown_result_ref"),
    (lambda b: b.update(market_date="2026-09-29"), "source_date_conflict"),
    (lambda b: b["metric_semantics"].update(sector_amount="元"), "source_definition_conflict"),
])
def test_cached_sources_are_recompiled_before_ref_selection(mutate, reason):
    source, context, _, view = _delivered()
    payload = finish_payload([{"result_ref": view[0]["result_ref"]}], source=source)
    finish_author_contract(context)
    mutate(context._owned_result_sources[0].observation.query_basis)
    with pytest.raises(FinishAuthoringError, match=reason):
        compile_finish_authoring(payload, context=context)


def test_old_draft_and_none_keep_body_bindings_and_no_receipt_even_with_a_catalogue():
    source, context, harness, _ = _delivered()
    old = finish_payload(draft="免疫治疗同样双红确认。", source=source)
    with_none = {**old, "answer_parts": None}
    a = compile_finish_authoring(old, context=context)
    b = compile_finish_authoring(with_none, context=context)
    assert a.envelope_payload() == old and b.envelope_payload() == with_none
    assert a.owned_answer is None and b.owned_answer is None
    left = harness.admit_finish(old, context=context, evidence=source.evidence, registry=ResearchToolRegistry(()))
    right = harness.admit_finish(with_none, context=context, evidence=source.evidence, registry=ResearchToolRegistry(()))
    assert left == right and left.draft == old["draft"] and left.owned_answer is None


def test_compiling_a_completed_body_does_not_bypass_required_bindings_or_evidence():
    _, context = frame_context()
    raw = {"status": "completed", "draft": "", "answer_parts": ["原正文。"], "gaps": [], "bindings": []}
    compiled = compile_finish_authoring(raw, context=context)
    assert compiled.envelope["status"] == "completed" and compiled.owned_answer is None
    admission = FinanceResearchHarness().admit_finish(raw, context=context, evidence=(), registry=ResearchToolRegistry(()))
    assert not admission.accepted and admission.owned_answer is None


@pytest.mark.parametrize("extra,code,phrase", [
    ({"owned_answer": {}, "status": "bad", "draft": 3}, "bad_claim_binding", "program-owned"),
    ({"answer_parts": [], "render_from_claims": True, "status": "bad"}, "bad_claim_binding", "cannot mix"),
    ({"format": "unknown", "status": "bad"}, "bad_claim_binding", "unsupported author format"),
    ({"status": "bad", "draft": 3, "answer_parts": 3}, "bad_status", "completed or partial"),
    ({"draft": 3, "answer_parts": 3}, "draft_not_string", "must be a string"),
    ({"answer_parts": [{"result_ref": "unknown"}], "render_from_claims": 0}, "bad_claim_binding", "unknown_result_ref"),
    ({"render_from_claims": 0}, "bad_claim_binding", "must be a boolean"),
    ({"draft": "第二正文。", "render_from_claims": True}, "bad_claim_binding", "second draft"),
])
def test_compilation_and_protocol_keep_preflight_and_error_priority(extra, code, phrase):
    _, context = frame_context()
    raw = {"status": "partial", "draft": "", "gaps": [], "bindings": [], **extra}
    for caller in (
        lambda: compile_finish_authoring(raw, context=context),
        lambda: validate_episode_finish(raw, context=context, evidence=()),
    ):
        with pytest.raises(ValueError, match=phrase) as error:
            caller()
        assert error.value.code == code


@pytest.mark.parametrize("field,value,code", [
    ("gaps", ("非法 tuple。",), "bad_gaps"),
    ("bindings", (), "bindings_not_list"),
    ("bindings", [{"output_id": "direct_assessment", "evidence_hashes": (), "basis": "evidence", "gap": ""}], "hashes_not_list"),
])
def test_immutable_copy_does_not_turn_invalid_tuple_fields_into_valid_lists(field, value, code):
    _, context = frame_context()
    raw = {"status": "partial", "draft": "原正文。", "gaps": [], "bindings": [], field: value}
    with pytest.raises(ValueError) as error:
        validate_episode_finish(raw, context=context, evidence=())
    assert error.value.code == code


def test_material_contract_and_claim_origins_keep_the_existing_owner():
    from intelligence.services.material_grounding import claim_finish_format

    _, context = history_setup()
    author = finish_author_contract(context)
    assert author.schema_payload() == finish_json_schema(context.contract)
    assert author.prompt_payload() == claim_finish_format(context.contract)
    assert validate_episode_finish(compact_finish(), context=context, evidence=()) == validate_episode_finish(
        legacy_finish(context), context=context, evidence=(),
    )
    raw = compact_finish()
    text = "上一条的收盘价为68.78元。本轮未重新核验。"
    raw["answers"][0]["claims"][0]["text"] = text
    compiled = compile_finish_authoring(raw, context=context)
    assert text in compiled.envelope["draft"]
    assert compiled.claim_origins["direct_answer"] == (0, 0)
    assert [c["text"] for c in compiled.envelope["bindings"][0]["claims"]] == ["上一条的收盘价为68.78元。", "本轮未重新核验。"]
    assert compiled.owned_answer is None
    with pytest.raises(TypeError):
        compiled.claim_origins["direct_answer"] = (1,)
    with pytest.raises(FinishAuthoringError, match="cannot mix"):
        compile_finish_authoring({"status": "bad", "draft": 3, "answer_parts": []}, context=context)


def test_material_prior_evidence_keeps_the_legacy_schema_and_format_exception():
    from intelligence.services.prior_evidence import PriorTurnEvidence

    _, context = history_setup()
    prior = PriorTurnEvidence(
        context.contract.task_frame_hash, "old-run", "old-message", "artifact-digest", "旧题", date(2026, 9, 30),
        (("E1", source_fixture().evidence[0]),),
    )
    context = replace(context, prior_evidence=prior)
    author = finish_author_contract(context)
    assert author.model_payload is None
    assert author.schema_payload() == finish_json_schema(context.contract, prior_evidence=prior)
    assert "format" not in author.json_schema["properties"]
    with pytest.raises(FinishAuthoringError, match="unsupported author format"):
        compile_finish_authoring(compact_finish(), context=context)
