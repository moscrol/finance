from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
from threading import BrokenBarrierError, Event
import time

import pytest

from intelligence.runtime.conversation_orchestrator import (
    ConversationContext,
    TurnOrchestrator,
    previous_completed_assistant_message,
    workbench_correction_guard_reason,
)
from intelligence.services import corrections, workbench_correction_ingest
from intelligence.services.conversation_store import ConversationStore, Message
from intelligence.services.run_store import RunStore
from intelligence.services.research_contract import ResearchDeadline


@pytest.fixture
def previous_answer() -> dict[str, str]:
    return {
        "message_id": "msg-answer-1",
        "role": "assistant",
        "status": "completed",
        "content": "双红后可以直接上车，但仍需结合量能和容量确认。",
    }


def test_recorded_correction_keeps_bounded_provenance(tmp_path: Path, previous_answer) -> None:
    path = tmp_path / "users" / "alice" / "corrections.jsonl"

    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path,
        user_text="不对，应该先看板块容量再下结论",
        previous_assistant=previous_answer,
        conversation_id="conv-1",
        corrected_message_id="msg-answer-1",
        themes=["板块"],
        ts="2026-09-25T02:00:00+00:00",
    )

    assert result.status == "recorded"
    assert result.reason == "recorded"
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["source"] == "workbench_conversation"
    assert record["conversation_id"] == "conv-1"
    assert record["corrected_message_id"] == "msg-answer-1"
    assert record["plane"] == "user_method"
    assert record["correction"] == "先看板块容量再下结论"
    assert len(record["original"]) <= 240


def test_requires_completed_assistant_answer(tmp_path: Path) -> None:
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        tmp_path / "corrections.jsonl",
        user_text="不对，应该先看板块容量",
        previous_assistant={
            "message_id": "msg-user",
            "role": "user",
            "status": "completed",
            "content": "瑞华泰怎么看",
        },
        conversation_id="conv-1",
        corrected_message_id="msg-user",
        ts="2026-09-25T02:00:00+00:00",
    )

    assert result.status == "skipped"
    assert result.reason == "no_prior_answer"


def test_market_commentary_is_not_user_method_correction(tmp_path: Path, previous_answer) -> None:
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        tmp_path / "corrections.jsonl",
        user_text="这波不对，应该是情绪退潮",
        previous_assistant=previous_answer,
        conversation_id="conv-1",
        corrected_message_id="msg-answer-1",
        ts="2026-09-25T02:00:00+00:00",
    )

    assert result.status == "skipped"
    assert result.reason == "market_commentary"


def test_engineering_text_is_not_written(tmp_path: Path, previous_answer) -> None:
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        tmp_path / "corrections.jsonl",
        user_text="不对，应该先修 pytest 失败再看结论",
        previous_assistant=previous_answer,
        conversation_id="conv-1",
        corrected_message_id="msg-answer-1",
        ts="2026-09-25T02:00:00+00:00",
    )

    assert result.status == "skipped"
    assert result.reason == "engineering"


@pytest.mark.parametrize(
    "user_text",
    [
        "那我现在应该买入还是继续观望呢？",
        "这个板块后面应该怎么看？",
        "你觉得应该关注哪些指标",
        "明天应该会继续涨吧",
        "我觉得这个板块应该还有一波",
        "那应该是什么原因导致的?",
        "我觉得应该是情绪退潮了",
        "今天应该是科技股领涨",
        "这波应为正常的技术回调",
        "不是退潮，是主线切换",
        "不是放量上涨，是缩量反弹",
        "你觉得应该是科技股领涨",
        "这里应该是情绪退潮了",
    ],
)
def test_follow_up_question_or_guess_is_not_a_correction(
    tmp_path: Path, previous_answer, user_text: str
) -> None:
    # Takeover review 2026-09-26: a bare "应该" matched every follow-up question,
    # writing "怎么看" / "会继续涨吧" into the ledger that opening recall replays.
    path = tmp_path / "corrections.jsonl"
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path,
        user_text=user_text,
        previous_assistant=previous_answer,
        conversation_id="conv-1",
        corrected_message_id="msg-answer-1",
        ts="2026-09-25T02:00:00+00:00",
    )

    assert result.status == "skipped"
    assert result.reason == "no_payload"
    assert not path.exists()


