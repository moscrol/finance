"""Output identity follows its producer, not an advisory slot-name allowlist."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from intelligence.runtime.conversation_orchestrator import (
    _merge_frame_outputs,
    _specialized_owner_required_outputs,
)
from intelligence.services import episode_factory
from intelligence.services.episode_authorization import (
    EpisodeAuthorizationSnapshot,
    capture_authorization_snapshot,
    validate_current_authorization,
)
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.research_contract import (
    FactSlot,
    RequiredOutput,
    ResearchProgram,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame, align_task_frame, rebase_task_frame
from intelligence.services.task_fulfillment import evaluate_task_fulfillment, render_prompt_constraint


def _frame(*ids: str, requirements=()) -> TaskFrame:
    frame = TaskFrame(
        "分析本地样例", "回答原问题", "general_finance_qa", "样例", "theme",
        "A股", None, ids or ("direct_answer",), (), (), None,
        "current_multi_source_evidence", 0.9,
    )
    return replace(frame, output_requirements=requirements) if requirements else frame


def _context(frame: TaskFrame):
    return build_episode_context(
        frame, task_id="provenance-test", today="2026-10-02",
        capabilities=("market_data",),
    )


def _by_id(context):
    return {item.output_id: item for item in context.contract.required_outputs}


@pytest.mark.parametrize("slot_id", ["novel_optional_receipt", "another_optional_receipt"])
def test_program_required_bit_reaches_contract_without_an_advisory_name_list(monkeypatch, slot_id):
    from intelligence.services import research_contract

    monkeypatch.setattr(research_contract, "compile_research_program", lambda *a, **k: ResearchProgram(
        "program", "general_finance_qa", (), required_fact_slots=(FactSlot(slot_id, False),),
    ))
    monkeypatch.setitem(episode_factory._OUTPUT_DESCRIPTIONS, slot_id, "新增检索建议")
    output = _by_id(_context(_frame()))[slot_id]
    assert output.required is False
    assert output.origin == "research_program"


def test_explicit_frame_requirement_wins_over_same_named_advisory():
    required = RequiredOutput("prime_quote", "本次明确要求的行情", origin="user_request")
    frame = _frame("prime_quote", requirements=(required,))
    output = _by_id(_context(frame))["prime_quote"]
    assert output.required is True
    assert output.origin == "user_request"
    assert output.description == required.description


def test_frame_optional_metadata_survives_contract_and_fulfillment():
    suggestion = RequiredOutput("counterpoint", "可不采用的反方建议", required=False, origin="heuristic")
    frame = _frame("counterpoint", requirements=(suggestion,))
    restored = TaskFrame.from_dict(json.loads(json.dumps(frame.to_dict())))
    assert restored == frame
    context = _context(restored)
    output = _by_id(context)["counterpoint"]
    assert (output.required, output.origin) == (False, "heuristic")
    verdict = evaluate_task_fulfillment(
        question=frame.raw_question, required_outputs=(output,), answer_text="正文",
        claims=(), sources=(),
    )
    assert verdict.missing_required == ()
    assert verdict.to_dict()["items"][0]["origin"] == "heuristic"
    assert "可选" in render_prompt_constraint(output)


def test_alias_merge_cannot_promote_suggestion_or_drop_explicit_requirement():
    suggestion = RequiredOutput("direct_answer", "可选", required=False, origin="heuristic")
    frame = _frame("direct_answer", requirements=(suggestion,))
    existing = (RequiredOutput("direct_assessment", "旧执行槽", required=False),)
    merged = _merge_frame_outputs(existing, frame, ())
    assert len(merged) == 1
    assert (merged[0].required, merged[0].origin) == (False, "heuristic")
    mandatory = replace(suggestion, required=True, origin="user_request")
    merged = _merge_frame_outputs(existing, replace(frame, output_requirements=(mandatory,)), ())
    assert (merged[0].required, merged[0].origin) == (True, "user_request")
    # Conversely a suggestion cannot demote an existing hard obligation.
    merged = _merge_frame_outputs((replace(existing[0], required=True),), frame, ())
    assert merged[0].required is True
    assert set(merged[0].merged_origins) == {"legacy", "heuristic"}
    # A second required alias must not overwrite the user-origin witness.
    from intelligence.services.output_requirement import merge_output_requirement
    explicit = replace(existing[0], required=True, origin="user_request")
    joined = merge_output_requirement(explicit, RequiredOutput("direct_answer", "旧槽"))
    assert joined.origin == "user_request"
    assert joined.merged_origins == ("legacy", "user_request")


def test_frame_metadata_cannot_be_added_or_changed_by_alignment_model():
    frame = _frame("direct_answer", requirements=(RequiredOutput(
        "direct_answer", "必须回答", origin="user_request",
    ),))
    changed = align_task_frame(frame, json.dumps({
        "output_requirements": [{"output_id": "direct_answer", "required": False, "origin": "heuristic"}],
        "required_outputs": [],
    }))
    assert changed == frame
    rebased = rebase_task_frame(
        frame, question_type="general_finance_qa", subject="样例", required_outputs=("counterpoint",),
    )
    assert rebased.output_requirements[0] == frame.output_requirements[0]


@pytest.mark.parametrize("metadata", [
    [{"output_id": "unknown", "description": "不在当前ID集"}],
    [{"output_id": "direct_answer", "description": "x", "origin": "forged"}],
    [{"output_id": "direct_answer", "description": "x", "required": "false"}],
    [{"output_id": "direct_answer", "description": "x", "grounding_mode": "unknown"}],
    [{"output_id": "direct_answer", "description": "x"}] * 2,
    [{"output_id": "direct_answer", "description": "x", "origin": "user_request", "required": False}],
    [{"output_id": "direct_answer", "description": "x", "origin": "heuristic", "max_calls": 90}],
    [{"output_id": "direct_answer", "description": "x", "origin": "heuristic", "merged_origins": ["user_request"], "required": False}],
])
def test_bad_frame_metadata_fails_closed(metadata):
    payload = _frame().to_dict()
    payload["output_requirements"] = metadata
    assert TaskFrame.from_dict(payload) is None


def test_legacy_payload_and_authorization_snapshot_stay_exact():
    frame = _frame()
    assert "output_requirements" not in frame.to_dict()
    context = _context(frame)
    old = replace(context.contract, required_outputs=(RequiredOutput("direct_answer", "答原题"),))
    payload = old.to_dict()
    assert "origin" not in payload["required_outputs"][0]
    assert ResearchTaskContract.from_dict(json.loads(json.dumps(payload))).to_dict() == payload
    # Assemble the legacy initial context; this is not a live repair projection.
    context = replace(context, contract=old, root_request=None)
    registry = ResearchToolRegistry(())
    saved = capture_authorization_snapshot(context, registry)
    # Captured by the unmodified P1a tree, not generated by the new serializer.
    fixture = json.loads((Path(__file__).parent / "fixtures" / "output-provenance-legacy-authorization.json").read_text())
    assert json.loads(json.dumps(frame.to_dict())) == fixture["frame"]
    assert saved == fixture["authorization"]
    assert EpisodeAuthorizationSnapshot.from_dict(saved, episode_id=old.task_id).to_dict() == saved
    validate_current_authorization(saved, context=context, registry=registry)
    changed = replace(old, required_outputs=(replace(old.required_outputs[0], origin="user_request"),))
    with pytest.raises(ValueError, match="does not match"):
        validate_current_authorization(saved, context=replace(context, contract=changed), registry=registry)


def test_specialized_owner_uses_frame_metadata_not_owner_slot_defaults():
    from types import SimpleNamespace

    output = SimpleNamespace(answer_contract=SimpleNamespace(required_outputs=("counterpoint",)))
    requirement = RequiredOutput("counterpoint", "建议", required=False, origin="method")
    projected = _specialized_owner_required_outputs(
        output, _frame("counterpoint", requirements=(requirement,)),
    )
    assert projected == (requirement,)


def test_envelope_hints_are_optional_through_real_frame_and_contract():
    from intelligence.services.query_understanding import QueryEnvelope
    from intelligence.services.task_frame import build_task_frame

    envelope = QueryEnvelope(
        "general_finance_qa", "theme", "样例", "回答问题", None, "generic", 0.8,
        required_outputs=("counterpoint",),
    )
    frame = build_task_frame("分析本地样例", envelope)
    requirement = frame.output_requirement("counterpoint")
    assert requirement is not None
    assert (requirement.required, requirement.origin) == (False, "heuristic")
    output = _by_id(_context(frame))["counterpoint"]
    assert output.required is False
    assert output.description == episode_factory._require_output_description("counterpoint")
    # Existing type defaults are explicitly not claimed to be migrated here.
    assert _by_id(_context(frame))["direct_answer"].required is True


@pytest.mark.parametrize("new_type", ["concept_definition", "personal_memory_recall"])
def test_rebase_and_factory_preserve_user_obligation_on_type_change(new_type):
    requirement = RequiredOutput("counterpoint", "用户明确要求", origin="user_request")
    frame = _frame("counterpoint", requirements=(requirement,))
    changed = rebase_task_frame(frame, question_type=new_type, subject="样例")
    assert "counterpoint" in changed.required_outputs
    assert changed.output_requirement("counterpoint") == requirement
    output = _by_id(_context(changed))["counterpoint"]
    assert output.origin == "user_request"
    assert output.description == requirement.description


@pytest.mark.parametrize("origin,merged_origins", [
    ("user_request", ()), ("method", ("method", "user_request")),
])
def test_history_reassembly_keeps_user_obligations_and_retires_unselected_hints(monkeypatch, origin, merged_origins):
    from intelligence.services import turn_controller
    from intelligence.services.conversation_materials import collect_material_turn_history
    from intelligence.services.conversation_store import Message

    def offline(_):
        return None, None, "offline"

    first = turn_controller.decide_turn(
        "只用本地已有资料，复盘这一波农业怎么走出来的。", llm_complete=offline,
    )
    history = collect_material_turn_history([
        Message("history-user", "conv", "user", first.task_frame.raw_question, "2026-10-02", "completed"),
    ])
    original_build = turn_controller.build_task_frame
    user = RequiredOutput("prime_quote", "另行确认的用户要求", origin=origin, merged_origins=merged_origins)
    retired = RequiredOutput("retired_hint", "未采用建议", required=False, origin="heuristic")
    retained = RequiredOutput("counterpoint", "保留的建议", required=False, origin="method")

    def trusted_build(*args, **kwargs):
        frame = original_build(*args, **kwargs)
        assert frame.history_intent is None  # Inheritance below rebuilds the output set.
        requirements = (user, retired, retained)
        ids = tuple(item.output_id for item in requirements)
        return replace(
            frame, required_outputs=tuple(dict.fromkeys((*frame.required_outputs, *ids))),
            output_requirements=(
                *(item for item in frame.output_requirements if item.output_id not in ids),
                *requirements,
            ),
        )

    monkeypatch.setattr(turn_controller, "build_task_frame", trusted_build)
    followup = turn_controller.decide_turn(
        "以前有没有类似？", previous_intent=first.turn_intent, previous_turn_id="t1",
        conversation_materials=history, llm_complete=offline,
    )
    frame = followup.task_frame
    assert frame.history_intent.purpose == "historical_comparison"
    assert frame.material_contract.data_scope == "local_only"
    assert frame.output_requirement(user.output_id) == user
    assert user.output_id in frame.required_outputs
    assert frame.output_requirement(retained.output_id) == retained
    assert retired.output_id not in frame.required_outputs
    assert frame.output_requirement(retired.output_id) is None
    assert TaskFrame.from_dict(frame.to_dict()) == frame
    context = _context(frame)
    assert _by_id(context)[user.output_id].required is True
    assert _by_id(context)[user.output_id].origin == origin
    assert _by_id(context)[user.output_id].merged_origins == merged_origins
    assert "evidence_search" not in context.contract.allowed_capabilities


def test_model_input_and_finalizer_receive_same_requirement_identity():
    from intelligence.services.episode_protocol import build_episode_input
    from intelligence.runtime.episode_finalizer import EpisodeFinalizer

    optional = RequiredOutput("counterpoint", "研究建议", required=False, origin="method")
    frame = _frame("counterpoint", requirements=(optional,))
    context = _context(frame)
    registry = ResearchToolRegistry(())
    payload = json.loads(build_episode_input(frame, context, registry))
    prompt = next(item for item in payload["research_contract"]["required_outputs"] if item["output_id"] == "counterpoint")
    assert (prompt["required"], prompt["origin"]) == (False, "method")
    final = EpisodeFinalizer._payload(
        task_frame=frame, context=context, evidence=(), gaps=(), failure_reason="test",
    )
    output = next(item for item in final["required_outputs"] if item["output_id"] == "counterpoint")
    assert (output["required"], output["origin"]) == (False, "method")


@pytest.mark.parametrize("change", [
    {"origin": []}, {"merged_origins": []}, {"merged_origins": ({},)},
    {"merged_origins": ("method", "heuristic")}, {"required": 1},
])
def test_constructor_rejects_malformed_provenance(change):
    with pytest.raises(ValueError):
        RequiredOutput("direct_answer", "x", **change)


def test_merged_origins_round_trip_and_authorization_detect_source_loss():
    from intelligence.services.output_requirement import merge_output_requirement

    merged = merge_output_requirement(
        RequiredOutput("counterpoint", "用户要求", origin="user_request"),
        RequiredOutput("counterpoint", "方法建议", required=False, origin="method"),
    )
    frame = _frame("counterpoint", requirements=(merged,))
    assert TaskFrame.from_dict(json.loads(json.dumps(frame.to_dict()))) == frame
    context = _context(frame)
    assert _by_id(context)["counterpoint"].merged_origins == ("method", "user_request")
    saved = capture_authorization_snapshot(context, ResearchToolRegistry(()))
    assert EpisodeAuthorizationSnapshot.from_dict(saved, episode_id=context.contract.task_id).to_dict() == saved
    changed = replace(context.contract, required_outputs=tuple(
        replace(item, merged_origins=()) for item in context.contract.required_outputs
    ))
    with pytest.raises(ValueError, match="does not match"):
        validate_current_authorization(
            saved, context=replace(context, contract=changed), registry=ResearchToolRegistry(()),
        )


@pytest.mark.parametrize("backend", ["continuous", "sdk"])
@pytest.mark.parametrize("required", [False, True])
def test_real_runtime_entry_preserves_optional_vs_user_obligation(backend, required):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
    from intelligence.services.agent_research import AgentEvidence
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.services.research_tool_registry import ToolSpec

    source = "user_request" if required else "method"
    frame = _frame("direct_answer", "counterpoint", requirements=(
        RequiredOutput("direct_answer", "回答原问题", origin="user_request"),
        RequiredOutput("counterpoint", "附加解释", required=required, origin=source),
    ))
    context = build_episode_context(
        frame, task_id=f"provenance-{backend}-{required}", today="2026-10-02",
        capabilities=("market_data",),
    )
    queries, prompts = [], []

    def tool(query, tool_context):
        queries.append(query)
        return [AgentEvidence(
            tool="market_data", title="本地样例", detail="样例呈现结构变化。",
            source="测试原件", source_date="2026-10-02", evidence_tier="L4", content_hash="sample-hash",
        )], "样例呈现结构变化。", ProviderTrace(
            provider="test:sample", capability="market_data", status="success", result_count=1,
        )

    registry = ResearchToolRegistry((ToolSpec(
        name="market_data", capability="market_data", description="读取本地样例",
        cost="local", freshness="current", runner=tool,
    ),))
    finish = json.dumps({
        "status": "completed", "draft": "样例呈现结构变化。", "gaps": [],
        "bindings": [{"output_id": "direct_answer", "evidence_hashes": ["sample-hash"], "gap": ""}],
    }, ensure_ascii=False)

    class Model:
        def complete(self, *, messages, tools, timeout):
            if not prompts:
                prompts.append(json.loads(messages[1]["content"]))
                return ModelTurn("", (ModelToolCall("sample", "market_data", {"query": "读取样例"}),), "scripted", "")
            return ModelTurn(finish, (), "scripted", "")

    def sdk(request):
        prompts.append(json.loads(request.input))
        request.tools[0].invoke("读取样例")
        return AgentsSdkResult(final_output=finish, llm_calls=2)

    runtime = ContinuousAgentEpisode(Model()) if backend == "continuous" else OpenAIAgentsRuntime(
        runner=sdk, backend="sdk_glm", model_name="offline-scripted",
    )
    outcome = runtime.run(task_frame=frame, context=context, registry=registry)
    sent = next(item for item in prompts[0]["research_contract"]["required_outputs"] if item["output_id"] == "counterpoint")
    assert (sent["required"], sent["origin"]) == (required, source)
    assert queries == ["读取样例"]
    assert (outcome.status == "completed") is (not required), (outcome.stop_reason, outcome.gaps)
    assert outcome.usage.tool_calls == 1
    assert len(outcome.evidence) == 1
    if required and backend == "continuous":
        rejection = next(event for event in outcome.events if event.kind == "finish")
        assert "counterpoint" in str(rejection.payload)
    elif required:
        # SDK exposes its existing generic failure reason, not the rejected ID.
        assert outcome.stop_reason == "sdk_invalid_finish"


@pytest.mark.parametrize("scope", ["material_only", "local_only"])
def test_numbered_material_questions_preserve_user_and_runtime_origins(scope):
    from intelligence.services.material_contract import MaterialContract, MaterialQuestion

    user = RequiredOutput("counterpoint", "用户另行要求的反方解释", origin="user_request")
    frame = replace(_frame("counterpoint", requirements=(user,)), material_contract=MaterialContract(
        "constraint_confirmed", "real", scope,
        questions=(MaterialQuestion("q1", "解释材料的主要结论"),), data_scope_declared=True,
    ))
    context = _context(frame)
    outputs = _by_id(context)
    assert outputs["answer_q1"].required is True
    assert outputs["answer_q1"].origin == "user_request"
    assert outputs["evidence_boundary"].origin == "runtime"
    assert outputs["counterpoint"].required is True
    assert outputs["counterpoint"].description == user.description
    assert outputs["counterpoint"].origin == "user_request"
    if scope == "material_only":
        assert context.contract.allowed_capabilities == ()
        assert all(not item.evidence_types for item in outputs.values())
