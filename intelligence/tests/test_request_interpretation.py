"""Root request fidelity and independently versioned, model-owned goal interpretation."""
from dataclasses import replace
import json
import socket

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.research_plan import parse_research_plan
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.task_frame import TaskFrame


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempts = []

    def deny(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("interpretation tests must stay offline")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    yield
    assert not attempts


def frame():
    return TaskFrame(
        "  请解释这个方法；保留用户原文。\n", "初始解释", "general_finance_qa", "样例",
        "theme", "A股", None, ("direct_answer",), (), (), None,
        "current_multi_source_evidence", 0.9,
        output_requirements=(RequiredOutput("direct_answer", "回答完整原题", origin="user_request"),),
    )


def context(task_id="interpretation-unit"):
    return build_episode_context(frame(), task_id=task_id, today="2026-10-03", capabilities=("market_data",))


def plan(proposal=None, **overrides):
    payload = dict(kind="PLAN", task_summary="解释方法", answer_elements=["解释"],
                   hypotheses=["方法有适用范围"], evidence_needs=["样例"], candidate_actions=[],
                   open_gaps=[], requested_mode="quick", revision=1, base_revision=0)
    if proposal is not None:
        payload["interpretation"] = proposal
    payload.update(overrides)
    return parse_research_plan(json.dumps(payload, ensure_ascii=False))


def proposal(contract, **overrides):
    from intelligence.services.request_interpretation import root_request_payload
    return dict(request_ref=root_request_payload(contract)["request_ref"], base_revision=0,
                goal="解释方法而非判断当前市场", reason="原问关注方法的适用范围", **overrides)


def test_root_request_is_exact_and_not_the_model_summary():
    from intelligence.services.request_interpretation import root_request_payload
    ctx = context()
    root = root_request_payload(ctx.contract)
    assert root["raw_question"] == frame().raw_question
    assert root["required_outputs"] == [item.to_dict() for item in ctx.contract.required_outputs]
    assert root["task_frame_hash"] == frame().task_frame_hash
    assert root["request_ref"] != root_request_payload(replace(ctx.contract, question="别的问题"))["request_ref"]
    assert root["request_ref"] != root_request_payload(replace(
        ctx.contract, required_outputs=(replace(ctx.contract.required_outputs[0], description="新的用户义务"),),
    ))["request_ref"]


def test_interpretation_revision_is_separate_from_plan_revision_and_authority():
    from intelligence.services.request_interpretation import accept_interpretation
    ctx = context()
    saved = ctx.contract.to_dict()
    ctx.root_budget.consume_call(seconds=0.5)
    spent = ctx.root_budget.to_snapshot()
    first = accept_interpretation(plan(proposal(ctx.contract)), context=ctx)
    assert first.interpretation.revision == 1
    unchanged = accept_interpretation(plan(revision=9, base_revision=1), context=first)
    assert unchanged is first  # ordinary plan revisions do not reset/increment interpretation
    second_payload = {**proposal(ctx.contract), "base_revision": 1, "goal": "先说明适用条件，再给反例"}
    second = accept_interpretation(plan(second_payload, revision=10, base_revision=9), context=first)
    assert second.interpretation.revision == 2
    assert second.contract is ctx.contract and second.contract.to_dict() == saved
    assert second.root_budget is ctx.root_budget and second.root_budget.to_snapshot() == spent
    assert second.deadline is ctx.deadline
    assert second.information_cutoff is ctx.information_cutoff
    assert second.history_results is ctx.history_results
    assert second.interpretation.request_ref == first.interpretation.request_ref


def test_stale_or_cross_request_proposal_does_not_mutate_current_state():
    from intelligence.services.request_interpretation import accept_interpretation
    ctx = context()
    first = accept_interpretation(plan(proposal(ctx.contract)), context=ctx)
    for bad in (proposal(ctx.contract), {**proposal(ctx.contract), "request_ref": "request:" + "0" * 64, "base_revision": 1}):
        with pytest.raises(ValueError, match="stale|request_ref"):
            accept_interpretation(plan(bad), context=first)
    assert first.interpretation.revision == 1
    assert ctx.interpretation is None


@pytest.mark.parametrize("variant", ["valid", "absent", "cross_root", "stale"])
def test_default_harness_interpretation_admission_is_structured_and_preserves_authority(variant):
    from intelligence.services.request_interpretation import interpretation_payload
    from intelligence.services.research_harness import FinanceResearchHarness
    ctx = context(f"interpretation-admission-{variant}")
    ctx.root_budget.consume_call(seconds=0.5)
    spent = ctx.root_budget.to_snapshot()
    payload = proposal(ctx.contract)
    if variant == "cross_root":
        payload["request_ref"] = "request:" + "0" * 64
    elif variant == "stale":
        payload["base_revision"] = 7
    candidate = plan(None if variant == "absent" else payload)
    result = FinanceResearchHarness().admit_interpretation(candidate, context=ctx)
    assert result.accepted == (variant in {"valid", "absent"})
    assert result.context.contract is ctx.contract
    assert result.context.root_request is ctx.root_request
    assert result.context.root_budget is ctx.root_budget
    assert result.context.root_budget.to_snapshot() == spent
    assert result.context.deadline is ctx.deadline
    assert result.context.information_cutoff is ctx.information_cutoff
    assert result.context.history_results is ctx.history_results
    assert ctx.interpretation is None
    if result.accepted:
        assert result.model_feedback == interpretation_payload(result.context)
        if variant == "valid":
            assert result.context.interpretation.revision == 1
        else:
            assert result.context is ctx
    else:
        assert result.context is ctx
        assert result.model_feedback == {}
        assert ("request_ref" if variant == "cross_root" else "stale") in result.error


@pytest.mark.parametrize("extra", [
    {"allowed_capabilities": ["web_search"]}, {"required_outputs": []}, {"deadline": 999},
    {"question_type": "methodology_discussion"}, {"subject": "另一个主体"}, {"timeframe": "未来"},
    {"base_revision": True}, {"base_revision": -1}, {"reason": ""}, {"goal": ""},
    {"request_ref": "unbound"},
])
def test_interpretation_is_closed_strict_and_cannot_grant_authority(extra):
    with pytest.raises(ValueError):
        plan({**proposal(context().contract), **extra})


def test_versioned_interpretation_round_trip_and_legacy_plan_shape():
    from intelligence.services.research_plan import plan_to_public_dict
    ctx = context()
    new = plan(proposal(ctx.contract))
    assert parse_research_plan(json.dumps({"kind": "PLAN", **plan_to_public_dict(new)})) == new
    assert "interpretation" not in plan_to_public_dict(plan())


def test_recovery_snapshot_versions_interpretation_without_resigning_legacy():
    from intelligence.services.episode_authorization import (
        EpisodeAuthorizationSnapshot, capture_authorization_snapshot, validate_current_authorization,
    )
    from intelligence.services.request_interpretation import accept_interpretation
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    ctx = context()
    registry = ResearchToolRegistry(())
    old = capture_authorization_snapshot(ctx, registry)
    revised = accept_interpretation(plan(proposal(ctx.contract)), context=ctx)
    new = capture_authorization_snapshot(revised, registry)
    assert old["schema_version"] == 1 and "interpretation" not in old
    assert new["schema_version"] == 2
    assert new["contract"] == old["contract"]
    assert EpisodeAuthorizationSnapshot.from_dict(new, episode_id=ctx.contract.task_id).to_dict() == new
    validate_current_authorization(new, context=revised, registry=registry)
    for saved, current in ((old, revised), (new, ctx)):
        with pytest.raises(ValueError, match="does not match"):
            validate_current_authorization(saved, context=current, registry=registry)
    corrupt = {**new, "interpretation": {**new["interpretation"], "request_ref": "request:" + "0" * 64}}
    with pytest.raises(ValueError, match="request_ref"):
        EpisodeAuthorizationSnapshot.from_dict(corrupt, episode_id=ctx.contract.task_id)


def _finish():
    return json.dumps({"status": "completed", "draft": "方法需要先核对适用条件。", "gaps": [],
                       "bindings": [{"output_id": "direct_answer", "evidence_hashes": ["method-hash"], "gap": ""}]})


def _registry(seen):
    from intelligence.services.agent_research import AgentEvidence
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec

    def tool(query, ctx):
        seen.append(ctx)
        return [AgentEvidence(tool="market_data", title="样例", detail="方法需要先核对适用条件。",
                              source="离线样例", source_date="2026-10-03", evidence_tier="L4", content_hash="method-hash")], "样例", ProviderTrace(
            provider="test", capability="market_data", status="success", result_count=1,
        )
    return ResearchToolRegistry((ToolSpec("market_data", "market_data", "本地样例", "local", "current", tool),))


@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("backend", ["continuous", "reference"])
def test_continuous_admission_changes_real_prompt_before_tools_and_keeps_root(mixed, backend):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.episode_store import MemoryEpisodeStore
    from intelligence.services.research_plan import plan_to_public_dict
    ctx = context(f"interpretation-{backend}-{mixed}")
    before = ctx.contract.to_dict()
    seen, prompts = [], []
    candidate = json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))})
    tool = ModelToolCall("sample", "market_data", {"query": "读取样例"})
    turns = [ModelTurn(candidate, (tool,) if mixed else (), "offline", ""),
             ModelTurn("", (replace(tool, call_id="real"),), "offline", ""),
             ModelTurn(_finish(), (), "offline", "")]

    class Model:
        def complete(self, *, messages, tools, timeout):
            prompts.append([dict(item) for item in messages])
            return turns.pop(0)

    store = MemoryEpisodeStore()
    runtime = ContinuousAgentEpisode(Model(), store=store) if backend == "continuous" else HarnessReferenceLoop(Model())
    outcome = runtime.run(task_frame=frame(), context=ctx, registry=_registry(seen))
    assert outcome.status == "completed", (outcome.stop_reason, outcome.gaps)
    assert len(seen) == 1
    assert ctx.contract.to_dict() == before
    assert seen[0].deadline.expires_at <= ctx.deadline.expires_at
    assert seen[0].information_cutoff is ctx.information_cutoff
    assert len(outcome.evidence) == 1 and outcome.evidence[0].content_hash == "method-hash"
    if mixed:
        assert not any(e.payload.get("interpretation_revision") for e in outcome.events)
        assert any(e.kind == "tool_error" and e.payload.get("error") == "invalid_plan" for e in outcome.events)
    else:
        assert ctx.interpretation is None  # the caller's immutable initial view is not overwritten
        assert any("interpretation_accepted" == e.payload.get("source") for e in outcome.events)
        assert any('"revision": 1' in item["content"] and '"goal": "解释方法而非判断当前市场"' in item["content"]
                   for item in prompts[1] if item["role"] == "user")
        request = next(e for e in outcome.events if e.kind == "tool_request")
        assert request.payload["interpretation_revision"] == 1
        if backend == "continuous":
            _, saved = store.load(ctx.contract.task_id)
            assert saved.authorization_snapshot["interpretation"]["revision"] == 1
            assert saved.authorization_snapshot["contract"]["task_frame_hash"] == frame().task_frame_hash


