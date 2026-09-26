"""Frozen suite selection and non-executing syntax validation for mutations."""
import shlex
import shutil
import subprocess

import pytest

from scripts.review_probes.run_extraction_mutations import SUITES, _parse_args, validate_source


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


def test_python_syntax_is_checked_without_execution():
    validate_source("raise RuntimeError('must not execute')\n", "example.py")
    with pytest.raises(SyntaxError):
        validate_source("def broken(\n", "example.py")


@pytest.mark.parametrize("shell", ["zsh", "bash", "sh"])
def test_shell_syntax_is_checked_without_execution(tmp_path, shell):
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} is unavailable")
    sentinel = tmp_path / "must not exist"
    source = f"#!/usr/bin/env {shell}\nprintf executed > {shlex.quote(str(sentinel))}\n"
    validate_source(source, "example.sh")
    assert not sentinel.exists()
    with pytest.raises(subprocess.CalledProcessError):
        validate_source(f"#!/usr/bin/env {shell}\nif true; then\n", "example.sh")


@pytest.mark.parametrize("source", ["pass\n", "#!/usr/bin/env python\npass\n"])
def test_shell_mutation_rejects_missing_or_unsupported_shebang(source):
    with pytest.raises(ValueError, match="supported shebang"):
        validate_source(source, "example.sh")
