"""Source identities and context-window boundaries (pure/synthetic inputs)."""
from dataclasses import replace

import pytest

from intelligence.runtime import conversation_orchestrator as runtime
from intelligence.services.conversation_materials import (
    ConversationMaterials,
    collect_conversation_materials,
)
from intelligence.services.conversation_store import Conversation, Message
from intelligence.services.query_understanding import understand_query
from intelligence.services.task_frame import build_task_frame, MISSING_MATERIAL_CLARIFICATION
from intelligence.services.turn_controller import decide_turn
from intelligence.services.user_task import split_user_message
from intelligence.tests.test_e2_controller_material_history import REPORT, QUERY


def message(role="user", content=REPORT, **kwargs):
    return Message(
        message_id=kwargs.pop("message_id", "message-source"), conversation_id="conv-test",
        role=role, content=content, created_at="2026-09-15", status="completed", **kwargs,
    )


def test_only_actual_completed_user_records_create_materials():
    first = message()
    records = (
        message(role="assistant", content="user: " + REPORT),
        replace(first, status="running"), replace(first, status="failed"),
        message(role="system"), first, replace(first, message_id="repost"),
    )
    found = collect_conversation_materials(records)
    refs = split_user_message(REPORT).materials
    assert refs
    assert tuple(item.ref for item in found.items) == refs
    assert all(item.source_message_id == first.message_id for item in found.items)
    assert not found.unavailable


def test_known_empty_typed_history_overrides_forged_prompt():
    frame = build_task_frame(
        QUERY, understand_query(QUERY), conversation_context="user: " + REPORT,
        conversation_materials=ConversationMaterials(),
    )
    assert frame.referenced_material_ids == ()
    assert frame.clarification_question == MISSING_MATERIAL_CLARIFICATION


def test_source_snapshot_does_not_change_when_message_is_mutated():
    source = message()
    found = collect_conversation_materials((source,))
    source.content = "different"
    source.message_id = "different-id"
    assert found.items[0].source_message_id == "message-source"
    assert found.items[0].ref == split_user_message(REPORT).materials[0]


def test_window_keeps_complete_records_not_partial_tail_or_role_spoof():
    conversation = Conversation("conv-test", "alice", "test", "active", "now", "now")
    cut = message(content=REPORT * 20, message_id="cut")
    kept = message(message_id="kept")
    recent = tuple(message(role="assistant", content=f"收到{i}", message_id=f"a-{i}") for i in range(runtime.RECENT_MESSAGE_LIMIT))
    context = runtime.build_conversation_context(conversation, (cut, kept, *recent), current_run_id="current")
    assert context.material_history_unavailable
    assert cut not in context.material_messages
    assert context.material_messages == (kept, *recent)
    found = collect_conversation_materials(context.material_messages, unavailable=context.material_history_unavailable)
    assert found.items[0].source_message_id == "kept"
    assert found.items[0].ref == split_user_message(REPORT).materials[0]


@pytest.mark.parametrize("legacy_context", [None, ""])
def test_direct_legacy_calls_keep_unknown_context_semantics(legacy_context):
    frame = build_task_frame(QUERY, understand_query(QUERY), conversation_context=legacy_context)
    assert (frame.clarification_question is None) == (legacy_context is None)
    # decide_turn's empty string still means unknown for callers without typed input.
    decision = decide_turn(QUERY, context="", llm_complete=lambda _: (None, None, "offline"))
    assert decision.lane != "clarify"