@pytest.mark.parametrize("backend", ["continuous", "reference", "sdk"])
@pytest.mark.parametrize("reject", [False, True])
def test_interpretation_admission_and_feedback_belong_to_injected_harness(backend, reject):
    """A replacement harness owns admission AND the subsequent model message."""
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.services.research_plan import plan_to_public_dict

    ctx = context(f"interpretation-seam-{backend}-{reject}")
    candidate = json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))})
    seen, prompts, admissions = [], [], []
    custom_rule = "CUSTOM_INTERPRETATION_RULE"
    rejection = "custom harness declined this interpretation"

    class CustomHarness(FinanceResearchHarness):
        def assemble_prompt(self, task_frame, context, registry):
            system, user = super().assemble_prompt(task_frame, context, registry)
            payload = json.loads(user)
            payload["interpretation_rule"] = custom_rule
            return system, json.dumps(payload, ensure_ascii=False)

        def admit_interpretation(self, plan, *, context):
            from intelligence.services.research_harness import InterpretationAdmission
            admissions.append(context)
            if reject:
                return InterpretationAdmission(context=context, model_feedback={}, error=rejection)
            admitted = super().admit_interpretation(plan, context=context)
            assert admitted.accepted
            return replace(admitted, model_feedback={
                **admitted.model_feedback, "interpretation_rule": custom_rule,
            })

    def assert_feedback(text):
        if reject:
            assert rejection in text
        else:
            feedback = json.loads(text)
            assert feedback["interpretation_rule"] == custom_rule
            assert feedback["interpretation"]["revision"] == 1
            assert feedback["root_request"] == json.loads(json.dumps(ctx.root_request.to_dict()))

    turns = [
        ModelTurn(candidate, ()),
        ModelTurn("", (ModelToolCall("safe", "market_data", {"query": "读取样例"}),)),
        ModelTurn(_finish(), ()),
    ]

    class Model:
        def complete(self, *, messages, **kwargs):
            prompts.append([dict(row) for row in messages])
            return turns.pop(0)

    def runner(request):
        assert json.loads(request.input)["interpretation_rule"] == custom_rule
        assert_feedback(request.on_model_response(candidate, False))
        assert request.on_model_response("", True) is None
        request.tools[0].invoke({"query": "读取样例"})
        return AgentsSdkResult(final_output=_finish(), llm_calls=3)

    harness = CustomHarness()
    if backend == "sdk":
        runtime = OpenAIAgentsRuntime(runner=runner, backend="sdk_glm", model_name="offline", harness=harness)
    else:
        runtime_type = ContinuousAgentEpisode if backend == "continuous" else HarnessReferenceLoop
        runtime = runtime_type(Model(), harness=harness)
    outcome = runtime.run(task_frame=frame(), context=ctx, registry=_registry(seen))
    assert outcome.status == "completed", (outcome.stop_reason, outcome.gaps)
    assert admissions == [ctx]
    assert len(seen) == 1
    assert ctx.interpretation is None
    assert seen[0].information_cutoff is ctx.information_cutoff
    assert seen[0].deadline.expires_at <= ctx.deadline.expires_at
    request = next(event for event in outcome.events if event.kind == "tool_request")
    assert request.payload.get("interpretation_revision") == (None if reject else 1)
    assert (outcome.plan is None) == reject
    if backend != "sdk":
        assert json.loads(prompts[0][1]["content"])["interpretation_rule"] == custom_rule
        feedback = next(
            event.payload["content"] for event in outcome.events
            if event.kind == "model_input" and event.payload.get("source") == "interpretation_accepted"
        ) if not reject else next(
            row["content"] for row in prompts[1] if rejection in row["content"]
        )
        assert_feedback(feedback)
        assert any(row["role"] == "user" and row["content"] == feedback for row in prompts[1])


