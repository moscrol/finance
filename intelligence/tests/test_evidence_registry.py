"""方案 1 PR3：数据块 provider 注册表 + enabled_providers 允许名单。"""

import pytest

from intelligence.services import evidence_registry
from intelligence.services.ask import AskOptions


def test_registry_covers_all_data_blocks_in_order():
    assert evidence_registry.PROVIDER_NAMES == (
        # D8/D10/D11 连成一段：同为历史类比，按粒度从粗到细排（题材级 / 市场情绪级 /
        # 个股级），提示词里相邻，模型据此对照三个层次的同一类事实。
        "D0", "D6", "D9", "D12", "D13", "D8", "D10", "D11", "D7", "W7", "D17", "M", "MARKET_DAILY", "V",
        # MAINLINE_KB 紧跟 D4：两块在提示词里相邻，讲的是同一批主线方向的两条腿
        # （盘面结构 vs 知识库积累）。D0-D9 已占满，故沿用 MARKET_DAILY 的描述式命名。
        "D1", "D4", "MAINLINE_KB", "D2", "D5", "D3",
    )


def test_default_none_allows_every_registered_provider():
    options = AskOptions(query="q")
    for name in evidence_registry.PROVIDER_NAMES:
        assert evidence_registry.provider_enabled(options, name) is True


def test_without_providers_disables_only_named_blocks():
    options = AskOptions(
        query="q",
        enabled_providers=evidence_registry.without_providers("D9", "D12", "D13"),
    )
    assert evidence_registry.provider_enabled(options, "D9") is False
    assert evidence_registry.provider_enabled(options, "D12") is False
    assert evidence_registry.provider_enabled(options, "D13") is False
    assert evidence_registry.provider_enabled(options, "D0") is True


def test_enabled_providers_whitelist_is_allow_not_force():
    options = AskOptions(
        query="q",
        enabled_providers=("D9", "D5"),
    )
    assert evidence_registry.provider_enabled(options, "D9") is True
    assert evidence_registry.provider_enabled(options, "D5") is True
    for name in ("D0", "D6", "D12", "D13", "D8", "D10", "D11", "D7", "W7", "D17", "M", "V", "D1", "D4", "D2", "D3"):
        assert evidence_registry.provider_enabled(options, name) is False


def test_empty_whitelist_disables_all_blocks():
    options = AskOptions(query="q", enabled_providers=())
    for name in evidence_registry.PROVIDER_NAMES:
        assert evidence_registry.provider_enabled(options, name) is False


def test_providers_allowing_memory_off_keeps_other_blocks():
    off = AskOptions(
        query="q",
        enabled_providers=evidence_registry.providers_allowing_memory(False),
    )
    assert evidence_registry.provider_enabled(off, "M") is False
    assert evidence_registry.provider_enabled(off, "V") is False
    assert evidence_registry.provider_enabled(off, "D0") is True
    on = AskOptions(
        query="q",
        enabled_providers=evidence_registry.providers_allowing_memory(True),
    )
    assert on.enabled_providers is None
    assert evidence_registry.provider_enabled(on, "M") is True


def test_without_providers_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown evidence providers"):
        evidence_registry.without_providers("not-a-block")