@pytest.mark.parametrize(
    "user_text,correction,prior_content",
    [
        ("你刚才说双红就能上，不对，应该先看容量", "先看容量", None),
        ("错了，应为先看客户验证进度", "先看客户验证进度", None),
        ("你理解错了，这里应为先看订单再看产能", "先看订单再看产能", None),
        ("这里应该是先看客户验证进度再谈弹性", "先看客户验证进度再谈弹性", None),
        ("你刚才的回答应该是先看客户验证进度", "先看客户验证进度", None),
        ("上一条应为先核验订单再讨论弹性", "先核验订单再讨论弹性", None),
        # The replacement form has an actual target in the previous answer.
        ("不是产能公告，是客户验证进度", "客户验证进度", "判断依据是产能公告。"),
    ],
)
def test_design_payload_forms_still_write(
    tmp_path: Path, previous_answer, user_text: str, correction: str, prior_content: str | None
) -> None:
    if prior_content is not None:
        previous_answer = {**previous_answer, "content": prior_content}
    path = tmp_path / "corrections.jsonl"
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path,
        user_text=user_text,
        previous_assistant=previous_answer,
        conversation_id="conv-1",
        corrected_message_id="msg-answer-1",
        ts="2026-09-25T02:00:00+00:00",
    )

    assert result.status == "recorded"
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["correction"] == correction


@pytest.mark.parametrize("later_ts,expected_status", [
    ("2026-09-25T20:00:00+00:00", "skipped"),
    ("2026-09-26T02:00:00+00:00", "skipped"),
    ("2026-09-26T02:00:01+00:00", "recorded"),
])
def test_duplicate_respects_24_hour_boundary(tmp_path: Path, previous_answer, later_ts, expected_status) -> None:
    path = tmp_path / "corrections.jsonl"
    kwargs = {
        "path": path,
        "user_text": "不对，应该先看板块容量再下结论",
        "previous_assistant": previous_answer,
        "conversation_id": "conv-1",
        "corrected_message_id": "msg-answer-1",
    }

    first = workbench_correction_ingest.maybe_record_workbench_correction(
        **kwargs, ts="2026-09-25T02:00:00+00:00"
    )
    second = workbench_correction_ingest.maybe_record_workbench_correction(
        **kwargs, ts=later_ts,
    )

    assert first.status == "recorded"
    assert second.status == expected_status
    assert second.reason == ("dedup" if expected_status == "skipped" else "recorded")
    assert len(path.read_text(encoding="utf-8").splitlines()) == (1 if expected_status == "skipped" else 2)


def _concurrent_correction(path, previous_answer, start, after_read, results) -> None:
    # Rendezvous immediately after the real ledger read. Without an enclosing
    # cross-process lock both writers necessarily inspect the same empty ledger.
    real_load = corrections.load_corrections

    def synchronized_load(*args, **kwargs):
        result = real_load(*args, **kwargs)
        try:
            after_read.wait(timeout=2)
        except BrokenBarrierError:
            pass  # A correct lock keeps the other process outside this read.
        return result

    corrections.load_corrections = synchronized_load
    start.wait(timeout=10)
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path,
        user_text="不对，应该先看板块容量再下结论",
        previous_assistant=previous_answer,
        conversation_id="conv-concurrent",
        corrected_message_id="msg-answer-1",
        ts="2026-09-25T02:00:00+00:00",
    )
    results.put((result.status, result.reason))


def test_duplicate_is_atomic_across_processes(tmp_path, previous_answer) -> None:
    path = tmp_path / "corrections.jsonl"
    ctx = multiprocessing.get_context("spawn")
    start, after_read, results = ctx.Barrier(2), ctx.Barrier(2), ctx.Queue()
    processes = [
        ctx.Process(
            target=_concurrent_correction,
            args=(path, previous_answer, start, after_read, results),
        )
        for _ in range(2)
    ]
    try:
        for process in processes:
            process.start()
        received = [results.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=5)
            assert process.exitcode == 0
        # The artificial two-second read holds the inode beyond the optional
        # lock window. The contender may fail open as busy, but cannot append.
        assert received.count(("recorded", "recorded")) == 1
        assert all(item in {("recorded", "recorded"), ("skipped", "dedup"), ("failed", "busy")} for item in received)
        assert len(path.read_text(encoding="utf-8").splitlines()) == 1
        retry = workbench_correction_ingest.maybe_record_workbench_correction(
            path, user_text="不对，应该先看板块容量再下结论", previous_assistant=previous_answer,
            conversation_id="conv-retry", corrected_message_id="msg-answer-1", ts="2026-09-25T02:00:00+00:00",
        )
        assert (retry.status, retry.reason) == ("skipped", "dedup")
        assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()


