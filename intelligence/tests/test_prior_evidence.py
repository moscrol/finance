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
        source="本地结构化数据", source_date="2026-09-14", content_hash="original-local", io_effect="local_read",
        supports=("old_output",), observations=(StructuredObservation("A股", "2026-09-14", "上涨家数", 3126),),
        **kwargs,
    )


def _source(tmp_path, *, source_question=LOCAL):
    store = RunStore("alice", root=tmp_path / "runs")
    run = store.create_run(source_question, "ask", session_id="conv")
    user = Message("old-user", "conv", "user", source_question, "2026-09-20", "completed", run_id=run.run_id)
    answer = Message("old-answer", "conv", "assistant", "E1证明抛压衰竭。", "2026-09-20", "completed", run_id=run.run_id)
    messages = [user, answer]
    original = decide_turn(source_question, llm_complete=no_llm).task_frame
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


@pytest.fixture
def source(tmp_path):
    return _source(tmp_path)


@pytest.mark.parametrize("question", [
    LOCAL.replace("请只查本地数据，", "请").replace("，不联网。", "。"),
    "可以查真实数据。" + LOCAL.replace("请只查本地数据，", "请").replace("，不联网。", "。"),
], ids=["ordinary", "full"])
def test_frozen_review_can_restore_local_originals_from_ordinary_research(tmp_path, question):
    _, _, _, frame, _, _, load = _source(tmp_path, source_question=question)
    snapshot = load()
    assert snapshot.entries == (("E2", replace(_atom(), supports=())),)
    assert snapshot.excluded_ordinals == ("E1",)
    # Original broad permissions do not grant even a local read in this turn.
    assert build_episode_context(frame, task_id="ordinary-prior").contract.allowed_capabilities == ()


@pytest.mark.parametrize("question", [
    "只分析以下虚构材料，不查其他资料：市场上涨家数3126。为什么？",
    "假设市场上涨家数3126，只依据给定题设回答。",
])
def test_material_sources_cannot_be_promoted_to_original_local_evidence(tmp_path, question):
    *_, load = _source(tmp_path, source_question=question)
    with pytest.raises(ValueError, match="original episode identity mismatch"):
        load()


@pytest.mark.parametrize("effect", ["unknown", "external_or_mixed"])
@pytest.mark.parametrize("broad_source", [False, True])
def test_a_local_tool_name_does_not_override_the_recorded_execution_effect(source, tmp_path, effect, broad_source):
    if broad_source:
        source = _source(
            tmp_path / "ordinary", source_question=LOCAL.replace("请只查本地数据，", "请").replace("，不联网。", "。"),
        )
    _, _, _, _, payload, save, load = source
    payload["outcome"]["evidence"][1]["io_effect"] = effect
    save()
    with pytest.raises(ValueError, match="no admissible"):
        load()


@pytest.mark.parametrize("suffix", [
    "旧答写‘2026-09-14上涨3126家’。", "仍复核2026-09-11和2026-09-14这两天。",
], ids=["quoted-date", "same-window"])
def test_quoted_dates_and_an_unchanged_explicit_window_keep_originals(source, suffix):
    store, _, messages, _, _, _, _ = source
    question = REVIEW + suffix
    frame = decide_turn(question, conversation_materials=collect_material_turn_history(messages), llm_complete=no_llm).task_frame
    snapshot = load_previous_evidence(frame, messages=messages, store=store,
                                      conversation_id="conv", current_run_id="current")
    assert snapshot.entries == (("E2", replace(_atom(), supports=())),)


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


@pytest.mark.parametrize("legacy", [False, True])
def test_nullable_history_metadata_preserves_ordinary_prior_evidence(source, legacy):
    _, _, _, _, payload, save, load = source
    if legacy:
        for row in payload["outcome"]["evidence"]:
            row.pop("history_provenance")
    save()
    assert load().entries[0][1] == replace(_atom(), supports=())


@pytest.mark.parametrize("value", [False, "", {}, {"query_id": "forged"}])
def test_malformed_history_metadata_does_not_become_ordinary_evidence(source, value):
    _, _, _, _, payload, save, load = source
    payload["outcome"]["evidence"][1]["history_provenance"] = value
    save()
    with pytest.raises(ValueError):
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


@pytest.mark.parametrize("question", [
    REVIEW + "现在换个问题。", REVIEW + "现在换题，解释量比的定义。", REVIEW + "改为2026年9月18日。",
    REVIEW + "以今天为准。", REVIEW + "只复核9月19日的数据。", REVIEW + "只看本周的数据。",
    REVIEW + "只复核2026-09-11的数据。", REVIEW + "以明天为准。",
], ids=["new-task", "switch-topic", "full-date", "today", "yearless-date", "this-week", "narrow-window", "tomorrow"])
def test_changed_scope_does_not_inherit_old_observations(source, monkeypatch, question):
    store, _, messages, frame, _, _, _ = source
    changed = replace(frame, raw_question=question)
    monkeypatch.setattr(store, "read_episode_artifact", lambda *a, **k: pytest.fail("new scope read old originals"))
    with pytest.raises(ValueError):
        load_previous_evidence(changed, messages=messages, store=store,
                               conversation_id="conv", current_run_id="current")


