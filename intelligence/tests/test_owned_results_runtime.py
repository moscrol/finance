"""Native episode/store/repair/recovery boundaries, with no live model."""

import json
from dataclasses import replace
from datetime import date

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_store import JsonlEpisodeStore
from intelligence.services.episode_restore import RestoreUnavailable
from intelligence.services.episode_messages import derive_messages, to_provider
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.repair_coordinator import RepairGoal, CoverageDelta
from intelligence.services.research_contract import InMemoryRootBudgetLedger
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolRunResult, ToolSpec
from intelligence.tests.owned_result_support import frame_context, source_fixture, finish_payload


def _registry(source):
    def runner(_query, _context):
        return ToolRunResult(source.evidence, source.observation, source.trace,
                             dataset=source.dataset, query_basis=source.query_basis)
    return ResearchToolRegistry((ToolSpec("mainline_context", "mainline_context", "同日行情", "local",
                                         "current", runner, io_effect="local_read"),))


class _Model:
    def __init__(self):
        self.calls = 0
        self.ref = ""
        self.source = source_fixture()
        self.seen = []

    def complete(self, *, messages, **_kwargs):
        self.calls += 1
        self.seen.append(json.loads(json.dumps(messages)))
        if self.calls == 1:
            return ModelTurn(json.dumps({"kind": "PLAN", "task_summary": "核对同日板块量价资格",
                "answer_elements": ["direct_assessment"], "hypotheses": [], "evidence_needs": ["同日主线行情"],
                "candidate_actions": ["mainline_context"], "branch_goals": [], "open_gaps": [], "revision": 1,
            }, ensure_ascii=False), ())
        if self.calls == 2:
            return ModelTurn("", (ModelToolCall("d4-source", "mainline_context", {"query": "同日行情"}),))
        for message in messages:
            if message["role"] != "tool":
                continue
            data = json.loads(message["content"])
            if "owned_results" in data:
                self.ref = next(p["result_ref"] for p in data["owned_results"]["parts"]
                                if "医药生物主题中的免疫治疗" in p["text"])
        return ModelTurn(json.dumps(finish_payload([{"result_ref": self.ref}], source=self.source), ensure_ascii=False), ())


def test_actual_episode_persists_only_the_adopted_ownership_receipt(tmp_path):
    frame, context = frame_context(task_id="native-owned-main")
    model, store = _Model(), JsonlEpisodeStore(tmp_path / "episodes")
    outcome = ContinuousAgentEpisode(model, store=store).run(task_frame=frame, context=context,
                                                            registry=_registry(model.source))
    assert outcome.stop_reason == "model_finish"
    assert "不满足严格双红" in outcome.draft
    finish = next(e for e in reversed(outcome.events) if e.kind == "finish")
    assert finish.to_dict()["payload"]["owned_answer"]["parts"] == [{"result_ref": model.ref}]
    events, state = store.load(context.contract.task_id)
    assert events[-1].payload["owned_answer"] == finish.payload["owned_answer"]
    assert state.terminal

    # Actual appended native input and derive_messages reconstruct the same prefix.
    last_model = next(e for e in reversed(events) if e.kind == "model_turn")
    assert to_provider(derive_messages(e for e in events if e.sequence < last_model.sequence)) == model.seen[-1]
    reopened = replace(context, _owned_result_sources=[])
    restored = ContinuousAgentEpisode.restore(context.contract.task_id, JsonlEpisodeStore(tmp_path / "episodes"),
                                               context=reopened, registry=_registry(model.source))
    assert restored.disposition == "already_terminal" and reopened._owned_result_sources
    from intelligence.services.research_harness import FinanceResearchHarness
    admission = FinanceResearchHarness().admit_finish(finish_payload([{"result_ref": model.ref}]),
        context=reopened, evidence=outcome.evidence, registry=_registry(model.source))
    assert admission.accepted and admission.draft == outcome.draft
    for tightened in (replace(reopened, information_cutoff=InformationCutoff(date(2026, 9, 29), "requested")),
                      replace(reopened, contract=replace(reopened.contract, task_id="another-run"))):
        with pytest.raises(RestoreUnavailable):
            ContinuousAgentEpisode.restore(context.contract.task_id, store, context=tightened, registry=_registry(model.source))

    class MissingSourceStore:
        def writer(self, episode_id):
            return store.writer(episode_id)

        def load(self, episode_id):
            saved, checkpoint = store.load(episode_id)
            return tuple(replace(e, payload={**e.to_dict()["payload"], "query_basis": {}})
                         if e.kind == "tool_result" else e for e in saved), checkpoint

    with pytest.raises(RestoreUnavailable, match="owned result source/ref/receipt unavailable"):
        ContinuousAgentEpisode.restore(context.contract.task_id, MissingSourceStore(), context=replace(context, _owned_result_sources=[]),
                                       registry=_registry(model.source))


