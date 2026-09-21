from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date
import json

import pytest

from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.conversation_materials import collect_material_turn_history
from intelligence.services.conversation_store import Message
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.prior_evidence import load_previous_evidence
from intelligence.services.run_store import RunStore, STATUS_COMPLETED
from intelligence.services.turn_controller import decide_turn
from intelligence.tests.test_reasoning_input_boundaries import LOCAL, REVIEW, no_llm


def _atom(**kwargs):
    return AgentEvidence(
        tool="finance_query", title="市场日频", detail="上涨家数=3126",
        source="本地结构化数据", source_date="2026-09-14", content_hash="original-local",
        supports=("old_output",), observations=(StructuredObservation("A股", "2026-09-14", "上涨家数", 3126),),
        **kwargs,
    )


@pytest.fixture
def source(tmp_path):
    store = RunStore("alice", root=tmp_path / "runs")
    run = store.create_run(LOCAL, "ask", session_id="conv")
    user = Message("old-user", "conv", "user", LOCAL, "2026-09-20", "completed", run_id=run.run_id)
    answer = Message("old-answer", "conv", "assistant", "E1证明抛压衰竭。", "2026-09-20", "completed", run_id=run.run_id)
    messages = [user, answer]
    original = decide_turn(LOCAL, llm_complete=no_llm).task_frame
    frame = decide_turn(REVIEW, conversation_materials=collect_material_turn_history(messages), llm_complete=no_llm).task_frame
    payload = {
        "schema_version": 1, "execution_kind": "continuous_episode",
        "task_frame": original.to_dict(),
        "contract": {"task_id": f"{run.run_id}:{answer.message_id}", "task_frame_hash": original.task_frame_hash},
        "outcome": {"task_frame_hash": original.task_frame_hash, "status": "completed",
                    "evidence": [asdict(replace(_atom(), tool="web_search", content_hash="external")), asdict(_atom())]},
        "research_context": {"information_cutoff": {"as_of_date": "2026-09-18"}},
    }
    def save():
        store.add_artifact(run.run_id, "continuous-episode.json", json.dumps(payload),
                           renderer="json", title="private", visibility="internal", downloadable=False)
    save()
    store.finish_run(run.run_id, STATUS_COMPLETED)
    def load(**kwargs):
        return load_previous_evidence(frame, messages=messages, store=store,
                                      conversation_id="conv", current_run_id="current", **kwargs)
    return store, run, messages, frame, payload, save, load


def test_only_original_local_atoms_are_restored_without_old_targets(source):
    _, run, messages, frame, _, _, load = source
    snapshot = load()
    assert snapshot.source_run_id == run.run_id
    assert snapshot.source_message_id == messages[-1].message_id
    assert snapshot.task_frame_hash == frame.task_frame_hash
    assert snapshot.excluded_ordinals == ("E1",)
    ref, atom = snapshot.entries[0]
    assert ref == "E2"
    assert atom == replace(_atom(), supports=())
    assert snapshot.receipt()["artifact_sha256"]
    assert "抛压衰竭" not in json.dumps(snapshot.receipt(), ensure_ascii=False)


@pytest.mark.parametrize("mutation", ["body", "missing", "symlink", "registration", "user", "session", "active"])
def test_artifact_integrity_and_ownership_fail_closed(source, tmp_path, mutation):
    store, run, _, _, _, _, load = source
    path = store.run_dir(run.run_id) / "continuous-episode.json"
    if mutation == "body":
        # Preserve length and valid schema: only the registered digest catches this.
        path.write_text(path.read_text().replace("3126", "3127"))
    elif mutation == "missing":
        path.unlink()
    elif mutation == "symlink":
        moved = tmp_path / "moved.json"
        path.rename(moved)
        path.symlink_to(moved)
    else:
        stored = store.load_run(run.run_id)
        if mutation == "registration":
            stored.artifacts = []
        elif mutation == "user":
            stored.user = "bob"
        elif mutation == "session":
            stored.session_id = "other-conversation"
        else:
            stored.status = "running"
        store._write_run(stored)
    with pytest.raises((OSError, ValueError)):
        load()


@pytest.mark.parametrize("mutation", ["task_id", "question", "frame_hash", "outcome_hash", "unknown_field", "bad_bool", "bad_value", "duplicate", "no_evidence", "cutoff", "schema_version"])
def test_registered_but_inconsistent_original_is_rejected(source, mutation):
    _, _, _, _, payload, save, load = source
    if mutation == "task_id":
        payload["contract"]["task_id"] = "different-run:old-answer"
    elif mutation == "question":
        payload["task_frame"]["raw_question"] = "其他问题"
    elif mutation == "frame_hash":
        payload["contract"]["task_frame_hash"] = "other"
    elif mutation == "outcome_hash":
        payload["outcome"]["task_frame_hash"] = "other"
    elif mutation == "unknown_field":
        payload["outcome"]["evidence"][1]["future_schema"] = True
    elif mutation == "bad_bool":
        payload["outcome"]["evidence"][1]["deep_read"] = "false"
    elif mutation == "bad_value":
        payload["outcome"]["evidence"][1]["observations"][0]["value"] = True
    elif mutation == "duplicate":
        payload["outcome"]["evidence"].append(payload["outcome"]["evidence"][1])
    elif mutation == "no_evidence":
        payload["outcome"]["evidence"] = []
    elif mutation == "schema_version":
        payload["schema_version"] = 99
    else:
        payload["research_context"] = None
    save()
    with pytest.raises(ValueError):
        load()


