"""Counterexamples for R-20260827-14 P0 (no user or network data)."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.audit_tool_usage_differential import analyze, load_manifest, render_markdown


def episode(root: Path, user: str, day: str, checks: list[dict] | None,
            events: list[dict], *, revision: str | None = None) -> Path:
    run = root / user / "runs" / f"run_{day}_120000_123456"
    run.mkdir(parents=True)
    path = run / "continuous-episode.json"
    doc = {"events": events}
    if checks is not None:
        doc["satisfiability_precheck"] = {"checks": checks}
    if revision:
        doc["code_revision"] = revision
    path.write_text(json.dumps(doc))
    return path


def check(output: str, *tools: str, status: str = "ready") -> dict:
    return {"output_id": output, "contributing_tools": list(tools), "status": status}


def event(kind: str, name: str) -> dict:
    return {"kind": kind, "payload": {"name": name}}


def test_requests_not_results_and_errors_still_count_as_called(tmp_path: Path):
    paths = [
        episode(tmp_path, "a77", "20260826", [check("first", "kb_search"),
                check("missing", "web_search"), check("unknown", status="suspicious")],
                [event("tool_request", "kb_search"), event("tool_error", "kb_search")],
                revision="rev-a"),
        episode(tmp_path, "probe-one", "20260827", [check("second", "kb_search")],
                [event("tool_result", "kb_search")]),
        episode(tmp_path, "default", "20260828", [], [event("tool_request", "kb_search")]),
        episode(tmp_path, "default", "20260829", None, []),
    ]
    r = analyze(paths)
    assert r["scope"]["sample_files"] == 4
    assert r["scope"]["missing_precheck"] == 1
    assert r["scope"]["probe_or_other_dirs"] == 1
    assert r["scope"]["code_revision_known_runs"] == 1
    assert r["run_counts"]["with_checks"] == 2
    assert r["run_counts"]["computable"] == 2
    assert r["run_counts"]["with_uncalled"] == 2
    assert r["tool_counts"]["kb_search"]["declared_runs"] == 2  # not 4 total
    assert r["tool_counts"]["kb_search"]["uncalled_runs"] == 1
    assert r["output_instances"]["declared_without_request"] == 2
    assert r["output_instances"]["suspicious_without_declaration"] == 1
    assert r["output_instances"]["by_output_id"] == {"missing": 1, "second": 1}
    text = render_markdown(r)
    assert "2；声明盲区 suspicious 1" in text
    assert "rev-a" in text and "1 / 4" in text


def test_filters_use_run_date_and_user_exact_not_mtime(tmp_path: Path):
    a = episode(tmp_path, "a77", "20260824", [check("one", "kb_search")], [])
    b = episode(tmp_path, "probe-one", "20260827", [check("two", "kb_search")], [])
    a.touch()  # Today's mtime must not change its cohort.
    r = analyze([a, b], since="2026-08-25")
    assert r["scope"]["sample_files"] == 1
    assert r["scope"]["date_min"] == "2026-08-27"
    assert r["tool_counts"]["kb_search"]["declared_runs"] == 1
    assert analyze([a, b], user="a77")["scope"]["sample_files"] == 1
    assert analyze([a, b], user="a")["scope"]["sample_files"] == 0


def test_manifest_freezes_exact_bytes_and_rejects_drift(tmp_path: Path):
    path = episode(tmp_path, "probe", "20260826", [check("x", "kb_search")], [])
    rel = path.relative_to(tmp_path).as_posix()
    doc = {"count": 1, "basis": "synthetic frozen cohort", "files": [
        {"relative_path": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
    manifest = tmp_path / "sample.json"
    manifest.write_text(json.dumps(doc))
    files, digest, basis = load_manifest(manifest, tmp_path)
    assert files == [path] and len(digest) == 64
    assert basis == "synthetic frozen cohort"
    assert analyze(files)["scope"]["sample_files"] == 1
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_manifest(manifest, tmp_path)
    doc["files"][0]["relative_path"] = "../other/runs/run_20260826_120000_123456/continuous-episode.json"
    manifest.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="unsafe"):
        load_manifest(manifest, tmp_path)


def test_multiple_contributors_one_called_not_an_instance_gap(tmp_path: Path):
    p = episode(tmp_path, "a77", "20260826", [check("x", "kb_search", "web_search")],
                [event("tool_request", "web_search"), event("tool_error", "web_search")])
    r = analyze([p])
    assert r["output_instances"]["declared_without_request"] == 0
    assert r["run_counts"]["with_uncalled"] == 1  # kb_search was not called
    assert r["tool_counts"]["kb_search"]["uncalled_runs"] == 1
    assert r["tool_counts"]["web_search"]["uncalled_runs"] == 0
