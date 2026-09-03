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


def resolve_ledger_path(repo_root: Path, *, timeout: float = 2.0) -> Path:
    """覆盖序对齐 ``intelligence.runtime.deploy_ledger.resolve_ledger_path``。

    SessionStart 必须能在宿主 python3、不 import 包的情况下跑，所以这里抄序
    不抄模块。Hook 环境通常没有 ``FINANCE_WS``，附属 worktree 也没有数据仓
    里的 ledger；多探一步 git common-dir 的父目录（主检出树），改覆盖序时
    与 ``deploy_ledger`` 一起改。
    """

    override = os.environ.get("FINANCE_DEPLOY_LEDGER", "").strip()
    if override:
        return Path(override).expanduser()
    finance_ws = os.environ.get("FINANCE_WS", "").strip()
    if finance_ws:
        return Path(finance_ws).expanduser() / "state" / LEDGER_NAME
    candidates: list[Path] = [repo_root / "state" / LEDGER_NAME]
    code, common = _git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=str(repo_root),
        timeout=timeout,
    )
    if code == 0 and common:
        candidates.append(Path(common).resolve().parent / "state" / LEDGER_NAME)
    candidates.append(Path.home() / ".finance-runtime" / LEDGER_NAME)
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def last_switch_for_port(
    ledger: Path, port: int = 8792
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """返回 ``(该 port 末次 switch, 比它更新且没记 port 的 switch)``。

    第二项不为 None 时，第一项**已经不能代表该 port 的现状**——账本里更新的那次
    切换没写 port，读取侧无从归属。这里不替它猜：``deploy_ledger.infer_port`` 在
    写入侧就明写「认不出来就 None，不猜 8792」，读取侧补一个猜测只是把同一个猜测
    藏得更深，而且会猜错——账本里 8796 的末次 switch 后面同样跟着未归属行，按
    「取最新」归属会把 8792 的 rev 报成 8796 的。
    """

    if not ledger.is_file():
        return None, None
    matched: dict[str, Any] | None = None
    unattributed: dict[str, Any] | None = None
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return None, None
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
        row_port = row.get("port")
        if row_port is None or str(row_port).strip() == "":
            unattributed = row
        elif str(row_port) == str(port):
            # 该 port 有了更新的确凿行，之前那条未归属行不再影响判断
            matched = row
            unattributed = None
    return matched, unattributed


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
    switch, unattributed = last_switch_for_port(
        resolve_ledger_path(repo_root, timeout=timeout)
    )
    if unattributed is not None:
        # 报「不知道」而不是报一个更旧的 rev：后者每个会话都读起来像真值。
        newer = str(unattributed.get("rev") or "")[:12]
        known = str((switch or {}).get("rev") or "")[:12]
        known_bit = f"，末次带 port=8792 的是 {known}" if known else ""
        lines.append(
            f"8792: 账本判不出——更新的 switch {newer} 未记 port{known_bit}"
            "；取真值 scripts/audit_deploy_ledger.py check"
        )
    elif switch:
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
