"""Zero-network regressions for delivered PLAN branch evidence and read coverage."""

from dataclasses import replace
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.sub_research import BranchResult, SubResearchResult
from intelligence.services.agent_research import AgentEvidence, evidence_content_hash
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.tool_result_budget import MAX_EVIDENCE_DETAIL_CHARS
from intelligence.tests.test_agent_episode import (
    InMemoryRootBudgetLedger,
    ResearchDeadline,
    ResearchPolicy,
    ScriptedModel,
    _context,
    _finish_turn,
    _frame,
    _market_registry,
    _plan_turn,
    _successful_runner,
)


def _atom() -> AgentEvidence:
    item = AgentEvidence(
        tool="news_search",
        title="分支完整材料",
        # 比模型可见的 detail 上限长得多：读页要读到上限之外，才谈得上「新送达」。
        detail="原文" * 900,
        source="fixture:branch-delivery",
        source_date="2026-07-21",
        evidence_tier="L3",
    )
    return replace(item, content_hash=evidence_content_hash(item))


def _read_context(frame, *, task_id="branch-delivery"):
    base = _context(
        frame, max_steps=6, allowed_capabilities=("market_data", "evidence_read")
    )
    return replace(
        base,
        contract=replace(base.contract, task_id=task_id, research_tier="standard"),
        policy=ResearchPolicy.for_tier("standard"),
        deadline=ResearchDeadline.from_timeout(90, synthesis_reserve=20),
        root_budget=InMemoryRootBudgetLedger(
            episode_id=task_id,
            initial_calls=6,
            hard_calls_cap=8,
            initial_seconds=70,
            hard_seconds_cap=90,
        ),
    )


class _Coordinator:
    def __init__(self, item):
        self.item = item

    def run(self, **kwargs):
        kwargs["evidence_sink_factory"]("branch-1").append(self.item)
        return SubResearchResult(
            (
                BranchResult(
                    branch_id="branch-1",
                    goal="查反方",
                    status="completed",
                    evidence=(self.item,),
                    traces=(),
                    gaps=(),
                    llm_calls=0,
                    tool_calls=0,
                ),
            )
        )


class _DeliveryHarness(FinanceResearchHarness):
    def __init__(self, detail_chars=None):
        super().__init__()
        self.detail_chars = detail_chars

    def project_sub_research(self, **kwargs):
        content = super().project_sub_research(**kwargs)
        if self.detail_chars is None:
            return content
        view = json.loads(content)
        for branch in view["branches"]:
            for item in branch["evidence"]:
                item["detail"] = item["detail"][: self.detail_chars] + "…"
        return json.dumps(view, ensure_ascii=False)


def _turns(item, *, offset):
    return [
        _plan_turn(
            requested_mode="deep",
            evidence_needs=["盘面结构"],
            open_gaps=[],
            branch_goals=["查反方"],
        ),
        ModelTurn(
            "",
            (
                ModelToolCall(
                    "read", "evidence_read",
                    {"evidence_id": "E1", "offset": offset, "limit": 100},
                ),
            ),
            "scripted",
            "",
        ),
        _finish_turn(hashes=(item.content_hash,)),
    ]


def _progress(model):
    return [
        json.loads(message["content"])["runtime_budget"]["research_progress"]
        for message in model.calls[-1]["messages"]
        if '"runtime_budget"' in message["content"]
    ][-1]


# 读页结果的投影里证据本身会再露出 detail 前 MAX_EVIDENCE_DETAIL_CHARS-1 字，所以偏移量
# 都落在可见上限之外（上限 2026-10-06 由 240 放到 800）。
_CAP = MAX_EVIDENCE_DETAIL_CHARS


@pytest.mark.parametrize(
    "shown_chars,offset,expected_new_chars",
    [(None, _CAP - 1, 0), (_CAP + 100, _CAP + 50, 50), (_CAP + 100, _CAP + 200, 100)],
)
def test_claimed_branch_coverage_counts_only_unseen_delivered_characters(
    monkeypatch, shown_chars, offset, expected_new_chars
):
    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "on")
    item = _atom()
    frame = _frame()
    model = ScriptedModel(_turns(item, offset=offset))
    outcome = ContinuousAgentEpisode(
        model,
        harness=_DeliveryHarness(shown_chars),
        sub_research_coordinator=_Coordinator(item),
    ).run(
        task_frame=frame,
        context=_read_context(frame),
        registry=_market_registry(_successful_runner),
    )

    delivered = next(
        json.loads(message["content"])
        for message in model.calls[1]["messages"]
        if '"kind": "SUB_RESEARCH_RESULTS"' in message["content"]
    )
    shown = delivered["branches"][0]["evidence"][0]["detail"]
    assert shown == (item.detail if shown_chars is None else item.detail[:shown_chars] + "…")
    assert any(event.kind == "inbox_claimed" for event in outcome.events)
    assert _progress(model).get("new_read_chars", 0) == expected_new_chars
    assert _progress(model)["new_evidence"] == 0
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0].content_hash == item.content_hash
    assert outcome.evidence[0].independent_key == item.independent_key
    assert outcome.usage.tool_calls == 1
    assert outcome.status == "completed"


