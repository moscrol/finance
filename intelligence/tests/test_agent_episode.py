from __future__ import annotations

from copy import deepcopy
import json

from intelligence.services.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import (
    ModelToolCall,
    ModelTurn,
)
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame


class ScriptedModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = iter(turns)
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, tools, timeout):
        self.calls.append(
            {
                "messages": deepcopy(messages),
                "tools": deepcopy(tools),
                "timeout": timeout,
            }
        )
        return next(self._turns)


def _frame(required_outputs: tuple[str, ...] = ("direct_assessment",)) -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=required_outputs,
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _context(
    frame: TaskFrame,
    *,
    max_steps: int = 3,
) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="episode-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=tuple(
            RequiredOutput(item, item, ("market_data",), True)
            for item in frame.required_outputs
        ),
        allowed_capabilities=("market_data",),
        research_tier="quick",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", max_steps, 30.0, 0.0),
        trace_parent_id="episode-test",
        today="2026-07-22",
        latest_data_date="2026-07-21",
    )


def _market_registry(runner) -> ResearchToolRegistry:
    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情与市场时序",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )


def _successful_runner(
    query: str,
    _context: AgentToolContext,
):
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail=f"{query}：上涨家数增加，成交保持活跃",
        source="本地行情",
        source_date="2026-07-21",
        evidence_tier="L4",
        content_hash="evidence-1",
    )
    return [evidence], "raw market observation", ProviderTrace(
        provider="test:market",
        capability="market_data",
        status="success",
        source_trade_date="2026-07-21",
        result_count=1,
    )


def _tool_turn(query: str, *, call_id: str = "call-1", name: str = "market_data") -> ModelTurn:
    return ModelTurn(
        "",
        (ModelToolCall(call_id, name, {"query": query}),),
        "scripted",
        "",
    )


def _finish_turn(
    *,
    status: str = "completed",
    draft: str = "当前更接近条件化修复，持续性取决于量能。",
    hashes: tuple[str, ...] = ("evidence-1",),
    gap: str = "",
) -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": status,
                "draft": draft,
                "gaps": [gap] if gap else [],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": list(hashes),
                        "gap": gap,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def test_second_model_turn_keeps_first_action_and_raw_tool_observation() -> None:
    frame = _frame()
    model = ScriptedModel([_tool_turn("A股 最新行情"), _finish_turn()])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    first_messages = model.calls[0]["messages"]
    second_messages = model.calls[1]["messages"]
    assert second_messages[:2] == first_messages[:2]
    assert second_messages[2]["role"] == "assistant"
    assert second_messages[2]["tool_calls"][0]["function"]["name"] == "market_data"
    assert second_messages[3]["role"] == "tool"
    tool_payload = json.loads(second_messages[3]["content"])
    assert tool_payload["observation"] == "raw market observation"
    assert tool_payload["evidence_hashes"] == ["evidence-1"]
    assert outcome.status == "completed"
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 1
    assert outcome.evidence[0].content_hash == "evidence-1"
    assert all(
        event.payload["task_frame_hash"] == frame.task_frame_hash
        for event in outcome.events
    )


def test_unknown_tool_error_returns_to_same_episode_without_runner_call() -> None:
    calls: list[str] = []

    def runner(query: str, context: AgentToolContext):
        calls.append(query)
        return _successful_runner(query, context)

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("rm -rf /", name="shell_exec"),
            _finish_turn(
                status="partial",
                draft="未执行未授权工具，当前无法完成判断。",
                hashes=(),
                gap="未授权工具不能执行",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(runner),
    )

    assert calls == []
    assert outcome.status == "partial"
    assert outcome.usage.tool_calls == 0
    assert outcome.usage.invalid_actions == 1
    second_messages = model.calls[1]["messages"]
    assert second_messages[-1]["role"] == "tool"
    assert "unknown_or_unauthorized_tool" in second_messages[-1]["content"]


