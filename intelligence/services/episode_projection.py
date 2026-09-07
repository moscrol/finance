"""对外 artifact 的事件投影：**唯一口径**。

来源：spec §7.4「Trace、Workbench、评测和 API 响应都从 Projection 生成」，
实施顺序第 5 步第 3 条；台账 §10.4 的 D5。

--------------------------------------------------------------------------
为什么要收口
--------------------------------------------------------------------------

``artifact["events"]`` 这一个数组有**五个下游**：
``conversation_orchestrator``、``api/stream_events``、
``eval/runtime_backend_benchmark``、``eval/normalize_harness_trace``、
``scripts/dump_episode_receipts``。而生产它的只有 ``continuous_turn_adapter``
里的一行内联列表推导。一个五消费者的对外契约挂在一行推导上，谁改都不知道自己
在改契约——收口成具名函数是为了让这个边界有名字、有不变量、有测试。

--------------------------------------------------------------------------
不变量：只投 Durable
--------------------------------------------------------------------------

Live 车道（``tool/*`` 阶段事件，见 ``episode_event_lanes``）**不进这个数组**。
今天它本来就进不来（Live 事件根本不写 ``ledger.events``），所以本模块上线时输出
与此前逐字节一致；钉住它是为了**将来**——第 4 条要动事件出口，那时"Live 悄悄漏进
重放/评测口径"是最容易发生且最难发现的一种回归。

--------------------------------------------------------------------------
两个边界的 fail 策略**故意不同**
--------------------------------------------------------------------------

``lane_for`` 在**发射**边界对未登记 kind fail closed（抛错）：那里抛错什么都不丢，
``EpisodeScope.emit`` 兜住并计进 ``event_sink_failures``，主路径不受影响。

本模块在 **artifact** 边界反过来：未登记的 kind **保留**并记进
``unregistered_kinds``。因为这里已经是研究做完之后，抛错等于把一次完成的研究
连同它的证据一起丢掉——为了一个分类表没跟上的 kind 付这个代价是荒谬的。
**但也不静默**：异常都装进返回值，由调用方写进 artifact，收据不说谎。

--------------------------------------------------------------------------
子研究分支的成对性对账（台账 §5.3-1）
--------------------------------------------------------------------------

每条 ``branch_started`` 必须对上一条 ``branch_completed`` / ``branch_failed``。
今天它靠 ``_run_sub_research`` 末尾那个「未执行兜底循环」成立——**但那是实现细节，
不是被断言的性质**：兜底循环在将来的事件出口合流改写里一旦丢掉，成对性会静默失效，
而所有测试都还是绿的。所以这里把它变成投影层的一条对账，两个方向都查：
``unpaired_branch_ids``（起了没终态）与 ``orphan_branch_terminals``（有终态没起）。

配套的另一半在发射侧：``branch_completed`` / ``branch_failed`` 的 payload 带
``error`` 字段（台账 §5.3-2）。没有它，「单分支取消」与「worker 异常失败」在事件流
里完全同形，"cancelled 可区分"这条要求在这一层根本判不出来。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_event_lanes import lane_for
from intelligence.services.episode_messages import (
    MODEL_VISIBLE_TEXT_FIELDS,
    sha256_text,
)


_BRANCH_START_KINDS = frozenset({"branch_started"})
_BRANCH_TERMINAL_KINDS = frozenset({"branch_completed", "branch_failed"})


def _redact_model_visible_text(event_dict: dict[str, object]) -> dict[str, object]:
    """把模型可见正文换成 ``<field>_sha256`` + ``<field>_chars``。

    对外 artifact 的纪律是「不带 prompt 正文」（``test_conversation_orchestrator`` 对
    ``configure`` 快照的断言），P0 往 durable 流里加了正文字段，这里是它们出仓前
    唯一的闸。hash 留下是为了事后仍能对账「system 变过没有」「这轮注入是哪一段」。
    """

    kind = str(event_dict.get("kind") or "")
    payload = event_dict.get("payload")
    if not isinstance(payload, dict):
        return event_dict
    fields = [name for k, name in MODEL_VISIBLE_TEXT_FIELDS if k == kind and name in payload]
    if not fields:
        return event_dict
    redacted = dict(payload)
    for name in fields:
        text = str(redacted.pop(name))
        redacted.setdefault(f"{name}_sha256", sha256_text(text))
        redacted.setdefault(f"{name}_chars", len(text))
    return {**event_dict, "payload": redacted}


def _branch_id_of(event: EpisodeEvent) -> str:
    return str(event.payload.get("branch_id") or "")


@dataclass(frozen=True)
class DurableEventProjection:
    """投影结果 + 投影过程中发现的异常（两者一起返回，避免异常无处可去）。"""

    events: tuple[dict[str, object], ...] = ()
    # 被挡在 artifact 之外的 Live kind（去重、保序）。非空即说明有人把 Live 事件
    # 写进了 durable 事件流——那是接线 bug，不是本模块能修的，但必须看得见。
    dropped_live_kinds: tuple[str, ...] = ()
    # 两张车道表都不认识的 kind（去重、保序）。事件**已保留**在 events 里。
    unregistered_kinds: tuple[str, ...] = ()
    # 发了 ``branch_started`` 却没有终态事件的 branch_id（保序）。
    unpaired_branch_ids: tuple[str, ...] = ()
    # 有终态却没见过 ``branch_started`` 的 branch_id（保序）。
    orphan_branch_terminals: tuple[str, ...] = ()

    @property
    def has_anomalies(self) -> bool:
        return bool(
            self.dropped_live_kinds
            or self.unregistered_kinds
            or self.unpaired_branch_ids
            or self.orphan_branch_terminals
        )

    def anomalies_to_dict(self) -> dict[str, list[str]]:
        payload: dict[str, list[str]] = {}
        if self.dropped_live_kinds:
            payload["dropped_live_kinds"] = list(self.dropped_live_kinds)
        if self.unregistered_kinds:
            payload["unregistered_kinds"] = list(self.unregistered_kinds)
        if self.unpaired_branch_ids:
            payload["unpaired_branch_ids"] = list(self.unpaired_branch_ids)
        if self.orphan_branch_terminals:
            payload["orphan_branch_terminals"] = list(self.orphan_branch_terminals)
        return payload


def project_durable_events(
    events: Iterable[EpisodeEvent],
    *,
    include_model_visible_text: bool = False,
) -> DurableEventProjection:
    """把 Episode 事件投影成对外 artifact 的 ``events`` 数组。

    形状就是 ``EpisodeEvent.to_dict()`` 逐字段原样——**这里不做裁剪也不改名**：
    五个下游按现有字段读，投影层擅自改形状等于一次无声的契约变更。本函数做两个判断：
    车道归属，以及（默认）把模型可见正文换成 hash——见 ``_redact_model_visible_text``。
    ``include_model_visible_text=True`` 只给私有、不出仓的读者（P2 的 durable store）。
    """

    kept: list[dict[str, object]] = []
    dropped: dict[str, None] = {}
    unregistered: dict[str, None] = {}
    started: dict[str, None] = {}
    terminated: dict[str, None] = {}
    for event in events:
        try:
            lane = lane_for(event.kind)
        except ValueError:
            unregistered[event.kind] = None
            kept.append(event.to_dict())
            continue
        if lane == "live":
            dropped[event.kind] = None
            continue
        if event.kind in _BRANCH_START_KINDS:
            started[_branch_id_of(event)] = None
        elif event.kind in _BRANCH_TERMINAL_KINDS:
            terminated[_branch_id_of(event)] = None
        row = event.to_dict()
        if not include_model_visible_text:
            row = _redact_model_visible_text(row)
        kept.append(row)
    return DurableEventProjection(
        events=tuple(kept),
        dropped_live_kinds=tuple(dropped),
        unregistered_kinds=tuple(unregistered),
        unpaired_branch_ids=tuple(
            branch_id for branch_id in started if branch_id not in terminated
        ),
        orphan_branch_terminals=tuple(
            branch_id for branch_id in terminated if branch_id not in started
        ),
    )


__all__ = ["DurableEventProjection", "project_durable_events"]
