from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


CONTENT_DELTA_SCHEMA_VERSION = "content-delta-1.0"
MAX_DELTA_BYTES = 10 * 1024 * 1024
REPLAY_RECIPE = "checkout base_commit, then apply entries by path"
# 检索访问日志是 append-only 遥测，不是知识内容：生成 delta 的过程本身会
# 通过 RAG 检索追加它，纳入快照会让 before/after 一致性校验自我失效。
EXCLUDED_PATH_SUFFIXES = ("relations/access_log.jsonl",)


def _is_excluded(relative: str) -> bool:
    return any(
        relative == suffix or relative.endswith(f"/{suffix}")
        for suffix in EXCLUDED_PATH_SUFFIXES
    )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _timestamp(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value or ""))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def _git(
    root: Path,
    args: list[str],
    *,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=text,
    )


def _git_paths(root: Path, args: list[str]) -> set[str]:
    output = _git(root, args, text=False).stdout
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in output.split(b"\0")
        if item
    }


def _filesystem_paths(scope: Path, repo_root: Path) -> set[str]:
    paths: set[str] = set()
    for current_root, dirnames, filenames in os.walk(
        scope,
        followlinks=False,
    ):
        root = Path(current_root)
        retained_dirs: list[str] = []
        for dirname in dirnames:
            candidate = root / dirname
            if dirname == ".git":
                continue
            if candidate.is_symlink():
                paths.add(candidate.relative_to(repo_root).as_posix())
            else:
                retained_dirs.append(dirname)
        dirnames[:] = retained_dirs
        for filename in filenames:
            candidate = root / filename
            paths.add(candidate.relative_to(repo_root).as_posix())
    return paths


def content_delta_payload(delta: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": delta.get("schema_version"),
        "base_commit": delta.get("base_commit"),
        "base_committed_at": delta.get("base_committed_at"),
        "scope": delta.get("scope"),
        "entry_count": delta.get("entry_count"),
        "total_bytes": delta.get("total_bytes"),
        "entries": delta.get("entries"),
    }


