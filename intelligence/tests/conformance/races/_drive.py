"""竞态夹具共用件：带 oracle store 与取消信号的单步驱动，外加几把读事件流的尺子。

不叫 ``test_*``：pytest 不收集；八个竞态文件都从这里取同一套替身，改一处全表生效。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from intelligence.runtime.agent_episode import (
    ContinuousAgentEpisode,
    EpisodeDrive,
    StepPoint,
)
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import AgentOutcome, EpisodeEvent, ModelTurn
from intelligence.services.cancel_signal import CancelSignal
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.task_frame import TaskFrame
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
)
from intelligence.tests.conformance.oracle import WriteOrderOracle

MODEL_SETTLEMENTS = frozenset({"model_turn", "model_error"})
TOOL_SETTLEMENTS = frozenset({"tool_result", "tool_error"})

Hook = Callable[[], None]


class EffectAwareModel:
    """脚本化 client 外包一层：向 provider 开口那一刻告诉 oracle，并可在请求期间执行钩子。

    ``on_call[n]`` 在第 n 次（从 1 起）请求**进行中**执行——这就是「取消在模型请求在飞时到达」。
    """

    def __init__(self, inner: ScriptedModelClient, oracle: WriteOrderOracle) -> None:
        self._inner = inner
        self._oracle = oracle
        self.calls = 0
        self.on_call: dict[int, Hook] = {}

    def complete(self, *, messages, tools, timeout) -> ModelTurn:
        self.calls += 1
        self._oracle.effect_started("model")
        hook = self.on_call.get(self.calls)
        if hook is not None:
            hook()
        return self._inner.complete(messages=messages, tools=tools, timeout=timeout)


def effect_registry(
    oracle: WriteOrderOracle, *, during_tool: Hook | None = None
) -> ResearchToolRegistry:
    """一个授权工具；``during_tool`` 在 runner 执行期间被调（取消在工具执行中到达）。"""

    def runner(query: str, _context: AgentToolContext):
        oracle.effect_started("tool", key=query)
        if during_tool is not None:
            during_tool()
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


def tool_then_finish() -> list[ScriptedTurn]:
    """两轮脚本：一轮点工具、一轮给终局——够走完 planning → tools → finish 全路径。"""

    return [
        ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),)),
        ScriptedTurn(finish=completed_finish()),
    ]


@dataclass
class Rig:
    """一次竞态实验的全部把手。"""

    task_id: str
    oracle: WriteOrderOracle
    signal: CancelSignal
    model: EffectAwareModel
    probe: ScenarioProbe
    frame: TaskFrame
    context: ResearchRunContext
    registry: ResearchToolRegistry
    episode: ContinuousAgentEpisode
    drive: EpisodeDrive | None = None
    points: list[StepPoint] = field(default_factory=list)

    def start(self) -> EpisodeDrive:
        self.drive = self.episode.manual_drive(
            task_frame=self.frame, context=self.context, registry=self.registry
        )
        return self.drive

    def run_until(self, phase: str) -> StepPoint | None:
        assert self.drive is not None
        point = self.drive.run_until(phase)
        self.points = list(self.drive.steps)
        return point

    def finish(self) -> AgentOutcome:
        assert self.drive is not None
        outcome = self.drive.run_to_end()
        self.points = list(self.drive.steps)
        return outcome

    def stored_events(self) -> tuple[EpisodeEvent, ...]:
        events, _state = self.oracle.load(self.task_id)
        return events

    def stored_state(self):
        _events, state = self.oracle.load(self.task_id)
        return state


def build_rig(
    task_id: str,
    *,
    turns: Sequence[ScriptedTurn] | None = None,
    during_tool: Hook | None = None,
    store: WriteOrderOracle | None = None,
) -> Rig:
    oracle = store if store is not None else WriteOrderOracle()
    probe = ScenarioProbe()
    signal = CancelSignal()
    frame = make_frame()
    context = make_context(frame, task_id=task_id)
    model = EffectAwareModel(
        ScriptedModelClient(list(turns if turns is not None else tool_then_finish()), probe),
        oracle,
    )
    episode = ContinuousAgentEpisode(model, is_cancelled=signal, store=oracle)
    return Rig(
        task_id=task_id,
        oracle=oracle,
        signal=signal,
        model=model,
        probe=probe,
        frame=frame,
        context=context,
        registry=effect_registry(oracle, during_tool=during_tool),
        episode=episode,
    )


# ── 尺子 ───────────────────────────────────────────────────────────────


def kinds(events: Sequence[EpisodeEvent], *names: str) -> list[str]:
    wanted = set(names)
    return [event.kind for event in events if not wanted or event.kind in wanted]


def only(events: Sequence[EpisodeEvent], kind: str) -> list[EpisodeEvent]:
    return [event for event in events if event.kind == kind]


def finish_event(events: Sequence[EpisodeEvent]) -> EpisodeEvent:
    finishes = only(events, "finish")
    assert len(finishes) == 1, f"恰一条 finish，实际 {len(finishes)}"
    return finishes[0]


def model_pairs(events: Sequence[EpisodeEvent]) -> dict[str, tuple[int, int | None]]:
    """turn_id → (意图序号, 结算序号或 None)。"""

    pairs: dict[str, tuple[int, int | None]] = {}
    for event in events:
        turn_id = str(event.payload.get("turn_id") or "")
        if not turn_id:
            continue
        if event.kind == "model_intent":
            pairs[turn_id] = (event.sequence, None)
        elif event.kind in MODEL_SETTLEMENTS and turn_id in pairs:
            intent, _ = pairs[turn_id]
            pairs[turn_id] = (intent, event.sequence)
    return pairs


def tool_pairs(events: Sequence[EpisodeEvent]) -> dict[str, tuple[int, int | None]]:
    """call_id → (tool_request 序号, 结算序号或 None)。"""

    pairs: dict[str, tuple[int, int | None]] = {}
    for event in events:
        call_id = str(event.payload.get("call_id") or "")
        if not call_id:
            continue
        if event.kind == "tool_request":
            pairs[call_id] = (event.sequence, None)
        elif event.kind in TOOL_SETTLEMENTS and call_id in pairs:
            intent, _ = pairs[call_id]
            pairs[call_id] = (intent, event.sequence)
    return pairs


def assert_no_orphan_intents(events: Sequence[EpisodeEvent]) -> None:
    for turn_id, (intent, settlement) in model_pairs(events).items():
        assert settlement is not None and settlement > intent, f"模型意图 {turn_id} 无结算"
    for call_id, (intent, settlement) in tool_pairs(events).items():
        assert settlement is not None and settlement > intent, f"工具意图 {call_id} 无结算"


def assert_store_mirrors_outcome(rig: Rig, outcome: AgentOutcome) -> None:
    stored = rig.stored_events()
    assert [e.to_dict() for e in stored] == [e.to_dict() for e in outcome.events]
    state = rig.stored_state()
    assert state is not None and state.phase == "done"


__all__ = [
    "AUTHORIZED_TOOL",
    "EffectAwareModel",
    "MODEL_SETTLEMENTS",
    "Rig",
    "TOOL_SETTLEMENTS",
    "assert_no_orphan_intents",
    "assert_store_mirrors_outcome",
    "build_rig",
    "effect_registry",
    "finish_event",
    "kinds",
    "model_pairs",
    "only",
    "tool_pairs",
    "tool_then_finish",
]