@pytest.mark.parametrize("backend", ["sdk_glm", "sdk_gpt"])
@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("custom_harness", [False, True])
def test_real_sdk_hook_admits_plan_before_tools_and_carries_interpretation(backend, mixed, custom_harness):
    from agents import Model, ModelResponse
    from agents.usage import Usage
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
    from intelligence.runtime.openai_agents_runtime import OpenAIAgentsRuntime, build_agents_model_settings
    from intelligence.services.research_plan import plan_to_public_dict
    ctx = context(f"interpretation-sdk-{backend}-{mixed}-{custom_harness}")
    seen = []
    candidate = json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))})

    class ScriptedModel(Model):
        def __init__(self):
            self.inputs = []

        async def get_response(self, system_instructions, input, **kwargs):
            self.inputs.append(input)
            index = len(self.inputs)
            output = []
            if index in (1, 3):
                output.append(ResponseOutputMessage(
                    id=f"message-{index}", role="assistant", status="completed", type="message",
                    content=[ResponseOutputText(annotations=[], type="output_text", text=candidate if index == 1 else _finish())],
                ))
            if index == 2 or (index == 1 and mixed):
                output.append(ResponseFunctionToolCall(
                    arguments=json.dumps({"query": "读取样例"}), call_id=f"call-{index}",
                    name="market_data", type="function_call", status="completed",
                ))
            assert index <= 3, "no extra private repair/model loops"
            return ModelResponse(output=output, usage=Usage(requests=1, input_tokens=10, output_tokens=5), response_id=f"r-{index}")

        def stream_response(self, *args, **kwargs):
            async def empty():
                if False:
                    yield None
            return empty()

    from intelligence.services.research_harness import FinanceResearchHarness
    admissions = []

    class CustomHarness(FinanceResearchHarness):
        def admit_interpretation(self, plan, *, context):
            admissions.append(context)
            result = super().admit_interpretation(plan, context=context)
            return replace(result, model_feedback={
                **result.model_feedback, "interpretation_rule": "CUSTOM_SDK_INTERPRETATION_RULE",
            })

    model = ScriptedModel()
    outcome = OpenAIAgentsRuntime(
        backend=backend, model_name="offline-scripted", model=model,
        model_settings=build_agents_model_settings(backend),
        harness=CustomHarness() if custom_harness else None,
    ).run(task_frame=frame(), context=ctx, registry=_registry(seen))
    assert outcome.status == "completed", (outcome.stop_reason, outcome.gaps)
    assert len(seen) == 1 and outcome.usage.tool_calls == 1
    assert outcome.usage.llm_calls == 3
    assert outcome.usage.input_tokens == 30 and outcome.usage.output_tokens == 15
    assert len(outcome.evidence) == 1
    second_input = json.dumps(model.inputs[1], ensure_ascii=False)
    assert bool(admissions) == (custom_harness and not mixed)
    assert ("CUSTOM_SDK_INTERPRETATION_RULE" in second_input) == (custom_harness and not mixed)
    if mixed:
        assert "invalid_plan" in second_input
        assert outcome.plan is None
    else:
        assert outcome.plan.interpretation.goal == "解释方法而非判断当前市场"
        assert 'accepted_plan_revision' in second_input
        assert any(e.payload.get("interpretation_revision") == 1 for e in outcome.events if e.kind == "tool_request")


