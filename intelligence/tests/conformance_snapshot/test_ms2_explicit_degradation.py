"""MS-2 降级必须显式：每个失败/未配置的 provider 都要有带理由的 attempt 行。

禁止静默回退——「谁试过、为什么没成」必须能从收据逐行读出。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.tests.conformance_snapshot.baseline import ratchet
from intelligence.tests.conformance_snapshot.providers import (
    CHAIN_ORDER,
    REQUESTED,
    empty_db,
    run_publishing_scenario,
    run_total_failure,
)
from intelligence.services.market_snapshot_sync import sync_market_snapshot

INV = "MS-2"

# 让指定 provider 落败的最小场景：复用发布场景（前面的 provider 自然落败）
# 或全败场景。
_FAILING_SCENARIO = {
    "duckdb_exact": ("publishing", "akshare_exact"),
    "akshare_exact": ("publishing", "duckdb_latest"),
    "duckdb_latest": ("total_failure", None),
}


@pytest.mark.parametrize("provider", CHAIN_ORDER)
def test_failed_provider_leaves_an_explicit_attempt_row(
    provider: str,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, provider)
    kind, publisher = _FAILING_SCENARIO[provider]
    result = (
        run_publishing_scenario(publisher, tmp_path)
        if kind == "publishing"
        else run_total_failure(tmp_path)
    )
    rows = [item for item in result.attempts if item.provider == provider]
    assert rows, f"{provider} 落败后没有 attempt 行——静默回退"
    row = rows[0]
    assert row.published is False
    assert row.quality != "complete"
    assert (row.error or "").strip(), "落败必须带理由，空 error 不可诊断"
    assert row.requested_trade_date == REQUESTED


def test_unconfigured_akshare_is_declared_not_skipped(tmp_path: Path) -> None:
    """runner 未配置 ≠ 无事发生：必须留「未配置」的 attempt 行。"""

    result = sync_market_snapshot(
        tmp_path / "snapshot",
        db_path=empty_db(tmp_path / "market.duckdb"),
        target_date=REQUESTED,
        akshare_runner=None,
    )
    rows = [item for item in result.attempts if item.provider == "akshare_exact"]
    assert rows and "未配置" in (rows[0].error or "")


def test_total_failure_is_honest(tmp_path: Path) -> None:
    result = run_total_failure(tmp_path)
    assert result.ok is False
    assert result.quality == "failed"
    assert result.provider is None
    assert result.served_trade_date is None
    assert result.written_files == ()
    assert all(item.published is False for item in result.attempts)
