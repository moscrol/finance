"""Presentation links and cutoff notices survive without rewriting admitted facts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
import json

import pytest

from intelligence.services import episode_evidence as snapshots
from intelligence.services.agent_research import StructuredObservation
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.tests.test_episode_evidence_snapshot import _atom, _fixture, _resign


def test_presentation_links_roundtrip_without_changing_first_writer_or_coverage():
    ledger, presented, _ = _fixture()
    before = ledger.snapshot()
    changed = (replace(presented[0], supports=("new-request",), contradicts=()), presented[1])
    payload = snapshots.capture_evidence_snapshot(
        episode_id="episode", ledger=ledger, presented_evidence=changed,
    )
    decoded = snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    restored = EvidenceLedger.from_recovery_snapshot(payload, episode_id="episode")
    assert payload["schema_version"] == 2
    assert decoded.presented_evidence == changed
    assert decoded.presented_hashes == ("first", "second")
    assert restored.items() == ledger.items()
    assert restored.snapshot() == before == ledger.snapshot()
    assert "new-request" not in dict(restored.snapshot().evidence_targets)["first"]
    assert decoded.to_dict() == payload


@pytest.mark.parametrize("changes", [
    {"detail": "replacement"}, {"title": "replacement"}, {"source": "replacement"},
    {"source_date": "2026-07-23"}, {"derived_from": ("replacement",)},
    {"observations": (StructuredObservation("公司", "2026-07-24", "营收亿元", 99),)},
    {"internal_locator": "replacement"}, {"deep_read": False},
])
def test_same_hash_presentations_may_not_replace_any_fact(changes):
    ledger, presented, _ = _fixture()
    with pytest.raises(ValueError):
        snapshots.capture_evidence_snapshot(
            episode_id="episode", ledger=ledger,
            presented_evidence=(replace(presented[0], supports=("request",), **changes),),
        )


@pytest.mark.parametrize("source_date", [
    "2026-07-25", "20260725", "2026-07-25T09:30:00+08:00",
    "2026-7-25", "2026-7-25 09:30:00", " 2026-07-25 ",
])
def test_future_presentation_restores_exact_notice_but_cannot_cover_output(source_date):
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    future = _atom("future", source_date=source_date, title="原日期提示", supports=("future-output",))
    assert ledger.append(future, covered_outputs=("future-output",)) == ()
    payload = ledger.to_recovery_snapshot(episode_id="episode", presented_evidence=(future,))
    decoded = snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    restored = EvidenceLedger.from_recovery_snapshot(payload, episode_id="episode")
    assert decoded.presented_evidence == (future,)
    assert payload["presentations"][0]["classification"] == "future_of_cutoff"
    assert restored.items() == ()
    assert restored.snapshot().covered_outputs == ()
    assert not restored.mark_output_covered("future-output", evidence_ids=("future",))
    assert decoded.to_dict() == payload


@pytest.mark.parametrize(("cutoff", "source_date"), [
    (None, "2026-07-25"), (date(2026, 7, 24), None),
    (date(2026, 7, 24), "2026-07-24"), (date(2026, 7, 24), "unknown"),
    (date(2026, 7, 24), "2026-99-99"), (date(2026, 7, 24), "2026-07-25garbage"),
    (None, "2026-7-25"), (date(2026, 7, 24), "2026-7-24"),
    (date(2026, 7, 24), "2026-7-25garbage"), (date(2026, 7, 24), "正文2026-7-25"),
    (date(2026, 7, 24), "/tmp/2026-7-25"), (date(2026, 7, 24), "2026-7-25 09:30:00+08:00garbage"),
    (date(2026, 7, 24), "2026-W30-6"), (date(2026, 7, 24), "2026W306"),
])
def test_unadmitted_presentations_require_real_future_date_not_title(cutoff, source_date):
    ledger = EvidenceLedger(information_cutoff=cutoff)
    item = _atom("missing", source_date=source_date, title="晚于问句日 2026-07-24")
    with pytest.raises(ValueError):
        ledger.to_recovery_snapshot(episode_id="episode", presented_evidence=(item,))


def test_v1_read_preserves_version_digest_and_presentation_semantics():
    ledger, presented, payload = _fixture()
    payload.pop("presentations")
    payload.update(schema_version=1, presented_hashes=[item.content_hash for item in presented])
    _resign(payload)
    original = deepcopy(payload)
    decoded = snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    assert decoded.to_dict() == original
    assert decoded.presented_evidence == presented
    assert EvidenceLedger.from_recovery_snapshot(payload, episode_id="episode").snapshot() == ledger.snapshot()
    state = EpisodeState(episode_id="episode", phase="planning", last_sequence=2,
                         evidence_snapshot=payload, evidence_snapshot_sequence=2)
    assert EpisodeState.from_dict(state.to_dict()).to_dict()["evidence_snapshot"] == original
    assert ledger.to_recovery_snapshot(episode_id="episode", presented_evidence=presented)["schema_version"] == 2


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "unknown", "coverage", "digest"])
def test_v1_reader_retains_strict_legacy_validation(mutation):
    _, presented, payload = _fixture()
    payload.pop("presentations")
    payload.update(schema_version=1, presented_hashes=[item.content_hash for item in presented])
    if mutation == "missing":
        del payload["entries"][0]["atom"]["observations"]
    elif mutation == "extra":
        payload["presentations"] = []
    elif mutation == "duplicate":
        payload["presented_hashes"] = ["first", "first"]
    elif mutation == "unknown":
        payload["presented_hashes"] = ["missing"]
    elif mutation == "coverage":
        payload["covered_outputs"] = ["forged"]
    _resign(payload)
    if mutation == "digest":
        payload["entries"][0]["atom"]["source_date"] = "2026-07-23"
    with pytest.raises(ValueError):
        snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


@pytest.mark.parametrize(("cutoff", "source_date"), [
    (None, "2026-07-25"), ("2026-07-24", None), ("2026-07-24", "2026-07-24"),
    ("2026-07-24", "unknown"), ("2026-07-24", "2026-07-25garbage"),
    ("2026-07-24", "2026-7-25garbage"), ("2026-07-24", "正文2026-7-25"),
    ("2026-07-24", "/tmp/2026-7-25"), ("2026-07-24", "2026-7-25 09:30:00+08:00garbage"),
    ("2026-07-24", "2026-W30-6"),
])
def test_v2_reader_rechecks_future_classification_even_with_recomputed_digest(cutoff, source_date):
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    payload = ledger.to_recovery_snapshot(
        episode_id="episode", presented_evidence=(_atom("future", source_date="2026-07-25"),),
    )
    payload["information_cutoff"] = cutoff
    payload["presentations"][0]["atom"]["source_date"] = source_date
    _resign(payload)
    with pytest.raises(ValueError):
        snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


@pytest.mark.parametrize(("path", "value"), [
    (("presentations", 0, "atom", "detail"), "changed"),
    (("presentations", 0, "atom", "source_date"), "2026-07-23"),
    (("presentations", 0, "atom", "observations", 0, "value"), 99),
    (("presentations", 0, "atom", "supports"), ["different-request"]),
    (("presentations", 0, "classification"), "future_of_cutoff"),
])
def test_v2_digest_covers_full_presentation_and_classification(path, value):
    _, _, payload = _fixture()
    node = payload
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValueError, match="digest"):
        snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    if path[-1] != "supports":
        _resign(payload)
        with pytest.raises(ValueError):
            snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


@pytest.mark.parametrize("mutation", ["duplicate", "missing-atom", "missing-classification", "extra", "coverage", "admitted"])
def test_future_presentation_schema_and_coverage_are_fail_closed(mutation):
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    payload = ledger.to_recovery_snapshot(
        episode_id="episode", presented_evidence=(_atom("future", source_date="2026-07-25"),),
    )
    if mutation == "duplicate":
        payload["presentations"].append(deepcopy(payload["presentations"][0]))
    elif mutation.startswith("missing-"):
        del payload["presentations"][0][mutation.removeprefix("missing-")]
    elif mutation == "extra":
        payload["presentations"][0]["unexpected"] = True
    elif mutation == "coverage":
        payload["covered_outputs"] = ["direct"]
    else:
        payload["presentations"][0]["classification"] = "admitted"
    _resign(payload)
    with pytest.raises(ValueError):
        snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


@pytest.mark.parametrize("durable", [False, True])
@pytest.mark.parametrize("future_only", [False, True])
def test_real_episode_reaches_next_model_after_future_only_or_mixed_results(tmp_path, durable, future_only):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.research_contract import InformationCutoff
    from intelligence.tests.test_agent_episode import (
        ScriptedModel, _context, _finish_turn, _frame, _market_registry, _successful_runner, _tool_turn,
    )

    frame = _frame()
    context = replace(_context(frame, max_steps=2), information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"))
    model = ScriptedModel([
        _tool_turn("historical cutoff probe"),
        _finish_turn(status="partial", draft="需补同日证据。", hashes=(), gap="缺少截止内证据"),
    ])

    def runner(query, tool_context):
        evidence, observation, trace = _successful_runner(query, tool_context)
        evidence = [replace(item, source_date="2026-07-25") for item in evidence]
        if not future_only:
            evidence.append(replace(evidence[0], source_date="2026-07-24", content_hash="in-cutoff"))
        return evidence, observation, replace(trace, source_trade_date="2026-07-25")

    store = JsonlEpisodeStore(tmp_path) if durable else None
    outcome = ContinuousAgentEpisode(model, store=store).run(
        task_frame=frame, context=context, registry=_market_registry(runner),
    )
    assert len(model.calls) == 2 and outcome.stop_reason == "model_finish"
    assert outcome.persistence == ("durable" if durable else "ephemeral")
    assert not any(event.kind == "persistence_failed" for event in outcome.events)
    assert outcome.evidence[0].source_date == ("2026-07-25" if future_only else "2026-07-24")
    if future_only:
        assert "晚于问句日 2026-07-24" in outcome.evidence[0].title
    if store is not None:
        state = store.load(context.contract.task_id)[1]
        decoded = snapshots.EpisodeEvidenceSnapshot.from_dict(state.evidence_snapshot, episode_id=context.contract.task_id)
        restored = EvidenceLedger.from_recovery_snapshot(state.evidence_snapshot, episode_id=context.contract.task_id)
        assert decoded.presented_evidence == outcome.evidence
        if future_only:
            assert restored.items() == ()
            assert not restored.mark_output_covered("direct_assessment", evidence_ids=(outcome.evidence[0].content_hash,))


@pytest.mark.parametrize("durable", [False, True])
def test_real_glm_parent_mixed_batch_keeps_child_original_and_parent_request_links(tmp_path, durable):
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.services.agent_research import evidence_content_hash
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.mode_governor import ModeSignals
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.services.research_contract import release_root_budget
    from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
    from intelligence.tests.test_sub_research_tool import _context, _frame

    class MixedModel:
        parent_calls = 0
        child_calls = 0

        def complete(self, *, messages, tools, timeout):
            child = "branch_findings" in json.dumps(messages[:2], ensure_ascii=False)
            if child:
                self.child_calls += 1
                if self.child_calls == 1:
                    return ModelTurn("", (ModelToolCall("child-tool", "market_data", {"query": "child"}),))
            else:
                self.parent_calls += 1
                if self.parent_calls == 1:
                    return ModelTurn("", (
                        ModelToolCall("direct-tool", "market_data", {"query": "direct"}),
                        ModelToolCall("branch-tool", "sub_research", {"goals": ["核验甲"]}),
                    ))
            return ModelTurn(json.dumps({
                "status": "partial", "draft": "证据仍不足。", "gaps": ["待核验"], "bindings": [],
            }, ensure_ascii=False), ())

    context = _context("max", allowed=("market_data", "sub_research"))
    model = MixedModel()

    def runner(query, _):
        item = _atom(source_date="2026-07-21",
                     supports=(("direct-output" if query == "direct" else "branch-output"),), contradicts=())
        item = replace(item, content_hash=evidence_content_hash(item))
        return [item], "原件证据", ProviderTrace(provider="fixture", capability="market_data", status="success")

    registry = ResearchToolRegistry((ToolSpec(
        name="market_data", capability="market_data", description="行情", cost="local", freshness="current", runner=runner,
    ),))
    store = JsonlEpisodeStore(tmp_path) if durable else None
    try:
        outcome = GLMAgentRuntime(client=model, episode_store=store,
                                 mode_signals=lambda *_: ModeSignals(user_mode="deep")).run(
            task_frame=_frame(), context=context, registry=registry,
        )
        assert model.parent_calls == model.child_calls == 2
        assert outcome.stop_reason == "model_finish"
        assert outcome.persistence == ("durable" if durable else "ephemeral")
        assert outcome.evidence[0].supports == ("direct-output",)
        if store is not None:
            state = store.load(context.contract.task_id)[1]
            decoded = snapshots.EpisodeEvidenceSnapshot.from_dict(state.evidence_snapshot, episode_id=context.contract.task_id)
            assert decoded.presented_evidence == outcome.evidence
            assert decoded.entries[0].atom.supports == ("branch-output",)
            assert decoded.entries[0].branch_owner is not None
            assert "direct-output" not in decoded.entries[0].targets
    finally:
        release_root_budget(context.contract.task_id)