@pytest.mark.parametrize("durable", [False, True])
@pytest.mark.parametrize("broad_source", [False, True])
def test_actual_loop_sees_remapped_originals_without_tools_or_inherited_coverage(source, tmp_path, durable, broad_source):
    from uuid import uuid4

    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.episode_evidence import EpisodeEvidenceSnapshot
    from intelligence.services.episode_store import JsonlEpisodeStore
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.tests.test_agent_episode import ScriptedModel

    if broad_source:
        source = _source(
            tmp_path / "ordinary", source_question=LOCAL.replace("请只查本地数据，", "请").replace("，不联网。", "。"),
        )
    _, _, _, frame, _, _, load = source
    context = replace(build_episode_context(frame, task_id=f"prior-{uuid4().hex}"), prior_evidence=load())
    store = JsonlEpisodeStore(tmp_path / "episodes") if durable else None
    finish = ModelTurn(json.dumps({
        "status": "completed", "draft": "上涨家数为3126（E1）。总量不足以证明抛压衰竭，撤回该断言。",
        "gaps": [], "bindings": [
            {"output_id": "direct_answer", "evidence_hashes": ["E1"], "basis": "evidence", "gap": ""},
            {"output_id": "evidence_boundary", "evidence_hashes": [], "basis": "user_premise", "gap": ""},
        ],
    }), (), "scripted", "")
    class ModelAfterCheckpoint(ScriptedModel):
        def complete(self, **kwargs):
            if store is not None:
                _, state = store.load(context.contract.task_id)
                snapshot = EpisodeEvidenceSnapshot.from_dict(
                    state.evidence_snapshot, episode_id=context.contract.task_id,
                )
                assert snapshot.presented_evidence == tuple(atom for _, atom in context.prior_evidence.entries)
                assert snapshot.presented_evidence[0].supports == ()
                assert snapshot.covered_outputs == ()
            return super().complete(**kwargs)

    model = ModelAfterCheckpoint([finish])
    episode = ContinuousAgentEpisode(model, store=store)
    continuations = []
    outcome = episode.run(task_frame=frame, context=context, registry=ResearchToolRegistry(()),
                          _continuation_sink=continuations)
    assert outcome.status == "completed"
    assert outcome.usage.tool_calls == 0
    assert all(call["tools"] == [] for call in model.calls)
    opening = next(json.loads(m["content"]) for m in model.calls[0]["messages"]
                   if m.get("role") == "user" and '"research_contract"' in m["content"])
    # The same material-only contract can have restored tool originals. That
    # context keeps canonical E bindings; the M/H-only vocabulary cannot express them.
    assert "finish_format" not in opening["material_grounding"]
    assert "historical_assistant_statements" in opening["material_grounding"]
    blocks = [json.loads(m["content"]) for m in model.calls[0]["messages"]
              if m.get("role") == "user" and '"kind": "prior_tool_evidence"' in m["content"]]
    assert len(blocks) == 1
    assert blocks[0]["receipt"]["bindings"] == [{"old_ref": "E2", "new_ref": "E1", "content_hash": "original-local"}]
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0].observations == _atom().observations
    assert continuations[0].initial_evidence_snapshot.covered_outputs == ()
    assert not any(e.kind == "tool_request" for e in outcome.events)
    # P6 的结构校验对同一 outcome 复查绑定来源：恢复的旧 hash 不得再被判成越界。
    from intelligence.services.episode_verifier import verify_episode_outcome

    verified = verify_episode_outcome(context.contract, outcome)
    assert [str(getattr(issue.code, "value", issue.code)) for issue in verified.issues
            if "material_source" in str(getattr(issue.code, "value", issue.code))] == []


