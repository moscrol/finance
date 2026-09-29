"""Cross-parent behavior of the history/runtime/financial union, offline only.

Parent greens are not combination evidence: exercise the moved publication
receipt, the shared cutoff boundary, and storage failure after a checked draft.
"""
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest

from intelligence.runtime.continuous_turn_adapter import (
    ContinuousTurnAdapter, _track_public_delivery,
)
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.historical_research.intent import (
    HistoryIntent, explicit_information_cutoff, infer_history_intent,
)
from intelligence.services.honesty_gates import requested_information_cutoff
from intelligence.services.research_contract import (
    InformationCutoff, ResearchDeadline, ResearchPolicy, ResearchRunContext,
)
from intelligence.services.track_contract import CONTRACT_STUB_HEADING
from intelligence.services.turn_controller import decide_turn
from intelligence.tests.test_boundary_partial_delivery import FACT, _delivery
from intelligence.tests.test_continuous_turn_adapter import _control
from intelligence.tests.test_episode_semantic_verifier import _structural


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("union seam tests must not connect")

    monkeypatch.setattr("socket.socket.connect", denied)
    monkeypatch.setattr("socket.create_connection", denied)


def _history_delivery(history=True):
    frame, verified = _structural(FACT)
    intent = HistoryIntent("historical_comparison") if history else None
    frame = replace(
        frame, raw_question="跟踪一下这些板块的历史路径", history_intent=intent,
    )
    contract = replace(
        verified.contract, task_id=f"union-seam-{uuid4().hex}",
        question=frame.raw_question, task_frame_hash=frame.task_frame_hash,
    )
    outcome = replace(
        verified.outcome, task_frame_hash=frame.task_frame_hash,
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
    )
    verified = verify_episode_outcome(contract, outcome)
    assert verified.verified_status == "completed"
    context = ResearchRunContext(
        contract=contract, deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy("standard", 3, 60, 20),
        trace_parent_id=contract.task_id, history_intent=intent,
        today="2026-09-22",
    )
    semantic = SemanticEpisodeOutcome(
        verified=verified, status="completed", public_answer=FACT, judge_status="passed",
    )
    return frame, context, semantic


@pytest.mark.parametrize("history", [False, True])
def test_final_track_projection_preserves_history_intent_without_disabling_track(history):
    _, context, _ = _history_delivery(history)
    answer, notices, receipt = _track_public_delivery(FACT, context)
    assert bool(receipt["missing_outputs"]) is not history
    assert bool(notices) is not history
    assert (CONTRACT_STUB_HEADING in answer) is not history
    assert FACT in answer


@pytest.mark.parametrize("exit_kind", ["normal", "verified_recovery"])
def test_history_intent_reaches_public_receipt_on_both_delivery_exits(exit_kind):
    frame, context, semantic = _history_delivery()

    class Runtime:
        def run(self, **_kwargs):
            return semantic.verified.outcome

    class Verifier:
        def verify(self, **_kwargs):
            return semantic

    adapter = ContinuousTurnAdapter(
        runtime=Runtime(), semantic_verifier=Verifier(), mode="on",
        context_factory=lambda *_a, **_kw: context,
        registry_factory=lambda *_a, **_kw: "registry",
    )
    result = (
        adapter.handle(frame=frame, control=_control(frame))
        if exit_kind == "normal"
        else adapter._recover_verified_delivery(frame, context, semantic, {})
    )
    assert result is not None
    # No executed history result was supplied: the independent history
    # publication ceiling must still hold. That is not a track-template gap.
    assert result.status == "partial"
    assert result.private_artifact["publication_assessment"]["max_status"] == "partial"
    assert FACT in result.answer and CONTRACT_STUB_HEADING not in result.answer
    assert result.private_artifact["track_contract"]["missing_outputs"] == []


