"""An unavailable recall classifier must not execute another user goal."""
from __future__ import annotations

import json
from pathlib import Path
import socket
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from intelligence.api import app as app_module
from intelligence.runtime import conversation_orchestrator
from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.conversation_store import ConversationStore
from intelligence.services import episode_tools, llm_refine, turn_controller
from intelligence.services.llm_settings import SessionLLMSettings
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import RunStore
from intelligence.services.turn_controller import TurnDecision
from intelligence.tests.test_workbench_correction_http import _conversation, _send


@pytest.fixture
def failed_recall_http(tmp_path, monkeypatch):
    finance = tmp_path / "finance"
    finance.mkdir()
    for key, value in {
        "FORESIGHT_USERS_DIR": tmp_path / "users",
        "FORESIGHT_EPISODE_STORE": tmp_path / "episodes",
        "FINANCE_DEPLOY_LEDGER": tmp_path / "deploy-ledger.jsonl",
        "FINANCE_REJUDGE_PENDING_INDEX": tmp_path / "pending/index.jsonl",
        "FINANCE_MEMORY_VECTOR_CACHE_DIR": tmp_path / "memory-cache",
        "FINANCE_WS": finance, "FINANCE_ROOT": finance,
        "WORKBENCH_KNOWLEDGE_WIKI": tmp_path / "wiki", "KB_VAULT": tmp_path / "wiki",
        "MARKET_SNAPSHOT_DIR": tmp_path / "snapshots",
        "MARKET_FEATURE_STORE_DB": finance / "db/market_feature_store.duckdb",
        "ENTITY_ANCHOR_SECURITIES_DB": finance / "db/market_feature_store.duckdb",
        "KB_RAG_CODE_ROOT": tmp_path / "rag-code",
        "KB_RAG_FULL_INDEX_DIR": tmp_path / "full-index",
        "RAG_INDEX_DIR": tmp_path / "index", "VECTOR_INDEX_DIR": tmp_path / "index",
        "RAG_WORKER_ENABLED": "0", "FINANCE_NEWS_FETCH": "0", "FINANCE_WEB_SEARCH": "0",
        "FINANCE_FOLLOWUPS": "0", "FORESIGHT_LLM_KEYCHAIN": "off",
    }.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.setattr(llm_refine, "detect_providers", lambda *a, **kw: ())
    downstream = []

    def forbid(name):
        def call(*args, **kwargs):
            downstream.append(name)
            raise AssertionError(f"unresolved scope reached {name}")
        return call

    # Fail before any side effect if the old implementation reaches a wrong lane.
    monkeypatch.setattr(socket.socket, "connect", forbid("network"))
    monkeypatch.setattr(socket.socket, "connect_ex", forbid("network"))
    monkeypatch.setattr(conversation_orchestrator, "answer_query", forbid("retrieval"))
    monkeypatch.setattr(conversation_orchestrator, "generate_lane_answer", forbid("lane_author"))
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", forbid("prefetch"))
    monkeypatch.setattr(ResearchToolRegistry, "execute", forbid("tool"))
    monkeypatch.setattr(llm_refine, "chat_with_tools", forbid("author"))
    provider = llm_refine.LLMProvider(
        name="openai", model="offline-controller", api_key="synthetic-only",
        base_url="https://offline.invalid/v1",
    )
    settings = SessionLLMSettings(credential_store=None)
    monkeypatch.setattr(settings, "runtime_providers_for", lambda _user: (provider,))
    with TestClient(app_module.create_app(repo_root=finance, llm_settings=settings)) as client:
        yield client, downstream


