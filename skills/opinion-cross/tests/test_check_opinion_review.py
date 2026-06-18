#!/usr/bin/env python3
"""check_opinion_review.validate 的单元测试（可 pytest，也可直接 python3 跑）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_opinion_review as cor  # noqa: E402


def _machine() -> dict:
    return {
        "term": "CPO",
        "opportunities": [
            {
                "target": "罗博特科",
                "resonance_tier": "Tier 2：双重验证 ⭐⭐",
                "hardness": {"dominant": "硬证据", "hard": ["…订单已超过15个亿…"],
                             "soft": ["CPO首选标的…罗博特科"], "noise": []},
            },
            {
                "target": "兆驰股份",
                "resonance_tier": "Tier 2：双重验证 ⭐⭐",
                "hardness": {"dominant": "硬证据", "hard": ["…3.35亿合同…"],
                             "soft": [], "noise": []},
            },
            {
                "target": "新易盛",
                "resonance_tier": "Tier 3：观察池 ⭐",
                "hardness": {"dominant": "软推演", "hard": [],
                             "soft": ["CPO 弹性首选"], "noise": []},
            },
        ],
    }


def _review() -> dict:
    return {
        "reviewed": [
            {"target": "罗博特科", "final_tier": "Tier 2", "anaphora_checked": True,
             "market_heat": "待补", "note": "光通信订单 15 亿，硬证据归属正确"},
            {"target": "兆驰股份", "final_tier": "Tier 2", "anaphora_checked": True,
             "market_heat": "待补", "note": "3.35 亿合同，归属正确"},
        ]
    }


def test_valid_passes():
    assert cor.validate(_machine(), _review()) == []


def test_missing_hard_evidence_review_fails():
    m, r = _machine(), _review()
    r["reviewed"] = [x for x in r["reviewed"] if x["target"] != "罗博特科"]
    issues = cor.validate(m, r)
    assert any("罗博特科" in i for i in issues)


def test_hard_evidence_anaphora_not_checked_fails():
    m, r = _machine(), _review()
    for x in r["reviewed"]:
        if x["target"] == "兆驰股份":
            x["anaphora_checked"] = False
    issues = cor.validate(m, r)
    assert any("兆驰股份" in i and "anaphora_checked" in i for i in issues)


def test_soft_target_not_required():
    # 新易盛是软推演（无硬证据），不在复核里也不该报错
    m = {"opportunities": [{"target": "新易盛", "resonance_tier": "Tier 3：观察池",
                            "hardness": {"dominant": "软推演", "hard": [], "soft": ["x"], "noise": []}}]}
    assert cor.validate(m, {"reviewed": []}) == []


def test_invalid_final_tier_fails():
    m, r = _machine(), _review()
    r["reviewed"][0]["final_tier"] = "Tier 9"
    issues = cor.validate(m, r)
    assert any("final_tier" in i for i in issues)


def test_non_bool_anaphora_checked_fails():
    m, r = _machine(), _review()
    r["reviewed"][0]["anaphora_checked"] = "true"
    issues = cor.validate(m, r)
    assert any("anaphora_checked" in i for i in issues)


def test_missing_market_heat_fails():
    m, r = _machine(), _review()
    r["reviewed"][0]["market_heat"] = ""
    issues = cor.validate(m, r)
    assert any("market_heat" in i for i in issues)


def test_missing_note_fails():
    m, r = _machine(), _review()
    del r["reviewed"][0]["note"]
    issues = cor.validate(m, r)
    assert any("note" in i for i in issues)


def test_reviewed_missing_target_fails():
    m = _machine()
    r = {"reviewed": [{"final_tier": "Tier 2", "anaphora_checked": True,
                       "market_heat": "待补", "note": "x"}]}
    issues = cor.validate(m, r)
    assert any("缺 target" in i for i in issues)


def test_missing_opportunities_key_fails():
    assert cor.validate({"term": "x"}, {"reviewed": []}) != []


def test_missing_reviewed_key_fails():
    assert cor.validate(_machine(), {}) != []


def _run_standalone() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_standalone())
