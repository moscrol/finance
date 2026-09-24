"""Observation-driven research through the production runtime composition root.

Only the model and data sources are doubles. These tests establish reachability
and enforcement, not natural-model research quality or Workbench HTTP delivery.
"""

from __future__ import annotations

from dataclasses import replace
import json

import pytest

from intelligence.runtime import agent_episode
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import AgentOutcome, ModelToolCall, ModelTurn
from intelligence.services.cancel_signal import CancelSignal
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import InMemoryRootBudgetLedger
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.tests.conformance.fixtures import (
    FORBIDDEN_TOOL,
    MISSING_EVIDENCE_HASH,
    assert_no_dangling_bindings,
    completed_finish,
    make_context,
    make_frame,
    partial_finish,
)

LEAD_TOOL = "chain_lead_lookup"
SOURCE_TOOL = "chain_source_lookup"
SOURCE_HASH = "chain-source-hash"


@pytest.fixture(autouse=True)
def _fixed_policy(monkeypatch):
    for key, value in {
        "WORKBENCH_RESEARCH_PROGRESS": "on",
        "WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES": "0",
        "WORKBENCH_TOOL_MENU_HIDE": "off",
        "ASK_EPISODE_HISTORY_COMPACTION": "off",
        "ASK_EPISODE_BUDGET_STATUS": "on",
    }.items():
        monkeypatch.setenv(key, value)


class ObservingClient:
    """Choose the follow-up from the last observation, never from fixture state."""

    def __init__(self, *, first_tool=LEAD_TOOL, forged_finish=False, before_followup=None):
        self.first_tool = first_tool
        self.forged_finish = forged_finish
        self.before_followup = before_followup
        self.observations: list[dict] = []
        self.menus: list[set[str]] = []
        self.finishes: list[dict] = []
        self.calls = 0

    def complete(self, *, messages, tools, timeout):
        self.calls += 1
        assert timeout > 0
        assert self.calls <= 6, "research chain did not terminate"
        self.menus.append({tool["function"]["name"] for tool in tools})
        if not tools:
            return ModelTurn(json.dumps(partial_finish(gap="Research window closed")), ())
        observations = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        if not observations:
            assert self.calls == 1, "tool observation was lost between model turns"
            return self._call(self.first_tool, "initial lead")
        latest = observations[-1]
        self.observations.append(latest)
        if latest["tool"] != SOURCE_TOOL:
            if latest.get("ok") is False:
                query = f"recover:{latest['error']}"
            elif not latest.get("evidence_ids"):
                query = "recover:empty"
            else:
                query = json.loads(latest["observation"])["next_query"]
            if self.before_followup:
                self.before_followup()
            return self._call(SOURCE_TOOL, query)
        evidence_ids = latest["evidence_ids"]
        assert evidence_ids, "source lookup returned no evidence"
        # E identifiers are the model-visible contract; hashes remain audit-side.
        refs = (MISSING_EVIDENCE_HASH,) if self.forged_finish else tuple(evidence_ids)
        finish = completed_finish(draft="The retrieved source supports the assessment.", evidence_hashes=refs)
        self.finishes.append(finish)
        return ModelTurn(json.dumps(finish), ())

    def _call(self, name, query):
        return ModelTurn("", (ModelToolCall(f"chain-{self.calls}", name, {"query": query}),))


def _run_chain(
    *,
    lead="source-A",
    failure="",
    client=None,
    root_calls=4,
    cancel=None,
) -> tuple[AgentOutcome, ObservingClient, list[tuple[str, str]]]:
    executed: list[tuple[str, str]] = []

    def runner(name):
        def run(query, _context):
            executed.append((name, query))
            if name == LEAD_TOOL and failure == "exception":
                raise RuntimeError("fixture source unavailable")
            if name == LEAD_TOOL and failure == "empty":
                return [], "No matching source; absence is not a negative fact.", ProviderTrace(
                    provider="test:chain", capability="market_data", status="success", result_count=0,
                )
            observation = json.dumps({"next_query": lead}) if name == LEAD_TOOL else f"Read source: {query}"
            evidence = AgentEvidence(
                tool=name,
                title="Research chain fixture",
                detail=observation,
                source="offline fixture",
                source_date="2026-07-24",
                evidence_tier="L4",
                content_hash="chain-lead-hash" if name == LEAD_TOOL else SOURCE_HASH,
            )
            return [evidence], observation, ProviderTrace(
                provider="test:chain", capability="market_data", status="success", result_count=1,
            )
        return run

    registry = ResearchToolRegistry(tuple(
        ToolSpec(
            name=name,
            capability="news_search" if name == FORBIDDEN_TOOL else "market_data",
            description="Offline research chain fixture",
            cost="local",
            freshness="current",
            io_effect="local_read",
            runner=runner(name),
        )
        for name in (LEAD_TOOL, SOURCE_TOOL, FORBIDDEN_TOOL)
    ))
    frame = make_frame()
    context = make_context(
        frame,
        task_id="research-chain",
        max_steps=4,
        timeout=60.0,
        root_budget=InMemoryRootBudgetLedger(
            episode_id="research-chain",
            initial_calls=root_calls,
            # Unallocated headroom must not be usable without a grant.
            hard_calls_cap=4,
            initial_seconds=60.0,
            hard_seconds_cap=60.0,
        ),
    )
    client = client or ObservingClient()
    runtime = GLMAgentRuntime(client=client, is_cancelled=cancel)
    session = runtime.start(frame, context=context, registry=registry)
    try:
        return session.outcome, client, executed
    finally:
        session.close()


