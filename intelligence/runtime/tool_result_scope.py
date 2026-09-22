"""Batch-local acceptance of branch callbacks, distinct from cache publication.

Storage failure may still settle received private results within the original
window. After close/expiry, children may keep their own logs/usage, but cannot
mutate the parent ledger. No lock is held across model/tool execution.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock


class ToolResultScope:
    def __init__(self, cutoff: float, clock: Callable[[], float]) -> None:
        self.cutoff = cutoff
        self._clock = clock
        self._lock = RLock()
        self._open = True

    @contextmanager
    def accepting(self) -> Iterator[bool]:
        # Only local parent settlement belongs here, never child execution.
        with self._lock:
            yield self._open and self._clock() < self.cutoff

    def close(self) -> None:
        with self._lock:
            self._open = False


_CURRENT: ContextVar[ToolResultScope | None] = ContextVar("tool_result_scope", default=None)


def current_tool_result_scope() -> ToolResultScope | None:
    return _CURRENT.get()


@contextmanager
def tool_result_scope(scope: ToolResultScope) -> Iterator[None]:
    token = _CURRENT.set(scope)
    try:
        yield
    finally:
        _CURRENT.reset(token)
