from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

from intelligence.services.content_delta import (
    apply_content_delta,
    build_content_delta,
    content_delta_errors,
    content_delta_payload,
    content_delta_worktree_errors,
)


def _repo(root: Path) -> Path:
    repo = root / "knowledge"
    wiki = repo / "wiki"
    wiki.mkdir(parents=True)
    (repo / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    (wiki / "modified.md").write_text("before\n", encoding="utf-8")
    (wiki / "deleted.md").write_text("delete\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "base",
        ],
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-07-10T17:00:00+08:00",
            "GIT_COMMITTER_DATE": "2026-07-10T17:00:00+08:00",
        },
    )
    return repo


def test_content_delta_captures_tracked_untracked_and_ignored_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(Path(tmp))
        wiki = repo / "wiki"
        (wiki / "modified.md").write_text("after\n", encoding="utf-8")
        (wiki / "deleted.md").unlink()
        (wiki / "untracked.md").write_text("new\n", encoding="utf-8")
        (wiki / "ignored.tmp").write_text("ignored\n", encoding="utf-8")
        timestamp = 1783677600
        for path in (
            wiki / "modified.md",
            wiki / "untracked.md",
            wiki / "ignored.tmp",
        ):
            os.utime(path, (timestamp, timestamp))

        first = build_content_delta(
            wiki,
            captured_at="2026-07-10T20:00:00+08:00",
        )
        second = build_content_delta(
            wiki,
            captured_at="2026-07-10T20:01:00+08:00",
        )

        assert first["artifact_sha"] == second["artifact_sha"]
        assert first["scope"] == "wiki"
        assert first["dirty"] is True
        assert [entry["path"] for entry in first["entries"]] == [
            "wiki/deleted.md",
            "wiki/ignored.tmp",
            "wiki/modified.md",
            "wiki/untracked.md",
        ]
        assert not content_delta_errors(
            first,
            evidence_cutoff="2026-07-10T20:00:00+08:00",
        )
        replay = Path(tmp) / "replay"
        subprocess.run(
            ["git", "clone", "-q", str(repo), str(replay)],
            check=True,
        )
        apply_content_delta(replay, first)
        assert (replay / "wiki" / "modified.md").read_text(
            encoding="utf-8"
        ) == "after\n"
        assert not (replay / "wiki" / "deleted.md").exists()
        assert (replay / "wiki" / "untracked.md").is_file()
        assert (replay / "wiki" / "ignored.tmp").is_file()
        assert not content_delta_worktree_errors(
            replay / "wiki",
            first,
        )


def test_content_delta_rejects_content_and_cutoff_tampering() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(Path(tmp))
        path = repo / "wiki" / "modified.md"
        path.write_text("after\n", encoding="utf-8")
        timestamp = 1783677600
        os.utime(path, (timestamp, timestamp))
        delta = build_content_delta(
            repo / "wiki",
            captured_at="2026-07-10T20:00:00+08:00",
        )

        content = deepcopy(delta)
        content["entries"][0]["content_base64"] = "dGFtcGVyZWQ="
        assert any(
            "content hash mismatch" in error
            for error in content_delta_errors(content)
        )

        cutoff = deepcopy(delta)
        cutoff["entries"][0]["modified_at"] = (
            "2026-07-10T20:01:00+08:00"
        )
        assert any(
            "after evidence_cutoff" in error
            for error in content_delta_errors(
                cutoff,
                evidence_cutoff="2026-07-10T20:00:00+08:00",
            )
        )

        unsafe = deepcopy(delta)
        unsafe["entries"][0]["path"] = "../outside.md"
        assert any(
            "path is unsafe" in error
            for error in content_delta_errors(unsafe)
        )

        assert "content delta base commit mismatch" in (
            content_delta_errors(
                delta,
                expected_base_commit="0" * 40,
            )
        )


def test_content_delta_rejects_omitted_deleted_and_untracked_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(Path(tmp))
        wiki = repo / "wiki"
        (wiki / "deleted.md").unlink()
        untracked = wiki / "untracked.md"
        untracked.write_text("new\n", encoding="utf-8")
        timestamp = 1783677600
        os.utime(untracked, (timestamp, timestamp))
        delta = build_content_delta(
            wiki,
            captured_at="2026-07-10T20:00:00+08:00",
        )

        for omitted_path in ("wiki/deleted.md", "wiki/untracked.md"):
            omitted = deepcopy(delta)
            omitted["entries"] = [
                entry
                for entry in omitted["entries"]
                if entry["path"] != omitted_path
            ]
            omitted["entry_count"] = len(omitted["entries"])
            omitted["total_bytes"] = sum(
                int(entry.get("size") or 0)
                for entry in omitted["entries"]
            )
            omitted["dirty"] = bool(omitted["entries"])
            canonical = json.dumps(
                content_delta_payload(omitted),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            omitted["artifact_sha"] = hashlib.sha256(
                canonical
            ).hexdigest()

            assert not content_delta_errors(omitted)
            assert (
                "content delta does not match current worktree"
                in content_delta_worktree_errors(wiki, omitted)
            )


def test_content_delta_rejects_symlinks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(Path(tmp))
        os.symlink("modified.md", repo / "wiki" / "link.md")

        with pytest.raises(ValueError, match="unsupported content delta"):
            build_content_delta(
                repo / "wiki",
                captured_at="2026-07-10T20:00:00+08:00",
            )


def test_content_delta_excludes_raw_ingest_queue_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(Path(tmp))
        wiki = repo / "wiki"
        (wiki / "modified.md").write_text("after\n", encoding="utf-8")
        raw_dir = wiki / "raw" / "cross-repo-ingest-queue" / "reports"
        raw_dir.mkdir(parents=True)
        raw_report = raw_dir / "scout-20260901-190004.json"
        raw_report.write_text("x" * 4096, encoding="utf-8")
        raw_other = wiki / "raw" / "cninfo-baseline.json"
        raw_other.write_text("y\n", encoding="utf-8")
        timestamp = 1783677600
        for path in (wiki / "modified.md", raw_report, raw_other):
            os.utime(path, (timestamp, timestamp))

        delta = build_content_delta(
            wiki,
            captured_at="2026-07-10T20:00:00+08:00",
        )

        assert [entry["path"] for entry in delta["entries"]] == [
            "wiki/modified.md"
        ]
        assert not content_delta_errors(delta)
        # 一致性校验必须双向一致：当前树同样排除 raw/，artifact_sha 才稳定
        assert not content_delta_worktree_errors(wiki, delta)
