#!/usr/bin/env python3
"""Worktree 合入看板：从 ``git cherry`` 生成，不手抄第二份清单。

失败形状
--------
多 session 并发留下几十棵 worktree。人写的 ``inflight/main.md`` 和项目笔记
「交接记录」会漂（写了「可合未合」之后合进去也不回写）。``git rev-list`` 的
ahead 数也会骗人：同一补丁以 squash / cherry-pick 进了 main，hash 不同仍算
超前。``git cherry`` 比的是补丁，全是 ``-`` 就是已经在基线里。

本脚本只打印。**绝不** ``worktree remove``。

SessionStart 只跑 ``--this``（当前 HEAD 一次 cherry，预算内两三行）。全仓
看板是人/agent 主动跑，不灌进每次会话。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LEDGER_NAME = "deploy-ledger.jsonl"
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
CODE_DIRTY_SKIP_PREFIXES = ("market_feature_store/exports/",)


@dataclass(frozen=True)
class TreeRow:
    path: str
    head: str
    branch: str
    cherry_plus: int
    cherry_minus: int
    ahead: int
    behind: int
    in_main: bool
    dirty: bool
    code_dirty: bool
    dirty_n: int
    kind: str
    subjects: tuple[str, ...] = field(default_factory=tuple)


def _git(args: list[str], *, cwd: str | None, timeout: float) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return completed.returncode, (completed.stdout or "").strip()


def resolve_base(cwd: str, timeout: float) -> str:
    """合入基线：日常远程是 gitea/main，没有再退 origin/main、main。"""

    for candidate in ("gitea/main", "origin/main", "main"):
        code, _ = _git(["rev-parse", "--verify", "--quiet", candidate], cwd=cwd, timeout=timeout)
        if code == 0:
            return candidate
    return "HEAD"


def parse_worktree_porcelain(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in text.splitlines():
        if raw.startswith("worktree "):
            if current:
                rows.append(current)
            current = {"path": raw.split(" ", 1)[1]}
        elif raw.startswith("HEAD "):
            current["head"] = raw.split(" ", 1)[1]
        elif raw.startswith("branch "):
            current["branch"] = raw.split(" ", 1)[1].removeprefix("refs/heads/")
        elif raw == "detached":
            current["branch"] = "(detached)"
    if current:
        rows.append(current)
    return rows


def tree_kind(path: str, main_checkout: str) -> str:
    posix = path.replace("\\", "/")
    if "/.finance-runtime/finance-workspace-" in posix:
        return "prod-snapshot"
    if "/fwp-wt-" in posix or "/.worktrees/" in posix:
        return "dev-wt"
    if os.path.abspath(path) == os.path.abspath(main_checkout):
        return "main-checkout"
    return "other"


def _status_paths(porcelain: str) -> list[str]:
    paths: list[str] = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        rel = line[3:].strip().strip('"')
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        paths.append(rel)
    return paths


def is_code_dirty(paths: list[str]) -> bool:
    for rel in paths:
        if any(rel.startswith(skip) for skip in CODE_DIRTY_SKIP_PREFIXES):
            continue
        if any(rel.startswith(prefix) for prefix in CODE_DIRTY_PREFIXES):
            return True
    return False


def cherry_counts(head: str, base: str, *, cwd: str, timeout: float) -> tuple[int, int, bool]:
    code, _ = _git(["merge-base", "--is-ancestor", head, base], cwd=cwd, timeout=timeout)
    if code == 0:
        return 0, 0, True
    code, out = _git(["cherry", base, head], cwd=cwd, timeout=timeout)
    if code != 0:
        return 0, 0, False
    plus = minus = 0
    for line in out.splitlines():
        if line.startswith("+ "):
            plus += 1
        elif line.startswith("- "):
            minus += 1
    return plus, minus, plus == 0


def unique_subjects(head: str, base: str, *, cwd: str, timeout: float, limit: int = 3) -> tuple[str, ...]:
    """只列 cherry+ 的补丁；``base..head`` 的 log 会把已等价进 main 的 hash 也算进去。"""

    code, out = _git(["cherry", "-v", base, head], cwd=cwd, timeout=timeout)
    if code != 0 or not out:
        return ()
    plus_lines = [line[2:] for line in out.splitlines() if line.startswith("+ ")]
    if len(plus_lines) > 80:
        return (f"（独特提交 {len(plus_lines)} 笔，略）",)
    return tuple(plus_lines[:limit])


def classify_worktree(
    spec: dict[str, str],
    *,
    base: str,
    main_checkout: str,
    timeout: float,
) -> TreeRow | None:
    path = spec.get("path") or ""
    head = spec.get("head") or ""
    if not path or not head:
        return None
    plus, minus, in_main = cherry_counts(head, base, cwd=path, timeout=timeout)
    _, ahead_s = _git(["rev-list", "--count", f"{base}..{head}"], cwd=path, timeout=timeout)
    _, behind_s = _git(["rev-list", "--count", f"{head}..{base}"], cwd=path, timeout=timeout)
    _, status = _git(["status", "--porcelain"], cwd=path, timeout=timeout)
    paths = _status_paths(status)
    subjects: tuple[str, ...] = ()
    if plus:
        subjects = unique_subjects(head, base, cwd=path, timeout=timeout)
    return TreeRow(
        path=path,
        head=head,
        branch=spec.get("branch") or "?",
        cherry_plus=plus,
        cherry_minus=minus,
        ahead=int(ahead_s or 0),
        behind=int(behind_s or 0),
        in_main=in_main,
        dirty=bool(paths),
        code_dirty=is_code_dirty(paths),
        dirty_n=len(paths),
        kind=tree_kind(path, main_checkout),
        subjects=subjects,
    )


def _last_switch_unix(ledger: Path, port: int) -> float:
    """账本里该 port 末次 ``switch`` 行的时刻；没有就 -inf（排在任何有记录的后面）。

    只认写入侧落的 ``unix``（``deploy_ledger.record`` 每行都写），不解析 ``ts``
    字串——两个字段同源，少一套解析就少一处漂。
    """

    latest = float("-inf")
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return latest
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("action") != "switch":
            continue
        if str(row.get("port") or "") != str(port):
            continue
        try:
            unix = float(row.get("unix"))
        except (TypeError, ValueError):
            continue
        latest = max(latest, unix)
    return latest


def resolve_ledger_path(
    repo_root: Path, *, timeout: float = 2.0, port: int = 8792
) -> Path:
    """读取侧解析。唯一的默认家是 ``~/.finance-runtime/deploy-ledger.jsonl``，与
    ``intelligence.runtime.deploy_ledger.default_ledger_path`` 同址——SessionStart 在宿主
    python3 下跑、不 import 包，所以这里抄址不抄模块，改址两处一起改。

    失败形状（2026-09-08 实测）：账本有两个家——主检出树 ``state/`` 那份（带 ``FINANCE_WS``
    的生产启动与部署脚本写的）与 ``~/.finance-runtime`` 那份（链切规程显式 ``--ledger`` 写的）。
    按固定顺序取第一份，SessionStart 就把 8792 报成一天前的 rev，而生产早切了两次。
    2026-09-09 工单 #44 把写入侧收成一个家；读取侧过渡期仍看三个**旧家**（``$FINANCE_WS/state/``、
    ``<repo_root>/state/``、git common-dir 父目录的 ``state/``）——切流前旧代码的生产进程还往那儿
    写 startup。存在的候选里取该 port 末次 switch 最新的那份（#675 的读法，不退）；都没有
    switch 行时唯一家优先。``audit_deploy_ledger.py migrate-homes --apply`` 把旧家并入后旧文件
    改名 ``.migrated-*``，不再被本函数看见。
    """

    override = os.environ.get("FINANCE_DEPLOY_LEDGER", "").strip()
    if override:
        return Path(override).expanduser()
    home = Path.home() / ".finance-runtime" / LEDGER_NAME
    candidates: list[Path] = [home]
    finance_ws = os.environ.get("FINANCE_WS", "").strip()
    if finance_ws:
        candidates.append(Path(finance_ws).expanduser() / "state" / LEDGER_NAME)
    candidates.append(repo_root / "state" / LEDGER_NAME)
    code, common = _git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=str(repo_root),
        timeout=timeout,
    )
    if code == 0 and common:
        candidates.append(Path(common).resolve().parent / "state" / LEDGER_NAME)
    unique: list[Path] = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    existing = [path for path in unique if path.is_file()]
    if not existing:
        return home
    # 稳定排序：时刻相同（含都没有 switch 行）时唯一家在前、旧家按老顺序。
    return max(existing, key=lambda path: _last_switch_unix(path, port))


def last_switch_for_port(ledger: Path, port: int = 8792) -> dict[str, Any] | None:
    if not ledger.is_file():
        return None
    matched: dict[str, Any] | None = None
    fallback: dict[str, Any] | None = None
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("action") != "switch":
            continue
        if not row.get("rev"):
            continue
        fallback = row
        if row.get("port") == port or str(row.get("port") or "") == str(port):
            matched = row
    return matched or fallback


def display_path(path: str) -> str:
    home = str(Path.home())
    if path.startswith(home + os.sep) or path.startswith(home + "/"):
        return "~" + path[len(home) :]
    return path


def format_board(rows: list[TreeRow], *, base: str, base_sha: str) -> str:
    unique = [row for row in rows if row.cherry_plus > 0]
    prune = [
        row
        for row in rows
        if row.in_main and row.kind == "dev-wt" and not row.code_dirty
    ]
    snapshots = [row for row in rows if row.kind == "prod-snapshot"]
    leftover_dirty = [
        row
        for row in rows
        if row.in_main and row.kind == "dev-wt" and row.code_dirty
    ]
    lines = [
        f"基准 {base}={base_sha[:12]}  （合入看 cherry+，不是 ahead 提交数）",
        f"树 {len(rows)} 棵 · 还有补丁 {len(unique)} · 补丁已在基线的 dev 树 {len(prune)}",
        "",
        "【还有补丁 — 真没合】",
    ]
    if not unique:
        lines.append("  （无）")
    for row in sorted(unique, key=lambda item: (item.cherry_plus, item.behind, item.branch)):
        flags = []
        if row.code_dirty:
            flags.append("CODE_DIRTY")
        elif row.dirty:
            flags.append("dirty")
        if row.behind:
            flags.append(f"behind:{row.behind}")
        flag = " ".join(flags)
        lines.append(
            f"  +{row.cherry_plus} -{row.cherry_minus}  {row.head[:12]}  "
            f"{row.branch}  {flag}".rstrip()
        )
        lines.append(f"      {display_path(row.path)}")
        for subject in row.subjects:
            lines.append(f"      · {subject}")
    lines += ["", "【补丁已在基线 — 树可拆，本脚本不拆】"]
    if not prune:
        lines.append("  （无）")
    for row in sorted(prune, key=lambda item: item.branch):
        extra = f"  dirty:{row.dirty_n}" if row.dirty else ""
        lines.append(
            f"  {row.head[:12]}  {row.branch}{extra}  {display_path(row.path)}"
        )
    if leftover_dirty:
        lines += ["", "【补丁已在基线，但还有代码脏文件 — 先认领再拆】"]
        for row in leftover_dirty:
            lines.append(
                f"  {row.head[:12]}  {row.branch}  {display_path(row.path)}"
            )
    lines += ["", "【生产快照】只留当前 8792 + 一个回滚锚；本脚本不拆"]
    for row in snapshots:
        lines.append(
            f"  {row.head[:12]}  dirty={str(row.dirty).lower()}  {display_path(row.path)}"
        )
    lines += [
        "",
        "拆树（需你确认）：git worktree remove <path>",
        "合入状态不要写进 inflight/main.md 或项目笔记交接记录，下次跑本脚本。",
    ]
    return "\n".join(lines) + "\n"


def this_tree_lines(
    *,
    cwd: str,
    base: str,
    base_sha: str,
    timeout: float,
    repo_root: Path,
) -> list[str]:
    code, head = _git(["rev-parse", "HEAD"], cwd=cwd, timeout=timeout)
    if code != 0 or not head:
        return []
    plus, minus, in_main = cherry_counts(head, base, cwd=cwd, timeout=timeout)
    if in_main:
        merge = f"合入: 本枝补丁已在 {base}={base_sha[:12]}（cherry+0）"
    else:
        merge = (
            f"合入: 本枝 cherry+{plus} / cherry-{minus} vs {base}={base_sha[:12]}"
        )
    lines = [merge]
    switch = last_switch_for_port(resolve_ledger_path(repo_root, timeout=timeout))
    if switch:
        rev = str(switch.get("rev") or "")
        port = switch.get("port")
        same = rev.startswith(base_sha[:12]) or base_sha.startswith(rev[:12])
        relation = "与 main 一致" if same else "与 main 不是同一份"
        port_bit = f" port={port}" if port is not None else ""
        lines.append(f"8792: {rev[:12]}（ledger switch{port_bit}；{relation}）")
    lines.append("看板: python3 scripts/worktree_board.py")
    return lines


def collect_rows(*, cwd: str, timeout: float) -> tuple[str, str, str, list[TreeRow]]:
    base = resolve_base(cwd, timeout)
    _, base_sha = _git(["rev-parse", base], cwd=cwd, timeout=timeout)
    _, common = _git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=cwd,
        timeout=timeout,
    )
    main_checkout = str(Path(common).resolve().parent) if common else cwd
    _, porcelain = _git(["worktree", "list", "--porcelain"], cwd=cwd, timeout=timeout)
    rows: list[TreeRow] = []
    for spec in parse_worktree_porcelain(porcelain):
        row = classify_worktree(
            spec, base=base, main_checkout=main_checkout, timeout=timeout
        )
        if row is not None:
            rows.append(row)
    return base, base_sha, main_checkout, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--json", action="store_true", help="机器可读")
    parser.add_argument(
        "--this",
        action="store_true",
        help="只报当前 HEAD（给 SessionStart，不扫全仓）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="单次 git 超时秒数",
    )
    args = parser.parse_args(argv)
    cwd = os.getcwd()
    repo_root = Path(cwd)
    timeout = max(1.0, float(args.timeout))
    if args.this:
        timeout = min(timeout, 8.0)
        base = resolve_base(cwd, timeout)
        _, base_sha = _git(["rev-parse", base], cwd=cwd, timeout=timeout)
        for line in this_tree_lines(
            cwd=cwd,
            base=base,
            base_sha=base_sha,
            timeout=timeout,
            repo_root=repo_root,
        ):
            print(line)
        return 0
    base, base_sha, _main_checkout, rows = collect_rows(cwd=cwd, timeout=timeout)
    if args.json:
        payload = {
            "base": base,
            "base_sha": base_sha,
            "trees": [asdict(row) for row in rows],
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    sys.stdout.write(format_board(rows, base=base, base_sha=base_sha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
