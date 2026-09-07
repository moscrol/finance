"""Durable episode store：事件追加日志 + 程序计数器覆写（INV-R2 / INV-R3 的存储侧）。

来源：``docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`` §6.3 P2；
工单 #29 步骤 A1 / A2。形状来自 pi「entries 只写一次 / registers 覆写当前值」与
dsh 追加式 ``SessionEvent`` 日志。搬的是不变量，不搬 SQLite 事务细节（§12 第 1 题：JSONL）。

--------------------------------------------------------------------------
两份东西、各自的读法
--------------------------------------------------------------------------

- ``events.jsonl``：只追加。每行一条 ``EpisodeEvent``，是重放日志（``derive_messages``
  重建模型历史、评测与投影从它派生）。它**不是**恢复用的位置指针——从事件流「推断」
  现在走到哪一步，会把「缺一条」读成「没发生」。
- ``state.json``：每次 phase 转移**整份覆写**的 ``EpisodeState``（durable program counter）。
  恢复只读它，再按它记下的预留 id 去事件流里**点查**结算有没有落下——点查是合法的，
  重放推断不是。

写序纪律（效果三明治，INV-R2）：意图事件（``INTENT_KINDS``）append 后 ``fsync``，结算不
``fsync``。崩溃能留下的唯一不确定是「意图有、结算无」；丢结算 = 落回不确定窗口，恢复策略
表能处理；丢意图则「外部效果发生过但没人知道」，那是不允许存在的形状。

撕裂末行：单写者顺序 append，崩溃只可能撕坏最后一行。读到末行解不出 JSON 就整行丢弃；
**非末行**坏了不是撕裂而是损坏，抛 ``EpisodeLogCorrupt``，不猜。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from types import MappingProxyType
from typing import Literal, Protocol

from intelligence.services.agent_runtime import EpisodeEvent, _json_copy
from intelligence.services.episode_event_lanes import DURABLE_EVENT_KINDS

__all__ = [
    "EPISODE_LOG_VERSION",
    "EPISODE_PHASES",
    "EPISODE_STORE_ENV",
    "EpisodeLogCorrupt",
    "EpisodePhase",
    "EpisodeState",
    "EpisodeStore",
    "INTENT_KINDS",
    "JsonlEpisodeStore",
    "MemoryEpisodeStore",
    "UnknownRequiredKind",
    "now_iso",
    "require_known_kinds",
    "resolve_episode_store_root",
]

# 事件日志的 schema 版本：写进 ``state.json`` 与 ``continuous-episode.json``。读者遇到不同
# 版本**拒绝**，不做静默升级——升级逻辑在有第二个版本时再写，写在这里的会是猜的。
EPISODE_LOG_VERSION = 1

EpisodePhase = Literal[
    "planning", "model_pending", "tools_pending", "repair", "finalizing", "done"
]
EPISODE_PHASES: frozenset[str] = frozenset(
    {"planning", "model_pending", "tools_pending", "repair", "finalizing", "done"}
)

# 意图类事件：外部效果（模型请求 / 工具执行 / 兜底合成）之前落下的那一条。append 后 fsync。
INTENT_KINDS: frozenset[str] = frozenset(
    {"model_intent", "tool_request", "finalization_recovery_started"}
)

EPISODE_STORE_ENV = "FORESIGHT_EPISODE_STORE"


class EpisodeLogCorrupt(RuntimeError):
    """事件日志非末行解不出 / 序号不连续：这是损坏，不是撕裂。"""


class UnknownRequiredKind(RuntimeError):
    """事件流里出现未登记且未打 ``ignorable`` 的 kind——读者不能假装看懂。"""

    def __init__(self, kind: str, sequence: int) -> None:
        super().__init__(f"unknown_required_kind: {kind!r} @sequence {sequence}")
        self.kind = kind
        self.sequence = sequence


def _frozen_mapping(value: Mapping[str, object] | None, *, path: str) -> Mapping[str, object]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} 必须是对象")
    # 递归复制成普通 dict / list（嵌套的冻结 payload——mappingproxy / tuple——也吃得下），
    # 既校验 JSON 安全，也切断与调用方活对象的引用。
    copied = _json_copy(value, path=path)
    assert isinstance(copied, dict)
    return MappingProxyType(copied)


@dataclass(frozen=True)
class EpisodeState:
    """程序计数器：一份**完整**状态，每次 phase 转移覆写。恢复只读它并 switch。

    - ``reserved_ids``：当前 phase 里已落意图、等结算的关联 id（模型 = ``turn_id``，
      工具 = ``call_id``）。恢复按它们点查结算。空 = 这个 phase 没有在飞的外部效果。
    - ``deadline_at``：研究截止的挂钟时刻（ISO-8601）。恢复时判「截止是否已过」只看它，
      不重建 ``ResearchDeadline`` 活对象。空串 = 未知，按已过处理（fail closed）。
    - ``retry``：捕获的重试策略，``{"remaining": int}``——恢复时模型意图无结算允许再试
      几次。写在状态里而不是恢复时现算：策略是当时的决定，不该被以后的代码改写。
    - ``contract_snapshot``：``configure`` 事件同源的快照（哈希与标量，不抄文本）。
    - ``cancel``：``CancelSignal.snapshot()``；非空即「取消已 durable」（INV-R4 的存储侧）。
    """

    episode_id: str
    phase: EpisodePhase
    turn_index: int = 0
    reserved_ids: tuple[str, ...] = ()
    consumed_seconds: float = 0.0
    deadline_at: str = ""
    retry: Mapping[str, object] = field(default_factory=dict)
    contract_snapshot: Mapping[str, object] = field(default_factory=dict)
    cancel: Mapping[str, object] | None = None
    log_version: int = EPISODE_LOG_VERSION
    last_sequence: int = 0
    updated_at: str = ""

    def __post_init__(self) -> None:
        episode_id = str(self.episode_id or "").strip()
        if not episode_id:
            raise ValueError("EpisodeState 必须携带 episode_id")
        if self.phase not in EPISODE_PHASES:
            raise ValueError(f"未知 phase: {self.phase!r}")
        if isinstance(self.turn_index, bool) or not isinstance(self.turn_index, int) or self.turn_index < 0:
            raise ValueError("turn_index 必须是非负整数")
        if isinstance(self.last_sequence, bool) or not isinstance(self.last_sequence, int) or self.last_sequence < 0:
            raise ValueError("last_sequence 必须是非负整数")
        if isinstance(self.log_version, bool) or not isinstance(self.log_version, int) or self.log_version < 1:
            raise ValueError("log_version 必须是正整数")
        reserved = tuple(str(item) for item in self.reserved_ids if str(item or "").strip())
        object.__setattr__(self, "episode_id", episode_id)
        object.__setattr__(self, "reserved_ids", reserved)
        object.__setattr__(self, "consumed_seconds", max(0.0, float(self.consumed_seconds)))
        object.__setattr__(self, "deadline_at", str(self.deadline_at or ""))
        object.__setattr__(self, "updated_at", str(self.updated_at or ""))
        object.__setattr__(self, "retry", _frozen_mapping(self.retry, path="retry"))
        object.__setattr__(
            self,
            "contract_snapshot",
            _frozen_mapping(self.contract_snapshot, path="contract_snapshot"),
        )
        if self.cancel is not None:
            object.__setattr__(self, "cancel", _frozen_mapping(self.cancel, path="cancel"))

    @property
    def terminal(self) -> bool:
        return self.phase == "done"

    def to_dict(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "phase": self.phase,
            "turn_index": self.turn_index,
            "reserved_ids": list(self.reserved_ids),
            "consumed_seconds": self.consumed_seconds,
            "deadline_at": self.deadline_at,
            "retry": dict(self.retry),
            "contract_snapshot": dict(self.contract_snapshot),
            "cancel": dict(self.cancel) if self.cancel is not None else None,
            "log_version": self.log_version,
            "last_sequence": self.last_sequence,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> EpisodeState:
        if not isinstance(payload, Mapping):
            raise ValueError("EpisodeState 载荷必须是对象")
        cancel = payload.get("cancel")
        return cls(
            episode_id=str(payload.get("episode_id") or ""),
            phase=str(payload.get("phase") or ""),  # type: ignore[arg-type]
            turn_index=int(payload.get("turn_index") or 0),
            reserved_ids=tuple(str(item) for item in (payload.get("reserved_ids") or ())),
            consumed_seconds=float(payload.get("consumed_seconds") or 0.0),
            deadline_at=str(payload.get("deadline_at") or ""),
            retry=dict(payload.get("retry") or {}),  # type: ignore[arg-type]
            contract_snapshot=dict(payload.get("contract_snapshot") or {}),  # type: ignore[arg-type]
            cancel=dict(cancel) if isinstance(cancel, Mapping) else None,
            log_version=int(payload.get("log_version") or 0),
            last_sequence=int(payload.get("last_sequence") or 0),
            updated_at=str(payload.get("updated_at") or ""),
        )


class EpisodeStore(Protocol):
    """四个动作，够 loop 落账、够 restore 读回。多进程写者 / 跨机复制是非目标。"""

    def append(
        self, episode_id: str, events: Sequence[EpisodeEvent], *, sync: bool = False
    ) -> None: ...

    def put_state(self, episode_id: str, state: EpisodeState) -> None: ...

    def load(self, episode_id: str) -> tuple[tuple[EpisodeEvent, ...], EpisodeState | None]: ...

    def list_open(self) -> tuple[str, ...]: ...


def require_known_kinds(events: Iterable[EpisodeEvent]) -> None:
    """读者入口校验：未登记且非 ignorable 的 kind → ``UnknownRequiredKind``。

    登记表是 ``episode_event_lanes.DURABLE_EVENT_KINDS``（单一事实源）。写方新增 kind 要么
    先登记，要么打 ``ignorable``——两条路都是显式的，没有「读者自己猜」这条。
    """

    for event in events:
        if event.kind in DURABLE_EVENT_KINDS or event.ignorable:
            continue
        raise UnknownRequiredKind(event.kind, event.sequence)


def _event_record(event: EpisodeEvent) -> dict[str, object]:
    return event.to_dict()


def _event_from_record(record: Mapping[str, object]) -> EpisodeEvent:
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("事件记录缺 payload 对象")
    return EpisodeEvent(
        int(record.get("sequence") or 0),
        str(record.get("kind") or ""),
        payload,
        ignorable=bool(record.get("ignorable", False)),
    )


def _require_contiguous(events: Sequence[EpisodeEvent], *, episode_id: str) -> None:
    expected = tuple(range(1, len(events) + 1))
    actual = tuple(event.sequence for event in events)
    if actual != expected:
        raise EpisodeLogCorrupt(
            f"{episode_id}: 事件序号不连续（期望 1..{len(events)}，读到 {actual[:8]}…）"
        )


class MemoryEpisodeStore:
    """测试与无落盘调用方用：同一套四动作，纯内存。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: dict[str, list[EpisodeEvent]] = {}
        self._states: dict[str, EpisodeState] = {}
        # 写序 oracle 与「意图 fsync、结算不 fsync」的断言靶：记录每次 append 的 sync 标记。
        self.append_log: list[tuple[str, tuple[int, ...], bool]] = []

    def append(
        self, episode_id: str, events: Sequence[EpisodeEvent], *, sync: bool = False
    ) -> None:
        items = tuple(events)
        if not items:
            return
        with self._lock:
            self._events.setdefault(episode_id, []).extend(items)
            self.append_log.append(
                (episode_id, tuple(event.sequence for event in items), bool(sync))
            )

    def put_state(self, episode_id: str, state: EpisodeState) -> None:
        if state.episode_id != episode_id:
            raise ValueError("state.episode_id 与写入的 episode_id 不一致")
        with self._lock:
            self._states[episode_id] = state

    def load(self, episode_id: str) -> tuple[tuple[EpisodeEvent, ...], EpisodeState | None]:
        with self._lock:
            events = tuple(self._events.get(episode_id, ()))
            state = self._states.get(episode_id)
        _require_contiguous(events, episode_id=episode_id)
        return events, state

    def list_open(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(
                    episode_id
                    for episode_id, state in self._states.items()
                    if not state.terminal
                )
            )

    def truncate(self, episode_id: str, *, keep: int) -> None:
        """测试用：模拟崩溃——只保留前 ``keep`` 条事件（状态另由测试决定保留哪份）。"""

        with self._lock:
            self._events[episode_id] = list(self._events.get(episode_id, ()))[:keep]


