"""Correction -> new Workbench conversation -> real Episode delivery, offline."""
from __future__ import annotations

import json
import time

import pytest

from intelligence.services import corrections, llm_refine
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.episode_evidence import EpisodeEvidenceSnapshot
from intelligence.services.episode_store import JsonlEpisodeStore
from intelligence.services.memory_status import record_status
from intelligence.tests.test_personal_memory_recall import _finish, route_response
from intelligence.tests.test_workbench_correction_http import (
    CORRECTION, _conversation, _send, offline_http,  # noqa: F401 - shared isolated HTTP fixture
)


@pytest.mark.parametrize("state", ["active", "rejected", "other_user"])
@pytest.mark.parametrize("judge_mode", ["off", "llm"])
@pytest.mark.usefixtures("offline_http")
def test_fresh_http_recall_delivers_record_or_read_status(tmp_path, monkeypatch, request, state, judge_mode):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", judge_mode)
    client, calls = request.getfixturevalue("offline_http")
    original = _conversation(client, "alice")
    ConversationStore("alice").append_message(
        original, "assistant", "产能公告可以直接作为兑现依据。",
        turn_intent={"question_type": "theme_analysis", "primary_subject": "光刻胶"},
    )
    _send(client, "alice", original, CORRECTION)
    path = tmp_path / "users" / "alice" / "corrections.jsonl"
    rows, error = corrections.load_corrections(path, strict=True)
    assert error is None and len(rows) == 1
    if state == "rejected":
        record_status(path, target_ts=rows[0]["id"], status="rejected")
    ledger_before = {file: file.read_bytes() for file in path.parent.glob("*.jsonl")}

    controller_calls = []

    def controller(messages, **kwargs):
        controller_calls.append((messages, kwargs))
        return route_response()

    capture = llm_refine.chat_with_tools

    def writer(*, messages, tools, **kwargs):
        _, provider, _ = capture(messages=messages, tools=tools, **kwargs)
        is_judge = any(tool["function"]["name"] == "submit_grounding_report" for tool in tools)
        answer = ({"passed": True, "rejected_sentence_indexes": [], "issues": []}
                  if is_judge else _finish("你此前纠偏：先看客户验证进度再下结论（E1）。"))
        return {
            "content": json.dumps(answer, ensure_ascii=False),
            "tool_calls": [], "finish_reason": "stop",
        }, provider, ""

    monkeypatch.setattr(llm_refine, "complete", controller)
    monkeypatch.setattr(llm_refine, "chat_with_tools", writer)
    user = "bob" if state == "other_user" else "alice"
    fresh = _conversation(client, user)
    assert ConversationStore(user).load_messages(fresh) == []
    calls.clear()
    created = _send(
        client, user, fresh,
        "关于光刻胶，我之前纠正过的研究顺序是什么？只回顾我的记录，不做行情判断。",
    )
    assert len(controller_calls) == 1
    assert 0 < controller_calls[0][1]["timeout"] <= 8
    assert len(calls) == (2 if judge_mode == "llm" else 1)
    task = next(
        json.loads(message["content"]) for message in calls[0]
        if message["role"] == "user" and '"research_contract"' in message["content"]
    )
    assert task["task_frame"]["question_type"] == "personal_memory_recall"
    assert task["research_contract"]["allowed_capabilities"] == ["memory_lookup"]
    assert task["research_contract"]["required_outputs"][0]["required"]
    assert rows[0]["correction"] not in task["conversation_context"]
    checkpoint = JsonlEpisodeStore(tmp_path / "episodes").load_state(
        f"{created['run_id']}:{created['assistant_message_id']}",
    )
    assert checkpoint.entry_identity["user_id"] == user
    assert checkpoint.entry_identity["conversation_id"] == fresh
    snapshot = EpisodeEvidenceSnapshot.from_dict(
        checkpoint.evidence_snapshot, episode_id=f"{created['run_id']}:{created['assistant_message_id']}",
    )
    memory = snapshot.presented_evidence
    assert len(memory) == 1
    message = next(item for item in client.get(
        f"/api/conversations/{fresh}/messages", params={"user": user},
    ).json() if item["message_id"] == created["assistant_message_id"])
    assert message["status"] == "completed"
    episode_path = tmp_path / "users" / user / "runs" / created["run_id"] / "continuous-episode.json"
    # The public message terminalizes before the worker flushes its private artifact.
    until = time.monotonic() + 3
    while not episode_path.exists() and time.monotonic() < until:
        time.sleep(0.01)
    episode = json.loads(episode_path.read_text())
    assert episode["outcome"]["usage"]["invalid_actions"] == 0
    if state == "active":
        assert memory[0].evidence_tier == "user_memory"
        assert "先看客户验证进度再下结论" in message["content"]
        assert episode["structural_verifier"]["verified_status"] == "completed"
    else:
        assert memory[0].evidence_tier == "user_memory_gap"
        assert "可用个人记录中未找到" in message["content"]
        assert "先看客户验证进度再下结论" not in message["content"]
        assert episode["structural_verifier"]["verified_status"] == "partial"
    assert {file: file.read_bytes() for file in ledger_before} == ledger_before
    if state == "other_user":
        assert client.get(f"/api/conversations/{original}/messages", params={"user": "bob"}).status_code == 404
