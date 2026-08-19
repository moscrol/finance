#!/usr/bin/env python3
"""本地代码地图门面。

跨 harness 的查询正门是本 CLI，不是 MCP。PR1 只实现 ``status``：
空图 / 零节点 fail-closed，禁止把空壳写成架构结论。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

SQLITE_TIMEOUT_SEC = 0.05
ONE_LINE_MAX = 80
STALE_HEAVY_MIN_COMMITS = 5
STALE_HEAVY_PATHS = ("intelligence/", "market_feature_store/", "scripts/")
# 与 scripts/session_facts.sh 同一套代码路径前缀；不要在这里写第二份家目录。
CODE_DIRTY_PREFIXES = (
    "intelligence/",
    "evolution/",
    "market_feature_store/",
    "scripts/",
    "tests/",
    "conftest.py",
    "pytest.ini",
    "ruff.toml",
    "test-environment.json",
    "requirements-consumer.lock",
)
CODE_DIRTY_EXCLUDE_PREFIXES = ("market_feature_store/exports/",)

EXIT_READY = 0
EXIT_STALE = 1
EXIT_EMPTY = 2
EXIT_ERROR = 3


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _git_ok(root: Path, *args: str) -> str | None:
    proc = _git(root, *args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _is_git_work_tree(root: Path) -> bool:
    return _git_ok(root, "rev-parse", "--is-inside-work-tree") == "true"


def _porcelain_path(line: str) -> str:
    path = line[3:] if len(line) >= 3 else line
    path = path.strip()
    if path.startswith('"') and path.endswith('"') and len(path) >= 2:
        path = path[1:-1]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path


def _worktree_dirty_code(root: Path) -> bool:
    proc = _git(root, "status", "--porcelain", "-uall")
    if proc.returncode != 0:
        return False
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        path = _porcelain_path(line)
        if any(path.startswith(ex) for ex in CODE_DIRTY_EXCLUDE_PREFIXES):
            continue
        for prefix in CODE_DIRTY_PREFIXES:
            if path.startswith(prefix) or path == prefix.rstrip("/"):
                return True
    return False


def _read_graph(root: Path) -> dict[str, Any]:
    """读 graph.db。file_missing / sqlite_error / node_count / git_head_sha。"""
    db = root / ".code-review-graph" / "graph.db"
    if not db.is_file():
        return {
            "file_missing": True,
            "sqlite_error": False,
            "node_count": 0,
            "git_head_sha": None,
        }
    try:
        uri = db.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=SQLITE_TIMEOUT_SEC)
        try:
            cur = con.execute("SELECT COUNT(*) FROM nodes")
            node_count = int(cur.fetchone()[0])
            cur = con.execute(
                "SELECT value FROM metadata WHERE key = 'git_head_sha'"
            )
            row = cur.fetchone()
            git_head_sha = row[0] if row else None
        finally:
            con.close()
    except sqlite3.Error:
        return {
            "file_missing": False,
            "sqlite_error": True,
            "node_count": None,
            "git_head_sha": None,
        }
    return {
        "file_missing": False,
        "sqlite_error": False,
        "node_count": node_count,
        "git_head_sha": git_head_sha,
    }


def _clip_one_line(line: str) -> str:
    if len(line) <= ONE_LINE_MAX:
        return line
    return line[:ONE_LINE_MAX]


def _one_line(
    status: str,
    *,
    node_count: int | None,
    head_sha: str | None,
    commits_behind: int | None,
    stale_weight: str | None,
    missing_sha: bool,
) -> str:
    if status == "empty":
        return _clip_one_line("代码地图: empty n=0 ← 禁止空图架构结论；正门=AGENTS")
    if status == "error":
        return _clip_one_line("代码地图: error ← 状态未知，禁止假装 ready")
    if status == "ready":
        short = (head_sha or "")[:7]
        n = 0 if node_count is None else node_count
        return _clip_one_line(f"代码地图: ready n={n} @{short}")
    if missing_sha:
        return _clip_one_line("代码地图: stale 无 git_head_sha ← 勿当当前架构")
    n = 0 if commits_behind is None else commits_behind
    if stale_weight == "heavy":
        return _clip_one_line(
            f"代码地图: stale 落后{n}且触及 intelligence/ ← 勿当当前架构"
        )
    return _clip_one_line(f"代码地图: stale 落后{n} commit，仍可搜")


def _stale_weight(root: Path, built_sha: str, commits_behind: int | None) -> str:
    if commits_behind is not None and commits_behind >= STALE_HEAVY_MIN_COMMITS:
        return "heavy"
    names = _git_ok(root, "diff", "--name-only", f"{built_sha}..HEAD")
    if names:
        for path in names.splitlines():
            if any(path.startswith(p) for p in STALE_HEAVY_PATHS):
                return "heavy"
    return "light"


def collect_status(root: Path) -> tuple[dict[str, Any], int]:
    graph = _read_graph(root)
    dirty = _worktree_dirty_code(root) if _is_git_work_tree(root) else False
    head_sha = _git_ok(root, "rev-parse", "HEAD") if _is_git_work_tree(root) else None

    def payload(
        status: str,
        exit_code: int,
        *,
        node_count: int | None,
        git_head_sha: str | None = None,
        commits_behind: int | None = None,
        stale_weight: str | None = None,
        missing_sha: bool = False,
    ) -> tuple[dict[str, Any], int]:
        one = _one_line(
            status,
            node_count=node_count,
            head_sha=head_sha,
            commits_behind=commits_behind,
            stale_weight=stale_weight,
            missing_sha=missing_sha,
        )
        body = {
            "status": status,
            "node_count": 0 if node_count is None and status == "empty" else node_count,
            "git_head_sha": git_head_sha,
            "head_sha": head_sha,
            "head_matches_build": bool(
                git_head_sha and head_sha and git_head_sha == head_sha
            ),
            "commits_behind": commits_behind,
            "stale_weight": stale_weight,
            "worktree_dirty_code": dirty,
            "one_line": one,
        }
        return body, exit_code

    if graph["sqlite_error"]:
        return payload("error", EXIT_ERROR, node_count=None)

    node_count = int(graph["node_count"] or 0)
    if graph["file_missing"] or node_count == 0:
        return payload("empty", EXIT_EMPTY, node_count=0, git_head_sha=graph["git_head_sha"])

    if not _is_git_work_tree(root) or head_sha is None:
        return payload("error", EXIT_ERROR, node_count=node_count)

    built = graph["git_head_sha"]
    if not built:
        return payload(
            "stale",
            EXIT_STALE,
            node_count=node_count,
            git_head_sha=None,
            missing_sha=True,
            stale_weight="heavy",
        )
    if built != head_sha:
        behind_s = _git_ok(root, "rev-list", "--count", f"{built}..HEAD")
        behind = int(behind_s) if behind_s is not None and behind_s.isdigit() else None
        weight = _stale_weight(root, built, behind)
        return payload(
            "stale",
            EXIT_STALE,
            node_count=node_count,
            git_head_sha=built,
            commits_behind=behind,
            stale_weight=weight,
        )
    return payload(
        "ready",
        EXIT_READY,
        node_count=node_count,
        git_head_sha=built,
        commits_behind=0,
        stale_weight=None,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code_map.py",
        description="本地代码地图门面（status / query / build）。PR1 仅 status。",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_status = sub.add_parser("status", help="空图 fail-closed 的新鲜度")
    flags = p_status.add_mutually_exclusive_group()
    flags.add_argument("--json", action="store_true", help="打印 JSON")
    flags.add_argument("--one-line", action="store_true", help="打印 ≤80 字一行")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd != "status":
        parser.error(f"invalid choice: {args.cmd}")
    payload, code = collect_status(repo_root())
    if args.json:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(payload["one_line"] + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
