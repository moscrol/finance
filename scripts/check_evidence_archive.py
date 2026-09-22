#!/usr/bin/env python3
"""Verify a SHA-256 archive against an immutable Git commit, not local disk.

Prevents 'shasum passes locally but ignored logs never reached Git'. Manifest
entries are repository-relative paths, exactly as produced by shasum -a 256.
Require the complete archive file set (excluding only the manifest), regular
Git blobs, unique in-directory paths, and matching bytes. No writes/network.

Usage: python3 scripts/check_evidence_archive.py <archive-dir> --revision HEAD
Exit 0 = complete + matching; 1 = invalid archive; 2 = invalid Git input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


MANIFEST = "sha256-manifest.txt"


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        # Replacement refs are local overlays, not bytes named by the SHA.
        ["git", "--no-replace-objects", "-C", str(repo), *args],
        check=True, capture_output=True, timeout=30,
    ).stdout


def check_archive(repo: Path, archive: str, revision: str) -> dict[str, object]:
    directory = PurePosixPath(archive)
    if (
        directory.is_absolute() or ".." in directory.parts
        or directory.as_posix() != archive or not directory.parts
    ):
        raise ValueError("archive must be a normalized repository-relative directory")
    # Resolve once: HEAD may move while validation is running.
    commit = _git(repo, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").decode().strip()
    prefix = archive + "/"
    entries: dict[str, tuple[str, str, str]] = {}
    for record in _git(repo, "ls-tree", "-rz", commit).split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        if path.startswith(prefix):
            mode, kind, oid = metadata.decode().split()
            entries[path] = mode, kind, oid
    manifest_path = prefix + MANIFEST
    errors: list[str] = []
    for path, (mode, kind, _oid) in entries.items():
        if mode not in {"100644", "100755"} or kind != "blob":
            errors.append(f"not a regular file: {path}")
    listed: dict[str, str] = {}
    manifest_entry = entries.get(manifest_path)
    if manifest_entry is None:
        errors.append(f"missing manifest in commit: {manifest_path}")
    elif manifest_entry[1] == "blob":
        text = _git(repo, "cat-file", "blob", manifest_entry[2]).decode("utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            if match is None:
                errors.append(f"invalid manifest line: {number}")
                continue
            digest, path = match.groups()
            parsed = PurePosixPath(path)
            if (
                not path.startswith(prefix) or ".." in parsed.parts
                or parsed.as_posix() != path or path == manifest_path
            ):
                errors.append(f"invalid manifest path: {path}")
                continue
            if path in listed:
                errors.append(f"duplicate manifest path: {path}")
            listed[path] = digest
    actual = set(entries) - {manifest_path}
    for path in sorted(set(listed) - actual):
        errors.append(f"missing from commit: {path}")
    for path in sorted(actual - set(listed)):
        errors.append(f"missing from manifest: {path}")
    for path in sorted(actual & set(listed)):
        mode, kind, oid = entries[path]
        if mode not in {"100644", "100755"} or kind != "blob":
            continue
        if hashlib.sha256(_git(repo, "cat-file", "blob", oid)).hexdigest() != listed[path]:
            errors.append(f"hash mismatch: {path}")
    return {
        "revision": commit, "archive": archive,
        "manifest_files": len(listed), "committed_files": len(actual),
        "ok": not errors, "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = check_archive(args.repo, args.archive, args.revision)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
