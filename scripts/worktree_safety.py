#!/usr/bin/env python3
"""Read-only worktree blockers shared by the board and cleanup_gate_trees.sh.

A clean Git status is not deletion permission. Keep query failures, ignored
contents and concrete process/launcher references visible to both callers.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable
from xml.parsers.expat import ExpatError


def git(args: list[str], *, cwd: str, timeout: float) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        return result.returncode, result.stdout.rstrip("\n")
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def ancestor(head: str, base: str, *, cwd: str, timeout: float, run_git: Callable = git) -> int:
    code, _ = run_git(["merge-base", "--is-ancestor", head, base], cwd=cwd, timeout=timeout)
    return code


def status_paths(raw: str) -> tuple[list[str], list[str]]:
    """Parse porcelain v1 -z; rename source is the following NUL record."""
    dirty, ignored = [], []
    records = iter(raw.split("\0"))
    for record in records:
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise ValueError("invalid git status record")
        (ignored if record[:2] == "!!" else dirty).append(record[3:])
        if "R" in record[:2] or "C" in record[:2]:
            if next(records, None) is None:
                raise ValueError("missing rename source")
    return dirty, ignored


def inspect_tree(path: str, *, timeout: float, run_git: Callable = git) -> dict:
    code, top = run_git(["rev-parse", "--show-toplevel"], cwd=path, timeout=timeout)
    result = {"paths": [], "ignored": [], "unknown_reason": ""}
    if code or not top or Path(top).resolve() != Path(path).resolve():
        result["unknown_reason"] = "worktree unavailable or repository root mismatch"
        return result
    code, raw = run_git(
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored"],
        cwd=path, timeout=timeout,
    )
    if code:
        result["unknown_reason"] = "git status failed; dirty state unknown"
        return result
    try:
        result["paths"], result["ignored"] = status_paths(raw)
    except ValueError as exc:
        result["unknown_reason"] = str(exc)
    return result


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _shell_paths(text: str, home: Path):
    # Launchers are shell text, not plist XML. Include quoted paths with spaces.
    prefix = rf"(?:{re.escape(str(home))}|\$HOME|\$\{{HOME\}}|~)/"
    pattern = rf'''["']({prefix}[^"'\n]+)["']|({prefix}[^\s"'<>;)]+)'''
    for match in re.finditer(pattern, text):
        raw = match.group(1) or match.group(2)
        for variable in ("${HOME}", "$HOME", "~"):
            if raw.startswith(variable + "/"):
                raw = str(home) + raw[len(variable):]
                break
        yield raw


def _load_launchd_plist(data: bytes, *, timeout: float) -> dict:
    try:
        value = plistlib.loads(data)
    except (ValueError, plistlib.InvalidFileException, ExpatError):
        if sys.platform != "darwin":
            raise
        # Use macOS semantics on the bytes already sampled, never rewrite the launcher.
        converted = subprocess.run(
            ["/usr/bin/plutil", "-convert", "binary1", "-o", "-", "--", "-"],
            input=data, capture_output=True, timeout=timeout,
        )
        converted.check_returncode()
        value = plistlib.loads(converted.stdout)
    if not isinstance(value, dict):
        raise ValueError("launchd plist root must be a dictionary")
    return value


def sample_context(*, timeout: float, home: Path | None = None) -> dict:
    home = home or Path.home()
    references, errors = [], []
    try:
        proc = subprocess.run(
            ["lsof", "-nP", "-S", "2", "-w", "-d", "^mem", "-Fpcftn"],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode:
            errors.append("lsof 采样失败; process usage unknown")
        else:
            pid = command = fd = kind = "?"
            for record in proc.stdout.splitlines():
                if record.startswith("p"):
                    pid, command, fd, kind = record[1:], "?", "?", "?"
                elif record.startswith("c"):
                    command = record[1:]
                elif record.startswith("f"):
                    fd, kind = record[1:], "?"
                elif record.startswith("t"):
                    kind = record[1:]
                elif record.startswith("n/"):
                    if _is_directory_watch(fd, kind):
                        continue
                    references.append({"kind": "process", "path": os.path.realpath(record[1:]),
                                       "source": f"pid={pid} {command} fd={fd}"})
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"lsof 采样失败: {type(exc).__name__}; process usage unknown")

    def add_reference(raw: str, source: Path, kind: str = "launcher"):
        references.append({"kind": kind, "path": os.path.realpath(raw), "source": str(source)})

    for directory, is_plist in ((home / "Library/LaunchAgents", True), (home / ".local/bin", False)):
        try:
            files = sorted(directory.iterdir()) if directory.exists() else []
            for file in files:
                if not file.is_file() or (is_plist and file.suffix != ".plist"):
                    continue
                try:
                    data = file.read_bytes()
                    if is_plist:
                        for value in _strings(_load_launchd_plist(data, timeout=timeout)):
                            if value.startswith("/"):
                                add_reference(value, file)
                            else:
                                for raw in _shell_paths(value, home):
                                    add_reference(raw, file)
                    elif b"\0" not in data:
                        for raw in _shell_paths(data.decode("utf-8"), home):
                            add_reference(raw, file)
                except (OSError, ValueError, UnicodeError, plistlib.InvalidFileException,
                        ExpatError, subprocess.SubprocessError) as exc:
                    errors.append(f"launcher unreadable: {file} ({type(exc).__name__})")
        except OSError as exc:
            errors.append(f"launcher directory unreadable: {directory} ({type(exc).__name__})")
    runtime = home / ".finance-runtime"
    try:
        links = [home / "finance-workspace-runtime"]
        if runtime.exists():
            links.extend(runtime.iterdir())
        for link in links:
            if link.is_symlink():
                add_reference(str(link), link, "runtime")
    except OSError as exc:
        errors.append(f"runtime links unreadable: {type(exc).__name__}")
    return {"references": references, "errors": errors}


def context_blockers(path: str, context: dict) -> list[str]:
    root = Path(path).resolve()
    blockers = []
    for ref in context["references"]:
        target = Path(ref["path"])
        if target.is_relative_to(root) or (
            ref["kind"] != "process" and root.is_relative_to(target)
        ):
            label = "进程" if ref["kind"] == "process" else "被 launchd/启动器引用"
            blockers.append(f"{label}: {ref['source']} -> {ref['path']}")
    return sorted(set(blockers))


def _is_directory_watch(fd: str, kind: str) -> bool:
    """A numbered descriptor on a DIR is a file watcher (Claude Code / editors hold thousands),
    not usage of the tree. cwd/rtd/txt and every regular file still count."""
    return kind == "DIR" and fd.isdigit()


# Regenerable build/test caches. Anything else that is ignored (evidence DBs, users/, snapshots)
# still blocks: the tool must not decide on the user's behalf that data is disposable.
CACHE_IGNORED = frozenset({"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
                           "node_modules", ".DS_Store"})


def is_cache_path(path: str) -> bool:
    parts = path.rstrip("/").split("/")
    return any(part in CACHE_IGNORED or part.endswith(".pyc") or part.startswith(".venv")
               for part in parts)


def file_blockers(state: dict) -> list[str]:
    return ([f"未提交: {path}" for path in state["paths"]]
            + [f"ignored 内容: {path}" for path in state["ignored"] if not is_cache_path(path)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("context", "check", "ancestor"))
    parser.add_argument("--context", type=Path)
    parser.add_argument("--path")
    parser.add_argument("--head")
    parser.add_argument("--base")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    if args.mode == "ancestor":
        if not all((args.path, args.head, args.base)):
            parser.error("ancestor requires --path, --head and --base")
        return ancestor(args.head, args.base, cwd=args.path, timeout=args.timeout)
    if args.context is None:
        parser.error("context/check requires --context")
    if args.mode == "context":
        context = sample_context(timeout=args.timeout)
        args.context.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
        if context["errors"]:
            print("; ".join(context["errors"]), file=sys.stderr)
            return 4
        return 0
    if not args.path:
        parser.error("check requires --path")
    try:
        context = json.loads(args.context.read_text(encoding="utf-8"))
        state = inspect_tree(args.path, timeout=args.timeout)
        errors = context["errors"] + ([state["unknown_reason"]] if state["unknown_reason"] else [])
        if errors:
            print("; ".join(errors), file=sys.stderr)
            return 4
        print("; ".join(file_blockers(state) + context_blockers(args.path, context)))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"safety audit unavailable: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