_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _directory_name(episode_id: str) -> str:
    """episode_id（``run_…:msg_…``）含冒号等文件系统不友好字符：替换后加短哈希保单射。"""

    safe = _UNSAFE_NAME.sub("_", episode_id)
    if safe == episode_id:
        return safe
    digest = hashlib.sha256(episode_id.encode("utf-8")).hexdigest()[:12]
    return f"{safe}-{digest}"


class JsonlEpisodeStore:
    """生产实现：``<root>/<episode_dir>/{events.jsonl,state.json}``。

    与 ``deploy-ledger.jsonl`` 同族：追加式 JSONL、零依赖。``state.json`` 走
    「写临时文件 → fsync → ``os.replace``」，读者永远只看到旧的或新的整份，没有半份。
    """

    EVENTS_NAME = "events.jsonl"
    STATE_NAME = "state.json"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser()
        self._lock = threading.RLock()

    def episode_dir(self, episode_id: str) -> Path:
        return self.root / _directory_name(str(episode_id))

    def append(
        self, episode_id: str, events: Sequence[EpisodeEvent], *, sync: bool = False
    ) -> None:
        items = tuple(events)
        if not items:
            return
        lines = "".join(
            json.dumps(_event_record(event), ensure_ascii=False) + "\n" for event in items
        )
        directory = self.episode_dir(episode_id)
        with self._lock:
            directory.mkdir(parents=True, exist_ok=True)
            with open(directory / self.EVENTS_NAME, "a", encoding="utf-8") as handle:
                handle.write(lines)
                handle.flush()
                if sync:
                    os.fsync(handle.fileno())

    def put_state(self, episode_id: str, state: EpisodeState) -> None:
        if state.episode_id != episode_id:
            raise ValueError("state.episode_id 与写入的 episode_id 不一致")
        directory = self.episode_dir(episode_id)
        target = directory / self.STATE_NAME
        temporary = directory / f".{self.STATE_NAME}.{os.getpid()}.tmp"
        body = json.dumps(state.to_dict(), ensure_ascii=False, indent=2)
        with self._lock:
            directory.mkdir(parents=True, exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)

    def _read_events(self, path: Path, *, episode_id: str) -> tuple[EpisodeEvent, ...]:
        if not path.is_file():
            return ()
        raw_lines = [line for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]
        events: list[EpisodeEvent] = []
        last_index = len(raw_lines) - 1
        for index, line in enumerate(raw_lines):
            try:
                record = json.loads(line)
                event = _event_from_record(record)
            except (ValueError, TypeError) as exc:
                if index == last_index:
                    # 撕裂末行：单写者 append 被崩溃切断。整行丢弃，前缀仍是合法日志。
                    break
                raise EpisodeLogCorrupt(
                    f"{episode_id}: 第 {index + 1} 行（非末行）解不出事件: {exc}"
                ) from exc
            events.append(event)
        frozen = tuple(events)
        _require_contiguous(frozen, episode_id=episode_id)
        return frozen

    def _read_state(self, path: Path) -> EpisodeState | None:
        if not path.is_file():
            return None
        return EpisodeState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def load(self, episode_id: str) -> tuple[tuple[EpisodeEvent, ...], EpisodeState | None]:
        directory = self.episode_dir(episode_id)
        with self._lock:
            events = self._read_events(directory / self.EVENTS_NAME, episode_id=episode_id)
            state = self._read_state(directory / self.STATE_NAME)
        return events, state

    def list_open(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        open_ids: list[str] = []
        with self._lock:
            for child in sorted(self.root.iterdir()):
                state_path = child / self.STATE_NAME
                if not child.is_dir() or not state_path.is_file():
                    continue
                try:
                    state = self._read_state(state_path)
                except (ValueError, OSError):
                    # 读不出的 state 不是「open」也不是「done」——列出来让人看见比吞掉好，
                    # 但它没有 episode_id 可报，用目录名代。
                    open_ids.append(child.name)
                    continue
                if state is not None and not state.terminal:
                    open_ids.append(state.episode_id)
        return tuple(sorted(open_ids))


def resolve_episode_store_root(finance_ws: str | None = None) -> Path:
    """store 根目录解析，覆盖序与 ``deploy_ledger.resolve_ledger_path`` 同：

    1. ``FORESIGHT_EPISODE_STORE``（测试 / 显式覆盖）
    2. ``$FINANCE_WS/state/episodes``（生产数据仓，跨快照）
    3. ``~/.finance-runtime/episodes``
    """

    override = os.environ.get(EPISODE_STORE_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    workspace = (finance_ws if finance_ws is not None else os.environ.get("FINANCE_WS", "")).strip()
    if workspace:
        return Path(workspace).expanduser() / "state" / "episodes"
    return Path.home() / ".finance-runtime" / "episodes"


def now_iso() -> str:
    """状态与合成事件的挂钟时刻，与 ``_EpisodeLedger.add`` 的 ``at`` 同格式。"""

    return datetime.now().astimezone().isoformat(timespec="milliseconds")
