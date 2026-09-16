"""LT-1 返回三元组契约：成功 = (非空内容, 生效 provider, 空 reason)。"""

from __future__ import annotations

import pytest

from intelligence.tests.conformance_transport.baseline import ratchet
from intelligence.tests.conformance_transport.transports import (
    TRANSPORT_NAMES,
    TransportProbe,
    run_complete,
)

INV = "LT-1"


@pytest.mark.parametrize("transport", TRANSPORT_NAMES)
def test_success_triple_shape(
    transport: str,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, transport)
    probe = TransportProbe()
    (content, provider, reason), _ledger = run_complete(
        transport, monkeypatch, probe, content="七二三一"
    )
    assert content == "七二三一"
    assert provider is not None and provider.transport == (
        "cli" if transport == "cli" else "http"
    )
    assert reason == "", "成功时 reason 必须是空串（调用方按空串判成功）"
    assert probe.invocations == 1, "成功恰好一次传输调用，不得重试"
