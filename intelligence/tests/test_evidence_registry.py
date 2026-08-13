"""方案 1 PR3：数据块 provider 注册表 + enabled_providers 收敛开关。"""

from intelligence.services import evidence_registry
from intelligence.services.ask import AskOptions


def test_registry_covers_all_data_blocks_in_order():
    assert evidence_registry.PROVIDER_NAMES == (
        # D10 紧跟 D8：同为历史类比（D8 题材级 / D10 市场情绪级），提示词里相邻。
        "D0", "D6", "D9", "D8", "D10", "D7", "W7", "M", "MARKET_DAILY", "V",
        # MAINLINE_KB 紧跟 D4：两块在提示词里相邻，讲的是同一批主线方向的两条腿
        # （盘面结构 vs 知识库积累）。D0-D9 已占满，故沿用 MARKET_DAILY 的描述式命名。
        "D1", "D4", "MAINLINE_KB", "D2", "D5", "D3",
    )
    # 旧开关唯一性只约束真有旧开关的块；MARKET_DAILY 与 MAINLINE_KB 的
    # legacy_option 为空 = 默认参与，仍受 enabled_providers 约束。
    legacy = [spec.legacy_option for spec in evidence_registry.REGISTRY if spec.legacy_option]
    assert len(set(legacy)) == len(legacy)


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
    for name in ("D0", "D6", "D8", "D10", "D7", "W7", "M", "V", "D1", "D4", "D2", "D3"):
        assert evidence_registry.provider_enabled(options, name) is False


def test_empty_whitelist_disables_all_blocks():
    options = AskOptions(query="q", enabled_providers=())
    for name in evidence_registry.PROVIDER_NAMES:
        assert evidence_registry.provider_enabled(options, name) is False
