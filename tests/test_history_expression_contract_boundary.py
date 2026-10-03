"""Historical rank/trace is not a forward priority/watch task.

The saved second live question triggered both forward templates. Test their actual
prompt/repair/receipt/write consumers; deterministic routing is not LLM acceptance.
"""

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from intelligence.runtime.continuous_turn_adapter import (
    ContinuousTurnAdapter,
)
from intelligence.runtime.turn_control_core import TurnControlResult
from intelligence.services import ranking_contract as ranking, track_contract as track
from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_ranking_contract import ANSWER as RANKING_ANSWER
from intelligence.tests.test_research_intent_boundaries import _TRACK_ANSWER
from tests.test_history_live_seams import FIRST, FOLLOWUPS, _decide


FORWARD = "跟踪英维克、申菱环境、高澜股份的新变化，谁更值得优先研究？排个序"
FORWARD_SLOTS = track.TRACK_CONTRACT_OUTPUT_ID_SET | ranking.RANKING_CONTRACT_OUTPUT_ID_SET


def _history_frame(tmp_path):
    store = ConversationStore("history-contract", root=tmp_path / "conversations")
    conv = store.create_conversation()
    first = _decide(store, conv, FIRST)
    second = _decide(store, conv, FOLLOWUPS[0], first.turn_intent, 1)
    assert second.task_frame.history_intent is not None
    return second.task_frame


def _context(frame):
    return build_episode_context(
        frame, task_id=f"history-expression-{uuid4().hex}", today="2026-09-18",
        latest_data_date="2026-09-15", capabilities=("finance_query",),
    )


def _unfulfilled(frame, context):
    return AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="partial",
        draft="尚无可核验的历史原件，不能据此声称样本比较已完成。",
        evidence=(), traces=(), gaps=("缺少历史原件",),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(), usage=AgentUsage(),
    )


def test_original_four_turn_prompts_use_history_not_forward_contracts(tmp_path):
    frozen = Path(__file__).resolve().parents[1] / (
        "docs/verification/history-market-anatomy/fbd8f2a6/questions.json"
    )
    assert json.loads(frozen.read_text())["questions"] == [FIRST, *FOLLOWUPS]
    store = ConversationStore("history-contract", root=tmp_path / "conversation")
    conv = store.create_conversation()
    previous = None
    for n, question in enumerate((FIRST, *FOLLOWUPS)):
        decision = _decide(store, conv, question, previous, n)
        frame = decision.task_frame
        context = _context(frame)
        assert context.history_intent == frame.history_intent
        assert context.history_intent.strict_window
        assert context.information_cutoff.as_of_date.isoformat() == "2026-09-15"
        system, user = FinanceResearchHarness().assemble_prompt(
            frame, context, ResearchToolRegistry(())
        )
        for heading in ("【跟踪方法建议", "【排序方法建议", "【情景树表达契约】"):
            assert heading not in system + user, (n + 1, heading)
        # These are real positive triggers without the authoritative task context.
        if n == 1:
            assert track.parse_track_intent(question, frame.question_type)
            assert ranking.parse_ranking_intent(question, frame.question_type)
        previous = decision.turn_intent


def test_repair_does_not_replace_history_evidence_gaps_with_forward_slots(tmp_path):
    frame = _history_frame(tmp_path)
    context = _context(frame)
    outcome = _unfulfilled(frame, context)
    original = verify_episode_outcome(context.contract, outcome)
    assert original.missing_outputs
    assert not FORWARD_SLOTS.intersection(original.missing_outputs)
    from intelligence.services.repair_coordinator import classify_repair_need

    need = classify_repair_need(outcome, original, rejected_claims=(), semantic_gap_outputs=())
    assert need.missing_outputs == original.missing_outputs
    assert not FORWARD_SLOTS.intersection(need.missing_outputs)
    # Ordinary forward tasks also have no second, name-based completion gate.
    assert not need.shape.contract_rewrite


