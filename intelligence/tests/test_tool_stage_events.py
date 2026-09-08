"""工具阶段事件与可达性登记（spec §7.1/§7.2，实施顺序第 3 步）。

这里验的是**接线**：registry.execute 在拿到 scope 时发事件、登记调用，
拿不到 scope 时行为与接线前逐字节一致。
"""

from __future__ import annotations

import pytest

from intelligence.services import agent_research, query_ledger
from intelligence.services.episode_scope import (
    TOOL_ERROR,
    TOOL_PRE_EXECUTE,
    TOOL_RESULT,
    EpisodeScope,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    QUERY_TOOL_PARAMETERS,
    ResearchToolRegistry,
    ToolSpec,
    UnknownResearchTool,
)


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, kind: str, payload: dict) -> None:
        self.events.append((kind, dict(payload)))

    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.events]

    def payload(self, kind: str) -> dict:
        for seen, payload in self.events:
            if seen == kind:
                return payload
        raise AssertionError(f"没有 {kind} 事件；实际有 {self.kinds()}")


def _ok_runner(
    value: str,
    context: agent_research.AgentToolContext,
) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
    return ([], f"ran {value}", ProviderTrace(provider="test", capability="market_data", status="ok"))


def _boom_runner(
    value: str,
    context: agent_research.AgentToolContext,
) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
    raise RuntimeError("runner 炸了")


def _registry(runner=_ok_runner) -> ResearchToolRegistry:
    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="行情",
                cost="local",
                freshness="current",
                runner=runner,
                parameters=dict(QUERY_TOOL_PARAMETERS),
            ),
            ToolSpec(
                name="memory_lookup",
                capability="memory_lookup",
                description="记忆",
                cost="local",
                freshness="stable",
                runner=runner,
                parameters=dict(QUERY_TOOL_PARAMETERS),
            ),
        )
    )


def _context(allowed: tuple[str, ...] = ("market_data",)) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="stage-events",
        question="测试",
        subject=None,
        subject_kind=None,
        question_type="quick_fact",
        required_outputs=(RequiredOutput("direct_assessment", "判断", allowed, True),),
        allowed_capabilities=allowed,
        task_frame_hash="hash-1",
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(5.0),
        policy=ResearchPolicy("quick", 4, 5.0, 0.0),
        trace_parent_id="stage-events",
    )


def _scope(registry: ResearchToolRegistry, sink: RecordingSink | None = None):
    return EpisodeScope(
        episode_id="ep-1",
        user_id="u-1",
        context=_context(),
        registry=registry,
        event_sink=sink,
    )


# 去重由 ``query_ledger_scope()`` 这个 ContextVar 上下文管理器界定：
# 不进该 scope 就没有 ledger，``executed`` 直接透传。所以只有那条去重用例需要
# 显式开 scope，其余用例天然互不干扰。


# ── 不传 scope：与接线前逐字节一致 ─────────────────────────────────────


def test_without_scope_nothing_is_emitted_and_result_unchanged() -> None:
    registry = _registry()
    observation = registry.execute(
        "market_data",
        {"query": "上证"},
        context=_context(),
        step_id="s-1",
    )
    assert observation.tool == "market_data"
    assert "ran" in observation.observation


def test_without_scope_authorization_error_contract_unchanged() -> None:
    """错误契约没动：仍是 UnknownResearchTool，消息逐字不变。"""

    registry = _registry()
    with pytest.raises(UnknownResearchTool, match="能力未授权：memory_lookup"):
        registry.execute(
            "memory_lookup",
            {"query": "x"},
            context=_context(),
            step_id="s-1",
        )


# ── 传 scope：发事件、登记调用 ─────────────────────────────────────────


def test_successful_call_emits_pre_execute_then_result() -> None:
    registry = _registry()
    sink = RecordingSink()
    scope = _scope(registry, sink)

    registry.execute(
        "market_data",
        {"query": "上证"},
        context=_context(),
        step_id="s-1",
        scope=scope,
        tool_call_id="call-42",
    )

    assert sink.kinds() == [TOOL_PRE_EXECUTE, TOOL_RESULT]
    assert sink.payload(TOOL_PRE_EXECUTE)["tool_call_id"] == "call-42"
    assert sink.payload(TOOL_RESULT)["tool_call_id"] == "call-42"


def test_invocation_is_recorded_for_reachability() -> None:
    registry = _registry()
    scope = _scope(registry)
    assert scope.dump()["invoked_tools"] == []

    registry.execute(
        "market_data",
        {"query": "上证"},
        context=_context(),
        step_id="s-1",
        scope=scope,
    )

    rows = {row["name"]: row for row in scope.dump()["tools"]}
    assert rows["market_data"]["invoked"] is True
    assert rows["market_data"]["broken_at"] is None


