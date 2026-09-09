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
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Literal

from intelligence.services.episode_messages import (
    EpisodeMessage,
    MessageLedger,
    sha256_text,
    user_message,
)

__all__ = [
    "INBOX_DISCARD_REASONS",
    "INBOX_SPOOL_DIRNAME",
    "INBOX_TARGETS",
    "Inbox",
    "InboxDiscardReason",
    "InboxReceipt",
    "InboxTarget",
    "SpoolRecord",
    "read_spool_record",
    "spool_dir_for",
    "write_spool_record",
]

logger = logging.getLogger(__name__)

InboxTarget = Literal["next_turn", "next_step"]
INBOX_TARGETS: frozenset[str] = frozenset({"next_turn", "next_step"})

InboxDiscardReason = Literal["rejected_by_harness", "cancelled", "episode_finished"]
INBOX_DISCARD_REASONS: frozenset[str] = frozenset(
    {"rejected_by_harness", "cancelled", "episode_finished"}
)

# 送达后事件流里没有正文的事件也要能定位到消息：``message_id`` 在一个 episode 内唯一。
_MESSAGE_ID_PREFIX = "inbox-"

# ── 跨进程投递槽（CLI steer 的门，工单 #30 范围第 5 条）────────────────────────
# ``Inbox.send`` 是进程内调用；Workbench 里 runtime 按次构造、``steer`` 端点按终态稿 §12 第 4 题
# 等 Alpha，另一个进程（``python3 -m intelligence.cli steer``）没有门可递话。投递槽把「递」拆成
# 两半：递话方把一条消息写成 ``<episode_dir>/inbox-spool/<ns>-<spool_id>.json``（写临时名再
# rename，读者永远只见整份）；驱动 loop 的进程在既有认领点（``pending`` / ``claim`` /
# ``discard_all``）先把槽里的文件逐个 ``send`` 进箱、事实落账后删文件。三事实仍只由 loop 写进
# events.jsonl，INV-R5 一字不改——槽只是运输，不是账。运输单位是文件而不是追加行：不用管撕裂行
# 与偏移量，「吞了没吞」就是「文件在不在」。删在 ``send`` 之后：崩在中间最多重吞一次
# （``spool_id`` 进 ``inbox_inserted`` payload，重复可对出来），反过来会无痕丢话。
INBOX_SPOOL_DIRNAME = "inbox-spool"
INBOX_SPOOL_SUFFIX = ".json"
_SPOOL_TMP_SUFFIX = ".tmp"
_SPOOL_INVALID_SUFFIX = ".invalid"


@dataclass(frozen=True)
class SpoolRecord:
    """槽里一条消息的形状——递话方与吞话方共用，字段与 ``inbox_inserted`` payload 对齐。"""

    spool_id: str
    content: str
    target: str = "next_step"
    source: str = "cli"
    wakeup: bool = False
    created_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "spool_id": self.spool_id,
            "content": self.content,
            "target": self.target,
            "source": self.source,
            "wakeup": self.wakeup,
            "created_at": self.created_at,
        }


def spool_dir_for(store: object | None, episode_id: str) -> Path | None:
    """``<episode_dir>/inbox-spool/``。只有落盘的 store（有 ``episode_dir``）才有槽；内存 store /
    无 store 回 None——那种 episode 只有进程内的门。"""

    if store is None:
        return None
    episode_dir = getattr(store, "episode_dir", None)
    if not callable(episode_dir):
        return None
    return Path(episode_dir(str(episode_id))) / INBOX_SPOOL_DIRNAME


def write_spool_record(spool: Path, record: SpoolRecord) -> Path:
    """原子投递：写 ``.tmp`` → fsync → ``os.replace`` 成 ``<ns>-<spool_id>.json``。
    文件名按纳秒时间戳排序 = 认领顺序。"""

    if not record.spool_id or not record.content.strip():
        raise ValueError("投递槽记录必须有 spool_id 与非空 content")
    if record.target not in INBOX_TARGETS:
        raise ValueError(f"未知收件箱队列: {record.target!r}（只有 next_turn / next_step）")
    spool = Path(spool)
    spool.mkdir(parents=True, exist_ok=True)
    final = spool / f"{time.time_ns():020d}-{record.spool_id}{INBOX_SPOOL_SUFFIX}"
    tmp = final.with_name(final.name + _SPOOL_TMP_SUFFIX)
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, final)
    return final


