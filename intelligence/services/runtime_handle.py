"""RuntimeHandle：一次 Episode 运行时的统一生命周期状态机。

来源：``docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md``
§7.3（统一 Runtime 生命周期），实施顺序第 4 步（2/2；1/2 是 Episode 入口构造
EpisodeScope）。

六态固定为：``created → started → running → cancel_requested → draining → closed``。
状态只进不退；允许沿序跳跃向前（正常完成 running→closed 不经过取消两态；
无在飞工作时 cancel_requested→closed 不经过 draining——draining 描述的是
「有已启动的工作正在收尾」这个事实，没有工作可收就不制造虚构状态）。

--------------------------------------------------------------------------
这个状态机在哪一层
--------------------------------------------------------------------------

**会话层（一个 Episode 身份的整个运行时），不是内层轮次循环。** 仓里已有的
取消/排空机制不重建：

- 内层排空已存在：``agent_episode`` 在模型轮与工具派发间检查 ``is_cancelled``；
  ``episode_tool_batch._dispatch`` 取消时停止等待、把未完成的调用落为
  ``rejected/cancelled``、``QueryPublishGuard`` 回滚未发布的查询登记。
  Handle 不伸手进去，只在会话层**表达**这个边界并留收据。
- resume 五条不变量已存在（``episode_session.py``：episode 身份、task frame
  hash、事件不丢、前缀不改写、必须产生新 model_turn），Handle 不复述，
  由 ``CallbackEpisodeSession.resume`` 继续拥有。
- 子研究 lineage 已存在（``sub_research.py``：预算账本
  ``{task_id}:{branch_id}``、trace ``{parent}:{branch_id}``），分支各有各的
  run 和 Scope，靠既有 lineage 对账。

--------------------------------------------------------------------------
钉死的设计点：Scope 生命周期（检阅方指定，不留给第 5 步猜）
--------------------------------------------------------------------------

**Scope 的生命周期 = 整个 Episode 身份（初始 run + 全部 repair resume），
不是单次 run。** 依据是既有行为而非新约定：``ContinuousAgentEpisode.resume``
不重进 ``run()``，它复用 continuation state 里的**同一个** ``tool_session``
——也就是 run() 入口构造的同一个 EpisodeScope。因此：

- ``invoked_tools`` 与事件收据**天然不按修复周期碎片化**，不存在归并问题；
- Handle **引用** Scope（``attach_scope``），不构造、不拥有——构造权钉在
  Episode 入口（4b23a516），一个 Episode 一个 Scope 一份收据；
- 每次 run **不派生子 Scope**。子研究分支是另一个 run、另一份身份
  （见上 lineage），其 Scope 不并入父收据——分支证据本来就经 evidence_sink
  汇给父，事件合流是第 5 步的事。

``dump()`` 里内嵌 ``scope.dump()``，生命周期收据与能力收据在一处对账。

--------------------------------------------------------------------------
取消与关闭的语义
--------------------------------------------------------------------------

- ``request_cancel`` / 上游信号只**挡未派发的工作**（新 resume 会被
  ``begin_work`` 拒绝），不打断在飞的 run/resume——那是「已启动的只读工作」，
  由内层机制排空后自行返回（``allow_during_cancel=True`` 的工作单元就是
  正在被排空的那一个）。
- 上游取消信号是**惰性折叠**的：``is_cancel_requested()`` / ``begin_work`` /
  ``end_work`` 首次观测到上游为真时才记 ``cancel_requested`` 转移。收据记的
  是首次观测时刻，不虚构信号发生时刻——运行时对信号的全部知识就来自观测。
- ``close()`` 幂等；close 之后 ``begin_work`` 一律拒绝并把拒绝记进收据
  （「close 后不得发布新 Agent/Tool/Event」在会话层的兑现点：事件只能产自
  run/resume 工作单元，挡住工作单元就挡住了事件）。close 不打断在飞工作
  （驱动方的 finally 可能在异常收尾时先到），只如实记 ``closed_with_inflight``。

--------------------------------------------------------------------------
写死认领（本轮有意不做，别处别以为已经做了）
--------------------------------------------------------------------------

1. **事件出口级 close 门**：EpisodeScope.event_sink 仍为 None（第 4 步 1/2 的
   决定），事件出口合流与 sink 级「close 后拒发」属第 5 步 Durable/Live。
2. **收据落盘**：``dump()`` 本轮只在对象上可取（经 ``session.runtime_handle``），
   进 artifact/Projection 属第 5 步。
3. **其余会话构造点的接线**：本轮接 ``GLMAgentRuntime.start``（生产主线）+
   ``ContinuousTurnAdapter`` 收尾 close。``openai_agents_runtime`` /
   ``codex_headless_runtime`` / ``headless_tool_gateway`` 的会话与
   子研究分支的 per-branch Handle 是第 4 步收尾轮（spec §7.3 验收里
   「Session、Headless Gateway 覆盖」尚未闭合，不得据本轮声称完成）。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from time import monotonic
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查；运行期无循环依赖但保持轻量
    from intelligence.services.episode_scope import EpisodeScope

__all__ = [
    "RuntimeHandle",
    "RuntimeHandleCancelled",
    "RuntimeHandleClosed",
    "RuntimeState",
]

RuntimeState = Literal[
    "created",
    "started",
    "running",
    "cancel_requested",
    "draining",
    "closed",
]

# 序号即合法方向：只允许向更大的序号转移。做成模块级常量而不是散在比较里，
# 是让「六态与顺序」只有一个事实源。
_STATE_ORDER: dict[str, int] = {
    "created": 0,
    "started": 1,
    "running": 2,
    "cancel_requested": 3,
    "draining": 4,
    "closed": 5,
}


class RuntimeHandleClosed(RuntimeError):
    """close 之后仍试图派发新工作。"""


class RuntimeHandleCancelled(RuntimeError):
    """取消请求之后仍试图派发新工作（在飞工作不受影响，由排空收尾）。"""


class RuntimeHandle:
    """一次 Episode 的运行时生命周期收据与工作单元门。

    线程模型：``request_cancel`` 可能来自另一个线程（API 取消端点 / 定时器），
    工作单元进出来自驱动线程，所以全部状态变更持锁。锁内不调用任何外部代码
    （上游取消信号除外——它是调用方给的谓词，约定必须快且不抛；抛了就按
    「信号不可用」处理，不折叠）。
    """

    def __init__(
        self,
        *,
        episode_id: str,
        task_frame_hash: str = "",
        upstream_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self.episode_id = str(episode_id or "").strip()
        if not self.episode_id:
            raise ValueError("runtime handle 必须携带 episode_id")
        self.task_frame_hash = str(task_frame_hash or "")
        self._upstream_cancelled = upstream_cancelled
        self._lock = threading.RLock()
        self._born_at = monotonic()
        self._state: RuntimeState = "created"
        self._in_flight = 0
        self._cancel_reason: str | None = None
        self._close_reason: str | None = None
        self._scope: EpisodeScope | None = None
        # 收据行按发生顺序追加：state 行是状态转移，note 行是不改状态的事实
        # （工作单元进出、被拒绝的派发、排空完成）。分两种而不砍掉 note，
        # 是因为四类验收场景的差别经常不在终态而在中间事实。
        self._receipts: list[dict[str, object]] = []
        self._record_transition("created", "handle_constructed")

    # ── 收据 ─────────────────────────────────────────────────────────

    def _elapsed_ms(self) -> int:
        return int((monotonic() - self._born_at) * 1000)

    def _record_transition(self, state: RuntimeState, reason: str) -> None:
        self._receipts.append(
            {
                "kind": "transition",
                "state": state,
                "reason": str(reason),
                "elapsed_ms": self._elapsed_ms(),
            }
        )

    def _record_note(self, event: str, reason: str) -> None:
        self._receipts.append(
            {
                "kind": "note",
                "event": str(event),
                "reason": str(reason),
                "elapsed_ms": self._elapsed_ms(),
            }
        )

    # ── 状态观测 ─────────────────────────────────────────────────────

    @property
    def state(self) -> RuntimeState:
        with self._lock:
            return self._state

    def is_closed(self) -> bool:
        with self._lock:
            return self._state == "closed"

    def is_cancel_requested(self) -> bool:
        """是否已请求取消（含惰性折叠上游信号）。"""

        with self._lock:
            self._fold_upstream_locked()
            return self._cancel_reason is not None

    def _fold_upstream_locked(self) -> None:
        if self._cancel_reason is not None or self._state == "closed":
            return
        upstream = self._upstream_cancelled
        if upstream is None:
            return
        try:
            fired = bool(upstream())
        except Exception:
            # 信号谓词自己坏了不等于取消。不折叠、不吞状态机其他职责。
            return
        if fired:
            self._request_cancel_locked("upstream_signal")

    # ── 转移 ─────────────────────────────────────────────────────────

    def _advance_locked(self, target: RuntimeState, reason: str) -> None:
        if _STATE_ORDER[target] <= _STATE_ORDER[self._state]:
            raise RuntimeError(
                f"runtime handle 不允许回退或原地转移：{self._state} -> {target}"
            )
        self._state = target
        self._record_transition(target, reason)

    def mark_started(self, reason: str = "initial_run_dispatched") -> None:
        with self._lock:
            if self._state != "created":
                raise RuntimeError(
                    f"mark_started 只能从 created 出发，当前 {self._state}"
                )
            self._advance_locked("started", reason)

    def mark_running(self, reason: str = "session_live") -> None:
        """started → running；取消已先到时不回退状态，只记事实。

        初始 run 期间上游可能已请求取消（此时状态已是 cancel_requested /
        draining）。这里强行转 running 就是回退；抛错则逼每个驱动方写同一段
        条件——都不对。压成一条 note，收据仍然如实。
        """

        with self._lock:
            if self._state == "closed":
                raise RuntimeHandleClosed("runtime handle 已关闭")
            if self._state == "started":
                self._advance_locked("running", reason)
                return
            if _STATE_ORDER[self._state] >= _STATE_ORDER["cancel_requested"]:
                self._record_note("session_live_suppressed", "取消已先于会话就绪")
                return
            raise RuntimeError(
                f"mark_running 只能从 started 出发，当前 {self._state}"
            )

    def request_cancel(self, reason: str = "cancel_requested") -> None:
        with self._lock:
            if self._state == "closed":
                # 对已结束的运行时请求取消不是错误，但值得留痕。
                self._record_note("cancel_after_close", reason)
                return
            self._request_cancel_locked(reason)

    def _request_cancel_locked(self, reason: str) -> None:
        if self._cancel_reason is not None:
            self._record_note("cancel_repeated", reason)
            return
        self._cancel_reason = str(reason)
        self._advance_locked("cancel_requested", reason)
        if self._in_flight > 0:
            # 有已启动的工作要收尾，这才配叫排空。
            self._advance_locked(
                "draining", f"in_flight={self._in_flight}"
            )

    def close(self, reason: str = "closed") -> None:
        """幂等关闭。任何状态可达 closed；重复 close 无观测差异。"""

        with self._lock:
            if self._state == "closed":
                return
            if self._in_flight > 0:
                # 驱动方的 finally 可能在异常收尾时先于工作单元退出到达。
                # 拒绝 close 会把泄漏做大，如实记录比阻止诚实。
                self._record_note(
                    "closed_with_inflight", f"in_flight={self._in_flight}"
                )
            self._close_reason = str(reason)
            self._advance_locked("closed", reason)

    # ── 工作单元门 ───────────────────────────────────────────────────

    def begin_work(self, kind: str, *, allow_during_cancel: bool = False) -> None:
        """派发一个工作单元（run / resume）前必须过这道门。

        - closed：一律拒绝（close 后不得发布新 Agent/Tool/Event 的兑现点）；
        - 取消已请求且 ``allow_during_cancel=False``：拒绝——cancel 只挡
          未派发的工作；
        - ``allow_during_cancel=True`` 用于**正在被排空的那一个**工作单元
          （初始 run 由 start() 同步派发，取消到达时它就是要排空的对象），
          不是给新工作开的后门。
        """

        with self._lock:
            self._fold_upstream_locked()
            if self._state == "closed":
                self._record_note("work_denied_closed", kind)
                raise RuntimeHandleClosed(
                    f"runtime handle 已关闭，拒绝派发 {kind}"
                )
            if self._cancel_reason is not None and not allow_during_cancel:
                self._record_note("work_denied_cancelled", kind)
                raise RuntimeHandleCancelled(
                    f"已请求取消（{self._cancel_reason}），拒绝派发 {kind}"
                )
            self._in_flight += 1
            if (
                self._cancel_reason is not None
                and self._state == "cancel_requested"
            ):
                # 取消时无在飞工作、随后又派发了被允许的排空单元：现在才真正
                # 进入排空。
                self._advance_locked("draining", f"drain_{kind}")
            self._record_note("work_begun", kind)

    def end_work(self, kind: str) -> None:
        with self._lock:
            self._fold_upstream_locked()
            if self._in_flight <= 0:
                raise RuntimeError("end_work 没有对应的 begin_work")
            self._in_flight -= 1
            self._record_note("work_ended", kind)
            if (
                self._in_flight == 0
                and self._cancel_reason is not None
                and self._state == "draining"
            ):
                self._record_note("drained", "全部在飞工作已收尾")

    # ── Scope 引用（不拥有）──────────────────────────────────────────

    def attach_scope(self, scope: EpisodeScope) -> None:
        """引用 Episode 入口构造的那个 Scope（一个 Episode 恰好一个）。

        身份必须一致：Handle 与 Scope 都以 ``contract.task_id`` 为 episode_id，
        对不上说明接线接错了对象，立刻炸而不是留一份两说的收据。
        """

        with self._lock:
            if scope.episode_id != self.episode_id:
                raise ValueError(
                    "scope 与 handle 的 episode_id 不一致："
                    f"{scope.episode_id!r} != {self.episode_id!r}"
                )
            if self._scope is not None and self._scope is not scope:
                raise RuntimeError("runtime handle 已经引用了另一个 scope")
            self._scope = scope

    # ── 收据出口 ─────────────────────────────────────────────────────

    def dump(self) -> dict[str, object]:
        with self._lock:
            self._fold_upstream_locked()
            return {
                "episode_id": self.episode_id,
                "task_frame_hash": self.task_frame_hash,
                "state": self._state,
                "cancel_requested": self._cancel_reason is not None,
                "cancel_reason": self._cancel_reason,
                "close_reason": self._close_reason,
                "in_flight": self._in_flight,
                "receipts": [dict(row) for row in self._receipts],
                "scope_attached": self._scope is not None,
                # 生命周期收据与能力收据一处对账（设计点：一个 Episode 一个
                # Scope 一份收据，无归并问题）。
                "scope": self._scope.dump() if self._scope is not None else None,
            }
