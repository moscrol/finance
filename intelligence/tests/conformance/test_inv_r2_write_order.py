"""INV-R2 效果三明治：任何外部效果前有 durable 意图、后有 durable 结算。

写序 oracle（``conformance/oracle.py``）包住 store 的 append，与假 model / 假 tool 的
「开始工作」时刻交错记录，断言每笔「意图 seq < 效果开始 < 结算 seq」、意图 fsync 而
结算不 fsync。非适用臂只验「确实不在场」：事件流里没有 model_intent、tool_request 不带
replay——有人给它接了却不改声明表，这里会红。
"""

from __future__ import annotations

import pytest

from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    MARKET_EVIDENCE_HASH,
    ScenarioProbe,
    ScriptedModelClient,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
)
from intelligence.tests.conformance.oracle import WriteOrderOracle

INV = "INV-R2"


class _EffectAwareModel:
    """脚本化 client 外面包一层：向 provider 开口的那一刻先告诉 oracle。"""

    def __init__(self, inner: ScriptedModelClient, oracle: WriteOrderOracle) -> None:
        self._inner = inner
        self._oracle = oracle

    def complete(self, *, messages, tools, timeout) -> ModelTurn:
        self._oracle.effect_started("model")
        return self._inner.complete(messages=messages, tools=tools, timeout=timeout)


def _effect_aware_registry(oracle: WriteOrderOracle) -> ResearchToolRegistry:
    def runner(query: str, _context: AgentToolContext):
        oracle.effect_started("tool", key=query)
        return (
            [
                AgentEvidence(
                    tool=AUTHORIZED_TOOL,
                    title="A股市场总览",
                    detail=f"{query}：上涨家数增加",
                    source="本地行情",
                    source_date="2026-07-24",
                    evidence_tier="L4",
                    content_hash=MARKET_EVIDENCE_HASH,
                )
            ],
            "上涨家数增加",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-24",
                result_count=1,
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name=AUTHORIZED_TOOL,
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )


_SCENARIO = (
    ScriptedTurn(
        tool_calls=(
            ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),
            ScriptedToolCall(AUTHORIZED_TOOL, "成交额"),
        ),
    ),
    ScriptedTurn(finish=completed_finish()),
)


def test_every_external_effect_is_sandwiched_by_durable_intent_and_settlement() -> None:
    """continuous_glm：两个工具并发 + 两次模型请求，每一笔都成三明治。"""

    oracle = WriteOrderOracle()
    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id="conf-inv-r2-continuous")
    runtime = GLMAgentRuntime(
        client=_EffectAwareModel(ScriptedModelClient(list(_SCENARIO), probe), oracle),
        episode_store=oracle,
    )
    outcome = runtime.run(
        task_frame=frame, context=context, registry=_effect_aware_registry(oracle)
    )

    assert outcome.status == "completed"
    oracle.assert_sandwich()
    intents = [e for e in outcome.events if e.kind == "model_intent"]
    settlements = [e for e in outcome.events if e.kind in {"model_turn", "model_error"}]
    assert len(intents) == 2 == len(settlements)
    assert [e.payload["turn_id"] for e in intents] == [e.payload["turn_id"] for e in settlements]
    requests = [e for e in outcome.events if e.kind == "tool_request"]
    assert [e.payload["replay"] for e in requests] == ["safe", "safe"]
    # 派发意图在结算之前（一批两个调用：请求₁请求₂结算₁结算₂）。
    kinds = [e.kind for e in outcome.events if e.kind in {"tool_request", "tool_result"}]
    assert kinds == ["tool_request", "tool_request", "tool_result", "tool_result"]
    # 状态机走过：planning → model_pending → tools_pending → planning → model_pending → done。
    phases = [entry.label for entry in oracle.timeline if entry.kind == "state"]
    assert phases[0] == "planning" and phases[-1] == "done"
    assert "tools_pending" in phases and "model_pending" in phases
    # store 里的日志与 outcome 事件逐条同形。
    stored, state = oracle.load("conf-inv-r2-continuous")
    assert [e.to_dict() for e in stored] == [e.to_dict() for e in outcome.events]
    assert state is not None and state.phase == "done" and state.last_sequence == len(stored)
    assert oracle.list_open() == ()


def test_store_failure_does_not_own_execution_but_is_receipted() -> None:
    """落盘失败进收据、不炸研究；失败后不再写（半份日志比没有更会骗恢复）。"""

    class BrokenStore(WriteOrderOracle):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def append(self, episode_id, events, *, sync=False):
            self.attempts += 1
            raise OSError("disk full")

    store = BrokenStore()
    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id="conf-inv-r2-broken")
    runtime = GLMAgentRuntime(
        client=ScriptedModelClient(list(_SCENARIO), probe), episode_store=store
    )
    outcome = runtime.run(task_frame=frame, context=context, registry=make_registry(probe))
    assert outcome.status == "completed"
    assert store.attempts == 1, "第一次失败后就该停写，而不是每条都再撞一次"


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_declared_arms_really_have_no_intent_events(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv-r2-{backend.name}")
    run = backend.build_driver().run(
        initial=(
            ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),)),
            ScriptedTurn(finish=completed_finish()),
        ),
        frame=frame,
        context=context,
        registry=make_registry(probe),
        probe=probe,
    )
    intents = [e for e in run.outcome.events if e.kind == "model_intent"]
    requests = [e for e in run.outcome.events if e.kind == "tool_request"]
    if verdict is Verdict.SUPPORTED:
        assert intents, f"{backend.name} 声明支持 INV-R2 却没有 model_intent"
        assert all("replay" in e.payload for e in requests), "派发意图必须带 replay 声明"
        model_settled = [e for e in run.outcome.events if e.kind in {"model_turn", "model_error"}]
        assert {e.payload["turn_id"] for e in intents} == {e.payload["turn_id"] for e in model_settled}
    else:
        assert not intents, (
            f"{backend.name} 声明 {verdict.value} 却发了 model_intent——先改 backends.py 声明表"
        )
        assert all("replay" not in e.payload for e in requests)
