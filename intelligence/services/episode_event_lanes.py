"""Durable / Live 两条事件车道：**单一分类表** + Live 车道的出口。

来源：``docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md``
§7.4（Durable Event 与 Projection），实施顺序第 5 步；台账
``docs/handoffs/2026-08-15-dsh-absorption-p0-execution-handoff.md`` §10.3–§10.5。

--------------------------------------------------------------------------
两条车道分别是什么
--------------------------------------------------------------------------

- **Durable**：进 ``_EpisodeLedger.events``。它是**重放日志**——
  ``episode_session`` 用「事件只增、前缀逐条相等」校验 resume，
  ``openai_agents_runtime`` 按它续号与切片，评测 artifact 与 Trace 从它派生。
  它同时是**对账权威**：金融字段与发布判据只认这一侧。
- **Live**：只走实时出口（进度/UI），**不进 ``ledger.events``、不占用 durable
  sequence**。Live 事件自带一个独立的编号空间，payload 里打 ``lane="live"``。

--------------------------------------------------------------------------
为什么工具阶段事件归 Live（2026-08-15 检阅裁定）
--------------------------------------------------------------------------

``tool/pre_execute`` / ``tool/result`` / ``tool/error`` 携带的是「runner 真被调起」
（被去重或预算挡掉的不发），而 durable 侧已有 ``tool_request`` / ``tool_result`` /
``tool_error`` 这对「派发与回收」。把阶段事件也放进 Durable 会有两笔代价：

1. **双账**——同一件事两套工具事件，违反「不造第二事实源」；除非同轮把 durable
   侧换掉，那是一次对外契约翻转（adapter 的 ``events`` 数组、trace normalizer、
   评测 artifact 都吃它），必须单独开轮。
2. **重放日志变长**——每次工具调用多 2–3 条，按并发批次成倍放大 resume 前缀。

裁定还给了一条方向性依据：**Live → Durable 将来是加法，Durable → Live 是对重放
消费者的破坏**。所以先归 Live，需要时再单向升级。

裁定的三个条件（本模块逐条兑现）：① durable 侧保持对账权威，阶段事件不得成为任何
金融字段或发布判据的唯一载体；② 分类落**这一张**表并用测试钉住，Live 不进
``ledger.events``、不携带 durable sequence；③ D3 只覆盖 ``tool/*`` 三事件。
``branch_*`` 由 D6（台账 §5.3-3）裁定归 Durable：它们承载证据来源、分支预算
消耗和成对身份，按 spec §7.4 不得在 Projection 丢失；归 Live 会让重放日志缺
分支，配对对账也无处可依。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from threading import RLock
from typing import Literal

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.research_tool_registry import (
    TOOL_ERROR,
    TOOL_PRE_EXECUTE,
    TOOL_RESULT,
)


EventLane = Literal["durable", "live"]


# 凡是能进 ``AgentOutcome.events``、再被 ``project_durable_events`` 投影的
# kind，都必须在这张表里。投影挂在 ``ContinuousTurnAdapter`` 上，三条 runtime
# 共用（``agent_episode`` / ``openai_agents_runtime`` / ``codex_headless`` +
# gateway），不是只覆盖 ``_EpisodeLedger.add``。
#
# 完整性由 ``test_durable_kind_table_matches_every_runtime_emitter`` 守住：
# 发射点漏登记会红，表里出现假 kind（payload 键冒充事件种类）也会红。
DURABLE_EVENT_KINDS: frozenset[str] = frozenset(
    {
        "task",
        # 模型可见即已落账（终态稿 §6.1 P0）：三种承载「模型看到的字」的事件。
        # prompt_assembled = system + 首轮 user；model_input = 每条 user 角色注入；
        # tool_budget_state = 底座覆写最后一条 tool 消息时的整段 content。
        # 归 durable 是必然：它们是重放消费者重建模型历史的唯一来源。
        "prompt_assembled",
        "model_input",
        "tool_budget_state",
        # 效果三明治（终态稿 §6.3 P2）：模型请求前的意图，预留 turn_id 给 model_turn /
        # model_error 结算复用。工具侧的意图沿用既有 tool_request（挪到派发前）。
        "model_intent",
        "plan",
        "mode_decision",
        "prefetch",
        "tool_menu",
        "model_turn",
        "model_error",
        "tool_request",
        "tool_result",
        "tool_error",
        "tool_closed",
        "branch_started",
        "branch_completed",
        "branch_failed",
        "branch_tool",
        "repair_goal",
        "repair_reentry",
        "repair_model_retry",
        "invalid_action",
        "finalization",
        "finalization_recovery_started",
        "finalization_recovery_outcome",
        "runtime_result",
        "finish",
        "configure",
        "root_budget_overdraft",
    }
)

# 工具流水线的三个阶段事件（常量定义在 ``research_tool_registry``，此处不抄字面量）。
LIVE_EVENT_KINDS: frozenset[str] = frozenset(
    {TOOL_PRE_EXECUTE, TOOL_RESULT, TOOL_ERROR}
)


def lane_for(kind: str) -> EventLane:
    """返回事件 kind 属于哪条车道；未登记的 kind **抛错**。

    fail closed 是有意的：这张表是分类的唯一事实源，一个没登记的 kind 说明
    发射点和分类表已经漂了。让它在发射处炸出来，比让它默默选一条车道好——
    后者要么污染重放日志，要么让事件人间蒸发，两种都得等到很久以后才发现。

    调用方只有 Live 出口（见 ``LiveEventSink``），而它挂在
    ``EpisodeScope.emit`` 的兜底之内：抛出的错会被吞掉并计进
    ``dump()["event_sink_failures"]``，**不影响主路径**。
    """

    normalized = str(kind or "").strip()
    if normalized in LIVE_EVENT_KINDS:
        return "live"
    if normalized in DURABLE_EVENT_KINDS:
        return "durable"
    raise ValueError(f"未登记的事件 kind，先在 episode_event_lanes 里定车道: {kind!r}")


class LiveEventSink:
    """Live 车道的出口：送到实时 sink，**绝不碰 durable 事件流**。

    实现 ``EpisodeScope.EventSink`` 协议。三条性质是裁定条件②的兑现：

    1. **不进 ``ledger.events``**——本类根本拿不到 ledger，只有一个发布回调；
    2. **不携带 durable sequence**——自带独立计数器，payload 打 ``lane="live"``，
       消费者据此知道这个序号与 durable 的序号不在一个编号空间里；
    3. **拒收 durable kind**——``lane_for`` 判不出 live 就抛，防止有人把重放日志
       该有的事件从这条旁路发出去（那会让 durable 流缺事件且无人察觉）。

    计数器上锁：发射点在 8 worker 的共享工具线程池里（见台账 §10.2）。这与
    ``_EpisodeLedger`` 那把锁是同一个理由，但**保护的是不同的状态**——那把锁保
    durable 列表，保不到这里。
    """

    def __init__(self, publish: Callable[[EpisodeEvent], None]) -> None:
        self._publish = publish
        self._lock = RLock()
        self._sequence = 0

    @property
    def published_count(self) -> int:
        """已发出的 Live 事件数（收据用，不参与控制流）。"""

        with self._lock:
            return self._sequence

    def emit(self, kind: str, payload: Mapping[str, object]) -> None:
        lane = lane_for(kind)
        if lane != "live":
            raise ValueError(f"durable 事件不得走 Live 出口: {kind!r}")
        # 与 ``_EpisodeLedger.add`` 同形的临界区：**读号 → 建事件 → 写回**，整段在
        # 锁内。两点都是有意的：
        #
        # 1. 不锁的话「读 → 写回」之间被切走，两个线程会拿到同一个号；
        # 2. 写回放在构造**之后**——payload 不可 JSON 化时 ``EpisodeEvent`` 会抛，
        #    此时序号不该被消耗掉，否则 Live 编号会留下一个没人解释的空洞。
        with self._lock:
            sequence = self._sequence + 1
            event = EpisodeEvent(sequence, kind, {**dict(payload), "lane": "live"})
            self._sequence = sequence
        # 发布留在锁外：``_publish`` 是外部回调，持锁调它既是死锁源，也会把工具
        # 执行的同步路径卡住（``EventSink`` 协议明写 emit 必须快）。
        self._publish(event)


__all__ = [
    "DURABLE_EVENT_KINDS",
    "EventLane",
    "LIVE_EVENT_KINDS",
    "LiveEventSink",
    "lane_for",
]