def test_duplicate_normalized_query_is_rejected_without_second_execution() -> None:
    calls: list[str] = []

    def runner(query: str, context: AgentToolContext):
        calls.append(query)
        return _successful_runner(query, context)

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情", call_id="call-1"),
            _tool_turn("  a股   最新行情 ", call_id="call-2"),
            _finish_turn(status="partial"),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(runner),
    )

    assert calls == ["A股 最新行情"]
    assert outcome.usage.tool_calls == 1
    assert outcome.usage.invalid_actions == 1
    assert "duplicate_query" in model.calls[2]["messages"][-1]["content"]


def test_tool_exception_is_traced_and_model_can_finish_same_episode() -> None:
    def broken_runner(_query: str, _context: AgentToolContext):
        raise RuntimeError("provider unavailable")

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            _finish_turn(
                status="partial",
                draft="行情工具不可用，本轮只能报告证据缺口。",
                hashes=(),
                gap="行情工具暂不可用",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(broken_runner),
    )

    assert outcome.status == "partial"
    assert outcome.usage.tool_calls == 1
    assert outcome.traces[0].status == "request_error"
    assert outcome.traces[0].step_id == "episode-test:episode:1"
    assert "tool_exception" in model.calls[1]["messages"][-1]["content"]


def test_invalid_completed_finish_gets_one_repair_turn_in_same_history() -> None:
    frame = _frame()
    invalid_finish = ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": "已经完成。",
                "gaps": [],
                "bindings": [],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )
    model = ScriptedModel(
        [_tool_turn("A股 最新行情"), invalid_finish, _finish_turn()]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.usage.invalid_actions == 1
    repair_messages = model.calls[2]["messages"]
    assert repair_messages[-1]["role"] == "user"
    assert "required output" in repair_messages[-1]["content"]
    assert any(event.kind == "invalid_action" for event in outcome.events)


def test_second_invalid_finish_returns_partial_without_template_fallback() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            ModelTurn("not json", (), "scripted", ""),
            ModelTurn("still not json", (), "scripted", ""),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "invalid_model_finish"
    assert outcome.draft == ""
    assert outcome.usage.invalid_actions == 2
    assert "模型未能返回可验证的结构化终止结果" in outcome.gaps


def test_step_exhaustion_preserves_collected_evidence_and_reports_gap() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 行情 1", call_id="call-1"),
            _tool_turn("A股 行情 2", call_id="call-2"),
            _tool_turn("A股 行情 3", call_id="call-3"),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=3),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "step_exhausted"
    assert outcome.evidence
    assert outcome.usage.llm_calls == 3
    assert outcome.usage.tool_calls == 3
    assert "研究预算已耗尽，仍有必需输出未覆盖" in outcome.gaps


def test_model_unavailable_before_evidence_fails_honestly() -> None:
    frame = _frame()
    model = ScriptedModel(
        [ModelTurn("", (), "glm", "provider unavailable")]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "failed"
    assert outcome.stop_reason == "model_unavailable"
    assert outcome.draft == ""
    assert "provider unavailable" in outcome.gaps


def test_multiple_tool_calls_cannot_bypass_total_step_budget() -> None:
    calls: list[str] = []

    def runner(query: str, context: AgentToolContext):
        calls.append(query)
        return _successful_runner(query, context)

    frame = _frame()
    batched_turn = ModelTurn(
        "",
        tuple(
            ModelToolCall(f"call-{index}", "market_data", {"query": f"行情 {index}"})
            for index in range(1, 4)
        ),
        "scripted",
        "",
    )
    model = ScriptedModel([batched_turn, _finish_turn()])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=2),
        registry=_market_registry(runner),
    )

    assert calls == ["行情 1", "行情 2"]
    assert outcome.usage.tool_calls == 2
    assert outcome.usage.invalid_actions == 1
    assert "tool_budget_exhausted" in model.calls[1]["messages"][-1]["content"]