def test_deduplicated_call_is_not_recorded_as_invoked() -> None:
    """被去重挡掉的第二次调用不能记成跑过了。

    登记写在 fetch 闭包里而不是 execute 顶部，就是为了这个：可达性收据说
    「跑过」时，必须真的有 runner 被调起。
    """

    calls: list[str] = []

    def counting_runner(value, context):
        calls.append(value)
        return _ok_runner(value, context)

    registry = _registry(counting_runner)
    scope = _scope(registry)

    with query_ledger.query_ledger_scope():
        for _ in range(2):
            registry.execute(
                "market_data",
                {"query": "同一个问题"},
                context=_context(),
                step_id="s-1",
                scope=scope,
            )

    assert len(calls) == 1, "第二次应被 query ledger 去重"
    assert scope.dump()["invoked_tools"] == ["market_data"]


def test_authorization_denial_emits_distinction_without_changing_contract() -> None:
    """事件里分得清「未授权」，而抛出的异常一个字没变。

    这是本步刻意画的边界：unknown_or_unauthorized_tool 那个压扁的串有 4 个
    生产者、1 个分支消费者、且进了模型可见文本，拆它是另一次有意变更。
    """

    registry = _registry()
    sink = RecordingSink()
    scope = _scope(registry, sink)

    with pytest.raises(UnknownResearchTool, match="能力未授权：memory_lookup"):
        registry.execute(
            "memory_lookup",
            {"query": "x"},
            context=_context(),
            step_id="s-1",
            scope=scope,
            tool_call_id="call-9",
        )

    payload = sink.payload(TOOL_ERROR)
    assert payload["stage"] == "authorize"
    assert payload["capability"] == "memory_lookup"
    assert "能力未授权" in payload["reason"]
    assert payload["tool_call_id"] == "call-9"


def test_runner_failure_emits_error_and_still_propagates() -> None:
    """只观测，不改变传播——吞掉异常就是把失败静默成空结果。"""

    registry = _registry(_boom_runner)
    sink = RecordingSink()
    scope = _scope(registry, sink)

    with pytest.raises(RuntimeError, match="runner 炸了"):
        registry.execute(
            "market_data",
            {"query": "上证"},
            context=_context(),
            step_id="s-1",
            scope=scope,
        )

    payload = sink.payload(TOOL_ERROR)
    assert payload["stage"] == "execute"
    assert payload["error_type"] == "RuntimeError"
    assert "runner 炸了" in payload["reason"]


def test_scope_without_sink_records_but_emits_nothing() -> None:
    """没挂 sink 时事件静默丢弃，但登记照做——事件是可观测性，登记是事实。"""

    registry = _registry()
    scope = _scope(registry, sink=None)
    registry.execute(
        "market_data",
        {"query": "上证"},
        context=_context(),
        step_id="s-1",
        scope=scope,
    )
    assert scope.dump()["invoked_tools"] == ["market_data"]
    assert scope.dump()["event_sink_attached"] is False


# ── sink 故障不得改变主路径 ────────────────────────────────────────────


class ExplodingSink:
    def emit(self, kind: str, payload: dict) -> None:
        raise RuntimeError("sink 挂了")


def test_sink_failure_does_not_rewrite_error_contract() -> None:
    """authorize 拒绝路径上，sink 异常不得顶替 UnknownResearchTool。"""

    registry = _registry()
    scope = _scope(registry, ExplodingSink())

    with pytest.raises(UnknownResearchTool, match="能力未授权：memory_lookup"):
        registry.execute(
            "memory_lookup",
            {"query": "x"},
            context=_context(),
            step_id="s-1",
            scope=scope,
        )

    assert scope.dump()["event_sink_failures"] == 1


def test_sink_failure_does_not_fail_a_successful_execution() -> None:
    """TOOL_RESULT 发在 runner 成功之后——sink 异常不得把成功改判成失败。"""

    registry = _registry()
    scope = _scope(registry, ExplodingSink())

    observation = registry.execute(
        "market_data",
        {"query": "上证"},
        context=_context(),
        step_id="s-1",
        scope=scope,
    )

    assert observation.tool == "market_data"
    dumped = scope.dump()
    assert dumped["event_sink_attached"] is True
    # 挂上了不等于送到了——收据必须说实话
    assert dumped["event_sink_failures"] == 2
    assert dumped["event_sink_failed_kinds"] == [TOOL_PRE_EXECUTE, TOOL_RESULT]


# ── 批次预筛：压扁真正发生的地方 ───────────────────────────────────────


