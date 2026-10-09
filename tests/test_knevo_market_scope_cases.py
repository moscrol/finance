"""Validate revealed method cases, not model answer quality or production policy."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "intelligence/eval/fixtures/knevo_market_scope_20261010.json"


def test_scope_regression_declares_its_non_benchmark_boundary():
    suite = json.loads(FIXTURE.read_text())
    assert suite["status"] == "revealed_method_regression_not_benchmark"
    assert suite["evaluation_only"] is True
    cases = suite["cases"]
    assert len(cases) == len({case["id"] for case in cases}) == 8
    for case in cases:
        assert case["question"] and case["pass_rules"] and case["fail_rules"]
    assert {case.get("majority") for case in cases if "scope_inputs" in case} == {"yes", "no", "undetermined"}


def test_majority_oracles_cover_all_possible_missing_members():
    cases = json.loads(FIXTURE.read_text())["cases"]
    for case in cases:
        if "scope_inputs" not in case:
            continue
        total, observed, matching = (case["scope_inputs"][key] for key in ("total", "observed", "matching"))
        if total is None:
            assert case["expected_bounds"] is None
            assert case["majority"] == "undetermined"
            continue
        assert 0 <= matching <= observed <= total
        possible = [matching + count for count in range(total - observed + 1)]
        assert case["expected_bounds"] == [min(possible), max(possible)]
        outcomes = {2 * count > total for count in possible}
        expected = "yes" if outcomes == {True} else "no" if outcomes == {False} else "undetermined"
        assert case["majority"] == expected, case["id"]


def test_regression_questions_and_gold_are_not_embedded_in_runtime_skills():
    cases = json.loads(FIXTURE.read_text())["cases"]
    skills = [(ROOT / "skills" / name / "SKILL.md").read_text()
              for name in ("finance-mode", "finance-market-review")]
    for case in cases:
        for skill in skills:
            assert case["id"] not in skill
            assert case["question"] not in skill
