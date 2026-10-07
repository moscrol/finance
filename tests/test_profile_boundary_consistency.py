"""用合成画像检查边界口径；公开仓不依赖私人画像候选或快照。"""
from __future__ import annotations

import pytest

from scripts.check_profile_boundary_consistency import check, classify, main


def _profile() -> dict:
    return {
        "id": "synthetic",
        "anti_patterns": ["给交易建议"],
        "reasoning_patterns": [{"name": "示例", "rule": "不出买卖建议"}],
        "voice_guidance": "不输出仓位建议",
    }


def test_profile_boundary_three_blanket_loci_are_consistent():
    result = check(_profile())
    assert {x["where"] for x in result["loci"]} == {
        "anti_patterns[0]", "reasoning_patterns[0]", "voice_guidance",
    }
    assert result["consistent"] and result["verdicts"] == ["blanket"]


def test_profile_boundary_anti_pattern_is_itself_a_prohibition():
    assert classify("给交易建议", "anti_patterns[0]") == "blanket"
    assert classify("给交易建议", "voice_guidance") == "neutral"


def _scope(profile, field):
    note = "；输出按 output_policy 档位"
    if field == "anti_patterns":
        profile[field][0] += note
    elif field == "reasoning_patterns":
        profile[field][0]["rule"] += note
    else:
        profile[field] += note


@pytest.mark.parametrize("field", ["anti_patterns", "reasoning_patterns", "voice_guidance"])
@pytest.mark.parametrize("leave_behind", [False, True])
def test_profile_boundary_partial_update_is_inconsistent(field, leave_behind):
    profile = _profile()
    for f in ("anti_patterns", "reasoning_patterns", "voice_guidance"):
        if (f != field) if leave_behind else (f == field):
            _scope(profile, f)
    result = check(profile)
    assert not result["consistent"]
    assert set(result["verdicts"]) == {"blanket", "scoped"}


def test_profile_boundary_all_scoped_is_consistent():
    profile = _profile()
    for field in ("anti_patterns", "reasoning_patterns", "voice_guidance"):
        _scope(profile, field)
    result = check(profile)
    assert result["consistent"] and result["verdicts"] == ["scoped"]


def test_profile_boundary_empty_input_is_not_an_authorization():
    result = check({})
    assert result["loci"] == [] and result["verdicts"] == []
    # 这里只验文案一致性，不应把 consistent=True 当成调用权限。
    assert "authorized" not in result


def test_profile_boundary_cli_reports_conflict(tmp_path):
    import json

    profile = _profile()
    _scope(profile, "anti_patterns")
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    assert main([str(path)]) == 1
