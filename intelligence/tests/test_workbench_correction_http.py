"""HTTP-to-first-provider delivery, not live-model adoption or financial quality.

Only synthetic users/data under tmp_path. The prior completed answer is a store
fixture; correction and fresh research turns enter through the real HTTP routes.
"""
from __future__ import annotations

import json
from pathlib import Path
import socket
import time

from fastapi.testclient import TestClient
import pytest

from intelligence.api import app as app_module
from intelligence.services import corrections, episode_tools, llm_refine
from intelligence.services.agent_research import evidence_content_hash
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.episode_evidence import EpisodeEvidenceSnapshot
from intelligence.services.episode_store import JsonlEpisodeStore
from intelligence.services.llm_settings import SessionLLMSettings
from intelligence.services.memory_status import record_status
from intelligence.services.research_tool_registry import ResearchToolRegistry


QUERY = "光刻胶题材现在怎么看"
CORRECTION = "不对，应该先看客户验证进度再下结论"


def _conversation(client, user):
    response = client.post("/api/conversations", json={"user": user})
    response.raise_for_status()
    return response.json()["conversation_id"]


def _send(client, user, conversation_id, content):
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"user": user, "content": content, "skill_mode": "hybrid"},
    )
    response.raise_for_status()
    created = response.json()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get(f"/api/runs/{created['run_id']}", params={"user": user})
        response.raise_for_status()
        run = response.json()
        response = client.get(
            f"/api/conversations/{conversation_id}/messages", params={"user": user},
        )
        response.raise_for_status()
        message = next(
            item for item in response.json()
            if item["message_id"] == created["assistant_message_id"]
        )
        if run["status"] in {"completed", "failed", "cancelled"} and message["status"] in {
            "completed", "failed", "cancelled",
        }:
            return created
        time.sleep(0.02)
    pytest.fail("HTTP turn did not terminalize within the fixture deadline")


@pytest.fixture
def offline_http(tmp_path: Path, monkeypatch):
    repo = tmp_path / "finance"
    repo.mkdir()
    env = {
        "FORESIGHT_USERS_DIR": str(tmp_path / "users"),
        "FORESIGHT_USER": "alice",
        "FINANCE_WS": str(repo),
        "KB_VAULT": str(tmp_path / "wiki"),
        "MARKET_SNAPSHOT_DIR": str(tmp_path / "snapshots"),
        "MARKET_FEATURE_STORE_DB": str(repo / "db" / "market_feature_store.duckdb"),
        "FORESIGHT_EPISODE_STORE": str(tmp_path / "episodes"),
        "FINANCE_DEPLOY_LEDGER": str(tmp_path / "deploy-ledger.jsonl"),
        "AGENT_RUNTIME_BACKEND": "continuous_glm",
        "ASK_CONTINUOUS_RUNTIME": "on",
        "RAG_WORKER_ENABLED": "0",
        "FINANCE_NEWS_FETCH": "0",
        "FINANCE_WEB_SEARCH": "0",
        "FINANCE_FOLLOWUPS": "0",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", lambda *a, **kw: ())
    monkeypatch.setattr(llm_refine, "detect_providers", lambda *a, **kw: ())
    monkeypatch.setattr(llm_refine, "complete", lambda *a, **kw: (None, None, "offline"))
    network_attempts = []
    tool_attempts = []

    def forbid_tools(_registry, *args, **kwargs):
        tool_attempts.append(args)
        raise AssertionError("Opening delivery must precede any model tool call")

    monkeypatch.setattr(ResearchToolRegistry, "execute", forbid_tools)

    def forbid_network(_socket, address):
        network_attempts.append(str(address))
        raise AssertionError("HTTP memory fixture must not contact a network provider")

    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid_network)
    provider = llm_refine.LLMProvider(
        name="openai", model="offline-capture", api_key="fixture-only",
        base_url="https://offline.invalid/v1",
    )
    settings = SessionLLMSettings(credential_store=None)
    monkeypatch.setattr(settings, "runtime_providers_for", lambda _user: (provider,))
    calls = []

    def capture(*, messages, tools, **kwargs):
        calls.append(json.loads(json.dumps(messages)))
        # The real serializer has delivered. Deliberately provide no answer:
        # a terminal failed/degraded run cannot be mistaken for model adoption.
        return None, provider, "offline_capture_stop"

    monkeypatch.setattr(llm_refine, "chat_with_tools", capture)
    with TestClient(app_module.create_app(repo_root=repo, llm_settings=settings)) as client:
        yield client, calls
    assert network_attempts == []
    assert tool_attempts == []