@pytest.mark.parametrize("contract", [track, ranking], ids=["track", "ranking"])
def test_shared_consumers_accept_authoritative_intent_not_answer_wording(tmp_path, contract):
    frame = _history_frame(tmp_path)
    intent = frame.history_intent
    query = "接着追踪这些个股，再排一下"  # Deliberately depends on inherited task state.
    kw = {"query": query, "question_type": "theme_track", "history_intent": intent}
    parser = contract.parse_track_intent if contract is track else contract.parse_ranking_intent
    legacy = contract.track_guidance_for_query if contract is track else contract.ranking_guidance_for_query
    rule = contract.episode_track_rule if contract is track else contract.episode_ranking_rule
    receipt = contract.contract_receipt if contract is track else contract.ranking_receipt
    assert not parser(**kw)
    assert legacy(**kw) == rule(**kw) == ""
    assert contract.contract_missing_outputs("", **kw) == ()
    saved = receipt(RANKING_ANSWER + _TRACK_ANSWER, **kw)
    assert saved["track_intent" if contract is track else "ranking_intent"] is False
    assert saved["missing_outputs"] == []
    # A model saying 'historical research' cannot switch off a forward contract.
    plain = {"query": FORWARD, "question_type": "theme_analysis"}
    assert parser(**plain)
    assert legacy(**plain) and rule(**plain)
    assert contract.contract_missing_outputs("这是历史研究，不用跟踪或矩阵。", **plain)


def test_actual_adapter_receipts_and_repair_keep_history_missing(tmp_path):
    frame = _history_frame(tmp_path)
    context = _context(frame)
    outcome = _unfulfilled(frame, context)

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    result = ContinuousTurnAdapter(
        runtime=Runtime(), mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=lambda _: {
            "passed": True, "rejected_sentence_indexes": [], "issues": [],
        }),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type,
        terminal_kind="research", needs_retrieval=True,
        capabilities=("finance_query",), contract_required=True,
    ))
    assert result.status != "completed"
    artifact = result.private_artifact
    assert artifact["track_contract"]["track_intent"] is False
    assert artifact["ranking_contract"]["ranking_intent"] is False
    assert artifact["track_contract"]["missing_outputs"] == []
    assert artifact["ranking_contract"]["missing_outputs"] == []
    assert not FORWARD_SLOTS.intersection(artifact["structural_verifier"]["missing_outputs"])
    assert "尚无可核验的历史计算原件" in result.answer


@pytest.mark.parametrize("writer", [track.ingest_next_watch, ranking.ingest_flip_conditions])
def test_both_checkpoint_writers_reject_history_even_with_registerable_answer(tmp_path, writer):
    frame = _history_frame(tmp_path)
    path = tmp_path / "checkpoints.jsonl"
    answer = RANKING_ANSWER + "\n" + _TRACK_ANSWER
    # Positive control proves the answer really would be registered otherwise.
    forward = writer(path, answer, query=FORWARD, as_of="2026-09-15")
    assert forward
    before = path.read_bytes()
    assert writer(
        path, answer, query=FOLLOWUPS[0], question_type=frame.question_type,
        history_intent=frame.history_intent, as_of="2026-09-15",
    ) == []
    assert path.read_bytes() == before
    missing = tmp_path / "untouched" / "checkpoints.jsonl"
    assert writer(missing, answer, query=FORWARD, history_intent=frame.history_intent) == []
    assert not missing.parent.exists()


def test_orchestrator_blocks_history_before_resolving_user_path_or_calling_writers(tmp_path, monkeypatch):
    from intelligence.runtime import conversation_orchestrator as co

    frame = _history_frame(tmp_path)
    calls = []

    def user_space(_uid):
        calls.append("user_space")
        return SimpleNamespace(checkpoints_path=tmp_path / "checks.jsonl")

    def leaking_writer(*_args, **_kwargs):
        calls.append("writer")
        return []

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(co.userspace, "user_space", user_space)
    monkeypatch.setattr(track, "ingest_next_watch", leaking_writer)
    monkeypatch.setattr(ranking, "ingest_flip_conditions", leaking_writer)
    fake = SimpleNamespace(run_store=SimpleNamespace(user_id="isolated-real-user"))
    kw = dict(query=FOLLOWUPS[0], answer=RANKING_ANSWER + _TRACK_ANSWER,
              question_type=frame.question_type, as_of="2026-09-15", theme=None, session_id="run")
    co.TurnOrchestrator._ingest_track_next_watch(fake, **kw, history_intent=frame.history_intent)
    assert calls == []
    co.TurnOrchestrator._ingest_track_next_watch(fake, **kw)
    assert calls == ["user_space", "writer", "writer"]


