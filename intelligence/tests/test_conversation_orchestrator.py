import io
import json
import urllib.error
from dataclasses import asdict
from threading import Event

import pytest

from intelligence.services import llm_refine
from intelligence.services.ask import AskOptions, AskResult
from intelligence.services.conversation_orchestrator import (
    TurnOrchestrator,
    build_conversation_context,
    sanitize_conversation_answer,
)
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.run_store import RunStore
from intelligence.workbench_skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
)
from intelligence.workbench_skills.registry import (
    SkillRegistry,
    builtin_skill_registry,
)
from intelligence.workbench_skills.router import (
    SkillRouteResult,
    SkillSelection,
    route_skills,
)


def _ask_result(
    query: str,
    *,
    synthesis: str | None = None,
    llm_provider: str | None = None,
) -> AskResult:
    return AskResult(
        query=query,
        trade_date="2026-07-11",
        matched_theme="测试题材",
        candidate_tier="A",
        priority_score=1.0,
        sections={"结论": [f"本轮检索：{query}"], "引用来源": ["[S1] fixture"]},
        found_market=True,
        synthesis=synthesis,
        llm_provider=llm_provider,
    )


def _prepare_turn(
    conversation_store: ConversationStore,
    run_store: RunStore,
    conversation_id: str,
    query: str,
    *,
    selected_skill_ids: list[str] | None = None,
) -> tuple[str, str]:
    conversation = conversation_store.load_conversation(conversation_id)
    run = run_store.create_run(
        query,
        "ask",
        session_id=conversation_id,
        parent_run_id=conversation.last_run_id,
    )
    conversation_store.append_message(
        conversation_id,
        "user",
        query,
        run_id=run.run_id,
        selected_skill_ids=selected_skill_ids,
    )
    assistant = conversation_store.append_message(
        conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    conversation_store.update_summary(
        conversation_id,
        conversation.summary,
        last_run_id=run.run_id,
    )
    return run.run_id, assistant.message_id


def test_three_turns_retrieve_fresh_and_include_bounded_context(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation("三轮测试")
    calls: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        return _ask_result(options.query)

    parent_run_id = None
    run_ids: list[str] = []
    for query in ("第一轮：液冷怎么样？", "第二轮：证据够硬吗？", "第三轮：下一步看什么？"):
        run_id, assistant_message_id = _prepare_turn(
            conversation_store, run_store, conversation.conversation_id, query
        )
        TurnOrchestrator(
            repo_root=tmp_path,
            conversation_store=conversation_store,
            run_store=run_store,
            answer_query_fn=answer_spy,
            skill_registry=SkillRegistry(),
        ).run_turn(
            conversation_id=conversation.conversation_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            query=query,
            skill_mode="auto",
            selected_skill_ids=[],
        )
        run = run_store.load_run(run_id)
        assert run.session_id == conversation.conversation_id
        assert run.parent_run_id == parent_run_id
        parent_run_id = run_id
        run_ids.append(run_id)

    assert [call.query for call in calls] == [
        "第一轮：液冷怎么样？",
        "第二轮：证据够硬吗？",
        "第三轮：下一步看什么？",
    ]
    assert len(calls) == 3
    assert "较早消息摘要" in calls[1].conversation_context
    assert "第一轮：液冷怎么样？" in calls[1].conversation_context
    assert "第二轮：证据够硬吗？" not in calls[1].conversation_context
    assert "第一轮：液冷怎么样？" in calls[2].conversation_context
    assert "第二轮：证据够硬吗？" in calls[2].conversation_context
    assert [run_store.load_run(run_id).status for run_id in run_ids] == [
        "completed",
        "completed",
        "completed",
    ]


def test_context_keeps_six_recent_messages_and_summarizes_older(tmp_path) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    for index in range(10):
        store.append_message(
            conversation.conversation_id,
            "user" if index % 2 == 0 else "assistant",
            f"message-{index}",
            run_id=f"run-{index}",
        )

    context = build_conversation_context(
        conversation,
        store.load_messages(conversation.conversation_id),
        current_run_id="run-current",
    )

    assert [message.content for message in context.recent_messages] == [
        "message-4",
        "message-5",
        "message-6",
        "message-7",
        "message-8",
        "message-9",
    ]
    assert "message-0" in context.summary
    assert "message-3" in context.summary
    assert "message-4" not in context.summary


def test_market_question_automatically_selects_daily_review() -> None:
    registry = builtin_skill_registry()

    route = route_skills(
        "今天市场怎么样？",
        "ask",
        "auto",
        [],
        registry=registry.definitions,
        llm_complete=lambda _: (None, None, "fixture no llm"),
    )

    assert [selection.skill_id for selection in route.selections] == [
        "daily-review"
    ]


class _FailingSkill:
    skill_id = "broken"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        raise RuntimeError("token=must-not-leak")


class _SuccessfulSkill:
    skill_id = "fixture"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        return SkillOutput(
            skill_id=self.skill_id,
            modules=[
                {
                    "module_id": "fixture_metric",
                    "title": "Fixture metric",
                    "kind": "metrics",
                    "status": "complete",
                    "summary": None,
                    "content": None,
                    "metrics": [{"label": "涨家数", "value": 3210}],
                    "items": [],
                    "table": None,
                    "warnings": [],
                    "provenance": {
                        "source": "canonical-fixture",
                        "as_of": "2026-07-11",
                    },
                }
            ],
            citations=[
                {
                    "source": "canonical-fixture",
                    "evidence_layer": "canonical",
                }
            ],
            warnings=[],
            as_of="2026-07-11",
            raw_result_ref="fixture.json",
        )


def test_current_skill_output_is_injected_as_current_turn_evidence(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "结合日报回答",
        selected_skill_ids=["fixture"],
    )
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="fixture",
            name="Fixture",
            description="fixture",
            version="1.0.0",
            triggers=("日报",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        _SuccessfulSkill(),
    )
    calls: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        return _ask_result(options.query)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=registry,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="结合日报回答",
        skill_mode="manual",
        selected_skill_ids=["fixture"],
    )

    assert len(calls) == 1
    assert "指标：涨家数=3210" in calls[0].supplemental_evidence
    assert '"value": 3210' not in calls[0].supplemental_evidence
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.selected_skill_ids == ["fixture"]
    assert assistant.invoked_skill_ids == ["fixture"]
    assert assistant.citations[0]["evidence_layer"] == "canonical"


def test_skill_failure_degrades_only_its_module_and_ask_still_completes(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "继续检索",
        selected_skill_ids=["broken"],
    )
    registry = SkillRegistry()
    registry.register(
        definition=SkillDefinition(
            skill_id="broken",
            name="Broken",
            description="fixture",
            version="1.0.0",
            triggers=("broken",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        executor=_FailingSkill(),
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=registry,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="继续检索",
        skill_mode="manual",
        selected_skill_ids=["broken"],
    )

    run = run_store.load_run(run_id)
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    skill_result = next(
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "skill.result"
    )
    assert run.status == "completed"
    assert assistant.status == "completed"
    assert assistant.invoked_skill_ids == ["broken"]
    assert any("broken" in warning for warning in assistant.degrades)
    assert "must-not-leak" not in json.dumps(asdict(assistant), ensure_ascii=False)
    assert skill_result["payload"]["status"] == "degraded"


def test_cooperative_cancellation_preserves_completed_skill_events(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store, run_store, conversation.conversation_id, "取消本轮"
    )
    cancelled = Event()

    def route_then_cancel(*args: object, **kwargs: object) -> SkillRouteResult:
        cancelled.set()
        return SkillRouteResult(
            selections=(SkillSelection("daily-review", "rule", "fixture"),),
            fallback_to_ask=False,
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: pytest.fail("取消后不应检索"),
        route_skills_fn=route_then_cancel,
        is_cancelled=cancelled.is_set,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="取消本轮",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert run_store.load_run(run_id).status == "cancelled"
    assert assistant.status == "cancelled"
    assert any(
        event["event_type"] == "message.error"
        and event["payload"]["status"] == "cancelled"
        for event in run_store.load_stream_events(run_id)
    )


def test_template_answer_is_saved_and_streamed_once_without_llm(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "无 key 也要回答",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="无 key 也要回答",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    text_events = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "text.delta"
    ]
    run = run_store.load_run(run_id)
    assert len(text_events) == 1
    assert "自然语言综合暂时不可用" in text_events[0]["payload"]["delta"]
    assert "命中主题" not in text_events[0]["payload"]["delta"]
    assert [artifact["path"] for artifact in run.artifacts] == [
        "answer.md",
        "report.json",
    ]
    assert "llm_unavailable_template_answer" in run.degrades


def test_successful_llm_report_persists_selected_model(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "真实模型回答",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(
            options.query,
            synthesis="真实模型输出",
            llm_provider="zhipu",
        ),
        skill_registry=SkillRegistry(),
        llm_model="glm-4-flash",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="真实模型回答",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["llm"] == {
        "used": True,
        "provider": "zhipu",
        "model": "glm-4-flash",
    }


def test_recovered_turn_prefixes_event_ids_to_avoid_replay_collisions(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "恢复后继续",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
        event_id_prefix="recovery:2:",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="恢复后继续",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    events = run_store.load_stream_events(run_id)
    assert events
    assert all(
        event["event_id"].startswith("recovery:2:")
        for event in events
    )


def test_completed_stream_persists_human_readable_answer(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "今日复盘",
    )
    raw_answer = (
        "**数据截至 2026-07-10。**\n\n"
        "以下基于 Daily Review 确定性投影数据。盘面 L4 信号待确认，"
        "replay 发酵信号也未匹配到任何主题，wiki 向量检索无可用命中。"
        "公司只有 graph_only/低置信暴露，整体证据层分布为 "
        "L1×6、L2×6、L4×1，尚缺 L3 硬证据。[D4]"
        "本轮未命中任何 L3硬证据硬证据。优先走 L3 证据工具补查。"
        "当前属于 high/L1_L3_candidate，L1/L2 认知完整但 "
        "cycle_status 仍需确认，RAG检索的wiki向量源降级未接入。"
    )

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.stream_text_delta is not None
        options.stream_text_delta(raw_answer)
        return _ask_result(
            options.query,
            synthesis=raw_answer,
            llm_provider="zhipu",
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="今日复盘",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.content == sanitize_conversation_answer(raw_answer)
    assert "2026-07-10" in assistant.content
    assert "本地复盘数据" in assistant.content
    assert "历史发酵信号" in assistant.content
    assert "知识库没有提供可用补充" in assistant.content
    assert "较高置信候选" in assistant.content
    assert "行业资料/公司基础资料" in assistant.content
    assert "阶段状态" in assistant.content
    assert "知识库资料没有提供可用补充" in assistant.content
    assert "公告等硬证据工具" in assistant.content
    assert "硬证据证据" not in assistant.content
    assert "硬证据硬证据" not in assistant.content
    for internal in (
        "Daily Review",
        "L1",
        "L2",
        "L3",
        "L4",
        "replay",
        "wiki",
        "graph_only",
        "high/L1_L3_candidate",
        "cycle_status",
        "RAG",
        "[D4]",
    ):
        assert internal not in assistant.content


def test_cancellation_between_text_deltas_marks_run_cancelled(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "流式取消",
    )
    cancelled = Event()

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.stream_text_delta is not None
        options.stream_text_delta("已完成片段")
        cancelled.set()
        options.stream_text_delta("不应落盘")
        return _ask_result(options.query, synthesis="已完成片段不应落盘")

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        is_cancelled=cancelled.is_set,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="流式取消",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert run_store.load_run(run_id).status == "cancelled"
    assert assistant.content == "已完成片段"
    assert assistant.status == "cancelled"


class _StreamingResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_openai_compatible_stream_forwards_real_provider_deltas(monkeypatch) -> None:
    provider = llm_refine.LLMProvider("fixture", "key", "https://llm.invalid/v1", "model")
    body = (
        b'data: {"choices":[{"delta":{"content":"real "}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"delta"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _StreamingResponse(body),
    )
    deltas: list[str] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
    )

    assert reason == ""
    assert result is not None
    assert result.answer == "real delta"
    assert deltas == ["real ", "delta"]


def test_openai_stream_checks_cancellation_between_provider_deltas(
    monkeypatch,
) -> None:
    provider = llm_refine.LLMProvider("fixture", "key", "https://llm.invalid/v1", "model")
    body = (
        b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"second"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _StreamingResponse(body),
    )
    cancelled = Event()
    deltas: list[str] = []

    def on_delta(delta: str) -> None:
        deltas.append(delta)
        cancelled.set()

    with pytest.raises(llm_refine.LLMStreamCancelled):
        llm_refine.synthesize_messages_stream(
            [{"role": "user", "content": "question"}],
            on_delta=on_delta,
            is_cancelled=cancelled.is_set,
        )

    assert deltas == ["first"]


def test_stream_unsupported_falls_back_to_one_complete_delta(monkeypatch) -> None:
    provider = llm_refine.LLMProvider("fixture", "key", "https://llm.invalid/v1", "model")
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    unsupported = urllib.error.HTTPError(
        "https://llm.invalid/v1/chat/completions",
        422,
        "stream unsupported",
        {},
        None,
    )
    monkeypatch.setattr(
        llm_refine,
        "_post_chat_stream",
        lambda *args, **kwargs: (_ for _ in ()).throw(unsupported),
    )
    monkeypatch.setattr(llm_refine, "_post_chat", lambda *args, **kwargs: "whole answer")
    deltas: list[str] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
    )

    assert reason == ""
    assert result is not None
    assert result.answer == "whole answer"
    assert deltas == ["whole answer"]


def test_message_revision_keeps_jsonl_append_only_but_loads_latest_state(tmp_path) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    pending = store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id="run-1",
    )

    completed = store.revise_message(
        conversation.conversation_id,
        pending.message_id,
        content="最终回答",
        status="completed",
        invoked_skill_ids=["daily-review"],
    )

    assert store.load_messages(conversation.conversation_id) == [completed]
    raw_lines = (
        tmp_path / conversation.conversation_id / "messages.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["message_id"] for line in raw_lines] == [
        pending.message_id,
        pending.message_id,
    ]