def _repair_goal(context):
    return RepairGoal(episode_id=context.contract.task_id, repair_goal_id="owned-repair", cycle=1,
                     missing_answer_elements=("direct_assessment",), unsupported_claims=(),
                     missing_evidence_modes=(), attempted_actions=(), evidence_progress=CoverageDelta(1, 0, 1),
                     remaining_calls=0, remaining_seconds=8)


@pytest.mark.parametrize("invalid", [False, True])
def test_real_repair_adopts_new_receipt_or_carries_exact_previous_body(tmp_path, invalid):
    class RepairModel(_Model):
        def complete(self, **kwargs):
            if self.calls < 3:
                return super().complete(**kwargs)
            self.calls += 1
            if invalid:
                return ModelTurn("invalid finish", ())
            return ModelTurn(json.dumps(finish_payload([{"result_ref": self.ref}, "自由研判已修订。"]), ensure_ascii=False), ())

    frame, context = frame_context(task_id=f"owned-repair-{invalid}")
    model, store, states = RepairModel(), JsonlEpisodeStore(tmp_path / "episodes"), []
    episode = ContinuousAgentEpisode(model, store=store)
    previous = episode.run(task_frame=frame, context=context, registry=_registry(model.source), _continuation_sink=states)
    repaired = episode.resume(states[0], previous, _repair_goal(context))
    finish = next(e for e in reversed(repaired.events) if e.kind == "finish")
    receipt = finish.to_dict()["payload"]["owned_answer"]
    assert "不满足严格双红" in repaired.draft
    assert receipt["free_blocks"] == (0 if invalid else 1)
    if invalid:
        assert repaired.stop_reason == "invalid_repair_finish" and repaired.draft == previous.draft
    else:
        assert repaired.stop_reason == "repair_model_finish" and repaired.draft.endswith("自由研判已修订。")


def test_actual_finalizer_gets_delivered_refs_without_private_witness(tmp_path):
    class RecoverModel(_Model):
        def complete(self, *, messages, **kwargs):
            if self.calls < 2:
                return super().complete(messages=messages, **kwargs)
            self.calls += 1
            if self.calls == 3:
                return ModelTurn("", (), error="model unavailable")
            payload = json.loads(messages[-1]["content"])
            view = payload["owned_results"]
            ref = next(p["result_ref"] for p in view["parts"] if "医药生物主题中的免疫治疗" in p["text"])
            assert "source_digest" not in messages[-1]["content"]
            assert "source_cards" not in messages[-1]["content"]
            return ModelTurn(json.dumps(finish_payload([{"result_ref": ref}]), ensure_ascii=False), ())

    frame, context = frame_context(task_id="owned-finalizer")
    model = RecoverModel()
    outcome = ContinuousAgentEpisode(model, finalizer=EpisodeFinalizer(model), store=JsonlEpisodeStore(tmp_path / "episodes")).run(
        task_frame=frame, context=context, registry=_registry(model.source))
    assert outcome.stop_reason == "finalization_recovered"
    finish = next(e for e in reversed(outcome.events) if e.kind == "finish")
    assert finish.payload["owned_answer"] and "不满足严格双红" in outcome.draft


