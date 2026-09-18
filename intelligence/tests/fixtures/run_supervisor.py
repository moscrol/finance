"""Keep test-owned workers inside the lifetime of their patched dependencies."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def drain_test_client(client: TestClient) -> None:
    """Cancel queued work and join running fakes before pytest undoes monkeypatch.

    Production shutdown intentionally does not wait for slow IO. Tests own their
    bounded runners and must release any gates before calling this helper. Access
    to the private executor is confined to test infrastructure, not a new runtime
    shutdown policy. Waiting also covers completion callbacks/credit settlement.
    """
    supervisor = client.app.state.supervisor
    supervisor.shutdown()
    supervisor._executor.shutdown(wait=True, cancel_futures=True)
    client.close()
