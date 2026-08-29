"""MS-4 状态收据：每个终态都要落 status 文件且与返回值一致（运维读的是它）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.tests.conformance_snapshot.baseline import ratchet
from intelligence.tests.conformance_snapshot.providers import (
    PROVIDER_NAMES,
    run_publishing_scenario,
    run_total_failure,
)

INV = "MS-4"


def _status(tmp_path: Path) -> dict[str, object]:
    path = tmp_path / "snapshot" / "market_snapshot_sync_status.json"
    assert path.is_file(), "终态没有落 status 收据"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("provider", PROVIDER_NAMES)
def test_status_receipt_mirrors_the_result(
    provider: str,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, provider)
    result = run_publishing_scenario(provider, tmp_path)
    status = _status(tmp_path)
    assert status["ok"] == result.ok
    assert status["provider"] == result.provider
    assert status["requested_trade_date"] == result.requested_trade_date
    assert status["served_trade_date"] == result.served_trade_date
    assert len(status["attempts"]) == len(result.attempts)
    assert [item["provider"] for item in status["attempts"]] == [
        item.provider for item in result.attempts
    ]


def test_total_failure_still_writes_the_receipt(tmp_path: Path) -> None:
    result = run_total_failure(tmp_path)
    status = _status(tmp_path)
    assert status["ok"] is False
    assert status["provider"] is None
    assert len(status["attempts"]) == len(result.attempts)
