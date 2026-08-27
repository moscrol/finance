"""KC-06：第二跳 target 从窄命中/邻居抽取，不拍脑袋。"""
from __future__ import annotations

from intelligence.services.hop_retrieval import (
    SECOND_HOP_MARK,
    SECOND_HOP_SLOT_RESERVE,
    SECOND_HOP_TARGET_CAP,
    extract_second_hop_targets,
    reserve_second_hop_slots,
)


def test_extract_orders_by_frequency_then_lexicon() -> None:
    texts = (
        "光刻胶配方依赖树脂和光引发剂，树脂决定耐蚀性",
        "树脂与单体配比，光引发剂用量影响灵敏度",
        "上游还有光引发剂供应商",
    )
    lexicon = ("光刻胶", "树脂", "光引发剂", "单体", "晶圆厂")
    assert extract_second_hop_targets(
        texts,
        lexicon,
        exclude=("光刻胶",),
    ) == ("树脂", "光引发剂", "单体")


def test_extract_caps_second_hop_targets_at_three() -> None:
    texts = ("甲 乙 丙 丁 戊 甲 乙 丙 丁 戊",)
    lexicon = ("甲", "乙", "丙", "丁", "戊")
    assert extract_second_hop_targets(texts, lexicon) == ("甲", "乙", "丙")
    assert SECOND_HOP_TARGET_CAP == 3


def test_neighbors_can_seed_when_evidence_texts_are_empty() -> None:
    lexicon = ("树脂", "光引发剂", "南大光电")
    assert extract_second_hop_targets(
        (),
        lexicon,
        neighbors=("南大光电", "树脂", "无关词"),
        exclude=("光刻胶",),
    ) == ("树脂", "南大光电")


def test_extract_skips_blank_and_excluded_and_stays_deterministic() -> None:
    assert extract_second_hop_targets(("树脂",), ("", "  ", "树脂"), exclude=("树脂",)) == ()
    first = extract_second_hop_targets(("单体 树脂",), ("单体", "树脂"))
    second = extract_second_hop_targets(("单体 树脂",), ("单体", "树脂"))
    assert first == second == ("单体", "树脂")
    assert SECOND_HOP_MARK == "〔第2跳〕"


def test_reserve_second_hop_keeps_one_when_first_hop_fills_window() -> None:
    assert SECOND_HOP_SLOT_RESERVE == 1
    assert reserve_second_hop_slots(
        [f"h1-{i}" for i in range(8)],
        ["h2-a", "h2-b"],
        room=8,
    ) == [f"h1-{i}" for i in range(7)] + ["h2-a"]
    assert reserve_second_hop_slots(["h1"], ["h2-a", "h2-b"], room=8) == [
        "h1",
        "h2-a",
        "h2-b",
    ]
