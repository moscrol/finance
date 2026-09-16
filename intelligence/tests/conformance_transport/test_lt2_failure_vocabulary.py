"""LT-2 失败词表：降级 reason 必须可分类，故障种类由类名/状态码承载。

下游闸门（semantic judge 重试判定、fallback 归因）读的就是这个串——
裸 RuntimeError 会让四种故障坍缩成一种（2026-08-27 生产 8/38 教训）。
"""

from __future__ import annotations

import pytest

from intelligence.tests.conformance_transport.baseline import ratchet
from intelligence.tests.conformance_transport.transports import (
    FAILURE_CASES,
    TRANSPORT_NAMES,
    TransportProbe,
    run_complete,
)

INV = "LT-2"


@pytest.mark.parametrize("transport", TRANSPORT_NAMES)
def test_transport_failure_maps_to_classified_reason(
    transport: str,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, transport)
    failure, expected_reason = FAILURE_CASES[transport]
    probe = TransportProbe()
    (content, provider, reason), _ledger = run_complete(
        transport, monkeypatch, probe, failure=failure
    )
    assert content is None
    assert provider is not None, "失败也要指认是哪个 provider 败的"
    assert reason == expected_reason
    assert "Traceback" not in reason, "reason 是分类词面，不是堆栈"


def test_cli_empty_response_keeps_its_own_class_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI 空响应与非零退出必须是**不同**的 reason（类名承载种类）。"""

    probe = TransportProbe()
    (content, _provider, reason), _ledger = run_complete(
        "cli", monkeypatch, probe, failure="cli_empty"
    )
    assert content is None
    assert reason == "LLM 调用失败（GrokCliEmptyResponse）"
    assert reason != FAILURE_CASES["cli"][1]