@pytest.mark.parametrize("backend", ["continuous", "sdk"])
def test_stale_plan_plus_tool_is_rejected_without_losing_accepted_goal(backend):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.research_plan import plan_to_public_dict
    ctx = context(f"interpretation-stale-{backend}")
    accepted = json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))})
    stale = json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract), revision=2, base_revision=1))})
    seen = []

    class Model:
        def __init__(self):
            self.turn = 0

        def complete(self, *, messages, tools, timeout):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(accepted, (), "offline", "")
            if self.turn == 2:
                return ModelTurn(stale, (ModelToolCall("bad", "market_data", {"query": "不应执行"}),), "offline", "")
            if self.turn == 3:
                return ModelTurn("", (ModelToolCall("good", "market_data", {"query": "读取样例"}),), "offline", "")
            return ModelTurn(_finish(), (), "offline", "")

    def sdk(request):
        assert request.on_model_response(accepted, False)
        assert request.on_model_response(stale, True)
        assert request.tools[0].invoke({"query": "不应执行"})["error"] == "invalid_plan"
        assert request.on_model_response("", True) is None
        request.tools[0].invoke({"query": "读取样例"})
        return AgentsSdkResult(final_output=_finish(), llm_calls=4)

    runtime = ContinuousAgentEpisode(Model()) if backend == "continuous" else OpenAIAgentsRuntime(runner=sdk, backend="sdk_glm", model_name="offline")
    outcome = runtime.run(task_frame=frame(), context=ctx, registry=_registry(seen))
    assert outcome.status == "completed"
    assert len(seen) == 1
    assert outcome.plan.revision == 1
    assert outcome.plan.interpretation.goal == "解释方法而非判断当前市场"
    assert all(e.payload.get("interpretation_revision") == 1 for e in outcome.events if e.kind == "tool_request")


