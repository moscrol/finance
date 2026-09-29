"""Real verifier + adapter: local rejection must not erase the reliable answer.

Scripted session replies, no network/provider calls. Financial/model quality is
not inferred from these composition checks.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.services import llm_refine
from intelligence.services.agent_runtime import AgentUsage, EpisodeEvent
from intelligence.services.episode_issues import Issue, IssueCode
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome, SemanticEpisodeVerifier
from intelligence.services.episode_session import CallbackEpisodeSession
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger, ResearchDeadline, ResearchPolicy, ResearchRunContext,
)
from intelligence.services.track_contract import CONTRACT_STUB_HEADING, ingest_next_watch
from intelligence.tests.test_continuous_turn_adapter import _control
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural

FACT = "需求仍待确认 E1。"
HEAD = FACT + "无上期基线，本期建立基线。复核期限：2026-10-21。\n"
WATCH = "**下期关注清单**：指标=需求；时间节点=2026-10-21。\n"
BAD = "触发条件=若评分低于987654321，则重新评估 E1。"
GOOD = "若到2026-10-21需求仍未改善，应重新评估 E1。"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("offline delivery regression must not connect")
    monkeypatch.setattr("socket.socket.connect", denied)
    monkeypatch.setattr("socket.create_connection", denied)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)


def _delivery(*, repair="none", draft=HEAD + WATCH + BAD, initial_check_raises=False):
    frame, verified = _structural(draft, detail="需求仍待确认，改善情况需要后续观察。")
    frame = replace(frame, raw_question="跟踪一下市场需求，但不要登记为长期跟踪。")
    contract = replace(verified.contract, question=frame.raw_question, task_frame_hash=frame.task_frame_hash)
    events = (
        EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        EpisodeEvent(2, "model_turn", {"task_frame_hash": frame.task_frame_hash}),
    )
    initial = replace(verified.outcome, task_frame_hash=frame.task_frame_hash, events=events)
    verified = verify_episode_outcome(contract, initial)
    assert verified.verified_status == "completed"
    context = ResearchRunContext(
        contract=contract, deadline=ResearchDeadline.from_timeout(120),
        policy=ResearchPolicy("standard", 3, 60, 20), trace_parent_id=contract.task_id,
        today="2026-09-18", latest_data_date="2026-09-17",
        root_budget=InMemoryRootBudgetLedger(
            episode_id=contract.task_id, initial_calls=3, hard_calls_cap=3,
            initial_seconds=60, hard_seconds_cap=120,
        ),
    )
    goals, checks = [], []

    class Runtime:
        def run(self, **_kwargs):
            assert repair == "none"
            return initial

    class Resumable:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                goals.append(goal)
                if repair == "raises":
                    raise RuntimeError("offline repair failure")
                updated = {
                    "good": HEAD + WATCH + GOOD,
                    "still_missing": HEAD + WATCH,
                    "still_bad": HEAD + WATCH + BAD.replace("987654321", "876543210"),
                    "empty_failure": "",
                    "recheck_raises": HEAD + WATCH + BAD.replace("987654321", "876543210"),
                }[repair]
                return replace(
                    previous, draft=updated,
                    status="partial" if repair == "empty_failure" else "completed",
                    stop_reason="repair_model_error" if repair == "empty_failure" else "repair_finish",
                    events=(*previous.events, EpisodeEvent(
                        len(previous.events) + 1, "model_turn", {"task_frame_hash": frame.task_frame_hash},
                    )), usage=AgentUsage(2, 1, 0),
                )
            return CallbackEpisodeSession(
                episode_id=context.contract.task_id, outcome=initial, resume_callback=resume,
            )

    class Verifier(SemanticEpisodeVerifier):
        def verify(self, **kwargs):
            if initial_check_raises or (repair == "recheck_raises" and checks):
                raise TimeoutError("offline recheck failure")
            result = super().verify(**kwargs)
            checks.append(result)
            return result

    result = ContinuousTurnAdapter(
        runtime=Runtime() if repair == "none" else Resumable(), mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        semantic_verifier=Verifier(judge_fn=_judge(True)),
    ).handle(frame=frame, control=_control(frame))
    return result, goals, checks


@pytest.mark.usefixtures("numeric_delete_mode")
@pytest.mark.parametrize("mode", ["llm", "off"])
@pytest.mark.parametrize("repair", ["none", "still_missing", "still_bad", "empty_failure", "raises", "recheck_raises"])
def test_bad_condition_is_removed_but_trusted_answer_is_delivered_as_partial(monkeypatch, tmp_path, mode, repair):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    result, goals, checks = _delivery(repair=repair)
    assert FACT in result.answer and "2026-10-21" in result.answer
    assert "987654321" not in result.answer and "876543210" not in result.answer
    assert result.status == "partial"
    assert CONTRACT_STUB_HEADING in result.answer
    assert "触发条件" in result.answer and result.open_gaps
    receipt = result.private_artifact["track_contract"]
    assert receipt["missing_outputs"] == ["track_next_watch"]
    semantic = result.private_artifact["semantic_verifier"]
    assert semantic["status"] == "partial"
    assert "track_next_watch" in semantic["verified"]["missing_outputs"]
    assert any("numeric_condition" in issue for check in checks for issue in check.issues)
    assert len(goals) == (0 if repair == "none" else 1)
    if repair in {"raises", "recheck_raises"}:
        assert result.private_artifact["failure"]["type"] == (
            "RuntimeError" if repair == "raises" else "TimeoutError"
        )
        assert result.private_artifact["delivery_recovery"]["source"] == "last_verified_public_answer"
        phases = result.private_artifact["phase_trace"]
        assert phases["terminal_phases"] == ["partial"]
        assert not phases.get("anomalies")
        assert result.citations
    if goals:
        assert "track_next_watch" in goals[0].missing_answer_elements
        assert goals[0].remaining_calls == 0 and not goals[0].reopen_tools
    path = tmp_path / "checkpoints.jsonl"
    assert ingest_next_watch(path, result.answer, query="请登记为长期跟踪", as_of="2026-09-18") == []
    assert not path.exists()


@pytest.mark.parametrize("mode", ["llm", "off"])
def test_bad_condition_is_marked_and_the_answer_is_delivered_complete(monkeypatch, tmp_path, mode):
    """标注模式孪生（2026-09-28）：同一条无出处的条件留在交付稿里、句内点名待核，
    穿过适配器的交付投影与复检不丢不改；槽位不再缺，回答不再压 partial，不起修稿轮。
    用户明确要求长期跟踪时，这条条件连同待核说明登记进台账（人工核验）——说明不被洗掉。"""

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    result, goals, _checks = _delivery(repair="none")
    marked = "触发条件=若评分低于987654321，则重新评估 E1（待核：「987654321」未在证据中找到出处）。"
    assert FACT in result.answer and marked in result.answer
    assert result.status == "completed" and not result.open_gaps
    assert CONTRACT_STUB_HEADING not in result.answer
    assert goals == []
    verdicts = result.private_artifact["semantic_verifier"]["sentence_verdicts"]
    assert [row["decision"] for row in verdicts if "987654321" in row["sentence"]] == ["marked"]
    path = tmp_path / "checkpoints.jsonl"
    written = ingest_next_watch(path, result.answer, query="请登记为长期跟踪", as_of="2026-09-18")
    assert [(row["claim"], row["metric"]) for row in written] == [
        ("指标=需求；时间节点=2026-10-21 " + marked, {"type": "manual"}),
    ]


@pytest.mark.usefixtures("numeric_delete_mode")
@pytest.mark.parametrize("mode", ["llm", "off"])
def test_legal_repair_reuses_same_session_and_is_reverified(monkeypatch, tmp_path, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    result, goals, checks = _delivery(repair="good")
    assert len(goals) == 1 and len(checks) == 2
    assert goals[0].remaining_calls == 0 and not goals[0].reopen_tools
    assert result.status == "completed"
    assert FACT in result.answer and GOOD in result.answer
    assert "987654321" not in result.answer and CONTRACT_STUB_HEADING not in result.answer
    assert result.private_artifact["track_contract"]["missing_outputs"] == []
    assert result.private_artifact["semantic_verifier"]["verified"]["missing_outputs"] == []
    path = tmp_path / "checkpoints.jsonl"
    assert ingest_next_watch(path, result.answer, query="跟踪一下但不要登记为长期跟踪") == []
    assert not path.exists()
    rows = ingest_next_watch(path, result.answer, query="请登记为长期跟踪", as_of="2026-09-18")
    assert len(rows) == 1 and rows[0]["due"] == "2026-10-21"


@pytest.mark.usefixtures("numeric_delete_mode")
def test_recovery_failure_still_uses_existing_fail_closed_path(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")

    def broken_recovery(*_args):
        raise ValueError("offline recovery failure")

    monkeypatch.setattr(ContinuousTurnAdapter, "_recover_verified_delivery", broken_recovery)
    result, _, _ = _delivery(repair="recheck_raises")
    assert result.status == "degraded" and "876543210" not in result.answer
    assert result.private_artifact["failure"]["type"] == "TimeoutError"
    assert result.private_artifact["delivery_recovery_failure"]["type"] == "ValueError"
    assert "delivery_recovery" not in result.private_artifact


def test_first_verification_exception_never_publishes_unchecked_draft(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    result, goals, checks = _delivery(initial_check_raises=True)
    assert not goals and not checks
    assert "delivery_recovery" not in result.private_artifact
    assert result.status == "degraded"
    assert "987654321" not in result.answer and FACT not in result.answer


@pytest.mark.parametrize("blocked_by", [
    "unavailable", "rejected", "withheld", "failed_structure", "integrity_issue",
    "wrong_frame", "wrong_episode", "empty", "cancelled",
])
def test_recovery_requires_a_releasable_answer_from_this_episode(blocked_by):
    frame, verified = _structural(FACT)
    semantic = SemanticEpisodeOutcome(
        verified=verified, status="completed", public_answer=FACT, judge_status="passed",
    )
    context = ResearchRunContext(
        contract=verified.contract, deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy("standard", 3, 60, 20), trace_parent_id=verified.contract.task_id,
    )
    if blocked_by in {"unavailable", "rejected"}:
        semantic = replace(semantic, judge_status=blocked_by)
    elif blocked_by == "withheld":
        semantic = replace(semantic, repair_withheld=True)
    elif blocked_by == "failed_structure":
        semantic = replace(semantic, verified=replace(verified, verified_status="failed"))
    elif blocked_by == "integrity_issue":
        semantic = replace(semantic, verified=replace(verified, issue_items=(
            Issue(IssueCode.UNKNOWN_EVIDENCE_HASH, "unknown", "unknown evidence"),
        )))
    elif blocked_by == "wrong_frame":
        frame = replace(frame, raw_question="另一轮不同的问题")
    elif blocked_by == "wrong_episode":
        semantic = replace(semantic, verified=replace(verified, contract=replace(
            verified.contract, task_id="another-episode",
        )))
    elif blocked_by == "empty":
        semantic = replace(semantic, public_answer="")
    adapter = ContinuousTurnAdapter(
        runtime=object(), semantic_verifier=SemanticEpisodeVerifier(judge_fn=_judge(True)),
        is_cancelled=lambda: blocked_by == "cancelled",
    )
    assert adapter._recover_verified_delivery(frame, context, semantic, {}) is None


def test_already_complete_watch_does_not_add_repair_or_notice(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    result, goals, checks = _delivery(draft=HEAD + WATCH + GOOD)
    assert result.status == "completed" and not goals and len(checks) == 1
    assert CONTRACT_STUB_HEADING not in result.answer and GOOD in result.answer
