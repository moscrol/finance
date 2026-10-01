"""scripts/harness_tier_gate.py：强模型不得退步、弱模型要有净增益。"""

from __future__ import annotations

import importlib.util
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
        ({"a"}, {"a", "b"}, {"a", "b", "c"}, {"a", "b", "c"}, "PASS"),
        ({"a"}, {"a"}, {"a", "b"}, {"a", "b"}, "WARN"),
        ({"a"}, {"b"}, {"c"}, {"c"}, "WARN"),
        ({"a"}, {"a", "b"}, {"a", "b", "c"}, {"a", "b", "d"}, "FAIL"),
        ({"a", "b"}, {"a"}, {"a"}, {"a"}, "FAIL"),
    ],
)
def test_verdicts(tg, wb, wn, sb, sn, expected) -> None:
    result = tg.gate(_mk(IDS, wb), _mk(IDS, wn), _mk(IDS, sb), _mk(IDS, sn))
    assert result["verdict"] == expected


def test_strong_regression_is_listed_even_if_rate_unchanged(tg) -> None:
    result = tg.gate(_mk(IDS, {"a"}), _mk(IDS, {"a", "b"}), _mk(IDS, {"c"}), _mk(IDS, {"d"}))
    assert result["verdict"] == "FAIL"
    assert result["strong_regressions"] == ["c"]
    assert result["strong"]["net"] == 0


def test_mismatched_case_ids_rejected(tg) -> None:
    with pytest.raises(tg.GateInputError):
        tg.compare({"a": True}, {"b": True}, label="x")


def test_content_correctness_report_is_expanded_to_all_cases(tg) -> None:
    ids = [c.id for c in cc.load_cases()]
    report = {"total": len(ids), "passed": len(ids) - 1, "failures": {ids[0]: ["x"]}}
    outcomes = tg.case_outcomes(report)
    assert set(outcomes) == set(ids)
    assert outcomes[ids[0]] is False
    assert all(outcomes[i] for i in ids[1:])


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
    assert tg.main(["check", *ok]) == 0
    bad = ok[:-1] + [write("sn2", {"a"})]
    assert tg.main(["check", *bad]) == 1
    missing = ok[:-1] + [str(tmp_path / "nope.json")]
    assert tg.main(["check", *missing]) == 2


def test_selftest_passes(tg) -> None:
    assert tg.main(["selftest"]) == 0
