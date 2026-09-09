"""06 号单：研究进展账接进连续 Episode 的行为测试（假模型、真 loop）。

守的是四件事：① 进展块叠在 ``runtime_budget`` 里且有 durable 承载（INV-R1 对账不破）；
② 同一查询反复无果 → 先建议换查询、再报停滞、最后关研究阶段（``research_stalled``），
已有证据一条不丢；③ 两个开关（整体 off / 收口阈值 0）各自把行为退回原样；
④ 工具报错不吞掉此前的成功证据。
"""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.task_frame import TaskFrame


class ScriptedModel:
    def __init__(self, turns: list[ModelTurn | Exception]) -> None:
        self._turns = iter(turns)
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, tools, timeout):
        self.calls.append(
            {"messages": deepcopy(messages), "tools": deepcopy(tools), "timeout": timeout}
        )
        effect = next(self._turns)
        if isinstance(effect, Exception):
            raise effect
        return effect


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _context(frame: TaskFrame, *, max_steps: int = 8) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="episode-progress-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=tuple(
            RequiredOutput(item, item, ("market_data",), True) for item in frame.required_outputs
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
        deadline=ResearchDeadline.from_timeout(60.0),
        policy=ResearchPolicy("quick", max_steps, 60.0, 0.0),
        trace_parent_id="episode-progress-test",
        today="2026-07-22",
        latest_data_date="2026-07-21",
    )


def _registry(runner) -> ResearchToolRegistry:
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


def _evidence_for(query: str) -> AgentEvidence:
    # 证据 hash 由查询决定：同查询 → 同 hash（重复），新查询 → 新 hash（新证据）。
    return AgentEvidence(
        tool="market_data",
        title=f"{query} 总览",
        detail=f"{query}：上涨家数增加",
        source="本地行情",
        source_date="2026-07-21",
        evidence_tier="L4",
        content_hash=f"hash-{query}",
    )


def _runner(query: str, _context: AgentToolContext):
    return (
        [_evidence_for(query)],
        f"raw market observation {query}",
        ProviderTrace(
            provider="test:market",
            capability="market_data",
            status="success",
            source_trade_date="2026-07-21",
            result_count=1,
        ),
    )


def _tool_turn(query: str, call_id: str) -> ModelTurn:
    return ModelTurn("", (ModelToolCall(call_id, "market_data", {"query": query}),), "scripted", "")