@pytest.mark.parametrize("reference_loop", [False, True])
def test_restored_original_context_keeps_legacy_format_in_repair_finalizer_and_headless(source, reference_loop):
    from uuid import uuid4

    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.codex_headless_runtime import CodexHeadlessRuntime
    from intelligence.runtime.episode_finalizer import EpisodeFinalizer
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
    from intelligence.services.episode_protocol import build_episode_input, finish_json_schema
    from intelligence.services.material_grounding import claim_finish_format
    from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.tests.test_agent_episode import ScriptedModel

    _, _, _, frame, _, _, load = source
    context = replace(build_episode_context(frame, task_id=f"prior-format-{uuid4().hex}"), prior_evidence=load())
    registry = ResearchToolRegistry(())
    bare_context = replace(context, prior_evidence=None)
    assert "finish_format" in json.loads(build_episode_input(frame, bare_context, registry))["material_grounding"]
    assert "format" in finish_json_schema(context.contract)["properties"]
    assert "format" not in finish_json_schema(context.contract, prior_evidence=context.prior_evidence)["properties"]
    assert claim_finish_format(context.contract, prior_evidence=context.prior_evidence) is None

    def completed(*, revised=False):
        text = "撤回旧答关于抛压衰竭的断言，本轮未新增核验。" if revised else "撤回旧答关于抛压衰竭的断言。"
        return ModelTurn(json.dumps({"status": "completed", "draft": text, "gaps": [], "bindings": [
            {"output_id": "direct_answer", "evidence_hashes": [], "basis": "evidence", "gap": "", "claims": [{
                "text": text, "kind": "historical_assistant_statement",
                "old_answer_coordinate": "old-answer", "historical_quote": "抛压衰竭", "basis": "assistant_judgment",
            }]},
            {"output_id": "evidence_boundary", "evidence_hashes": [], "basis": "user_premise", "gap": ""},
        ]}), (), "offline")

    model = ScriptedModel([completed(), completed(revised=True)])
    loop = HarnessReferenceLoop(model) if reference_loop else ContinuousAgentEpisode(model)
    states = []
    first = loop.run(task_frame=frame, context=context, registry=registry, _continuation_sink=states)
    assert first.status == "completed"
    goal = RepairGoal(context.contract.task_id, "prior-format-repair", 1, ("evidence_boundary",),
                      (), (), (), CoverageDelta(0, 0, 0), 0, 20)
    result = loop.resume(states[0], first, goal)
    assert result.status == "completed" and result.usage.tool_calls == 0
    repair = next(json.loads(event.payload["content"]) for event in result.events
                  if event.kind == "model_input" and event.payload.get("source") == "repair_goal")
    assert "finish_format" not in repair

    recovery = ScriptedModel([completed()])
    EpisodeFinalizer(recovery).recover(task_frame=frame, context=context, evidence=first.evidence,
                                       gaps=(), failure_reason="invalid_model_finish")
    finalizer_payload = json.loads(recovery.calls[0]["messages"][1]["content"])
    assert "finish_format" not in finalizer_payload["material_grounding"]
    assert '"bindings"' in recovery.calls[0]["messages"][0]["content"]

    class SchemaCaptured(BaseException):
        pass

    def capture(command):
        schema = json.loads((command.cwd / "episode-finish.schema.json").read_text())
        assert schema == finish_json_schema()
        raise SchemaCaptured()

    with pytest.raises(SchemaCaptured):
        CodexHeadlessRuntime(command_runner=capture).run(task_frame=frame, context=context, registry=registry)


def test_restored_originals_reject_explicit_compact_finish_at_validation(source):
    from intelligence.services.episode_protocol import validate_episode_finish
    from intelligence.tests.test_material_answer_authoring import compact_finish, history_setup, legacy_finish

    _, _, _, _, _, _, load = source
    _, bare_context = history_setup()
    restored = replace(bare_context, prior_evidence=load())
    empty = replace(restored, prior_evidence=replace(restored.prior_evidence, entries=()))
    compact = compact_finish()
    # A provider can ignore the advertised schema. Admission must enforce the
    # same M/H-only boundary as the prompt, even when this answer uses no E ref.
    with pytest.raises(ValueError, match="unsupported author format"):
        validate_episode_finish(compact, context=restored, evidence=())
    baseline = validate_episode_finish(compact, context=bare_context, evidence=())
    assert validate_episode_finish(compact, context=empty, evidence=()) == baseline
    assert validate_episode_finish(legacy_finish(restored), context=restored, evidence=()) == baseline


def test_frozen_scope_exempts_only_restored_prior_atoms(source):
    """P6 冻结范围规则 × #819 旧输入恢复：只有原件校验过的旧 hash 可绑，本轮新读仍拒。"""
    from intelligence.services.agent_runtime import OutputEvidenceBinding
    from intelligence.services.material_grounding import binding_source_errors, grounding_scope

    _, _, _, frame, _, _, load = source
    # 独立的 episode id：root budget 按 live episode 去重，复用 "current" 会撞上一条测试的预算。
    contract = build_episode_context(frame, task_id="frozen-scope-check").contract
    assert grounding_scope(contract) == "material_only"
    prior = frozenset(item.content_hash for _, item in load().entries)
    assert prior == {"original-local"}
    fresh = replace(_atom(), content_hash="fresh-local-read", supports=())
    evidence = (replace(_atom(), supports=()), fresh)

    def binding(*hashes):
        return OutputEvidenceBinding(output_id="direct_answer", evidence_hashes=tuple(hashes), gap="", basis="evidence")

    assert binding_source_errors(contract, binding("original-local"), "x", evidence, frozen_prior_hashes=prior) == ()
    assert binding_source_errors(contract, binding("fresh-local-read"), "x", evidence, frozen_prior_hashes=prior) == (
        "binding exceeds frozen data scope: fresh-local-read",
    )
    assert binding_source_errors(contract, binding("original-local"), "x", evidence) == (
        "binding exceeds frozen data scope: original-local",
    )
    assert binding_source_errors(contract, binding("missing"), "x", evidence, frozen_prior_hashes=frozenset({"missing"})) == (
        "binding exceeds frozen data scope: missing",
    )
