"""The probe runner must reject unrelated reds, survivors, and unsafe outputs."""
from __future__ import annotations

import fnmatch
import importlib.util
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/review_probes/runtime_identity_effects/run_checks.py"
spec = importlib.util.spec_from_file_location("runtime_identity_effects_probe", SCRIPT)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize(
    ("kind", "name", "message", "expected", "total", "accepted"),
    [
        (None, "witness", "", set(), 2, True),
        ("failure", "witness", "Failed: DID NOT RAISE <class 'ValueError'>", {"witness"}, 2, True),
        (None, "witness", "", {"witness"}, 2, False),
        ("failure", "other", "Failed: DID NOT RAISE <class 'ValueError'>", {"witness"}, 2, False),
        ("failure", "witness", "TypeError: fixture broke", {"witness"}, 2, False),
        ("error", "witness", "ImportError: collection failed", {"witness"}, 2, False),
        ("skipped", "witness", "not run", set(), 2, False),
        (None, "witness", "", set(), 3, False),
    ],
)
def test_junit_requires_named_behavioral_failures(tmp_path, kind, name, message, expected, total, accepted):
    suite = ET.Element("testsuite")
    witness = ET.SubElement(suite, "testcase", name=name)
    ET.SubElement(suite, "testcase", name="positive_control")
    if kind:
        ET.SubElement(witness, kind, message=message)
    xml = tmp_path / "junit.xml"
    ET.ElementTree(suite).write(xml)
    assert runner.junit_verdict(xml, expected, total)["accepted"] is accepted


def _arguments(monkeypatch, candidate, output):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--candidate", str(candidate),
                                     "--expect-revision", "expected", "--output", str(output)])


def test_existing_output_preserves_first_failure(tmp_path, monkeypatch):
    candidate, output = tmp_path / "candidate", tmp_path / "output"
    output.mkdir()
    evidence = output / "first-red.log"
    evidence.write_text("first failure")
    _arguments(monkeypatch, candidate, output)
    monkeypatch.setattr(runner, "identity", lambda _: {"revision": "expected", "status": ""})
    with pytest.raises(FileExistsError):
        runner.main()
    assert evidence.read_text() == "first failure"
    assert sorted(p.name for p in output.iterdir()) == ["first-red.log"]


@pytest.mark.parametrize("observed", [
    {"revision": "wrong", "status": ""},
    {"revision": "expected", "status": " M source.py"},
])
def test_candidate_must_be_exact_and_clean(tmp_path, monkeypatch, observed):
    output = tmp_path / "output"
    _arguments(monkeypatch, tmp_path / "candidate", output)
    monkeypatch.setattr(runner, "identity", lambda _: observed)
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert not output.exists()


def test_probes_require_explicit_selection(pytestconfig):
    patterns = pytestconfig.getini("python_files")
    for path in runner.PROBE.glob("*.py"):
        assert not any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)


def test_output_cannot_be_inside_candidate(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    _arguments(monkeypatch, candidate, candidate / "output")
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert not candidate.exists()