@pytest.mark.parametrize("query", [
    "我之前记录的检查清单是什么？只回顾我的记录，不做行情判断。",
    "关于光刻胶，我之前纠正过的研究顺序是什么？只回顾我的记录。",
    "结合我之前的判断，评估光刻胶现在的上涨空间。",
])
@pytest.mark.parametrize("failure", ["unavailable", "exception", "timeout", "empty", "json", "schema"])
def test_recall_scope_failure_stops_before_other_goal(
    tmp_path: Path, monkeypatch, failed_recall_http, query: str, failure: str,
):
    client, downstream = failed_recall_http
    calls = []

    def controller(messages, **kwargs):
        calls.append(messages)
        if failure == "exception":
            raise RuntimeError("PRIVATE_CONTROLLER_DIAGNOSTIC")
        return {
            "unavailable": (None, None, "PRIVATE_CONTROLLER_DIAGNOSTIC"),
            "timeout": ('{"personal_records_only":true}', None, ""),
            "empty": ("  ", None, ""),
            "json": ("{", None, ""),
            "schema": ('{"personal_records_only":1}', None, ""),
        }[failure]

    monkeypatch.setattr(llm_refine, "complete", controller)
    if failure == "timeout":
        ticks = iter(range(0, 10000, 9))
        monkeypatch.setattr(turn_controller, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    cid = _conversation(client, "alice")
    created = _send(client, "alice", cid, query)
    run = client.get(f"/api/runs/{created['run_id']}", params={"user": "alice"}).json()
    messages = client.get(f"/api/conversations/{cid}/messages", params={"user": "alice"}).json()
    user = next(m for m in messages if m["message_id"] == created["user_message_id"])
    answer = next(m for m in messages if m["message_id"] == created["assistant_message_id"])
    assert downstream == []
    assert len(calls) == 1 and "personal_records_only" in calls[0][0]["content"]
    assert run["status"] == answer["status"] == "failed"
    assert user["content"] == query
    assert "未能确认" in answer["content"] and "原问题已保留" in answer["content"]
    assert "PRIVATE_CONTROLLER_DIAGNOSTIC" not in answer["content"]
    assert not answer.get("turn_intent") and not answer.get("research_plan")
    run_dir = tmp_path / "users/alice/runs" / created["run_id"]
    trace = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text().splitlines()]
    failed = next(step for step in trace if step["step_id"] == "controller")
    payload = json.loads(failed["output_summary"])
    assert failed["status"] == "failed" and payload["raw_question"] == query
    assert payload["llm_failure_reason"].startswith("personal_recall_")
    assert not any(step["step_id"] in {"plan", "retrieve", "memory_prefetch"} for step in trace)
    assert not (run_dir / "continuous-episode.json").exists()
    assert not list((tmp_path / "episodes").glob("**/*.jsonl"))


def test_failed_recall_does_not_seed_the_next_turn(monkeypatch, failed_recall_http):
    client, downstream = failed_recall_http
    monkeypatch.setattr(llm_refine, "complete", lambda *a, **kw: (None, None, "offline"))
    cid = _conversation(client, "alice")
    _send(client, "alice", cid, "我之前记录的检查清单是什么？只回顾我的记录。")
    received = []

    def capture_next_controller(query, **kwargs):
        received.append(kwargs)
        raise RuntimeError("next-turn capture complete")

    # The next real HTTP turn must not inherit the rejected candidate contract.
    monkeypatch.setattr(conversation_orchestrator, "decide_turn", capture_next_controller)
    _send(client, "alice", cid, "请继续处理原问题。")
    assert len(received) == 1
    assert received[0]["previous_intent"] is None
    assert received[0]["previous_turn_id"] is None
    assert downstream == []


@pytest.mark.parametrize("query", [
    "我之前记录的检查清单是什么？只回顾我的记录。",
    "结合我之前的判断，评估光刻胶现在的上涨空间。",
])
def test_recall_failure_preserves_cancellation_after_controller_returns(tmp_path, query):
    """Cancellation wins when it races the unresolved-recall failure exit."""
    conversations = ConversationStore("alice", root=tmp_path / "conversations")
    runs = RunStore("alice", root=tmp_path / "runs")
    conversation = conversations.create_conversation()
    run = runs.create_run(query, "ask", session_id=conversation.conversation_id)
    conversations.append_message(
        conversation.conversation_id, "user", query, run_id=run.run_id,
    )
    assistant = conversations.append_message(
        conversation.conversation_id, "assistant", "", status="pending", run_id=run.run_id,
    )
    cancelled = False

    def controller(_query, **_kwargs):
        nonlocal cancelled
        cancelled = True
        return TurnDecision(
            lane="research",
            needs_retrieval=False,
            needs_memory=True,
            needs_template=False,
            llm_failure_reason="personal_recall_provider_error",
            llm_failure_detail="synthetic-only",
        )

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversations,
        run_store=runs,
        turn_controller_fn=controller,
        is_cancelled=lambda: cancelled,
        cancellation_reason=lambda: "cancelled_by_user",
        answer_query_fn=lambda *_args, **_kwargs: pytest.fail("cancelled recall must not retrieve"),
        lane_answer_fn=lambda *_args, **_kwargs: pytest.fail("cancelled recall must not author"),
    )
    result = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run.run_id,
        assistant_message_id=assistant.message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "cancelled"
    assert runs.load_run(run.run_id).status == "cancelled"
    stored = next(
        message
        for message in conversations.load_messages(conversation.conversation_id)
        if message.message_id == assistant.message_id
    )
    assert stored.status == "cancelled"