def test_batch_prefilter_emits_distinction_where_flattening_happens() -> None:
    """生产批次流在 registry.execute **之前**就 continue 了。

    区分事件只发在 execute 内部的话，「诊断拿到了区分」就只在测试里成立，
    真实批次一条都收不到——这是本步最容易自欺的一处。
    """

    from intelligence.runtime.episode_tool_batch import ToolBatchExecutor
    from intelligence.services.agent_runtime import ModelToolCall

    registry = _registry()
    sink = RecordingSink()
    scope = _scope(registry, sink)

    result = ToolBatchExecutor(scope=scope).execute(
        (
            ModelToolCall(call_id="c-1", name="memory_lookup", arguments={"query": "x"}),
            ModelToolCall(call_id="c-2", name="no_such_tool", arguments={"query": "y"}),
        ),
        registry=registry,
        context=_context(),
        remaining_slots=4,
    )

    # wire 上仍是压扁的那个串——错误契约没动
    assert [item.error for item in result.items] == [
        "unknown_or_unauthorized_tool",
        "unknown_or_unauthorized_tool",
    ]

    # 事件里分得开
    by_call = {
        payload["tool_call_id"]: payload
        for kind, payload in sink.events
        if kind == TOOL_ERROR
    }
    assert by_call["c-1"]["capability"] == "memory_lookup"
    assert "能力未授权" in by_call["c-1"]["reason"]
    assert by_call["c-2"]["capability"] is None
    assert by_call["c-2"]["reason"] == "工具未注册"


# ── 生产链路真的构造 Scope 了（第 4 步认领项之一）─────────────────────


def test_agent_episode_run_constructs_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """机制不再休眠：真实驱动 run()，批次会话拿到的必须是入口构造的 Scope。

    第 3 步把接缝接到执行路径上，但生产链路一直没人构造 Scope，于是事件、登记、
    dump 在生产里都不发生——而所有测试仍然全绿，因为没有任何断言在问「生产里
    真的建了吗」。这条就是那个断言：驱动一次最小 Episode（一轮工具调用 +
    一轮 finish），在 new_session 处捕获 scope 实参，断言身份沿用仓内既有约定、
    注册表就是传给 run() 的同一个对象、且经真实路径执行过的调用登记进了收据。

    此前的版本是 inspect.getsource 抓源码子串：run() 从未被调用，
    「context.contract.task_id」被 run() 里注释的字面串满足着，抽个 helper
    就会假报警——本仓明令禁止的假测试形状，故重写为经真实入口的行为断言。
    """

    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.episode_tool_batch import ToolBatchExecutor
    from intelligence.tests.test_agent_episode import (
        ScriptedModel,
        _context as _episode_context,
        _finish_turn,
        _frame,
        _market_registry,
        _successful_runner,
        _tool_turn,
    )

    captured: list[EpisodeScope | None] = []
    real_new_session = ToolBatchExecutor.new_session

    def capturing_new_session(self, *, scope=None):
        captured.append(scope)
        return real_new_session(self, scope=scope)

    # spy 本身不是问题，问题只会出在不经真入口。这里 run() 是真的在跑：
    # 模型轮次、工具执行、finish 全走生产代码，spy 只把 scope 实参拿出来看，
    # 然后原样委托回真 new_session，不改变任何行为。
    monkeypatch.setattr(ToolBatchExecutor, "new_session", capturing_new_session)

    frame = _frame()
    context = _episode_context(frame)
    registry = _market_registry(_successful_runner)
    outcome = ContinuousAgentEpisode(
        ScriptedModel([_tool_turn("A股 最新行情"), _finish_turn()])
    ).run(task_frame=frame, context=context, registry=registry)

    assert outcome.status == "completed"
    assert outcome.usage.tool_calls == 1
    [scope] = captured  # 一次 run() 恰好开一个批次会话
    assert isinstance(scope, EpisodeScope)
    # 身份是仓内既有约定（contract.task_id），不是新发明的第二种 Episode 身份
    assert scope.episode_id == context.contract.task_id
    # 注册表是 run() 实际用的那一份：传入的每个 spec 原对象不经复制或替换，只多出
    # episode 期才绑得出 runner 的 derived_calculation（capability-amplification §3.4，
    # 与 sub_research 同一条 with_specs 路）；传入的注册表本身不被改动。
    assert scope.registry is not registry
    for name in registry.names():
        assert scope.registry.resolve(name) is registry.resolve(name)
    assert set(scope.registry.names()) == {*registry.names(), "derived_calculation"}
    assert "derived_calculation" not in registry.names()
    # Scope 不只是被构造了，还真的活在执行路径里：登记经真实入口发生
    assert scope.dump()["invoked_tools"] == ["market_data"]