def _finish_turn(hashes: tuple[str, ...]) -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": "当前更接近条件化修复，持续性取决于量能。",
                "gaps": [],
                "bindings": [
                    {"output_id": "direct_assessment", "evidence_hashes": list(hashes), "gap": ""}
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def _budget_blocks(model: ScriptedModel) -> list[dict[str, object]]:
    """每次模型请求时最后一条 tool 消息上的 runtime_budget（按请求顺序）。"""

    blocks: list[dict[str, object]] = []
    for call in model.calls:
        tools = [m for m in call["messages"] if m.get("role") == "tool"]
        if not tools:
            continue
        payload = json.loads(str(tools[-1]["content"]))
        if isinstance(payload, dict) and "runtime_budget" in payload:
            blocks.append(payload["runtime_budget"])
    return blocks


def _run(model: ScriptedModel, *, max_steps: int = 8):
    frame = _frame()
    return ContinuousAgentEpisode(model).run(
        task_frame=frame, context=_context(frame, max_steps=max_steps), registry=_registry(_runner)
    )


def test_progress_block_rides_runtime_budget_and_is_durable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_RESEARCH_PROGRESS", raising=False)
    model = ScriptedModel([_tool_turn("q1", "c1"), _finish_turn(("hash-q1",))])
    outcome = _run(model)

    assert outcome.status == "completed" and outcome.stop_reason == "model_finish"
    blocks = _budget_blocks(model)
    assert len(blocks) == 1
    progress = blocks[0]["research_progress"]
    assert progress["batch"] == 1 and progress["new_evidence"] == 1
    assert progress["evidence_total"] == 1 and progress["stalled_batches"] == 0
    assert progress["last_batch"] == [{"tool": "market_data", "query": "q1", "result": "new:1"}]
    assert "suggestion" not in progress
    # durable 承载：tool_budget_state 事件里的 runtime_budget 与模型看到的同一份。
    states = [e for e in outcome.events if e.kind == "tool_budget_state"]
    assert len(states) == 1
    assert states[0].payload["runtime_budget"]["research_progress"]["batch"] == 1
    assert json.loads(str(states[0].payload["model_content"]))["runtime_budget"] == blocks[0]


def test_repeated_query_is_steered_then_stalled_then_finalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_RESEARCH_PROGRESS", raising=False)
    monkeypatch.setenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", "3")
    model = ScriptedModel(
        [
            _tool_turn("q1", "c1"),
            _tool_turn("q1", "c2"),
            _tool_turn("q1", "c3"),
            _tool_turn("q1", "c4"),
            _finish_turn(("hash-q1",)),
        ]
    )
    outcome = _run(model)

    assert outcome.status == "completed" and outcome.stop_reason == "model_finish"
    # 已有证据一条不丢：四批只有第一批带来证据，终局仍绑到它。
    assert [item.content_hash for item in outcome.evidence] == ["hash-q1"]
    assert outcome.bindings[0].evidence_hashes == ("hash-q1",)

    blocks = _budget_blocks(model)
    assert len(blocks) == 4
    second, third, fourth = blocks[1]["research_progress"], blocks[2]["research_progress"], blocks[3]["research_progress"]
    # 第 2 批：同查询第二次、零新证据 → 换查询。
    assert second["stalled_batches"] == 1
    assert second["repeated_queries"] == [{"tool": "market_data", "query": "q1", "attempts": 2}]
    assert "switch_query" in second["suggestion"] and "stalled" not in second["suggestion"]
    assert "重复同一查询不会带来新证据" in second["instruction"]
    # 第 3 批：连续两批零新证据 → 报停滞并预告收口。
    assert third["stalled_batches"] == 2 and "stalled" in third["suggestion"]
    assert "再一批没有新证据，研究阶段将自动关闭" in third["instruction"]
    # 第 4 批：连续三批 → 关研究阶段，最后一次模型请求不再给工具。
    assert fourth["stalled_batches"] == 3
    finalizations = [e for e in outcome.events if e.kind == "finalization"]
    assert [e.payload["reason"] for e in finalizations] == ["research_stalled"]
    assert model.calls[-1]["tools"] == []
    closing = [m for m in model.calls[-1]["messages"] if m.get("role") == "user"][-1]
    assert str(closing["content"]).endswith("关闭原因：research_stalled")
    # 重复调用被去重闸拒掉的那三次记成 duplicate，不是笼统 rejected。
    duplicates = [e for e in outcome.events if e.kind == "tool_error" and e.payload.get("error") == "duplicate_query"]
    assert len(duplicates) == 3
    assert fourth["last_batch"] == [{"tool": "market_data", "query": "q1", "result": "duplicate"}]


def test_new_evidence_resets_stall_and_finalization_does_not_fire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_RESEARCH_PROGRESS", raising=False)
    monkeypatch.setenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", "3")
    model = ScriptedModel(
        [
            _tool_turn("q1", "c1"),
            _tool_turn("q1", "c2"),
            _tool_turn("q1", "c3"),
            _tool_turn("q2", "c4"),
            _finish_turn(("hash-q1", "hash-q2")),
        ]
    )
    outcome = _run(model)
    assert outcome.status == "completed"
    assert [e.kind for e in outcome.events if e.kind == "finalization"] == []
    blocks = _budget_blocks(model)
    fourth = blocks[3]["research_progress"]
    assert fourth["stalled_batches"] == 0 and fourth["new_evidence"] == 1 and fourth["evidence_total"] == 2
    assert "stalled" not in fourth.get("suggestion", [])
    assert sorted(item.content_hash for item in outcome.evidence) == ["hash-q1", "hash-q2"]


def test_stall_finalization_default_off_only_steers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_RESEARCH_PROGRESS", raising=False)
    # 缺省不设阈值 = 只提醒不收口（既有 loop 测试的预算账不变）。
    monkeypatch.delenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", raising=False)
    model = ScriptedModel(
        [
            _tool_turn("q1", "c1"),
            _tool_turn("q1", "c2"),
            _tool_turn("q1", "c3"),
            _tool_turn("q1", "c4"),
            _tool_turn("q1", "c5"),
            _finish_turn(("hash-q1",)),
        ]
    )
    outcome = _run(model)
    assert outcome.status == "completed"
    assert [e for e in outcome.events if e.kind == "finalization"] == []
    fifth = _budget_blocks(model)[4]["research_progress"]
    assert fifth["stalled_batches"] == 4 and "stalled" in fifth["suggestion"]
    assert "自动关闭" not in fifth["instruction"]
    # 阈值 0：模型直到自己收口前都还能拿到工具。
    assert model.calls[-1]["tools"] != []


def test_progress_off_switch_restores_previous_budget_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_RESEARCH_PROGRESS", "off")
    monkeypatch.setenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", "3")
    model = ScriptedModel(
        [
            _tool_turn("q1", "c1"),
            _tool_turn("q1", "c2"),
            _tool_turn("q1", "c3"),
            _tool_turn("q1", "c4"),
            _finish_turn(("hash-q1",)),
        ]
    )
    outcome = _run(model)
    assert outcome.status == "completed"
    assert all("research_progress" not in block for block in _budget_blocks(model))
    assert [e for e in outcome.events if e.kind == "finalization"] == []


def test_tool_error_after_success_keeps_evidence_and_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_RESEARCH_PROGRESS", raising=False)

    def flaky(query: str, context: AgentToolContext):
        if query == "boom":
            raise RuntimeError("provider exploded")
        return _runner(query, context)

    frame = _frame()
    model = ScriptedModel([_tool_turn("q1", "c1"), _tool_turn("boom", "c2"), _finish_turn(("hash-q1",))])
    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame, context=_context(frame), registry=_registry(flaky)
    )
    assert outcome.status == "completed"
    assert [item.content_hash for item in outcome.evidence] == ["hash-q1"]
    second = _budget_blocks(model)[1]["research_progress"]
    assert second["last_batch"] == [{"tool": "market_data", "query": "boom", "result": "error"}]
    assert second["stalled_batches"] == 1 and second["evidence_total"] == 1
