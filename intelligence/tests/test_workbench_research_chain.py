"""Offline HTTP-to-episode chain; scripted models/sources, never live quality."""

from __future__ import annotations

from dataclasses import replace
import json
import os
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import intelligence.api.app as api
from intelligence.services import llm_refine
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelTurn, ModelToolCall
from intelligence.services.episode_store import JsonlEpisodeStore
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.run_store import RunStore
from intelligence.tests.test_workbench_conversation_integration import _send

QUESTION = "基于目前市场数据，后面市场会怎么演绎？"
DRAFT = "当前上涨家数增加，但成交未同步扩大。据此判断，延续性仍需观察，不能将上涨直接等同于趋势确认。"


class ObservingModel:
    def __init__(self, *, fabricated_reference: bool = False) -> None:
        self.fabricated_reference = fabricated_reference
        self.observations: list[dict] = []
        self.judge_requests: list[dict] = []
        self.writer_calls = 0

    def complete(self, *, messages, tools, timeout):
        assert timeout > 0
        tool_names = [item["function"]["name"] for item in tools]
        if "submit_grounding_report" in tool_names:
            request = json.loads(messages[-1]["content"])
            self.judge_requests.append(request)
            return ModelTurn(
                content=json.dumps(
                    {
                        "passed": True,
                        "rejected_sentence_indexes": [],
                        "issues": [],
                    }
                ),
                tool_calls=(),
            )
        self.writer_calls += 1
        assert self.writer_calls <= 5, "offline model did not terminate"
        task = json.loads(
            next(row["content"] for row in messages if row["role"] == "user")
        )
        observed = [
            json.loads(row["content"]) for row in messages if row["role"] == "tool"
        ]
        self.observations = observed
        if not observed:
            query = "initial"
        elif len(observed) == 1:
            last = observed[-1]
            if last.get("error"):
                query = "recover:" + last["error"]
            elif not last.get("evidence_ids"):
                query = "recover:empty"
            else:
                query = json.loads(last["observation"])["next_query"]
        else:
            evidence_refs = observed[-1]["evidence_ids"]
            if self.fabricated_reference:
                evidence_refs = ["never-registered-http-evidence"]
            return ModelTurn(
                content=json.dumps(
                    {
                        "status": "completed",
                        "draft": DRAFT,
                        "gaps": [],
                        "bindings": [
                            {
                                "output_id": row["output_id"],
                                "basis": row["grounding_mode"],
                                "evidence_hashes": evidence_refs,
                                "gap": "",
                            }
                            for row in task["research_contract"]["required_outputs"]
                        ],
                    },
                    ensure_ascii=False,
                ),
                tool_calls=(),
            )
        assert "market_data" in tool_names
        return ModelTurn(
            content="",
            tool_calls=(
                ModelToolCall(
                    call_id=f"http-chain-{self.writer_calls}",
                    name="market_data",
                    arguments={"query": query},
                ),
            ),
        )


@pytest.fixture(params=["off", "on"])
def offline_workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request):
    for key in tuple(os.environ):
        if key.startswith(("ASK_", "LLM_", "WORKBENCH_", "FORESIGHT_")) or key.endswith(
            "_API_KEY"
        ):
            monkeypatch.delenv(key)
    for key, value in {
        "HOME": str(tmp_path),
        "FINANCE_WS": str(tmp_path / "finance"),
        "FORESIGHT_USERS_DIR": str(tmp_path / "users"),
        "FORESIGHT_EPISODE_STORE": str(tmp_path / "episodes"),
        "AGENT_RUNTIME_BACKEND": "continuous_glm",
        "ASK_CONTINUOUS_RUNTIME": "on",
        "WORKBENCH_ADAPTIVE_RESEARCH": request.param,
        "FORESIGHT_STRICT_DERIVATION": "1",
        "WORKBENCH_RESEARCH_PROGRESS": "on",
        "WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES": "0",
        "WORKBENCH_TOOL_MENU_HIDE": "off",
        "ASK_EPISODE_HISTORY_COMPACTION": "off",
        "ASK_EPISODE_BUDGET_STATUS": "on",
        "FINANCE_NEWS_FETCH": "0",
        "FINANCE_WEB_SEARCH": "0",
        "KB_VAULT": str(tmp_path / "wiki"),
    }.items():
        monkeypatch.setenv(key, value)

    network_attempts = []

    def no_network(*args, **kwargs):
        network_attempts.append((args, kwargs))
        raise AssertionError("offline HTTP chain attempted a socket connection")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    monkeypatch.setattr(
        llm_refine,
        "complete",
        lambda *args, **kwargs: (
            json.dumps(
                {
                    "route_id": "market_forecast",
                    "subject": None,
                    "timeframe": None,
                    "confidence": 1.0,
                    "reason": "offline controller model",
                }
            ),
            "offline",
            None,
        ),
    )
    yield tmp_path
    assert not network_attempts, (
        "even caught outbound attempts violate the offline contract"
    )