@pytest.mark.parametrize("valid", [True, False])
def test_actual_deadline_carry_chooses_receipt_for_the_adopted_body(monkeypatch, tmp_path, valid):
    import intelligence.runtime.agent_episode as episode_module
    import intelligence.services.research_contract as contract_module

    now = [100.0]
    monkeypatch.setattr(episode_module, "monotonic", lambda: now[0])
    monkeypatch.setattr(contract_module.time, "monotonic", lambda: now[0])
    frame, base = frame_context(task_id=f"owned-deadline-{valid}")
    root = InMemoryRootBudgetLedger(episode_id=base.contract.task_id, initial_calls=6, hard_calls_cap=6,
                                   initial_seconds=6, hard_seconds_cap=6)
    context = replace(base, root_budget=root)

    class DeadlineModel(_Model):
        def complete(self, *, timeout, **kwargs):
            if self.calls < 3:
                return super().complete(timeout=timeout, **kwargs)
            self.calls += 1
            now[0] += timeout + 0.5
            payload = finish_payload(["自由分析已重排。", {"result_ref": self.ref}]) if valid else "bad finish"
            return ModelTurn(json.dumps(payload, ensure_ascii=False) if valid else payload, ())

    model, states = DeadlineModel(), []
    episode = ContinuousAgentEpisode(model, store=JsonlEpisodeStore(tmp_path / "episodes"))
    previous = episode.run(task_frame=frame, context=context, registry=_registry(model.source), _continuation_sink=states)
    carried = episode.resume(states[0], previous, _repair_goal(context))
    assert carried.stop_reason == "repair_deadline_exhausted"
    receipt = next(e.to_dict()["payload"]["owned_answer"] for e in reversed(carried.events) if e.kind == "finish")
    assert receipt["free_blocks"] == (1 if valid else 0)
    assert (carried.draft != previous.draft) is valid
    from hashlib import sha256
    assert receipt["draft_sha256"] == sha256(carried.draft.encode()).hexdigest()


def test_paused_native_source_restores_refs_into_the_first_recovery_model_request(tmp_path):
    frame, context = frame_context(task_id="owned-prefix-reopen")
    source_model, store = _Model(), JsonlEpisodeStore(tmp_path / "episodes")
    drive = ContinuousAgentEpisode(source_model, store=store).manual_drive(task_frame=frame, context=context,
                                                                        registry=_registry(source_model.source))
    assert drive.run_until("tools_settled").phase == "tools_settled"
    drive.close()
    saved, _ = store.load(context.contract.task_id)
    original_tool = next(e for e in saved if e.kind == "tool_result")
    original_parts = json.loads(original_tool.payload["model_content"])["owned_results"]["parts"]
    fresh = replace(context, _owned_result_sources=[])
    result = ContinuousAgentEpisode.restore(context.contract.task_id, JsonlEpisodeStore(tmp_path / "episodes"),
                                             context=fresh, registry=_registry(source_model.source))
    assert result.disposition == "resumable"
    derived = derive_messages(result.events)
    assert next(m.content for m in derived if m.role == "tool") == original_tool.payload["model_content"]

    class RecoveryModel:
        def complete(self, *, messages, **_kwargs):
            payload = json.loads(messages[-1]["content"])
            assert payload["owned_results"]["parts"] == original_parts
            ref = next(p["result_ref"] for p in original_parts if "医药生物主题中的免疫治疗" in p["text"])
            return ModelTurn(json.dumps(finish_payload([{"result_ref": ref}]), ensure_ascii=False), ())

    turn = EpisodeFinalizer(RecoveryModel()).recover(task_frame=frame, context=fresh, evidence=source_model.source.evidence,
                                                   gaps=(), failure_reason="interrupted")
    from intelligence.services.research_harness import FinanceResearchHarness
    accepted = FinanceResearchHarness().admit_finish(turn.content, context=fresh, evidence=source_model.source.evidence,
                                                    registry=_registry(source_model.source))
    assert accepted.accepted and "不满足严格双红" in accepted.draft
    missing_evidence = FinanceResearchHarness().admit_finish(turn.content, context=fresh, evidence=(),
                                                            registry=_registry(source_model.source))
    assert not missing_evidence.accepted and missing_evidence.owned_answer is None
