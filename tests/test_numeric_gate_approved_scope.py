"""Explicitly approved non-candidates must not erase the scanned population or failures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_numeric_gate_label_ab import NEW_ROW, RESTATEMENT, _write_receipt, ab


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_digest(paths):
    pairs = sorted((str(p.resolve()), sha(p)) for p in paths)
    return hashlib.sha256(
        json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def write_manifest(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return sha(path)


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "users"
    good = _write_receipt(root, RESTATEMENT, NEW_ROW)
    bad = root / "u1/runs/run_20260929_130000_000002/continuous-episode.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{}")
    for name in ("run.json", "report.json"):
        (bad.parent / name).write_text('{"status":"failed"}')
    (bad.parent / "answer.md").write_text("No research answer")
    row = ab.replay_ab(bad, ab.DEFAULT_RELABELS)
    assert row["error"]
    entry = {
        "path": str(bad.resolve()),
        "run": bad.parent.name,
        "input_sha256": sha(bad),
        "classification": "failed_without_public_research_answer",
        "expected_replay_error": row["error"],
        "files": {
            name: {
                "sha256": sha(bad.parent / name),
                "bytes": (bad.parent / name).stat().st_size,
            }
            for name in (
                "continuous-episode.json",
                "run.json",
                "report.json",
                "answer.md",
            )
        },
    }
    data = {
        "schema": "numeric_gate_non_candidates_v1",
        "approved_by_user": True,
        "approval_ref": "explicit-test-authorization",
        "scan_count": 2,
        "scan_sha256": scan_digest([good, bad]),
        "approved_count": 1,
        "entries": [entry],
    }
    manifest = tmp_path / "approval.json"
    digest = write_manifest(manifest, data)
    return root, good, bad, manifest, data, digest


def approved_args(corpus):
    root, _, _, manifest, _, digest = corpus
    return [
        "--users-root",
        str(root),
        "--approved-non-candidates",
        str(manifest),
        "--approval-sha256",
        digest,
    ]


def test_default_stays_strict_even_when_an_approval_file_exists(corpus):
    assert ab.main(["--users-root", str(corpus[0])]) == 2


def test_exact_approval_keeps_all_rows_and_original_error(corpus, tmp_path, capsys):
    before = {p: sha(p) for p in corpus[0].rglob("*") if p.is_file()}
    result = tmp_path / "result.json"
    assert ab.main([*approved_args(corpus), "--json", str(result)]) == 0
    rows = json.loads(result.read_text())
    assert len(rows) == 2
    excluded = [r for r in rows if r.get("applicability") == "approved_non_candidate"]
    assert len(excluded) == 1 and excluded[0]["error"]
    assert excluded[0]["approval_manifest_sha256"] == corpus[-1]
    assert excluded[0]["input_sha256"] == sha(corpus[2])
    assert before == {p: sha(p) for p in before}
    output = capsys.readouterr().out
    assert "存证 episode：2 个；重放失败 1 个" in output
    assert "批准不适用 1 个" in output and "适用组重放失败 0 个" in output
    assert "非全部答卷通过" in output


@pytest.mark.parametrize(
    "mutation",
    [
        "unapproved",
        "wrong_schema",
        "missing_ref",
        "duplicate_entry",
        "wrong_count",
        "unknown_path",
        "wrong_run",
        "wrong_episode_hash",
        "unknown_classification",
        "wrong_error",
        "missing_side_file",
        "unsafe_side_file",
        "wrong_side_hash",
        "wrong_side_bytes",
        "wrong_scan_count",
        "wrong_scan_hash",
        "empty_entries",
    ],
)
def test_bad_approved_manifest_is_blocked(corpus, mutation, tmp_path, capsys):
    root, good, bad, manifest, data, _ = corpus
    item = data["entries"][0]
    if mutation == "unapproved":
        data["approved_by_user"] = False
    elif mutation == "wrong_schema":
        data["schema"] = "unknown"
    elif mutation == "missing_ref":
        data["approval_ref"] = ""
    elif mutation == "duplicate_entry":
        data["entries"].append(dict(item))
        data["approved_count"] = 2
    elif mutation == "wrong_count":
        data["approved_count"] = 2
    elif mutation == "unknown_path":
        item["path"] = str(tmp_path / "not-in-scan/continuous-episode.json")
    elif mutation == "wrong_run":
        item["run"] = "not-the-run"
    elif mutation == "wrong_episode_hash":
        item["input_sha256"] = "0" * 64
    elif mutation == "unknown_classification":
        item["classification"] = "any_failure"
    elif mutation == "wrong_error":
        item["expected_replay_error"] = "some other error"
    elif mutation == "missing_side_file":
        item["files"].pop("run.json")
    elif mutation == "unsafe_side_file":
        item["files"]["../elsewhere"] = item["files"]["run.json"]
    elif mutation == "wrong_side_hash":
        item["files"]["report.json"]["sha256"] = "0" * 64
    elif mutation == "wrong_side_bytes":
        item["files"]["report.json"]["bytes"] += 1
    elif mutation == "wrong_scan_count":
        data["scan_count"] = 3
    elif mutation == "wrong_scan_hash":
        data["scan_sha256"] = "0" * 64
    elif mutation == "empty_entries":
        data["entries"] = []
        data["approved_count"] = 0
    digest = write_manifest(manifest, data)
    assert (
        ab.main(
            [
                "--users-root",
                str(root),
                "--approved-non-candidates",
                str(manifest),
                "--approval-sha256",
                digest,
            ]
        )
        == 2
    )
    assert "✅" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "kind", ["manifest_only", "hash_only", "wrong_hash", "malformed_json"]
)
def test_explicit_manifest_and_pin_are_both_required(corpus, kind, capsys):
    root, _, _, manifest, _, digest = corpus
    args = ["--users-root", str(root)]
    if kind != "hash_only":
        args += ["--approved-non-candidates", str(manifest)]
    if kind != "manifest_only":
        args += ["--approval-sha256", "0" * 64 if kind == "wrong_hash" else digest]
    if kind == "malformed_json":
        manifest.write_text("{bad json")
        args[-1] = sha(manifest)
    assert ab.main(args) == 2
    assert "✅" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "which",
    [
        "episode",
        "answer",
        "applicable",
        "new_receipt",
        "missing_receipt",
        "duplicate_scan",
    ],
)
def test_frozen_population_or_artifact_drift_blocks(corpus, which):
    root, good, bad, _, _, _ = corpus
    args = approved_args(corpus)
    if which == "episode":
        bad.write_text('{"changed":true}')
    elif which == "answer":
        (bad.parent / "answer.md").write_text("changed")
    elif which == "applicable":
        good.write_text(good.read_text() + " ")
    elif which == "new_receipt":
        extra = root / "u2/runs/run_extra/continuous-episode.json"
        extra.parent.mkdir(parents=True)
        extra.write_text("{}")
    elif which == "missing_receipt":
        bad.unlink()
    elif which == "duplicate_scan":
        args = [str(root), str(bad), *args[2:]]
    assert ab.main(args) == 2


def test_non_candidate_does_not_hide_new_doubts(corpus):
    assert (
        ab.main(
            [
                *approved_args(corpus),
                "--relabel",
                "market_daily:强势股成交占比%=强势股成交占比",
            ]
        )
        == 1
    )


def test_approval_does_not_turn_a_new_replay_error_into_an_exemption(
    corpus, monkeypatch
):
    original = ab.replay_ab

    def broken(path, relabels):
        row = original(path, relabels)
        if Path(path) == corpus[1]:
            row["error"] = "new decoder failure"
        return row

    monkeypatch.setattr(ab, "replay_ab", broken)
    assert ab.main(approved_args(corpus)) == 2


def test_previously_non_candidate_now_replayable_requires_review(corpus, monkeypatch):
    original = ab.replay_ab

    def now_readable(path, relabels):
        row = original(path, relabels)
        if Path(path) == corpus[2]:
            row["error"] = None
        return row

    monkeypatch.setattr(ab, "replay_ab", now_readable)
    assert ab.main(approved_args(corpus)) == 2


def test_old_strict_baseline_can_be_compared_without_rewriting_it(corpus, tmp_path):
    baseline = tmp_path / "strict.json"
    assert ab.main(["--users-root", str(corpus[0]), "--json", str(baseline)]) == 2
    original_hash = sha(baseline)
    assert ab.main([*approved_args(corpus), "--baseline", str(baseline)]) == 0
    assert sha(baseline) == original_hash
    # Without the explicit authorization the very same population is still strict-red.
    assert ab.main(["--users-root", str(corpus[0]), "--baseline", str(baseline)]) == 2


@pytest.mark.parametrize(
    "mutation", ["scope", "hash", "new_error", "metric", "foreign_approval"]
)
def test_baseline_is_not_a_way_to_hide_drift(corpus, tmp_path, mutation):
    rows = [ab.replay_ab(p, ab.DEFAULT_RELABELS) for p in (corpus[1], corpus[2])]
    expected = 2
    if mutation == "scope":
        rows.pop()
    elif mutation == "hash":
        rows[0]["input_sha256"] = "0" * 64
    elif mutation == "new_error":
        rows[0]["error"] = "new baseline failure"
    elif mutation == "metric":
        rows[0]["asis"] = {"99": ["123%"]}
        expected = 1
    elif mutation == "foreign_approval":
        rows[1].update(
            applicability="approved_non_candidate", approval_manifest_sha256="0" * 64
        )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(rows))
    assert ab.main([*approved_args(corpus), "--baseline", str(baseline)]) == expected


def test_approved_mode_refuses_to_overwrite_any_existing_report(corpus, tmp_path):
    output = tmp_path / "historical.json"
    output.write_text("historical evidence")
    assert ab.main([*approved_args(corpus), "--json", str(output)]) == 2
    assert output.read_text() == "historical evidence"


def test_no_vacuous_success_when_all_receipts_are_exempted(corpus):
    root, good, bad, manifest, data, _ = corpus
    good.unlink()
    data.update(scan_count=1, scan_sha256=scan_digest([bad]))
    digest = write_manifest(manifest, data)
    assert (
        ab.main(
            [
                "--users-root",
                str(root),
                "--approved-non-candidates",
                str(manifest),
                "--approval-sha256",
                digest,
            ]
        )
        == 2
    )
