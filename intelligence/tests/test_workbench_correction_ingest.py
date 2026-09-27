from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.runtime.conversation_orchestrator import (
    ConversationContext,
    TurnOrchestrator,
    previous_completed_assistant_message,
    workbench_correction_guard_reason,
)
from intelligence.services import workbench_correction_ingest
from intelligence.services.conversation_store import ConversationStore, Message
from intelligence.services.run_store import RunStore


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
    "user_text,correction",
    [
        ("你刚才说双红就能上，不对，应该先看容量", "先看容量"),
        ("错了，应为先看客户验证进度", "先看客户验证进度"),
        ("你理解错了，这里应为先看订单再看产能", "先看订单再看产能"),
        ("这里应该是先看客户验证进度再谈弹性", "先看客户验证进度再谈弹性"),
        ("不是产能公告，是客户验证进度", "客户验证进度"),
    ],
)
def test_design_payload_forms_still_write(
    tmp_path: Path, previous_answer, user_text: str, correction: str
) -> None:
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


def test_duplicate_within_24_hours_is_skipped(tmp_path: Path, previous_answer) -> None:
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
        **kwargs, ts="2026-09-25T20:00:00+00:00"
    )

    assert first.status == "recorded"
    assert second.status == "skipped"
    assert second.reason == "dedup"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


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
