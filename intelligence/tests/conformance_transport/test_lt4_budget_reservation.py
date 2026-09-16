"""LT-4 预算在副作用前预占：超额拒发时传输零触碰，预占累计跨回退/重试。

「配额要在副作用前预占，不是事后计数」——MOC 已确立原则的传输层落点：
入口检查是快路径，权威闸在传输边界的 ``_reserve_llm_call``（并发/回退都
先过它）。
"""

from __future__ import annotations

import pytest

from intelligence.tests.conformance_transport.baseline import ratchet
from intelligence.tests.conformance_transport.transports import (
    TRANSPORT_NAMES,
    TransportProbe,
    run_complete,
)

INV = "LT-4"


@pytest.mark.parametrize("transport", TRANSPORT_NAMES)
def test_zero_budget_rejects_before_any_transport_touch(
    transport: str,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, transport)
    probe = TransportProbe()
    (content, provider, reason), ledger = run_complete(
        transport, monkeypatch, probe, max_calls=0
    )
    assert content is None and provider is None
    assert "预算" in reason or "上限" in reason, "拒发理由必须点名预算"
    assert probe.invocations == 0, "超额后传输仍被触碰——预占闸被绕过"
    assert ledger.rejected_count >= 1, "拒发必须计数（收据不说谎）"


@pytest.mark.parametrize("transport", TRANSPORT_NAMES)
def test_success_consumes_exactly_one_reservation(
    transport: str,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, transport)
    probe = TransportProbe()
    (content, _provider, _reason), ledger = run_complete(
        transport, monkeypatch, probe, max_calls=1
    )
    assert content is not None
    summary = ledger.summary()
    assert summary["reserved_count"] == 1
    assert summary["call_count"] == 1
