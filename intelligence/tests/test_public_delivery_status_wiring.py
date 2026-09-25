"""Exercise reachable status paths through the real turn orchestrator."""
from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

from intelligence.runtime import conversation_orchestrator as runtime
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.research_contract import TurnIntent
from intelligence.services.run_store import RunStore
from intelligence.services.turn_controller import TurnDecision
from intelligence.tests.test_conversation_orchestrator import _prepare_turn
from intelligence.tests.test_public_delivery_gate import CONTRACT, _frame


@pytest.mark.parametrize("turn_status,research_status,answer_status,gate_calls", [
    ("completed", "complete", "partial", 1),
    ("partial", "partial", "partial", 1),
    ("failed", "blocked", "missing", 0),
])
def test_delivery_gate_preserves_reachable_statuses(
    tmp_path, turn_status, research_status, answer_status, gate_calls,
) -> None:
    conversations = ConversationStore("alice", root=tmp_path / "conversations")
    runs = RunStore("alice", root=tmp_path / "runs")
    conversation = conversations.create_conversation()
    query = "当前市场有哪些证据边界"
    frame = _frame(query)
    run_id, assistant_id = _prepare_turn(
        conversations, runs, conversation.conversation_id, query,
    )
    intent = TurnIntent(
        primary_subject=frame.subject, secondary_topics=(),
        question_type=frame.question_type, answer_owner=None,
        comparison_entities=(), inherited_from_turn=None,
        timeframe=frame.timeframe, required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )
    body = "数据截至2026-09-23，证据范围只有当日行情。具体判断详见正文附表。"

    def controller(_query, **_kwargs):
        return TurnDecision(
            lane="research", needs_retrieval=True, needs_memory=False,
            needs_template=True, question_type=frame.question_type,
            capabilities=("market_data",), task_frame=frame, turn_intent=intent,
        )

    class Adapter:
        def handle(self, *, frame, control):
            return ContinuousTurnResult(
                handled=True, status=turn_status, answer=body,
                as_of="2026-09-23", citations=(), warnings=(), events=(),
                private_artifact={
                    "contract": CONTRACT,
                    "semantic_verifier": {"judge_status": "passed", "issues": []},
                    "events": [{"kind": "task", "payload": {
                        "task_frame_hash": frame.task_frame_hash,
                    }}],
                },
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy or model dependency must not run")

    orchestrator = runtime.TurnOrchestrator(
        repo_root=tmp_path, conversation_store=conversations, run_store=runs,
        answer_query_fn=forbidden, route_skills_fn=forbidden,
        lane_answer_fn=forbidden, turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    )
    spy = Mock(wraps=runtime.review_public_delivery)
    with patch.object(runtime, "review_public_delivery", spy):
        orchestrator.run_turn(
            conversation_id=conversation.conversation_id, run_id=run_id,
            assistant_message_id=assistant_id, query=query,
            skill_mode="auto", selected_skill_ids=[],
        )
    report = json.loads((runs.run_dir(run_id) / "report.json").read_text())
    assert report["research_status"] == research_status
    assert report["answer_status"] == answer_status
    assert spy.call_count == gate_calls
    if gate_calls:
        assert report["public_delivery_gate"]["verdict"] == "incomplete"
        assert report["business_status"] == report["status"] == "partial"
        assert "public_delivery_gate:incomplete" in report["warnings"]
        assert "【交付自检】" in (runs.run_dir(run_id) / "answer.md").read_text()
    else:
        # A failed projection exits before delivery; do not inject an impossible
        # completed transport with a blocked business projection to reach the gate.
        assert report["business_status"] == report["status"] == "blocked"
        assert "public_delivery_gate" not in report