def read_spool_record(path: Path) -> SpoolRecord | None:
    """读一条槽记录；形状不对回 None（调用方隔离文件，不猜正文）。"""

    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    content = raw.get("content")
    spool_id = raw.get("spool_id")
    target = raw.get("target", "next_step")
    if not isinstance(content, str) or not content.strip():
        return None
    if not isinstance(spool_id, str) or not spool_id:
        return None
    if not isinstance(target, str) or target not in INBOX_TARGETS:
        return None
    source = raw.get("source", "cli")
    created_at = raw.get("created_at", "")
    return SpoolRecord(
        spool_id=spool_id,
        content=content,
        target=target,
        source=source if isinstance(source, str) and source else "cli",
        wakeup=bool(raw.get("wakeup", False)),
        created_at=created_at if isinstance(created_at, str) else "",
    )


def _quarantine(path: Path) -> None:
    """坏文件改名 ``.invalid`` 留给人看，不落账：没有可信正文就不能说「话到过」。"""

    target = path.with_name(path.name + _SPOOL_INVALID_SUFFIX)
    try:
        os.replace(path, target)
    except OSError as exc:
        logger.warning("收件箱投递槽坏文件隔离失败 %s: %s", path, exc)
        return
    logger.warning("收件箱投递槽坏文件已隔离: %s", target)


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
        spool: Path | None = None,
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
        # 跨进程投递槽（见模块顶部注释）。None = 这个 episode 只有进程内的门。
        self._spool = Path(spool) if spool is not None else None
        # 吞槽发生在认领点（驱动线程），但 ``pending`` 也可能被别的线程读；锁住
        # 「列目录 → 逐个 send → 删」整段，两个吞话方不会看见同一个文件。
        self._spool_lock = threading.Lock()

    # ── 观测 ─────────────────────────────────────────────────────────────

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def pending(self, target: InboxTarget | None = None) -> int:
        # loop 在模型停下时用它判「还有话没」——槽里的话也算，否则 CLI 的 next_turn 会被
        # 一次「没话了」的判定漏过去。
        self.ingest_spool()
        with self._lock:
            if target is None:
                return sum(len(queue) for queue in self._queues.values())
            return len(self._queues[self._check_target(target)])

    # ── 投递槽 ───────────────────────────────────────────────────────────

    def ingest_spool(self) -> int:
        """把投递槽里的消息文件逐个 ``send`` 进箱，事实落账后删文件；回吞了几条。

        箱子关着（收口 / 取消后）不吞：文件留在槽里，``reopen`` 后下一次认领再吞——收口后到的话
        与进程内 ``send`` 一样不落账（``inbox_closed``），递话方按 ``state.json`` 的终局自己判。
        形状不对的文件改名 ``.invalid`` 隔离、不落账。
        """

        spool = self._spool
        if spool is None:
            return 0
        with self._spool_lock:
            if self.closed:
                return 0
            try:
                paths = sorted(
                    path
                    for path in spool.iterdir()
                    if path.is_file() and path.suffix == INBOX_SPOOL_SUFFIX
                )
            except FileNotFoundError:
                return 0
            except OSError as exc:
                logger.warning("收件箱投递槽读不出 %s: %s", spool, exc)
                return 0
            ingested = 0
            for path in paths:
                record = read_spool_record(path)
                if record is None:
                    _quarantine(path)
                    continue
                receipt = self.send(
                    user_message(record.content, source=record.source),
                    target=record.target,  # 已由 read_spool_record 校验在 INBOX_TARGETS 内
                    wakeup=record.wakeup,
                    spool_id=record.spool_id,
                )
                if receipt.reason == "inbox_closed":
                    # 没落账就不能删：话还没到过账本。留在槽里等 reopen。
                    break
                # 至少 inserted 已落（拒收还有 discarded），运输单位可以销毁。
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                ingested += 1
            return ingested

    # ── 写入 ─────────────────────────────────────────────────────────────

    def send(
        self,
        message: EpisodeMessage,
        *,
        target: InboxTarget = "next_step",
        wakeup: bool = False,
        spool_id: str = "",
    ) -> InboxReceipt:
        """入箱。返回回执；拒收 / 已收口都不抛——递话方不该能把研究主路径打断。
        ``spool_id`` 只在话来自投递槽时非空，进 ``inbox_inserted`` payload 让递话方对回执；
        进程内 ``send`` 的 payload 形状不变。"""

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
                **({"spool_id": str(spool_id)} if spool_id else {}),
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
        self.ingest_spool()
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
        # 关箱前最后吞一次槽：收口前到的话与进程内 send 同命——inserted 落了、随即 discarded，
        # 事件流说得清「到了但没送到」，而不是让文件在槽里烂成无迹可查。
        self.ingest_spool()
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
