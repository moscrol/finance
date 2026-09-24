"""Keep test-owned workers inside the lifetime of their patched dependencies."""
from __future__ import annotations

from threading import Timer, current_thread
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class _OwnedTimers(dict[tuple[str, str], Timer]):
    """Record this supervisor's timers even after its completion callback pops them.

    The supervisor already serializes all writes with its lock. After the test
    joins its executor, no worker can create/start another timer in this list.
    No global Timer factory or unrelated process thread is patched or inspected.
    """

    def __init__(self, timers: dict[tuple[str, str], Timer]) -> None:
        super().__init__(timers)
        self.owned = list(timers.values())

    def __setitem__(self, key: tuple[str, str], timer: Timer) -> None:
        self.owned.append(timer)
        super().__setitem__(key, timer)


def track_test_client_timers(client: TestClient) -> None:
    """Register ownership before a fixture yields its client or accepts test work."""
    supervisor = client.app.state.supervisor
    with supervisor._lock:
        if not isinstance(supervisor._timers, _OwnedTimers):
            supervisor._timers = _OwnedTimers(supervisor._timers)


def drain_test_client(client: TestClient) -> None:
    """Cancel queued work and join owned workers/timers before monkeypatch undo.

    Production shutdown intentionally does not wait for slow IO. Tests own their
    bounded runners and must release any gates before calling this helper. Access
    to the private executor is confined to test infrastructure, not a new runtime
    shutdown policy. Waiting also covers completion callbacks/credit settlement
    and already-fired timeout callbacks no longer in the active task table.
    """
    supervisor = client.app.state.supervisor
    supervisor.shutdown()
    supervisor._executor.shutdown(wait=True, cancel_futures=True)
    with supervisor._lock:
        if not isinstance(supervisor._timers, _OwnedTimers):
            raise RuntimeError("register test timer ownership before submitting work")
        timers = tuple(supervisor._timers.owned)
    for timer in timers:
        timer.cancel()
    for timer in timers:
        if timer is not current_thread() and timer.ident is not None:
            timer.join()
    client.close()
