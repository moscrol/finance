"""方案 1 PR3：数据块 provider 注册表 + enabled_providers 收敛开关。"""

from intelligence.services import evidence_registry
from intelligence.services.ask import AskOptions


def test_registry_covers_all_data_blocks_in_order():
    assert evidence_registry.PROVIDER_NAMES == (
        "D0", "D6", "D9", "D8", "D7", "W7", "M", "MARKET_DAILY", "V",
        "D1", "D4", "D2", "D5", "D3",
    )
    legacy = {spec.legacy_option for spec in evidence_registry.REGISTRY}
    assert len(legacy) == len(evidence_registry.REGISTRY)  # 每块唯一旧开关


def test_default_none_falls_back_to_legacy_flags():
    options = AskOptions(query="q", include_moneyflow_block=False)
    assert evidence_registry.provider_enabled(options, "D9") is False
    assert evidence_registry.provider_enabled(options, "D0") is True


def test_enabled_providers_whitelist_overrides_legacy_flags():
    options = AskOptions(
        query="q",
        include_moneyflow_block=False,  # 白名单模式下旧开关不再参与
        enabled_providers=("D9", "D5"),
    )
    assert evidence_registry.provider_enabled(options, "D9") is True
    assert evidence_registry.provider_enabled(options, "D5") is True
    for name in ("D0", "D6", "D8", "D7", "W7", "M", "V", "D1", "D4", "D2", "D3"):
        assert evidence_registry.provider_enabled(options, name) is False


def test_empty_whitelist_disables_all_blocks():
    options = AskOptions(query="q", enabled_providers=())
    for name in evidence_registry.PROVIDER_NAMES:
        assert evidence_registry.provider_enabled(options, name) is False
