"""Local score comparison is not generic-benefit acceptance."""

from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path

import pytest

from intelligence.eval import content_correctness as cc

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def tg():
    spec = importlib.util.spec_from_file_location("harness_tier_gate", REPO / "scripts" / "harness_tier_gate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _mk(ids, passed):
    return {i: i in passed for i in ids}


IDS = ["a", "b", "c", "d"]


@pytest.mark.parametrize(
    "wb,wn,sb,sn,expected",
    [
        ({"a"}, {"a", "b"}, {"a", "b", "c"}, {"a", "b", "c"}, "INCONCLUSIVE"),
        ({"a"}, {"a"}, {"a", "b"}, {"a", "b"}, "INCONCLUSIVE"),
        ({"a"}, {"b"}, {"c"}, {"c"}, "FAIL"),
        ({"a"}, {"a", "b"}, {"a", "b", "c"}, {"a", "b", "d"}, "FAIL"),
        ({"a", "b"}, {"a"}, {"a"}, {"a"}, "FAIL"),
    ],
)
def test_verdicts(tg, wb, wn, sb, sn, expected) -> None:
    result = tg.gate(_mk(IDS, wb), _mk(IDS, wn), _mk(IDS, sb), _mk(IDS, sn))
    assert result["verdict"] == expected


def test_all_two_case_boolean_combinations_keep_per_case_regressions(tg) -> None:
    for bits in itertools.product((False, True), repeat=8):
        arms = [dict(zip(("a", "b"), bits[i:i + 2])) for i in range(0, 8, 2)]
        result = tg.gate(*arms)
        broken = any(base[key] and not new[key] for base, new in (arms[:2], arms[2:]) for key in base)
        assert result["verdict"] == ("FAIL" if broken else "INCONCLUSIVE")
        assert result["acceptance"] == "not_established"


def test_strong_regression_is_listed_even_if_rate_unchanged(tg) -> None:
    result = tg.gate(_mk(IDS, {"a"}), _mk(IDS, {"a", "b"}), _mk(IDS, {"c"}), _mk(IDS, {"d"}))
    assert result["verdict"] == "FAIL"
    assert result["strong_regressions"] == ["c"]
    assert result["strong"]["net"] == 0


def test_mismatched_case_ids_rejected(tg) -> None:
    with pytest.raises(tg.GateInputError):
        tg.compare({"a": True}, {"b": True}, label="x")


@pytest.mark.parametrize("kind", ["valid", "wrong_class", "wrong_rate", "foreign_ids", "bad_failure_reason"])
def test_summary_without_explicit_case_ids_is_not_pairable(tg, tmp_path: Path, capsys, kind: str) -> None:
    # Even an internally consistent summary erases the IDs of all passed cases.
    prefix = "foreign-" if kind == "foreign_ids" else ""
    report = cc.summarize([
        cc.CaseResult(prefix + case.id, case.error_class, True, []) for case in cc.load_cases()
    ])
    if kind == "wrong_class":
        report["by_class"][next(iter(report["by_class"]))]["passed"] = 0
    elif kind == "wrong_rate":
        report["pass_rate"] = 0.0
    elif kind == "bad_failure_reason":
        report["passed"] -= 1
        report["failures"] = {cc.load_cases()[0].id: "not-a-list"}
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    args = ["check", "--json"]
    for flag in ("weak-base", "weak-new", "strong-base", "strong-new"):
        args.extend(["--" + flag, str(path)])
    assert tg.main(args) == 2
    output = capsys.readouterr()
    assert not output.out
    assert "cases" in output.err


@pytest.mark.parametrize("field,value", [
    ("total", 1), ("passed", 1), ("failures", {}),
    ("by_class", {"x": {"n": 1, "passed": 0}}), ("pass_rate", 0.0),
])
def test_cases_cannot_hide_any_summary_field(tg, field: str, value: object) -> None:
    with pytest.raises(tg.GateInputError):
        tg.case_outcomes({"cases": {"a": True}, field: value})


def test_explicit_cases_do_not_load_current_question_set(tg, monkeypatch) -> None:
    def no_inference():
        pytest.fail("comparison must use the input's case IDs, not today's question set")

    monkeypatch.setattr(cc, "load_cases", no_inference)
    assert tg.case_outcomes({"cases": {"unrelated-id": False}}) == {"unrelated-id": False}


@pytest.mark.parametrize("report", [{}, {"metadata": "not outcomes"}])
def test_missing_cases_is_input_error(tg, report) -> None:
    with pytest.raises(tg.GateInputError, match="cases"):
        tg.case_outcomes(report)


def test_content_correctness_report_with_stale_total_rejected(tg) -> None:
    with pytest.raises(tg.GateInputError):
        tg.case_outcomes({"total": 3, "passed": 3, "failures": {}})


def test_cli_exit_codes(tg, tmp_path: Path) -> None:
    def write(name, passed):
        path = tmp_path / name
        path.write_text(json.dumps({"cases": _mk(IDS, passed)}), encoding="utf-8")
        return str(path)

    ok = ["--weak-base", write("wb", {"a"}), "--weak-new", write("wn", {"a", "b"}),
          "--strong-base", write("sb", {"a", "b"}), "--strong-new", write("sn", {"a", "b"})]
    assert tg.main(["check", *ok]) == 3
    bad = ok[:-1] + [write("sn2", {"a"})]
    assert tg.main(["check", *bad]) == 1
    missing = ok[:-1] + [str(tmp_path / "nope.json")]
    assert tg.main(["check", *missing]) == 2


def test_selftest_passes(tg) -> None:
    assert tg.main(["selftest"]) == 0