@pytest.mark.parametrize("interpreted", [False, True])
def test_root_survives_execution_projection_and_finalizer_without_rebuilding(interpreted):
    from intelligence.runtime.episode_finalizer import EpisodeFinalizer
    from intelligence.services.episode_authorization import capture_authorization_snapshot, validate_current_authorization, EpisodeAuthorizationSnapshot
    from intelligence.services.request_interpretation import accept_interpretation, interpretation_payload, RootRequest
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    ctx = context(f"frozen-root-{interpreted}")
    original = ctx.root_request.to_dict()
    if interpreted:
        ctx = accept_interpretation(plan(proposal(ctx.contract)), context=ctx)
    projection = replace(ctx.contract, required_outputs=(replace(ctx.contract.required_outputs[0], preplaced_gap="待补依据"),))
    changed = replace(ctx, contract=projection)
    assert changed.root_request is ctx.root_request
    assert interpretation_payload(changed)["root_request"] == original
    assert changed.root_budget is ctx.root_budget and changed.deadline is ctx.deadline
    registry = ResearchToolRegistry(())
    snapshot = capture_authorization_snapshot(changed, registry)
    assert snapshot["schema_version"] == 2
    assert json.loads(json.dumps(original)) == snapshot["root_request"]
    assert EpisodeAuthorizationSnapshot.from_dict(snapshot, episode_id=projection.task_id).to_dict() == snapshot
    validate_current_authorization(snapshot, context=changed, registry=registry)
    wrong = replace(changed, root_request=RootRequest.from_contract(projection))
    with pytest.raises(ValueError):
        validate_current_authorization(snapshot, context=wrong, registry=registry)
    if interpreted:
        payload = EpisodeFinalizer._payload(task_frame=frame(), context=changed, evidence=(), gaps=(), failure_reason="timeout")
        assert payload["request_interpretation"]["root_request"] == original
        assert payload["request_interpretation"]["interpretation"] == ctx.interpretation.to_dict()