@pytest.mark.parametrize("first_result", ["lead-a", "lead-b", "empty", "error"])
@pytest.mark.parametrize(
    "fabricated_reference", [False, True], ids=["bound", "fabricated"]
)
def test_http_research_follows_observation_and_persists_identity(
    offline_workbench: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_result: str,
    fabricated_reference: bool,
):
    model = ObservingModel(fabricated_reference=fabricated_reference)
    executed: list[str] = []

    def registry(frame, context, **kwargs):
        def source(query, tool_context):
            executed.append(query)
            if len(executed) == 1 and first_result == "error":
                raise RuntimeError("offline source unavailable")
            if len(executed) == 1 and first_result == "empty":
                return (
                    [],
                    "no fixture evidence",
                    ProviderTrace(
                        provider="offline:market",
                        capability="market_data",
                        status="success",
                        result_count=0,
                    ),
                )
            detail = (
                json.dumps({"next_query": first_result}, ensure_ascii=False)
                if len(executed) == 1
                else DRAFT
            )
            evidence = AgentEvidence(
                tool="market_data",
                title="offline market observation",
                detail=detail,
                source="offline fixture",
                source_date=context.today,
                evidence_tier="L4",
                content_hash=f"http-chain-evidence-{len(executed)}",
            )
            return (
                [evidence],
                detail,
                ProviderTrace(
                    provider="offline:market",
                    capability="market_data",
                    status="success",
                    source_trade_date=context.today,
                    result_count=1,
                ),
            )

        return ResearchToolRegistry(
            (
                ToolSpec(
                    name="market_data",
                    capability="market_data",
                    description="offline market source",
                    cost="local",
                    freshness="current",
                    runner=source,
                ),
            )
        )

    monkeypatch.setattr(api, "build_episode_registry", registry)
    monkeypatch.setattr(api, "GLMModelClient", lambda **kwargs: model)
    app = api.create_app(
        repo_root=Path(__file__).parent / "fixtures" / "chat_workbench_repo"
    )
    # Message completion does not join artifact publication; drain our own workers.
    with TestClient(app) as client, app.state.supervisor._executor:
        created = client.post(
            "/api/conversations", json={"title": "offline chain", "user": "alice"}
        )
        assert created.status_code == 200, created.text
        conversation_id = created.json()["conversation_id"]
        payload, run = _send(client, conversation_id, QUESTION, skill_mode="auto")
        run_id = payload["run_id"]
        response = client.get(
            f"/api/conversations/{conversation_id}/messages", params={"user": "alice"}
        )
        response.raise_for_status()
        result = response.json()

    assert executed[0] == "initial"
    assert len(executed) == 2, (executed, payload, result)
    expected = {"empty": "recover:empty", "error": "recover:tool_exception"}.get(
        first_result, first_result
    )
    assert executed[1] == expected, "follow-up must match the observed fixture lead"
    if first_result == "error":
        assert (
            model.observations[0]["detail"]
            == "RuntimeError: offline source unavailable"
        )
    assert model.writer_calls == 3
    artifact_path = (
        RunStore(user_id="alice").run_dir(run_id) / "continuous-episode.json"
    )
    artifact = json.loads(artifact_path.read_text())
    outcome = artifact["outcome"]
    assert outcome["usage"]["tool_calls"] == 2
    hashes = {row["content_hash"] for row in outcome["evidence"]}
    assert all(set(row["evidence_hashes"]) <= hashes for row in outcome["bindings"])
    assistant = next(row for row in result if row["role"] == "assistant")
    answer = (artifact_path.parent / "answer.md").read_text()
    assert assistant["content"] == answer
    if fabricated_reference:
        assert outcome["status"] != "completed", "fabricated evidence must not complete"
        assert DRAFT not in answer
        assert any(row["kind"] == "invalid_action" for row in outcome["events"])
    else:
        assert run["status"] == assistant["status"] == "completed"
        assert outcome["draft"] == answer == DRAFT
        assert len(model.judge_requests) == 1
        assert artifact["semantic_verifier"]["public_answer"] == answer
        assert artifact["semantic_verifier"]["judge_status"] == "passed"
        assert all(
            row["evidence_hashes"] == ["http-chain-evidence-2"]
            for row in outcome["bindings"]
        )
        assert assistant["citations"]
    episode_id = artifact["contract"]["task_id"]
    store = JsonlEpisodeStore(offline_workbench / "episodes")
    events, state = store.load(episode_id)
    assert state is not None and state.terminal
    assert dict(state.entry_identity) == {
        "schema_version": 1,
        "kind": "episode_entry_identity",
        "episode_id": episode_id,
        "entry": "workbench_conversation",
        "user_id": "alice",
        "run_id": run_id,
        "conversation_id": conversation_id,
        "assistant_message_id": assistant["message_id"],
    }
    assert [row.sequence for row in events] == list(range(1, len(events) + 1))
    assert artifact["runtime_handle"]["episode_id"] == episode_id
    assert artifact["runtime_handle"]["state"] == "closed"
    assert artifact["runtime_handle"]["scope"]["derive_mismatches"] == 0


def test_http_oracle_detects_observation_replacement(offline_workbench, monkeypatch):
    original = FinanceResearchHarness.project_tool_result

    def replace_lead(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        payload = json.loads(result.model_content)
        if payload["query"] == "initial":
            payload["observation"] = json.dumps({"next_query": "wrong-route"})
        return replace(result, model_content=json.dumps(payload))

    monkeypatch.setattr(FinanceResearchHarness, "project_tool_result", replace_lead)
    with pytest.raises(AssertionError, match="follow-up must match"):
        test_http_research_follows_observation_and_persists_identity(
            offline_workbench,
            monkeypatch,
            "lead-a",
            False,
        )


def test_http_oracle_detects_fabricated_reference_laundering(
    offline_workbench, monkeypatch
):
    original = FinanceResearchHarness.admit_finish

    def launder_reference(self, content, **kwargs):
        payload = json.loads(content)
        for binding in payload.get("bindings", []):
            if binding.get("evidence_hashes") == ["never-registered-http-evidence"]:
                binding["evidence_hashes"] = ["http-chain-evidence-2"]
        return original(self, json.dumps(payload), **kwargs)

    monkeypatch.setattr(FinanceResearchHarness, "admit_finish", launder_reference)
    with pytest.raises(AssertionError, match="fabricated evidence must not complete"):
        test_http_research_follows_observation_and_persists_identity(
            offline_workbench,
            monkeypatch,
            "lead-a",
            True,
        )
