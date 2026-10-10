#!/usr/bin/env python3
"""Block high-signal credential literals in changed index blobs, without echoing them.

An archived text receipt can contain a full login session while passing filename
and private-key checks. Read Git's index, never the working copy: cleaning a file
without re-staging must not hide what the next commit would publish. Check added,
modified, copied and renamed blobs, including extensionless/binary files and the
first commit. Do not follow symlinks or read external submodule content.

This is a narrow offline regression guard, NOT a general secret scanner: it does
not search history, decode archives/base64 wrappers, validate/revoke credentials,
or prove an upload safe. Expired tokens still block. No per-directory exemptions.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# Values are matched only to classify; output contains neither matches nor hashes.
_RULES = (
    (
        "session-or-refresh-literal",
        re.compile(
            rb'''(?i)["']?(?:session_?token|refresh_?token|access_?token)["']?'''
            rb'''\s*[:=]\s*["'][A-Za-z0-9_.~+/%=-]{60,}["']'''
        ),
    ),
    (
        "app-secret-literal",
        re.compile(
            rb'''(?i)["']?app[_-]?secret["']?\s*[:=]\s*["'][A-Za-z0-9_+/.=-]{24,}["']'''
        ),
    ),
    (
        "encrypted-session-shape",
        re.compile(
            rb"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*\."
            rb"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{80,}\.[A-Za-z0-9_-]{8,}\b"
        ),
    ),
    (
        "signed-token-shape",
        re.compile(
            rb"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{40,}\b"
        ),
    ),
)


class IndexReadError(Exception):
    """Fail closed without propagating potentially sensitive Git stderr."""


def _git(*args: str) -> bytes:
    try:
        result = subprocess.run(["git", *args], capture_output=True, check=False)
    except OSError as exc:
        raise IndexReadError("Git unavailable") from exc
    if result.returncode:
        raise IndexReadError("Git index read failed")
    return result.stdout


def scan_bytes(data: bytes) -> list[tuple[int, str]]:
    """Return line/rule metadata only; even exceptions must not carry content."""
    return sorted({
        (data.count(b"\n", 0, match.start()) + 1, rule)
        for rule, pattern in _RULES
        for match in pattern.finditer(data)
    })


def scan_index() -> tuple[int, int, list[tuple[str, int, str]]]:
    changed = set(_git(
        "diff", "--cached", "--name-only", "--no-renames", "--diff-filter=ACMTU", "-z", "--"
    ).split(b"\0")) - {b""}
    if not changed:
        return 0, 0, []
    entries = {}
    for record in _git("ls-files", "--stage", "-z", "--").split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        if path not in changed:
            continue
        mode, oid, stage = metadata.split()
        if stage != b"0":
            raise IndexReadError("Unmerged index entry")
        entries[path] = (mode, oid)
    if set(entries) != changed:
        raise IndexReadError("Changed path missing from index")
    scanned = submodules = 0
    findings = []
    for path, (mode, oid) in sorted(entries.items()):
        if mode == b"160000":
            submodules += 1
            continue
        data = _git("cat-file", "blob", oid.decode("ascii"))
        scanned += 1
        findings.extend((os.fsdecode(path), line, rule) for line, rule in scan_bytes(data))
    return scanned, submodules, findings


def main() -> int:
    try:
        scanned, submodules, findings = scan_index()
    except (IndexReadError, ValueError):
        print("凭据内容检查无法读取完整暂存区；拒绝提交（未输出文件内容）。", file=sys.stderr)
        return 2
    for path, line, rule in findings:
        # Quote unusual filenames, so filenames cannot inject terminal controls.
        print(f"{json.dumps(path, ensure_ascii=True)}:{line}: {rule} [value withheld]")
    print(f"暂存内容检查：{scanned} 个 blob；{submodules} 个子模块仅记录引用、不扫描外部内容。")
    if findings:
        print("发现疑似凭据；移到仓外密钥管理并重新暂存。已公开的值须先撤销，删文件不等于撤销。")
        return 1
    print("本次暂存内容未命中上述规则；不代表历史或所有类型凭据均安全。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