def test_real_run_turn_passes_inherited_history_to_checkpoint_boundary(tmp_path, monkeypatch):
    from intelligence.runtime import conversation_orchestrator as co
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
    from intelligence.services.run_store import RunStore
    from intelligence.services.turn_controller import decide_turn
    from intelligence.tests.test_conversation_orchestrator import _prepare_turn

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_EPISODE_STORE", str(tmp_path / "episodes"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    store = ConversationStore("history-contract", root=tmp_path / "messages")
    runs = RunStore("history-contract", root=tmp_path / "runs")
    conv = store.create_conversation()
    first = decide_turn(FIRST, llm_complete=lambda _: (None, None, "offline"))
    store.append_message(conv.conversation_id, "user", FIRST)
    store.append_message(conv.conversation_id, "assistant", "尚无历史样本结论。",
                         turn_intent=first.turn_intent.to_dict())
    run_id, message_id = _prepare_turn(store, runs, conv.conversation_id, FOLLOWUPS[0])
    captured = []
    writes = []
    frames = []
    expected_intent = replace(first.task_frame.history_intent, analysis_window_source="analogue")
    original_ingest = co.TurnOrchestrator._ingest_track_next_watch

    class Adapter:
        def handle(self, *, frame, control):
            frames.append(frame)
            return ContinuousTurnResult(
                handled=True, status="partial", answer=RANKING_ANSWER + _TRACK_ANSWER,
                as_of="2026-09-15", citations=(), warnings=(), private_artifact=None, events=(),
            )

    def capture(self, **kwargs):
        captured.append(kwargs)
        # Bypass only the test-user guard, not the history gate being tested.
        with monkeypatch.context() as m:
            m.delenv("PYTEST_CURRENT_TEST", raising=False)
            original_ingest(self, **kwargs)

    def writer(*_args, **_kwargs):
        writes.append("leaked")
        return []

    monkeypatch.setattr(co, "decide_turn", lambda raw, **kw: decide_turn(
        raw, **kw, llm_complete=lambda _: (None, None, "offline")
    ))
    monkeypatch.setattr(co.TurnOrchestrator, "_ingest_track_next_watch", capture)
    monkeypatch.setattr(track, "ingest_next_watch", writer)
    monkeypatch.setattr(ranking, "ingest_flip_conditions", writer)
    result = co.TurnOrchestrator(
        repo_root=tmp_path, conversation_store=store, run_store=runs,
        continuous_turn_adapter=Adapter(),
    ).run_turn(
        conversation_id=conv.conversation_id, run_id=run_id,
        assistant_message_id=message_id, query=FOLLOWUPS[0], skill_mode="auto", selected_skill_ids=[],
    )
    assert result.status == "completed"  # Transport completed, not business acceptance.
    assert len(captured) == 1
    assert len(frames) == 1 and frames[0].history_intent == expected_intent
    assert captured[0]["history_intent"] == expected_intent
    assert writes == []
    assert not list((tmp_path / "users").rglob("checkpoints.jsonl"))


def test_forward_history_analogy_and_explicit_cancellation_keep_forward_templates(tmp_path):
    # Mentioning a historical analogue is not itself a retrospective task.
    query = "这轮液冷和2023年光模块行情在机制上有哪些相似和不同？对英维克、申菱环境、高澜股份的排序有什么影响"
    frame = understand_query(query).task_frame
    assert frame.history_intent is None
    system, user = FinanceResearchHarness().assemble_prompt(frame, _context(frame), ResearchToolRegistry(()))
    assert "【排序方法建议（可选）】" in system + user
    store = ConversationStore("history-cancel", root=tmp_path / "cancel")
    conv = store.create_conversation()
    first = _decide(store, conv, FIRST)
    cancelled = _decide(store, conv, "停止历史研究。" + FORWARD, first.turn_intent, 1)
    assert cancelled.task_frame.history_intent is None
    system, user = FinanceResearchHarness().assemble_prompt(
        cancelled.task_frame, _context(cancelled.task_frame), ResearchToolRegistry(())
    )
    assert "【跟踪方法建议（可选）】" in system + user
    assert "【排序方法建议（可选）】" in system + user