def _reordered_default_clock_writer(path, previous_answer, early, late_done, results, earlier_call):
    if earlier_call:
        real_flock = workbench_correction_ingest.fcntl.flock

        def delayed_flock(fd, operation):
            early.set()
            if not late_done.wait(timeout=10):
                raise TimeoutError("later writer did not finish")
            return real_flock(fd, operation)

        workbench_correction_ingest.fcntl.flock = delayed_flock
    else:
        if not early.wait(timeout=10):
            raise TimeoutError("earlier writer did not reach lock")
        # Default timestamps have second precision. The later caller must
        # actually enter in a later second, without injecting a shared clock.
        time.sleep(1.05)
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path, user_text="不对，应该先看板块容量再下结论",
        previous_assistant=previous_answer, conversation_id="conv-reordered",
        corrected_message_id=previous_answer["message_id"],
    )
    results.put((result.status, result.reason))
    if not earlier_call:
        late_done.set()


def test_default_clock_deduplicates_when_processes_acquire_lock_in_reverse_order(tmp_path, previous_answer):
    path = tmp_path / "corrections.jsonl"
    ctx = multiprocessing.get_context("spawn")
    early, late_done, results = ctx.Event(), ctx.Event(), ctx.Queue()
    processes = [ctx.Process(
        target=_reordered_default_clock_writer,
        args=(path, previous_answer, early, late_done, results, earlier),
    ) for earlier in (True, False)]
    try:
        for process in processes:
            process.start()
        outcomes = [results.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=5)
            assert process.exitcode == 0
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert sorted(outcomes) == [("recorded", "recorded"), ("skipped", "dedup")], rows
        assert len(rows) == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()


def test_dedup_read_failure_is_fail_open(tmp_path, previous_answer, monkeypatch) -> None:
    def failed_read(*args, **kwargs):
        raise OSError("private ledger unavailable")

    monkeypatch.setattr(corrections, "load_corrections", failed_read)
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        tmp_path / "corrections.jsonl",
        user_text="不对，应该先看板块容量再下结论",
        previous_assistant=previous_answer,
        conversation_id="conv-1",
        corrected_message_id="msg-answer-1",
    )
    assert result.status == "failed"
    assert result.reason == "write_failed"
    assert result.error_type == "OSError"


@pytest.mark.parametrize("stop", ["cancelled", "deadline_exhausted"])
def test_known_stop_before_ingest_has_no_filesystem_side_effects(tmp_path, previous_answer, stop):
    path = tmp_path / "new-user" / "corrections.jsonl"
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path, user_text="不对，应该先看板块容量再下结论", previous_assistant=previous_answer,
        conversation_id="conv-stop", corrected_message_id="msg-answer-1",
        deadline=ResearchDeadline.from_timeout(0 if stop == "deadline_exhausted" else 5),
        is_cancelled=lambda: stop == "cancelled",
    )
    assert (result.status, result.reason) == ("failed", stop)
    assert not path.parent.exists()


def test_cancellation_after_lock_acquired_prevents_ledger_read_and_append(tmp_path, previous_answer, monkeypatch):
    cancelled = Event()
    real_flock = workbench_correction_ingest.fcntl.flock

    def acquire_then_cancel(fd, operation):
        assert operation & workbench_correction_ingest.fcntl.LOCK_NB
        real_flock(fd, operation)
        cancelled.set()

    monkeypatch.setattr(workbench_correction_ingest.fcntl, "flock", acquire_then_cancel)
    monkeypatch.setattr(corrections, "load_corrections", lambda *a, **kw: pytest.fail("read began after cancellation"))
    monkeypatch.setattr(corrections, "record_correction", lambda *a, **kw: pytest.fail("write began after cancellation"))
    path = tmp_path / "corrections.jsonl"
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path, user_text="不对，应该先看板块容量再下结论", previous_assistant=previous_answer,
        conversation_id="conv-stop", corrected_message_id="msg-answer-1", is_cancelled=cancelled.is_set,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert (result.status, result.reason) == ("failed", "cancelled")
    assert not path.read_text()


