"""CLI steer：从另一个进程给正在跑的 episode 递话（运行底座 P3，工单 #30 范围第 5 条）。

``Inbox.send`` 是进程内调用；Workbench 里 runtime 按次构造，``steer`` 端点按终态稿 §12 第 4 题
推荐等 Alpha。CLI 于是走 durable 目录：把话写进 ``<episode_dir>/inbox-spool/``（见
``episode_inbox`` 模块顶部），驱动 loop 的进程在下一个认领点吞进箱、三事实落账。本模块只做
递话方这一半：找对 store 根、判 episode 在不在 / 收口没、原子写槽、按 ``spool_id`` 从
events.jsonl 对回执。

两个 fail closed：

1. store 根与 Workbench 进程解析一致才递得到（``FORESIGHT_EPISODE_STORE`` >
   ``$FINANCE_WS/state/episodes`` > ``~/.finance-runtime/episodes``）。根不同就是部署账本那种
   「两个家」——所以 ``events.jsonl`` 不在就拒投并把看过的路径打出来，不静默写到一个没人读的目录。
2. ``state.json`` 已终局就拒投：收口后的箱子不吞槽也不落账，写了等于丢进黑洞。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import time
import uuid

from intelligence.services.episode_inbox import (
    INBOX_TARGETS,
    SpoolRecord,
    spool_dir_for,
    write_spool_record,
)
from intelligence.services.episode_store import (
    EpisodeLogCorrupt,
    JsonlEpisodeStore,
    now_iso,
)

__all__ = [
    "EpisodeFinished",
    "EpisodeNotFound",
    "SteerDelivery",
    "SteerError",
    "SteerReceipt",
    "deliver_steer",
    "list_open_episodes",
    "read_receipt",
    "wait_receipt",
]

_INSERTED = "inbox_inserted"
_CLAIMED = "inbox_claimed"
_DISCARDED = "inbox_discarded"


class SteerError(RuntimeError):
    code = "steer_error"


class EpisodeNotFound(SteerError):
    code = "episode_not_found"


class EpisodeFinished(SteerError):
    code = "episode_finished"


@dataclass(frozen=True)
class SteerDelivery:
    """投递成功的回执：话已在槽里，送达要等 loop 的下一个认领点。"""

    episode_id: str
    spool_id: str
    spool_path: Path
    store_root: Path
    target: str

    def to_dict(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "spool_id": self.spool_id,
            "spool_path": str(self.spool_path),
            "store_root": str(self.store_root),
            "target": self.target,
        }


@dataclass(frozen=True)
class SteerReceipt:
    """从 events.jsonl 对出来的命运：``fate`` 空 = 已入箱未决；``claimed`` = 模型可见；
    ``discarded:<reason>`` = 没送到模型。"""

    spool_id: str
    message_id: str
    fate: str = ""

    @property
    def settled(self) -> bool:
        return bool(self.fate)

    def to_dict(self) -> dict[str, object]:
        return {
            "spool_id": self.spool_id,
            "message_id": self.message_id,
            "fate": self.fate,
            "settled": self.settled,
        }


def deliver_steer(
    *,
    store_root: str | Path,
    episode_id: str,
    content: str,
    target: str = "next_step",
    source: str = "cli",
    wakeup: bool = False,
    spool_id: str | None = None,
) -> SteerDelivery:
    text = str(content or "")
    if not text.strip():
        raise ValueError("要递的话不能为空")
    if target not in INBOX_TARGETS:
        raise ValueError(f"未知收件箱队列: {target!r}（只有 next_turn / next_step）")
    root = Path(store_root).expanduser()
    store = JsonlEpisodeStore(root)
    episode_dir = store.episode_dir(episode_id)
    events_path = episode_dir / store.EVENTS_NAME
    if not events_path.is_file():
        raise EpisodeNotFound(
            f"episode {episode_id!r} 不在 store {root}（没有 {events_path}）。"
            "确认与 Workbench 进程用同一套 FORESIGHT_EPISODE_STORE / FINANCE_WS，或用 --list 看在跑的。"
        )
    state = store.load_state(episode_id)
    if state is not None and state.terminal:
        raise EpisodeFinished(
            f"episode {episode_id!r} 已收口（phase=done，{state.updated_at or '时刻未知'}），收件箱不再吞槽。"
        )
    spool = spool_dir_for(store, episode_id)
    if spool is None:  # JsonlEpisodeStore 一定有 episode_dir；防御性，不该到这里
        raise SteerError("落盘 store 没有给出投递槽目录")
    record = SpoolRecord(
        spool_id=str(spool_id or uuid.uuid4().hex[:12]),
        content=text,
        target=str(target),
        source=str(source or "cli"),
        wakeup=bool(wakeup),
        created_at=now_iso(),
    )
    path = write_spool_record(spool, record)
    return SteerDelivery(
        episode_id=str(episode_id),
        spool_id=record.spool_id,
        spool_path=path,
        store_root=root,
        target=record.target,
    )


def read_receipt(*, store_root: str | Path, episode_id: str, spool_id: str) -> SteerReceipt | None:
    """读一次 events.jsonl：找到带 ``spool_id`` 的 ``inbox_inserted`` 才算入箱；再按 ``message_id``
    找认领 / 丢弃。没入箱回 None。"""

    store = JsonlEpisodeStore(store_root)
    try:
        events, _state = store.load(episode_id)
    except EpisodeLogCorrupt as exc:
        raise SteerError(f"events.jsonl 读不出: {exc}") from exc
    message_id = ""
    for event in events:
        if event.kind == _INSERTED and event.payload.get("spool_id") == spool_id:
            message_id = str(event.payload.get("message_id") or "")
            break
    if not message_id:
        return None
    fate = ""
    for event in events:
        if event.payload.get("message_id") != message_id:
            continue
        if event.kind == _CLAIMED:
            fate = "claimed"
        elif event.kind == _DISCARDED:
            fate = f"discarded:{event.payload.get('reason', '')}"
    return SteerReceipt(spool_id=str(spool_id), message_id=message_id, fate=fate)


def wait_receipt(
    *,
    store_root: str | Path,
    episode_id: str,
    spool_id: str,
    timeout_s: float,
    poll_s: float = 0.5,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> SteerReceipt | None:
    """轮询到命运已定或超时；超时回最后一次读到的（可能是「已入箱未决」或 None）。"""

    deadline = clock() + max(0.0, float(timeout_s))
    latest: SteerReceipt | None = None
    while True:
        latest = read_receipt(store_root=store_root, episode_id=episode_id, spool_id=spool_id)
        if latest is not None and latest.settled:
            return latest
        remaining = deadline - clock()
        if remaining <= 0:
            return latest
        sleep(min(max(0.0, float(poll_s)), remaining))


def list_open_episodes(store_root: str | Path) -> tuple[str, ...]:
    return JsonlEpisodeStore(store_root).list_open()
