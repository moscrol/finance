"""Direct replies may still follow a real controller call; persist its identity."""

from __future__ import annotations

import json

import pytest

from intelligence.eval import model_admission
from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services import llm_refine
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.lane_generation import LaneAnswer
from intelligence.services.run_store import RunStore
from intelligence.services.turn_controller import TurnDecision
from intelligence.tests.test_conversation_orchestrator import _prepare_turn
from intelligence.workbench_skills.registry import SkillRegistry


@pytest.mark.parametrize("lane", ["clarify", "chat", "meta", "knowledge"])
@pytest.mark.parametrize("reported,expected_exit", [("expected", 0), ("wrong", 1), ("", 2), (None, 2)])
def test_direct_lane_persists_controller_identity_before_terminal(
    tmp_path, lane, reported, expected_exit,
):
    store = ConversationStore("alice", root=tmp_path / "conversations")
    runs = RunStore("alice", root=tmp_path / "runs")
    conversation = store.create_conversation()
    query = "帮我看看"
    run_id, message_id = _prepare_turn(store, runs, conversation.conversation_id, query)

    def controller(*_args, **_kwargs):
        ledger = llm_refine.current_call_ledger()
        assert ledger is not None
        if reported is not None:
            ledger.record(llm_refine.LLMCallRecord(
                caller="controller", provider="fixture", model="expected",
                requested_model="expected", reported_model=reported,
                identity_state="reported" if reported else "unreported",
                attempt_id="controller-attempt", status="success", elapsed_ms=1,
            ))
        return TurnDecision(
            lane=lane, needs_retrieval=False, needs_memory=False, needs_template=False,
            question_type="general_knowledge", confidence=0.8, reason="fixture",
            clarification_questions=("你问的是哪个对象？",) if lane == "clarify" else (),
        )

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path, conversation_store=store, run_store=runs,
        turn_controller_fn=controller, skill_registry=SkillRegistry(),
        route_skills_fn=lambda *_a, **_kw: pytest.fail("direct lane must not route"),
        answer_query_fn=lambda *_a, **_kw: pytest.fail("direct lane must not retrieve"),
    )
    orchestrator.generate_lane_answer = lambda *_a, **_kw: LaneAnswer(answer="直接回复。")
    result = orchestrator.run_turn(
        conversation_id=conversation.conversation_id, run_id=run_id,
        assistant_message_id=message_id, query=query, skill_mode="manual", selected_skill_ids=[],
    )
    assert result.status == "completed"
    events = runs.load_stream_events(run_id)
    ledgers = [event for event in events if event["event_type"] == "trace.step"
               and event["payload"]["step"]["name"] == "llm_call_ledger"]
    assert len(ledgers) == (0 if reported is None else 1)
    if ledgers:
        record = json.loads(ledgers[0]["payload"]["step"]["output_summary"])["records"][0]
        assert record["reported_model"] == reported
        terminal = next(event for event in events if event["event_type"] == "message.complete")
        assert ledgers[0]["seq"] < terminal["seq"]
    checked = model_admission.check_paths([runs.run_dir(run_id) / "trace.jsonl"], ["expected"])
    assert model_admission.overall_exit_code(checked) == expected_exit
    assert checked[0].served == ({reported: 1} if reported else {})
