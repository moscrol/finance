"""Network guard for the opt-in workspace smoke subprocess, not a sandbox."""
from __future__ import annotations

import socket

import pytest


def pytest_configure(config):
    patch = pytest.MonkeyPatch()

    def blocked(*args, **kwargs):
        raise AssertionError("workspace smoke forbids network access")

    for target, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"),
                         (socket, "create_connection"), (socket, "getaddrinfo")):
        patch.setattr(target, name, blocked)
    config.add_cleanup(patch.undo)


@pytest.fixture(autouse=True)
def isolated_user_state(tmp_path, monkeypatch):
    from intelligence import userspace

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setattr(userspace, "USERS_DIR", tmp_path / "users")