@pytest.mark.parametrize("state", ["active", "other_user", "rejected"])
def test_http_correction_reaches_fresh_first_request(tmp_path, monkeypatch, offline_http, state):
    # Pytest sets this again between fixture setup and the test call. All roots
    # have been isolated above before enabling the production write-side guard.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    client, calls = offline_http
    original_conversation = _conversation(client, "alice")
    previous = ConversationStore("alice").append_message(
        original_conversation, "assistant", "产能公告可以直接作为兑现依据。",
        turn_intent={"question_type": "theme_analysis", "primary_subject": "光刻胶"},
    )
    _send(client, "alice", original_conversation, CORRECTION)
    path = tmp_path / "users" / "alice" / "corrections.jsonl"
    rows, error = corrections.load_corrections(path, strict=True)
    assert error is None
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "workbench_conversation"
    assert row["conversation_id"] == original_conversation
    assert row["corrected_message_id"] == previous.message_id
    assert row["themes"] == ["光刻胶"]
    if state == "rejected":
        record_status(path, target_ts=row["id"], status="rejected")

    user = "bob" if state == "other_user" else "alice"
    fresh = _conversation(client, user)
    assert ConversationStore(user).load_messages(fresh) == []
    calls.clear()
    created = _send(client, user, fresh, QUERY)
    episode_id = f"{created['run_id']}:{created['assistant_message_id']}"
    checkpoint = JsonlEpisodeStore(tmp_path / "episodes").load_state(episode_id)
    assert checkpoint is not None
    assert checkpoint.entry_identity["entry"] == "workbench_conversation"
    assert checkpoint.entry_identity["user_id"] == user
    assert checkpoint.entry_identity["conversation_id"] == fresh
    assert checkpoint.entry_identity["run_id"] == created["run_id"]
    assert checkpoint.entry_identity["assistant_message_id"] == created["assistant_message_id"]
    snapshot = EpisodeEvidenceSnapshot.from_dict(
        checkpoint.evidence_snapshot, episode_id=episode_id,
    )
    memory = [item for item in snapshot.presented_evidence if item.tool == "memory_lookup"]
    assert len(memory) == 1
    assert memory[0].content_hash == evidence_content_hash(memory[0])
    assert memory[0].evidence_tier == ("user_memory" if state == "active" else "user_memory_gap")
    assert calls, "real HTTP research turn never reached the provider boundary"
    first = calls[0]
    task = next(
        json.loads(message["content"]) for message in first
        if message["role"] == "user" and '"research_contract"' in message["content"]
    )
    assert task["task_frame"]["subject"] == "光刻胶"
    assert row["correction"] not in task["conversation_context"]
    assert "memory_lookup" in task["research_contract"]["allowed_capabilities"]
    prior = next(
        output for output in task["research_contract"]["required_outputs"]
        if output["output_id"] == "prior_recall"
    )
    assert prior["grounding_mode"] == "user_premise" and not prior["required"]
    text = json.dumps(first, ensure_ascii=False)
    assert str(tmp_path) not in text
    assert "不是市场事实" in text
    if state == "active":
        assert row["correction"] in text
        assert "[E1] 用户纠偏原则" in text
        assert "台账 corrections；先验，非市场事实" in text
    else:
        assert row["correction"] not in text
        assert "status=empty" in text
    # A cross-user request cannot read the write-side conversation or run.
    if state == "other_user":
        assert client.get(
            f"/api/conversations/{original_conversation}/messages", params={"user": "bob"},
        ).status_code == 404
        assert client.get(
            f"/api/runs/{created['run_id']}", params={"user": "alice"},
        ).status_code == 404