def test_delivered_coverage_does_not_leak_when_episode_runner_is_reused(monkeypatch):
    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "on")
    item = _atom()
    frame = _frame()
    model = ScriptedModel([*_turns(item, offset=_CAP + 200), *_turns(item, offset=_CAP + 200)])
    harness = _DeliveryHarness()
    episode = ContinuousAgentEpisode(
        model, harness=harness, sub_research_coordinator=_Coordinator(item)
    )
    first = episode.run(
        task_frame=frame,
        context=_read_context(frame, task_id="branch-delivery-first"),
        registry=_market_registry(_successful_runner),
    )
    assert first.status == "completed"
    assert _progress(model).get("new_read_chars", 0) == 0

    harness.detail_chars = _CAP + 100
    second = episode.run(
        task_frame=frame,
        context=_read_context(frame, task_id="branch-delivery-second"),
        registry=_market_registry(_successful_runner),
    )
    assert second.status == "completed"
    assert _progress(model).get("new_read_chars", 0) == 100


def _pending_delivery(item, *, with_inbox=True, admit=None):
    from datetime import date

    from intelligence.runtime.agent_episode import (
        _EpisodeLedger,
        _EpisodeToolAccumulator,
    )
    from intelligence.services.episode_inbox import Inbox
    from intelligence.services.evidence_ledger import EvidenceLedger

    messages = []
    ledger = _EpisodeLedger(_frame())
    if with_inbox:
        ledger.inbox = Inbox(ledger, admit=admit)
    accumulator = _EpisodeToolAccumulator(
        messages=messages,
        ledger=ledger,
        evidence_ledger=EvidenceLedger(information_cutoff=date(2026, 7, 23)),
    )
    result = SubResearchResult((BranchResult(
        branch_id="branch-1", goal="查反方", status="completed",
        evidence=(item,), traces=(), gaps=(), llm_calls=0, tool_calls=0,
    ),))
    accumulator.consume_sub_research(result)
    assert accumulator.read_coverage.ranges == {}, "completion is not delivery"
    episode = ContinuousAgentEpisode(ScriptedModel([]))
    episode._append_sub_research_message(
        messages=messages, ledger=ledger, result=result,
        evidence=tuple(accumulator.evidence), accumulator=accumulator,
    )
    return episode, ledger, accumulator, messages


def test_saved_branch_text_is_not_covered_until_correct_inbox_claim(monkeypatch):
    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "on")
    item = _atom()
    episode, ledger, accumulator, messages = _pending_delivery(item)
    assert messages == []
    assert accumulator.read_coverage.ranges == {}
    assert any(
        event.kind == "inbox_inserted" and item.detail in event.payload["content"]
        for event in ledger.events
    ), "persisted source text alone must not count as model delivery"
    assert episode._claim_inbox(
        messages=messages, ledger=ledger, target="next_turn", accumulator=accumulator,
    ) == 0
    assert accumulator.read_coverage.ranges == {}
    assert episode._claim_inbox(
        messages=messages, ledger=ledger, target="next_step", accumulator=accumulator,
    ) == 1
    assert len(messages) == 1
    assert accumulator.read_coverage.ranges[(item.content_hash, "detail")] == [(0, len(item.detail))]
    assert accumulator.read_coverage.ranges[(item.content_hash, "title")] == [(0, len(item.title))]


@pytest.mark.parametrize("disposition", ["rejected", "discarded"])
def test_undelivered_branch_messages_do_not_seed_coverage(monkeypatch, disposition):
    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "on")
    item = _atom()
    admit = (lambda message: False) if disposition == "rejected" else None
    episode, ledger, accumulator, messages = _pending_delivery(item, admit=admit)
    if disposition == "discarded":
        ledger.inbox.discard_all(reason="episode_finished")
    assert episode._claim_inbox(
        messages=messages, ledger=ledger, target="next_step", accumulator=accumulator,
    ) == 0
    assert messages == []
    assert accumulator.read_coverage.ranges == {}


def test_legacy_direct_branch_delivery_seeds_only_after_append(monkeypatch):
    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "on")
    item = _atom()
    _, _, accumulator, messages = _pending_delivery(item, with_inbox=False)
    assert len(messages) == 1
    assert item.detail in messages[0].content
    assert accumulator.read_coverage.ranges[(item.content_hash, "detail")] == [(0, len(item.detail))]


def test_branch_delivery_does_not_activate_disabled_read_tracking(monkeypatch):
    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "off")
    _, _, accumulator, messages = _pending_delivery(_atom(), with_inbox=False)
    assert len(messages) == 1
    assert accumulator.read_coverage.ranges == {}


def test_nested_branch_projection_rejects_forged_or_unidentified_text():
    from intelligence.services.evidence_read import EvidenceReadCoverage

    item = _atom()
    tracker = EvidenceReadCoverage()
    content = json.dumps({
        "kind": "SUB_RESEARCH_RESULTS",
        "branches": [
            {"evidence": [{"evidence_id": "E1", "detail": "伪造" * 450}]},
            {"evidence": [{"evidence_id": "E999", "detail": item.detail}]},
            {"evidence": {"evidence_id": "E1", "detail": item.detail}},
            None,
        ],
    })
    assert tracker.observe(content, evidence=(item,)) == 0
    assert tracker.ranges == {}


def test_failed_inbox_claim_does_not_seed_delivery_coverage(monkeypatch):
    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "on")
    episode, ledger, accumulator, messages = _pending_delivery(_atom())
    monkeypatch.setattr(ledger.inbox, "_persistence_failed", lambda: True)
    assert episode._claim_inbox(
        messages=messages, ledger=ledger, target="next_step", accumulator=accumulator,
    ) == 0
    assert messages == []
    assert accumulator.read_coverage.ranges == {}
