"""Reproduce a rejected experiment; green tests do not certify its semantics."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import perspective_signal_candidate as signals

ROOT = Path(__file__).resolve().parents[1]
VALUE = "容量与逆势同时成立才列入观察"
POSITIVE = "容量方向正在分歧后修复，逻辑更清晰，逆势表现与主动性更强，尚需观察后续承接。"


@pytest.fixture
def profile():
    return {
        "opportunity_preferences": [VALUE],
        "signal_match_rules": [{
            "field": "opportunity_preferences", "value_sha256": signals.value_sha256(VALUE),
            "all_of": [["容量方向", "容量板块"], ["分歧后修复", "分歧后的修复"],
                       ["逻辑更清晰", "逻辑性更强"], ["逆势表现", "逆势走强"],
                       ["主动性更强", "主动性增强"]],
            "none_of": ["承接不足", "逻辑被证伪"],
        }],
    }


def match(profile, facts):
    return signals.matches(next(iter(signals.validated_rules(profile).values())), facts)


def test_literal_controls_do_not_mutate_profile(profile):
    before = copy.deepcopy(profile)
    for text in (POSITIVE, POSITIVE.replace("逆势表现", "逆势走强")):
        assert match(profile, text)
    assert profile == before


@pytest.mark.parametrize("phrase", ["容量方向", "分歧后修复", "逻辑更清晰", "逆势表现", "主动性更强"])
def test_each_literal_group_is_required(profile, phrase):
    assert not match(profile, POSITIVE.replace(phrase, "待核实"))


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
    "如果" + POSITIVE, "假设" + POSITIVE, "If " + POSITIVE,
    "`" + POSITIVE + "`", "传闻" + POSITIVE, "例如" + POSITIVE,
    "“" + POSITIVE + "”", POSITIVE.replace("。", "？"),
    POSITIVE.replace("，逻辑更清晰", "。另一标的逻辑更清晰"),
    POSITIVE.replace("，逻辑更清晰", "\n另一标的逻辑更清晰"),
    "容量方向正在分歧后修复，逻辑更清晰，但顺势走弱，主动性减弱。",
    "未确认逆势表现；" + POSITIVE, VALUE,
])
def test_original_literal_guards_are_reproducible(profile, text):
    assert not match(profile, text)


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
def test_invalid_diagnostic_contracts_fail_closed(profile, mutate):
    mutate(profile)
    with pytest.raises(ValueError):
        match(profile, VALUE)


def test_frozen_semantic_failures_remain_visible_not_approved():
    candidate = json.loads((ROOT / "docs/verification/2026-09-25-spt-signal-contract/candidate.json").read_text())
    suite = json.loads((ROOT / "docs/verification/2026-09-25-spt-contract-challenge/challenges.json").read_text())
    result = signals.challenge(candidate["entries"][0]["rule"], suite["cases"])
    assert result["status"] == "FAIL"
    assert (result["passed"], result["failed"]) == (4, 8)
    assert {r["id"] for r in result["cases"] if not r["passed"]} == {
        "same-sentence-different-subjects", "different-time-windows", "unverified-observations",
        "criteria-not-observations", "denial-by-reference", "withdrawal-by-reference",
        "future-uncertainty-not-current-denial", "quoted-label-not-quoted-claim",
    }
    assert "容量方向" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("cases", [None, [], [{}], ["bad"],
    [{"id": "x", "facts": "private", "expected_match": "false"}],
    [{"id": "x", "facts": "", "expected_match": False}],
    [{"id": "x", "facts": "private", "expected_match": False}] * 2,
])
def test_invalid_challenges_fail_closed(profile, cases):
    with pytest.raises(ValueError):
        signals.challenge(profile["signal_match_rules"][0], cases)