def _assert_delivered(outcome, executed, expected_query):
    assert executed == [(LEAD_TOOL, "initial lead"), (SOURCE_TOOL, expected_query)]
    assert outcome.status == "completed"
    assert outcome.stop_reason == "model_finish"
    assert outcome.usage.tool_calls == 2
    assert outcome.usage.llm_calls == 3
    assert outcome.usage.invalid_actions == 0
    assert_no_dangling_bindings(outcome)
    assert outcome.bindings[0].evidence_hashes == (SOURCE_HASH,)


@pytest.mark.parametrize("lead", ["source-A:2024", "source-B:2025"])
def test_observation_selects_next_query_and_real_evidence_binding(lead):
    outcome, client, executed = _run_chain(lead=lead)
    _assert_delivered(outcome, executed, lead)
    assert client.observations[0]["runtime_budget"]["research_progress"]["evidence_total"] == 1
    assert all(FORBIDDEN_TOOL not in menu for menu in client.menus)


@pytest.mark.parametrize("failure,error", [("empty", "empty"), ("exception", "tool_exception")])
def test_local_failure_returns_to_model_and_allows_alternate_tool(failure, error):
    outcome, client, executed = _run_chain(failure=failure)
    _assert_delivered(outcome, executed, f"recover:{error}")
    first = client.observations[0]
    if failure == "empty":
        assert first["ok"] is True
        assert first["evidence_ids"] == []
    else:
        assert first["ok"] is False
        assert first["error"] == error
    assert {e.content_hash for e in outcome.evidence} == {SOURCE_HASH}


def test_unauthorized_attempt_is_visible_but_does_not_prevent_later_research():
    outcome, client, executed = _run_chain(client=ObservingClient(first_tool=FORBIDDEN_TOOL))
    assert executed == [(SOURCE_TOOL, "recover:unknown_or_unauthorized_tool")]
    assert all(FORBIDDEN_TOOL not in menu for menu in client.menus)
    assert client.observations[0]["error"] == "unknown_or_unauthorized_tool"
    assert outcome.status == "completed"
    assert outcome.usage.invalid_actions == 1
    assert_no_dangling_bindings(outcome)


def test_fluent_finish_with_invented_reference_cannot_ship():
    outcome, client, executed = _run_chain(client=ObservingClient(forged_finish=True))
    assert len(executed) == 2
    assert client.finishes, "forged final must actually reach the harness"
    assert outcome.status != "completed"
    assert any(event.kind == "invalid_action" for event in outcome.events)
    assert_no_dangling_bindings(outcome)
    assert all(MISSING_EVIDENCE_HASH not in b.evidence_hashes for b in outcome.bindings)


def test_exhausted_root_budget_stops_chain_without_discarding_prior_evidence():
    outcome, client, executed = _run_chain(root_calls=1)
    assert executed == [(LEAD_TOOL, "initial lead")]
    assert client.menus[-1] == set()
    assert outcome.status == "partial"
    assert outcome.gaps
    assert {e.content_hash for e in outcome.evidence} == {"chain-lead-hash"}
    assert any(event.kind == "finalization" for event in outcome.events)


def test_cancel_after_observation_fences_the_followup_before_runner():
    cancel = CancelSignal()
    client = ObservingClient(before_followup=lambda: cancel.request("user", "test follow-up fence"))
    outcome, client, executed = _run_chain(client=client, cancel=cancel)
    assert client.observations, "cancel must arrive after an actual observation"
    assert executed == [(LEAD_TOOL, "initial lead")]
    assert outcome.stop_reason == "cancelled"
    assert {e.content_hash for e in outcome.evidence} == {"chain-lead-hash"}


def test_oracle_detects_lost_observation_content(monkeypatch):
    original = FinanceResearchHarness.project_tool_result

    def lose_content(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        payload = json.loads(result.model_content)
        if payload["tool"] == LEAD_TOOL:
            payload["observation"] = json.dumps({"next_query": "wrong-source"})
        return replace(result, model_content=json.dumps(payload))

    monkeypatch.setattr(FinanceResearchHarness, "project_tool_result", lose_content)
    outcome, _, executed = _run_chain(lead="source-A")
    with pytest.raises(AssertionError):
        _assert_delivered(outcome, executed, "source-A")
    assert executed[-1] == (SOURCE_TOOL, "wrong-source")


def test_oracle_detects_unauthorized_menu_leak(monkeypatch):
    original = agent_episode.tool_definitions_for_menu

    def leak_menu(menu, *, registry, context):
        forbidden = [
            item for item in registry.tool_definitions()
            if item["function"]["name"] == FORBIDDEN_TOOL
        ]
        return original(menu, registry=registry, context=context) + forbidden

    monkeypatch.setattr(agent_episode, "tool_definitions_for_menu", leak_menu)
    with pytest.raises(AssertionError):
        test_unauthorized_attempt_is_visible_but_does_not_prevent_later_research()


def test_oracle_detects_fabricated_reference_laundering(monkeypatch):
    original = FinanceResearchHarness.admit_finish

    def launder_reference(self, content, **kwargs):
        payload = json.loads(content)
        for binding in payload.get("bindings", []):
            if binding.get("evidence_hashes") == [MISSING_EVIDENCE_HASH]:
                binding["evidence_hashes"] = [SOURCE_HASH]
        return original(self, json.dumps(payload), **kwargs)

    monkeypatch.setattr(FinanceResearchHarness, "admit_finish", launder_reference)
    with pytest.raises(AssertionError):
        test_fluent_finish_with_invented_reference_cannot_ship()


def test_oracle_detects_unaccounted_tool_budget(monkeypatch):
    monkeypatch.setattr(InMemoryRootBudgetLedger, "consume_call", lambda self, seconds: None)
    with pytest.raises(AssertionError):
        test_exhausted_root_budget_stops_chain_without_discarding_prior_evidence()
