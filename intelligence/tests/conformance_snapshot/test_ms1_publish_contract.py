"""MS-1 发布契约：任一路发布的根目录必须过 root contract，不得空壳/冒充。

2026-06-22 sector 空壳回填的失败形状：行数与覆盖率全绿、值是空的——所以
这里对**发布产物**跑 ``validate_market_snapshot_root``，不数行数。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.market_snapshot_contract import (
    validate_market_snapshot_root,
)
from intelligence.tests.conformance_snapshot.baseline import ratchet
from intelligence.tests.conformance_snapshot.providers import (
    PROVIDER_NAMES,
    REQUESTED,
    run_publishing_scenario,
    write_protected_snapshot,
)

INV = "MS-1"


@pytest.mark.parametrize("provider", PROVIDER_NAMES)
def test_published_root_passes_the_snapshot_contract(
    provider: str,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, provider)
    result = run_publishing_scenario(provider, tmp_path)
    root = tmp_path / "snapshot"

    assert result.ok is True
    assert result.provider == provider
    assert result.quality == "complete"

    if provider == "existing_complete":
        # 保护旁路的「发布契约」= 零发布：不写文件、不动原件。
        assert result.written_files == ()
        assert result.preserved_existing_snapshot is True
        return

    assert result.written_files, "发布路径必须真的落盘"
    served = result.served_trade_date
    assert served is not None
    contract = validate_market_snapshot_root(root, served)
    assert contract["status"] == "PASS", contract["errors"] or contract["warnings"]
    assert contract["ready"] is True

    published = json.loads((root / f"{served}.json").read_text(encoding="utf-8"))
    assert published["quality"] == "complete"
    assert published["provider"] == provider
    assert published["requested_trade_date"] == REQUESTED
    assert published["served_trade_date"] == served

    publishing = result.attempts[-1]
    assert publishing.provider == provider
    assert publishing.published is True
    assert publishing.quality == "complete"


def test_fallback_serves_prior_date_without_impersonation(tmp_path: Path) -> None:
    """duckdb_latest 旧日供数不得冒充当日：目标日文件不落盘、freshness=historical。"""

    result = run_publishing_scenario("duckdb_latest", tmp_path)
    root = tmp_path / "snapshot"
    assert result.served_trade_date is not None
    assert result.served_trade_date < REQUESTED
    assert not (root / f"{REQUESTED}.json").exists(), "旧日数据冒充当日文件"
    latest = json.loads((root / "latest.json").read_text(encoding="utf-8"))
    assert latest["freshness"] == "historical"
    assert latest["served_trade_date"] == result.served_trade_date


def test_protected_snapshot_bytes_are_untouched(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    protected = write_protected_snapshot(root, REQUESTED)
    before = protected.read_bytes()
    run_publishing_scenario("existing_complete", tmp_path)
    assert protected.read_bytes() == before, "更高优先级快照被覆写"
