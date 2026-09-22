#!/usr/bin/env python3
"""Check uncommitted evidence using an isolated index, then verify the real commit.

Prevents two failures: GIT_INDEX_FILE scoped only to read-tree (later add touches
someone else's index), and printing a tree mismatch while returning exit 0.

prepare writes only unreachable Git objects and a temporary index, never refs or
worktree files. It uses literal repository-relative paths, rooted at pinned HEAD,
not the real index. verify requires a distinct, single-parent commit of exactly
that preview tree and reruns the archive checker on both committed versions.
Neither command commits to a branch, pushes, resets, or rewrites history.

Usage:
  python3 scripts/preview_evidence_archive.py prepare docs/verification/example \
    --repo <worktree> --paths docs/handoffs/example.md
  # Stop on nonzero exit. Keep the JSON preview_revision; make an explicit
  # pathspec commit separately, checking its exit status before continuing.
  python3 scripts/preview_evidence_archive.py verify docs/verification/example \
    --repo <worktree> --preview <preview_revision> --revision <new_commit>

Exit 0 = check passed (prepare is NOT a committed/pushed result), 1 = rejected,
2 = invalid input, Git failure, or environment failure. No network.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

if __package__:
    from .check_evidence_archive import check_archive
else:
    from check_evidence_archive import check_archive


# check_archive also launches Git; refuse caller redirection consistently rather
# than silently switching repositories/indexes in just one of the two helpers.
_REDIRECT = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(
        ["git", "--no-replace-objects", "--literal-pathspecs", "-C", str(repo), *args],
        check=True, capture_output=True, text=True, timeout=30, env=env,
    ).stdout.strip()


def _path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not path.parts or path.is_absolute() or path.as_posix() != value
        or ".." in path.parts or ".git" in path.parts or value.startswith(":")
    ):
        raise ValueError(f"expected a literal repository-relative path: {value!r}")
    return value


def _repo(repo: Path) -> Path:
    redirected = [key for key in _REDIRECT if key in os.environ]
    if redirected:
        raise ValueError(f"refusing inherited Git redirection: {', '.join(redirected)}")
    return Path(_git(repo, "rev-parse", "--show-toplevel")).resolve()


def _commit(repo: Path, revision: str) -> str:
    return _git(repo, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}")


def _parents(repo: Path, revision: str) -> list[str]:
    # Revision walkers (including `show --format=%P`) may hide or rewrite
    # parents at shallow/graft boundaries. Read the immutable object header.
    header = _git(repo, "cat-file", "commit", revision).split("\n\n", 1)[0]
    return [line.removeprefix("parent ") for line in header.splitlines() if line.startswith("parent ")]


def prepare(repo: Path, archive: str, paths: list[str]) -> dict[str, object]:
    repo = _repo(repo)
    archive = _path(archive)
    selected = list(dict.fromkeys([archive, *(_path(p) for p in paths)]))
    base = _commit(repo, "HEAD")
    # The env is attached to EVERY subprocess, never just `git read-tree`.
    with tempfile.TemporaryDirectory(prefix="evidence-preview-") as directory:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
        _git(repo, "read-tree", base, env=env)
        _git(repo, "add", "--", *selected, env=env)
        tree = _git(repo, "write-tree", env=env)
        preview = _git(
            repo, "commit-tree", tree, "-p", base,
            "-m", "Unreferenced evidence preview; not a branch commit", env=env,
        )
    checked = check_archive(repo, archive, preview)
    errors = list(checked["errors"])
    if _commit(repo, "HEAD") != base:
        errors.append("HEAD moved during preview; create a fresh preview")
    return {
        "ok": not errors, "phase": "preview_only", "repo": str(repo),
        "archive": archive, "paths": selected, "base_revision": base,
        "preview_revision": preview, "tree": tree,
        "archive_check": checked, "errors": errors,
    }


def verify(repo: Path, archive: str, preview: str, revision: str) -> dict[str, object]:
    repo = _repo(repo)
    archive = _path(archive)
    preview = _commit(repo, preview)
    revision = _commit(repo, revision)
    preview_parents = _parents(repo, preview)
    parents = _parents(repo, revision)
    preview_tree = _git(repo, "rev-parse", f"{preview}^{{tree}}")
    tree = _git(repo, "rev-parse", f"{revision}^{{tree}}")
    errors = []
    if preview == revision:
        errors.append("preview itself is not a distinct real commit")
    if len(preview_parents) != 1 or parents != preview_parents:
        errors.append("real commit must have exactly the preview's pinned base parent")
    if tree != preview_tree:
        errors.append("real commit tree differs from preview tree")
    preview_check = check_archive(repo, archive, preview)
    actual_check = check_archive(repo, archive, revision)
    errors.extend(f"preview: {e}" for e in preview_check["errors"])
    errors.extend(f"real commit: {e}" for e in actual_check["errors"])
    return {
        "ok": not errors, "phase": "committed_bytes_only", "repo": str(repo),
        "archive": archive, "preview_revision": preview, "revision": revision,
        "preview_tree": preview_tree, "tree": tree,
        "preview_check": preview_check, "archive_check": actual_check,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "verify"):
        child = sub.add_parser(command)
        child.add_argument("archive")
        child.add_argument("--repo", type=Path, default=Path.cwd())
        if command == "prepare":
            child.add_argument("--paths", nargs="+", default=[])
        else:
            child.add_argument("--preview", required=True)
            child.add_argument("--revision", required=True)
    args = parser.parse_args(argv)
    try:
        result = (
            prepare(args.repo, args.archive, args.paths) if args.command == "prepare"
            else verify(args.repo, args.archive, args.preview, args.revision)
        )
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
