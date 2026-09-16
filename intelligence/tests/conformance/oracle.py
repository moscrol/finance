"""写序 oracle（INV-R2）：包住 store 的 append 与假 model / 假 tool 的「效果开始」交错记录。

日志只能看到最终写了什么，看不到「效果是不是在意图之前就开始了」。spy 把三类时刻
写进同一条时间线，事后断言每笔效果三明治的因果序：

    意图 append（sync=True） < 效果开始 < 结算 append（sync=False）

P2 先落在这里、先服务 ``test_inv_r2_write_order``；P4（工单 #31）把它定为**公共件**，
三处复用、同一份断言：

- ``test_inv_r2_write_order``：INV-R2 矩阵那一格（两个工具并发 + 两次模型请求）；
- ``test_inv_r3_restore``：Tier A 崩溃现场从它的日志截出来，先断言日志本身的写序；
- ``conformance/races/``：八条竞态 × 两序，每一序结束都 ``assert_sandwich()``。

用法：把它当 ``EpisodeStore`` 传给 ``ContinuousAgentEpisode(store=…)`` / ``GLMAgentRuntime(
episode_store=…)``；假 model / 假 tool 在开始工作那一刻调 ``effect_started(label, key)``；
跑完调 ``assert_sandwich()``。断言只认 kind / 关联 id / sync 标记，不读 payload 正文。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import threading

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_store import EpisodeState, MemoryEpisodeStore

_MODEL_SETTLEMENTS = frozenset({"model_turn", "model_error"})
_TOOL_SETTLEMENTS = frozenset({"tool_result", "tool_error"})


@dataclass(frozen=True)
class TimelineEntry:
    kind: str  # "append" | "state" | "effect"
    label: str  # event kind / phase / effect label
    key: str = ""  # turn_id / call_id，用来把意图与结算配成一组
    # 工具效果只知道 query（runner 签名里没有 call_id），意图同时带 call_id 与 query，
    # 靠它把「效果开始」归到某条意图上。
    alt: str = ""
    sync: bool | None = None
    sequence: int = 0


@dataclass
class SandwichViolation:
    message: str
    entries: tuple[TimelineEntry, ...] = ()


@dataclass
class WriteOrderOracle:
    """实现 ``EpisodeStore`` 四动作（委托给内存 store），并记录时间线。"""

    inner: MemoryEpisodeStore = field(default_factory=MemoryEpisodeStore)
    timeline: list[TimelineEntry] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ── EpisodeStore ──────────────────────────────────────────────────────

    def append(
        self, episode_id: str, events: Sequence[EpisodeEvent], *, sync: bool = False
    ) -> None:
        self.inner.append(episode_id, events, sync=sync)
        with self._lock:
            for event in events:
                payload = event.payload
                key = str(payload.get("turn_id") or payload.get("call_id") or "")
                arguments = payload.get("arguments")
                query = ""
                if isinstance(arguments, dict) or hasattr(arguments, "get"):
                    query = str(arguments.get("query") or "")  # type: ignore[union-attr]
                self.timeline.append(
                    TimelineEntry(
                        "append",
                        event.kind,
                        key=key,
                        alt=query,
                        sync=sync,
                        sequence=event.sequence,
                    )
                )

    def put_state(self, episode_id: str, state: EpisodeState) -> None:
        self.inner.put_state(episode_id, state)
        with self._lock:
            self.timeline.append(
                TimelineEntry("state", state.phase, key=",".join(state.reserved_ids))
            )

    def load(self, episode_id: str):
        return self.inner.load(episode_id)

    def list_open(self) -> tuple[str, ...]:
        return self.inner.list_open()

    # ── 效果侧钩子（假 model / 假 tool 在真正开始工作时调）─────────────────

    def effect_started(self, label: str, key: str = "") -> None:
        with self._lock:
            self.timeline.append(TimelineEntry("effect", label, key=key))

    # ── 断言 ─────────────────────────────────────────────────────────────

    def violations(self) -> list[SandwichViolation]:
        """每条 ``model_intent`` / 已派发 ``tool_request`` 都要有：之后的效果开始、再之后的结算。"""

        found: list[SandwichViolation] = []
        entries = tuple(self.timeline)
        model_effects = [i for i, e in enumerate(entries) if e.kind == "effect" and e.label == "model"]
        model_intents = [i for i, e in enumerate(entries) if e.kind == "append" and e.label == "model_intent"]
        if len(model_effects) != len(model_intents):
            found.append(
                SandwichViolation(
                    f"模型效果 {len(model_effects)} 次 vs model_intent {len(model_intents)} 条，不成对",
                )
            )
        for intent_index, effect_index in zip(model_intents, model_effects):
            intent = entries[intent_index]
            if intent.sync is not True:
                found.append(SandwichViolation(f"model_intent seq{intent.sequence} 没有 fsync", (intent,)))
            if effect_index < intent_index:
                found.append(
                    SandwichViolation(
                        f"模型请求在 model_intent seq{intent.sequence} 之前就开始了",
                        (entries[effect_index], intent),
                    )
                )
            settlement = next(
                (
                    e
                    for e in entries[effect_index + 1 :]
                    if e.kind == "append" and e.label in _MODEL_SETTLEMENTS and e.key == intent.key
                ),
                None,
            )
            if settlement is None:
                found.append(SandwichViolation(f"model_intent {intent.key} 之后没有结算", (intent,)))
            elif settlement.sync:
                found.append(SandwichViolation(f"结算 {settlement.label} {intent.key} 不该 fsync", (settlement,)))

        for index, entry in enumerate(entries):
            if entry.kind != "append" or entry.label != "tool_request":
                continue
            effect_index = next(
                (
                    j
                    for j, e in enumerate(entries)
                    if e.kind == "effect" and e.label == "tool" and e.key == entry.alt
                ),
                None,
            )
            if effect_index is None:
                # 未派发的调用（拒绝 / 零授权）没有效果，也不要求意图 fsync。
                continue
            if entry.sync is not True:
                found.append(SandwichViolation(f"tool_request {entry.key} 是派发意图却没有 fsync", (entry,)))
            if effect_index < index:
                found.append(
                    SandwichViolation(
                        f"工具 {entry.key} 在 tool_request 意图（seq{entry.sequence}）之前就开始跑了",
                        (entries[effect_index], entry),
                    )
                )
            settlement = next(
                (
                    e
                    for e in entries[effect_index + 1 :]
                    if e.kind == "append" and e.label in _TOOL_SETTLEMENTS and e.key == entry.key
                ),
                None,
            )
            if settlement is None:
                found.append(SandwichViolation(f"tool_request {entry.key} 之后没有结算", (entry,)))
            elif settlement.sync:
                found.append(SandwichViolation(f"结算 {settlement.label} {entry.key} 不该 fsync", (settlement,)))
        return found

    def assert_sandwich(self) -> None:
        problems = self.violations()
        assert not problems, "\n".join(item.message for item in problems)


__all__ = ["SandwichViolation", "TimelineEntry", "WriteOrderOracle"]
