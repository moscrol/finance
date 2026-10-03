"""Methods guide the author; only the task/evidence contract owns completion.

Real continuous Episode and adapter with a scripted model/source/judge. These
checks prove wiring and budget effects, not weak/strong model answer quality.
"""
from dataclasses import replace
import json
import socket
from uuid import uuid4

import pytest

from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
from intelligence.runtime.repair_budget import admit_repair
from intelligence.services import llm_refine, ranking_contract, track_contract
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import EpisodeEvent, ModelToolCall, ModelTurn, OutputEvidenceBinding
from intelligence.services.episode_protocol import EpisodeFinishRejection, validate_episode_finish
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.repair_coordinator import classify_repair_need, progress_from_ledger, warrant_repair
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger, RequiredOutput, ResearchDeadline, ResearchPolicy, ResearchRunContext,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.tests.test_continuous_turn_adapter import _control
from intelligence.tests.test_episode_semantic_verifier import _structural
from intelligence.tests.test_repair_coordinator import _snap

QUESTIONS = (
    "跟踪一下市场需求的新变化，不要登记长期跟踪。",
    "甲公司、乙公司谁更值得优先研究？排个序，不要登记长期跟踪。",
)
PROSE = "需求仍待确认，改善情况需要后续观察 E1。"
DRAFTS = (
    PROSE,
    "## 当前结论\n" + PROSE + "\n\n- 若需求仍未改善，应重新评估 E1。",
    "无上期基线，本期建立基线。" + PROSE + "复核期限：2026-11-03。\n"
    "## 下期关注清单\n- 若到2026-11-03需求仍未改善，应重新评估 E1。",
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    attempts = []

    def deny(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("expression advisory tests must stay offline")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")
    yield
    assert not attempts


def setup(question=QUESTIONS[0], draft=PROSE, extra=None, seconds_headroom=60):
    frame, verified = _structural(draft, detail=PROSE)
    outputs = verified.contract.required_outputs + ((extra,) if extra else ())
    frame = replace(frame, raw_question=question, question_type="general_finance_qa",
                    required_outputs=tuple(row.output_id for row in outputs))
    contract = replace(verified.contract, task_id=f"expression-{uuid4().hex}",
                       question=question, question_type=frame.question_type,
                       task_frame_hash=frame.task_frame_hash, required_outputs=outputs)
    context = ResearchRunContext(
        contract=contract, deadline=ResearchDeadline.from_timeout(120),
        policy=ResearchPolicy("standard", 3, 60, 20), trace_parent_id=contract.task_id,
        today="2026-10-03", latest_data_date="2026-10-02",
        root_budget=InMemoryRootBudgetLedger(
            episode_id=contract.task_id, initial_calls=3, hard_calls_cap=3,
            initial_seconds=60, hard_seconds_cap=60 + seconds_headroom,
        ),
    )
    outcome = replace(verified.outcome, task_frame_hash=frame.task_frame_hash,
                      events=(replace(verified.outcome.events[0], payload={"task_frame_hash": frame.task_frame_hash}),))
    return frame, context, outcome


def finish(draft=PROSE, output_ids=("direct_assessment",), ref="E1"):
    return {"status": "completed", "draft": draft, "gaps": [], "bindings": [
        {"output_id": output_id, "evidence_hashes": [ref], "gap": ""} for output_id in output_ids
    ]}


@pytest.mark.parametrize("seconds_headroom", [0, 60])
@pytest.mark.parametrize("backend", ["glm", "sdk"])
@pytest.mark.parametrize("question", QUESTIONS)
@pytest.mark.parametrize("draft", DRAFTS, ids=["prose", "custom-headings", "track-template"])
def test_real_episode_does_not_spend_a_repair_for_template_absence(question, draft, backend, seconds_headroom):
    frame, context, _ = setup(question, draft, seconds_headroom=seconds_headroom)
    calls, actions, reviews = [], [], []
    before = context.root_budget.to_snapshot()
    root = context.root_request

    class Model:
        def complete(self, *, messages, tools, timeout):
            calls.append(messages)
            assert len(calls) <= 2, "template absence triggered another model call"
            if len(calls) == 1:
                return ModelTurn("", (ModelToolCall("observe", "market_data", {"query": "需求"}),))
            return ModelTurn(json.dumps(finish(draft), ensure_ascii=False), ())

    def source(query, tool_context):
        actions.append(query)
        evidence = AgentEvidence("market_data", "需求", PROSE, "离线观察",
                                 source_date="2026-10-02", content_hash="expression-observation")
        return [evidence], PROSE, ProviderTrace("offline", "market_data", "success")

    def judge(request):
        reviews.append(request)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    registry = ResearchToolRegistry((ToolSpec("market_data", "market_data", "观察", "local", "current", source),))
    sdk_requests = []

    def runner(request):
        sdk_requests.append(request)
        assert len(sdk_requests) == 1, "template absence triggered another SDK segment"
        request.tools[0].invoke("需求")
        return AgentsSdkResult(json.dumps(finish(draft), ensure_ascii=False), 2)

    runtime = GLMAgentRuntime(client=Model()) if backend == "glm" else OpenAIAgentsRuntime(
        runner=runner, backend="sdk_glm", model_name="offline",
    )
    result = ContinuousTurnAdapter(
        runtime=runtime, mode="on",
        context_factory=lambda *_a, **_kw: context, registry_factory=lambda *_a, **_kw: registry,
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(frame=frame, control=_control(frame))
    assert result.status == "completed", result.private_artifact
    assert result.answer == draft
    assert result.open_gaps == ()
    artifact = result.private_artifact
    assert artifact["repair_attempts"] == artifact["backfill_turns"] == 0
    assert artifact["structural_verifier"]["missing_outputs"] == []
    assert artifact["semantic_verifier"]["verified"]["missing_outputs"] == []
    assert len(calls) == (2 if backend == "glm" else 0)
    assert len(sdk_requests) == (1 if backend == "sdk" else 0)
    assert actions == ["需求"] and reviews
    model_input = str(calls[0]) if backend == "glm" else str(sdk_requests[0].input)
    heading = "跟踪方法建议（可选）" if question == QUESTIONS[0] else "排序方法建议（可选）"
    assert heading in model_input
    assert context.root_request is root
    after = context.root_budget.to_snapshot()
    for key in ("allocated_calls", "allocated_seconds", "hard_calls_cap", "hard_seconds_cap"):
        assert after[key] == before[key]
    for key in ("track_contract", "ranking_contract"):
        receipt = artifact[key]
        assert receipt["authority"] == "advisory" and receipt["schema_version"] == 2
        assert receipt["missing_outputs"] == []
        assert "missing_template_elements" in receipt


@pytest.mark.parametrize("output_id", ["track_ttl", "ranking_matrix", "user_requested_appendix"])
def test_same_named_user_obligation_is_not_erased_or_reclassified_by_template_name(output_id):
    extra = RequiredOutput(output_id, "用户明确要求的补充", ("market_data",), origin="user_request")
    _, context, outcome = setup(extra=extra)
    verified = verify_episode_outcome(context.contract, outcome)
    assert output_id in verified.missing_outputs
    need = classify_repair_need(outcome, verified, rejected_claims=(), semantic_gap_outputs=())
    assert output_id in need.missing_outputs
    assert not need.shape.contract_rewrite  # a name is not permission for tool-closed rewrite
    with pytest.raises(EpisodeFinishRejection, match="required output lacks evidence"):
        validate_episode_finish(finish(ref=outcome.evidence[0].content_hash), context=context, evidence=outcome.evidence)
    bound = replace(outcome, bindings=(*outcome.bindings, OutputEvidenceBinding(output_id, (outcome.evidence[0].content_hash,))))
    assert verify_episode_outcome(context.contract, bound).missing_outputs == ()
    assert validate_episode_finish(finish(output_ids=("direct_assessment", output_id)), context=context, evidence=outcome.evidence).status == "completed"
    with pytest.raises(EpisodeFinishRejection) as error:
        validate_episode_finish(finish(output_ids=("direct_assessment", output_id), ref="invented"), context=context, evidence=outcome.evidence)
    assert error.value.code == "forged_hash"


@pytest.mark.parametrize("module,heading", [(track_contract, "跟踪方法建议"), (ranking_contract, "排序方法建议")])
def test_episode_methods_are_visible_optional_and_do_not_prescribe_a_fixed_form(module, heading):
    rule = module.build_track_guidance_for_episode() if module is track_contract else module.build_ranking_guidance_for_episode()
    assert heading in rule and "可选" in rule
    assert "任务合同" in rule and "证据" in rule
    for retired in ("必须按此结构", "表头逐字", "结尾必给", "默认 30 天", "默认 90 天"):
        assert retired not in rule


@pytest.mark.parametrize("case", ["allowed", "spent-slot", "no-headroom", "tier-cap", "no-evidence", "no-diagnosis"])
def test_review_only_repair_is_tool_closed_and_consumes_existing_headroom(case):
    _, context, outcome = setup()
    if case == "no-evidence":
        outcome = replace(outcome, evidence=())
    structural = verify_episode_outcome(context.contract, outcome)
    feedback = () if case == "no-diagnosis" else ('{"stage":"judge","sentence":"待修订断言"}',)
    need = classify_repair_need(outcome, structural, rejected_claims=(), semantic_gap_outputs=(), review_feedback=feedback)
    before_progress = _snap(evidence=(), covered=(), gaps=("direct_assessment",), family="market")
    after_progress = _snap(evidence=("e1",), covered=("direct_assessment",), gaps=(), family="market")
    progress = progress_from_ledger(
        before_progress, before_progress if case in {"no-evidence", "no-diagnosis"} else after_progress,
    )
    if case == "spent-slot":
        assert progress.coverage_delta.progressed  # cannot fall through to a tool-open grant
    if case == "no-diagnosis":
        assert not need.shape.delivery
    cycle = 100 if case == "tier-cap" else 1
    root = InMemoryRootBudgetLedger(
        episode_id=context.contract.task_id, initial_calls=3, hard_calls_cap=5,
        initial_seconds=60, hard_seconds_cap=60 if case == "no-headroom" else 120,
    )
    root.consume_call(seconds=5)
    before = root.to_snapshot()
    admission = admit_repair(
        need, warrant_repair(progress, cycle=cycle, research_tier="standard"),
        episode_id=context.contract.task_id, previous_progress=progress,
        remaining_calls=2, remaining_seconds=0 if case == "no-headroom" else 60,
        cycle=cycle, root_budget=root, evidence_count=len(outcome.evidence),
        tools_open=True, allow_delivery_repair=case != "spent-slot",
    )
    if case != "allowed":
        assert admission is None
        assert root.to_snapshot() == before
        return
    assert admission.delivery_only and not admission.goal.reopen_tools
    assert admission.goal.missing_answer_elements == () and admission.goal.unsupported_claims == feedback
    assert admission.goal.remaining_calls == admission.grant.calls_granted == 0
    assert 0 < admission.grant.seconds_granted <= 60
    after = root.to_snapshot()
    assert after["remaining_calls"] == before["remaining_calls"]
    assert after["allocated_calls"] == before["allocated_calls"]
    assert after["hard_seconds_cap"] == before["hard_seconds_cap"]
    assert after["allocated_seconds"] == before["allocated_seconds"] + admission.grant.seconds_granted
    assert after["remaining_seconds"] == before["remaining_seconds"] + admission.grant.seconds_granted
    assert not root.grant(admission.grant)  # no duplicate allocation or refund of spent time


def test_mixed_review_and_delivery_feedback_reaches_same_session_repair(numeric_delete_mode):
    from intelligence.services.episode_session import CallbackEpisodeSession
    from intelligence.tests.test_research_delivery_checks import _financial_evidence

    bad_condition = "若评分低于987654321，则重新评估 E1。"
    draft = PROSE + "2026中报含金量为1.587元/元。" + bad_condition
    frame, context, initial = setup(draft=draft)
    context = replace(context, deadline=ResearchDeadline.from_timeout(0))
    initial = replace(initial, evidence=(*initial.evidence, *_financial_evidence()))
    goals, checks = [], []

    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                goals.append(goal)
                return replace(previous, draft=PROSE, stop_reason="repair_finish", events=(
                    *previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {
                        "task_frame_hash": frame.task_frame_hash,
                    }),
                ))

            return CallbackEpisodeSession(
                episode_id=context.contract.task_id, outcome=initial, resume_callback=resume,
            )

    class Verifier(SemanticEpisodeVerifier):
        def verify(self, **kwargs):
            result = super().verify(**kwargs)
            checks.append(result)
            return result

    # No tool budget remains; both independently produced diagnoses must ride
    # the same existing tool-closed repair, not buy another author turn.
    result = ContinuousTurnAdapter(
        runtime=Runtime(), mode="on",
        context_factory=lambda *_a, **_kw: context, registry_factory=lambda *_a, **_kw: "registry",
        semantic_verifier=Verifier(judge_fn=lambda _request: {
            "passed": True, "rejected_sentence_indexes": [], "issues": [],
        }),
    ).handle(frame=frame, control=_control(frame))
    assert checks[0].sentence_verdicts and checks[0].delivery_repair_notes
    assert len(goals) == 1 and len(checks) == 2
    goal = goals[0]
    assert set(checks[0].delivery_repair_notes) <= set(goal.unsupported_claims)
    anchored = [json.loads(item) for item in goal.unsupported_claims if item.startswith("{")]
    assert any(item["sentence"] == bad_condition for item in anchored)
    assert not any(item.startswith("claim_index:") for item in goal.unsupported_claims)
    assert len(goal.unsupported_claims) == len(set(goal.unsupported_claims))
    assert goal.remaining_calls == 0 and not goal.reopen_tools
    assert result.status == "completed" and result.answer == PROSE


def test_retired_rejection_event_remains_readable_without_an_active_emitter(tmp_path):
    from intelligence.services.episode_store import JsonlEpisodeStore

    store = JsonlEpisodeStore(tmp_path)
    event = EpisodeEvent(1, "finish", {
        "rejection_code": "expression_slot_binding", "rejection_kind": "format",
    })
    store.append("legacy-expression", (event,))
    events, _ = store.load("legacy-expression")
    assert events == (event,)


def test_reranking_reference_does_not_command_a_table_or_freeze_uncovered_variables():
    from intelligence.tests.test_ranking_contract import PRIOR_CONTEXT
    rule = ranking_contract.episode_ranking_rule(
        "如果铜价回落，排序会怎么变", conversation_context=PRIOR_CONTEXT,
    )
    assert "机械" in rule and "参考" in rule
    assert "必须以此为基线" not in rule
    assert "排序不变，需补该变量的敏感性" not in rule
