"""Compact author input compiles to the unchanged, source-checked finish contract."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.codex_headless_runtime import CodexHeadlessRuntime, HeadlessProcessResult
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.conversation_materials import ConversationMaterials, HistoricalAssistantStatement
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import build_episode_input, finish_json_schema, validate_episode_finish
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.turn_controller import decide_turn
from intelligence.tests.test_codex_headless_runtime import _jsonl


OLD = "上一条收盘价为68.78元，日期为2026-09-24。"
TEXT = "上一条的收盘价为68.78元，本轮未重新核验。"


def history_setup():
    frame = decide_turn(
        "不重新查询。请复述你上一条的判断。",
        conversation_materials=ConversationMaterials(assistant_statements=(
            HistoricalAssistantStatement("assistant-old", OLD),
        )),
    ).task_frame
    return frame, build_episode_context(frame, task_id="author-" + uuid4().hex)


def compact_finish():
    return {"format": "material_claims_v1", "status": "completed", "answers": [
        {"output_id": "direct_answer", "claims": [{
            "text": TEXT, "kind": "historical_assistant_statement",
            "sources": [{"ref": "H1", "quote": "收盘价为68.78元"}],
        }]},
        {"output_id": "evidence_boundary", "claims": [{
            "text": "本轮未重新查询和核验。", "kind": "premise_declaration",
            "sources": [{"ref": "M1", "quote": "不重新查询"}],
        }]},
    ]}


def legacy_finish(context):
    return {"status": "completed", "draft": "", "render_from_claims": True, "gaps": [], "bindings": [
        {"output_id": "direct_answer", "basis": "evidence", "evidence_hashes": [], "gap": "", "claims": [{
            "text": TEXT, "kind": "historical_assistant_statement", "old_answer_coordinate": "assistant-old",
            "historical_quote": "收盘价为68.78元", "basis": "assistant_judgment",
        }]},
        {"output_id": "evidence_boundary", "basis": "user_premise", "evidence_hashes": [], "gap": "", "claims": [{
            "text": "本轮未重新查询和核验。", "kind": "premise_declaration", "material_anchors": [{
                "material_id": context.contract.material_grounding.materials[0].material_id, "quote": "不重新查询",
            }],
        }]},
    ]}


def test_compact_history_is_identical_to_legacy_without_promoting_assistant_judgment():
    _, context = history_setup()
    raw = compact_finish()
    saved = deepcopy(raw)
    parsed = validate_episode_finish(raw, context=context, evidence=())
    assert parsed == validate_episode_finish(legacy_finish(context), context=context, evidence=())
    assert [b.basis for b in parsed.bindings] == ["evidence", "user_premise"]
    assert parsed.bindings[0].claims[0].basis == "assistant_judgment"
    assert not any(b.evidence_hashes for b in parsed.bindings)
    assert not context.contract.allowed_capabilities and raw == saved


def test_context_free_decoder_and_legacy_compilation_keep_original_payload():
    from intelligence.services.episode_protocol import parse_finish_json
    from intelligence.services.material_answer_authoring import compile_material_author_finish

    _, context = history_setup()
    raw = compact_finish()
    assert parse_finish_json(json.dumps(raw, ensure_ascii=False)) == raw
    legacy = legacy_finish(context)
    assert compile_material_author_finish(legacy, context.contract) is legacy


@pytest.mark.parametrize("mutation,code", [
    ("E9", "unknown_evidence_ref"), ("fake_id", "material_source_violation"), ("fake_quote", "material_quote_mismatch"),
])
def test_legacy_source_identity_and_quote_rejections_are_distinct(mutation, code):
    _, context = history_setup()
    raw = legacy_finish(context)
    if mutation == "E9":
        raw["bindings"][0]["evidence_hashes"] = ["E9"]
    else:
        claim = raw["bindings"][0]["claims"][0]
        claim["old_answer_coordinate" if mutation == "fake_id" else "historical_quote"] = "invented"
    with pytest.raises(ValueError) as error:
        validate_episode_finish(raw, context=context, evidence=())
    assert error.value.code == code


@pytest.mark.parametrize("mutation", [
    "unknown_format", "legacy_top", "basis", "hashes", "raw_coordinate", "unknown_output", "duplicate_output",
    "unknown_M", "unknown_H", "E9", "fake_quote", "history_as_M", "material_as_H", "two_H", "empty_H",
    "gap_and_claims", "missing_output",
])
def test_compact_protocol_rejects_invalid_structure_and_sources(mutation):
    _, context = history_setup()
    raw = compact_finish()
    answer = raw["answers"][0]
    claim = answer["claims"][0]
    if mutation == "unknown_format":
        raw["format"] = "material_claims_v2"
    elif mutation == "legacy_top":
        raw["draft"] = ""
    elif mutation in {"basis", "hashes"}:
        answer["basis" if mutation == "basis" else "evidence_hashes"] = "user_premise" if mutation == "basis" else ["E9"]
    elif mutation == "raw_coordinate":
        claim["old_answer_coordinate"] = "assistant-old"
    elif mutation == "unknown_output":
        answer["output_id"] = "invented"
    elif mutation == "duplicate_output":
        raw["answers"].append(deepcopy(answer))
    elif mutation in {"unknown_M", "unknown_H", "history_as_M", "E9"}:
        claim["sources"][0]["ref"] = {"unknown_M": "M999", "unknown_H": "H999", "history_as_M": "M1", "E9": "E9"}[mutation]
    elif mutation == "fake_quote":
        claim["sources"][0]["quote"] = "原文没有的片段"
    elif mutation == "material_as_H":
        claim["kind"] = "material_fact"
    elif mutation == "two_H":
        claim["sources"].append(deepcopy(claim["sources"][0]))
    elif mutation == "empty_H":
        claim["sources"] = []
    elif mutation == "missing_output":
        raw["answers"].pop()
    else:
        answer["gap"] = "缺少旧答。"
    saved = deepcopy(raw)
    with pytest.raises(ValueError) as error:
        validate_episode_finish(raw, context=context, evidence=())
    if mutation == "fake_quote":
        assert error.value.code == "material_quote_mismatch" and error.value.kind.value == "format"
    elif mutation == "two_H":
        assert error.value.code == "historical_excerpt_shape" and error.value.kind.value == "format"
    elif mutation in {"unknown_M", "unknown_H", "E9", "history_as_M", "material_as_H", "empty_H"}:
        assert error.value.code == "material_source_violation" and error.value.kind.value == "integrity"
    assert raw == saved


def test_compact_multisentence_history_claim_is_cut_and_each_piece_keeps_one_history_source():
    _, context = history_setup()
    raw = compact_finish()
    raw["answers"][0]["claims"][0]["text"] = "复述旧答。没有重新核验。"
    saved = deepcopy(raw)
    parsed = validate_episode_finish(raw, context=context, evidence=())
    pieces = parsed.bindings[0].claims
    assert [piece.text for piece in pieces] == ["复述旧答。", "没有重新核验。"]
    assert {(piece.kind, piece.old_answer_coordinate, piece.historical_quote) for piece in pieces} == {
        ("historical_assistant_statement", "assistant-old", "收盘价为68.78元")
    }
    assert "复述旧答。没有重新核验。" in parsed.draft and raw == saved

def test_compact_partial_preserves_authored_status_gap_and_every_claim():
    _, context = history_setup()
    raw = compact_finish()
    raw.update(status="partial", gaps=["未重新核验旧答。"])
    raw["answers"][0].update(claims=[], gap="旧答未提供成交额，无法复述。")
    parsed = validate_episode_finish(raw, context=context, evidence=())
    assert parsed.status == "partial" and parsed.gaps == ("未重新核验旧答。",)
    assert parsed.bindings[0].gap == raw["answers"][0]["gap"] and parsed.bindings[0].claims == ()
    assert parsed.bindings[1].claims[0].text == raw["answers"][1]["claims"][0]["text"]


@pytest.mark.parametrize("claim", [None, [], {}, {"text": None, "kind": "reasoning", "sources": []},
    {"text": "方法推理。", "kind": [], "sources": []}, {"text": "方法推理。", "kind": "reasoning", "sources": [None]},
])
def test_malformed_author_claims_are_protocol_errors(claim):
    _, context = history_setup()
    raw = compact_finish()
    raw["answers"][0]["claims"] = [claim]
    with pytest.raises(ValueError) as error:
        validate_episode_finish(raw, context=context, evidence=())
    assert error.value.code == "bad_claim_binding"


@pytest.mark.parametrize("scope", ["full", "local_only", "unsettled", None])
def test_compact_author_protocol_requires_settled_material_only(scope):
    _, context = history_setup()
    contract = context.contract.material_contract
    if scope is None:
        contract = None
    elif scope == "unsettled":
        contract = replace(contract, classification="boundary_uncertain", uncertain_reasons=("待确认",))
    else:
        contract = replace(contract, data_scope=scope)
    context = replace(context, contract=replace(context.contract, material_contract=contract))
    with pytest.raises(ValueError):
        validate_episode_finish(compact_finish(), context=context, evidence=())
    assert "format" not in finish_json_schema(context.contract)["properties"]


def test_compact_author_projection_schema_and_finalizer_share_frozen_catalogue():
    from intelligence.services.material_answer_authoring import material_author_payload, material_author_schema

    frame, context = history_setup()
    saved = context.contract.to_dict()
    opening = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    author = material_author_payload(context.contract)
    assert opening["material_grounding"] == author
    assert author["sources"] == [
        {"ref": "M1", "kind": "user_material", "text": frame.raw_question},
        {"ref": "H1", "kind": "historical_assistant_statement", "text": OLD},
    ]
    assert "material_grounding" not in opening["research_contract"]
    assert "assistant_statements" not in opening["task_frame"]["conversation_materials"]
    assert OLD not in opening["conversation_context"]
    schema = finish_json_schema(context.contract)
    assert schema == material_author_schema(context.contract)
    assert schema["properties"]["format"]["enum"] == ["material_claims_v1"]
    assert schema["additionalProperties"] is False
    calls = []

    class Writer:
        def complete(self, *, messages, tools, timeout):
            assert tools == []
            calls.append(messages)
            return ModelTurn(json.dumps(compact_finish(), ensure_ascii=False), (), "offline")

    recovered = EpisodeFinalizer(Writer()).recover(
        task_frame=frame, context=context, evidence=(), gaps=(), failure_reason="invalid_model_finish",
    )
    assert json.loads(calls[0][1]["content"])["material_grounding"] == author
    assert "wire_template" in calls[0][0]["content"]
    validate_episode_finish(recovered.content, context=context, evidence=())
    assert context.contract.to_dict() == saved


def test_extra_bracket_is_rejected_with_safe_json_position_then_same_episode_recovers():
    frame, context = history_setup()
    good = json.dumps(compact_finish(), ensure_ascii=False)
    bad = good + "]"
    with pytest.raises(ValueError) as error:
        validate_episode_finish(bad, context=context, evidence=())
    assert error.value.code == "not_json_object"
    assert f"line 1 column {len(good) + 1} char {len(good)}" in str(error.value)
    assert TEXT not in str(error.value)
    calls = []
    original_policy, original_deadline = context.policy, context.deadline

    class Writer:
        def complete(self, *, messages, tools, timeout):
            assert tools == [] and 0 < timeout <= context.policy.total_seconds
            calls.append(deepcopy(messages))
            return ModelTurn(bad if len(calls) == 1 else good, (), "offline")

    result = ContinuousAgentEpisode(Writer()).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert result.status == "completed" and TEXT in result.draft
    assert len(calls) == result.usage.llm_calls == 2 and result.usage.invalid_actions == 1
    assert result.usage.tool_calls == 0 and result.evidence == ()
    assert "line 1 column" in str(calls[1])
    assert context.policy is original_policy and context.deadline is original_deadline
    authored = [event.payload.get("content") for event in result.events if event.kind == "model_turn"]
    assert bad in authored and good in authored


@pytest.mark.parametrize("repair_quote", [False, True])
def test_compiled_history_keeps_canonical_judge_sources_and_semantic_rejection(repair_quote):
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.tests.material_judge_helpers import material_judge_report

    frame, context = history_setup()
    raw = compact_finish()
    mixed = "上一条收盘价为68.78元，因此本轮已经核实当前价格。"
    raw["answers"][0]["claims"][0]["text"] = mixed

    class Writer:
        calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            value = deepcopy(raw)
            if repair_quote and self.calls == 1:
                value["answers"][0]["claims"][0]["sources"][0]["quote"] = "原文没有的摘录"
            return ModelTurn(json.dumps(value, ensure_ascii=False), (), "offline")

    writer = Writer()
    result = ContinuousAgentEpisode(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert writer.calls == (2 if repair_quote else 1)
    requests = []

    def judge(request):
        requests.append(request)
        historical = request["material_grounding"]["historical_assistant_statements"][0]
        assert historical == {"source_message_id": "assistant-old", "text": OLD, "basis": "assistant_judgment"}
        assert "sources" not in request["material_grounding"]
        claim = request["output_bindings"][0]["claims"][0]
        assert claim["old_answer_coordinate"] == "assistant-old" and claim["basis"] == "assistant_judgment"
        indexes = [row["index"] for row in request["sentences"] if row["text"] == mixed]
        return material_judge_report(request, rejected=indexes, issues=["旧答与当前事实混句。"])

    verdict = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, result), deadline=context.deadline,
    )
    assert requests and verdict.status != "completed" and verdict.judge_status == "rejected"
    assert mixed not in verdict.public_answer


def test_headless_uses_author_schema_and_shared_compiler():
    frame, context = history_setup()
    calls = []

    def run(command):
        calls.append(command)
        schema = json.loads((command.cwd / "episode-finish.schema.json").read_text())
        assert schema["properties"]["format"]["enum"] == ["material_claims_v1"]
        return HeadlessProcessResult(stdout=_jsonl(wrapper_command=None, finish=compact_finish()), stderr="", returncode=0)

    result = CodexHeadlessRuntime(command_runner=run).run(
        task_frame=frame, context=context, registry=ResearchToolRegistry(()),
    )
    assert len(calls) == 1 and result.status == "completed" and TEXT in result.draft
    assert result.usage.tool_calls == 0 and result.evidence == ()
    assert not Path(calls[0].cwd).exists()
