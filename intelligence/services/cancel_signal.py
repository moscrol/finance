"""类型化取消信号（INV-R4 的输入侧）。

来源：``docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`` §3 INV-R4、
§6.2 P1 第 2 条；工单 #28 步骤 B。形状来自 dsh ``AgentCancelCause = user | parent | hook |
disposed``（first cause wins）与 pi「``aborted`` 当且仅当 signal 被拉；超时 / 传输失败 /
provider 拒绝一律 ``error``」。

--------------------------------------------------------------------------
为什么不再裸传 ``Callable[[], bool]``
--------------------------------------------------------------------------

此前取消是一个布尔谓词从 ``GLMAgentRuntime`` 一路传到 Episode、工具批次、子研究、
``RuntimeHandle``；``finish{stop_reason=cancelled}`` 不带原因，``RuntimeHandle.cancel_reason``
是自由字符串。事后归因分不清「用户点了停」「父 episode 取消了分支」「hook 否决」「进程
在收尾」——四种的重试语义与责任归属完全不同。

``CancelSignal`` 把原因收成枚举、first cause wins，并且**可调用**：``signal()`` 返回
``requested``，所以所有既有 ``is_cancelled()`` 接缝零改动就能收到它。上游若仍是裸谓词，
``coerce`` 把它包起来并给一个默认原因——包装是惰性折叠的：谓词首次观测为真的那一刻才记
原因，与 ``RuntimeHandle`` 对上游信号的处理同一口径。

线程模型：``request`` 可能来自另一个线程（API 取消端点 / 定时器），观测来自驱动线程，
状态变更持锁；锁内不调外部代码（上游谓词除外——它是调用方给的谓词，约定快且不抛，
抛了按「信号不可用」处理，不折叠）。
"""

from __future__ import annotations

from collections.abc import Callable
import threading
from typing import Literal

__all__ = ["CANCEL_CAUSES", "CancelCause", "CancelSignal"]

CancelCause = Literal["user", "parent", "hook", "deadline", "disposed"]
CANCEL_CAUSES: frozenset[str] = frozenset({"user", "parent", "hook", "deadline", "disposed"})


class CancelSignal:
    """可调用的类型化取消信号。``signal()`` == ``signal.requested``。"""

    def __init__(
        self,
        upstream: Callable[[], bool] | None = None,
        *,
        upstream_cause: CancelCause = "user",
        upstream_detail: str = "upstream_signal",
    ) -> None:
        if upstream_cause not in CANCEL_CAUSES:
            raise ValueError(f"未知取消原因: {upstream_cause!r}")
        self._upstream = upstream
        self._upstream_cause: CancelCause = upstream_cause
        self._upstream_detail = str(upstream_detail)
        self._lock = threading.Lock()
        self._cause: CancelCause | None = None
        self._detail = ""

    # ── 构造 ─────────────────────────────────────────────────────────────

    @classmethod
    def coerce(
        cls,
        value: Callable[[], bool] | CancelSignal | None,
        *,
        cause: CancelCause = "user",
    ) -> CancelSignal:
        """接缝处统一入口：已是信号原样返回；裸谓词包起来；None 给一个永不触发的信号。"""

        if isinstance(value, CancelSignal):
            return value
        return cls(value, upstream_cause=cause)

    def child(self, *, cause: CancelCause = "parent", detail: str = "parent_cancelled") -> CancelSignal:
        """派生给子工作（子研究分支）的信号：父取消传下去时原因记为 ``parent``，
        子自己被取消时记自己的原因。"""

        return CancelSignal(self, upstream_cause=cause, upstream_detail=detail)

    # ── 变更 ─────────────────────────────────────────────────────────────

    def request(self, cause: CancelCause, detail: str = "") -> bool:
        """请求取消。first cause wins：已有原因时不覆盖，返回 False。"""

        if cause not in CANCEL_CAUSES:
            raise ValueError(f"未知取消原因: {cause!r}")
        with self._lock:
            if self._cause is not None:
                return False
            self._cause = cause
            self._detail = str(detail)
            return True

    def _fold_upstream_locked(self) -> None:
        if self._cause is not None or self._upstream is None:
            return
        try:
            fired = bool(self._upstream())
        except Exception:
            # 谓词自己坏了不等于取消。
            return
        if fired:
            self._cause = self._upstream_cause
            self._detail = self._upstream_detail

    # ── 观测 ─────────────────────────────────────────────────────────────

    @property
    def upstream(self) -> Callable[[], bool] | None:
        """被包住的上游谓词 / 父信号。装配审计用：断言「几处接缝看的是同一份事实」。"""

        return self._upstream

    @property
    def requested(self) -> bool:
        with self._lock:
            self._fold_upstream_locked()
            return self._cause is not None

    @property
    def cause(self) -> CancelCause | None:
        with self._lock:
            self._fold_upstream_locked()
            return self._cause

    @property
    def detail(self) -> str:
        with self._lock:
            self._fold_upstream_locked()
            return self._detail

    def __call__(self) -> bool:
        return self.requested

    def snapshot(self) -> dict[str, object]:
        """收据用：三个字段一次取，避免锁外拼出「requested=True 但 cause=None」的假态。"""

        with self._lock:
            self._fold_upstream_locked()
            return {
                "requested": self._cause is not None,
                "cause": self._cause,
                "detail": self._detail,
            }
