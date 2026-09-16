"""LT-3 超时不越窗：传输边界收到的窗口 ≤ 请求窗口（CLI 有已声明的 1s 地板）。"""

from __future__ import annotations

import pytest

from intelligence.tests.conformance_transport.baseline import ratchet
from intelligence.tests.conformance_transport.transports import (
    TRANSPORT_NAMES,
    TransportProbe,
    run_complete,
)

INV = "LT-3"


@pytest.mark.parametrize("transport", TRANSPORT_NAMES)
def test_transport_window_never_exceeds_requested(
    transport: str,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, transport)
    probe = TransportProbe()
    requested = 30.0
    run_complete(transport, monkeypatch, probe, timeout=requested)
    assert probe.timeouts, "传输边界没有收到超时参数"
    received = probe.timeouts[0]
    assert 0 < received <= requested, (
        f"{transport} 收到 {received}s > 请求 {requested}s——各订阅各的时钟"
        "会让共享窗口失效"
    )


def test_cli_declared_floor_is_exactly_one_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI 的 max(1.0, timeout) 地板：亚秒残窗会被抬到 1s——已声明偏差。

    这是防退化超时的设计取舍（TRANSPORT_NOTES 在案），本测试把它钉成
    **显式契约**：若哪天地板被移除或改值，这里先红，声明表同步更新。
    """

    probe = TransportProbe()
    run_complete("cli", monkeypatch, probe, timeout=0.5)
    assert probe.timeouts and probe.timeouts[0] == 1.0


def test_http_subsecond_window_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = TransportProbe()
    run_complete("http", monkeypatch, probe, timeout=0.5)
    assert probe.timeouts and 0 < probe.timeouts[0] <= 0.5