def build_content_delta(
    scope_path: str | Path,
    *,
    captured_at: str,
    max_bytes: int = MAX_DELTA_BYTES,
) -> dict[str, Any]:
    scope = Path(scope_path).expanduser().resolve()
    repo_root = Path(
        _git(scope, ["rev-parse", "--show-toplevel"]).stdout.strip()
    ).resolve()
    try:
        scope_relative = scope.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("content delta scope is outside repository") from exc
    scope_name = (
        "."
        if scope_relative == Path(".")
        else scope_relative.as_posix()
    )
    scope_arg = "." if scope_name == "." else scope_name
    base_commit = _git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()
    base_committed_at = _git(
        repo_root,
        ["show", "-s", "--format=%cI", base_commit],
    ).stdout.strip()
    tracked = _git_paths(
        repo_root,
        ["ls-files", "-z", "--", scope_arg],
    )
    changed = _git_paths(
        repo_root,
        [
            "diff",
            "--name-only",
            "--no-renames",
            "-z",
            "HEAD",
            "--",
            scope_arg,
        ],
    )
    changed.update(_filesystem_paths(scope, repo_root) - tracked)

    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for relative in sorted(changed):
        if _is_excluded(relative):
            continue
        path = repo_root / relative
        if not os.path.lexists(path):
            entries.append({"path": relative, "state": "deleted"})
            continue
        file_stat = path.lstat()
        if stat.S_ISREG(file_stat.st_mode):
            state = "file"
            mode = (
                "100755"
                if file_stat.st_mode & stat.S_IXUSR
                else "100644"
            )
            content = path.read_bytes()
        else:
            raise ValueError(f"unsupported content delta entry: {relative}")
        total_bytes += len(content)
        if total_bytes > max_bytes:
            raise ValueError("content delta exceeds maximum size")
        entries.append(
            {
                "path": relative,
                "state": state,
                "mode": mode,
                "size": len(content),
                "content_sha256": _sha256(content),
                "content_base64": base64.b64encode(content).decode("ascii"),
                "modified_at": datetime.fromtimestamp(
                    file_stat.st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
            }
        )
    delta = {
        "schema_version": CONTENT_DELTA_SCHEMA_VERSION,
        "captured_at": captured_at,
        "base_commit": base_commit,
        "base_committed_at": base_committed_at,
        "scope": scope_name,
        "dirty": bool(entries),
        "entry_count": len(entries),
        "total_bytes": total_bytes,
        "entries": entries,
        "replay_recipe": REPLAY_RECIPE,
    }
    delta["artifact_sha"] = _sha256(
        _canonical_bytes(content_delta_payload(delta))
    )
    return delta


def content_delta_errors(
    delta: object,
    *,
    evidence_cutoff: str | None = None,
    expected_base_commit: str | None = None,
) -> list[str]:
    if not isinstance(delta, dict):
        return ["content delta must be an object"]
    errors: list[str] = []
    if delta.get("schema_version") != CONTENT_DELTA_SCHEMA_VERSION:
        errors.append("content delta schema mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(delta.get("base_commit") or "")):
        errors.append("content delta base commit is invalid")
    if delta.get("replay_recipe") != REPLAY_RECIPE:
        errors.append("content delta replay recipe mismatch")
    try:
        _timestamp(delta.get("captured_at"))
    except ValueError:
        errors.append("content delta captured_at is invalid")
    if (
        expected_base_commit
        and delta.get("base_commit") != expected_base_commit
    ):
        errors.append("content delta base commit mismatch")
    scope = str(delta.get("scope") or "")
    scope_path = PurePosixPath(scope)
    if (
        not scope
        or scope_path.is_absolute()
        or ".." in scope_path.parts
    ):
        errors.append("content delta scope is unsafe")
    entries = delta.get("entries")
    if not isinstance(entries, list):
        errors.append("content delta entries must be a list")
        entries = []
    seen: set[str] = set()
    total_bytes = 0
    previous_path = ""
    cutoff = None
    if evidence_cutoff:
        try:
            cutoff = _timestamp(evidence_cutoff)
        except ValueError:
            errors.append("content delta evidence_cutoff is invalid")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"content delta entry {index} is not an object")
            continue
        path = str(entry.get("path") or "")
        relative = PurePosixPath(path)
        if (
            not path
            or relative.is_absolute()
            or ".." in relative.parts
            or (
                scope != "."
                and path != scope
                and not path.startswith(f"{scope}/")
            )
        ):
            errors.append(f"content delta entry path is unsafe: {path}")
        if path in seen:
            errors.append(f"duplicate content delta path: {path}")
        if previous_path and path < previous_path:
            errors.append("content delta entries are not canonical")
        seen.add(path)
        previous_path = path
        state = entry.get("state")
        if state == "deleted":
            if set(entry) != {"path", "state"}:
                errors.append(f"deleted content delta entry is invalid: {path}")
            continue
        if state != "file":
            errors.append(f"content delta entry state is invalid: {path}")
            continue
        if entry.get("mode") not in {
            "100644",
            "100755",
        }:
            errors.append(f"content delta mode mismatch: {path}")
        try:
            content = base64.b64decode(
                str(entry.get("content_base64") or ""),
                validate=True,
            )
        except (ValueError, binascii.Error):
            errors.append(f"content delta base64 is invalid: {path}")
            continue
        total_bytes += len(content)
        if entry.get("size") != len(content):
            errors.append(f"content delta size mismatch: {path}")
        if entry.get("content_sha256") != _sha256(content):
            errors.append(f"content delta content hash mismatch: {path}")
        if cutoff is not None:
            try:
                modified_at = _timestamp(entry.get("modified_at"))
            except ValueError:
                errors.append(f"content delta modified_at is invalid: {path}")
            else:
                if modified_at > cutoff:
                    errors.append(
                        f"content delta entry is after evidence_cutoff: {path}"
                    )
    if delta.get("entry_count") != len(entries):
        errors.append("content delta entry count mismatch")
    if delta.get("total_bytes") != total_bytes:
        errors.append("content delta byte count mismatch")
    if delta.get("dirty") is not bool(entries):
        errors.append("content delta dirty flag mismatch")
    if delta.get("artifact_sha") != _sha256(
        _canonical_bytes(content_delta_payload(delta))
    ):
        errors.append("content delta artifact hash mismatch")
    if cutoff is not None:
        try:
            base_committed_at = _timestamp(
                delta.get("base_committed_at")
            )
        except ValueError:
            errors.append("content delta base_committed_at is invalid")
        else:
            if base_committed_at > cutoff:
                errors.append(
                    "content delta base commit is after evidence_cutoff"
                )
    return errors


def content_delta_worktree_errors(
    scope_path: str | Path,
    delta: object,
) -> list[str]:
    errors = content_delta_errors(delta)
    if errors or not isinstance(delta, dict):
        return errors
    current = build_content_delta(
        scope_path,
        captured_at=str(delta.get("captured_at") or ""),
    )
    if current["artifact_sha"] != delta.get("artifact_sha"):
        errors.append("content delta does not match current worktree")
    return errors


def apply_content_delta(
    checkout_root: str | Path,
    delta: object,
) -> None:
    errors = content_delta_errors(delta)
    if errors or not isinstance(delta, dict):
        raise ValueError("invalid content delta: " + "; ".join(errors))
    root = Path(checkout_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("content delta checkout root is unavailable")
    for entry in delta["entries"]:
        path = root / str(entry["path"])
        parent = path.parent.resolve()
        try:
            parent.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"content delta entry escapes checkout: {entry['path']}"
            ) from exc
        if entry["state"] == "deleted":
            if os.path.lexists(path):
                if path.is_dir() and not path.is_symlink():
                    raise ValueError(
                        f"content delta deletion is a directory: "
                        f"{entry['path']}"
                    )
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        parent = path.parent.resolve()
        try:
            parent.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"content delta entry escapes checkout: {entry['path']}"
            ) from exc
        if os.path.lexists(path):
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                raise ValueError(
                    f"content delta file target is a directory: "
                    f"{entry['path']}"
                )
        content = base64.b64decode(
            entry["content_base64"],
            validate=True,
        )
        path.write_bytes(content)
        path.chmod(int(str(entry["mode"])[-3:], 8))
        modified_at = _timestamp(entry["modified_at"])
        modified_ns = int(modified_at.timestamp() * 1_000_000_000)
        os.utime(path, ns=(modified_ns, modified_ns))
