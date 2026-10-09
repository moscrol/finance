"""用合成文本检查拆分、待裁定标记、内容还原和同输入 ID 稳定性。

测试不读取私人画像或快照；这里只验证文本处理契约，不验证金融判据。
"""

from __future__ import annotations

import pytest

from scripts.split_monolithic_lens import split_description, split_lens, verify_lossless


def test_plain_semicolon_list_splits_one_rule_per_clause() -> None:
    text = "温度超过上限才标记异常；电量低于阈值需要检查电池；传感器离线转人工复核"
    rules = split_description(text)
    assert [r["text"] for r in rules] == text.split("；")
    assert all(r["status"] == "clear" for r in rules)


def test_condition_and_conclusion_joined_by_comma_stay_in_one_rule() -> None:
    rules = split_description("温度超过上限需要确认传感器，确认有效后才发送通知；设备断电后必须检查备用电源")
    assert len(rules) == 2
    assert "确认有效后才发送通知" in rules[0]["text"]
    assert all(r["status"] == "clear" for r in rules)


def test_conclusion_severed_by_a_semicolon_is_flagged_not_silently_split() -> None:
    rules = split_description("必须先检查温度传感器是否有效；否则不发送异常通知")
    assert len(rules) == 2
    assert rules[1]["status"] == "needs_review"
    assert "否则" in rules[1]["review_reasons"][0]
    assert "后半截" in rules[1]["review_reasons"][0]


def test_bare_noun_phrase_fragment_is_flagged() -> None:
    rules = split_description("设备状态=已连接且有足够电量；待机状态；所有通道必须可用")
    assert rules[1]["text"] == "待机状态"
    assert rules[1]["status"] == "needs_review"
    assert "名词短语" in rules[1]["review_reasons"][0]


def test_semicolon_inside_parentheses_is_flagged_by_bracket_check() -> None:
    rules = split_description("设备状态（电源必须正常；传感器必须在线）同时满足")
    assert any(r["status"] == "needs_review" for r in rules)
    assert any("括号" in reason for r in rules for reason in r["review_reasons"])


def test_lossless_check_actually_fails_when_a_rule_is_dropped() -> None:
    original = "甲；乙；丙"
    rules = split_description(original)
    verify_lossless(original, rules)
    with pytest.raises(AssertionError, match="拆分不可逆"):
        verify_lossless(original, rules[:-1])


def test_lossless_check_fails_when_text_is_quietly_edited() -> None:
    original = "设备在线才发送通知；电量不足需要检查电池"
    rules = split_description(original)
    rules[0]["text"] = rules[0]["text"].replace("才", "不")
    with pytest.raises(AssertionError, match="拆分不可逆"):
        verify_lossless(original, rules)


@pytest.fixture
def synthetic_profile() -> dict:
    return {
        "id": "synthetic",
        "market_lenses": [
            {
                "name": name,
                "description": "；".join(f"第{i}路{name}读数超出阈值才需要标记异常" for i in range(size)),
                "weight": 0.5,
            }
            for name, size in (("温度", 35), ("电量", 45))
        ],
    }


def test_long_lenses_split_losslessly(synthetic_profile) -> None:
    total = 0
    for lens in synthetic_profile["market_lenses"]:
        out = split_lens(synthetic_profile, lens["name"], profile_id="synthetic")
        assert [r["text"] for r in out["rules"]] == lens["description"].split("；")
        assert out["rule_count"] == len(out["rules"])
        assert all(r["rule_id"].startswith(f"synthetic.{lens['name']}.") for r in out["rules"])
        assert len({r["rule_id"] for r in out["rules"]}) == out["rule_count"]
        assert all(len(r["text_sha256"]) == 12 for r in out["rules"])
        total += out["rule_count"]
    assert total == 80


def test_rule_ids_are_stable_across_runs(synthetic_profile) -> None:
    a = split_lens(synthetic_profile, "温度", profile_id="synthetic")
    b = split_lens(synthetic_profile, "温度", profile_id="synthetic")
    assert [r["rule_id"] for r in a["rules"]] == [r["rule_id"] for r in b["rules"]]
    assert [r["text_sha256"] for r in a["rules"]] == [r["text_sha256"] for r in b["rules"]]


@pytest.mark.parametrize("description", [
    "独立样本甲需要复查，确认后才入库；证据不足必须停在待核验",
    "资料齐全才进入下一步；否则需要补充资料；暂停状态",
])
def test_other_text_shapes_split_losslessly_too(description: str) -> None:
    profile = {"market_lenses": [{"name": "样本", "description": description}]}
    out = split_lens(profile, "样本", profile_id="synthetic")
    assert out["rule_count"] >= 1
    assert out["clear"] + out["needs_review"] == out["rule_count"]
    verify_lossless(description, out["rules"])
