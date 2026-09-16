"""MS-5 发布门 fail-closed：非 complete / 缺日期 / 过不了 contract 的文档拒绝发布。

``_publish_complete_document`` 是三源共用的唯一落盘口——这道门松了，
上游任何一源的降级产物都能穿到消费方。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.services.market_snapshot_sync import _publish_complete_document
from intelligence.tests.conformance_snapshot.providers import (
    _complete_akshare_document,
)


def test_non_complete_document_is_rejected(tmp_path: Path) -> None:
    document = _complete_akshare_document("2026-07-16")
    document["quality"] = "partial"
    with pytest.raises(ValueError, match="complete"):
        _publish_complete_document(tmp_path / "snapshot", document)
    assert not (tmp_path / "snapshot" / "2026-07-16.json").exists()


def test_missing_trade_date_is_rejected(tmp_path: Path) -> None:
    document = _complete_akshare_document("2026-07-16")
    document.pop("trade_date")
    with pytest.raises(ValueError, match="trade_date"):
        _publish_complete_document(tmp_path / "snapshot", document)


def test_contract_failing_document_is_rejected_before_touching_base(
    tmp_path: Path,
) -> None:
    """quality=complete 但结构烂（缺 market 必需字段）→ 发布前 contract 拦下。"""

    document = _complete_akshare_document("2026-07-16")
    document["market"] = {"stage": "只剩一个字段"}
    with pytest.raises(ValueError, match="contract"):
        _publish_complete_document(tmp_path / "snapshot", document)
    assert not (tmp_path / "snapshot").exists() or not list(
        (tmp_path / "snapshot").iterdir()
    ), "contract 未过却污染了发布目录"