@pytest.mark.parametrize("day", [None, "2026-09-22", "2026-09-14 garbage"])
def test_unqualified_source_dates_are_not_admitted(source, day):
    _, _, _, _, payload, save, load = source
    payload["outcome"]["evidence"][1]["source_date"] = day
    save()
    with pytest.raises(ValueError, match="no admissible"):
        load()


def test_current_cutoff_and_target_frame_are_rechecked(source):
    *_, load = source
    snapshot = load()
    assert snapshot.admitted(task_frame_hash=snapshot.task_frame_hash, cutoff=date(2026, 9, 11)) == ()
    with pytest.raises(ValueError, match="different task frame"):
        snapshot.admitted(task_frame_hash="other", cutoff=date(2026, 9, 18))


@pytest.mark.parametrize("mutation", ["cross_conv", "source_message", "missing_user", "failed_answer", "history_unavailable"])
def test_authoritative_bounded_message_chain_is_required(source, mutation):
    _, _, messages, _, _, _, load = source
    if mutation == "cross_conv":
        messages[-1].conversation_id = "other"
    elif mutation == "source_message":
        messages[-1].message_id = "unbound"
    elif mutation == "missing_user":
        messages.pop(0)
    elif mutation == "failed_answer":
        messages[-1].status = "failed"
    with pytest.raises(ValueError):
        load(history_unavailable=mutation == "history_unavailable")


@pytest.mark.parametrize("question", [
    "请复核刚才的解释。只依据本轮材料回答。",
    "> 请复核刚才的解释。仍只用已取得的本地数据。",
    REVIEW + "只依据本轮材料回答。",
])
def test_unrequested_reuse_never_opens_originals(source, monkeypatch, question):
    store, _, messages, _, _, _, _ = source
    frame = decide_turn(question, conversation_materials=collect_material_turn_history(messages), llm_complete=no_llm).task_frame
    monkeypatch.setattr(store, "read_episode_artifact", lambda *a, **k: pytest.fail("unauthorized snapshot read"))
    assert load_previous_evidence(frame, messages=messages, store=store,
                                  conversation_id="conv", current_run_id="current") is None


@pytest.mark.parametrize("question", [REVIEW + "现在换个问题。", REVIEW + "改为2026年9月18日。"])
def test_changed_scope_does_not_inherit_old_observations(source, monkeypatch, question):
    store, _, messages, frame, _, _, _ = source
    changed = replace(frame, raw_question=question)
    monkeypatch.setattr(store, "read_episode_artifact", lambda *a, **k: pytest.fail("new scope read old originals"))
    with pytest.raises(ValueError):
        load_previous_evidence(changed, messages=messages, store=store,
                               conversation_id="conv", current_run_id="current")


def test_actual_loop_sees_remapped_originals_without_tools_or_inherited_coverage(source):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.tests.test_agent_episode import ScriptedModel

    _, _, _, frame, _, _, load = source
    context = replace(build_episode_context(frame, task_id="current"), prior_evidence=load())
    finish = ModelTurn(json.dumps({
        "status": "completed", "draft": "上涨家数为3126（E1）。总量不足以证明抛压衰竭，撤回该断言。",
        "gaps": [], "bindings": [
            {"output_id": "direct_answer", "evidence_hashes": ["E1"], "basis": "evidence", "gap": ""},
            {"output_id": "evidence_boundary", "evidence_hashes": [], "basis": "user_premise", "gap": ""},
        ],
    }), (), "scripted", "")
    model = ScriptedModel([finish])
    episode = ContinuousAgentEpisode(model)
    continuations = []
    outcome = episode.run(task_frame=frame, context=context, registry=ResearchToolRegistry(()),
                          _continuation_sink=continuations)
    assert outcome.status == "completed"
    assert outcome.usage.tool_calls == 0
    assert all(call["tools"] == [] for call in model.calls)
    blocks = [json.loads(m["content"]) for m in model.calls[0]["messages"]
              if m.get("role") == "user" and '"kind": "prior_tool_evidence"' in m["content"]]
    assert len(blocks) == 1
    assert blocks[0]["receipt"]["bindings"] == [{"old_ref": "E2", "new_ref": "E1", "content_hash": "original-local"}]
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0].observations == _atom().observations
    assert continuations[0].initial_evidence_snapshot.covered_outputs == ()
    assert not any(e.kind == "tool_request" for e in outcome.events)