@pytest.mark.parametrize("stop", ["cancelled", "deadline_exhausted"])
@pytest.mark.parametrize("duplicate", [False, True])
def test_stop_during_dedup_read_is_rechecked_before_canonical_append(tmp_path, previous_answer, monkeypatch, stop, duplicate):
    cancelled = Event()
    deadline = ResearchDeadline.from_timeout(0.05 if stop == "deadline_exhausted" else 5)
    real_read = workbench_correction_ingest._within_dedup_window

    def read_then_stop(*args):
        real_read(*args)
        if stop == "cancelled":
            cancelled.set()
        else:
            time.sleep(deadline.remaining() + 0.01)
        return duplicate

    monkeypatch.setattr(workbench_correction_ingest, "_within_dedup_window", read_then_stop)
    monkeypatch.setattr(corrections, "record_correction", lambda *a, **kw: pytest.fail("write began after known stop"))
    path = tmp_path / "corrections.jsonl"
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path, user_text="不对，应该先看板块容量再下结论", previous_assistant=previous_answer,
        conversation_id="conv-stop", corrected_message_id="msg-answer-1", is_cancelled=cancelled.is_set,
        deadline=deadline,
    )
    assert (result.status, result.reason) == ("failed", stop)
    assert not path.read_text()


def test_manual_writer_still_records_repeated_explicit_requests(tmp_path) -> None:
    path = tmp_path / "corrections.jsonl"
    for _ in range(2):
        corrections.record_correction(path, correction="先核验订单再看产能")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_runtime_finds_completed_assistant_not_latest_intent_message() -> None:
    context = ConversationContext(
        summary="",
        recent_messages=(
            Message(
                message_id="msg-completed",
                conversation_id="conv-1",
                role="assistant",
                content="上一轮完成稿",
                created_at="2026-09-25T01:00:00+00:00",
                status="completed",
            ),
            Message(
                message_id="msg-pending",
                conversation_id="conv-1",
                role="assistant",
                content="未完成草稿",
                created_at="2026-09-25T01:01:00+00:00",
                status="pending",
                turn_intent={"question_type": "stock_deep_dive"},
            ),
        ),
    )

    assert previous_completed_assistant_message(context).message_id == "msg-completed"


def test_runtime_guards_identity_and_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert workbench_correction_guard_reason("") == "identity_skipped"
    assert workbench_correction_guard_reason("tester") == "identity_skipped"
    assert workbench_correction_guard_reason("probe-alice") == "identity_skipped"
    assert workbench_correction_guard_reason("default") is None

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test-runtime")
    assert workbench_correction_guard_reason("default") == "identity_skipped"


def test_orchestrator_write_side_is_fail_open_and_uses_temp_user_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    store = ConversationStore("default", root=tmp_path / "conversations")
    run_store = RunStore("default", root=tmp_path / "runs")
    conversation = store.create_conversation()
    run = run_store.create_run("瑞华泰怎么看", "ask", session_id=conversation.conversation_id)
    traced: list[dict[str, object]] = []
    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=store,
        run_store=run_store,
    )
    monkeypatch.setattr(
        orchestrator,
        "_trace",
        lambda *args, **kwargs: traced.append(kwargs),
    )
    context = ConversationContext(
        summary="",
        recent_messages=(
            Message(
                message_id="msg-answer-1",
                conversation_id=conversation.conversation_id,
                role="assistant",
                content="双红后可以直接上车。",
                created_at="2026-09-25T01:00:00+00:00",
                status="completed",
            ),
        ),
    )

    orchestrator._maybe_ingest_workbench_correction(
        context=context,
        query="不对，应该先看板块容量再下结论",
        conversation_id=conversation.conversation_id,
        run_id=run.run_id,
        assistant_message_id="msg-new-answer",
        warnings=[],
    )

    path = tmp_path / "users" / "default" / "corrections.jsonl"
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["source"] == "workbench_conversation"
    assert traced[0]["status"] == "completed"


def test_orchestrator_write_failure_is_fail_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    store = ConversationStore("default", root=tmp_path / "conversations")
    run_store = RunStore("default", root=tmp_path / "runs")
    conversation = store.create_conversation()
    run = run_store.create_run("瑞华泰怎么看", "ask", session_id=conversation.conversation_id)
    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=store,
        run_store=run_store,
    )
    monkeypatch.setattr(orchestrator, "_trace", lambda *args, **kwargs: None)

    def fail_write(*args, **kwargs):
        raise OSError("fixture write failure")

    monkeypatch.setattr(
        workbench_correction_ingest,
        "maybe_record_workbench_correction",
        fail_write,
    )
    warnings: list[str] = []
    orchestrator._maybe_ingest_workbench_correction(
        context=ConversationContext(summary="", recent_messages=()),
        query="不对，应该先看板块容量再下结论",
        conversation_id=conversation.conversation_id,
        run_id=run.run_id,
        assistant_message_id="msg-new-answer",
        warnings=warnings,
    )

    assert warnings == ["user_correction_ingest_failed"]
