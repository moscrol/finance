"""LT-5 凭证不入痕：key 不得出现在 reason / 台账 / provider repr 任何一处。"""

from __future__ import annotations

import json

import pytest

from intelligence.tests.conformance_transport.baseline import ratchet
from intelligence.tests.conformance_transport.transports import (
    FAILURE_CASES,
    SECRET,
    TRANSPORT_NAMES,
    TransportProbe,
    make_provider,
    run_complete,
)

INV = "LT-5"


@pytest.mark.parametrize("transport", TRANSPORT_NAMES)
@pytest.mark.parametrize("outcome", ("success", "failure"))
def test_api_key_never_leaks_into_observability(
    transport: str,
    outcome: str,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, transport)
    probe = TransportProbe()
    failure = FAILURE_CASES[transport][0] if outcome == "failure" else None
    (_content, provider, reason), ledger = run_complete(
        transport, monkeypatch, probe, failure=failure
    )
    assert SECRET not in reason
    assert SECRET not in json.dumps(ledger.summary(), ensure_ascii=False)
    if provider is not None:
        assert SECRET not in repr(provider), (
            "LLMProvider.api_key 必须 repr=False——repr 进日志就是泄漏"
        )


def test_provider_repr_hides_key_by_construction() -> None:
    for transport in TRANSPORT_NAMES:
        assert SECRET not in repr(make_provider(transport))
