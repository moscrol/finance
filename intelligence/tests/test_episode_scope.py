"""EpisodeScope / ToolPipeline 接缝的测试。

对应 spec §7.1、§7.2 的验收条款；实施顺序第 2 步只建接缝，因此这里验的是
**接缝本身的不变量**，不验接线（接线是第 3 步）。
"""

from __future__ import annotations

import pytest

from intelligence.services import agent_research
from intelligence.services.episode_scope import (
    Authorization,
    EpisodeScope,
    EventSink,
    ToolPipeline,
    ToolReachability,
    ToolRequest,
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
    ResearchToolRegistry,
    ToolSpec,
)


def _runner(
    value: str,
    context: agent_research.AgentToolContext,
) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
    return ([], f"ran {value}", ProviderTrace(provider="test", model="test"))


def _registry() -> ResearchToolRegistry:
    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="行情",
                cost="low",
                freshness="current",
                runner=_runner,
            ),
            ToolSpec(
                name="memory_lookup",
                capability="memory_lookup",
                description="记忆",
                cost="low",
                freshness="stale",
                runner=_runner,
            ),
        )
    )


def _context(allowed: tuple[str, ...] = ("market_data",)) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="scope-test",
        question="测试问题",
        subject=None,
        subject_kind=None,
        question_type="quick_fact",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", allowed, True),
        ),
        allowed_capabilities=allowed,
        task_frame_hash="hash-abc",
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(2.0),
        policy=ResearchPolicy("quick", 4, 2.0, 0.0),
        trace_parent_id="scope-test",
    )


def _scope(**kwargs: object) -> EpisodeScope:
    defaults: dict[str, object] = {
        "episode_id": "ep-1",
        "user_id": "u-1",
        "context": _context(),
        "registry": _registry(),
    }
    defaults.update(kwargs)
    return EpisodeScope(**defaults)  # type: ignore[arg-type]


# ── Scope 的派生视图 ────────────────────────────────────────────────────


def test_scope_requires_episode_id() -> None:
    with pytest.raises(ValueError, match="episode_id"):
        _scope(episode_id="  ")


def test_allowed_tools_follow_contract_capabilities() -> None:
    scope = _scope()
    assert scope.allowed_tools() == ("market_data",)
    assert scope.allowed_capabilities == ("market_data",)
    assert scope.task_frame_hash == "hash-abc"


def test_model_visible_set_equals_authorized_set() -> None:
    """「授权了但模型看不见」这条不变量被钉在 Scope 上。

    将来谁给模型单独加一层过滤，这条会立刻红——那正是想要的效果。
    """

    scope = _scope(context=_context(allowed=("market_data", "memory_lookup")))
    visible = {
        item["function"]["name"] for item in scope.model_visible_definitions()
    }
    assert visible == set(scope.allowed_tools())


def test_authorize_distinguishes_unregistered_from_unauthorized() -> None:
    """未注册 与 未授权 必须能分开——registry.execute 当前把两者压成同一个异常。"""

    scope = _scope()

    granted = scope.authorize("market_data")
    assert granted.allowed is True
    assert granted.capability == "market_data"
    assert granted.reason == ""

    unauthorized = scope.authorize("memory_lookup")
    assert unauthorized.allowed is False
    assert unauthorized.capability == "memory_lookup"
    assert "能力未授权" in unauthorized.reason

    unknown = scope.authorize("no_such_tool")
    assert unknown.allowed is False
    assert unknown.capability == ""
    assert unknown.reason == "工具未注册"


def test_authorization_rejects_incoherent_values() -> None:
    with pytest.raises(ValueError):
        Authorization(allowed=True, tool="t", capability="c", reason="不该有")
    with pytest.raises(ValueError):
        Authorization(allowed=False, tool="t", capability="c", reason="   ")


# ── 可达性四段 ─────────────────────────────────────────────────────────


def test_reachability_reports_stage_where_chain_breaks() -> None:
    scope = _scope(invoked_tools=frozenset({"market_data"}))
    rows = {row.name: row for row in scope.reachability()}

    assert rows["market_data"].broken_at() is None
    assert rows["memory_lookup"].broken_at() == "not_authorized"


def test_reachability_marks_authorized_but_uninvoked() -> None:
    """授权且可见、但模型没选它——这不是故障，只是事实。"""

    scope = _scope()
    rows = {row.name: row for row in scope.reachability()}
    assert rows["market_data"].broken_at() == "not_invoked"


def test_broken_at_is_ordered_by_stage() -> None:
    row = ToolReachability(
        name="t",
        capability="c",
        defined=False,
        authorized=True,
        model_visible=True,
        invoked=True,
    )
    assert row.broken_at() == "not_defined"


# ── dump() 收据 ────────────────────────────────────────────────────────


def test_dump_reports_unattached_ledger_and_sink() -> None:
    """账本/事件出口没挂上时，证据和事件会静默去不到任何地方。

    这是最难发现的一类故障，所以 dump 必须显式回答挂没挂，而不是只在挂上时才提。
    """

    dumped = _scope().dump()
    assert dumped["evidence_ledger_attached"] is False
    assert dumped["event_sink_attached"] is False


def test_dump_lists_every_registered_tool_with_all_four_stages() -> None:
    dumped = _scope(invoked_tools=frozenset({"market_data"})).dump()
    tools = {row["name"]: row for row in dumped["tools"]}

    assert set(tools) == {"market_data", "memory_lookup"}
    for row in tools.values():
        assert set(row) >= {
            "defined",
            "authorized",
            "model_visible",
            "invoked",
            "broken_at",
        }

    assert tools["market_data"]["invoked"] is True
    assert tools["memory_lookup"]["authorized"] is False
    assert dumped["invoked_tools"] == ["market_data"]
    assert dumped["episode_id"] == "ep-1"
    assert dumped["task_frame_hash"] == "hash-abc"


def test_dump_carries_information_cutoff() -> None:
    dumped = _scope().dump()
    cutoff = dumped["information_cutoff"]
    assert isinstance(cutoff, dict)
    assert set(cutoff) == {"as_of_date", "source"}


# ── Protocol 形状 ──────────────────────────────────────────────────────


def test_event_sink_protocol_is_structural() -> None:
    class Sink:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def emit(self, kind: str, payload: dict) -> None:
            self.seen.append(kind)

    sink = Sink()
    assert isinstance(sink, EventSink)
    scope = _scope(event_sink=sink)
    assert scope.dump()["event_sink_attached"] is True


def test_tool_pipeline_protocol_rejects_partial_implementation() -> None:
    """少一个阶段就不算 ToolPipeline——阶段是完整的一串，不能挑着实现。"""

    class Partial:
        def prepare(self, request: ToolRequest, scope: EpisodeScope) -> None: ...

    assert not isinstance(Partial(), ToolPipeline)


def test_tool_request_carries_tool_call_id() -> None:
    """tool_call_id 贯穿全流水线，是 Trace/UI/评测三者对账的锚点。"""

    request = ToolRequest(
        tool="market_data", arguments={"query": "上证"}, tool_call_id="call-1"
    )
    assert request.tool_call_id == "call-1"
