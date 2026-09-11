"""INV-R5 收件箱：外部输入经且仅经收件箱；入箱 / 认领 / 丢弃三事实 durable。

终态稿 §6.4 P3 验收：INV-R5；竞态「steer 到达 vs 模型停下」两序；``derive_messages`` 仍逐字节
相等（收件箱消息是 durable 事件，天然进派生——conftest 强制严格派生，任何不等在请求前就抛）。
非适用臂只验「确实不在场」：事件流里没有 inbox_*。
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode, _EpisodeLedger
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.runtime.sub_research import SubResearchResult
from intelligence.services.agent_runtime import EpisodeEvent, ModelTurn
from intelligence.services.episode_inbox import Inbox
from intelligence.services.episode_messages import EpisodeMessage, user_message
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    ScenarioProbe,
    ScriptedModelClient,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
)

INV = "INV-R5"
_INBOX_KINDS = {"inbox_inserted", "inbox_claimed", "inbox_discarded"}


class _HookedModel:
    """脚本化 client 外面包一层：记录每次请求的线格式消息；第 N 次请求**进行中**可触发钩子
    （模拟「话在模型思考时到达」）。"""

    def __init__(self, inner: ScriptedModelClient) -> None:
        self._inner = inner
        self.requests: list[list[dict[str, object]]] = []
        self.on_call: dict[int, Callable[[], None]] = {}

    def complete(self, *, messages, tools, timeout) -> ModelTurn:
        self.requests.append([dict(item) for item in messages])
        hook = self.on_call.get(len(self.requests))
        if hook is not None:
            hook()
        return self._inner.complete(messages=messages, tools=tools, timeout=timeout)


def _user_texts(request: list[dict[str, object]]) -> list[str]:
    return [str(item.get("content")) for item in request if item.get("role") == "user"]


def _kinds(events: tuple[EpisodeEvent, ...], *names: str) -> list[str]:
    wanted = set(names)
    return [event.kind for event in events if event.kind in wanted]


def _inbox_events(events: tuple[EpisodeEvent, ...], kind: str) -> list[EpisodeEvent]:
    return [event for event in events if event.kind == kind]


def _runtime(turns: tuple[ScriptedTurn, ...], probe: ScenarioProbe, **kwargs) -> tuple[GLMAgentRuntime, _HookedModel]:
    model = _HookedModel(ScriptedModelClient(list(turns), probe))
    runtime = GLMAgentRuntime(client=model, **kwargs)
    return runtime, model


def test_steer_sent_during_a_turn_is_claimed_before_the_next_request() -> None:
    """next_step：第一次请求时递进来，工具跑完、第二次请求前被认领——模型在第二次请求里看到它。"""

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id="conf-inv-r5-steer")
    runtime, model = _runtime(
        (
            ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),)),
            ScriptedTurn(finish=completed_finish()),
        ),
        probe,
    )
    receipts = []
    model.on_call[1] = lambda: receipts.append(runtime.steer("先看北向资金", target="next_step"))

    outcome = runtime.run(task_frame=frame, context=context, registry=make_registry(probe))

    assert outcome.status == "completed"
    assert receipts and receipts[0].accepted and receipts[0].message_id == "inbox-1"
    assert len(model.requests) == 2
    assert "先看北向资金" not in _user_texts(model.requests[0])
    # 第二次请求：工具结果之后、紧挨模型请求前的最后一条 user 消息就是它。
    assert model.requests[1][-1] == {"role": "user", "content": "先看北向资金"}
    assert _kinds(outcome.events, *_INBOX_KINDS) == ["inbox_inserted", "inbox_claimed"]
    inserted = _inbox_events(outcome.events, "inbox_inserted")[0].payload
    assert inserted["source"] == "steer" and inserted["target"] == "next_step"
    # 认领在第二条 model_intent 之前——事件序说清「模型看到它时它已落账」。
    kinds = _kinds(outcome.events, "inbox_claimed", "model_intent", "model_turn")
    assert kinds == ["model_intent", "model_turn", "inbox_claimed", "model_intent", "model_turn"]
    # 收口之后递话：箱子已关，回执说 inbox_closed、账本不再长；不抛。
    late = runtime.steer("晚了")
    assert not late.accepted and late.reason == "inbox_closed"
    assert _kinds(outcome.events, *_INBOX_KINDS) == ["inbox_inserted", "inbox_claimed"]
    # 从没跑过的 episode：没有箱子可递。
    fresh = ContinuousAgentEpisode(_HookedModel(ScriptedModelClient([], probe)))
    assert fresh.steer("更早").reason == "no_active_episode"


@pytest.mark.parametrize("arrival", ["during_model_call", "after_model_stopped"])
def test_follow_up_when_the_model_stops_gives_it_another_turn_in_both_orders(arrival: str) -> None:
    """竞态「steer 到达 vs 模型停下」两序：话在模型思考时到（A）或模型已停下、loop 还没检查时到（B），
    两种历史都合法——都被认领恰一次，都让模型再跑一轮，都不丢。"""

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv-r5-followup-{arrival}")
    sends: list[object] = []
    model_turns_seen = {"n": 0}

    def event_sink(event: EpisodeEvent) -> None:
        # B 序：模型的终局（第二轮）已结算（model_turn 落账）、loop 尚未走到停机判定。
        if event.kind == "model_turn":
            model_turns_seen["n"] += 1
            if arrival == "after_model_stopped" and model_turns_seen["n"] == 2:
                sends.append(runtime.steer("再补一句资金面", target="next_turn"))

    # 轮 1 取证（终局要绑证据），轮 2 给终局——follow-up 在这一轮到，轮 3 再给终局。
    runtime, model = _runtime(
        (
            ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),)),
            ScriptedTurn(finish=completed_finish()),
            ScriptedTurn(finish=completed_finish()),
        ),
        probe,
        event_sink=event_sink,
    )
    if arrival == "during_model_call":
        model.on_call[2] = lambda: sends.append(runtime.steer("再补一句资金面", target="next_turn"))

    outcome = runtime.run(task_frame=frame, context=context, registry=make_registry(probe))

    assert outcome.status == "completed"
    assert len(sends) == 1 and sends[0].accepted  # type: ignore[attr-defined]
    assert len(model.requests) == 3, "有 follow-up 时模型必须再跑一轮"
    # 第三次请求里：模型自己的第一份终局留作 assistant，随后是 follow-up。
    roles = [item["role"] for item in model.requests[2][-2:]]
    assert roles == ["assistant", "user"]
    assert model.requests[2][-1]["content"] == "再补一句资金面"
    assert _kinds(outcome.events, *_INBOX_KINDS) == ["inbox_inserted", "inbox_claimed"]
    # 认领恰一次，且在第二次结算之后、第三次意图之前——两序都是这一个位置。
    kinds = _kinds(outcome.events, "inbox_claimed", "model_intent", "model_turn")
    assert kinds == [
        "model_intent", "model_turn",
        "model_intent", "model_turn", "inbox_claimed",
        "model_intent", "model_turn",
    ]


def test_cancelled_episode_discards_pending_messages_with_reason_cancelled() -> None:
    cancelled = {"flag": False}
    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id="conf-inv-r5-cancel")
    runtime, model = _runtime(
        (ScriptedTurn(finish=completed_finish()),),
        probe,
        is_cancelled=lambda: cancelled["flag"],
    )

    def arrive_then_cancel() -> None:
        runtime.steer("还没送到就取消了", target="next_turn")
        cancelled["flag"] = True

    model.on_call[1] = arrive_then_cancel

    outcome = runtime.run(task_frame=frame, context=context, registry=make_registry(probe))

    assert outcome.stop_reason == "cancelled"
    assert _kinds(outcome.events, *_INBOX_KINDS) == ["inbox_inserted", "inbox_discarded"]
    discarded = _inbox_events(outcome.events, "inbox_discarded")[0].payload
    assert discarded["reason"] == "cancelled" and discarded["message_id"] == "inbox-1"
    # 丢弃在 finish 之前落账：finish 之后没有未决的 inserted。
    kinds = [event.kind for event in outcome.events]
    assert kinds.index("inbox_discarded") < kinds.index("finish")
    assert len(model.requests) == 1


def test_follow_up_during_finalization_is_not_claimed_and_is_discarded_at_finish() -> None:
    """收口阶段不认领 next_turn：episode 正按预算关门，留到 finish 统一 episode_finished。"""

    probe = ScenarioProbe()
    frame = make_frame()
    # max_steps=1：一次工具调用后工具额度耗尽 → 收口合成那一问。
    context = make_context(frame, task_id="conf-inv-r5-finalizing", max_steps=1)
    runtime, model = _runtime(
        (
            ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),)),
            ScriptedTurn(finish=completed_finish()),
        ),
        probe,
    )
    model.on_call[2] = lambda: runtime.steer("收口时才到的追问", target="next_turn")

    outcome = runtime.run(task_frame=frame, context=context, registry=make_registry(probe))

    assert outcome.status == "completed"
    assert len(model.requests) == 2
    assert _kinds(outcome.events, *_INBOX_KINDS) == ["inbox_inserted", "inbox_discarded"]
    assert _inbox_events(outcome.events, "inbox_discarded")[0].payload["reason"] == "episode_finished"
    finalizations = [event for event in outcome.events if event.kind == "finalization"]
    assert finalizations, "场景应真的走到收口"


class _RejectingHarness(FinanceResearchHarness):
    def admit_inbox_message(self, message: EpisodeMessage) -> bool:
        return "买入" not in message.content


@pytest.mark.parametrize("rejecting", [False, True])
def test_harness_admission_has_teeth(rejecting: bool) -> None:
    """接缝有牙：换一个拒收实现，同一句话模型就看不到；默认实现放行。"""

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv-r5-teeth-{int(rejecting)}")
    model = _HookedModel(
        ScriptedModelClient(
            [
                ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),)),
                ScriptedTurn(finish=completed_finish()),
            ],
            probe,
        )
    )
    episode = ContinuousAgentEpisode(
        model, harness=_RejectingHarness() if rejecting else FinanceResearchHarness()
    )
    receipts = []
    model.on_call[1] = lambda: receipts.append(episode.steer("买入茅台", target="next_step"))

    outcome = episode.run(task_frame=frame, context=context, registry=make_registry(probe))

    assert outcome.status == "completed"
    seen = "买入茅台" in _user_texts(model.requests[1])
    if rejecting:
        assert not receipts[0].accepted and receipts[0].reason == "rejected_by_harness"
        assert not seen
        assert _kinds(outcome.events, *_INBOX_KINDS) == ["inbox_inserted", "inbox_discarded"]
        assert _inbox_events(outcome.events, "inbox_discarded")[0].payload["reason"] == "rejected_by_harness"
    else:
        assert receipts[0].accepted and seen
        assert _kinds(outcome.events, *_INBOX_KINDS) == ["inbox_inserted", "inbox_claimed"]


def test_finish_drains_the_box_before_the_finish_event_at_the_ledger_choke_point() -> None:
    """十个 return 点共用一个出口：``finish`` 落账前账本清箱，丢弃事件序号全在 finish 之前。"""

    ledger = _EpisodeLedger(make_frame())
    inbox = Inbox(ledger)
    ledger.inbox = inbox
    inbox.send(user_message("a", source="steer"), target="next_step")
    inbox.send(user_message("b", source="steer"), target="next_turn")

    ledger.add("finish", {"status": "completed", "stop_reason": "model_finish"})

    kinds = [event.kind for event in ledger.events]
    assert kinds[-3:] == ["inbox_discarded", "inbox_discarded", "finish"]
    assert {e.payload["reason"] for e in ledger.events if e.kind == "inbox_discarded"} == {"episode_finished"}
    assert inbox.closed
    # 取消终局用取消原因。
    ledger2 = _EpisodeLedger(make_frame())
    inbox2 = Inbox(ledger2)
    ledger2.inbox = inbox2
    inbox2.send(user_message("a", source="steer"))
    ledger2.add("finish", {"status": "failed", "stop_reason": "cancelled"})
    assert [e.payload["reason"] for e in ledger2.events if e.kind == "inbox_discarded"] == ["cancelled"]


def test_sub_research_feedback_goes_through_the_inbox_not_model_input() -> None:
    """§6.4 第 3 条：子研究回灌 = ``inbox.send(target=next_step, source="sub_research")``；
    没有收件箱的账本（旧调用方）退回 ``model_input``，事件流与 P2 相同。"""

    probe = ScenarioProbe()
    episode = ContinuousAgentEpisode(_HookedModel(ScriptedModelClient([], probe)))
    result = SubResearchResult(branches=(), refused_reason="分支预算不足")

    ledger = _EpisodeLedger(make_frame())
    ledger.inbox = Inbox(ledger)
    messages: list[EpisodeMessage] = []
    episode._append_sub_research_message(messages=messages, ledger=ledger, result=result)
    assert messages == [], "回灌不再直接进 messages——等下一次请求前认领"
    inserted = _inbox_events(tuple(ledger.events), "inbox_inserted")
    assert len(inserted) == 1 and inserted[0].payload["source"] == "sub_research"
    assert inserted[0].payload["target"] == "next_step" and ledger.inbox.pending("next_step") == 1
    assert not [event for event in ledger.events if event.kind == "model_input"]
    claimed = ledger.inbox.claim("next_step")
    assert claimed[0].source == "sub_research" and "分支预算不足" in claimed[0].content

    plain = _EpisodeLedger(make_frame())
    plain_messages: list[EpisodeMessage] = []
    episode._append_sub_research_message(messages=plain_messages, ledger=plain, result=result)
    assert [event.kind for event in plain.events if event.kind.startswith(("model_input", "inbox"))] == ["model_input"]
    assert plain_messages[-1].source == "sub_research"


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_declared_arms_really_have_no_inbox_events(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv-r5-{backend.name}")
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
    inbox_kinds = _kinds(run.outcome.events, *_INBOX_KINDS)
    if verdict is Verdict.SUPPORTED:
        # 支持臂：没人递话时事件流也干净；输入面在场由 steer 回执证明（不是 no_active_episode 那种缺席）。
        assert inbox_kinds == []
        assert hasattr(run.runtime, "steer"), f"{backend.name} 声明支持 INV-R5 却没有 steer 入口"
    else:
        assert inbox_kinds == [], (
            f"{backend.name} 声明 {verdict.value} 却发了收件箱事件——先改 backends.py 声明表"
        )
        assert not hasattr(run.runtime, "steer")
