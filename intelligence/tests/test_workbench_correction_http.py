"""HTTP-to-first-provider delivery, not live-model adoption or financial quality.

Only synthetic users/data under tmp_path. The prior completed answer is a store
fixture; correction and fresh research turns enter through the real HTTP routes.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import errno
import json
from pathlib import Path
import socket
from threading import BoundedSemaphore, Event
import time

from fastapi.testclient import TestClient
import pytest

from intelligence.api import app as app_module
from intelligence.services import corrections, episode_tools, llm_refine, memory_prefetch, user_memory
from intelligence.services.agent_research import evidence_content_hash
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.episode_evidence import EpisodeEvidenceSnapshot
from intelligence.services.episode_store import JsonlEpisodeStore
from intelligence.services.llm_settings import SessionLLMSettings
from intelligence.services.memory_status import record_status
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import RunStore


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


@pytest.fixture(params=["off", "on"], ids=["adaptive-off", "adaptive-on"])
def offline_http(tmp_path: Path, monkeypatch, request):
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
        "WORKBENCH_ADAPTIVE_RESEARCH": request.param,
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


def _first_request_memory(tmp_path, calls, created, user, conversation_id):
    episode_id = f"{created['run_id']}:{created['assistant_message_id']}"
    checkpoint = JsonlEpisodeStore(tmp_path / "episodes").load_state(episode_id)
    assert checkpoint is not None
    assert checkpoint.entry_identity["entry"] == "workbench_conversation"
    assert checkpoint.entry_identity["user_id"] == user
    assert checkpoint.entry_identity["conversation_id"] == conversation_id
    assert checkpoint.entry_identity["run_id"] == created["run_id"]
    assert checkpoint.entry_identity["assistant_message_id"] == created["assistant_message_id"]
    snapshot = EpisodeEvidenceSnapshot.from_dict(
        checkpoint.evidence_snapshot, episode_id=episode_id,
    )
    memory = [item for item in snapshot.presented_evidence if item.tool == "memory_lookup"]
    assert len(memory) == 1
    assert memory[0].content_hash == evidence_content_hash(memory[0])
    assert calls, "real HTTP research turn never reached the provider boundary"
    first = calls[0]
    task = next(
        json.loads(message["content"]) for message in first
        if message["role"] == "user" and '"research_contract"' in message["content"]
    )
    assert task["task_frame"]["subject"] == "光刻胶"
    assert "memory_lookup" in task["research_contract"]["allowed_capabilities"]
    prior = next(
        output for output in task["research_contract"]["required_outputs"]
        if output["output_id"] == "prior_recall"
    )
    assert prior["grounding_mode"] == "user_premise" and not prior["required"]
    text = json.dumps(first, ensure_ascii=False)
    assert str(tmp_path) not in text
    assert "不是市场事实" in text
    return text, memory[0], task


def _fresh_memory_request(tmp_path, client, calls):
    fresh = _conversation(client, "alice")
    assert ConversationStore("alice").load_messages(fresh) == []
    calls.clear()
    created = _send(client, "alice", fresh, QUERY)
    text, memory, task = _first_request_memory(tmp_path, calls, created, "alice", fresh)
    assert CORRECTION not in task["conversation_context"]
    return created, text, memory


def _assert_gap(text, memory, reason):
    assert memory.evidence_tier == "user_memory_gap"
    assert f"status={reason}" in memory.detail
    assert f"status={reason}" in text
    assert "先看客户验证进度再下结论" not in text
    if reason != "empty":
        assert "status=empty" not in text


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
    text, memory, task = _first_request_memory(tmp_path, calls, created, user, fresh)
    assert memory.evidence_tier == ("user_memory" if state == "active" else "user_memory_gap")
    assert row["correction"] not in task["conversation_context"]
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


@pytest.mark.parametrize("ledger", ["corrections", "judgments"])
@pytest.mark.parametrize("content", ["{broken-private-sentinel", "[]"])
def test_http_corrupt_memory_is_unavailable_not_empty(tmp_path, offline_http, ledger, content):
    client, calls = offline_http
    root = tmp_path / "users" / "alice"
    path, _ = corrections.record_correction(
        root / "corrections.jsonl", correction="先看客户验证进度再下结论", themes=["光刻胶"],
    )
    broken = root / f"{ledger}.jsonl"
    # A valid correction must not hide a damaged sibling ledger or partial row.
    with broken.open("a", encoding="utf-8") as stream:
        stream.write(content + "\n")
    before = path.read_bytes(), broken.read_bytes()
    _, text, memory = _fresh_memory_request(tmp_path, client, calls)
    _assert_gap(text, memory, "unavailable")
    assert "broken-private-sentinel" not in text
    assert (path.read_bytes(), broken.read_bytes()) == before


def test_http_reader_exception_is_private_and_recovers(tmp_path, monkeypatch, offline_http):
    client, calls = offline_http
    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl",
        correction="先看客户验证进度再下结论", themes=["光刻胶"],
    )
    attempted = []

    def failed(*args, **kwargs):
        attempted.append(kwargs)
        raise OSError(f"{tmp_path}/private-error-sentinel")

    with monkeypatch.context() as patch:
        patch.setattr(user_memory, "relevant_memory_records", failed)
        _, text, memory = _fresh_memory_request(tmp_path, client, calls)
        _assert_gap(text, memory, "unavailable")
        assert len(attempted) == 1 and attempted[0]["strict"] is True
        assert "private-error-sentinel" not in text
    _, text, memory = _fresh_memory_request(tmp_path, client, calls)
    assert memory.evidence_tier == "user_memory"
    assert "先看客户验证进度再下结论" in text


def test_http_timeout_busy_late_result_and_recovery(tmp_path, monkeypatch, offline_http):
    client, calls = offline_http
    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl",
        correction="先看客户验证进度再下结论", themes=["光刻胶"],
    )
    release = Event()
    started = [Event(), Event()]
    attempts = []
    slots = BoundedSemaphore(2)
    real = user_memory.relevant_memory_records

    def slow(*args, **kwargs):
        index = len(attempts)
        attempts.append(kwargs)
        started[index].set()
        assert release.wait(30), "fixture reader was not released"
        return real(*args, **kwargs)

    # Own and join the test's workers so no blocked read survives fixture roots.
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="http-memory-test") as pool:
        monkeypatch.setattr(memory_prefetch, "_POOL", pool)
        monkeypatch.setattr(memory_prefetch, "_SLOTS", slots)
        monkeypatch.setattr(memory_prefetch, "MEMORY_PREFETCH_SECONDS", 0.05)
        monkeypatch.setattr(user_memory, "relevant_memory_records", slow)
        previous = []
        store = JsonlEpisodeStore(tmp_path / "episodes")
        try:
            for index in range(2):
                created, text, memory = _fresh_memory_request(tmp_path, client, calls)
                assert started[index].is_set()
                assert not release.is_set(), "provider must be reached before the read ends"
                _assert_gap(text, memory, "timeout")
                episode_id = f"{created['run_id']}:{created['assistant_message_id']}"
                previous.append((episode_id, store.load_state(episode_id).evidence_snapshot))
            _, text, memory = _fresh_memory_request(tmp_path, client, calls)
            _assert_gap(text, memory, "busy")
            assert len(attempts) == 2
        finally:
            release.set()
        # Wait for both done callbacks, not just the reader's return statement.
        for _ in range(2):
            assert slots.acquire(timeout=3), "worker did not release its admission slot"
        for _ in range(2):
            slots.release()
        for episode_id, snapshot in previous:
            assert store.load_state(episode_id).evidence_snapshot == snapshot
        monkeypatch.setattr(user_memory, "relevant_memory_records", real)
        monkeypatch.setattr(memory_prefetch, "MEMORY_PREFETCH_SECONDS", 1.0)
        _, text, memory = _fresh_memory_request(tmp_path, client, calls)
        assert memory.evidence_tier == "user_memory"
        assert "先看客户验证进度再下结论" in text
        assert len(attempts) == 2


@pytest.mark.parametrize("error_number", [errno.EACCES, errno.ENOSPC], ids=["permission", "disk-full"])
def test_http_write_failure_warns_and_keeps_research_running(
    tmp_path, monkeypatch, offline_http, error_number,
):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    client, calls = offline_http
    conversation = _conversation(client, "alice")
    previous = ConversationStore("alice").append_message(
        conversation, "assistant", "产能公告可以直接作为兑现依据。",
        turn_intent={"question_type": "theme_analysis", "primary_subject": "光刻胶"},
    )
    target = tmp_path / "users" / "alice" / "corrections.jsonl"
    real_open = Path.open
    attempts = []

    def denied(path, mode="r", *args, **kwargs):
        if path == target and mode == "a":
            attempts.append(path)
            raise OSError(error_number, "private-write-error-sentinel", str(path))
        return real_open(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", denied)
        created = _send(client, "alice", conversation, CORRECTION)
    assert attempts == [target]
    assert not target.exists()
    assert calls, "a correction write error aborted research before the provider"
    run_store = RunStore("alice")
    assert "user_correction_ingest_failed" in run_store.load_run(created["run_id"]).degrades
    steps = run_store.load_trace(created["run_id"])
    failures = [step for step in steps if step["step_id"] == "user_correction_ingest_failed"]
    assert len(failures) == 1 and failures[0]["status"] == "failed"
    payload = json.loads(failures[0]["output_summary"])
    assert payload == {
        "status": "failed", "reason": "write_failed", "plane": "user_method",
        "corrected_message_id": previous.message_id,
        "error_type": "PermissionError" if error_number == errno.EACCES else "OSError",
    }
    assert not any(step["step_id"] == "user_correction_recorded" for step in steps)
    assert "private-write-error-sentinel" not in json.dumps([calls, steps], ensure_ascii=False)
    _, text, memory = _fresh_memory_request(tmp_path, client, calls)
    _assert_gap(text, memory, "empty")
    # Repeating the correction after IO recovery succeeds once, then deduplicates.
    _send(client, "alice", conversation, CORRECTION)
    before = target.read_bytes()
    _send(client, "alice", conversation, CORRECTION)
    assert target.read_bytes() == before
    rows, error = corrections.load_corrections(target, strict=True)
    assert error is None and len(rows) == 1
    assert rows[0]["corrected_message_id"] == previous.message_id
    _, text, memory = _fresh_memory_request(tmp_path, client, calls)
    assert memory.evidence_tier == "user_memory"
    assert rows[0]["correction"] in text
