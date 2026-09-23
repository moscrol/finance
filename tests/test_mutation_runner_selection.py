"""The two parent branches expose different CLI selectors; keep both usable."""
import pytest

from scripts.review_probes.run_extraction_mutations import SUITES, _parse_args


@pytest.mark.parametrize("suite", tuple(SUITES))
def test_suite_selects_both_frozen_definitions_and_tests(suite):
    args = _parse_args(["--suite", suite, "--output", "unused-output"])
    assert (args.tests, args.definitions) == SUITES[suite]


def test_no_selector_still_runs_extraction():
    args = _parse_args(["--output", "unused-output"])
    assert (args.tests, args.definitions) == SUITES["extraction"]


def test_explicit_selectors_override_suite_without_mutating_defaults():
    before = {key: (list(tests), definitions) for key, (tests, definitions) in SUITES.items()}
    args = _parse_args([
        "--suite", "financial-r6", "--output", "unused-output",
        "--definitions", "scripts/review_probes/research_tail_union_mutations.json",
        "--tests", "intelligence/tests/test_research_tail_union_seams.py",
    ])
    assert args.tests == ["intelligence/tests/test_research_tail_union_seams.py"]
    assert args.definitions == "scripts/review_probes/research_tail_union_mutations.json"
    # The report label must not claim a frozen suite the run did not execute.
    assert args.suite == "custom"
    assert SUITES == before
    later = _parse_args(["--suite", "financial-r6", "--output", "unused-output"])
    assert (later.tests, later.definitions) == SUITES["financial-r6"]
    assert later.suite == "financial-r6"
