from __future__ import annotations

import copy

import pytest

from intelligence import userspace
from intelligence.services import perspective_exam as exam
from intelligence.services import perspective_lab as lab
from intelligence.services import perspective_signals as signals

VALUE = "容量与逆势同时成立才列入观察"
POSITIVE = "容量方向正在分歧后修复，逻辑更清晰，逆势表现与主动性更强，尚需观察后续承接。"


@pytest.fixture
def profile():
    return {
        "id": "teacher", "display_name": "Teacher",
        "opportunity_preferences": [VALUE], "risk_triggers": ["库存风险"],
        "signal_match_rules": [{
            "field": "opportunity_preferences", "value_sha256": signals.value_sha256(VALUE),
            "all_of": [["容量方向", "容量板块"], ["分歧后修复", "分歧后的修复"],
                       ["逻辑更清晰", "逻辑性更强"], ["逆势表现", "逆势走强"],
                       ["主动性更强", "主动性增强"]],
            "none_of": ["承接不足", "逻辑被证伪"],
        }],
    }


def evaluate(profile, facts, question="怎么看"):
    return lab.evaluate_role(profile, facts=facts, question=question)


def test_all_conditions_and_aliases_match_without_mutation(profile):
    before = copy.deepcopy(profile)
    for text in (POSITIVE, POSITIVE.replace("容量方向", "容量板块").replace("逆势表现", "逆势走强")):
        result = evaluate(profile, text)
        assert result["direction"] == "opportunity"
        assert result["opportunity_hits"] == [VALUE]
    assert profile == before


@pytest.mark.parametrize("phrase", ["容量方向", "分歧后修复", "逻辑更清晰", "逆势表现", "主动性更强"])
def test_each_condition_is_required(profile, phrase):
    assert evaluate(profile, POSITIVE.replace(phrase, "待核实"))["opportunity_hits"] == []


@pytest.mark.parametrize("text", [
    POSITIVE.replace("逆势表现", "没有逆势表现"),
    POSITIVE.replace("逆势表现", "未见逆势表现"),
    POSITIVE.replace("逆势表现", "并非逆势表现"),
    POSITIVE.replace("逆势表现", "not 逆势表现"),
    POSITIVE.replace("主动性更强", "主动性并不更强"),
    POSITIVE.replace("逆势表现", "逆势表现消失"),
    POSITIVE.replace("逆势表现", "逆势表现可能存在"),
    POSITIVE + "但承接不足。",
    POSITIVE + "最新观察未见逆势表现。",
    "如果" + POSITIVE,
    "假设" + POSITIVE,
    "If " + POSITIVE,
    "`" + POSITIVE + "`",
    "传闻" + POSITIVE,
    "例如" + POSITIVE,
    "“" + POSITIVE + "”",
    POSITIVE.replace("。", "？"),
    POSITIVE.replace("，逻辑更清晰", "。另一标的逻辑更清晰"),
    POSITIVE.replace("，逻辑更清晰", "\n另一标的逻辑更清晰"),
    "容量方向正在分歧后修复，逻辑更清晰，但顺势走弱，主动性减弱。",
    "未确认逆势表现；" + POSITIVE,
    VALUE,  # Legacy whole-value match must not bypass the conditions.
])
def test_uncertain_negative_contrary_and_disjoint_facts_do_not_trigger(profile, text):
    result = evaluate(profile, text)
    assert result["opportunity_hits"] == []
    assert result["direction"] == "none"
    assert not result["abstain"]


def test_question_is_not_observed_evidence(profile):
    assert evaluate(profile, "没有市场事实", question=POSITIVE)["direction"] == "none"


def test_unconfigured_rules_still_use_legacy_matching(profile):
    profile.pop("signal_match_rules")
    assert evaluate(profile, "逆势同时成立才列入观察")["direction"] == "opportunity"


def test_other_fields_and_boundary_precedence_preserved(profile):
    assert evaluate(profile, POSITIVE + "库存风险。")["direction"] == "mixed"
    profile["honest_boundaries"] = ["财务审计"]
    result = evaluate(profile, POSITIVE, question="财务审计")
    assert result["direction"] == "abstain"
    assert result["opportunity_hits"] == result["risk_hits"] == []


def test_exam_uses_same_contract(profile):
    result = exam.score_case(profile, {
        "id": "ka-1", "kind": "known_answer", "question": "观察优先级？", "facts": POSITIVE,
        "expected_direction": "opportunity", "expected_field": "opportunity_preferences",
        "expected_terms": ["容量", "逆势"],
    })
    assert result["passed"]


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(signal_match_rules=None),
    lambda p: p["signal_match_rules"].append(copy.deepcopy(p["signal_match_rules"][0])),
    lambda p: p["signal_match_rules"][0].update(field="anti_patterns"),
    lambda p: p["signal_match_rules"][0].update(value_sha256="0" * 64),
    lambda p: p["signal_match_rules"][0].update(all_of=[]),
    lambda p: p["signal_match_rules"][0].update(all_of=[["容量"]]),
    lambda p: p["signal_match_rules"][0].update(all_of=[["容量"], []]),
    lambda p: p["signal_match_rules"][0].update(all_of=[["容"], ["逆势"]]),
    lambda p: p["signal_match_rules"][0].update(all_of=[["容量"], ["容量"]]),
    lambda p: p["signal_match_rules"][0].update(all_of=[["容量", " 容量 "], ["逆势"]]),
    lambda p: p["signal_match_rules"][0].update(none_of="否定"),
    lambda p: p["signal_match_rules"][0].update(extra="ignored typo"),
    lambda p: p["opportunity_preferences"].append(VALUE),
    lambda p: p["opportunity_preferences"].clear(),
    lambda p: p["opportunity_preferences"].__setitem__(0, VALUE + "改写"),
])
def test_invalid_contracts_fail_closed(profile, mutate):
    mutate(profile)
    with pytest.raises(ValueError):
        evaluate(profile, VALUE)


def test_save_validates_contract_and_ratchets_removal(profile, tmp_path, monkeypatch):
    monkeypatch.setenv(userspace.ENV_USERS_DIR, str(tmp_path))
    us = userspace.user_space("alice")
    lab.init_perspective(us, "teacher")
    lab._save_profile(us, profile)
    target = lab.profile_path(us, "teacher")
    original = target.read_bytes()
    bad = copy.deepcopy(profile)
    bad["opportunity_preferences"][0] += "改写"
    with pytest.raises(ValueError, match="absent"):
        lab._save_profile(us, bad)
    removed = copy.deepcopy(profile)
    removed.pop("signal_match_rules")
    with pytest.raises(lab.ProfileRegressionError, match="signal_match_rules"):
        lab._save_profile(us, removed)
    assert target.read_bytes() == original


def test_risk_contract_supported_and_bound_to_correct_field(profile):
    profile["signal_match_rules"][0]["field"] = "risk_triggers"
    profile["risk_triggers"], profile["opportunity_preferences"] = [VALUE], []
    assert evaluate(profile, POSITIVE)["direction"] == "risk"
