"""「未映射」是数据缺口，不能被写成一个方向名。

实测 2026-07-31：日报里写「双红集中在 未映射 等方向」「主要分布：未映射(30)」，
下游模型据此在答案里推出整整一段：

  「当日资金也主要集中在"未映射"方向，这意味着虽然短线热度强势，
    但底层板块的产业映射尚不清晰」

它在自信地解释一个 NULL。对研究工具来说这比答不出来更糟。

根因：dim_sector 630 个板块里 288 个（46%）没有 sw_l1，占位桶几乎总是排第一。
分组表格照常展示它（数据不隐藏），但凡是命名方向的句子必须排除它，并显式
把它标成缺口。
"""
from __future__ import annotations

from market_feature_store.reports.daily_review import (
    UNMAPPED_SW_L1,
    _focus_sw_l1,
    _named_groups,
    _unmapped_note,
)

GROUPS = [
    (UNMAPPED_SW_L1, [object(), object(), object()]),
    ("有色金属", [object(), object()]),
    ("医药生物", [object()]),
]


def test_named_groups_drop_the_placeholder() -> None:
    assert [sw for sw, _ in _named_groups(GROUPS)] == ["有色金属", "医药生物"]


def test_the_gap_is_stated_not_hidden() -> None:
    note = _unmapped_note(GROUPS)

    assert "3 个题材未映射" in note
    assert "数据缺口" in note
    assert "不构成方向" in note


def test_no_note_when_everything_is_mapped() -> None:
    assert _unmapped_note([("有色金属", [object()])]) == ""


def test_focus_never_names_the_placeholder() -> None:
    """「集中在 X 等方向」的 X 里不能出现占位符。"""
    focus = _focus_sw_l1({"industry_1": "电力设备"}, GROUPS)

    assert UNMAPPED_SW_L1 not in focus
    assert "电力设备" in focus


def test_all_unmapped_yields_no_direction_rather_than_a_fake_one() -> None:
    """全部未映射时，宁可说没有已映射方向，也不能把占位符当方向。"""
    only_unmapped = [(UNMAPPED_SW_L1, [object(), object()])]

    assert _named_groups(only_unmapped) == []
    assert "2 个题材未映射" in _unmapped_note(only_unmapped)
    assert UNMAPPED_SW_L1 not in _focus_sw_l1({}, only_unmapped)


def test_conclusion_does_not_degrade_into_a_dash_direction() -> None:
    """没有已映射方向时不能写「双红集中在 - 等方向」。

    那句话读起来仍像在给方向，只是方向名变成了一个短横；下游模型照样会拿它做归因。
    """
    from market_feature_store.reports.daily_review import _double_red_conclusion

    assert "集中在 电力设备 等方向" in _double_red_conclusion("电力设备")

    for empty in ("-", ""):
        out = _double_red_conclusion(empty)
        assert "集中在" not in out
        assert "无法给出行业级方向归因" in out
