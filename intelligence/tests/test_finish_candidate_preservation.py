"""Pre-admission prose is not a completion certificate (live turn-6/7 shapes)."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.historical_research.intent import HistoryIntent
from intelligence.services.research_annotations import CANDIDATE_REVIEW_NOTICE
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput, ResearchDeadline, ResearchPolicy, ResearchRunContext, ResearchTaskContract,
)
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.task_frame import TaskFrame


FIRST = "**板块比较**\n\n光纤趋势较强，但放量滞涨须警惕；汽车偏弱势修复。[E1]"
SECOND = "**历史边界**\n\n已有相似窗口，但仍缺随后收益及失败案例，不能当成胜率。[E1]"
LAST = "最新补充：只把相似窗口作为发现线索，不把热度当成上涨概率。[E1]"


class Model:
    def __init__(self, turns):
        self.turns = iter(turns)
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        turn = next(self.turns)
        if isinstance(turn, Exception):
            raise turn
        return turn


def setup_episode():
    frame = TaskFrame(
        raw_question="这里的行情哪个板块更有机会，历史上有相似的阶段吗",
        user_goal="比较板块及历史", question_type="comparison_analog", subject="A股",
        subject_kind="market_pattern", market_scope="A股", timeframe="最近交易日",
        required_outputs=("direct_assessment",), assumptions=(), ambiguities=(),
        clarification_question=None, evidence_policy="current_market_scenarios", confidence=0.95,
    )
    context = ResearchRunContext(
        contract=ResearchTaskContract(
            task_id="candidate-test", question=frame.raw_question, subject=frame.subject,
            subject_kind=frame.subject_kind, question_type=frame.question_type,
            required_outputs=(RequiredOutput("direct_assessment", "比较板块", ("market_data",), True),),
            allowed_capabilities=("market_data",), research_tier="quick", freshness="current",
            timeframe=frame.timeframe, evidence_plan=EvidencePlan(), task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(60), policy=ResearchPolicy("quick", 8, 60, 0),
        trace_parent_id="candidate-test", today="2026-09-18", latest_data_date="2026-09-17",
        history_intent=HistoryIntent("historical_comparison"),
    )
    context.history_results.append({
        "operation": "find_analogues", "purpose": "historical_comparison", "status": "ok",
        "query_id": "analogue-1", "result_ref": "analogue-result",
    })
    card = AgentEvidence(
        tool="market_data", title="同窗板块比较", detail="光纤较强，汽车修复，类比不是验证。",
        source="本地行情", source_date="2026-09-17", content_hash="collected-evidence",
    )
    def runner(query, _context):
        return [card], query, ProviderTrace(provider="test", capability="market_data", status="success", result_count=1)
    registry = ResearchToolRegistry((ToolSpec(
        name="market_data", capability="market_data", description="行情", cost="local", freshness="current", runner=runner,
    ),))
    return frame, context, registry, (card,)


def envelope(draft=SECOND, *, history=True, ref="E1"):
    value = {
        "status": "partial", "draft": draft, "gaps": [],
        "bindings": [{"output_id": "direct_assessment", "evidence_hashes": [ref], "basis": "evidence", "gap": ""}],
    }
    if history:
        value["history_research"] = {
            "purpose": "historical_comparison", "result_refs": ["analogue-1"],
            "claim_level": "historical_comparison", "research_only": True,
            "promotion_eligible": False, "decision_eligible": False,
        }
    return value


def turn(value):
    return ModelTurn(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), (), "scripted", "")


def test_format_then_history_gap_keeps_tools_and_both_drafts():
    frame, context, registry, _ = setup_episode()
    model = Model([
        ModelTurn("", (ModelToolCall("q1", "market_data", {"query": "同窗比较"}),), "scripted", ""),
        turn(FIRST + "\n\n" + json.dumps(envelope("摘要", history=True), ensure_ascii=False)),
        turn(envelope()),
        turn(envelope(LAST, history=False)),
    ])
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert model.calls[3]["tools"], "格式错不能耗掉补历史的机会"
    assert FIRST in outcome.draft and SECOND in outcome.draft and LAST in outcome.draft
    assert outcome.status == "partial"
    assert outcome.usage.tool_calls == 1 and outcome.usage.llm_calls == 4
    assert not any(e.kind == "finalization_recovery_started" for e in outcome.events)
    assert "继续" in model.calls[3]["messages"][-1]["content"]
    assert [e.payload["code"] for e in outcome.events if e.kind == "invalid_action"] == ["not_json_object", "history_missing_comparison"]


@pytest.mark.parametrize("mixed", [False, True])
def test_rejected_candidate_is_not_admitted(mixed):
    _, context, registry, evidence = setup_episode()
    raw = json.dumps(envelope(), ensure_ascii=False)
    admission = FinanceResearchHarness().admit_finish(FIRST + "\n\n" + raw if mixed else raw, context=context, evidence=evidence, registry=registry)
    assert not admission.accepted and admission.status is None
    assert admission.candidate is not None
    assert SECOND in admission.candidate.draft
    assert (FIRST in admission.candidate.draft) is mixed


@pytest.mark.parametrize("attack", ["forged", "hidden_forgery", "foreign", "history_forged", "hidden_history_forgery", "duplicate", "nested_duplicate", "tool", "ambiguous", "trailing", "embedded_fence", "secret_only"])
def test_candidate_extraction_fails_closed(attack):
    _, context, registry, evidence = setup_episode()
    value = envelope()
    if attack in {"forged", "hidden_forgery"}:
        value["bindings"][0]["evidence_hashes"] = ["invented-hash"]
        if attack == "hidden_forgery":
            value["status"] = "bad"  # earlier FORMAT must not mask later integrity
    if attack == "foreign":
        value["task_frame_hash"] = "foreign-task"
    if attack in {"history_forged", "hidden_history_forgery"}:
        value["history_research"]["result_refs"] = ["never-executed"]
        if attack == "hidden_history_forgery":
            value["history_research"]["decision_eligible"] = True
    if attack == "tool":
        value["tool_calls"] = [{"name": "web_fetch"}]
    if attack == "secret_only":
        value["draft"] = 'api_key="test。secret尾部"'
    raw = json.dumps(value, ensure_ascii=False)
    if attack == "duplicate":
        raw = raw[:-1] + ',"draft":"second"}'
    if attack == "nested_duplicate":
        raw = raw.replace('"output_id": "direct_assessment"', '"output_id":"direct_assessment","output_id":"direct_assessment"')
    if attack == "ambiguous":
        raw = FIRST + "\n" + raw + "\n" + raw
    if attack == "trailing":
        raw += "\nnot part of the envelope"
    if attack == "embedded_fence":
        raw = FIRST + "\n```json\n" + raw + "\n```"
    admission = FinanceResearchHarness().admit_finish(raw, context=context, evidence=evidence, registry=registry)
    assert not admission.accepted
    assert admission.candidate is None


def test_recovery_receives_whole_candidate_and_its_used_evidence():
    frame, context, registry, evidence = setup_episode()
    value = envelope(SECOND * 90)
    admission = FinanceResearchHarness().admit_finish(value, context=context, evidence=evidence, registry=registry)
    assert admission.candidate is not None
    cards = evidence + tuple(replace(evidence[0], content_hash=f"card-{i}", detail=f"观察{i}：" + "具体观察" * 150) for i in range(20))
    model = Model([turn(envelope(LAST, history=False))])
    EpisodeFinalizer(model).recover(
        task_frame=frame, context=context, evidence=cards, gaps=(), failure_reason="invalid_model_finish",
        candidate_drafts=(admission.candidate.draft + " 另一依据[E21]。",),
        evidence_priority=tuple(card.content_hash for card in cards[:16]),
    )
    payload = json.loads(model.calls[0]["messages"][1]["content"])
    assert admission.candidate.draft in payload["candidate_drafts"][0]
    by_id = {card["evidence_id"]: card for card in payload["evidence"]}
    assert len(by_id) > 12
    for index in (*range(1, 17), 21):
        assert by_id[f"E{index}"]["detail"] == cards[index - 1].detail
        assert "content_hash" not in by_id[f"E{index}"]
    assert [item["evidence_id"] for item in payload["evidence"][:16]] == [f"E{i}" for i in range(1, 17)]
    assert 0 < model.calls[0]["timeout"] <= 20
    assert model.calls[0]["tools"] == []
    assert "1200" not in model.calls[0]["messages"][0]["content"]


def test_normal_prompt_does_not_cap_analysis_at_1000_characters():
    frame, context, registry, _ = setup_episode()
    harness = FinanceResearchHarness()
    system, _ = harness.assemble_prompt(frame, context, registry)
    assert "1000 汉字" not in system
    assert "1000 汉字" not in harness.steering_message("begin_finalization", detail="deadline")


@pytest.mark.parametrize("failure", ["invalid", "provider", "tools"])
def test_candidate_survives_failed_recovery_without_extra_calls(failure):
    frame, context, registry, _ = setup_episode()
    context = replace(context, policy=replace(context.policy, max_steps=1))
    final_turn = {
        "invalid": turn("still not JSON"),
        "provider": RuntimeError("provider unavailable"),
        "tools": ModelTurn("", (ModelToolCall("forbidden", "market_data", {"query": "not executed"}),), "scripted", ""),
    }[failure]
    model = Model([
        ModelTurn("", (ModelToolCall("q1", "market_data", {"query": "同窗比较"}),), "scripted", ""),
        turn(envelope()), final_turn,
    ])
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert SECOND in outcome.draft
    assert outcome.status == "partial" and outcome.stop_reason == "finalization_recovery_failed"
    assert outcome.usage.tool_calls == 1 and len(model.calls) == 3
    payload = json.loads(model.calls[-1]["messages"][1]["content"])
    assert SECOND in payload["candidate_drafts"][0]
    assert model.calls[-1]["tools"] == []


@pytest.mark.parametrize("mutation", ["foreign", "semantics", "reorder", "unknown_revival", "duplicate"])
def test_retained_candidate_cannot_change_evidence_identity(mutation):
    from intelligence.services.finish_candidate import merge_finish_candidates
    frame, context, registry, evidence = setup_episode()
    value = envelope()
    if mutation == "unknown_revival":
        value["draft"] += " 尚未核实的引用[E2]。"
    candidate = FinanceResearchHarness().admit_finish(value, context=context, evidence=evidence, registry=registry).candidate
    assert candidate is not None
    other = replace(evidence[0], content_hash="other-card")
    current = evidence
    if mutation == "foreign":
        candidate = replace(candidate, task_frame_hash="another-task")
    elif mutation == "semantics":
        current = (replace(evidence[0], source_date="2020-01-01"),)
    elif mutation == "reorder":
        current = (other, *evidence)
    elif mutation == "unknown_revival":
        current = (*evidence, other)
    else:
        current = (*evidence, *evidence)
    body, bindings, count = merge_finish_candidates(
        (candidate,), task_frame_hash=frame.task_frame_hash, evidence=current,
        draft=LAST, bindings=(), contract=context.contract,
    )
    assert body == LAST and not bindings and count == 0


def test_partial_candidate_stays_partial_even_when_judge_passes():
    from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.finish_candidate import CANDIDATE_REVIEW_NOTICE
    frame, context, registry, evidence = setup_episode()
    admission = FinanceResearchHarness().admit_finish(envelope(), context=context, evidence=evidence, registry=registry)
    candidate = admission.candidate
    assert candidate is not None
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash, status="partial", draft=candidate.draft,
        evidence=evidence, bindings=candidate.bindings, gaps=(CANDIDATE_REVIEW_NOTICE,),
        traces=(), stop_reason="invalid_model_finish", usage=AgentUsage(1, 0),
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
    )
    reviewed = SemanticEpisodeVerifier(judge_fn=lambda _request: {"passed": True, "rejected_sentence_indexes": [], "issues": []}).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, outcome), deadline=context.deadline,
    )
    assert candidate.draft in reviewed.public_answer
    assert reviewed.status == "partial"
    assert CANDIDATE_REVIEW_NOTICE in reviewed.public_answer


@pytest.mark.parametrize("backend", ["sdk_glm", "sdk_gpt"])
def test_sdk_retains_candidate_without_own_hidden_repair(backend):
    from intelligence.runtime.openai_agents_runtime import OpenAIAgentsRuntime, AgentsSdkResult
    frame, context, registry, _ = setup_episode()
    calls = []
    def runner(request):
        calls.append(request)
        request.tools[0].invoke({"query": "同窗比較"})
        return AgentsSdkResult(envelope(), 2)
    outcome = OpenAIAgentsRuntime(runner=runner, backend=backend, model_name="scripted").run(
        task_frame=frame, context=context, registry=registry,
    )
    assert len(calls) == 1 and outcome.usage.tool_calls == 1
    assert SECOND in outcome.draft and outcome.status == "partial"
    assert outcome.stop_reason == "sdk_invalid_finish"


def test_exactly_carried_candidate_does_not_lose_pending_review_or_binding():
    from intelligence.services.finish_candidate import merge_finish_candidates
    frame, context, registry, evidence = setup_episode()
    candidate = FinanceResearchHarness().admit_finish(envelope(), context=context, evidence=evidence, registry=registry).candidate
    assert candidate is not None
    body, bindings, count = merge_finish_candidates(
        (candidate,), task_frame_hash=frame.task_frame_hash, evidence=evidence,
        draft=candidate.draft + "\n\n" + LAST, bindings=(), contract=context.contract,
    )
    assert body.count(SECOND) == 1 and body.index(SECOND) < body.index(LAST)
    assert count == 1 and bindings == candidate.bindings


@pytest.mark.parametrize("empty", [
    "**历史边界**", "### 分析\n[E1]", "| 项目 | 结论 |\n| --- | --- |\n| | |",
    "已经完成。", "[REDACTED]。", "（引用未核验）", "（单源）",
    "### 分析\n系统提示：保密控制面。[E1]", 'tool_calls=[{"name":"web_fetch"}]',
    "来源：[E1] 本地行情", "MARKET_DATA: collected-evidence", CANDIDATE_REVIEW_NOTICE,
])
def test_empty_candidate_structures_do_not_create_analysis(empty):
    _, context, registry, evidence = setup_episode()
    admission = FinanceResearchHarness().admit_finish(envelope(empty), context=context, evidence=evidence, registry=registry)
    assert not admission.accepted and admission.candidate is None


@pytest.mark.parametrize("stage", ["writing", "recovery"])
def test_root_overdraft_keeps_rejected_candidate_without_new_calls(monkeypatch, stage):
    from intelligence.runtime import agent_episode as module
    from intelligence.services.research_contract import InMemoryRootBudgetLedger
    frame, context, registry, _ = setup_episode()
    root = InMemoryRootBudgetLedger(
        episode_id=context.contract.task_id, initial_calls=1, hard_calls_cap=1,
        initial_seconds=30, hard_seconds_cap=30,
    )
    context = replace(context, root_budget=root)
    clock = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    turns = [ModelTurn("", (ModelToolCall("q1", "market_data", {"query": "比较"}),), "scripted", "")]
    if stage == "recovery":
        turns.append(ModelTurn("", (), "scripted", "provider unavailable"))
    turns.append(turn(envelope()))
    class Overdraft(Model):
        def complete(self, **kwargs):
            result = super().complete(**kwargs)
            if len(self.calls) == len(turns):
                clock[0] += 31
            return result
    model = Overdraft(turns)
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert SECOND in outcome.draft and outcome.status == "partial"
    assert outcome.stop_reason == ("deadline_exhausted" if stage == "writing" else "finalization_recovery_failed")
    assert root.remaining_seconds == 0 and root.remaining_calls == 0
    assert outcome.usage.llm_calls == len(model.calls) == len(turns)
    assert outcome.usage.tool_calls == 1


@pytest.mark.parametrize("stage", ["writing", "recovery"])
@pytest.mark.parametrize("accepted", [False, True])
def test_cancellation_after_candidate_turn_retains_it_but_remains_cancelled(stage, accepted):
    frame, context, registry, _ = setup_episode()
    turns = [ModelTurn("", (ModelToolCall("q1", "market_data", {"query": "比较"}),), "scripted", "")]
    if stage == "recovery":
        context = replace(context, policy=replace(context.policy, max_steps=1))
        turns.append(turn("invalid, no draft"))
    turns.append(turn(envelope(history=not accepted)))
    model = Model(turns)
    outcome = ContinuousAgentEpisode(model, is_cancelled=lambda: len(model.calls) >= len(turns)).run(
        task_frame=frame, context=context, registry=registry,
    )
    assert SECOND in outcome.draft
    assert outcome.stop_reason == "cancelled" and outcome.status == "failed"
    assert len(model.calls) == len(turns) and outcome.usage.tool_calls == 1


@pytest.mark.parametrize("backend", ["continuous", "sdk"])
@pytest.mark.parametrize("repair", ["accepted", "rejected"])
@pytest.mark.parametrize("cancel", [False, True])
def test_session_resume_preserves_earlier_analysis_in_order(backend, repair, cancel):
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
    from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
    frame, context, registry, _ = setup_episode()
    followup = envelope(SECOND, history=repair == "rejected")
    if backend == "continuous":
        model = Model([
            ModelTurn("", (ModelToolCall("q1", "market_data", {"query": "比较"}),), "scripted", ""),
            turn(envelope(FIRST, history=False)), turn(followup),
        ])
        runtime = GLMAgentRuntime(client=model, is_cancelled=lambda: cancel and len(model.calls) >= 3)
    else:
        calls = []
        def runner(request):
            calls.append(request)
            if len(calls) == 1:
                request.tools[0].invoke({"query": "比较"})
                return AgentsSdkResult(envelope(FIRST, history=False), 2, continuation_input=object())
            return AgentsSdkResult(followup, 1)
        runtime = OpenAIAgentsRuntime(runner=runner, backend="sdk_gpt", model_name="scripted", is_cancelled=lambda: cancel and len(calls) >= 2)
    session = runtime.start(frame, context=context, registry=registry)
    previous = session.outcome
    goal = RepairGoal(
        episode_id=context.contract.task_id, repair_goal_id="preserve-repair", cycle=1,
        missing_answer_elements=("direct_assessment",), unsupported_claims=(), missing_evidence_modes=(),
        attempted_actions=(), evidence_progress=CoverageDelta(1, 0, 1), remaining_calls=0, remaining_seconds=10,
    )
    updated = session.resume(goal)
    assert FIRST in updated.draft and SECOND in updated.draft
    assert updated.draft.index(FIRST) < updated.draft.index(SECOND)
    assert updated.events[:len(previous.events)] == previous.events
    assert updated.usage.llm_calls == 3 and updated.usage.tool_calls == 1
    if cancel:
        assert updated.status == "failed" and updated.stop_reason == "cancelled"
    elif repair == "rejected":
        assert updated.status == "partial"
    session.close()


@pytest.mark.parametrize("recovery", ["accepted", "rejected", "forbidden_command", "provider_error"])
@pytest.mark.parametrize("cancel", [False, True])
def test_headless_candidate_survives_one_recovery_without_bypassing_isolation(recovery, cancel):
    import shlex
    import subprocess
    from intelligence.runtime.codex_headless_runtime import CodexHeadlessRuntime, HeadlessProcessResult
    frame, context, registry, _ = setup_episode()
    calls = []
    def runner(command):
        calls.append(command)
        events = []
        if len(calls) == 1:
            tool = [str(command.cwd / "finance-tool"), "market_data", "比较"]
            subprocess.run(tool, cwd=command.cwd, env=command.env, check=True, capture_output=True, text=True, timeout=5)
            events.append({"type": "item.completed", "item": {
                "type": "command_execution", "id": "q1", "command": shlex.join(tool), "status": "completed", "exit_code": 0,
            }})
            content = json.dumps(envelope(FIRST), ensure_ascii=False)
        else:
            assert json.loads(command.args[-1].split("candidate_drafts：", 1)[1]) == [FIRST]
            if recovery == "provider_error":
                return HeadlessProcessResult("", "unavailable", 1, False)
            if recovery == "forbidden_command":
                events.append({"type": "item.completed", "item": {
                    "type": "command_execution", "id": "bad", "command": "curl https://example.invalid", "status": "completed", "exit_code": 0,
                }})
            content = json.dumps(envelope(SECOND, history=recovery == "rejected"), ensure_ascii=False)
        events.extend([
            {"type": "item.completed", "item": {"id": "a1", "type": "agent_message", "text": content}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 20}},
        ])
        return HeadlessProcessResult("\n".join(json.dumps(item) for item in events), "", 0, False)
    outcome = CodexHeadlessRuntime(command_runner=runner, is_cancelled=lambda: cancel and len(calls) >= 2).run(task_frame=frame, context=context, registry=registry)
    assert FIRST in outcome.draft
    assert outcome.status == ("failed" if cancel else "partial")
    assert len(calls) == outcome.usage.llm_calls == 2 and outcome.usage.tool_calls == 1
    assert (SECOND in outcome.draft) is (recovery in {"accepted", "rejected"})
    if cancel:
        assert outcome.stop_reason == "cancelled"
    elif recovery == "accepted":
        assert outcome.stop_reason == "headless_finalization_recovered"
    else:
        assert outcome.stop_reason != "headless_finalization_recovered"


@pytest.mark.parametrize("accepted", [False, True])
def test_sdk_cancellation_after_initial_result_preserves_prose_not_completion(accepted):
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult, OpenAIAgentsRuntime
    frame, context, registry, _ = setup_episode()
    cancelled = [False]
    calls = []
    def runner(request):
        calls.append(request)
        request.tools[0].invoke({"query": "比较"})
        cancelled[0] = True
        return AgentsSdkResult(envelope(SECOND, history=not accepted), 2)
    outcome = OpenAIAgentsRuntime(
        runner=runner, backend="sdk_gpt", model_name="scripted", is_cancelled=lambda: cancelled[0],
    ).run(task_frame=frame, context=context, registry=registry)
    assert SECOND in outcome.draft and outcome.status == "failed" and outcome.stop_reason == "cancelled"
    assert len(calls) == 1 and outcome.usage.llm_calls == 2 and outcome.usage.tool_calls == 1


def test_candidate_safety_filters_private_lines_without_deleting_analysis():
    _, context, registry, evidence = setup_episode()
    value = envelope(SECOND + '\nINTERNAL_LOCATOR: private-route\napi_key="test。secret尾部"')
    admission = FinanceResearchHarness().admit_finish(value, context=context, evidence=evidence, registry=registry)
    assert admission.candidate is not None and SECOND in admission.candidate.draft
    assert "private-route" not in admission.candidate.draft and "secret尾部" not in admission.candidate.draft


def test_candidate_notice_alone_does_not_spend_judge_call():
    from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    frame, context, _, evidence = setup_episode()
    called = []
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash, status="partial", draft=CANDIDATE_REVIEW_NOTICE,
        evidence=evidence, traces=(), gaps=(CANDIDATE_REVIEW_NOTICE,),
        stop_reason="invalid_model_finish", bindings=(), usage=AgentUsage(),
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
    )
    reviewed = SemanticEpisodeVerifier(judge_fn=lambda request: called.append(request)).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, outcome), deadline=context.deadline,
    )
    assert not called and reviewed.delivery_mode == "no_public_analysis"


def test_candidate_material_merge_counts_actual_combined_length():
    from intelligence.services.finish_candidate import merge_finish_candidates
    from intelligence.services.material_delivery import material_question_outputs, question_body, question_sections
    from intelligence.tests.test_e2_material_delivery import setup_delivery, outcome_for, finish_for
    frame, context = setup_delivery(memo=True)
    registry = ResearchToolRegistry(())
    original = outcome_for(context, draft="## q1\n甲的原分析。\n\n## q2\n" + "甲" * 120)
    value = finish_for(original)
    value["status"] = "wrong format"
    admission = FinanceResearchHarness().admit_finish(value, context=context, evidence=original.evidence, registry=registry)
    assert not admission.accepted and admission.candidate is not None
    body, _, retained = merge_finish_candidates(
        (admission.candidate,), task_frame_hash=frame.task_frame_hash, evidence=original.evidence,
        draft="## q1\n甲的补充分析。\n\n## q2\n" + "乙" * 120,
        bindings=original.bindings, contract=context.contract,
    )
    assert retained == 1 and "甲" * 120 in body and "乙" * 120 in body
    sections = question_sections(body)
    assert set(sections) == {"q1", "q2"} and all(len(parts) == 1 for parts in sections.values())
    spec = next(item for item in material_question_outputs(context.contract) if item.question_id == "q2")
    assert question_body(spec, body) == "", "preservation must not exempt old text from the user's limit"