@pytest.mark.parametrize("field", ["raw_question", "required_outputs", "request_ref"])
def test_corrupt_root_snapshot_cannot_be_restored(field):
    from intelligence.services.request_interpretation import RootRequest
    payload = context(f"corrupt-root-{field}").root_request.to_dict()
    payload[field] = [] if field == "required_outputs" else "changed"
    with pytest.raises(ValueError):
        RootRequest.from_dict(payload)


def test_failed_interpretation_checkpoint_fences_the_next_model_and_tool():
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelTurn
    from intelligence.services.episode_store import MemoryEpisodeStore
    from intelligence.services.research_plan import plan_to_public_dict
    ctx = context("interpretation-store-failure")
    seen = []

    class Store(MemoryEpisodeStore):
        failed = False

        def put_state(self, episode_id, state):
            if state.authorization_snapshot.get("interpretation") is not None:
                self.failed = True
                raise OSError("disk full at interpretation admission")
            return super().put_state(episode_id, state)

    class Model:
        calls = 0

        def complete(self, **kwargs):
            self.calls += 1
            assert self.calls == 1, "failed save must fence further provider effects"
            return ModelTurn(json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))}), ())

    store, model = Store(), Model()
    result = ContinuousAgentEpisode(model, store=store).run(task_frame=frame(), context=ctx, registry=_registry(seen))
    assert store.failed
    assert result.persistence == "failed" and result.stop_reason == "storage_failed"
    assert result.usage.tool_calls == 0 and not seen and model.calls == 1


@pytest.mark.parametrize("boundary", ["cancel", "deadline", "stage", "repair"])
def test_sdk_interpretation_respects_execution_boundary(boundary, monkeypatch):
    from intelligence.runtime import openai_agents_runtime as sdk
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.services.research_plan import plan_to_public_dict
    ctx = context(f"sdk-boundary-{boundary}")
    cancelled = [False]
    seen = []
    state = sdk._AgentsRunState(registry=_registry(seen), context=ctx, is_cancelled=lambda: cancelled[0], tool_stage_expires_at=10**20)
    if boundary == "cancel":
        cancelled[0] = True
    if boundary == "deadline":
        monkeypatch.setattr(type(ctx.deadline), "expired", property(lambda self: True))
    if boundary == "stage":
        monkeypatch.setattr(sdk, "monotonic", lambda: 10**21)
    class MustNotAdmit(FinanceResearchHarness):
        def admit_interpretation(self, plan, *, context):
            raise AssertionError("runtime boundary must reject before domain admission")

    feedback = state.observe_model_response(
        json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))}),
        False, MustNotAdmit(), allow_plan=boundary != "repair",
    )
    assert "PLAN cancelled or research stage closed" in feedback
    assert state.active_context is ctx and state.plan is None
    assert state.invoke("market_data", {"query": "bad"})["error"] == "invalid_plan"
    assert not seen


