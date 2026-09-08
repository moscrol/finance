"""收件箱：外部输入进 episode 的唯一通道（INV-R5）。

来源：``docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`` §2 钦定词
「收件箱」、§3 INV-R5、§5 第 2 条接触点、§6.4 P3。形状来自 dsh ``Inbox``（``send(msg,
target=next-turn|next-step, wakeup)``，splice 落日志）与 pi ``getSteeringMessages`` /
``getFollowUpMessages``；三事实 durable 是本仓自己加的判据。

--------------------------------------------------------------------------
它替代的失败形状
--------------------------------------------------------------------------

此前 ``run()`` 之后没有外部输入面；loop 内部要给模型递话（子研究回灌、模式裁决）
就直接往 ``messages`` append。两处后果：

1. 外部（Workbench / CLI / 父 episode）想在研究中途递一句「换个方向」，没有门；
2. 「递了没递到」不可审计——消息进了列表就当送达，崩溃、取消、收口时丢在半路
   的话没有任何事实记录。

收件箱把「递话」拆成三个各自 durable 的事实：

- ``inbox_inserted``：话到了箱里（带正文，是模型可见正文的唯一落点）；
- ``inbox_claimed``：loop 把它从箱里取出、进了 ``messages``——**这一刻才模型可见**；
- ``inbox_discarded``：没送到模型就丢了，带 ``reason``（领域拒收 / 取消 / 收口）。

三事实齐了，任何一条消息的命运都能从事件流读出：``inserted`` 之后要么 ``claimed``
要么 ``discarded``，二者恰有其一；崩溃只可能留下「inserted 有、后两者无」这一种
不确定（与效果三明治同形）。

--------------------------------------------------------------------------
两个队列
--------------------------------------------------------------------------

- ``next_step``：下一次模型请求前送达（pi steering）。loop 在**每次**模型请求前
  ``claim("next_step")``，含收口合成那一问。
- ``next_turn``：模型停下（无工具调用、非收口）时送达（pi follow-up）。有话就
  不结束，再给模型一轮。收口阶段不认领——episode 正在按预算关门，收口后统一
  ``inbox_discarded{reason=episode_finished}``。

``wakeup`` 只记账不生效：本仓 loop 是同步驱动的，没有「空闲等输入」的状态可唤醒。
字段保留是为了与 dsh 形状对齐，将来 ``step()`` 拆出（P4）后才有意义。

--------------------------------------------------------------------------
领域接触点
--------------------------------------------------------------------------

``admit`` 是 ``ResearchHarness.admit_inbox_message`` 的接缝：领域决定这句话收不收
（例：拒收含个股买卖指令的 steer）。判定在 ``send`` 时做——发送方当场拿到
拒收回执，而不是等到下一次认领才发现被丢。拒收仍先落 ``inbox_inserted``（话确实
到过），再落 ``inbox_discarded{reason=rejected_by_harness}``。判定函数自己抛异常
按拒收处理（认不出就 fail closed），``detail`` 带异常类名。

发射点写字面量 kind（``"inbox_inserted"`` 等）而不用 ``episode_messages`` 里的常量：运行底座目录
（``gen_runtime_catalog`` / ``test_episode_event_lanes``）按 AST 扫字符串常量找发射文件，常量名
它看不见。派生侧（``derive_messages``）用常量。

线程模型：``send`` 可能来自另一个线程（将来的 API 端点 / 父 episode），``claim`` 来自
驱动线程。队列与计数器持本地锁；事件落账走 ``ledger.add``（它自己持锁、序号原子）。
``inbox_inserted`` 先落账再入队：崩溃只可能留下「账有、队列无」，而队列是派生物。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import threading
from typing import Literal

from intelligence.services.episode_messages import (
    EpisodeMessage,
    MessageLedger,
    sha256_text,
)

__all__ = [
    "INBOX_DISCARD_REASONS",
    "INBOX_TARGETS",
    "Inbox",
    "InboxDiscardReason",
    "InboxReceipt",
    "InboxTarget",
]

InboxTarget = Literal["next_turn", "next_step"]
INBOX_TARGETS: frozenset[str] = frozenset({"next_turn", "next_step"})

InboxDiscardReason = Literal["rejected_by_harness", "cancelled", "episode_finished"]
INBOX_DISCARD_REASONS: frozenset[str] = frozenset(
    {"rejected_by_harness", "cancelled", "episode_finished"}
)

# 送达后事件流里没有正文的事件也要能定位到消息：``message_id`` 在一个 episode 内唯一。
_MESSAGE_ID_PREFIX = "inbox-"


@dataclass(frozen=True)
class InboxReceipt:
    """``send`` 的回执。``accepted=False`` 时 ``reason`` 是 ``inbox_discarded`` 落的那个原因，
    或 ``inbox_closed``（episode 已收口，没有落账——finish 之后不再产生事件）。"""

    message_id: str
    accepted: bool
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "accepted": self.accepted,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class _Entry:
    message_id: str
    message: EpisodeMessage
    target: str
    wakeup: bool


class Inbox:
    """一个 episode 的收件箱。构造时绑定账本；``send`` / ``claim`` / ``discard_all`` 各落自己的事实。"""

    def __init__(
        self,
        ledger: MessageLedger,
        *,
        admit: Callable[[EpisodeMessage], bool] | None = None,
    ) -> None:
        self._ledger = ledger
        self._admit = admit
        self._lock = threading.Lock()
        self._counter = 0
        self._queues: dict[str, list[_Entry]] = {"next_turn": [], "next_step": []}
        self._closed = False
        # 取消时是否保留箱内消息（dsh ``keepInbox``）。默认 False：取消即清箱并落
        # ``inbox_discarded{reason=cancelled}``。置 True 的调用方要自己负责这些消息的后事
        # （本单不做恢复认领）。
        self.keep_on_cancel = False

    # ── 观测 ─────────────────────────────────────────────────────────────

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def pending(self, target: InboxTarget | None = None) -> int:
        with self._lock:
            if target is None:
                return sum(len(queue) for queue in self._queues.values())
            return len(self._queues[self._check_target(target)])

    # ── 写入 ─────────────────────────────────────────────────────────────

    def send(
        self,
        message: EpisodeMessage,
        *,
        target: InboxTarget = "next_step",
        wakeup: bool = False,
    ) -> InboxReceipt:
        """入箱。返回回执；拒收 / 已收口都不抛——递话方不该能把研究主路径打断。"""

        if message.role != "user":
            # 只有 user 角色能从外部进对话：system 是宪法、assistant 是模型、tool 要配对。
            raise ValueError(f"收件箱只收 user 角色消息，收到 {message.role!r}")
        target_key = self._check_target(target)
        with self._lock:
            if self._closed:
                return InboxReceipt(message_id="", accepted=False, reason="inbox_closed")
            self._counter += 1
            message_id = f"{_MESSAGE_ID_PREFIX}{self._counter}"
        ledger = self._ledger
        ledger.add(
            "inbox_inserted",
            {
                "message_id": message_id,
                "target": target_key,
                "source": str(message.source or ""),
                "wakeup": bool(wakeup),
                "content": message.content,
                "content_sha256": sha256_text(message.content),
                "chars": len(message.content),
            },
        )
        admitted, detail = self._admitted(message)
        if not admitted:
            ledger.add(
                "inbox_discarded",
                {
                    "message_id": message_id,
                    "target": target_key,
                    "source": str(message.source or ""),
                    "reason": "rejected_by_harness",
                    **({"detail": detail} if detail else {}),
                },
            )
            return InboxReceipt(
                message_id=message_id, accepted=False, reason="rejected_by_harness"
            )
        entry = _Entry(
            message_id=message_id, message=message, target=target_key, wakeup=bool(wakeup)
        )
        with self._lock:
            if self._closed:
                # 落账与入队之间被收口了：按收口丢弃，事实不留空洞。
                should_discard = True
            else:
                self._queues[target_key].append(entry)
                should_discard = False
        if should_discard:
            self._discard(entry, reason="episode_finished")
            return InboxReceipt(message_id=message_id, accepted=False, reason="inbox_closed")
        return InboxReceipt(message_id=message_id, accepted=True)

    # ── 认领 / 丢弃 ─────────────────────────────────────────────────────

    def claim(self, target: InboxTarget) -> list[EpisodeMessage]:
        """取出该队列全部消息并逐条落 ``inbox_claimed``。调用方随即把返回的消息 append 进
        ``messages``——两步之间没有别的模型可见改动，派生才能逐字节相等。"""

        target_key = self._check_target(target)
        with self._lock:
            entries = list(self._queues[target_key])
            self._queues[target_key].clear()
        ledger = self._ledger
        for entry in entries:
            ledger.add(
                "inbox_claimed",
                {
                    "message_id": entry.message_id,
                    "target": entry.target,
                    "source": str(entry.message.source or ""),
                },
            )
        return [entry.message for entry in entries]

    def discard_all(self, *, reason: InboxDiscardReason) -> int:
        """清箱并逐条落 ``inbox_discarded{reason}``。``reason=cancelled`` 且 ``keep_on_cancel``
        时不清（消息留在箱里、事件流里仍是 inserted 未决）。收口 / 取消后箱子关闭：
        之后的 ``send`` 只回 ``inbox_closed``，不再落账。"""

        if reason not in INBOX_DISCARD_REASONS:
            raise ValueError(f"未知丢弃原因: {reason!r}")
        with self._lock:
            keep = reason == "cancelled" and self.keep_on_cancel
            if keep:
                entries: list[_Entry] = []
            else:
                entries = [entry for queue in self._queues.values() for entry in queue]
                for queue in self._queues.values():
                    queue.clear()
            self._closed = True
        for entry in entries:
            self._discard(entry, reason=reason)
        return len(entries)

    def reopen(self) -> None:
        """修复轮（``resume``）重开箱子：``finish`` 之后 episode 又活了，外部输入面随之恢复。
        收口时已丢弃的不回来——事件流里它们的命运已经写死。"""

        with self._lock:
            self._closed = False

    # ── 内部 ─────────────────────────────────────────────────────────────

    def _discard(self, entry: _Entry, *, reason: str) -> None:
        ledger = self._ledger
        ledger.add(
            "inbox_discarded",
            {
                "message_id": entry.message_id,
                "target": entry.target,
                "source": str(entry.message.source or ""),
                "reason": reason,
            },
        )

    def _admitted(self, message: EpisodeMessage) -> tuple[bool, str]:
        if self._admit is None:
            return True, ""
        try:
            return bool(self._admit(message)), ""
        except Exception as exc:  # noqa: BLE001 - 领域判定坏了按拒收处理，不让递话方把 loop 打断
            return False, f"admit_error:{type(exc).__name__}"

    @staticmethod
    def _check_target(target: str) -> str:
        if target not in INBOX_TARGETS:
            raise ValueError(f"未知收件箱队列: {target!r}（只有 next_turn / next_step）")
        return str(target)
