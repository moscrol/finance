"""sw_l1 映射回填钉（工单 2026-08-26-sw-l1-mapping-backfill-workorder）。

2026-08-26 批：成员多数派推导（占比>=0.5 且标注成员>=8，08-25/08-26 两日一致）
补 176 条原为 None 的映射。三条纪律各配一钉：
1. 达标概念可查（宽度袋对照行不再「缺数」）；
2. 低于阈值的真跨行业概念**必须**保持 None——硬指行业比缺数更糟；
3. 既有条目不动（与成员多数派的已知分歧仍按静态表，改判走人工不走脚本）。
"""
from __future__ import annotations

from market_feature_store.sources.sector_mapping import board_to_sw_l1, lookup_sw_l1


def test_derived_mappings_are_queryable() -> None:
    assert lookup_sw_l1("光纤光缆") == "通信"
    assert lookup_sw_l1("农林牧渔") == "农林牧渔"


def test_cross_industry_concepts_stay_unmapped() -> None:
    # 08-26 实测多数派：海洋经济 35% / 超导概念 23%，低于 0.5 阈值。
    assert lookup_sw_l1("海洋经济") is None
    assert lookup_sw_l1("超导概念") is None


def test_existing_entries_untouched_by_derivation() -> None:
    # 成员多数派与静态表分歧的两条（电子化学品→电子 100%、维生素→医药生物 72.7%），
    # 本批不改判：既有条目是人工口径，翻案走人工评审。
    assert lookup_sw_l1("电子化学品") == "基础化工"
    assert lookup_sw_l1("维生素") == "基础化工"


def test_meirong_huli_key_added() -> None:
    # 申万2021 第 31 个一级行业「美容护理」原缺键，本批随推导补上。
    assert "美容护理" in set(board_to_sw_l1().values())