@pytest.mark.parametrize("backend", ["continuous", "sdk"])
def test_repair_does_not_admit_or_dispatch_new_interpretation(backend):
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
    from intelligence.services.agent_runtime import ModelTurn, ModelToolCall
    from intelligence.services.research_plan import plan_to_public_dict
    from intelligence.tests.test_episode_session import _goal
    ctx = context(f"interpretation-repair-{backend}")
    candidate = json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))})
    stale = json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract), revision=2, base_revision=1))})
    seen = []

    class Model:
        turns = 0

        def complete(self, **kwargs):
            self.turns += 1
            if self.turns == 1:
                return ModelTurn(candidate, ())
            if self.turns == 2:
                return ModelTurn("", (ModelToolCall("first", "market_data", {"query": "first"}),))
            if self.turns == 3:
                return ModelTurn(_finish(), ())
            assert self.turns == 4
            return ModelTurn(stale, (ModelToolCall("bad", "market_data", {"query": "bad"}),))

    calls = []

    def runner(request):
        calls.append(request)
        if len(calls) == 1:
            request.on_model_response(candidate, False)
            request.on_model_response("", True)
            request.tools[0].invoke({"query": "first"})
            return AgentsSdkResult(_finish(), 3, continuation_input=[])
        assert "解释方法而非判断当前市场" in request.input
        assert "PLAN cancelled or research stage closed" in request.on_model_response(stale, True)
        assert request.tools[0].invoke({"query": "bad"})["error"] == "invalid_plan"
        return AgentsSdkResult(_finish(), 1, continuation_input=[])

    runtime = GLMAgentRuntime(client=Model()) if backend == "continuous" else OpenAIAgentsRuntime(runner=runner, backend="sdk_glm", model_name="offline")
    session = runtime.start(frame(), context=ctx, registry=_registry(seen))
    initial = session.outcome
    result = session.resume(replace(_goal(ctx.contract.task_id), missing_answer_elements=(), missing_evidence_modes=()))
    assert len(seen) == 1 and result.usage.tool_calls == 1
    assert result.plan == initial.plan and result.plan.interpretation.base_revision == 0
    assert result.evidence == initial.evidence
    assert result.stop_reason == ("invalid_repair_plan" if backend == "continuous" else "repair_model_finish")
    assert any(event.kind == "invalid_action" for event in result.events[len(initial.events):])


def test_sdk_plan_segments_share_total_timeout_turn_cap_and_provider_history(monkeypatch):
    import asyncio
    from agents import Model, ModelResponse, Runner
    from agents.usage import Usage
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText
    from intelligence.runtime.openai_agents_runtime import AgentsSdkRequest, _run_openai_agents_sdk, build_agents_model_settings
    inputs, caps, timeouts = [], [], []
    run, wait_for = Runner.run, asyncio.wait_for

    async def record_run(*args, **kwargs):
        caps.append(kwargs["max_turns"])
        return await run(*args, **kwargs)

    async def record_wait(awaitable, timeout):
        timeouts.append(timeout)
        return await wait_for(awaitable, timeout)

    monkeypatch.setattr(Runner, "run", record_run)
    monkeypatch.setattr(asyncio, "wait_for", record_wait)

    class PlanModel(Model):
        async def get_response(self, system_instructions, input, **kwargs):
            inputs.append(input)
            text = f"PLAN-{len(inputs)}"
            return ModelResponse(output=[ResponseOutputMessage(
                id=text, role="assistant", status="completed", type="message",
                content=[ResponseOutputText(annotations=[], type="output_text", text=text)],
            )], usage=Usage(requests=1, input_tokens=10, output_tokens=3), response_id=text)

        def stream_response(self, *args, **kwargs):
            raise AssertionError("non-streaming only")

    result = _run_openai_agents_sdk(AgentsSdkRequest(
        instructions="offline test", input="original question", tools=(), max_turns=3,
        timeout=9.0, backend="sdk_glm", model_name="offline", model=PlanModel(),
        model_settings=build_agents_model_settings("sdk_glm"),
        on_model_response=lambda text, tools: f"accepted {text}",
    ))
    assert caps == [3, 2, 1] and timeouts == [9.0]
    assert result.llm_calls == 3 and result.input_tokens == 30 and result.output_tokens == 9
    assert result.final_output == "PLAN-3"  # cap reached: no hidden fourth segment
    history = json.dumps(inputs[2], ensure_ascii=False)
    assert "original question" in history and "accepted PLAN-1" in history and "accepted PLAN-2" in history


