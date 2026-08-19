#!/usr/bin/env python3
"""本地代码地图门面。

跨 harness 的查询正门是本 CLI，不是 MCP。PR1 只实现 ``status``：
空图 / 零节点 fail-closed，禁止把空壳写成架构结论。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
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


DOORS_HIT_CAP = 20
TITLE_MAX = 40
RETIRED_RE = re.compile(r"退役|禁止|已废弃|刻意|不要跑|停用")
HEADING_RE = re.compile(r"^(#{1,6})\s+")
VAULT_GRAPH = Path(".agent-memory") / "10_knowledge" / "finance-agent-capability-graph.md"
VAULT_AUDIT = Path(".agent-memory") / "scripts" / "graph_audit.py"
EMPTY_NEXT_ACTION = (
    "structure 层不可用：禁止把空图写成架构结论。正门见 layers.doors。"
    "python3 scripts/code_map.py build --full"
)
UVX_HINT = "需要 uv/uvx（https://docs.astral.sh/uv/），不要改去直调 MCP build"
FULL_POSTPROCESS_MIN_FILES = 30


def tokenize(question: str) -> list[str]:
    """按空白与标点切 token，但保留 [_-]。ASCII 做 casefold；丢掉长度 < 2。"""
    tokens: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        raw = "".join(buf)
        folded = raw.casefold() if raw.isascii() else raw
        buf.clear()
        if len(folded) >= 2:
            tokens.append(folded)

    for ch in question:
        if ch in "_-" or ch.isalnum():
            buf.append(ch)
        else:
            flush()
    flush()
    return tokens


def _tokens_in_line(line: str, tokens: list[str]) -> list[str]:
    hay = line.casefold()
    return [tok for tok in tokens if tok in hay or tok in line]


def _heading_level(line: str) -> int | None:
    m = HEADING_RE.match(line)
    return len(m.group(1)) if m else None


def _retired_for(line: str) -> list[str]:
    if RETIRED_RE.search(line):
        return [line]
    return []


def _door_hit(rel: str, excerpt: str, matched: list[str], symbol: str | None = None) -> dict[str, Any]:
    return {
        "title": excerpt[:TITLE_MAX],
        "path": rel,
        "symbol": symbol,
        "excerpt": excerpt,
        "retired": _retired_for(excerpt),
        "_matched": matched,
    }


def _source_rank(rel: str) -> int:
    if rel == "AGENTS.md":
        return 0
    if rel == "CLAUDE.md":
        return 1
    if rel.startswith(".agent-memory/"):
        return 2
    return 3


def _scan_markdown_doors(root: Path, rel: str, tokens: list[str]) -> list[dict[str, Any]]:
    path = root / rel
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        matched = _tokens_in_line(raw, tokens)
        if matched and stripped and stripped not in seen:
            hits.append(_door_hit(rel, stripped, matched))
            seen.add(stripped)
        level = _heading_level(raw) if matched else None
        if level is not None:
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                nxt_level = _heading_level(nxt)
                if nxt_level is not None and nxt_level <= level:
                    break
                body = nxt.strip()
                if body and body not in seen:
                    hits.append(_door_hit(rel, body, matched))
                    seen.add(body)
                j += 1
            i = j
            continue
        i += 1
    return hits


def _scan_spec_titles(root: Path, tokens: list[str]) -> list[dict[str, Any]]:
    specs_dir = root / "docs" / "superpowers" / "specs"
    if not specs_dir.is_dir():
        return []
    hits: list[dict[str, Any]] = []
    for path in sorted(specs_dir.glob("*.md")):
        rel = path.relative_to(root).as_posix()
        stem = path.stem
        heading = ""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    heading = line.strip()
                    break
        except OSError:
            continue
        for excerpt in (stem, heading):
            if not excerpt:
                continue
            matched = _tokens_in_line(excerpt, tokens)
            if matched:
                hits.append(_door_hit(rel, excerpt, matched))
    return hits


def _fallback_parse_node_table(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("## 节点清单"):
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"节点", ""}:
            continue
        if set(cells[0]) <= {"-", " "}:
            continue
        rows.append((cells[0], cells[1], cells[2]))
    return rows


def _scan_vault_doors(root: Path, tokens: list[str]) -> tuple[str, list[dict[str, Any]]]:
    graph = root / VAULT_GRAPH
    if not graph.is_file():
        return "unavailable", []
    text = graph.read_text(encoding="utf-8")
    rows: list[tuple[str, str, str]] = []
    audit = root / VAULT_AUDIT
    parse = None
    if audit.is_file():
        spec = importlib.util.spec_from_file_location("_code_map_graph_audit", audit)
        if spec is not None and spec.loader is not None:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            parse = getattr(mod, "parse_node_table", None)
    if parse is not None:
        for node, _repo, specs in parse(text):
            paths = " ".join(getattr(s, "path", str(s)) for s in specs)
            rows.append((node, paths, f"{node} {paths}"))
    else:
        for node, _repo, path_cell in _fallback_parse_node_table(text):
            rows.append((node, path_cell, f"{node} {path_cell}"))
    rel = VAULT_GRAPH.as_posix()
    hits: list[dict[str, Any]] = []
    for node, path_cell, excerpt in rows:
        matched = _tokens_in_line(node, tokens) + _tokens_in_line(path_cell, tokens)
        # 去重 token 但保序
        seen_tok: list[str] = []
        for tok in matched:
            if tok not in seen_tok:
                seen_tok.append(tok)
        if seen_tok:
            hits.append(_door_hit(rel, excerpt.strip(), seen_tok))
    return "ok", hits


def search_doors(root: Path, tokens: list[str]) -> tuple[str, list[dict[str, Any]]]:
    vault_state, vault_hits = _scan_vault_doors(root, tokens)
    hits = (
        _scan_markdown_doors(root, "AGENTS.md", tokens)
        + _scan_markdown_doors(root, "CLAUDE.md", tokens)
        + vault_hits
        + _scan_spec_titles(root, tokens)
    )
    hits.sort(
        key=lambda h: (
            -len(set(h["_matched"])),
            _source_rank(h["path"]),
            h["path"],
            h["excerpt"],
        )
    )
    trimmed = hits[:DOORS_HIT_CAP]
    for hit in trimmed:
        hit.pop("_matched", None)
    return vault_state, trimmed


class UvxMissing(Exception):
    """PATH 上没有 uvx。门面 fail closed，不猜测 Python API。"""


def _uvx_path() -> str | None:
    return shutil.which("uvx")


def run_crg_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    if any(part in {"init", "install"} for part in args):
        raise RuntimeError("禁止 code-review-graph init|install")
    uvx = _uvx_path()
    if not uvx:
        raise UvxMissing(UVX_HINT)
    return subprocess.run(
        [uvx, "--from", "code-review-graph", "code-review-graph", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _is_path_like(value: str) -> bool:
    return bool(value) and ("/" in value or "\\" in value)


def _relpath(path: str, root: Path) -> str:
    raw = Path(path)
    if not raw.is_absolute():
        raw = root / raw
    try:
        return raw.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).name or Path(path).as_posix()


def search_graph(question: str, cwd: Path | None = None) -> list[dict[str, Any]]:
    """可搜时才调用。解析 CRG search 的 JSON results，不按行切开。"""
    root = cwd or repo_root()
    try:
        proc = run_crg_cli(["search", question], root)
    except UvxMissing:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    rows = data.get("results") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    hits: list[dict[str, Any]] = []
    for item in rows[:DOORS_HIT_CAP]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        file_path = str(item.get("file_path") or "")
        excerpt = str(item.get("qualified_name") or item.get("signature") or name)
        rel = _relpath(file_path, root) if file_path else ""
        if not rel and _is_path_like(name):
            rel = _relpath(name, root)
        symbol = None if _is_path_like(name) else (name or None)
        title_src = symbol or Path(rel).name or Path(name).name or excerpt
        hits.append(
            {
                "title": title_src[:TITLE_MAX],
                "path": rel,
                "symbol": symbol,
                "excerpt": excerpt,
                "retired": [],
            }
        )
    return hits


def _doors_claim(tokens: list[str], hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "missing"
    hay = "\n".join(h["excerpt"] for h in hits)
    hay_cf = hay.casefold()
    if tokens and all((tok in hay_cf or tok in hay) for tok in tokens):
        return "ok"
    return "partial"


def collect_query(root: Path, question: str) -> tuple[dict[str, Any], int]:
    status_payload, _status_code = collect_status(root)
    status = status_payload["status"]
    tokens = tokenize(question)
    vault_state, door_hits = search_doors(root, tokens)
    doors_state = "ok" if door_hits else "missing"

    if status == "empty":
        structure_state, structure_hits = "refused_empty", []
    elif status == "error":
        structure_state, structure_hits = "refused_error", []
    else:
        structure_hits = search_graph(question, root)
        if status == "stale":
            structure_state = "stale"
        elif structure_hits:
            structure_state = "ok"
        else:
            structure_state = "missing"

    if structure_state in {"refused_empty", "refused_error"}:
        structure_claim = "unavailable"
    else:
        structure_claim = structure_state if structure_state != "ok" else (
            "ok" if structure_hits else "missing"
        )

    next_action = EMPTY_NEXT_ACTION if status in {"empty", "error"} else "正门见 layers.doors。"
    payload = {
        "query": question,
        "status": status,
        "vault": vault_state,
        "layers": {
            "doors": {"state": doors_state, "hits": door_hits},
            "structure": {"state": structure_state, "hits": structure_hits},
            "narrative": {"state": "missing", "hits": []},
        },
        "conflicts": [],
        "completeness_claim": {
            "doors": _doors_claim(tokens, door_hits),
            "structure": structure_claim,
            "narrative": "unavailable",
            "recall": "untested",
        },
        "next_action": next_action,
    }
    return payload, 0


def _read_receipt(root: Path) -> dict[str, Any]:
    path = root / ".code-review-graph" / "status.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_receipt(root: Path, **fields: Any) -> None:
    folder = root / ".code-review-graph"
    folder.mkdir(parents=True, exist_ok=True)
    current = _read_receipt(root)
    current.update(fields)
    (folder / "status.json").write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _hot_file_count(root: Path, since_sha: str) -> int:
    names = _git_ok(root, "diff", "--name-only", f"{since_sha}..HEAD")
    if not names:
        return 0
    return sum(
        1
        for path in names.splitlines()
        if any(path.startswith(prefix) for prefix in STALE_HEAVY_PATHS)
    )


def collect_build(
    root: Path,
    *,
    full: bool = False,
    postprocess: str | None = None,
) -> tuple[dict[str, Any], int]:
    if not _is_git_work_tree(root):
        sys.stderr.write("code_map build 拒绝：不是 git 工作树，避免 walk 扫到密钥\n")
        return {"ok": False, "error": "not_git"}, 2
    if not (root / ".code-review-graphignore").is_file():
        sys.stderr.write("code_map build 拒绝：缺少 .code-review-graphignore\n")
        return {"ok": False, "error": "no_ignore"}, 2
    if _uvx_path() is None:
        sys.stderr.write(UVX_HINT + "\n")
        return {"ok": False, "error": "no_uvx"}, 2

    receipt = _read_receipt(root)
    built_at = receipt.get("built_at_sha")
    if not isinstance(built_at, str) or not built_at:
        built_at = None
    use_full = full or built_at is None

    if postprocess is None:
        if use_full:
            postprocess = "full"
        elif built_at and _hot_file_count(root, built_at) >= FULL_POSTPROCESS_MIN_FILES:
            postprocess = "full"
        else:
            postprocess = "minimal"

    if use_full:
        args = ["build"]
    else:
        args = ["update", "--base", built_at]
    if postprocess == "minimal":
        args.append("--skip-flows")
    elif postprocess == "none":
        args.append("--skip-postprocess")

    try:
        proc = run_crg_cli(args, root)
    except UvxMissing:
        sys.stderr.write(UVX_HINT + "\n")
        return {"ok": False, "error": "no_uvx"}, 2
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout or "code-review-graph 失败\n")
        return {"ok": False, "error": "crg", "argv": args}, proc.returncode or 2

    graph = _read_graph(root)
    head = _git_ok(root, "rev-parse", "HEAD")
    node_count = graph["node_count"] if graph["node_count"] is not None else 0
    _write_receipt(
        root,
        built_at_sha=head,
        node_count=node_count,
        postprocess=postprocess,
        wiki_generated=False,
        worktree_dirty_code=_worktree_dirty_code(root),
    )
    return {"ok": True, "argv": args, "built_at_sha": head, "node_count": node_count}, 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code_map.py",
        description="本地代码地图门面（status / query / build）。",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_status = sub.add_parser("status", help="空图 fail-closed 的新鲜度")
    flags = p_status.add_mutually_exclusive_group()
    flags.add_argument("--json", action="store_true", help="打印 JSON")
    flags.add_argument("--one-line", action="store_true", help="打印 ≤80 字一行")
    p_query = sub.add_parser("query", help="先正门、再结构、再叙事")
    p_query.add_argument("question", help="用户问题 / 拟实现的能力名")
    p_query.add_argument("--json", action="store_true", help="打印 JSON（query 默认就是 JSON）")
    p_build = sub.add_parser("build", help="包装 CRG build/update，禁止 init")
    p_build.add_argument("--full", action="store_true", help="忽略收据，跑全量 build")
    p_build.add_argument(
        "--postprocess",
        choices=("full", "minimal", "none"),
        default=None,
        help="门面旗标，翻译成 --skip-flows / --skip-postprocess",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "status":
        payload, code = collect_status(repo_root())
        if args.json:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(payload["one_line"] + "\n")
        return code
    if args.cmd == "query":
        payload, code = collect_query(repo_root(), args.question)
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return code
    if args.cmd == "build":
        payload, code = collect_build(
            repo_root(),
            full=args.full,
            postprocess=args.postprocess,
        )
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return code
    parser.error(f"invalid choice: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