@pytest.mark.usefixtures("numeric_delete_mode")
def test_storage_failure_after_semantic_check_never_uses_verified_recovery(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    resume = ContinuousTurnAdapter._resume_for_gap

    def save_failed(self, **kwargs):
        candidate = resume(self, **kwargs)
        assert candidate is not None
        outcome, structural, delivery_only = candidate
        failed = replace(outcome, status="failed", persistence="failed", stop_reason="storage_failed")
        return failed, replace(structural, outcome=failed), delivery_only

    def recovery_forbidden(*_a, **_kw):
        pytest.fail("a trusted earlier draft cannot override the storage failure fence")

    monkeypatch.setattr(ContinuousTurnAdapter, "_resume_for_gap", save_failed)
    monkeypatch.setattr(ContinuousTurnAdapter, "_recover_verified_delivery", recovery_forbidden)
    result, goals, checks = _delivery(repair="good")
    assert len(goals) == len(checks) == 1  # a checked draft existed before saving failed
    assert result.status == "failed" and FACT not in result.answer
    assert not result.citations
    assert result.private_artifact["failure"]["type"] == "storage_failed"
    assert result.private_artifact["learning_eligible"] is False
    assert "delivery_recovery" not in result.private_artifact


@pytest.mark.parametrize("instruction", [
    "以2026-09-11为信息截止日", "2026-09-11信息截止日",
    "信息截止日2026-09-11", "信息截止日：2026-09-11",
    "截至2026-09-11", "截止到2026年9月11日",
])
def test_history_and_finance_cutoff_forms_keep_the_same_date(instruction):
    assert requested_information_cutoff(instruction, today="2026-09-22") == InformationCutoff(
        date(2026, 9, 11), "requested",
    )


@pytest.mark.parametrize("query", [
    '解释这句话：“以2026-09-11为信息截止日”。',
    '解释这句话：“截至2026-09-11”。',
    '> 以2026-09-11为信息截止日\n解释这段材料。',
    '```text\n截至2026-09-11\n```\n解释这段材料。',
    '材料：\n    信息截止日2026-09-11\n解释上述材料。',
    '解释这句话：“以2026-09-11为信息截止日',
    '不要以2026-09-11为信息截止日',
    '报告期截至2026-09-11',
    '复查日截至2026-09-11',
    '截至2026-09-11至2026-09-18的观察窗口',
    '截至2026-09-11；信息截止日为2026-09-18',
    '信息截止日2026-02-30；站在2026-09-11收盘',
])
def test_cutoff_provenance_roles_negation_and_conflicts_do_not_fallback(query):
    assert requested_information_cutoff(query, today="2026-09-22") is None


def test_material_cutoff_cannot_override_independent_top_level_cutoff():
    query = '解释“信息截止日2026-09-18”。以2026-09-11为信息截止日分析。'
    assert requested_information_cutoff(query, today="2026-09-22") == InformationCutoff(
        date(2026, 9, 11), "requested",
    )


# History intent and Episode cutoff assembly must read one parser: a negated or
# role-bound date that the Episode refuses cannot re-enter via `HistoryIntent`
# and win the `min()` in `build_episode_context` (#863 independent review, F1).
HISTORY_TAIL = "，历史上有没有类似情况，找出共同特征"


@pytest.mark.parametrize("instruction, expected", [
    ("以2026-09-11为信息截止日", date(2026, 9, 11)),
    ("截至2026-09-11", date(2026, 9, 11)),
    ("信息截止日：2026年9月11日", date(2026, 9, 11)),
    ("不要以2026-09-11为信息截止日", None),
    ("报告期截至2026-09-11", None),
    ("复查日截至2026-09-11", None),
    ("截至2026-09-11至2026-09-18的观察窗口", None),
])
def test_history_intent_and_episode_cutoff_read_one_truth(instruction, expected):
    query = instruction + HISTORY_TAIL
    intent = infer_history_intent(query)
    assert intent is not None and intent.window_error is None
    requested = requested_information_cutoff(query, today="2026-09-22")
    assert explicit_information_cutoff(query) == expected
    assert (requested.as_of_date if requested else None) == expected
    assert intent.information_cutoff == (expected.isoformat() if expected else None)


def test_conflicting_explicit_cutoffs_clarify_history_and_never_guess_episode():
    query = "截至2026-09-11；信息截止日为2026-09-18" + HISTORY_TAIL
    assert requested_information_cutoff(query, today="2026-09-22") is None
    with pytest.raises(ValueError):
        explicit_information_cutoff(query)
    assert infer_history_intent(query).window_error


def test_negated_cutoff_does_not_reach_episode_through_history_intent():
    query = "不要以2026-09-11为信息截止日" + HISTORY_TAIL
    frame = decide_turn(query).task_frame
    assert frame.history_intent is not None
    assert frame.history_intent.information_cutoff is None
    context = build_episode_context(
        frame, task_id="union-cutoff-e2e", today="2026-09-22", latest_data_date="2026-09-19",
    )
    assert context.information_cutoff.as_of_date == date(2026, 9, 22)
