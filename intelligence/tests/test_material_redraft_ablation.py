"""Real Workbench-to-author delivery plus offline model-pin tests; no live LLM."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services import llm_refine
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import RunStore
from scripts.material_redraft_ablation import (
    WRITER, select_writer_provider, transform_messages, verify_effective_provider,
)
from scripts.perspective_request_capture import RequestCapture, RequestCaptured
from scripts.redraft_projection import ProjectionRefused

CASES = json.loads((Path(__file__).resolve().parents[2] /
    "docs/verification/material-redraft-ablation-2026-09-29/cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_real_workbench_request_changes_only_h_without_changing_canonical_history(tmp_path, monkeypatch, case):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "absent.duckdb"))

    def forbidden(*_args, **_kwargs):
        pytest.fail("material-only capture must not call resolver or controller model")

    monkeypatch.setattr("intelligence.services.query_resolution.QueryResolver.resolve", forbidden)
    monkeypatch.setattr("intelligence.services.turn_controller.llm_refine.complete", forbidden)
    store = ConversationStore("alice", root=tmp_path / "conversations")
    runs = RunStore("alice", root=tmp_path / "runs")
    conversation = store.create_conversation()
    user = store.append_message(conversation.conversation_id, "user", case["prior_user"], run_id="synthetic")
    old = store.append_message(conversation.conversation_id, "assistant", case["prior_assistant"], run_id="synthetic")
    run = runs.create_run(case["query"], "ask", session_id=conversation.conversation_id)
    store.append_message(conversation.conversation_id, "user", case["query"], run_id=run.run_id)
    assistant = store.append_message(conversation.conversation_id, "assistant", "", status="running", run_id=run.run_id)

    class Capture(RequestCapture):
        def complete(self, *, messages, tools, **kwargs):
            self.before = deepcopy(messages)
            off, _ = transform_messages(messages, clean=False)
            assert off is messages
            transformed, self.metadata = transform_messages(messages, clean=True)
            assert messages == self.before
            super().complete(messages=transformed, tools=tools, **kwargs)

    capture = Capture(today="2026-09-29")
    adapter = capture.adapter()
    adapter._tier = "max"
    seen = []

    def registry(frame, context):
        seen.append((frame, context))
        return ResearchToolRegistry(())

    adapter._registry_factory = registry
    orchestrator = TurnOrchestrator(repo_root=tmp_path, conversation_store=store,
                                   run_store=runs, continuous_turn_adapter=adapter)
    with pytest.raises(RequestCaptured):
        orchestrator.run_turn(conversation_id=conversation.conversation_id, run_id=run.run_id,
                              assistant_message_id=assistant.message_id, query=case["query"],
                              skill_mode="auto", selected_skill_ids=[])
    payload = capture.payload()
    frame, context = seen[0]
    assert capture.calls == 1 and capture.tool_count == 0
    assert context.contract.allowed_capabilities == ()
    assert frame.material_contract.data_scope == "material_only"
    canonical = context.contract.material_grounding
    assert canonical.historical_assistant_statements[0].text == case["prior_assistant"]
    assert canonical.historical_assistant_statements[0].source_message_id == old.message_id
    assert any(s.source_message_id == user.message_id for s in canonical.materials)
    assert len(frame.conversation_materials.question_sources) == 2
    original = next(json.loads(m["content"]) for m in capture.before
                    if m["role"] == "user" and "research_contract" in m["content"])
    expected = deepcopy(original)
    expected["material_grounding"]["sources"] = [s for s in original["material_grounding"]["sources"] if s["ref"].startswith("M")]
    assert payload == expected
    assert capture.metadata["omitted_refs"] == ["H1"]
    assert [m for m in capture.messages if m["role"] != "user"] == [m for m in capture.before if m["role"] != "user"]
    assert all(case["prior_assistant"] not in m["content"] for m in capture.messages)
    # The retained original request still contains H; no in-place mutation.
    assert any(s["text"] == case["prior_assistant"] for s in original["material_grounding"]["sources"])


def test_provider_selection_excludes_other_models_without_fallback():
    flash = SimpleNamespace(model=WRITER)
    assert select_writer_provider([SimpleNamespace(model="glm-5.3"), flash]) == (flash,)
    verify_effective_provider((flash,))


@pytest.mark.parametrize("models", [[], ["glm-5.3"], [WRITER, WRITER]])
def test_missing_or_ambiguous_writer_blocks_before_transport(models):
    with pytest.raises(ProjectionRefused):
        select_writer_provider([SimpleNamespace(model=m) for m in models])


@pytest.mark.parametrize("models", [[], ["glm-5.3"], [WRITER, "glm-5.3"]])
def test_cross_model_effective_chain_is_refused(models):
    with pytest.raises(ProjectionRefused):
        verify_effective_provider([SimpleNamespace(model=m) for m in models])


def test_real_provider_override_cannot_silently_replace_flash_with_53():
    p = llm_refine.LLMProvider("synthetic", "not-a-real-key", "https://example.invalid", WRITER)
    with llm_refine.provider_override(p):
        verify_effective_provider(llm_refine.detect_providers())
        with pytest.raises(ProjectionRefused):
            verify_effective_provider(llm_refine.detect_providers("glm-5.3"))


@pytest.mark.parametrize("messages", [[], [{"role": "user", "content": "{}"}]])
def test_missing_author_payload_blocks_before_transport(messages):
    with pytest.raises(ProjectionRefused):
        transform_messages(messages, clean=True)
