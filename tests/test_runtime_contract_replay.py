"""The host must reject harness errors, missing cases and non-semantic reds."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from scripts.review_probes import run_runtime_contract_checks as runner


def xml(path, cases):
    suite = ET.Element("testsuite")
    for name, tag, message in cases:
        case = ET.SubElement(suite, "testcase", classname="probe", name=name)
        if tag:
            ET.SubElement(case, tag, message=message).text = message
    ET.ElementTree(suite).write(path)


@pytest.fixture
def sample(tmp_path):
    (tmp_path / "results.json").write_text(json.dumps({"complete": True, "final_status": ""}))
    (tmp_path / "definitions.json").write_text(json.dumps([
        {"id": "fence", "targets": ["test_guard"]},
    ]))
    green = [("test_guard", "", ""), ("test_control", "", "")]
    xml(tmp_path / "baseline.xml", green)
    xml(tmp_path / "restored-full.xml", green)
    xml(tmp_path / "fence-green.xml", green[:1])
    xml(tmp_path / "fence-red.xml", [("test_guard", "failure", "assert False")])
    return tmp_path


def test_accepts_pytest_assertion_without_optional_xml_type(sample):
    result = runner.audit(sample)
    assert result["accepted"] and result["baseline"] == 2
    assert result["mutations"][0]["failures"][0]["name"] == "test_guard"


@pytest.mark.parametrize("cases", [
    [("test_guard", "", "")],
    [("test_guard", "error", "collection failed")],
    [("test_guard", "skipped", "not run")],
    [("test_guard", "failure", "ModuleNotFoundError: missing dependency")],
    [("test_other", "failure", "assert False")],
    [("test_guard", "failure", "assert False"), ("test_guard", "", "")],
    [],
])
def test_rejects_survivor_errors_skips_wrong_or_missing_cases(sample, cases):
    xml(sample / "fence-red.xml", cases)
    with pytest.raises(AssertionError):
        runner.audit(sample)


@pytest.mark.parametrize("stage", ["baseline", "fence-green", "restored-full"])
def test_rejects_red_baseline_or_restoration(sample, stage):
    xml(sample / (stage + ".xml"), [("test_guard", "failure", "assert False")])
    with pytest.raises(AssertionError):
        runner.audit(sample)


def test_drain_witness_must_observe_close_not_a_missing_lock_hook(sample):
    ident = "inbox_suspend_does_not_drain_delivery"
    (sample / "definitions.json").write_text(json.dumps([
        {"id": ident, "targets": ["test_guard"]},
    ]))
    (sample / "fence-green.xml").rename(sample / (ident + "-green.xml"))
    red = sample / (ident + "-red.xml")
    xml(red, [("test_guard", "failure", "assert False\n + where False = wait(10)")])
    with pytest.raises(AssertionError, match="not a semantic witness"):
        runner.audit(sample)
    xml(red, [("test_guard", "failure", "Failed: DID NOT RAISE <class 'TimeoutError'>")])
    assert runner.audit(sample)["accepted"]


@pytest.mark.parametrize("definition", [group[0] for group in runner.GROUPS.values()])
def test_registered_runtime_mutations_still_match_unique_compilable_guards(definition):
    root = Path(__file__).resolve().parents[1]
    runner.validate_definitions(root, root / "scripts/review_probes" / definition)


@pytest.mark.parametrize("source,new", [("x = 2\n", "x = 3"), ("x = 1\nx = 1", "x = 3"), ("x = 1", "x = (")])
def test_preflight_rejects_stale_duplicate_or_invalid_mutation(tmp_path, source, new):
    (tmp_path / "module.py").write_text(source)
    definitions = tmp_path / "definitions.json"
    definitions.write_text(json.dumps([{"id": "guard", "path": "module.py", "old": "x = 1", "new": new}]))
    with pytest.raises((ValueError, SyntaxError)):
        runner.validate_definitions(tmp_path, definitions)


def test_output_refuses_candidate_overlap(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["replay", "--candidate", str(tmp_path),
                                   "--expect-revision", "sha", "--group", "writer",
                                   "--output", str(tmp_path / "bad")])
    with pytest.raises(SystemExit) as result:
        runner.main()
    assert result.value.code == 2
    assert not (tmp_path / "bad").exists()


def test_output_never_overwrites_prior_evidence(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "raw.log"
    sentinel.write_bytes(b"first failure")
    monkeypatch.setattr(runner, "identity", lambda _: {"revision": "sha", "status": ""})
    original_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda p: str(p) == "/usr/bin/sandbox-exec" or original_exists(p))
    monkeypatch.setattr("sys.argv", ["replay", "--candidate", str(candidate),
                                   "--expect-revision", "sha", "--group", "writer",
                                   "--output", str(output)])
    with pytest.raises(FileExistsError):
        runner.main()
    assert sentinel.read_bytes() == b"first failure"