def test_sdk_timeout_after_acceptance_retains_goal_for_same_session_repair():
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
    from intelligence.services.research_plan import plan_to_public_dict
    from intelligence.tests.test_episode_session import _goal
    ctx = context("interpretation-timeout-repair")
    calls = []

    def runner(request):
        calls.append(request)
        if len(calls) == 1:
            request.on_model_response(json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))}), False)
            raise TimeoutError("offline timeout after accepted goal")
        task = json.loads(request.input)
        assert task["request_interpretation"]["interpretation"]["revision"] == 1
        assert task["request_interpretation"]["root_request"]["raw_question"] == frame().raw_question
        assert not request.tools
        return AgentsSdkResult(json.dumps({"status": "partial", "draft": "尚缺依据", "gaps": ["待补依据"], "bindings": []}), 1)

    runtime = OpenAIAgentsRuntime(runner=runner, backend="sdk_glm", model_name="offline")
    session = runtime.start(frame(), context=ctx, registry=_registry([]))
    original = session.outcome
    assert original.stop_reason == "sdk_timeout" and original.plan.interpretation is not None
    repaired = session.resume(replace(_goal(ctx.contract.task_id), remaining_calls=0, missing_answer_elements=(), missing_evidence_modes=()))
    assert len(calls) == 2 and repaired.stop_reason != "sdk_run_error"
    assert repaired.plan == original.plan


@pytest.mark.parametrize("backend", ["continuous", "sdk"])
def test_revision_keeps_spent_budget_evidence_and_query_dedup(backend):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
    from intelligence.services.agent_runtime import ModelTurn, ModelToolCall
    from intelligence.services.research_plan import plan_to_public_dict
    ctx = context(f"spent-interpretation-{backend}")
    budget = ctx.root_budget
    initial_calls = budget.remaining_calls
    candidate = json.dumps({"kind": "PLAN", **plan_to_public_dict(plan(proposal(ctx.contract)))})
    seen = []
    turns = [
        ModelTurn("", (ModelToolCall("before", "market_data", {"query": "same"}),)),
        ModelTurn(candidate, ()),
        ModelTurn("", (ModelToolCall("after", "market_data", {"query": "same"}),)),
        ModelTurn(_finish(), ()),
    ]

    class Model:
        def complete(self, **kwargs):
            return turns.pop(0)

    def runner(request):
        request.on_model_response("", True)
        before = request.tools[0].invoke({"query": "same"})
        spent_calls = budget.remaining_calls
        assert before["evidence_hashes"] == ["method-hash"]
        request.on_model_response(candidate, False)
        assert budget.remaining_calls == spent_calls
        request.on_model_response("", True)
        assert request.tools[0].invoke({"query": "same"})["error"] == "duplicate_query"
        return AgentsSdkResult(_finish(), 4)

    runtime = ContinuousAgentEpisode(Model()) if backend == "continuous" else OpenAIAgentsRuntime(runner=runner, backend="sdk_glm", model_name="offline")
    result = runtime.run(task_frame=frame(), context=ctx, registry=_registry(seen))
    assert len(seen) == 1 and result.usage.tool_calls == 1
    assert budget.remaining_calls == initial_calls - 1
    assert len(result.evidence) == 1 and result.evidence[0].content_hash == "method-hash"
    assert result.plan.interpretation is not None
    assert any(event.kind == "tool_error" and event.payload.get("error") == "duplicate_query" for event in result.events)
